# PayPal Account Setup — Getting Your `.env` Values

Walks through getting the four PayPal values the backend needs:

```
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
PAYPAL_WEBHOOK_ID=...
PAYPAL_API_BASE_URL=...
```

Do this twice: once for **sandbox** (development/testing, do this first) and once for **live** (production, only once you're ready to accept real money).

---

## 1. Create a PayPal Developer account

1. Go to **developer.paypal.com** and log in with a PayPal account (or create one — a personal account is fine to start; you'll need a **Business** account before you can go live).
2. This gives you access to the **Developer Dashboard**, separate from paypal.com itself. Sandbox testing doesn't require any business verification — you can start immediately.

## 2. Create an App (this gives you the Client ID + Secret)

1. In the Developer Dashboard, go to **Apps & Credentials**.
2. Make sure the toggle at the top is set to **Sandbox** (not Live) for now.
3. Click **Create App**.
   - Name it something like `afrobraid-api-sandbox`.
   - App type: **Merchant** (this is the type that can create/capture orders, which is what our backend does).
4. Once created, you'll land on the app's detail page with:
   - **Client ID** → this is `PAYPAL_CLIENT_ID`
   - **Secret** (click "Show") → this is `PAYPAL_CLIENT_SECRET`

That's 2 of the 4 values done.

**Note on the Client ID**: this same value also needs to go to your **frontend** (to load PayPal's JS SDK, as covered in the integration doc) — it's meant to be public. The **Secret** must never go to the frontend or any client-side code; it's backend-only, same as `STRIPE_SECRET_KEY`.

## 3. Set the API base URL

For the sandbox app:
```
PAYPAL_API_BASE_URL=https://api-m.sandbox.paypal.com
```
This is already the default in `.env.example`, so nothing to change for sandbox.

For a live app later:
```
PAYPAL_API_BASE_URL=https://api-m.paypal.com
```

## 4. Create the webhook (gives you `PAYPAL_WEBHOOK_ID`)

The backend listens for PayPal events at:
```
POST /api/v1/webhooks/paypal/payments
```
That's a reconciliation safety net (the primary confirmation path doesn't depend on it, per the integration doc), but it still needs to be registered so PayPal has somewhere to send `PAYMENT.CAPTURE.*` events.

1. Still on your sandbox app's page in the Developer Dashboard, scroll to **Sandbox Webhooks** (or go to **Webhooks** in the sidebar).
2. Click **Add Webhook**.
3. **Webhook URL**: your backend's publicly reachable URL + the path above, e.g.:
   ```
   https://your-domain.com/api/v1/webhooks/paypal/payments
   ```
   - For local development, PayPal can't reach `localhost` — use a tunnel like **ngrok** (`ngrok http 8000`, same idea as the Stripe CLI tunnel you're likely already using) and point the webhook at the ngrok URL. You already do this for Stripe (see `STRIPE_CONNECT_REFRESH_URL` in your `.env` pointing at an ngrok URL) — same pattern here.
4. **Event types to subscribe to** — select at minimum:
   - `PAYMENT.CAPTURE.COMPLETED`
   - `PAYMENT.CAPTURE.DENIED`
   (Everything else PayPal sends is safely ignored by the backend, so it's fine to select "all events" too if you'd rather not hunt through the list — just make sure those two are included.)
5. Save. PayPal shows you the new webhook's **Webhook ID** — that's `PAYPAL_WEBHOOK_ID`.

## 5. Fill in `.env`

```
PAYPAL_CLIENT_ID=<from step 2>
PAYPAL_CLIENT_SECRET=<from step 2>
PAYPAL_WEBHOOK_ID=<from step 4>
PAYPAL_API_BASE_URL=https://api-m.sandbox.paypal.com
```

Do the same for `.env.test` and `.env.prod` — though note `.env.test` doesn't actually need real values, because the backend short-circuits all PayPal calls with fake responses whenever `ENVIRONMENT=test` (same as it does for Stripe), so nothing hits the real PayPal API during automated tests.

## 6. Test it with a sandbox buyer account

PayPal auto-creates a sandbox **personal** (buyer) and **business** (merchant) account for you when you sign up. Find them under **Sandbox Accounts** in the Developer Dashboard — you can view/reset each one's login and starting balance there. Use the sandbox personal account's email/password to log in and approve payments when testing the checkout flow end-to-end (via the frontend's PayPal button, in the sandbox environment PayPal shows a "this is a sandbox" banner so you can't confuse it with a real transaction).

## 7. Going live

When you're ready for real payments:

1. Upgrade your PayPal account to a **Business** account if you haven't (required to accept live payments) — paypal.com will walk you through business verification (business details, bank account for payouts, etc.).
2. In the Developer Dashboard, switch the toggle from **Sandbox** to **Live**, and repeat steps 2–4 there: create a **live** app (new Client ID/Secret, separate from sandbox), and a **live** webhook (new Webhook ID) pointing at your real production domain.
3. Update `.env.prod` with the live values and `PAYPAL_API_BASE_URL=https://api-m.paypal.com`.
4. Also swap the frontend's PayPal JS SDK `client-id` to the live Client ID for production builds.

Sandbox and live are entirely separate credential sets — nothing carries over automatically, so don't forget step 2 (new webhook) when you flip to live, or webhook events will silently go nowhere.
