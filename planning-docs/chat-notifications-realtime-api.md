# Chat, Notifications & Realtime API

Reference for the frontend integration of: in-app chat (per booking), abuse
reporting, chat-language translation, notifications, and the WebSocket
push channel. All endpoints are versioned under `/api/v1`.

## Conventions

### Auth

Every endpoint below (except the two Stripe/Veriff-style webhooks, which
don't apply here) requires a bearer token from the existing auth flow:

```
Authorization: Bearer <access_token>
```

`user_type` on the token determines whether you're the "customer" or
"braider" side of a conversation - there's no separate chat-specific role.

### Response envelope

Every REST response (success or error) is wrapped the same way:

```json
{
  "status": "success",
  "status_label": "Success",
  "data": { /* endpoint-specific payload, or null on error */ },
  "error": null
}
```

On error:

```json
{
  "status": "error",
  "status_label": "Error",
  "data": null,
  "error": {
    "code": "CHAT_ACCESS_DENIED",
    "message": "You don't have access to this conversation."
  }
}
```

`message` is localized to the request's resolved locale (see below).
Validation errors (missing/malformed fields) come back as
`code: "VALIDATION_ERROR"` with an additional `error.details` array
(standard FastAPI/Pydantic shape) instead of the errors listed per-endpoint
below.

### Locale

Two independent locale concepts - don't conflate them:

- **Request/display locale** - resolved per-request from `?lang=` or the
  `Accept-Language` header (falls back to `en`). Controls error messages,
  notification `title`/`body` text, and a FLAGGED message's
  `violation_notice`. Supported: `en`, `de`, `fr`.
- **`chat_locale`** - an explicit, sticky preference stored on the user's
  profile (`PATCH /api/v1/users/me`). This is what drives chat message
  translation - see [Translation behavior](#translation-behavior). It is
  **not** inferred from `Accept-Language`; the user must set it.

### Pagination

Every list endpoint below takes:

| Query param | Default | Notes |
|---|---|---|
| `page` | `1` | 1-indexed |
| `page_size` | `20` | max `100` |

and returns:

```json
{
  "items": [ /* ... */ ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 42,
    "total_pages": 3,
    "has_next": true,
    "has_previous": false
  }
}
```

---

## 1. Setting your chat language

```
PATCH /api/v1/users/me
```

```json
{ "chat_locale": "en" }
```

Send `""` (empty string) to clear it. Allowed values: whatever
`supported_locales` is configured to (currently `en`, `de`, `fr`) - anything
else returns `422 INVALID_CHAT_LOCALE`.

`GET /api/v1/users/me` and every auth response (login/signup/refresh/etc.)
now also include `chat_locale` in the user object.

**Prompt the user to set this** the first time they open chat (or in
profile settings) - translation silently does nothing until both sides of a
conversation have set it.

---

## 2. Chat

### Data model

**Thread** - one per booking, between that booking's customer and braider.

```ts
type ChatThread = {
  id: string;               // uuid
  booking_id: string;       // uuid
  other_participant_id: string;
  other_participant_name: string;
  last_message_at: string | null;   // ISO 8601
  last_message_preview: string | null; // null if the last message was flagged
  last_message_flagged: boolean;
  unread_count: number;
  created_at: string;
};
```

**Message**

```ts
type ChatMessageStatus = "SENT" | "FLAGGED";

type ChatMessage = {
  id: string;
  thread_id: string;
  sender_id: string;
  status: ChatMessageStatus;
  body: string | null;           // null when status is FLAGGED
  body_locale: string | null;    // locale the sender wrote it in, if set
  translated_body: string | null;
  translated_locale: string | null;
  violation_notice: string | null; // populated (localized) when FLAGGED
  created_at: string;
};
```

**Important - flagged messages:** when `status` is `FLAGGED`, `body` is
always `null` and stays `null` forever - the platform never stores the
plaintext of a message that looks like it's sharing contact details or
payment/account info. Render `violation_notice` in place of the bubble text
(it's already localized server-side), e.g.:

> ⚠️ This message was withheld because it looks like it shares contact
> details or payment/account information...

Do not treat a FLAGGED response as an error - the send call still returns
`200` and the message is a real row in the thread; it's just redacted.

### Endpoints

#### List your conversations

```
GET /api/v1/chat/threads?page=1&page_size=20
```

→ `PaginatedData<ChatThread>`, newest activity first. Use this for the
chat inbox / conversation list screen.

#### Get or start the thread for a booking

```
GET /api/v1/chat/bookings/{booking_id}/thread
```

→ `ChatThread`. Call this when the user taps "Chat" from a booking detail
screen - it creates the thread on first call. Only succeeds once the
booking's deposit (or full payment) has gone through; it stays available
even if the booking is later cancelled.

Errors:
| Code | Status | When |
|---|---|---|
| `BOOKING_NOT_FOUND` | 404 | Bad booking id |
| `CHAT_ACCESS_DENIED` | 403 | You're neither the customer nor the braider on this booking |
| `CHAT_NOT_AVAILABLE` | 403 | No successful payment yet - gate the "Chat" button on booking status instead of showing this |

#### List messages in a thread

```
GET /api/v1/chat/threads/{thread_id}/messages?page=1&page_size=20
```

→ `PaginatedData<ChatMessage>`. **Ordered newest-first** (page 1 = most
recent) - reverse the page's `items` client-side if you render top-to-bottom.

Errors: `CHAT_THREAD_NOT_FOUND` (404), `CHAT_ACCESS_DENIED` (403, not a
participant).

#### Send a message

```
POST /api/v1/chat/threads/{thread_id}/messages
```

```json
{ "body": "Hi! Looking forward to my appointment." }
```

→ `ChatMessage` (the one just created - `SENT` or `FLAGGED`, see above).
Max length 2000 characters (server-validated; empty/whitespace-only is
rejected with the standard `VALIDATION_ERROR` shape, not a custom code).

Also triggers, server-side (you don't need to do anything for these -
listed so you know what to expect over the WebSocket):
- A `notification` created for the recipient.
- If both participants have set a **different** `chat_locale`, an async
  translation job - `translated_body`/`translated_locale` on this message
  will be `null` in the immediate response and filled in moments later,
  pushed via WebSocket (see [Realtime](#3-realtime-websocket)).

#### Mark a conversation as read

```
POST /api/v1/chat/threads/{thread_id}/read
```

→ `ChatThread` with `unread_count: 0`. Call when the user opens/foregrounds
a thread.

#### Report the other participant

```
POST /api/v1/chat/threads/{thread_id}/report
```

```json
{
  "reason": "HARASSMENT",
  "details": "Kept asking to pay outside the app.",
  "message_id": null
}
```

`reason` is one of: `HARASSMENT`, `INAPPROPRIATE_CONTENT`, `SPAM`,
`SCAM_OR_FRAUD`, `OFF_PLATFORM_SOLICITATION`, `OTHER`. `details` (≤1000
chars) and `message_id` (reference a specific message, e.g. from a
long-press "Report this message" action) are both optional.

→

```json
{
  "id": "…",
  "thread_id": "…",
  "reported_user_id": "…",
  "reason": "HARASSMENT",
  "status": "OPEN",
  "created_at": "…"
}
```

Reviewed by Afrobraid staff via the admin panel - there's no further
customer-facing state to poll (don't build a "report status" UI for
end users from this).

---

## 3. Realtime (WebSocket)

One connection per logged-in user, used for **both** live chat messages and
notifications.

```
wss://<host>/api/v1/ws?token=<access_token>
```

- The access token travels as a **query param** (browsers can't set custom
  headers on a WS handshake) - same JWT you already use for `Authorization`.
- On auth failure the server closes the socket with code `4401` before
  ever completing the handshake's application-level accept. Reconnect with
  a fresh token (e.g. after your normal token-refresh flow) rather than
  retrying the same one.
- The client doesn't need to send anything after connecting - it's a
  push-only channel from the server. (Sending arbitrary text is harmless
  and ignored.)
- **This is a live nudge, not a delivery guarantee.** Everything pushed
  here was already durably saved via a REST call first. If the socket was
  disconnected when something happened, don't try to "catch up" from the
  socket - just re-fetch the relevant list (`GET /threads/{id}/messages`,
  `GET /notifications`) on reconnect.
- Reconnect with backoff on close/error, same as any WS client.

### Event shapes

Every message is JSON with a top-level `type`:

**`chat_message`** - a new message was sent in one of your threads (you'll
get this whether you're the sender or the recipient, so multiple tabs/devices
stay in sync):

```json
{
  "type": "chat_message",
  "thread_id": "…",
  "message": { /* ChatMessage, same shape as the REST endpoints */ }
}
```

**`chat_message_translated`** - fired once, shortly after a `chat_message`
event, only when translation was actually triggered (see
[Translation behavior](#translation-behavior)):

```json
{
  "type": "chat_message_translated",
  "thread_id": "…",
  "message_id": "…",
  "translated_body": "Bonjour !",
  "translated_locale": "fr"
}
```

Patch the matching message in your local store by `message_id` rather than
re-fetching the whole thread.

**`notification`** - a new notification for you:

```json
{
  "type": "notification",
  "notification": { /* Notification, same shape as GET /notifications */ }
}
```

Use this to bump an unread badge / show a toast; the notification is
already persisted, so a page reload without the socket still shows it via
`GET /api/v1/notifications`.

### Minimal client sketch

```js
const socket = new WebSocket(`wss://api.example.com/api/v1/ws?token=${accessToken}`);

socket.onmessage = (event) => {
  const payload = JSON.parse(event.data);
  switch (payload.type) {
    case "chat_message":
      // append/replace payload.message in the thread payload.thread_id
      break;
    case "chat_message_translated":
      // patch translated_body/translated_locale onto the message by id
      break;
    case "notification":
      // increment unread badge, optionally toast payload.notification
      break;
  }
};
```

---

## 4. Translation behavior

Chat translation is **opt-in on both sides**, and only ever between the two
locales actually in play - it never machine-translates into every
supported language the way some other content in this API does (e.g.
review text).

| Sender `chat_locale` | Recipient `chat_locale` | Result |
|---|---|---|
| not set | (any) | No translation. `translated_body` stays `null`. |
| (any) | not set | No translation. |
| `en` | `en` (same) | No translation - nothing to translate. |
| `en` | `fr` (different) | Translated into `fr`, delivered async via `chat_message_translated`. |

A FLAGGED message is never translated (there's no plaintext to translate).

**UI recommendation:** show `body` by default; if `translated_body` is
present and the viewer's own `chat_locale` matches `translated_locale`,
prefer showing `translated_body` with a small "Translated from {body_locale}
· see original" affordance (same pattern as WhatsApp/Messenger's inline
translate).

---

## 5. Chat reports (admin)

For your admin panel, not the customer-facing app:

```
GET   /api/v1/admin/chat/reports?status=OPEN&page=1&page_size=20
PATCH /api/v1/admin/chat/reports/{report_id}
```

`GET` requires `ADMIN` role, defaults to `status=OPEN`; pass
`status=UNDER_REVIEW|RESOLVED|DISMISSED` or omit `status` entirely to
browse all. Returns `AdminChatReportResponse[]`, which includes
`reporter_name`/`reported_user_name`/`booking_id` for context.

`PATCH` body:

```json
{ "status": "RESOLVED", "admin_notes": "Warned the braider." }
```

---

## 6. Notifications

Generic, works the same for customers, braiders, and admins.

```ts
type NotificationType = "CHAT_NEW_MESSAGE" | "CHAT_MESSAGE_FLAGGED";

type Notification = {
  id: string;
  type: NotificationType;
  title: string;   // localized to the request's ?lang=/Accept-Language
  body: string;
  related_type: string | null;  // e.g. "chat_thread" - use for deep-linking
  related_id: string | null;    // e.g. the thread_id
  is_read: boolean;
  read_at: string | null;
  created_at: string;
};
```

Currently the only emitter wired up is chat (new message /
message-withheld) - `related_type: "chat_thread"` + `related_id` is enough
to deep-link straight into the right conversation from a notification tap.

### Endpoints

```
GET    /api/v1/notifications
PATCH  /api/v1/notifications/{notification_id}/read
POST   /api/v1/notifications/read-all
DELETE /api/v1/notifications/{notification_id}
```

**List** - `GET /api/v1/notifications`, query params (all optional, all
combinable with `page`/`page_size`):

| Param | Type | Notes |
|---|---|---|
| `is_read` | `bool` | filter to read-only / unread-only |
| `date_from` | ISO 8601 datetime | inclusive, compared to `created_at` |
| `date_to` | ISO 8601 datetime | inclusive |

→ `PaginatedData<Notification>`, newest first. `date_to < date_from`
returns `400 INVALID_DATE_RANGE`.

> When building the query string, **URL-encode the `+` in a UTC-offset ISO
> timestamp** (e.g. `2026-08-08T12:00:00+00:00` → `...%2B00:00`) - a raw
> `+` decodes as a space server-side. Use your HTTP client's `params`/query
> object rather than string-concatenating the URL.

**Mark one read** - `PATCH /api/v1/notifications/{id}/read` → `Notification`.

**Mark all read** - `POST /api/v1/notifications/read-all` →
`{ "marked_count": 3 }`.

**Delete** - `DELETE /api/v1/notifications/{id}` →
`{ "message": "Notification deleted." }`. `404 NOTIFICATION_NOT_FOUND` if
it's already gone or isn't yours.

---

## 7. Error code reference

New codes introduced by this feature set (in addition to the app's existing
generic ones like `VALIDATION_ERROR`, `INVALID_ACCESS_TOKEN`, `FORBIDDEN`):

| Code | HTTP | Meaning |
|---|---|---|
| `INVALID_CHAT_LOCALE` | 422 | `chat_locale` isn't one of the supported locales |
| `CHAT_NOT_AVAILABLE` | 403 | Booking hasn't had a successful payment yet |
| `CHAT_THREAD_NOT_FOUND` | 404 | Bad `thread_id` |
| `CHAT_ACCESS_DENIED` | 403 | Not a participant in this thread/booking |
| `CHAT_MESSAGE_NOT_FOUND` | 404 | Bad `message_id` on a report |
| `CHAT_REPORT_NOT_FOUND` | 404 | Bad `report_id` (admin) |
| `NOTIFICATION_NOT_FOUND` | 404 | Bad `notification_id`, or it's not yours |
| `INVALID_DATE_RANGE` | 400 | `date_to` before `date_from` |
| `BOOKING_NOT_FOUND` | 404 | Bad `booking_id` when opening a thread |

---

## 8. Suggested integration order

1. Add a "chat language" picker to profile/onboarding →
   `PATCH /api/v1/users/me { chat_locale }`.
2. Open the WebSocket right after login (and on every token refresh /
   reconnect) - keep it open app-wide, not per-screen.
3. Booking detail screen: show a "Chat" button once the booking is
   confirmed; on tap, `GET /api/v1/chat/bookings/{booking_id}/thread`,
   navigate to the thread using the returned `id`.
4. Thread screen: `GET .../messages` for history, send via
   `POST .../messages`, call `POST .../read` on open/foreground, patch
   the list live from `chat_message`/`chat_message_translated` WS events.
5. Inbox screen: `GET /api/v1/chat/threads` for the list + unread badges,
   refreshed from `chat_message` WS events without a full refetch (bump
   `unread_count` and `last_message_*` locally, or just refetch the row).
6. Notification bell: `GET /api/v1/notifications`, badge from unread
   count, live-bump from `notification` WS events, mark-read on open.
7. "Report" affordance in the thread's overflow menu →
   `POST .../report`.
