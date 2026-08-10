# Braider Stats & Payments API

Four new endpoints: booking stats, a booking trend graph, payment stats, and a payments list. All are `BRAIDER`-role, scoped to the calling braider's own data.

## Auth

```
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token → `401 INVALID_ACCESS_TOKEN`
- Wrong role → `403 FORBIDDEN`

If the braider has no profile yet, every endpoint below returns a zeroed/empty result rather than an error.

---

## 1. GET `/api/v1/braiders/me/bookings/stats` — Booking stats

### Query params

| Param | Type | Notes |
|---|---|---|
| `date_from` | ISO date | optional, bounds `starts_at` |
| `date_to` | ISO date | optional, bounds `starts_at`; must be ≥ `date_from` or `400 INVALID_BOOKING_DATE_RANGE` |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "total_bookings": 128,
    "completed": 94,
    "declined": 21,
    "upcoming": 13
  },
  "error": null
}
```

Definitions (see `DECLINED_BOOKING_STATUSES` / `UPCOMING_BOOKING_STATUSES` in `app/modules/bookings/enums.py`):
- `total_bookings` — every booking in range, any status.
- `completed` — `status == COMPLETED`.
- `declined` — `CANCELLED_BY_CUSTOMER`, `CANCELLED_BY_BRAIDER`, `CANCELLED_NO_PAYMENT`, or `EXPIRED`. (`NO_SHOW` and `DISPUTED` are deliberately excluded — those appointments did happen, they just went wrong afterward.)
- `upcoming` — `CONFIRMED` or `IN_PROGRESS` (booked, not yet resolved).

---

## 2. GET `/api/v1/braiders/me/bookings/timeseries` — Booking trend (multi-line graph)

### Query params

| Param | Type | Default | Notes |
|---|---|---|---|
| `date_from` | ISO date | today − 90 days | |
| `date_to` | ISO date | today | must be ≥ `date_from` or `400` |
| `interval` | `day` \| `week` \| `month` | `day` | bucket size |
| `status` | `BookingStatus`, repeatable | all statuses present in range | e.g. `?status=COMPLETED&status=CANCELLED_BY_BRAIDER` to plot only those two lines |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "interval": "day",
    "statuses": ["CANCELLED_BY_BRAIDER", "COMPLETED", "CONFIRMED"],
    "points": [
      {
        "bucket": "2026-08-01T00:00:00Z",
        "counts": { "COMPLETED": 4, "CONFIRMED": 2 }
      },
      {
        "bucket": "2026-08-02T00:00:00Z",
        "counts": { "COMPLETED": 1, "CANCELLED_BY_BRAIDER": 1 }
      }
    ]
  },
  "error": null
}
```

Each point's `counts` only includes statuses with a non-zero count that day — treat a missing key as `0` when plotting a line. `statuses` at the top level is the full set of lines to render (either what you requested via `status=`, or every status that appeared in range if you didn't filter).

---

## 3. GET `/api/v1/braiders/me/payments/stats` — Payment stats (money flow)

### Query params

| Param | Type | Notes |
|---|---|---|
| `status` | `PaymentStatus` | optional (`PENDING`, `SUCCEEDED`, `FAILED`, `CANCELED`) |
| `date_from` | ISO date | optional, bounds `BookingPayment.created_at` (when the charge happened, not the appointment date) |
| `date_to` | ISO date | optional; must be ≥ `date_from` or `400` |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "total_received": "4820.00",
    "total_refunded": "0.00",
    "net_revenue": "4820.00",
    "pending": "150.00",
    "currency": "EUR"
  },
  "error": null
}
```

- `total_received` — sum of `SUCCEEDED` payments in range.
- `total_refunded` — sum of refunded amounts in range.
- `net_revenue` — `total_received - total_refunded`, computed regardless of any `status` filter.
- `pending` — sum of `PENDING` payments in range.

**Heads up:** refunds are not yet a live feature in this codebase — there's no refund webhook handler yet, so `total_refunded` will always read `0.00` today. The field is wired up and will start reflecting real numbers automatically once refunds ship; no frontend changes needed then.

---

## 4. GET `/api/v1/braiders/me/payments` — List payments

### Query params

| Param | Type | Notes |
|---|---|---|
| `purpose` | `PaymentPurpose` | optional (`FULL`, `DEPOSIT`, `BALANCE`) |
| `status` | `PaymentStatus` | optional |
| `date_from` | ISO date | optional, bounds `created_at` |
| `date_to` | ISO date | optional; must be ≥ `date_from` or `400` |
| `page` | int | default 1 |
| `page_size` | int | default 20, max 100 |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "items": [
      {
        "id": "3d6b9c1e-3b1f-4a2e-9c7e-1a9f5b6d2e10",
        "booking_id": "8d416c5e-57ed-4597-a587-326807a96277",
        "booking_reference": "AB12CD34",
        "purpose": "DEPOSIT",
        "status": "SUCCEEDED",
        "amount": "30.00",
        "amount_refunded": "0.00",
        "is_refunded": false,
        "currency": "EUR",
        "created_at": "2026-08-01T10:00:00Z"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total_items": 1,
    "total_pages": 1,
    "has_next": false,
    "has_previous": false
  },
  "error": null
}
```

`is_refunded` is `amount_refunded > 0` — always `false` today for the same reason as above (refunds aren't live yet), but ready for when they are. `purpose` tells you deposit vs. full vs. balance; combine with `status` to distinguish e.g. a failed balance charge from a succeeded one.

---

## Common error codes

| Code | HTTP status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `FORBIDDEN` | 403 | caller isn't a `BRAIDER` |
| `INVALID_BOOKING_DATE_RANGE` | 400 | `date_to` earlier than `date_from` |
| `VALIDATION_ERROR` | 422 | malformed query param (e.g. bad `interval` value) |
| `INTERNAL_SERVER_ERROR` | 500 | unhandled server error |

All error responses share the standard envelope:

```json
{
  "status": "error",
  "status_label": "string",
  "data": null,
  "error": { "code": "string", "message": "string" }
}
```

## Notes on multi-language

Enum values (`BookingStatus`, `PaymentPurpose`, `PaymentStatus`) are returned as raw uppercase strings, same as every other endpoint in this API — the frontend owns translating them into display labels per locale, there's no server-rendered label on these fields. The only localized text these endpoints touch is `status_label` in the response envelope itself, which already follows the request's `Accept-Language`/`?lang=` locale like every other endpoint.
