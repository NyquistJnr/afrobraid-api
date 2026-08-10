# Booking Reschedule API

Base URL prefix: `/api/v1/bookings`

## Auth

Requires a Bearer JWT for a user with role `CUSTOMER`. Only the customer who owns the booking can reschedule it — there is no braider-initiated reschedule endpoint.

```
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token → `401 INVALID_ACCESS_TOKEN`
- Inactive user → `403 USER_NOT_ACTIVE`
- Wrong role (e.g. braider token) → `403 FORBIDDEN`

---

## Reschedule a booking

`POST /api/v1/bookings/{booking_id}/reschedule`

Moves a confirmed booking to a new appointment time, **for free** — no repricing, no new charge, no change to the deposit/balance split. This is not the same as a cancel-and-rebook: the same booking row is updated in place, its reference/receipt/payment history is untouched, and no refund or additional payment is triggered.

### Eligibility rules

| Rule | Detail |
|---|---|
| Ownership | `booking.customer_id` must match the authenticated user, else `404 BOOKING_NOT_FOUND` (existence isn't leaked to non-owners) |
| Status | Booking must be `CONFIRMED` (deposit or full payment has succeeded, appointment hasn't started/finished/been cancelled). Any other status → `409 BOOKING_NOT_RESCHEDULABLE` |
| Cutoff | Must be requested **more than 24 hours before the current `starts_at`** — i.e. `now < cancellation_cutoff_at`. Once inside that window → `409 BOOKING_RESCHEDULE_WINDOW_CLOSED`. This is the same `cancellation_cutoff_at` field already returned on the booking, not a separate concept |
| New time | The new `starts_at` must be in the future, else `422 BOOKING_STARTS_IN_PAST` |
| Availability | The new slot must not collide with another booking on the same braider's calendar (enforced at the database level), else `409 BOOKING_SLOT_UNAVAILABLE`. The API does **not** re-validate the braider's open hours/weekly availability beyond that — same trust model as booking creation, the client is expected to only offer times the availability endpoint returned as free |
| Reschedule count | Unlimited — a booking can be rescheduled any number of times, each time subject to the same 24h-before-*current*-time rule |

Duration, price, currency, deposit/balance amounts, and `payment_schedule` never change on a reschedule — only the time-related fields move.

### Path params

| Param | Type | Notes |
|---|---|---|
| `booking_id` | UUID | must belong to the authenticated customer |

### Request body

```json
{
  "starts_at": "2026-08-20T14:00:00Z"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `starts_at` | ISO 8601 datetime (UTC) | yes | the new appointment start time |

### What changes on the booking

On success, the following fields are recomputed and persisted (everything else is untouched):

| Field | New value |
|---|---|
| `starts_at` | the requested time |
| `ends_at` | `starts_at + duration_minutes` (duration is unchanged from the original booking) |
| `braider_timezone` | re-snapshotted from the braider's current availability settings |
| `blocked_from` / `blocked_until` | recomputed from the new `starts_at`/`ends_at` plus the braider's current buffer minutes (internal fields, not in the API response) |
| `cancellation_cutoff_at` | `starts_at - 24h` (same rule applied at original booking time) |
| `balance_charge_due_at` | recomputed as `cancellation_cutoff_at + 45min` **only if** `payment_schedule == DEPOSIT_THEN_BALANCE`; otherwise stays `null` |

`balance_charge_state`, `deposit_amount`, `balance_amount`, `total`, and every payment row are left exactly as they were.

### Response `200`

Same shape as `GET /api/v1/bookings/{booking_id}` — the full updated booking.

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "uuid",
    "reference": "AB-7QK3M2",
    "status": "CONFIRMED",
    "braider_id": "uuid",
    "braider_name": "string",
    "customer_name": "string",
    "style_id": "uuid",
    "style_name": "string",
    "duration_minutes": 180,
    "is_mobile": true,
    "client_address": "string | null",
    "client_latitude": "decimal | null",
    "client_longitude": "decimal | null",
    "country": "DE",
    "currency": "EUR",
    "starts_at": "2026-08-20T14:00:00Z",
    "ends_at": "2026-08-20T17:00:00Z",
    "items": [
      {
        "item_type": "SERVICE",
        "name": "string | null",
        "quantity": 1,
        "unit_amount": "80.00",
        "line_amount": "80.00",
        "is_required": true
      }
    ],
    "service_subtotal": "80.00",
    "travel_fee": "10.00",
    "subtotal": "90.00",
    "platform_fee": "5.00",
    "vat_on_service": "15.20",
    "vat_on_platform_fee": "0.95",
    "vat_total": "16.15",
    "total": "111.15",
    "deposit_amount": "30.00",
    "balance_amount": "81.15",
    "payment_schedule": "DEPOSIT_THEN_BALANCE",
    "cancellation_cutoff_at": "2026-08-19T14:00:00Z",
    "payments": [
      {
        "purpose": "DEPOSIT",
        "status": "SUCCEEDED",
        "amount": "30.00",
        "currency": "EUR",
        "client_secret": null
      }
    ],
    "created_at": "2026-07-01T10:00:00Z"
  },
  "error": null
}
```

### Errors

```json
{
  "status": "error",
  "status_label": "Error",
  "data": null,
  "error": { "code": "BOOKING_RESCHEDULE_WINDOW_CLOSED", "message": "This booking can no longer be rescheduled - it's within 24 hours of the appointment." }
}
```

| Code | HTTP status | When |
|---|---|---|
| `BOOKING_NOT_FOUND` | 404 | booking doesn't exist, or doesn't belong to the authenticated customer |
| `BOOKING_NOT_RESCHEDULABLE` | 409 | booking status isn't `CONFIRMED` (e.g. still `PENDING_PAYMENT`, already `IN_PROGRESS`/`COMPLETED`, or any cancelled/expired/disputed/no-show status) |
| `BOOKING_RESCHEDULE_WINDOW_CLOSED` | 409 | now is within 24h of the booking's *current* `starts_at` (`now >= cancellation_cutoff_at`) |
| `BOOKING_STARTS_IN_PAST` | 422 | requested `starts_at` is not in the future |
| `BOOKING_SLOT_UNAVAILABLE` | 409 | requested time collides with another booking on the braider's calendar |
| `VALIDATION_ERROR` | 422 | malformed `booking_id` (non-UUID) or `starts_at` (not a valid datetime); response includes a `details` array |
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `USER_NOT_ACTIVE` | 403 | user account inactive |
| `FORBIDDEN` | 403 | wrong role (e.g. braider token) |
| `INTERNAL_SERVER_ERROR` | 500 | unhandled server error |

---

## Side effects

On success, two background jobs are queued (async, don't block the response):

1. **Email to the customer** — a "your appointment was moved from X to Y" confirmation, sent to the address on file.
2. **In-app notifications** — one `BOOKING_RESCHEDULED` notification for the customer and one for the braider (delivered over the existing notifications REST/websocket channel, same as payment-succeeded notifications). The braider does **not** receive an email for this, consistent with braiders not receiving booking emails elsewhere in the API today.

Neither side effect blocks or can fail the reschedule itself — if email/notification delivery has a transient issue, the booking's new time is already committed.

---

## Example: full flow

```
POST /api/v1/bookings/7c9e6b4a-.../reschedule
Authorization: Bearer <customer_access_token>
Content-Type: application/json

{ "starts_at": "2026-08-20T14:00:00Z" }
```

Success → `200` with the updated booking (see above). The customer's booking list / detail view immediately reflects the new `starts_at`/`ends_at`; the braider's calendar slot moves in the same transaction (old slot freed, new slot occupied) since both are driven by the same `blocked_from`/`blocked_until` update.

---

## Related enums

See `BookingStatus`, `PaymentSchedule`, `PaymentPurpose`, `PaymentStatus`, `BookingItemType`, `Currency` in [braider-bookings-api.md](braider-bookings-api.md#enums) — this endpoint reuses the same enums and response envelope conventions.
