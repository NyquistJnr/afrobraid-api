# PayPal via Stripe — Integration Note

Supersedes the earlier standalone-PayPal docs (removed). PayPal now works through the **existing Stripe checkout flow** — no new backend endpoints, no new credentials, no separate PayPal integration. This is Stripe's own native support for PayPal as a payment method on the same PaymentIntent your frontend already confirms today.

## What changed on the backend

One line, in `app/modules/bookings/payments/client.py`: the PaymentIntent creation call no longer hardcodes `payment_method_types: ["card"]`. Omitting it turns on Stripe's **dynamic payment methods** — Stripe automatically shows/ranks whichever payment methods are enabled in the Dashboard for the customer's currency, location, and amount. Nothing else about the booking API changed: same `POST /api/v1/bookings` request/response shape as before, same `client_secret` returned, same webhook.

## What you need to do in the Stripe Dashboard

1. Go to **Settings → Payment methods** in the Stripe Dashboard (dashboard.stripe.com/settings/payment_methods).
2. Find **PayPal** in the list and turn it on.
   - This is only available because your business is based in the EU — Stripe restricts PayPal-via-Stripe to EU (excl. Hungary), UK, Switzerland, Norway, and Liechtenstein.
3. Do the same in **both** your test-mode and live-mode Dashboard settings when you're ready (they're configured separately).

That's the entire setup — no client ID, secret, or webhook ID to manage for PayPal specifically. It rides on your existing `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`.

## What the frontend needs to change

This is the one real piece of frontend work. Today, if the integration only handles cards, `stripe.confirmPayment()` likely doesn't need to leave the page. PayPal is a **redirect-based** payment method — the customer gets sent to PayPal to approve, then back to your site — so two things become necessary once PayPal is enabled:

1. **Pass a `return_url`** in `confirmPayment`:
   ```js
   const { error } = await stripe.confirmPayment({
     elements,
     confirmParams: {
       return_url: "https://yourapp.com/booking/confirm", // must exist, see below
     },
     redirect: "if_required", // keeps cards in-page; PayPal still redirects
   });
   ```
   `redirect: "if_required"` means Stripe only actually redirects the browser for payment methods that need it (PayPal). Card payments still resolve in-page exactly as before.

2. **Handle the return page.** After the customer approves on PayPal and is redirected back to `return_url`, Stripe appends query params (`payment_intent`, `payment_intent_client_secret`, `redirect_status`). On that page:
   ```js
   const clientSecret = new URLSearchParams(window.location.search).get("payment_intent_client_secret");
   const { paymentIntent } = await stripe.retrievePaymentIntent(clientSecret);

   if (paymentIntent.status === "succeeded") {
     // show booking confirmed — the backend's Stripe webhook has already
     // (or will momentarily) flip the booking to CONFIRMED server-side
   } else if (paymentIntent.status === "processing") {
     // rare for PayPal, but handle it: show a pending state
   } else {
     // payment_failed or requires_payment_method — show retry UI
   }
   ```
   The backend's existing Stripe webhook (`payment_intent.succeeded` / `payment_intent.payment_failed`) is what actually confirms the booking server-side — this page is just reflecting that back to the customer, same as it would for any other outcome today.

No other frontend changes are needed — the PayPal button itself is rendered by Stripe's Payment Element automatically once it's enabled in the Dashboard; there's no separate PayPal SDK to load or button to build.
