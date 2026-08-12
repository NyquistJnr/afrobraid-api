# Admin Bookings & Payments API

All endpoints require a Bearer JWT for a user with role `ADMIN`.

## GET `/api/v1/admin/braiders/{braider_id}/onboarding`

Returns the braider's onboarding progress as all 8 steps:

- `BUSINESS_INFO`
- `PHONE_VERIFICATION`
- `VERIFF`
- `SERVICE_TYPE`
- `PORTFOLIO`
- `SERVICE_LOCATION`
- `AVAILABILITY`
- `PAYMENT_SETUP`

Each step includes `completed` and `completed_at`, plus the response includes `current_step` and overall `completed_at`.

## GET `/api/v1/admin/bookings`

Lists every booking on the platform, newest-created first.

Query params:

| Param | Type | Notes |
|---|---|---|
| `status` | `BookingStatus` | optional |
| `date_from`, `date_to` | ISO date | optional; bounds appointment `starts_at` |
| `created_from`, `created_to` | ISO date | optional; bounds `bookings.created_at` |
| `customer_id` | UUID | optional |
| `braider_id` | UUID | optional; this is the braider profile id |
| `country` | string | optional 2-letter country code |
| `currency` | `Currency` | optional |
| `is_mobile` | bool | optional |
| `payment_schedule` | `FULL_UPFRONT` or `DEPOSIT_THEN_BALANCE` | optional |
| `search` | string | matches booking reference, style name, customer name/email, braider business/name/email |
| `page`, `page_size` | int | default pagination; max page size 100 |

## GET `/api/v1/admin/bookings/{booking_id}`

Returns a full admin booking detail, including customer/braider ids and emails, schedule, address, price breakdown, booking items, payments, Stripe ids, refund amounts, failure details, and lifecycle timestamps.

## Scoped Admin Booking Lists

These return the same paginated booking shape as `GET /api/v1/admin/bookings`.

| Endpoint | Use |
|---|---|
| `GET /api/v1/admin/bookings/braiders/{braider_id}` | all bookings for one braider profile |
| `GET /api/v1/admin/bookings/customers/{customer_id}` | all bookings for one customer |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/customers/{customer_id}` | all bookings shared by one braider and one customer |

Supported query params: `status`, `date_from`, `date_to`, `created_from`, `created_to`, `country`, `currency`, `is_mobile`, `payment_schedule`, `search`, `page`, and `page_size`.

The braider route also accepts `customer_id`; the customer route also accepts `braider_id`.

## Scoped Admin Booking Stats

| Endpoint | Use |
|---|---|
| `GET /api/v1/admin/bookings/braiders/{braider_id}/stats` | braider booking/revenue stats |
| `GET /api/v1/admin/bookings/customers/{customer_id}/stats` | customer booking/spend stats |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/customers/{customer_id}/stats` | relationship stats for a specific braider/customer pair |

Supported query params: `status`, `date_from`, `date_to`, `created_from`, `created_to`, `payment_date_from`, `payment_date_to`, `country`, `currency`, `is_mobile`, `payment_schedule`, and `search`.

Stats include total bookings, per-status counts, completed/upcoming/declined/pending/no-show/disputed counts, mobile vs salon counts, unique/repeat counterpart counts, total booking value, average booking value, service subtotal, platform fee total, VAT total, paid/refunded/net amounts, pending payment amount, braider earnings, and customer spend.

## Admin Charts

Each chart endpoint supports `date_from`, `date_to`, `payment_date_from`, `payment_date_to`, `country`, `currency`, `is_mobile`, `payment_schedule`, and `search`.

Revenue line charts also support `interval=day|week|month`.

Style pie charts also support `limit` (default `8`, max `25`) and fold the rest into `Other`.

| Endpoint | Chart |
|---|---|
| `GET /api/v1/admin/bookings/braiders/{braider_id}/charts/revenue` | line chart of braider earnings |
| `GET /api/v1/admin/bookings/customers/{customer_id}/charts/revenue` | line chart of customer spend |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/customers/{customer_id}/charts/revenue` | line chart for the relationship |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/charts/weekday` | weekday bar chart for braider |
| `GET /api/v1/admin/bookings/customers/{customer_id}/charts/weekday` | weekday bar chart for customer |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/customers/{customer_id}/charts/weekday` | weekday bar chart for the relationship |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/charts/status` | booking status bar chart for braider |
| `GET /api/v1/admin/bookings/customers/{customer_id}/charts/status` | booking status bar chart for customer |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/customers/{customer_id}/charts/status` | booking status bar chart for the relationship |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/charts/styles` | most-booked styles pie chart for braider |
| `GET /api/v1/admin/bookings/customers/{customer_id}/charts/styles` | most-booked styles pie chart for customer |
| `GET /api/v1/admin/bookings/braiders/{braider_id}/customers/{customer_id}/charts/styles` | most-booked styles pie chart for the relationship |

## GET `/api/v1/admin/payments`

Lists every booking payment on the platform, newest-created first.

Query params:

| Param | Type | Notes |
|---|---|---|
| `purpose` | `FULL`, `DEPOSIT`, `BALANCE` | optional |
| `status` | `PaymentStatus` | optional |
| `date_from`, `date_to` | ISO date | optional; bounds payment `created_at` |
| `booking_date_from`, `booking_date_to` | ISO date | optional; bounds booking appointment `starts_at` |
| `customer_id` | UUID | optional |
| `braider_id` | UUID | optional; this is the braider profile id |
| `booking_id` | UUID | optional |
| `currency` | `Currency` | optional |
| `is_refunded` | bool | optional; maps to `amount_refunded_minor > 0` |
| `search` | string | matches booking reference, Stripe payment/charge ids, customer name/email, braider business/name/email |
| `page`, `page_size` | int | default pagination; max page size 100 |

Invalid date ranges return `400 INVALID_BOOKING_DATE_RANGE`. Wrong role returns `403 FORBIDDEN`.
