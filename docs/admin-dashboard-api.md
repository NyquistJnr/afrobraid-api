# Admin Dashboard API

Base URL prefix: `/api/v1/admin/dashboard`

All endpoints require a Bearer JWT for a user with role `ADMIN`.

Common filters:

| Param | Type | Notes |
|---|---|---|
| `date_from`, `date_to` | ISO date | bounds booking appointment `starts_at` |
| `created_from`, `created_to` | ISO date | overview/financials only; bounds booking `created_at` |
| `payment_date_from`, `payment_date_to` | ISO date | bounds payment `created_at` for cash totals |
| `country` | 2-letter country code | optional |
| `currency` | `Currency` | optional |
| `is_mobile` | boolean | optional |
| `payment_schedule` | `FULL_UPFRONT` or `DEPOSIT_THEN_BALANCE` | optional |
| `search` | string | matches booking ref, style, customer, and braider fields |
| `status` | `BookingStatus` | overview/financials only |

## GET `/overview`

Platform-wide booking dashboard totals: booking counts, status counts, mobile/salon split, unique/repeat customer and braider counts, booking value, paid/refunded/net paid, pending amount, braider earnings, and customer spend.

## GET `/financials`

Finance-focused totals: service subtotal, platform fee total, VAT total, gross booking value, paid/refunded/net paid, pending payment amount, braider earnings, gross margin before tax, and estimated profit after VAT.

## GET `/charts/revenue`

Line chart of platform GMV. Supports `interval=day|week|month`.

## GET `/charts/weekday`

Bar chart grouped by ISO weekday.

## GET `/charts/status`

Bar chart grouped by booking status.

## GET `/charts/countries`

Bar chart grouped by booking country.

## GET `/charts/styles`

Pie chart of most-booked/highest-GMV styles. Supports `limit` from 1 to 25; defaults to 8 and folds remaining styles into `Other`.
