# Admin - Chat API

Base URL prefix: `/api/v1/admin/chat/reports`

## Auth

All endpoints require a Bearer JWT for a user with role `ADMIN`.

```http
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token -> `401 INVALID_ACCESS_TOKEN`
- Wrong role -> `403 FORBIDDEN`

---

## Chat report values

### Report reasons

| Reason |
|---|
| `HARASSMENT` |
| `INAPPROPRIATE_CONTENT` |
| `SPAM` |
| `SCAM_OR_FRAUD` |
| `OFF_PLATFORM_SOLICITATION` |
| `OTHER` |

### Report statuses

| Status | Meaning |
|---|---|
| `OPEN` | Newly submitted report awaiting moderation. |
| `UNDER_REVIEW` | Admin has acknowledged the report and is investigating. |
| `RESOLVED` | Report was acted on or otherwise completed. |
| `DISMISSED` | Report was reviewed and dismissed. |

---

## GET `/api/v1/admin/chat/reports` - List chat reports for moderation

Returns paginated chat reports with booking, reporter, reported user, optional message, reason, details, status, and admin notes. Results are ordered newest-first (`created_at DESC`).

### Query params

| Param | Type | Notes |
|---|---|---|
| `status` | `ChatReportStatus` (`OPEN`, `UNDER_REVIEW`, `RESOLVED`, `DISMISSED`) | optional in OpenAPI; current implementation defaults to `OPEN` when omitted |
| `page` | int | default 1, min 1 |
| `page_size` | int | default 20, min 1, max 100 |

Current implementation note: omitting `status` returns `OPEN`, not all statuses.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "items": [
      {
        "id": "ec17388d-03d5-4fe3-a896-ef301d10c9e1",
        "thread_id": "d0342619-b887-49c4-b61b-4490da735389",
        "booking_id": "80414d59-d58f-4f39-97f8-6f94e73c5c02",
        "reporter_id": "a5088658-6efb-4aa5-bcde-f4dd6efcd124",
        "reporter_name": "Nyla Okafor",
        "reported_user_id": "18f61b9b-377a-43a7-b763-36798cdd6e7e",
        "reported_user_name": "Amina Bello",
        "message_id": "6f0a52b0-e4e6-4ea7-9230-c0c9726f5161",
        "reason": "OFF_PLATFORM_SOLICITATION",
        "details": "The user asked me to pay outside the app.",
        "status": "OPEN",
        "admin_notes": null,
        "created_at": "2026-08-12T09:30:00Z",
        "updated_at": "2026-08-12T09:30:00Z"
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

### Response fields

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Chat report id. |
| `thread_id` | UUID | Chat thread id. |
| `booking_id` | UUID | Booking associated with the chat thread. |
| `reporter_id` | UUID | User who submitted the report. |
| `reporter_name` | string | Reporter full name, resolved server-side. |
| `reported_user_id` | UUID | User being reported. |
| `reported_user_name` | string | Reported user's full name, resolved server-side. |
| `message_id` | UUID or null | Specific reported message, if any. |
| `reason` | `ChatReportReason` | Report category. |
| `details` | string or null | Reporter-provided details. |
| `status` | `ChatReportStatus` | Current admin workflow state. |
| `admin_notes` | string or null | Internal admin notes. |
| `created_at` / `updated_at` | ISO datetime | Report timestamps. |

---

## PATCH `/api/v1/admin/chat/reports/{report_id}` - Update a chat report

Updates a report's admin status and, optionally, its internal admin notes.

### Path params

| Param | Type |
|---|---|
| `report_id` | UUID |

### Request body

```json
{
  "status": "UNDER_REVIEW",
  "admin_notes": "Checking booking/payment history and recent messages."
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `status` | `ChatReportStatus` | yes | New report workflow status. |
| `admin_notes` | string or null | no | Trimmed server-side. Blank/whitespace-only becomes `null`. If omitted, existing notes are unchanged. |

Important note: sending `"admin_notes": null` or a blank string does not clear existing notes because the service only writes notes when the validated value is non-null.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "ec17388d-03d5-4fe3-a896-ef301d10c9e1",
    "thread_id": "d0342619-b887-49c4-b61b-4490da735389",
    "booking_id": "80414d59-d58f-4f39-97f8-6f94e73c5c02",
    "reporter_id": "a5088658-6efb-4aa5-bcde-f4dd6efcd124",
    "reporter_name": "Nyla Okafor",
    "reported_user_id": "18f61b9b-377a-43a7-b763-36798cdd6e7e",
    "reported_user_name": "Amina Bello",
    "message_id": "6f0a52b0-e4e6-4ea7-9230-c0c9726f5161",
    "reason": "OFF_PLATFORM_SOLICITATION",
    "details": "The user asked me to pay outside the app.",
    "status": "UNDER_REVIEW",
    "admin_notes": "Checking booking/payment history and recent messages.",
    "created_at": "2026-08-12T09:30:00Z",
    "updated_at": "2026-08-12T10:15:00Z"
  },
  "error": null
}
```

### Errors

| Code | Status | When |
|---|---|---|
| `CHAT_REPORT_NOT_FOUND` | 404 | `report_id` does not exist |
| `VALIDATION_ERROR` | 422 | malformed UUID/body or invalid status enum |

---

## Common error codes

| Code | HTTP status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `FORBIDDEN` | 403 | caller is not an `ADMIN` |
| `CHAT_REPORT_NOT_FOUND` | 404 | `report_id` does not exist |
| `VALIDATION_ERROR` | 422 | malformed query params/path params/body |
| `INTERNAL_SERVER_ERROR` | 500 | unhandled server error |

All error responses share the standard envelope:

```json
{
  "status": "error",
  "status_label": "Error",
  "data": null,
  "error": { "code": "string", "message": "string" }
}
```
