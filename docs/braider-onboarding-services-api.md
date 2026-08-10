# Braider Onboarding — Services API

Base URL prefix: `/api/v1/braiders/onboarding/services`

This is the **`SERVICE_TYPE`** step of the braider onboarding flow (4th of 8 — see [Onboarding flow](#onboarding-flow) below). It lets a braider build their "service menu": pick styles from the platform catalog and set their own price/duration, plus optional per-style variations and add-ons with their own prices.

## Auth

All endpoints require a Bearer JWT for a user with role `BRAIDER`.

```
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token → `401 INVALID_ACCESS_TOKEN`
- Wrong role → `403 FORBIDDEN`

`POST` auto-creates the braider's profile if one doesn't exist yet — this can legitimately be the *first* onboarding action a braider takes. **Step ordering is not enforced** — a braider can call these endpoints before finishing earlier onboarding steps.

---

## Endpoints

| Method | Path | Purpose | Success status |
|---|---|---|---|
| GET | `/api/v1/braiders/onboarding/services` | List your service menu (paginated) | 200 |
| GET | `/api/v1/braiders/onboarding/services/{braider_style_id}` | Get one menu entry | 200 |
| POST | `/api/v1/braiders/onboarding/services` | Add a style to your menu | 201 |
| PUT | `/api/v1/braiders/onboarding/services/{braider_style_id}` | Edit a menu entry | 200 |
| DELETE | `/api/v1/braiders/onboarding/services/{braider_style_id}` | Remove a style from your menu | 204 |

`braider_style_id` is the **row id** of the braider's menu entry — not the catalog `style_id`. It's returned as `id` in the response body of GET/POST/PUT.

### Prerequisite: public style catalog (for picker UI)

These are separate, public/read-only endpoints used to source `style_id`, `style_variation_id`, and `addon_id` for the requests below (no auth role restriction beyond being logged in isn't even required — they're public catalog reads):

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/style-categories` | list of categories |
| GET | `/api/v1/styles` | paginated; filters `category_id`, `search`; only returns active styles |
| GET | `/api/v1/styles/{style_id}` | single style |
| GET | `/api/v1/addons` | list of active add-ons |

---

## GET `/api/v1/braiders/onboarding/services` — List your service menu

### Query params

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` | int | 1 | min 1 |
| `page_size` | int | 20 | min 1, max 100 |

If the braider has no profile yet, returns an empty page rather than an error.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "items": [ /* array of BraiderStyleResponse, see below */ ],
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

---

## GET `/api/v1/braiders/onboarding/services/{braider_style_id}` — Get one menu entry

### Path params

| Param | Type |
|---|---|
| `braider_style_id` | UUID |

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": { /* BraiderStyleResponse, see below */ },
  "error": null
}
```

### Error `404`
`BRAIDER_STYLE_NOT_FOUND` — profile missing, row missing, or row belongs to a different braider.

---

## POST `/api/v1/braiders/onboarding/services` — Add a style to your menu

### Request body

```json
{
  "style_id": "6e3f0a0c-bb9f-4715-ae93-da95b0e9b9ce",
  "base_price": "180.00",
  "duration_minutes": 240,
  "variations": [
    { "style_variation_id": "1eeef850-0d5d-46b6-9e7f-057f724ab925", "price": "200.00" }
  ],
  "addons": [
    { "addon_id": "cc35d230-d447-4522-aec7-db69d34a855a", "price": "20.00", "is_required": false }
  ]
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `style_id` | UUID | yes | must exist and be active |
| `base_price` | decimal string/number | yes | `> 0` |
| `duration_minutes` | int | no | `> 0` if given (see note below — becomes required later) |
| `variations` | array | no | default `[]`; each item: `style_variation_id` (UUID, must belong to `style_id` and be active) + `price` (`> 0`) |
| `addons` | array | no | default `[]`; each item: `addon_id` (UUID, must be active) + `price` (`>= 0`, zero allowed for free/bundled add-ons) + `is_required` (bool, default `false`) |

`duration_minutes` is optional at creation but effectively becomes required later: attempting to compute availability slots or a booking for a style with no `duration_minutes` fails with `422 BRAIDER_STYLE_DURATION_MISSING`.

### Response `201`

Same shape as the GET-single response — a `BraiderStyleResponse`:

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "8d416c5e-57ed-4597-a587-326807a96277",
    "style_id": "6e3f0a0c-bb9f-4715-ae93-da95b0e9b9ce",
    "style_slug": "knotless-braids-mid-back",
    "style_name_en": "Knotless Braids - Mid Back",
    "style_name_de": "Knotless Braids - Mittellang",
    "style_name_fr": "Tresses Knotless - Mi-Dos",
    "primary_image_url": null,
    "base_price": "180.00",
    "duration_minutes": 240,
    "is_active": true,
    "variations": [
      {
        "id": "86538614-9cd8-4715-9ec1-6c36c8d93937",
        "style_variation_id": "1eeef850-0d5d-46b6-9e7f-057f724ab925",
        "name_en": "Mid-back length",
        "name_de": "Rückenlang (Mitte)",
        "name_fr": "Longueur Mi-Dos",
        "price": "200.00"
      }
    ],
    "addons": [
      {
        "id": "be5f5561-76e0-4339-bb18-7c75e1d441fb",
        "addon_id": "cc35d230-d447-4522-aec7-db69d34a855a",
        "name_en": "Beads",
        "name_de": "Perlen",
        "name_fr": "Perles",
        "price": "20.00",
        "is_required": false
      }
    ]
  },
  "error": null
}
```

Side effect: marks the `SERVICE_TYPE` onboarding step complete (one-way — never un-marked, even if the braider later deletes all their styles).

### Errors

| Code | Status | When |
|---|---|---|
| `STYLE_NOT_FOUND` | 404 | `style_id` doesn't exist |
| `STYLE_NOT_ACTIVE` | 400 | `style_id` exists but is inactive/unpublished |
| `BRAIDER_STYLE_ALREADY_EXISTS` | 409 | braider already has this `style_id` on their menu |
| `INVALID_STYLE_VARIATION` | 400 | a `style_variation_id` doesn't exist, doesn't belong to `style_id`, or is inactive |
| `INVALID_ADDON` | 400 | an `addon_id` doesn't exist or is inactive |
| `VALIDATION_ERROR` | 422 | malformed body / constraint violations (e.g. `base_price <= 0`) |

---

## PUT `/api/v1/braiders/onboarding/services/{braider_style_id}` — Edit a menu entry

### Path params

| Param | Type |
|---|---|
| `braider_style_id` | UUID — must belong to the calling braider |

### Request body

All fields optional — **partial update semantics**:

```json
{
  "base_price": "190.00",
  "duration_minutes": 210,
  "is_active": true,
  "variations": [
    { "style_variation_id": "1eeef850-0d5d-46b6-9e7f-057f724ab925", "price": "210.00" }
  ],
  "addons": []
}
```

| Field | Type | Notes |
|---|---|---|
| `base_price` | decimal | `> 0` if sent; omit/`null` to leave unchanged |
| `duration_minutes` | int | `> 0` if sent; omit/`null` to leave unchanged |
| `is_active` | bool | omit/`null` to leave unchanged |
| `variations` | array \| null | **full replacement** if present (including `[]`, which clears all); `null`/omitted = don't touch existing variations |
| `addons` | array \| null | same full-replacement semantics as `variations` |

Important: `variations`/`addons` are not merged — sending any array (even empty) deletes all existing rows for that list and inserts the new ones. Same per-item validation as POST applies (variation must belong to the style and be active; addon must be active).

### Response `200`

Same `BraiderStyleResponse` shape as POST/GET.

### Errors

| Code | Status | When |
|---|---|---|
| `BRAIDER_STYLE_NOT_FOUND` | 404 | row missing or belongs to another braider |
| `INVALID_STYLE_VARIATION` | 400 | as above |
| `INVALID_ADDON` | 400 | as above |
| `VALIDATION_ERROR` | 422 | malformed body |

Note: editing does not affect onboarding-step completion (already set on first create).

---

## DELETE `/api/v1/braiders/onboarding/services/{braider_style_id}` — Remove a style from your menu

### Path params

| Param | Type |
|---|---|
| `braider_style_id` | UUID — must belong to the calling braider |

### Response `204`

No body.

### Errors

| Code | Status | When |
|---|---|---|
| `BRAIDER_STYLE_NOT_FOUND` | 404 | row missing or belongs to another braider |

Variations and add-ons for the deleted entry cascade-delete automatically. There is no cap on how many styles a braider can add or remove.

---

## Response schema reference

### `BraiderStyleResponse`

```ts
{
  id: uuid;                    // braider_styles.id (the menu-entry id, use as braider_style_id in other calls)
  style_id: uuid;
  style_slug: string;
  style_name_en: string;
  style_name_de: string | null;
  style_name_fr: string | null;
  primary_image_url: string | null;
  base_price: decimal;
  duration_minutes: number | null;
  is_active: boolean;
  variations: BraiderStyleVariationResponse[];
  addons: BraiderStyleAddonResponse[];
}
```

### `BraiderStyleVariationResponse`

```ts
{
  id: uuid;                    // braider_style_variations.id (row id, distinct from style_variation_id)
  style_variation_id: uuid;
  name_en: string;
  name_de: string | null;
  name_fr: string | null;
  price: decimal;
}
```

### `BraiderStyleAddonResponse`

```ts
{
  id: uuid;                    // braider_style_addons.id
  addon_id: uuid;
  name_en: string;
  name_de: string | null;
  name_fr: string | null;
  price: decimal;
  is_required: boolean;
}
```

---

## Onboarding flow

Onboarding steps, in canonical order (`OnboardingStep` enum):

```
BUSINESS_INFO → PHONE_VERIFICATION → VERIFF → SERVICE_TYPE → PORTFOLIO
→ SERVICE_LOCATION → AVAILABILITY → PAYMENT_SETUP → COMPLETED
```

This feature is step **`SERVICE_TYPE`** (4th of 8). Steps can be completed in any order — there is no hard gate preventing a braider from calling these endpoints before finishing earlier steps. `SERVICE_TYPE` completion is **one-way**: once the first style is successfully added, the step stays complete even if all styles are later removed.

### GET `/api/v1/braiders/onboarding/status` — overall onboarding progress

Auth: BRAIDER only.

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "current_step": "SERVICE_TYPE",
    "business_info_completed_at": "2026-08-01T10:00:00Z",
    "phone_verification_completed_at": "2026-08-01T10:05:00Z",
    "veriff_completed_at": "2026-08-01T10:10:00Z",
    "service_type_completed_at": null,
    "portfolio_completed_at": null,
    "service_location_completed_at": null,
    "availability_completed_at": null,
    "payment_setup_completed_at": null,
    "completed_at": null
  },
  "error": null
}
```

`current_step` is a derived UI hint — "first step, in canonical order, not yet complete" — not an enforcement mechanism. `completed_at` is set automatically once every step's `*_completed_at` is non-null. There is no explicit "finish onboarding" endpoint.

---

## Common error codes

| Code | HTTP status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `FORBIDDEN` | 403 | caller isn't a `BRAIDER` |
| `STYLE_NOT_FOUND` | 404 | `style_id` doesn't exist |
| `STYLE_NOT_ACTIVE` | 400 | `style_id` exists but inactive |
| `BRAIDER_STYLE_NOT_FOUND` | 404 | menu entry doesn't exist / not owned by caller |
| `BRAIDER_STYLE_ALREADY_EXISTS` | 409 | duplicate `style_id` on the same braider's menu |
| `INVALID_STYLE_VARIATION` | 400 | bad/inactive/mismatched `style_variation_id` |
| `INVALID_ADDON` | 400 | bad/inactive `addon_id` |
| `BRAIDER_STYLE_DURATION_MISSING` | 422 | (downstream, not from these endpoints directly) a style with no `duration_minutes` is needed for availability/booking calculation |
| `VALIDATION_ERROR` | 422 | malformed request body/params; response includes a `details` array |
| `INTERNAL_SERVER_ERROR` | 500 | unhandled server error |

All error responses share this envelope:

```json
{
  "status": "error",
  "status_label": "string",
  "data": null,
  "error": { "code": "string", "message": "string" }
}
```
