# Admin — Auth API

Base URL prefix: `/api/v1/admin/auth`

ADMIN accounts are **invite-only**. Regular signup (`POST /api/v1/auth/signup/email`) and regular
social login (`POST /api/v1/auth/social/{provider}`) both reject `"ADMIN"` as a `user_type` — the
only way a new ADMIN user is ever created is through the invite flow below. Once an ADMIN account
exists, it signs in through the separate admin-only login endpoints (also below) — the regular
`/api/v1/auth/login` and `/api/v1/auth/social/{provider}` endpoints will authenticate an admin's
credentials fine, but treat them like any other user; use the admin endpoints when you specifically
need to assert the caller is an admin.

## Auth

`POST /invites` requires a Bearer JWT for a user with role `ADMIN` (same as every other
`/api/v1/admin/...` route). Every other endpoint on this page is unauthenticated by design — that's
how you *become* authenticated as an admin.

```
Authorization: Bearer <access_token>
```

---

## POST `/api/v1/admin/auth/invites` — Invite a new admin

Admin-only. Sends an invite link to `email`. A previously-issued, still-pending invite for the same
email is silently revoked when a new one is sent, so only the latest link ever works.

### Request body

```json
{ "email": "new-admin@example.com" }
```

### Response `201`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": { "message": "Invite sent.", "email": "new-admin@example.com" },
  "error": null
}
```

The invite email links to `{FRONTEND_URL}/admin/invite/accept?token=<raw_token>` and expires after
`ADMIN_INVITE_EXPIRE_HOURS` (default 72h, env-configurable).

### Errors

| Code | Status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `FORBIDDEN` | 403 | caller isn't an `ADMIN` |
| `EMAIL_ALREADY_EXISTS` | 409 | `email` already belongs to a user (any type) |
| `VALIDATION_ERROR` | 422 | malformed email |

---

## POST `/api/v1/admin/auth/invites/accept` — Accept an invite via email/password

Public. Completes account creation for a pending invite: creates the ADMIN user (pre-verified —
the invite itself, sent by an existing admin, is the trust anchor) and logs them in.

### Request body

```json
{
  "token": "<raw_token_from_email_link>",
  "first_name": "Nyla",
  "last_name": "Admin",
  "password": "Str0ngPassword!"
}
```

`last_name` is optional. `password` follows the same strength rule as regular signup (min 8 chars,
at least one letter and one number).

### Response `200`

Same `AuthTokenResponse` shape as regular login/signup-verify (access/refresh tokens, `user_type:
"ADMIN"`, no `braider` block).

### Errors

| Code | Status | When |
|---|---|---|
| `ADMIN_INVITE_INVALID` | 400 | token unknown, expired, already accepted, or revoked (e.g. superseded by a newer invite) |
| `EMAIL_ALREADY_EXISTS` | 409 | the invited email was registered by some other path after the invite was sent |
| `VALIDATION_ERROR` | 422 | malformed body / weak password |

---

## POST `/api/v1/admin/auth/invites/accept/social/{provider}` — Accept an invite via social login

Public. `provider` ∈ `google`, `facebook`, `tiktok`. The provider's verified email must exactly
match the email the invite was sent to, or the invite is rejected — this prevents accepting someone
else's invite with your own social account.

### Request body

```json
{ "token": "<raw_token_from_email_link>", "provider_token": "<provider_id_token>" }
```

### Response `200`

Same `AuthTokenResponse` shape as above.

### Errors

| Code | Status | When |
|---|---|---|
| `ADMIN_INVITE_INVALID` | 400 | token unknown/expired/accepted/revoked, or the provider identity is already linked to an account |
| `ADMIN_INVITE_EMAIL_MISMATCH` | 403 | the provider's verified email doesn't match the invite's email |
| `EMAIL_ALREADY_EXISTS` | 409 | the invited email was registered by some other path after the invite was sent |
| `SOCIAL_AUTH_FAILED` | 401 | provider token couldn't be verified |
| `UNSUPPORTED_PROVIDER` | 400 | `provider` isn't one of `google`/`facebook`/`tiktok` |

---

## POST `/api/v1/admin/auth/login` — Admin email/password login

Public. Same credential check as regular login, plus a role assertion. If the credentials are
correct but the account **isn't** ADMIN, this returns the exact same `INVALID_CREDENTIALS` error as
a wrong password — it never reveals that a non-admin account exists at that email.

### Request body

Same shape as `POST /api/v1/auth/login`: `{ "email", "password", "remember_me"? }`.

### Response `200`

`AuthTokenResponse`, `user_type: "ADMIN"`.

### Errors

| Code | Status | When |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | wrong password, unknown email, **or** correct credentials for a non-admin account |
| `USER_NOT_ACTIVE` | 403 | account is deactivated/suspended |
| `EMAIL_NOT_VERIFIED` | 403 | email not yet verified (shouldn't happen for an invite-created admin) |
| `RATE_LIMITED` | 429 | too many attempts for this email |

---

## POST `/api/v1/admin/auth/social/{provider}` — Admin social login

Public. `provider` ∈ `google`, `facebook`, `tiktok`. **Never creates an account** — only signs in an
existing user already linked to that provider (or matched by verified email) who is ADMIN. If no
matching user exists, or the matched user isn't ADMIN, this returns `SOCIAL_AUTH_FAILED` — same
non-disclosure reasoning as the email login above. To create a new admin via social login, use
`POST /invites/accept/social/{provider}` with a valid invite instead.

### Request body

```json
{ "provider_token": "<provider_id_token>" }
```

Note: unlike the regular `/api/v1/auth/social/{provider}` endpoint, there's no `user_type` field —
this endpoint can't create a user, so it wouldn't do anything.

### Response `200`

`AuthTokenResponse`, `user_type: "ADMIN"`.

### Errors

| Code | Status | When |
|---|---|---|
| `SOCIAL_AUTH_FAILED` | 401 | no matching user, or the matched user isn't ADMIN, or the provider token couldn't be verified |
| `USER_NOT_ACTIVE` | 403 | account is deactivated/suspended |
| `UNSUPPORTED_PROVIDER` | 400 | `provider` isn't one of `google`/`facebook`/`tiktok` |

---

## Common error codes

| Code | HTTP status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token (`/invites` only) |
| `FORBIDDEN` | 403 | caller isn't an `ADMIN` (`/invites` only) |
| `VALIDATION_ERROR` | 422 | malformed request body |
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
