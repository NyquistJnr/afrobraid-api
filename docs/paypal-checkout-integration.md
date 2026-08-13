# PayPal Checkout Integration — Frontend Guide

Backend support for paying for a booking with PayPal, alongside the existing Stripe flow. This doc covers everything the frontend needs: the API contract, the exact request/response shapes, error codes, and how to wire up PayPal's JS SDK.

## Architecture summary

- Customer picks a payment method at booking time (`STRIPE` or `PAYPAL`, defaults to `STRIPE` if omitted — existing integrations are unaffected).
- For PayPal, the backend creates a PayPal **Order** (Orders v2, `intent=CAPTURE`) and returns its `paypal_order_id` instead of a Stripe `client_secret`.
- The frontend uses PayPal's JS SDK to let the customer approve that order (Smart Payment Buttons or PayPal Checkout).
- After approval, the frontend calls a backend **capture** endpoint. The backend captures the order server-side and confirms the booking — the frontend never tells the backend "payment succeeded," it only tells the backend "the customer approved, please capture."
- A backend-only webhook exists as a reconciliation safety net; it is not part of the frontend flow.

```
Customer                Frontend                    Backend                 PayPal
   |                        |                           |                      |
   |  choose PayPal         |                           |                      |
   |----------------------->|                           |                      |
   |                        |  POST /bookings           |                      |
   |                        |  payment_provider=PAYPAL  |                      |
   |                        |-------------------------->|                      |
   |                        |                           |  create order        |
   |                        |                           |--------------------->|
   |                        |                           |<----------------------|
   |                        |<-- booking + order_id ----|                      |
   |                        |                           |                      |
   |  approve on PayPal     |  render PayPal Buttons    |                      |
   |  (popup/redirect)      |  using order_id           |                      |
   |<-----------------------|-------------------------------------------------->|
   |------------------------------------------------------------------------->  |
   |                        |  onApprove fires          |                      |
   |                        |  POST .../paypal/capture  |                      |
   |                        |-------------------------->|                      |
   |                        |                           |  capture order       |
   |                        |                           |--------------------->|
   |                        |                           |<----------------------|
   |                        |<-- booking (CONFIRMED) ---|                      |
```

## Auth

Both endpoints below require the normal customer bearer token:
```
Authorization: Bearer <access_token>
```
Ownership is enforced server-side — a customer can only create/capture their own bookings.

## Response envelope

Every endpoint returns the same envelope shape:

```jsonc
// success
{
  "status": "success",
  "status_label": "Success",
  "data": { /* ... */ },
  "error": null
}

// error
{
  "status": "error",
  "status_label": "Error",
  "data": null,
  "error": {
    "code": "BOOKING_PAYMENT_NOT_CAPTURABLE",
    "message": "This booking's payment can't be captured."
  }
}
```

`message` is localized (`en`/`de`/`fr`) based on the request's locale — don't hardcode UI copy off it, use `code` for logic.

---

## 1. Create a booking with PayPal

```
POST /api/v1/bookings
```

Same endpoint as the existing Stripe flow — just add `payment_provider`.

### Request body

```jsonc
{
  "booking_calculation_id": "3f1b2c...-uuid",
  "starts_at": "2026-08-20T14:00:00Z",
  "terms_accepted": true,
  "payment_provider": "PAYPAL"   // "STRIPE" | "PAYPAL", defaults to "STRIPE" if omitted
}
```

### Response — `201 Created`

Only the fields relevant to payment are shown; the rest of `BookingResponse` (style, pricing breakdown, etc.) is unchanged from the Stripe flow.

```jsonc
{
  "status": "success",
  "data": {
    "id": "b0a1...-uuid",
    "reference": "AB12CD34",
    "status": "PENDING_PAYMENT",
    "total": "180.00",
    "deposit_amount": "180.00",
    "payment_schedule": "FULL_UPFRONT",
    "payments": [
      {
        "purpose": "FULL",
        "status": "PENDING",
        "amount": "180.00",
        "currency": "EUR",
        "provider": "PAYPAL",
        "client_secret": null,
        "paypal_order_id": "8AC63406YR317660T"
      }
    ],
    "...": "..."
  },
  "error": null
}
```

**Key fields for the PayPal path:**

| Field | Notes |
|---|---|
| `payments[0].provider` | `"PAYPAL"` |
| `payments[0].paypal_order_id` | The PayPal Order ID. Use this to render the PayPal button (see below). |
| `payments[0].client_secret` | Always `null` for PayPal — that field is Stripe-only. |
| `payments[0].status` | `"PENDING"` until the capture succeeds. |

If `payment_provider` is `"STRIPE"` (or omitted), the response is exactly as before: `provider: "STRIPE"`, `client_secret` populated, `paypal_order_id: null`.

### Errors

Same errors as the existing booking-creation flow (`BOOKING_CALCULATION_EXPIRED`, `BOOKING_PRICE_DRIFT`, `BOOKING_SLOT_UNAVAILABLE`, etc.) — nothing PayPal-specific can fail at this step except a transient PayPal outage, which currently surfaces as a generic `500`.

---

## 2. Capture the PayPal order

Call this **after** the customer approves the order in the PayPal UI (i.e. inside your `onApprove` handler).

```
POST /api/v1/bookings/{booking_id}/payments/paypal/capture
```

No request body.

### Response — `200 OK`

Returns the full, updated `BookingResponse` — same shape as `GET /api/v1/bookings/{booking_id}`.

```jsonc
{
  "status": "success",
  "data": {
    "id": "b0a1...-uuid",
    "status": "CONFIRMED",
    "payments": [
      {
        "purpose": "FULL",
        "status": "SUCCEEDED",
        "amount": "180.00",
        "currency": "EUR",
        "provider": "PAYPAL",
        "client_secret": null,
        "paypal_order_id": "8AC63406YR317660T"
      }
    ],
    "...": "..."
  },
  "error": null
}
```

- `booking.status` flips to `CONFIRMED` (for `FULL` or `DEPOSIT` purpose payments).
- `payments[0].status` flips to `SUCCEEDED`.
- **Idempotent**: calling this again after a successful capture just returns the same `200` with the booking already `CONFIRMED` — safe to retry on a flaky network without side effects (e.g. no duplicate confirmation email).

### Errors

| HTTP | `error.code` | Meaning | Suggested frontend handling |
|---|---|---|---|
| 404 | `BOOKING_NOT_FOUND` | Booking doesn't exist or doesn't belong to this customer | Treat as a hard failure, send them back to booking flow |
| 404 | `BOOKING_PAYMENT_NOT_FOUND` | No payment row exists on this booking (shouldn't happen in normal flow) | Hard failure |
| 409 | `BOOKING_PAYMENT_NOT_CAPTURABLE` | Payment isn't PayPal, or isn't in a capturable state (e.g. it's a Stripe booking, or already `FAILED`) | Hard failure — don't retry |
| 402 | `PAYPAL_PAYMENT_DECLINED` | PayPal declined the capture (e.g. the customer's funding source failed) | Show a "payment declined, try again or use a different method" message. The booking stays `PENDING_PAYMENT`; the customer can create a new booking/payment attempt. |
| 502 | `PAYPAL_API_UNAVAILABLE` | Couldn't reach PayPal | Show a transient-error message, offer a retry button (safe to retry — capture is idempotent) |

---

## Frontend implementation: PayPal JS SDK

You need a **PayPal Client ID** (public, safe to expose in frontend code — this is different from the server-side secret). Load PayPal's SDK with it:

```html
<script src="https://www.paypal.com/sdk/js?client-id=YOUR_PAYPAL_CLIENT_ID&currency=EUR&intent=capture"></script>
```

Use sandbox credentials during development (the backend currently points at `https://api-m.sandbox.paypal.com`), and swap to live credentials — both frontend Client ID and backend secret — together when going to production.

### Rendering the button

The key point: **do not** let PayPal's SDK create the order (`actions.order.create`) — the backend already created it. Wire `createOrder` to just resolve with the `paypal_order_id` you got back from `POST /api/v1/bookings`:

```js
paypal.Buttons({
  createOrder: (data, actions) => {
    // orderId came from the booking-creation response:
    // booking.payments[0].paypal_order_id
    return Promise.resolve(orderId);
  },

  onApprove: async (data, actions) => {
    // data.orderID === orderId, confirms the customer approved it.
    const res = await fetch(`/api/v1/bookings/${bookingId}/payments/paypal/capture`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    const body = await res.json();

    if (!res.ok) {
      // handle body.error.code as documented above
      return;
    }

    // body.data is the updated BookingResponse, status === "CONFIRMED"
    // navigate to booking confirmation screen
  },

  onCancel: (data) => {
    // Customer closed the PayPal popup without approving.
    // Booking stays PENDING_PAYMENT — nothing to clean up server-side.
    // Let them retry the button, or go back and choose Stripe instead.
  },

  onError: (err) => {
    // SDK-level error (network, popup blocked, etc.) — not a decline.
    // Show a generic retry message.
  },
}).render("#paypal-button-container");
```

### Notes

- **Amounts/currency**: only `EUR` is supported today (same as Stripe) — no currency selector needed.
- **No polling needed**: the capture endpoint is synchronous — by the time it returns `200`, the booking is already `CONFIRMED`. Don't build a "wait for webhook" polling loop; there isn't one on the critical path.
- **Retry semantics**: if `capture` fails with a network error (timeout, etc.) and you don't know if it landed, it's always safe to call it again — it's idempotent on both the "already succeeded" and "PayPal order already captured" cases.
- **Declines are terminal for that order**: if `PAYPAL_PAYMENT_DECLINED` comes back, don't retry the same capture call — the payment row is now `FAILED`. The customer needs to start over (new booking calculation → new booking → new PayPal order), same as a declined card would require on the Stripe side.
- **`GET /api/v1/bookings/{id}`** can be used at any time to re-fetch current status (e.g. on page reload after an approval popup closed unexpectedly) — it returns the same `payments[]` shape.

---

## Quick reference: all payment-related fields

### `BookingPaymentResponse`

| Field | Type | Notes |
|---|---|---|
| `purpose` | `"FULL" \| "DEPOSIT" \| "BALANCE"` | |
| `status` | `"PENDING" \| "SUCCEEDED" \| "FAILED" \| "CANCELED"` | |
| `amount` | decimal string, e.g. `"180.00"` | |
| `currency` | `"EUR"` | |
| `provider` | `"STRIPE" \| "PAYPAL"` | |
| `client_secret` | `string \| null` | Stripe only |
| `paypal_order_id` | `string \| null` | PayPal only |

### `BookingCreateRequest` addition

| Field | Type | Default |
|---|---|---|
| `payment_provider` | `"STRIPE" \| "PAYPAL"` | `"STRIPE"` |
