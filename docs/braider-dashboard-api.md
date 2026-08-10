# Braider Dashboard API

Four endpoints for a braider's home dashboard: an overview stats tile, a revenue line-chart, a "busiest days" bar-chart, and a "top styles" pie-chart. All are `BRAIDER`-role, scoped to the calling braider's own data, and share the same optional `date_from`/`date_to` filter shape as the existing [booking stats & payments API](braider-stats-payments-api.md).

## Auth

```
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token → `401 INVALID_ACCESS_TOKEN`
- Wrong role → `403 FORBIDDEN`

If the braider has no profile yet, every endpoint below returns a zeroed/empty result rather than an error.

## A note on "revenue"

Every money figure on these four endpoints is the braider's **own share** (`braider_share_minor` / `braider_share_total` — what actually gets transferred to the braider), not the gross amount the customer paid. That's different from the existing `GET /api/v1/braiders/me/payments/stats` endpoint, which reports gross customer-facing totals (including the platform fee and VAT the braider never sees). Use the payments endpoint for "how much moved through Stripe"; use these dashboard endpoints for "how much did I actually earn."

All four also bound `starts_at` (the appointment date), not `created_at` or payment date — a dashboard is a view of business performance by appointment period, matching the convention already used by `GET /api/v1/braiders/me/bookings/stats`.

---

## 1. GET `/api/v1/braiders/me/dashboard/overview` — Stat tiles

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
    "completed_bookings": 94,
    "upcoming_bookings": 13,
    "cancelled_bookings": 20,
    "no_show_bookings": 1,
    "completion_rate": "73.4",
    "cancellation_rate": "15.6",
    "total_revenue": "6420.00",
    "average_booking_value": "68.30",
    "unique_customers": 71,
    "repeat_customers": 18,
    "repeat_customer_rate": "25.4",
    "average_rating": "4.80",
    "rating_count": 62,
    "currency": "EUR"
  },
  "error": null
}
```

| Field | Meaning |
|---|---|
| `total_bookings` | every booking in range, any status |
| `completed_bookings` / `upcoming_bookings` / `cancelled_bookings` / `no_show_bookings` | same status groupings as `GET /bookings/stats` (`upcoming` = `CONFIRMED`/`IN_PROGRESS`, `cancelled` = `CANCELLED_BY_CUSTOMER`/`CANCELLED_BY_BRAIDER`/`CANCELLED_NO_PAYMENT`/`EXPIRED`) |
| `completion_rate` / `cancellation_rate` | `completed_bookings` / `cancelled_bookings` as a percentage of `total_bookings`, one decimal place, `0.0` if `total_bookings` is 0 |
| `total_revenue` | sum of the braider's share of every `SUCCEEDED` payment for bookings in range |
| `average_booking_value` | `total_revenue / completed_bookings`; `0.00` if there are no completed bookings |
| `unique_customers` | distinct customers who booked in range |
| `repeat_customers` | of those, how many booked more than once **within this same date range** (this is not lifetime repeat-customer count — a wide date range gives a more meaningful number than a narrow one) |
| `repeat_customer_rate` | `repeat_customers / unique_customers` as a percentage |
| `average_rating` / `rating_count` | the braider's overall cached rating (`BraiderProfile.average_rating`/`rating_count`) — **not** scoped to the date range, since reviews aren't tied to a specific appointment date in a way that's meaningful to filter |

---

## 2. GET `/api/v1/braiders/me/dashboard/revenue-timeseries` — Revenue (line chart)

### Query params

| Param | Type | Default | Notes |
|---|---|---|---|
| `date_from` | ISO date | today − 90 days | |
| `date_to` | ISO date | today | must be ≥ `date_from` or `400` |
| `interval` | `day` \| `week` \| `month` | `day` | bucket size |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "interval": "day",
    "currency": "EUR",
    "points": [
      { "bucket": "2026-08-01T00:00:00Z", "revenue": "180.00", "bookings_count": 3 },
      { "bucket": "2026-08-02T00:00:00Z", "revenue": "60.00", "bookings_count": 1 }
    ]
  },
  "error": null
}
```

Buckets with zero revenue in the range are simply omitted (no zero-filled gaps) — plot with a zero default for any missing date. `bookings_count` is the number of distinct bookings that had at least one succeeded payment in that bucket, so it can be lower than the number of payments (a deposit + balance on the same booking still counts once).

---

## 3. GET `/api/v1/braiders/me/dashboard/bookings-by-weekday` — Busiest days (bar chart)

### Query params

| Param | Type | Notes |
|---|---|---|
| `date_from` | ISO date | optional, bounds `starts_at` |
| `date_to` | ISO date | optional; must be ≥ `date_from` or `400` |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "currency": "EUR",
    "points": [
      { "weekday": 1, "bookings_count": 22, "revenue": "1540.00" },
      { "weekday": 2, "bookings_count": 15, "revenue": "1020.00" },
      { "weekday": 3, "bookings_count": 18, "revenue": "1260.00" },
      { "weekday": 4, "bookings_count": 20, "revenue": "1400.00" },
      { "weekday": 5, "bookings_count": 30, "revenue": "2100.00" },
      { "weekday": 6, "bookings_count": 38, "revenue": "2660.00" },
      { "weekday": 7, "bookings_count": 5, "revenue": "350.00" }
    ]
  },
  "error": null
}
```

`weekday` is ISO 8601 (1 = Monday … 7 = Sunday). Always returns all 7 entries, zero-filled, so the bar chart's x-axis never shifts. Only counts bookings whose status ever occupied the calendar (`PENDING_PAYMENT`, `CONFIRMED`, `IN_PROGRESS`, `COMPLETED`, `NO_SHOW`, `DISPUTED`) — cancelled/expired holds don't count toward "how busy is this day." `revenue` here is the braider's share summed from the booking record itself (`braider_share_total`), not filtered to succeeded payments only, since this endpoint is about scheduling load rather than cash collected.

---

## 4. GET `/api/v1/braiders/me/dashboard/style-breakdown` — Top styles (pie chart)

### Query params

| Param | Type | Notes |
|---|---|---|
| `date_from` | ISO date | optional, bounds `starts_at` |
| `date_to` | ISO date | optional; must be ≥ `date_from` or `400` |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "currency": "EUR",
    "total_revenue": "6420.00",
    "slices": [
      { "style_id": "8d416c5e-57ed-4597-a587-326807a96277", "style_name": "Box Braids", "bookings_count": 40, "revenue": "2800.00", "revenue_share": "43.6" },
      { "style_id": "3d6b9c1e-3b1f-4a2e-9c7e-1a9f5b6d2e10", "style_name": "Cornrows", "bookings_count": 25, "revenue": "1500.00", "revenue_share": "23.4" },
      { "style_id": null, "style_name": "Other", "bookings_count": 30, "revenue": "2120.00", "revenue_share": "33.0" }
    ]
  },
  "error": null
}
```

Ordered by `revenue` descending. Returns the top 8 styles individually; anything beyond that is folded into a single trailing slice with `style_id: null` and a localized "Other" label, so the pie chart never has an unreadable number of slices. `style_name` follows the request's locale (`Accept-Language`/`?lang=`), same as everywhere else in the API. `revenue_share` is each slice's percentage of `total_revenue`. Same status filter and revenue basis (`braider_share_total` on the booking record) as the weekday breakdown.

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
