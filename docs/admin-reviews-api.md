# Admin - Reviews API

Base URL prefix: `/api/v1/admin/reviews`

## Auth

All endpoints require a Bearer JWT for a user with role `ADMIN`.

```http
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token -> `401 INVALID_ACCESS_TOKEN`
- Wrong role -> `403 FORBIDDEN`

---

## Review statuses

| Status | Meaning |
|---|---|
| `PENDING` | The written comment is waiting for admin moderation. |
| `APPROVED` | The written comment is publicly visible. The rating counts toward the braider average. |
| `REJECTED` | The review is rejected. Its rating is excluded from the braider average. |

---

## GET `/api/v1/admin/reviews` - List reviews for moderation

Returns paginated reviews for the admin moderation queue. Results are ordered by `created_at` ascending, so the oldest matching reviews appear first.

### Query params

| Param | Type | Notes |
|---|---|---|
| `status` | `ReviewStatus` (`PENDING`, `APPROVED`, `REJECTED`) | optional in OpenAPI; current implementation defaults to `PENDING` when omitted |
| `page` | int | default 1, min 1 |
| `page_size` | int | default 20, min 1, max 100 |

Current implementation note: omitting `status` returns `PENDING`, not all statuses.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "items": [
      {
        "id": "9d871401-2305-4be0-a7b1-1360fb0f4f4f",
        "braider_id": "4b220c8e-b5d1-4f33-9dbf-4784144ce007",
        "braider_name": "Amina Bello",
        "customer_id": "a5088658-6efb-4aa5-bcde-f4dd6efcd124",
        "customer_name": "Nyla Okafor",
        "rating": 5,
        "comment_en": "Beautiful work and very professional.",
        "comment_de": "Schoene Arbeit und sehr professionell.",
        "comment_fr": "Tres beau travail et tres professionnel.",
        "status": "PENDING",
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
| `id` | UUID | Review id. |
| `braider_id` | UUID | Braider profile id being reviewed. |
| `braider_name` | string | Braider display name, resolved server-side. |
| `customer_id` | UUID | Customer user id who wrote the review. |
| `customer_name` | string | Customer full name, resolved server-side. |
| `rating` | int | 1 to 5 stars. |
| `comment_en` / `comment_de` / `comment_fr` | string or null | Stored localized review comments. |
| `status` | `ReviewStatus` | Current moderation status. |
| `created_at` / `updated_at` | ISO datetime | Review timestamps. |

---

## POST `/api/v1/admin/reviews/{review_id}/approve` - Approve a review

Approves a review's written comment and recomputes the braider's cached average rating/rating count. No request body.

### Path params

| Param | Type |
|---|---|
| `review_id` | UUID |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "9d871401-2305-4be0-a7b1-1360fb0f4f4f",
    "braider_id": "4b220c8e-b5d1-4f33-9dbf-4784144ce007",
    "braider_name": "Amina Bello",
    "customer_id": "a5088658-6efb-4aa5-bcde-f4dd6efcd124",
    "customer_name": "Nyla Okafor",
    "rating": 5,
    "comment_en": "Beautiful work and very professional.",
    "comment_de": "Schoene Arbeit und sehr professionell.",
    "comment_fr": "Tres beau travail et tres professionnel.",
    "status": "APPROVED",
    "created_at": "2026-08-12T09:30:00Z",
    "updated_at": "2026-08-12T10:05:00Z"
  },
  "error": null
}
```

### Errors

| Code | Status | When |
|---|---|---|
| `REVIEW_NOT_FOUND` | 404 | `review_id` does not exist |
| `VALIDATION_ERROR` | 422 | malformed UUID |

---

## POST `/api/v1/admin/reviews/{review_id}/reject` - Reject a review

Rejects a review. A rejected review's rating is excluded from the braider's average until the review is approved again. No request body.

### Path params

| Param | Type |
|---|---|
| `review_id` | UUID |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "9d871401-2305-4be0-a7b1-1360fb0f4f4f",
    "braider_id": "4b220c8e-b5d1-4f33-9dbf-4784144ce007",
    "braider_name": "Amina Bello",
    "customer_id": "a5088658-6efb-4aa5-bcde-f4dd6efcd124",
    "customer_name": "Nyla Okafor",
    "rating": 5,
    "comment_en": "Beautiful work and very professional.",
    "comment_de": "Schoene Arbeit und sehr professionell.",
    "comment_fr": "Tres beau travail et tres professionnel.",
    "status": "REJECTED",
    "created_at": "2026-08-12T09:30:00Z",
    "updated_at": "2026-08-12T10:10:00Z"
  },
  "error": null
}
```

### Errors

| Code | Status | When |
|---|---|---|
| `REVIEW_NOT_FOUND` | 404 | `review_id` does not exist |
| `VALIDATION_ERROR` | 422 | malformed UUID |

---

## Common error codes

| Code | HTTP status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `FORBIDDEN` | 403 | caller is not an `ADMIN` |
| `REVIEW_NOT_FOUND` | 404 | `review_id` does not exist |
| `VALIDATION_ERROR` | 422 | malformed query params/path params |
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
