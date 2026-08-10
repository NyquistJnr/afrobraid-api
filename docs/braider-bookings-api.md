# Braider Bookings API

Base URL prefix: `/api/v1/braiders/me/bookings`

## Auth

All endpoints require a Bearer JWT for a user with role `BRAIDER`.

```
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token → `401 INVALID_ACCESS_TOKEN`
- Inactive user → `403 USER_NOT_ACTIVE`
- Wrong role (e.g. customer token) → `403 FORBIDDEN`

---

## 1. List bookings

`GET /api/v1/braiders/me/bookings`

Returns the authenticated braider's own bookings, paginated.

### Query params

| Param | Type | Required | Notes |
|---|---|---|---|
| `status` | `BookingStatus` enum (see below) | no | filter by exact status |
| `date_from` | ISO date (`YYYY-MM-DD`) | no | filters on `starts_at` |
| `date_to` | ISO date (`YYYY-MM-DD`) | no | filters on `starts_at`; must be ≥ `date_from` or `400 INVALID_BOOKING_DATE_RANGE` |
| `search` | string | no | matches style name (localized) or customer first/last name, case-insensitive |
| `page` | int | no | default `1`, min `1` |
| `page_size` | int | no | default `20`, min `1`, max `100` |

Results are ordered by `starts_at DESC`.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "reference": "string",
        "status": "CONFIRMED",
        "braider_id": "uuid",
        "braider_name": "string",
        "customer_name": "string",
        "style_name": "string",
        "starts_at": "2026-08-10T09:00:00Z",
        "ends_at": "2026-08-10T12:00:00Z",
        "total": "120.00",
        "currency": "EUR"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total_items": 42,
    "total_pages": 3,
    "has_next": true,
    "has_previous": false
  },
  "error": null
}
```

Note: pagination fields are flat (`page`, `page_size`, `total_items`, `total_pages`, `has_next`, `has_previous`) — not nested under a `pagination` object.

If the authenticated user has no braider profile yet, this returns an empty page (`items: []`, `total_items: 0`) rather than an error.

---

## 2. Get booking details

`GET /api/v1/braiders/me/bookings/{booking_id}`

### Path params

| Param | Type | Notes |
|---|---|---|
| `booking_id` | UUID | must belong to the authenticated braider, else `404 BOOKING_NOT_FOUND` |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "uuid",
    "reference": "string",
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
    "starts_at": "2026-08-10T09:00:00Z",
    "ends_at": "2026-08-10T12:00:00Z",
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
    "cancellation_cutoff_at": "2026-08-08T09:00:00Z",
    "payments": [
      {
        "purpose": "DEPOSIT",
        "status": "SUCCEEDED",
        "amount": "30.00",
        "currency": "EUR"
      }
    ],
    "created_at": "2026-07-01T10:00:00Z"
  },
  "error": null
}
```

Note: names are pre-resolved strings (`braider_name`, `customer_name`, `style_name`) — there are no nested braider/customer/style objects to unpack. `payments[].client_secret` is normally absent/`null` on GET; it's only populated right after a payment intent is created elsewhere.

Internal-only fields (hold expiry, balance-charge retry state, Stripe customer/PM ids, braider payout shares, cancellation actor, terms acceptance) are **not** included in this response.

### Error `404`

```json
{
  "status": "error",
  "status_label": "Error",
  "data": null,
  "error": { "code": "BOOKING_NOT_FOUND", "message": "Booking not found" }
}
```

---

## Enums

### `BookingStatus`
`PENDING_PAYMENT`, `CONFIRMED`, `IN_PROGRESS`, `COMPLETED`, `NO_SHOW`, `CANCELLED_BY_CUSTOMER`, `CANCELLED_BY_BRAIDER`, `CANCELLED_NO_PAYMENT`, `EXPIRED`, `DISPUTED`

### `PaymentSchedule`
`FULL_UPFRONT`, `DEPOSIT_THEN_BALANCE`

### `PaymentPurpose`
`FULL`, `DEPOSIT`, `BALANCE`

### `PaymentStatus`
`PENDING`, `SUCCEEDED`, `FAILED`, `CANCELED`

### `BookingItemType`
`SERVICE`, `VARIATION`, `ADDON`, `TRAVEL`, `PLATFORM_FEE`, `VAT_SERVICE`, `VAT_PLATFORM_FEE`

### `Currency`
`EUR` (only value currently supported)

---

## Common error codes

| Code | HTTP status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `USER_NOT_ACTIVE` | 403 | user account inactive |
| `FORBIDDEN` | 403 | wrong role (e.g. customer token on braider route) |
| `BOOKING_NOT_FOUND` | 404 | booking doesn't exist or doesn't belong to this braider |
| `INVALID_BOOKING_DATE_RANGE` | 400 | `date_to` earlier than `date_from` on list endpoint |
| `VALIDATION_ERROR` | 422 | bad query/path param (e.g. non-UUID `booking_id`, malformed date); response includes a `details` array |
| `INTERNAL_SERVER_ERROR` | 500 | unhandled server error |

All error responses share this envelope:

```json
{
  "status": "error",
  "status_label": "string",
  "data": null,
  "error": { "code": "string", "message": "string" }
}
```
