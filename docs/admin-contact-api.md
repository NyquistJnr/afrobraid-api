# Admin Contact Submissions API

Base URL prefix: `/api/v1/admin/contact-submissions`

All endpoints require a Bearer JWT for a user with role `ADMIN`.

## GET `/api/v1/admin/contact-submissions`

Lists Contact Us submissions, newest first.

| Param | Type | Notes |
|---|---|---|
| `platform` | `CUSTOMER` or `BRAIDER` | optional |
| `purpose` | `GENERAL`, `PARTNER`, `PRICING`, `FAQS` | optional |
| `is_read` | boolean | optional; use `false` for unread inbox |
| `date_from`, `date_to` | ISO date | optional; bounds `created_at` |
| `search` | string | optional; searches name, email, phone, subject, and message |
| `page`, `page_size` | int | default pagination; max page size 100 |

Each item includes the submitted fields plus `is_read`, `read_at`, and `read_by_admin_id`.

## GET `/api/v1/admin/contact-submissions/{submission_id}`

Gets a single submission.

## POST `/api/v1/admin/contact-submissions/{submission_id}/mark-read`

Marks the submission as read, setting `is_read=true`, `read_at=now`, and `read_by_admin_id` to the calling admin.

## POST `/api/v1/admin/contact-submissions/{submission_id}/mark-unread`

Marks the submission as unread, clearing `read_at` and `read_by_admin_id`.
