# Booking Flow, Payments, Receipts & Payouts

## Context

The API today can onboard braiders, publish their style menu with prices, compute availability slots, and onboard them onto Stripe Connect Express — but **nothing can actually be booked or paid for**. `availability/router.py` admits it in its own docstring: _"Doesn't yet exclude already-booked times (there's no booking system yet)."_ `PlatformSettings` (10% fee / 20% VAT) has zero consumers.

This project builds the missing half: a **public booking calculator** that prices a job, an **authenticated booking** that consumes that calculation and takes money, a **split deposit/balance payment lifecycle** that survives bookings made 9 months out, **localized HTML receipts**, and **delayed payouts** to braiders after the service is delivered.

**Confirmed product decisions** (do not re-litigate):

|                   |                                                                                                                                                                                        |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Platform fee      | **Customer-paid, added on top.** `subtotal → +10% fee → +VAT → total`. Braider receives `subtotal`. Approved example: 200 → fee 20 → VAT 44 → **customer pays 264, braider gets 200**. |
| Deposit           | **10% of the gross total**, a new `PlatformSettings` field (PERCENTAGE\|FIXED), seeded 10%, Redis-cached                                                                               |
| Payment timing    | Appointment **≤24h away → 100% upfront**. Otherwise **10% deposit now, balance auto-charged later**                                                                                    |
| Cancellation      | Deposit is **non-refundable**. Customer may cancel until **24h before**; inside 24h they cannot cancel                                                                                 |
| Forfeited deposit | **Braider receives their proportional share**; platform keeps its fee slice                                                                                                            |
| Confirmation      | **Instant** — no braider acceptance — but the braider **can cancel**, which fully refunds the customer                                                                                 |
| Receipts          | **Localized HTML only** (en/de/fr), emailed + viewable at a URL. No PDF, no new dependencies                                                                                           |
| VAT               | **Two independent rates** (`vat_on_service`, `vat_on_platform_fee`), both **seeded 20%** so the approved €264 reproduces exactly                                                       |

---

## Design corrections that shape the build

These were found by pressure-testing the obvious design. Each one is a real bug avoided.

1. **Gate booking on the braider being payable.** Discovery deliberately doesn't require `payment_setup_completed_at`, so a braider with _no Connect account at all_ is publicly visible. `POST /bookings` must 409 unless `charges_enabled AND payouts_enabled`. Otherwise you hold a customer's money for months and `Transfer.create` fails at release with no destination.

2. **Never schedule long-horizon work in Redis.** arq stores deferred jobs in a Redis sorted set; `conftest.py` literally calls `flushdb()`. A 9-month `_defer_until` would silently vanish on any restart or eviction. **The DB is the schedule** — `balance_charge_due_at` on `bookings`, driven by a sweeper cron. Same for reminders (`*_sent_at` columns).

3. **Separate the cancellation cutoff from the balance charge.** Firing the charge at the _exact_ cutoff instant guarantees contention. `cancellation_cutoff_at = starts_at - 24h`; `balance_charge_due_at = cutoff + 45min grace`. Both the cancel endpoint and the charge task take `SELECT … FOR UPDATE` and re-assert state; whichever commits first wins, the other no-ops. Also make the full-upfront threshold _wider_ (~26h) than the charge trigger, or a booking made at T-24h05m schedules a balance charge that is already nearly due.

4. **`nextval()` is not gapless** — a rolled-back transaction burns the number permanently, which contradicts the receipt-numbering requirement. Use a `receipt_counters(year, last_number)` row locked `FOR UPDATE` inside the receipt insert.

5. **VAT has two suppliers, not one.** The braider supplies €200 of hairdressing; the platform supplies €20 of intermediation. Blending them means charging VAT on a Kleinunternehmer's (§19 UStG) service that nobody may remit — and under §14c UStG, VAT wrongly shown is owed anyway. Two rates, two columns, `vat_total := sum` (never recomputed from a blended base).

6. **No transfer-reversal path = an open chargeback hole.** Disputes land 120+ days out, after payout. Add `booking_transfer_reversals` and attempt `Transfer.create_reversal` on `charge.dispute.created`. `PAYOUT_RELEASE_DELAY_HOURS = 48` covers the near-term window.

7. **Webhook dedupe is not durability.** Insert-first stops _duplicate_ delivery; it does nothing for _dropped_ or _out-of-order_ delivery, or a webhook landing before the API transaction committed. Needs: `booking_id`+`purpose` in PI `metadata` so the handler can resolve by metadata; `RECEIVED → PROCESSED` states (not commit-and-forget); and a `reconcile_stripe_payments_cron` safety net.

8. **Two Stripe webhook endpoints, two secrets.** Connect events (`account.updated`) and platform events (`payment_intent.*`) sign with different secrets. Add `stripe_payments_webhook_secret` + a second route. Also **pin `stripe.api_version`** — it's currently unset, so Stripe can reshape payloads under you.

9. **Compute pricing entirely in integer minor units.** `Numeric(10,2)` → `int` once at the top makes `deposit + balance == total` a provable invariant. `to_minor_units` must quantize _before_ scaling — never `int(d * 100)`. Pass `rounding=ROUND_HALF_UP` explicitly at every `quantize`; `getcontext()` is thread-local and won't apply inside `asyncio.to_thread`.

10. **Allocate the braider's split, don't compute it twice.** `share_deposit = round(subtotal * deposit / total)`, then `share_balance = subtotal - share_deposit`. Exact by construction, and each share is provably ≤ its charge (since `subtotal ≤ total`) — which is what makes `source_transaction` legal.

11. **Stripe's EUR minimum charge is €0.50.** Clamp the deposit to `[50, total]`; if the residual balance lands in `(0, 50)`, fold it in and charge 100% upfront.

12. **Mobile bookings need a customer address.** `travel_fee` is flat and `travel_radius_km` is currently decorative. Capture and snapshot the service address, validate distance against the radius (the `earthdistance` extension is already enabled in migration `7c3e9a1f5b2d`). `travel_fee IS NULL` means _free travel_, not an error.

13. **Off-session at 9 months: card expiry is the dominant failure, not SCA.** Read `card.exp_month/exp_year` at booking time and flag bookings whose card dies before the appointment. Set `payment_method_types=["card"]` explicitly — iDEAL/Bancontact/Sofort give no reusable off-session mandate. The mandate disclosure ("we will charge €237.60 on <date>") is a **network requirement**, and it's what makes the non-refundable deposit enforceable under the EU Consumer Rights Directive (Art. 16(l) exempts date-specific personal services from the 14-day withdrawal right).

14. **Smaller but real:** `EXCLUDE` violations are SQLSTATE `23P01` and abort the transaction — `await db.flush()` right after `db.add()` to surface it, then `rollback()` before any further query. Use `'[)'` range bounds or adjacent bookings falsely collide. Put `buffer_minutes` _inside_ the blocked range. Exactly 0-or-1 variation per booking (they're absolute-price alternatives, not additive). Consume a calculation atomically (`UPDATE … WHERE status='DRAFT' RETURNING id`). `arq` already owns `ctx["redis"]` and it is **not** `decode_responses=True` — use `ctx["cache_redis"]`.

---

## Architecture

```
app/core/
  money.py       to_minor_units / from_minor_units (quantize-then-scale)
  currency.py    Currency enum (EUR), country→currency map
  cache.py       get_json / set_json / delete   ← first cache helper in the repo

app/modules/bookings/
  pricing.py           PURE function, no I/O — the most testable artifact here
  models.py schemas.py repository.py service.py
  router.py            tag "Bookings"            /api/v1/bookings
  braider_router.py    tag "Braider - Bookings"  /api/v1/braiders/me/bookings
  tasks.py
  calculations/        tag "Booking Calculator"  /api/v1/booking-calculations
  payments/            client.py service.py webhook.py   (Stripe)
  receipts/            models.py service.py templates.py router.py
```

Follows the repo's existing nesting precedent (`braiders/payment_setup/`). Two routers in one module gives the two separate Swagger tags requested, exactly as `styles/` does with `router.py` + `admin_router.py`.

**Money type split** (document in a module docstring so it doesn't read as an accident):

- `bookings` / `booking_items` / `receipts` → `Numeric(10,2)` — repo convention, human-facing.
- `booking_payments` / `_refunds` / `_transfers` / `_reversals` → `BigInteger` minor units + `currency` — pure mirrors of Stripe objects, must be byte-exact.

---

## Pricing algorithm

`app/modules/bookings/pricing.py` — pure, no DB, no I/O. Everything in integer minor units.

```
minor(d)     = int(Decimal(d).quantize(Q2, ROUND_HALF_UP).scaleb(2))
pct(base, r) = int((Decimal(base) * Decimal(r) / 100).quantize(1, ROUND_HALF_UP))

1  SERVICE   variation price REPLACES base_price (absolute, not a delta). 0-or-1 only.
2  ADDONS    additive. is_required ones injected server-side, not deselectable.
3  TRAVEL    minor(travel_fee or 0) if is_mobile else 0
4  subtotal  = service_base + addons_total + travel        ← exactly what the braider earns
5  platform_fee = pct(subtotal, fee_value) | minor(fee_value)
6  vat_on_service      = pct(subtotal,     vat_service_rate)
   vat_on_platform_fee = pct(platform_fee, vat_platform_fee_rate)
   vat_total           = sum of the two   ← DEFINED as the sum, never re-derived
7  total    = subtotal + platform_fee + vat_total
8  SPLIT    hours_out <= FULL_PAYMENT_THRESHOLD + GRACE (~26h) → full upfront
            else deposit = clamp(pct(total, deposit_value), MIN_CHARGE, total)
                 balance = total - deposit                  ← derived, exact
                 if 0 < balance < MIN_CHARGE → fold into full upfront
9  SHARES   share_deposit = round(subtotal * deposit / total)
            share_balance = subtotal - share_deposit         ← derived, never recomputed
```

**Asserted invariants** (raise `PricingInvariantError`): `subtotal + fee + vat_total == total`; `vat_on_service + vat_on_platform_fee == vat_total`; `deposit + balance == total`; `share_deposit + share_balance == subtotal`; each share ≤ its charge; all emitted line items sum to `total`; nothing negative.

Approved check: subtotal 20000 → fee 2000 → vat 4000+400 → **total 26400**; deposit 2640 / balance 23760; shares 2000 / 18000. ✓

---

## Endpoints

**Tag `Booking Calculator`** — `/api/v1/booking-calculations`, **no auth**, router-level `ip_rate_limiter(key_prefix="booking_calc", limit=30, window_seconds=3600)`.

|                      |            |                                                                                     |
| -------------------- | ---------- | ----------------------------------------------------------------------------------- |
| POST                 | `/preview` | stateless, writes nothing — _added alongside the CRUD; most clients will want this_ |
| POST                 | ``         | 201, persists a DRAFT with `expires_at` (2h)                                        |
| GET / PATCH / DELETE | `/{id}`    | PATCH & DELETE are DRAFT-only; PATCH fully recomputes                               |

Input is IDs only — `{braider_id, style_id, style_variation_id?, braider_style_addon_ids[], is_mobile}`. **No prices ever come from the client.** Reject >1 variation and any addon not belonging to that `braider_style`.

> A calculation has **no owner** and can never be used for authorization — only as an input echo. The booking re-derives and re-authorizes everything. Put this in a code comment.

**Tag `Bookings`** — `/api/v1/bookings`, `require_roles(CUSTOMER)`: `POST ``, `GET ``(paginated), `GET /{id}`, `POST /{id}/cancel`, `POST /{id}/pay`(resume a hold / complete an SCA-blocked balance),`GET /{id}/receipts`.

**Tag `Braider - Bookings`** — `/api/v1/braiders/me/bookings`, `require_roles(BRAIDER)`: `GET ``, `GET /{id}`, `POST /{id}/cancel` (reason required → full refund).

**Tag `Receipts`** — `GET /api/v1/receipts/{public_token}` → **`HTMLResponse`**, no auth. A deliberate, documented exception to the `APIResponse[T]` rule (it's a document, not an API payload). `?lang=` already works via `LocaleMiddleware`.

**Webhooks** — existing `POST /api/v1/webhooks/stripe` (Connect) + **new** `POST /api/v1/webhooks/stripe/payments` (platform account, own secret). Both `include_in_schema=False`.

---

## Data model

New enums, each created once via the repo's raw-SQL idiom (`op.execute("CREATE TYPE …")` + `postgresql.ENUM(create_type=False)` per column).

**`booking_calculations`** — braider/style/variation refs, `is_mobile`, `currency`, `duration_minutes`, the full amount breakdown, **rate snapshots** (`platform_fee_type/value`, `vat_service_rate`, `vat_platform_fee_rate`, `deposit_type/value`), `status DRAFT|CONSUMED|EXPIRED`, `expires_at`, `consumed_by_booking_id`, `created_by_user_id`, `client_ip_hash` (salted SHA-256 — **never the raw IP**; it's personal data under GDPR and there's no lawful basis for storing it against an anonymous actor). Partial index on `(expires_at) WHERE status='DRAFT'`. Plus `booking_calculation_addons`.

**`bookings`** — the big one. `reference` (`AB-7QK3M2`), customer/braider refs, `status`, `starts_at`/`ends_at`, **`blocked_from`/`blocked_until`** (= `starts_at` / `ends_at + buffer`), `braider_timezone`, service-address snapshot, **full amount + rate snapshot** (so receipts survive catalog and price changes), `braider_vat_status`/`braider_vat_number`, `braider_share_total/_deposit/_balance`, `payment_schedule`, `hold_expires_at`, `cancellation_cutoff_at`, `balance_charge_due_at`/`_state`/`_attempts`/`_last_error`, `*_reminder_sent_at`, lifecycle timestamps, `cancelled_by`, `stripe_customer_id`/`stripe_payment_method_id` + card expiry, `terms_version`/`terms_accepted_at`, and **`locale`** (customer's locale at booking time — drives every downstream email and receipt).

Check constraints mirror every pricing invariant. Double-booking guard:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE bookings ADD CONSTRAINT ex_bookings_no_overlap
  EXCLUDE USING gist (braider_id WITH =,
                      tstzrange(blocked_from, blocked_until, '[)') WITH &&)
  WHERE (status IN ('PENDING_PAYMENT','CONFIRMED','IN_PROGRESS','COMPLETED','NO_SHOW','DISPUTED'));
```

`btree_gist` is safe to assume — `earthdistance` is already enabled and is _less_ commonly whitelisted on managed Postgres.

**`booking_items`** — one row per line including the fee and VAT lines, with `name_en/de/fr` snapshotted and `source_*_id` columns carrying **no FKs** (a deleted addon must never break a two-year-old receipt). Makes the receipt renderer a flat loop and `sum(line_amount) == total` assertable.

**`booking_payments`** — `purpose FULL|DEPOSIT|BALANCE`, `status`, minor-unit amounts, `braider_share_minor`, `amount_refunded_minor`, `amount_transferred_minor`, Stripe ids, `idempotency_key`, `is_off_session`, `transfer_group`, `attempt_number`, failure fields.

```sql
CREATE UNIQUE INDEX uq_booking_payment_succeeded
  ON booking_payments (booking_id, purpose) WHERE status = 'SUCCEEDED';
```

Partial (not plain) unique, so failed balance attempts persist as history while at most one charge per purpose can succeed. Keys are `booking:{id}:balance:{attempt}` — **note Stripe idempotency keys expire after 24h**, so the DB state check is load-bearing, not belt-and-braces.

**`booking_refunds`**, **`booking_transfers`** (partial unique on `booking_payment_id WHERE status IN ('PENDING','SUCCEEDED')`), **`booking_transfer_reversals`**, **`receipts`** (with `prior_receipts_total` — what makes the balance receipt a correct _Schlussrechnung_ deducting the _Anzahlungsrechnung_, plus a `public_token` and the immutable rendered `html`), **`receipt_counters`**, **`stripe_webhook_events`** (`stripe_event_id` PK, `source`, `status RECEIVED|PROCESSED|FAILED|IGNORED`, `attempts`).

**Altered:** `users += stripe_customer_id`; `platform_settings += deposit_type/value, vat_platform_fee_type/value` (nullable → backfill the singleton row → `SET NOT NULL`, and extend `ck_platform_settings_value_ranges`).

---

## Status machine

```
PENDING_PAYMENT · CONFIRMED · IN_PROGRESS · COMPLETED · NO_SHOW
CANCELLED_BY_CUSTOMER · CANCELLED_BY_BRAIDER · CANCELLED_NO_PAYMENT · EXPIRED · DISPUTED
```

Encode legal transitions as a module-level `dict[BookingStatus, set[BookingStatus]]`, raise `InvalidBookingTransitionError` (409) otherwise, and test the matrix exhaustively. Money effects:

- **→ CONFIRMED** (`payment_intent.succeeded`): captured on the **platform** account. Braider gets nothing yet. Schedules the balance. Issues a receipt.
- **→ CANCELLED_BY_CUSTOMER** (before cutoff): **no refund**, deposit forfeited, `balance_charge_state → ABANDONED`, and the braider's deposit share is released to them.
- **→ CANCELLED_BY_BRAIDER**: **full refund of every succeeded payment**, deposit included; reverse any transfer. Platform absorbs Stripe's non-returned processing fee (~1.5% + €0.25) — braider cancellations cost real money and should eventually carry a penalty.
- **→ CANCELLED_NO_PAYMENT**: retry ladder exhausted at `starts_at - 4h`. Deposit forfeited (customer fault).
- **COMPLETED / NO_SHOW → payout** at `ends_at + 48h`: braider paid in full on both.
- **→ DISPUTED**: attempt reversal, freeze payouts, alert admin.

---

## Stripe sequences

All charges on the **platform** account. No `transfer_data`, no `application_fee_amount` — **separate charges and transfers**, so funds are held until the service is delivered. `transfer_group = f"booking_{id}"`, `metadata = {booking_id, purpose}` on every intent.

- **≤24h (full upfront)** — insert booking → `flush()` (surfaces `23P01`) → commit → `Customer.create` (cached on `users.stripe_customer_id`) → `PaymentIntent.create(amount=total_minor, payment_method_types=["card"])` → client confirms on-session → webhook confirms.
- **>24h (deposit)** — same, but `setup_future_usage="off_session"` and the UI **must** show the mandate disclosure. On success, persist the payment method + card expiry and set `balance_charge_state = SCHEDULED`.
- **Balance** — sweeper cron → `FOR UPDATE` → re-assert `CONFIRMED`/`SCHEDULED`/past-cutoff → flip to `IN_PROGRESS` → **commit** → _then_ call `PaymentIntent.create(off_session=True, confirm=True)`.
- **Off-session failure** — `CardError` raises synchronously. `authentication_required` → needs customer-present 3DS, email a pay-link to `POST /{id}/pay`. `card_declined`/`expired_card` → "update your card" link. Ladder **+2h, +6h, +12h**, hard deadline `starts_at - 4h`.
- **Customer cancel** — **zero Stripe calls** on the cancel path itself; the slot falls out of the exclusion predicate automatically.
- **Braider cancel** — `Refund.create` per succeeded payment, `PaymentIntent.cancel` for uncaptured ones, reverse any transfer.
- **Payout** — `Transfer.create(amount=braider_share_minor, destination=acct, source_transaction=charge_id, transfer_group)`, one per captured charge. `source_transaction` makes funds available immediately (no negative-balance risk). **Skip any payment with `amount_refunded_minor > 0`.** `insufficient_capabilities_for_transfer` → `PAYOUT_BLOCKED` + admin alert + daily retry, never a silent infinite loop.

---

## Caching

`app/core/cache.py` (`get_json`/`set_json`/`delete`) + `app/modules/platform_settings/cache.py` exposing a frozen `EffectivePlatformSettings` dataclass under key `cache:platform_settings:v1`, **TTL 7 days** (comfortably over the 24h requirement).

Invalidation on PATCH is a **double-delete**: `delete` → `commit` → `delete` again, so a concurrent read can't repopulate from the pre-commit snapshot. Thread redis service-first per repo convention: `update_settings(db, redis, *, data)`, router adds `redis: Redis = Depends(get_redis)`. Admin `GET` stays **uncached** (admins must see DB truth); only the pricing engine reads through the cache. Worker sets `ctx["cache_redis"] = get_redis_client()` in `on_startup` — **not** `ctx["redis"]`, which arq owns and which isn't `decode_responses=True`.

---

## Background work

**Tasks:** booking confirmed/cancelled emails, `charge_booking_balance`, balance reminder, payment-failed pay-link, appointment reminder, `release_booking_payout`, `issue_booking_receipt`, `issue_credit_note`, `reverse_transfer`.

**Crons** (`from arq import cron`; `WorkerSettings.cron_jobs`, a separate list from `functions`) — every one idempotent, batched, re-asserting state under `FOR UPDATE SKIP LOCKED`:

`expire_booking_holds` (1m) · `sweep_balance_charges` (5m — **the primary balance driver**) · `send_balance_reminders` (hourly, T-72h) · `send_appointment_reminders` (hourly) · `start_due_bookings` (15m) · `complete_due_bookings` (15m) · `release_due_payouts` (15m) · `expire_booking_calculations` (hourly, batched `LIMIT 5000`) · `reconcile_stripe_payments` (30m) · `retry_webhook_events` (10m).

---

## Files to change

| file                                                                    | change                                                                                                                                                                                            |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/main.py`                                                           | 5 × `include_router`                                                                                                                                                                              |
| `app/worker.py`                                                         | register ~10 tasks, add `cron_jobs`, `on_startup` sets `ctx["cache_redis"]`, `# noqa: F401` model imports                                                                                         |
| `alembic/env.py`                                                        | import the new model modules `# noqa: F401`                                                                                                                                                       |
| `tests/conftest.py`                                                     | extend the hardcoded TRUNCATE list with all new tables, **before** `braider_profiles, users` (`RESTART IDENTITY` also resets `receipt_counters` — desirable, but only if it's listed)             |
| `app/core/exceptions.py`                                                | ~22 new `AppError` subclasses                                                                                                                                                                     |
| `app/core/config.py`                                                    | `stripe_payments_webhook_secret`, `stripe_api_version`, hold/TTL/threshold/grace/deadline/release-delay knobs, `terms_version`, `public_base_url`, dummy company HQ fields, `client_ip_hash_salt` |
| `app/locales/{en,de,fr}.json`                                           | ~90 keys: `booking.*`, `booking_calculation.*`, `payment.*`, `receipt.*`, `email.booking_*`                                                                                                       |
| `platform_settings/{models,schemas,service,router}.py` + new `cache.py` | 4 new fields, extended check constraint, redis-threaded `update_settings`                                                                                                                         |
| `braiders/availability/service.py`                                      | subtract booked ranges from `compute_available_slots`; fix the per-day exceptions N+1 while in there                                                                                              |
| `braiders/availability/router.py`                                       | the public route description still says "there's no booking system yet"                                                                                                                           |
| `braiders/payment_setup/{service,webhook,client}.py`                    | refactor `handle_webhook` into a `_HANDLERS` dispatcher, insert-first event dedupe, pin `stripe.api_version`                                                                                      |
| `braiders/discovery/{schemas,service}.py`                               | expose `travel_fee` on `BraiderLocationResponse` — required to price a mobile booking, and EU price transparency requires showing mandatory charges pre-order                                     |

`requirements.txt` is **unchanged** — no new dependency is needed.

---

## Phases

Each is independently shippable, migratable and testable.

| #     | scope                                                                                                                                                             | ships                                      |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **0** | `money.py`, `currency.py`, `cache.py`, settings cache; `platform_settings` +4 columns                                                                             | Admins can configure the deposit %, cached |
| **1** | Pricing engine + public calculator + cleanup cron. **Zero Stripe.**                                                                                               | Frontend can build the entire quote UI     |
| **2** | `bookings`, `booking_items`, `booking_payments`, webhook events, `btree_gist` + exclusion, availability integration, braider payability gate, confirmation emails | **A customer can book and pay**            |
| **3** | Balance sweeper, retry ladder, `POST /{id}/pay`, failure emails, `CANCELLED_NO_PAYMENT`                                                                           | The deposit model actually completes       |
| **4** | Refunds, both cancel endpoints, cutoff enforcement, `charge.refunded`                                                                                             | Cancellations work end to end              |
| **5** | Transfers, reversals, completion + payout crons, dispute handling                                                                                                 | **Braiders get paid**                      |
| **6** | Receipts, gapless numbering, 3-locale HTML templates, public receipt URL, credit notes                                                                            | Receipts                                   |
| **7** | Reconciliation, webhook retries, admin endpoints, `NO_SHOW`, DAC7 reporting query                                                                                 | Hardening                                  |

---

## Verification

**`tests/modules/bookings/test_pricing.py` is the highest-value file in the project** — pure functions, no DB, no fixtures. Key cases: the approved 200→264 example byte-exact; **variation replaces base price** (180 + 200 → 200, not 380); required addons force-included; VAT computed per-base then summed, _not_ blended (pins the rounding order); divergent rates (service 0% Kleinunternehmer + fee 19%); `ROUND_HALF_UP` not bankers'; and property tests over 0.01–9999.99 for `deposit + balance == total` and `shares sum to subtotal and never exceed their charge` — the latter is what protects `source_transaction`.

Other suites: `test_money.py` (quantize-then-scale; the `int(d*100)` float trap explicitly guarded) · `test_settings_cache.py` (miss/hit/invalidate/TTL; worker client returns `str` not `bytes`) · `test_calculations.py` (CRUD, expiry, `?lang=de`, rate limit) · `test_double_booking.py` (overlap 409; **adjacent bookings with buffer 0 must succeed**; buffer 30 makes the same pair collide; two concurrent `asyncio.gather` creates → exactly one 201) · `test_booking_create.py` (price drift 409, no Connect account 409, mobile without address 422, outside radius 422, snapshot immutability) · `test_payment_flow.py` (duplicate webhook is a no-op; webhook arriving _before_ the payment row resolves via metadata) · `test_balance_charge.py` (**cancel-then-sweep and sweep-then-cancel orderings both correct**) · `test_cancellation.py` · `test_payouts.py` · `test_receipts.py` (gapless under concurrency, year rollover, `prior_receipts_total`, all §14 UStG fields) · `test_webhook_idempotency.py` · extend `test_availability.py`.

**The highest-leverage test decision:** `bookings/payments/client.py` short-circuits on `settings.environment == "test"` and returns deterministic fakes (`pi_test_<uuid>`, `ch_test_<uuid>`, `tr_test_<uuid>`) — exactly as `shared/translation/client.py` already does. Without it, every booking test needs Stripe mocking. Where a test needs specific Stripe behaviour, `monkeypatch.setattr` on the service — which requires the service to import client functions **by name at module level**, as `payment_setup/service.py` already does.

Run: `python -m pytest tests/ -q`. Note ~11 pre-existing failures in `tests/modules/auth/` that are unrelated to this work.

---

## Flagged for you — not blocking, but act before going live

1. **Get a tax advisor before Phase 6 ships a receipt with a tax number on it.** I am not one. The two-rate schema is built to be _correctable_, but the seeded 20% is Austria's rate — Germany is 19%, France 20% — and the braider's VAT status (`STANDARD` vs `SMALL_BUSINESS` §19 UStG) is currently `UNKNOWN` for everyone. You need to collect it, and the correct treatment of VAT on a _forfeited_ deposit (compensation, arguably outside the scope of VAT) is genuinely unsettled.
2. **DAC7 / PStTG.** As an EU platform intermediating personal services you have annual reporting obligations per braider (identity, consideration, fees withheld, per quarter). The schema supports it — just never hard-delete booking or transfer rows.
3. **Card-only in v1** is a real product limitation in DE/FR, where card penetration is lower than you'd like. SEPA Direct Debit would need a separate mandate integration.
4. **Separate charges and transfers is a one-way door.** Customers and PaymentMethods live on the platform account and are not portable to destination or direct charges later.
5. **Worth putting to the stakeholder:** charging 100% upfront always would delete the entire balance subsystem — a cron, a retry ladder, a pay-link flow, ~6 states, and the whole 9-month card-expiry risk. The deposit model exists to reduce customer friction; it's worth quantifying whether that friction is worth this much machinery.
6. **Pre-existing, not fixed here:** `compute_available_slots` has a DST bug (`datetime.combine(..., tzinfo=tz)` on a spring-forward-nonexistent local time yields a wrong instant), and `duration_minutes` lives only on `BraiderStyle` — so a knee-length variation cannot take longer than a shoulder-length one.
