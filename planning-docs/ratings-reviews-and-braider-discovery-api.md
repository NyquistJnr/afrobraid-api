# Ratings & Reviews + Braider Search/Detail — API Contract

> **STATUS: LIVE.** Everything in this document is implemented and merged on `staging`. Ratings/reviews are a brand-new module (`app/modules/reviews/`); the braider search and detail endpoints are existing endpoints that got one new field (`rating`) added to their response.

---

## 0. Conventions (apply to every endpoint below)

**Response envelope.** Every response — success or error — is wrapped the same way:

```jsonc
// success
{ "status": "success", "status_label": "Success", "data": { /* ... */ }, "error": null }

// error
{ "status": "error", "status_label": "Error", "data": null, "error": { "code": "SOME_CODE", "message": "Human-readable, already localized." } }
```

The frontend should read the payload from `data`, and on a non-2xx response, branch on `error.code` (stable, machine-checkable) rather than parsing `error.message` (localized prose, for display only).

**Auth.** `Authorization: Bearer <access_token>` header, same JWT as the rest of the app. Endpoints marked **Public** need no auth at all. Endpoints marked **Customer** 403 with `FORBIDDEN` if the token belongs to a BRAIDER/ADMIN account.

**Locale.** Every endpoint that returns translatable text (style names, bio, portfolio captions, review comments) picks a locale the same way: `?lang=en|de|fr` query param, falling back to the `Accept-Language` header, falling back to `en`. There's nothing extra to do here beyond what the frontend already does for the rest of the API — same mechanism, same three locales.

**Pagination.** Every list endpoint below takes the same two query params and returns the same shape:

| Param | Default | Notes |
|---|---|---|
| `page` | `1` | 1-indexed |
| `page_size` | `20` | max `100` |

```jsonc
{
  "items": [ /* ... */ ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 47,
    "total_pages": 3,
    "has_next": true,
    "has_previous": false
  }
}
```

---

## 1. Braider Search — `GET /api/v1/braiders`

**Public.** Only returns braiders who've completed onboarding (payment setup included).

### Query params

| Param | Type | Notes |
|---|---|---|
| `lat`, `lng` | float | Give both together or neither. `lat` ∈ [-90, 90], `lng` ∈ [-180, 180]. |
| `radius_km` | float | Only meaningful with `lat`/`lng`. Defaults to `100` if `lat`/`lng` given but this isn't. |
| `style_id` | UUID | Filters + adds `matched_style` to each result. |
| `style_slug` | string | Same as `style_id` but by slug. If both given, `style_id` wins. |
| `search` | string | Matches braider business name. |
| `date_from`, `date_to` | date (`YYYY-MM-DD`) | Give both together or neither. Max 90 days apart. Filters to braiders with at least one structurally-open day in range (not a slot-level check). |
| `min_amount`, `max_amount` | decimal | Matches braiders with at least one offered style priced in range. |
| `country_code` | string(2) | ISO 3166-1 alpha-2, e.g. `DE`. |
| `is_mobile` | bool | Braider offers a mobile service. |
| `page`, `page_size` | int | See §0. |

### Response `200`

`APIResponse<PaginatedData<BraiderSearchItem>>`

```jsonc
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "5e2a1b3c-....",
        "business_name": "Ada's Braids",
        "logo_url": "https://cdn.example.com/braiders/.../logo.jpg",
        "location": {
          "location_type": "SALON",              // "SALON" | "HOME_STUDIO" | null
          "salon_name": "The Studio",             // null unless location_type == SALON
          "address_line1": "123 Main St",         // null unless location_type == SALON
          "address_line2": null,
          "postal_code": "10115",
          "city": "Berlin",
          "country": "DE",
          "latitude": "52.520008",                // fuzzed ±400m for HOME_STUDIO/mobile-only, exact for SALON
          "longitude": "13.404954",
          "offers_mobile": false,
          "travel_radius_km": null,
          "travel_fee": null
        },
        "distance_km": 4.32,                      // null unless lat/lng were passed
        "cover_photo_url": "https://cdn.example.com/braiders/.../portfolio/1.jpg",
        "matched_style": {                        // null unless style_id/style_slug was passed
          "style_id": "9f1c....",
          "name": "Knotless Braids",
          "base_price": "180.00",
          "duration_minutes": 240
        },
        "styles": [                               // full menu, capped at 5, independent of matched_style
          { "style_id": "9f1c....", "name": "Knotless Braids", "base_price": "180.00", "duration_minutes": 240 }
        ],
        "rating": "4.75"                          // NEW — see §3 for what this means. null if no ratings yet.
      }
    ],
    "pagination": { "page": 1, "page_size": 20, "total_items": 1, "total_pages": 1, "has_next": false, "has_previous": false }
  },
  "error": null
}
```

### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `INVALID_SEARCH_LOCATION` | 400 | Only one of `lat`/`lng` given |
| `INVALID_SEARCH_DATE_RANGE` | 400 | Only one of `date_from`/`date_to` given, range inverted, or >90 days |
| `INVALID_SEARCH_PRICE_RANGE` | 400 | `max_amount` < `min_amount` |
| `VALIDATION_ERROR` | 422 | Malformed query param (e.g. `lat` out of range) |

---

## 2. Braider Detail — `GET /api/v1/braiders/{braider_id}`

**Public.** 404s if the braider hasn't finished onboarding.

### Response `200`

`APIResponse<BraiderDetail>`

```jsonc
{
  "status": "success",
  "data": {
    "id": "5e2a1b3c-....",
    "business_name": "Ada's Braids",
    "logo_url": "https://cdn.example.com/braiders/.../logo.jpg",
    "bio": "10 years experience with protective styles...",   // localized per §0
    "gender": "FEMALE",                            // "MALE" | "FEMALE" | "OTHER" | "PREFER_NOT_TO_SAY" | null
    "location": { /* same shape as §1 */ },
    "portfolio": [
      { "id": "a1b2....", "url": "https://cdn.example.com/....jpg", "caption": "Waist-length knotless", "position": 0 }
    ],
    "styles": [
      {
        "style_id": "9f1c....",
        "slug": "knotless-braids",
        "name": "Knotless Braids",
        "base_price": "180.00",
        "duration_minutes": 240,
        "variations": [ { "id": "....", "name": "Mid-back length", "price": "200.00" } ],
        "addons": [ { "id": "....", "name": "Beads", "price": "20.00", "is_required": false } ]
      }
    ],
    "rating": "4.75"                                // NEW — same field/meaning as §1
  },
  "error": null
}
```

### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `BRAIDER_NOT_FOUND` | 404 | Doesn't exist, or hasn't finished onboarding |

---

## 3. Ratings & Reviews

### 3.1 The model, in plain terms

- A customer can rate + optionally review a braider **once they've had a booking with that braider that reached a successful payment.** Trying before that gets `REVIEW_NOT_ELIGIBLE`.
- One review per (customer, braider) pair, ever. There's no "create" vs "edit" distinction in the API — you always call the same `PUT .../reviews/me`, and it creates the first time, updates every time after.
- **The star rating is live immediately.** The moment a customer submits/updates a rating, it's folded into the braider's average — the `rating` field you already see in §1/§2 — with no moderation delay.
- **The written comment needs admin approval before it's public.** Submitting a comment (or editing an existing one) sets it to `PENDING`; it only appears in the public reviews list (§3.2) once an admin approves it. A review with no comment at all has nothing to moderate, so it's auto-`APPROVED`.
- Editing an **already-approved** comment resets it to `PENDING` — re-approval is required again. (The rating itself is unaffected by this — it's always live regardless of comment status.)
- If an admin **rejects** a review outright (e.g. spam/abuse), that review's rating is also excluded from the braider's average until/unless it's approved again.
- Comments auto-translate into the platform's other locales (same DeepL pipeline used for braider bios and portfolio captions) — the customer only ever writes one language, the other two show up shortly after, machine-translated.

```
submit rating+comment ──► rating counts immediately, comment = PENDING
                              │
                              ├──► admin approves ──► comment now public, review.status = APPROVED
                              │
                              └──► admin rejects ───► review.status = REJECTED, rating excluded from average

submit rating only ──► review.status = APPROVED immediately (nothing to moderate)

edit an approved comment ──► back to PENDING, needs re-approval
edit just the rating ──► average updates immediately, comment/status untouched
```

### 3.2 List a braider's public reviews — `GET /api/v1/braiders/{braider_id}/reviews`

**Public.** Only returns reviews whose comment is `APPROVED` (this includes rating-only reviews, which are auto-approved). A rating that's still `PENDING` moderation is *not* omitted from the braider's average shown in §1/§2 — it's just not in this list yet.

Query params: `page`, `page_size` (see §0).

### Response `200`

`APIResponse<PaginatedData<PublicReview>>`

```jsonc
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "c4d5....",
        "customer_name": "Amara O.",              // full name is "first last" server-side; truncate/format client-side if you want initials-only
        "rating": 5,
        "comment": "Loved it, will book again!",  // localized per §0. null if the customer left no comment.
        "created_at": "2026-08-01T10:00:00Z",
        "updated_at": "2026-08-03T09:15:00Z"       // != created_at if the customer edited it after it was approved
      }
    ],
    "pagination": { "page": 1, "page_size": 20, "total_items": 12, "total_pages": 1, "has_next": false, "has_previous": false }
  },
  "error": null
}
```

Note: `customer_name` today is the raw `"{first_name} {last_name}"` with no masking. Flag to backend now if the product wants first-name-only / initials for privacy — this is a one-line change but needs a product decision, not a frontend workaround.

### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `BRAIDER_NOT_FOUND` | 404 | Braider doesn't exist |

---

### 3.3 Get your own review for a braider — `GET /api/v1/braiders/{braider_id}/reviews/me`

**Customer.** Use this to check "have I already reviewed this braider" / prefill an edit form. 404s (not an empty object) if you haven't reviewed them yet — treat that 404 as "show the 'leave a review' form empty," not as an error state.

### Response `200`

`APIResponse<Review>`

```jsonc
{
  "status": "success",
  "data": {
    "id": "c4d5....",
    "braider_id": "5e2a1b3c-....",
    "rating": 5,
    "comment_en": "Loved it, will book again!",
    "comment_de": "Toll, komme wieder!",           // MACHINE-translated if the customer wrote in English
    "comment_fr": "Génial, je reviendrai !",
    "comment_en_source": "HUMAN",                  // "HUMAN" | "MACHINE" | "PENDING" | "FAILED" | null, per-locale
    "comment_de_source": "MACHINE",
    "comment_fr_source": "MACHINE",
    "status": "APPROVED",                           // "PENDING" | "APPROVED" | "REJECTED"
    "created_at": "2026-08-01T10:00:00Z",
    "updated_at": "2026-08-03T09:15:00Z"
  },
  "error": null
}
```

This is the *only* endpoint that returns all three locales + their translation status at once (the public list in §3.2 only returns the one localized `comment` string) — useful if you want to show "translation in progress" state on the customer's own "my reviews" screen. `*_source: "PENDING"` means the translation job hasn't run yet (near-instant in practice); `"FAILED"` means DeepL errored and that locale's text is simply blank until the customer edits again.

### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `REVIEW_NOT_FOUND` | 404 | You haven't reviewed this braider yet |

---

### 3.4 Rate & review a braider — `PUT /api/v1/braiders/{braider_id}/reviews/me`

**Customer.** Creates your review the first time, updates it every time after — always the same endpoint, always full-replace semantics (see request fields below for exactly what "full-replace" means for `comment`).

### Request body

```jsonc
{
  "rating": 5,                              // required, integer 1-5
  "comment": "Loved it, will book again!"   // optional
}
```

| Field | Rules |
|---|---|
| `rating` | Required. Integer, `1` ≤ x ≤ `5`. |
| `comment` | Optional. Written in whichever locale the request is in (see §0) — that locale becomes `HUMAN`-sourced, the other two get queued for machine translation. Max 1000 chars, trimmed server-side. **Omit or send `null`/`""` to remove an existing comment** (the rating is kept) — there's no separate "clear comment" endpoint. |

Every call sends the full desired state — there's no partial-patch semantics for `comment`: if you send the *same* text as what's already saved for the current locale, nothing is re-triggered (no re-translation, no status reset). If you send *different* text, it's treated as an edit (see §3.1's PENDING-reset rule). If you send no `comment` field at all while one already exists, it's cleared.

### Response `200`

Same shape as §3.3's `Review` object.

### Errors

| `error.code` | HTTP | When |
|---|---|---|
| `REVIEW_NOT_ELIGIBLE` | 403 | No booking with this braider has reached a successful payment |
| `BRAIDER_NOT_FOUND` | 404 | Braider doesn't exist |
| `VALIDATION_ERROR` | 422 | `rating` missing/out of range, or `comment` over 1000 chars |

### Suggested frontend flow

1. After a booking's status makes it eligible (in practice: once it's past `PENDING_PAYMENT`), show a "Rate your braider" prompt — e.g. on the booking detail/history screen.
2. Call `GET .../reviews/me` first to know whether to render "leave a review" (404) or "edit your review" (200, prefill from it).
3. On submit, `PUT .../reviews/me`. The response's `rating` is authoritative — you can optimistically bump the braider's displayed average, but re-fetch `GET /api/v1/braiders/{id}` (§2) if you want the *exact* server-computed average rather than eyeballing it client-side.
4. If `status: "PENDING"` comes back, show something like "Your review is live! Your written comment is awaiting approval and will appear publicly soon." Don't hide the rating — it already counts.
5. Nothing to poll: there's no webhook/push for admin approval today. If you want the customer to see the moment their comment goes public, re-check `GET .../reviews/me` (cheap, low-traffic) when they revisit that screen, rather than polling continuously.

---

## 4. Reference — enums used above

| Enum | Values |
|---|---|
| `ReviewStatus` (`review.status`) | `PENDING`, `APPROVED`, `REJECTED` |
| Comment translation source (`comment_*_source`) | `HUMAN`, `MACHINE`, `PENDING`, `FAILED` |
| `Gender` | `MALE`, `FEMALE`, `OTHER`, `PREFER_NOT_TO_SAY` |
| `LocationType` | `HOME_STUDIO`, `SALON`, or `null` |

---

## 5. Not in scope for the customer app (mentioned for completeness only)

There's also an admin moderation surface — `GET /api/v1/admin/reviews`, `POST /api/v1/admin/reviews/{id}/approve`, `POST /api/v1/admin/reviews/{id}/reject` — but that's ADMIN-role-only and belongs to the internal moderation dashboard, not the customer-facing app. Ignore it unless you're also building that dashboard.
