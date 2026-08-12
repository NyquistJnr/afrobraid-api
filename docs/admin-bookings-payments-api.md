# Admin Bookings & Payments API

All endpoints require a Bearer JWT for a user with role `ADMIN`.

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
