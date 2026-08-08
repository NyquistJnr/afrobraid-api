# AI Hairstyle Try-On — API Contract

> **STATUS: LIVE.** Everything in this document is implemented and merged on `staging`. Brand-new module (`app/modules/tryon/`). Depends on the existing style catalog (`app/modules/styles/`) for the "pick a style" part of the flow — those endpoints are documented in §1 for convenience since you'll need them here, but they aren't new.

---

## 0. Conventions (apply to every endpoint below)

**Response envelope.** Every response — success or error — is wrapped the same way:

```jsonc
// success
{ "status": "success", "status_label": "Success", "data": { /* ... */ }, "error": null }

// error
{ "status": "error", "status_label": "Error", "data": null, "error": { "code": "SOME_CODE", "message": "Human-readable, already localized." } }
```

Read the payload from `data`. On a non-2xx response, branch on `error.code` (stable, machine-checkable), not `error.message` (localized prose, display-only).

**Auth.** `Authorization: Bearer <access_token>` header, same JWT as the rest of the app. **Any logged-in account works** — customer, braider, or admin. There is no role restriction on this feature (unlike most of the app, nothing here is customer-only).

**Locale.** `?lang=en|de|fr` query param, falling back to `Accept-Language`, falling back to `en`. Affects style/variation names in responses and the `error_message` shown on a `FAILED` try-on.

---

## 1. Prerequisite — browsing styles to pick from

Not part of this feature's build, but you'll call these first to populate a "choose a style" UI. Full detail in the styles module; the shape you need:

### `GET /api/v1/style-categories` — Public

`APIResponse<StyleCategoryPublicResponse[]>`

```jsonc
[{ "id": "c1...", "slug": "braids", "name": "Braids", "display_order": 0 }]
```

### `GET /api/v1/styles?category_id=&search=&page=&page_size=` — Public

`APIResponse<PaginatedData<StylePublicResponse>>` — see the ratings/discovery API doc for the `pagination` block shape.

```jsonc
{
  "items": [
    {
      "id": "9f1c....",
      "slug": "knotless-braids",
      "category_id": "c1...",
      "name": "Knotless Braids",
      "description": "Lightweight, no tension on the scalp...",
      "is_active": true,
      "images": [{ "id": "img1", "url": "https://cdn.../style.jpg", "position": 0 }],
      "variations": [{ "id": "v1...", "name": "Mid-back length", "display_order": 0, "is_active": true }]
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total_items": 40, "total_pages": 2, "has_next": true, "has_previous": false }
}
```

### `GET /api/v1/styles/{style_id}` — Public

Same `StylePublicResponse` shape as one item above.

`style.id` and `variation.id` from these responses are what you pass as `style_id` / `style_variation_id` in §3.2 below.

---

## 2. The flow, in plain terms

This is a **client-direct-upload + background-generation** flow, not a single request-response. Nothing here is instant — generation genuinely takes time (roughly 10–40 seconds in practice, occasionally longer if the model provider is cold).

```
1. POST /api/v1/tryon/upload-url   { content_type }
        │  returns a presigned URL, valid 5 minutes
        ▼
2. PUT <upload_url>                (raw photo bytes; Content-Type header MUST
        │                           exactly match what you sent in step 1)
        ▼
3. POST /api/v1/tryon              { object_key, style_id and/or description }
        │  returns immediately — status: "PROCESSING"
        ▼
4. poll GET /api/v1/tryon/{id} every ~3-5s
        │
        ├──► status: "COMPLETED" → result_url is set → show the image
        └──► status: "FAILED"    → error_message is set → offer "try again" (back to step 1)
```

Key things this implies for the frontend:

- **The API never receives the photo through a normal request body** — you PUT it straight to object storage using the URL from step 1. This keeps large image uploads off the API server entirely.
- **The original uploaded photo is deleted automatically** once generation finishes (success or failure) — there's nothing to clean up client-side, and don't expect to be able to re-fetch the original later.
- **Style, description, or both.** At least one of `style_id` / `description` is required in step 3. Sending both combines them — e.g. picking "Knotless Braids" *and* typing "shoulder length, honey blonde" produces a prompt combining both. Pure free-text (no style picked) also works fine.
- **A user can have at most 3 try-ons `PROCESSING` at once** (server-enforced, see errors below) — surface this as a friendly "wait for one to finish" message, not a generic error.

---

## 3. Endpoints

### 3.1 Get an upload URL — `POST /api/v1/tryon/upload-url`

Step 1 of the flow. Any logged-in user.

#### Request body

```jsonc
{ "content_type": "image/jpeg" }   // "image/jpeg" | "image/png" | "image/webp"
```

#### Response `200`

`APIResponse<TryOnUploadUrlResponse>`

```jsonc
{
  "upload_url": "https://<r2-bucket>.r2.cloudflarestorage.com/tryon/....?X-Amz-...",
  "object_key": "tryon/5a4efcc1-.../original/df7fe10a-....webp",
  "expires_in": 300
}
```

| Field | Notes |
|---|---|
| `upload_url` | Presigned PUT URL. Expires in `expires_in` seconds (300) — request a fresh one if the user takes too long picking a photo. |
| `object_key` | Opaque string. Save it — you pass it back verbatim in §3.2. Don't try to parse or construct it yourself. |

#### Step 2 (not an API call — direct-to-storage)

```
PUT <upload_url>
Content-Type: image/jpeg      ← MUST exactly match the content_type sent above
Body: <raw image bytes>
```

If the `Content-Type` header on this PUT doesn't match what was requested in step 1, R2 rejects the upload with a signature error (not one of this API's error codes — it's a raw S3-style XML error from storage itself). This is the #1 integration gotcha with presigned uploads — double check it.

#### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `VALIDATION_ERROR` | 422 | `content_type` missing or not one of the three allowed values |

---

### 3.2 Start generating a try-on — `POST /api/v1/tryon`

Step 3 of the flow. Any logged-in user.

#### Request body

```jsonc
{
  "object_key": "tryon/5a4efcc1-.../original/df7fe10a-....webp",   // required, from §3.1
  "style_id": "9f1c....",             // optional, from §1
  "style_variation_id": "v1...",      // optional, must belong to style_id if sent
  "description": "shoulder length, honey blonde highlights"  // optional, max 500 chars
}
```

At least one of `style_id` / `description` is required. All three of `style_id`, `style_variation_id`, `description` can be combined.

#### Response `202`

`APIResponse<TryOnResponse>` — see §5 for the full field reference. On creation, `status` is always `PROCESSING` and `result_url`/`error_message` are always `null`.

```jsonc
{
  "id": "8b71ba86-....",
  "status": "PROCESSING",
  "style": { "id": "9f1c....", "slug": "knotless-braids", "name": "Knotless Braids" },
  "style_variation": null,
  "description": "shoulder length, honey blonde highlights",
  "result_url": null,
  "error_message": null,
  "created_at": "2026-08-08T17:53:45.297430Z"
}
```

#### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `TRYON_STYLE_OR_DESCRIPTION_REQUIRED` | 400 | Neither `style_id` nor `description` sent |
| `INVALID_TRYON_IMAGE_UPLOAD` | 400 | `object_key` wasn't from your own §3.1 call, nothing was actually uploaded to it, or the uploaded file is the wrong type / over 10MB |
| `STYLE_NOT_FOUND` | 404 | `style_id` doesn't exist |
| `STYLE_NOT_ACTIVE` | 400 | `style_id` exists but isn't published |
| `TRYON_STYLE_VARIATION_INVALID` | 400 | `style_variation_id` doesn't belong to `style_id` (or was sent without a `style_id`) |
| `MAX_PENDING_TRYONS_REACHED` | 400 | Caller already has 3 try-ons `PROCESSING` |
| `VALIDATION_ERROR` | 422 | `description` over 500 chars, malformed UUIDs, etc. |

---

### 3.3 Poll a try-on — `GET /api/v1/tryon/{id}`

Step 4 of the flow. Any logged-in user — scoped to their own try-ons (someone else's `id` 404s, same as "doesn't exist").

#### Response `200`

Same `TryOnResponse` shape as §3.2. Poll roughly every 3–5 seconds until `status` is no longer `PROCESSING`. On `COMPLETED`, `result_url` is a permanent public image URL. On `FAILED`, `error_message` is a localized, user-safe string (raw error detail is server-side only) — the sensible UX is to let the user retry from step 1 with the same or a new photo.

There's no push/webhook for completion today — polling is the only option.

#### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `TRYON_NOT_FOUND` | 404 | Doesn't exist, or belongs to a different user |

---

### 3.4 List your try-on history — `GET /api/v1/tryon`

Any logged-in user. No pagination (this list is expected to stay small) — every try-on the user has ever created, newest first.

#### Response `200`

`APIResponse<TryOnResponse[]>`

---

### 3.5 Delete a try-on — `DELETE /api/v1/tryon/{id}`

Any logged-in user — scoped to their own. Removes the record and any stored image (original and/or result, whichever still exist).

#### Response `204`

No body.

#### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `TRYON_NOT_FOUND` | 404 | Doesn't exist, or belongs to a different user |

---

## 4. Suggested frontend flow

1. Let the user pick a photo (camera or gallery). Call `POST /tryon/upload-url` with that file's mime type, then `PUT` the raw bytes to `upload_url` (§3.1). Show an upload-progress state — this part is typically fast (seconds).
2. Let the user pick a style from §1's catalog, type a free-text description, or both. Enforce "at least one" client-side to avoid a round trip for `TRYON_STYLE_OR_DESCRIPTION_REQUIRED`.
3. Call `POST /tryon` (§3.2). On success, immediately show a "generating your look..." state — don't block on a spinner expecting a fast response, this is a multi-second-to-tens-of-seconds background job.
4. Poll `GET /tryon/{id}` (§3.3) every 3–5 seconds. Recommended: stop showing an indefinite spinner after ~90 seconds and instead show "this is taking longer than usual, we'll keep trying" (keep polling in the background, or let the user navigate away and check `GET /tryon` — §3.4 — later) rather than appearing frozen.
5. On `COMPLETED`, show `result_url`. On `FAILED`, show `error_message` with a retry action that restarts from step 1 (the failed original photo is already gone server-side, so a fresh upload is required — don't try to resubmit the same `object_key`).
6. `GET /tryon` (§3.4) is what powers a "your try-ons" history/gallery screen — useful for letting users revisit or delete past results (§3.5) without re-generating.

---

## 5. Reference — `TryOnResponse` fields & enums

```jsonc
{
  "id": "uuid",
  "status": "PROCESSING",              // see enum below
  "style": { "id": "uuid", "slug": "string", "name": "string" } | null,
  "style_variation": { "id": "uuid", "name": "string" } | null,
  "description": "string" | null,
  "result_url": "https://..." | null,   // only non-null when status == COMPLETED
  "error_message": "string" | null,     // only non-null when status == FAILED, already localized
  "created_at": "2026-08-08T17:53:45.297430Z"
}
```

| Enum | Values |
|---|---|
| `TryOnStatus` (`status`) | `PROCESSING`, `COMPLETED`, `FAILED` |
| Accepted upload `content_type` | `image/jpeg`, `image/png`, `image/webp` |

| Limit | Value |
|---|---|
| Max upload size | 10MB |
| Max `description` length | 500 characters |
| Max concurrent `PROCESSING` try-ons per user | 3 |
| Upload URL validity | 300 seconds |

---

## 6. Not in scope for the customer app (mentioned for completeness only)

There's no admin/moderation surface for this feature — every try-on is private to the user who created it, nothing is reviewed or made public. Nothing here to build for an admin dashboard.
