# Contact Us — API Contract

> **STATUS: LIVE.** Implemented on this branch as a brand-new module (`app/modules/contact/`), migrated and tested against a local database. Not yet merged to `staging`.

---

## 0. Conventions

**Response envelope.** Every response — success or error — is wrapped the same way as the rest of the API:

```jsonc
// success
{ "status": "success", "status_label": "Success", "data": { /* ... */ }, "error": null }

// error
{ "status": "error", "status_label": "Error", "data": null, "error": { "code": "SOME_CODE", "message": "Human-readable, already localized." } }
```

Read the payload from `data`; on a non-2xx response, branch on `error.code` (stable) rather than `error.message` (localized prose, for display only).

**Auth.** None. This endpoint is public — no `Authorization` header needed or checked.

**Locale.** `?lang=en|de|fr` query param, falling back to the `Accept-Language` header, falling back to `en` — same mechanism as the rest of the API. It only affects the language of the confirmation `message` in the response (§1) and of any `VALIDATION_ERROR`/`RATE_LIMITED` error text — it does **not** need to match the language the user actually typed their message in; that's stored verbatim, as-is, untranslated.

**No email is sent.** Submitting the form only persists it server-side for the team to review. The customer/braider does **not** receive a confirmation email, and no internal notification email fires either — there's no polling/webhook to know when it's read. If you want an on-screen "thanks, we got it" confirmation, use the `data.message` string in the response (§1) — it's already localized.

---

## 1. Submit the Contact Us form — `POST /api/v1/contact`

**Public.** Rate-limited to **5 requests/hour per client IP**. Use one form/endpoint for both the customer app and the braider app — the only difference is which `platform` value you send.

### Request body

```jsonc
{
  "first_name": "Ada",
  "last_name": "Nwosu",
  "phone_number": "+15551234567",
  "email": "ada@example.com",
  "subject": "Question about pricing",
  "message": "Do you offer discounts for repeat bookings?",
  "platform": "CUSTOMER",
  "purpose": "PRICING"
}
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `first_name` | string | Yes | Trimmed server-side, must not be blank after trimming. |
| `last_name` | string | Yes | Same as `first_name`. |
| `phone_number` | string | Yes | **E.164 format** — a leading `+`, no spaces/dashes/parens, e.g. `"+15551234567"`, `"+2348012345678"`. Anything else is a `VALIDATION_ERROR`. |
| `email` | string | Yes | Must be a valid email address. |
| `subject` | string \| null | No | Trimmed; empty string is treated as not provided (`null`). Max 255 chars. |
| `message` | string | Yes | Trimmed, must not be blank after trimming. Max 5000 chars. |
| `platform` | enum | Yes | `"CUSTOMER"` or `"BRAIDER"` — which app the message came from. See §3. |
| `purpose` | enum | No | One of §3's `ContactPurpose` values. **Omit it (or don't send the field at all) to default to `"GENERAL"`.** |

### Response `201`

`APIResponse<ContactSubmissionResponse>`

```jsonc
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "c46e9132-5220-42e2-b7f4-f2d2fcd44fc1",
    "message": "Thanks for reaching out - we've received your message and will get back to you soon."
  },
  "error": null
}
```

| Field | Notes |
|---|---|
| `id` | The submission's server-generated ID. Not currently retrievable through any other endpoint — treat it as opaque, useful only for support correspondence ("reference this ID") if you want to surface it. |
| `message` | A ready-to-display confirmation string, already localized per §0. Safe to show directly, or ignore it and render your own copy. |

### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `VALIDATION_ERROR` | 422 | A required field is missing/blank, `phone_number` isn't E.164, `email` isn't a valid address, `message`/`subject` exceed max length, or `platform`/`purpose` isn't one of the allowed enum values. `error.details` (validation errors only, see §0's envelope) lists each offending field. |
| `RATE_LIMITED` | 429 | More than 5 submissions from the same IP within an hour. Response includes a `Retry-After` header (seconds) — use it to disable the submit button / show a cooldown instead of retrying immediately. |

---

## 2. Suggested frontend flow

1. Render the form with all fields in §1. `subject` and `purpose` can be hidden/optional in the UI — omit them entirely from the request if unset, don't send empty strings for `purpose` (it's an enum, not free text).
2. Set `platform` based on which app is submitting — hardcode it per app rather than exposing it as a user-facing choice.
3. If you want a "reason for contacting us" dropdown, map it to `purpose` (§3); default the dropdown to "General" if you don't want to ask at all.
4. On `201`, show `data.message` (or your own "thanks" copy) and clear the form. There's nothing to poll — no status ever changes on this submission from the client's perspective.
5. On `VALIDATION_ERROR`, map `error.details[].loc` (last element is the field name) to the corresponding form field for inline errors.
6. On `RATE_LIMITED`, disable the form and show a retry countdown using the `Retry-After` header value (seconds).

---

## 3. Reference — enums used above

| Enum | Values | Notes |
|---|---|---|
| `ContactPlatform` (`platform`) | `CUSTOMER`, `BRAIDER` | Required — tells the team which app the message came from. |
| `ContactPurpose` (`purpose`) | `GENERAL`, `PARTNER`, `PRICING`, `FAQS` | Optional, defaults to `GENERAL`. Expect more values to be added over time — treat an unrecognized future value as "show it generically" rather than hardcoding an exhaustive switch with no fallback. |

---

## 4. Not in scope (mentioned for completeness only)

There's currently no way to list/read back submitted contact messages through the API — no admin endpoint exists yet. The team reviews these directly in the database for now. If an admin dashboard needs to list/search/resolve submissions, that's a separate, not-yet-built surface — flag it to backend if/when that's needed.
