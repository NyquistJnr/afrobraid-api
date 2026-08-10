# Admin — User Management API

Base URL prefix: `/api/v1/admin/users`

## Auth

All endpoints require a Bearer JWT for a user with role `ADMIN`.

```
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token → `401 INVALID_ACCESS_TOKEN`
- Wrong role → `403 FORBIDDEN`

---

## GET `/api/v1/admin/users` — List users

### Query params

| Param | Type | Notes |
|---|---|---|
| `user_type` | `UserType` (`CUSTOMER`, `BRAIDER`, `ADMIN`) | optional; omit to list every user |
| `page` | int | default 1, min 1 |
| `page_size` | int | default 20, min 1, max 100 |

Results are ordered newest-first (`created_at DESC`).

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "items": [
      {
        "id": "5b1c1a2e-9d3e-4b1a-8c3e-2f1a9b6d4e10",
        "first_name": "Amara",
        "last_name": "Okafor",
        "email": "amara@example.com",
        "phone_number": "+491701234567",
        "user_type": "BRAIDER",
        "is_email_verified": true,
        "is_active": false,
        "suspension_reason": "Fraudulent bookings",
        "suspended_at": "2026-08-24T09:00:00Z",
        "created_at": "2026-05-01T12:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1,
      "has_next": false,
      "has_previous": false
    }
  },
  "error": null
}
```

`is_active: false` means the account is currently suspended. `suspension_reason`/`suspended_at` are both `null` for an account that's never been suspended, and are cleared back to `null` on unsuspend (not just "reason blank").

---

## POST `/api/v1/admin/users/{user_id}/suspend` — Suspend a user

Blocks login immediately. An existing session is also cut off on its next token refresh (not just new logins) — suspension is enforced on every authenticated request, not only at sign-in.

### Path params

| Param | Type |
|---|---|
| `user_id` | UUID |

### Request body

```json
{ "reason": "Fraudulent bookings" }
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `reason` | string | no | Max 500 chars. Blank/whitespace-only is treated as no reason (stored as `null`). If given, shown to the user verbatim on their next login attempt — see below. |

Body can be omitted entirely (`{}` or no body) to suspend without a reason.

### Response `200`

Same shape as a list item (`AdminUserResponse`):

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "5b1c1a2e-9d3e-4b1a-8c3e-2f1a9b6d4e10",
    "first_name": "Amara",
    "last_name": "Okafor",
    "email": "amara@example.com",
    "phone_number": "+491701234567",
    "user_type": "BRAIDER",
    "is_email_verified": true,
    "is_active": false,
    "suspension_reason": "Fraudulent bookings",
    "suspended_at": "2026-08-24T09:00:00Z",
    "created_at": "2026-05-01T12:00:00Z"
  },
  "error": null
}
```

### What the suspended user sees on login

No frontend change needed. The existing login error response (`403 USER_NOT_ACTIVE`) now carries the reason inline in `error.message`, localized to whatever locale the login request is in:

```json
{
  "status": "error",
  "status_label": "Error",
  "data": null,
  "error": {
    "code": "USER_NOT_ACTIVE",
    "message": "This account has been suspended: Fraudulent bookings"
  }
}
```

If no reason was given at suspend time, the message falls back to the original generic text: `"This account has been deactivated."`

### Errors

| Code | Status | When |
|---|---|---|
| `USER_NOT_FOUND` | 404 | `user_id` doesn't exist |
| `CANNOT_SUSPEND_SELF` | 409 | the calling admin tries to suspend their own account |
| `VALIDATION_ERROR` | 422 | `reason` over 500 chars |

---

## POST `/api/v1/admin/users/{user_id}/unsuspend` — Lift a suspension

No request body.

### Path params

| Param | Type |
|---|---|
| `user_id` | UUID |

### Response `200`

Same `AdminUserResponse` shape, with `is_active: true` and `suspension_reason`/`suspended_at` both reset to `null`.

Calling this on a user who isn't currently suspended is harmless and idempotent — it just (re)confirms `is_active: true`.

### Errors

| Code | Status | When |
|---|---|---|
| `USER_NOT_FOUND` | 404 | `user_id` doesn't exist |

---

## Common error codes

| Code | HTTP status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `FORBIDDEN` | 403 | caller isn't an `ADMIN` |
| `USER_NOT_FOUND` | 404 | `user_id` doesn't exist |
| `CANNOT_SUSPEND_SELF` | 409 | suspend called with `user_id` == the calling admin's own id |
| `VALIDATION_ERROR` | 422 | malformed request body/params |
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
