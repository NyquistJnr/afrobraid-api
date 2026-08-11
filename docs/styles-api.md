# Styles catalog API (admin and public)

This is the integration contract for the central hairstyle catalog: categories, styles, style images, variations, and add-ons.

## Base conventions

All paths below are relative to the API host, for example `https://api.example.com`.

### Authentication

Every `/api/v1/admin/...` endpoint requires an access token for a user whose `user_type` is `ADMIN`:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

The public catalog endpoints do **not** require authentication. They can also be called with a customer or braider access token; it makes no difference to their response.

### Success envelope

Successful JSON responses use this envelope (except `204` deletions, which have no body):

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {},
  "error": null
}
```

### Error envelope

```json
{
  "status": "error",
  "status_label": "Error",
  "data": null,
  "error": {
    "code": "STYLE_NOT_FOUND",
    "message": "This style doesn't exist."
  }
}
```

Validation failures use HTTP `422` and `error.code: "VALIDATION_ERROR"`. They include FastAPI/Pydantic field details under `error.details`; the frontend should still validate inputs locally for a better experience:

```json
{
  "status": "error",
  "status_label": "Error",
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please check your input and try again.",
    "details": [
      { "loc": ["body", "name"], "msg": "Value error, Name cannot be blank.", "type": "value_error" }
    ]
  }
}
```

### Locale and translated fields

Supported display locales are `en`, `de`, and `fr`; English is the default. Public endpoints resolve the locale from the `lang` query string first, then the `Accept-Language` header, then English:

```http
GET /api/v1/styles?lang=de
Accept-Language: fr
```

The example above returns German values where available. Public responses return one resolved `name`/`description` value, with fallback from the requested language to English and then another available language. Admin responses always return all language variants plus their translation status.

Admin-entered catalog text is authored in English. A create or changed name/description queues machine translation to German and French. Immediately after submission those target fields can be `null` and their corresponding `*_source` value is `"PENDING"`.

Translation source values are `HUMAN`, `MACHINE`, `PENDING`, and `FAILED` (or `null` when no value/status exists).

### Pagination

Style-list endpoints accept:

| Parameter | Type | Default | Limits |
|---|---:|---:|---|
| `page` | integer | `1` | minimum `1` |
| `page_size` | integer | `20` | `1`–`100` |

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 0,
    "total_pages": 0,
    "has_next": false,
    "has_previous": false
  }
}
```

### Shared nested objects

`StyleImage`:

```json
{
  "id": "9bccc303-14f6-4683-9f60-07eccfda4b2c",
  "url": "https://cdn.example.com/styles/.../images/file.jpg",
  "position": 0
}
```

Image and variation arrays are sorted by `position` and `display_order`, respectively.

## Public styles API

Public base prefix: `/api/v1`

### GET `/api/v1/style-categories` — list categories

Returns every category, sorted ascending by `display_order`. Categories do not have an active/inactive state.

**Response `200`**

```json
{
  "status": "success",
  "status_label": "Success",
  "data": [
    {
      "id": "6c38a7bd-321a-4f55-a3f5-66b349032e83",
      "slug": "knotless-braids",
      "name": "Knotless Braids",
      "display_order": 1
    }
  ],
  "error": null
}
```

### GET `/api/v1/styles` — list published styles

Returns only styles where `is_active` is `true`; inactive variations are also filtered out of list results. Styles are ordered alphabetically by the English name.

| Parameter | Type | Required | Notes |
|---|---|---:|---|
| `category_id` | UUID | no | exact category filter |
| `search` | string | no | case-insensitive contains search against the **English** name |
| `page`, `page_size` | integer | no | pagination controls above |
| `lang` | `en`/`de`/`fr` | no | overrides `Accept-Language` |

**Response `200`**

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "items": [
      {
        "id": "86e11160-ee13-4a7d-884e-b4b0b89d8ec5",
        "slug": "knotless-braids-mid-back",
        "category_id": "6c38a7bd-321a-4f55-a3f5-66b349032e83",
        "name": "Knotless Braids — Mid Back",
        "description": "Classic knotless braids finished at mid-back length.",
        "is_active": true,
        "images": [
          {
            "id": "9bccc303-14f6-4683-9f60-07eccfda4b2c",
            "url": "https://cdn.example.com/styles/.../images/file.jpg",
            "position": 0
          }
        ],
        "variations": [
          {
            "id": "d1c9c6d1-625c-43b8-8333-6893714745fb",
            "name": "Mid-back length",
            "display_order": 1,
            "is_active": true
          }
        ]
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

### GET `/api/v1/styles/{style_id}` — get a style

| Path parameter | Type |
|---|---|
| `style_id` | UUID |

Returns the same public style shape shown above. It supports `lang` and `Accept-Language` in the same way as the list endpoint.

**Important current behavior:** unlike the public list endpoint, this endpoint does not enforce `is_active`, and it includes inactive variations. Public clients should normally navigate from the list response and should independently hide a detail response where `is_active` is `false` (and hide variations where `is_active` is `false`) until this backend behavior is changed.

| Error | Status | When |
|---|---:|---|
| `STYLE_NOT_FOUND` | 404 | no style exists for `style_id` |

### GET `/api/v1/addons` — list active add-ons

Returns only active add-ons, alphabetically by English name. Supports `lang`/`Accept-Language`; it is not paginated.

**Response `200`**

```json
{
  "status": "success",
  "status_label": "Success",
  "data": [
    {
      "id": "58c1dcdd-43e4-42c2-945d-7804cdb3ff6c",
      "slug": "beads",
      "name": "Beads",
      "suggested_price": "15.00",
      "is_active": true
    }
  ],
  "error": null
}
```

`suggested_price` is a decimal JSON string (or `null`), not a numeric JS float. It is a suggestion only; it is not a final booking price.

## Admin styles API

Admin base prefix: `/api/v1/admin`

All endpoints in this section can return `401 INVALID_ACCESS_TOKEN` for an absent/invalid/expired token and `403 FORBIDDEN` for an authenticated non-admin user.

### Category endpoints

#### GET `/api/v1/admin/style-categories`

Returns all categories sorted by `display_order`.

```json
{
  "data": [
    {
      "id": "6c38a7bd-321a-4f55-a3f5-66b349032e83",
      "slug": "knotless-braids",
      "name_en": "Knotless Braids",
      "name_de": null,
      "name_fr": null,
      "name_en_source": "HUMAN",
      "name_de_source": "PENDING",
      "name_fr_source": "PENDING",
      "display_order": 1
    }
  ]
}
```

The outer success fields are omitted from abbreviated examples in this admin section, but are always present.

#### POST `/api/v1/admin/style-categories`

Creates a category. Its slug is generated from `name` and made unique by appending `-2`, `-3`, etc. when needed.

```json
{ "name": "Knotless Braids", "display_order": 1 }
```

| Field | Type | Required | Rules |
|---|---|---:|---|
| `name` | string | yes | trimmed, non-blank, max 150 characters |
| `display_order` | integer | no | default `0` |

Returns `201` with a category object.

#### PUT `/api/v1/admin/style-categories/{category_id}`

Updates any supplied fields. It does **not** change the generated slug.

```json
{ "name": "New category name", "display_order": 2 }
```

All fields are optional; use `name` under the same rules as creation.

| Error | Status | When |
|---|---:|---|
| `STYLE_CATEGORY_NOT_FOUND` | 404 | category does not exist |

#### DELETE `/api/v1/admin/style-categories/{category_id}`

Returns `204 No Content` on success. It cannot delete a category referenced by a style.

| Error | Status | When |
|---|---:|---|
| `STYLE_CATEGORY_NOT_FOUND` | 404 | category does not exist |
| `ENTITY_IN_USE` | 409 | one or more styles still reference it |

### Style endpoints

An admin style object:

```json
{
  "id": "86e11160-ee13-4a7d-884e-b4b0b89d8ec5",
  "slug": "knotless-braids-mid-back",
  "category_id": "6c38a7bd-321a-4f55-a3f5-66b349032e83",
  "name_en": "Knotless Braids — Mid Back",
  "name_de": "Knotenlose Zöpfe — Mittlerer Rücken",
  "name_fr": "Tresses sans nœuds — Mi-dos",
  "name_en_source": "HUMAN",
  "name_de_source": "MACHINE",
  "name_fr_source": "MACHINE",
  "description_en": "Classic knotless braids finished at mid-back length.",
  "description_de": null,
  "description_fr": null,
  "description_en_source": "HUMAN",
  "description_de_source": "PENDING",
  "description_fr_source": "PENDING",
  "is_active": true,
  "images": [],
  "variations": []
}
```

#### GET `/api/v1/admin/styles`

Lists all styles, including inactive/unpublished styles and inactive variations.

| Parameter | Type | Required | Notes |
|---|---|---:|---|
| `category_id` | UUID | no | exact category filter |
| `search` | string | no | case-insensitive contains search against English name |
| `page`, `page_size` | integer | no | pagination controls |

Returns `200` with the standard paginated structure. Styles are ordered alphabetically by English name.

#### GET `/api/v1/admin/styles/{style_id}`

Returns one full admin style object, including every image and variation.

| Error | Status |
|---|---:|
| `STYLE_NOT_FOUND` | 404 |

#### POST `/api/v1/admin/styles`

Creates a style. It is created with `is_active: false`; explicitly publish it with the update endpoint when ready.

```json
{
  "category_id": "6c38a7bd-321a-4f55-a3f5-66b349032e83",
  "name": "Knotless Braids — Mid Back",
  "description": "Classic knotless braids finished at mid-back length."
}
```

| Field | Type | Required | Rules |
|---|---|---:|---|
| `category_id` | UUID or `null` | no | if supplied and non-null, must be an existing category |
| `name` | string | yes | trimmed, non-blank, max 150 chars |
| `description` | string or `null` | no | trimmed if supplied, non-blank, max 2,000 chars |

Returns `201` with an admin style object. It starts with no images or variations. The slug is generated from name and remains unchanged after later name edits.

| Error | Status | When |
|---|---:|---|
| `STYLE_CATEGORY_NOT_FOUND` | 404 | supplied category does not exist |

#### PUT `/api/v1/admin/styles/{style_id}`

Updates supplied fields:

```json
{
  "name": "Knotless Braids — Waist Length",
  "description": "Updated description.",
  "category_id": "6c38a7bd-321a-4f55-a3f5-66b349032e83",
  "is_active": true
}
```

All fields are optional. `name` and `description` use the validation rules above; a changed text field queues translations.

**Current API limitation:** `category_id: null` does not clear an existing category; the server treats it like an omitted field. There is currently no endpoint payload that unassigns a category. Slug is never regenerated.

| Error | Status | When |
|---|---:|---|
| `STYLE_NOT_FOUND` | 404 | style does not exist |
| `STYLE_CATEGORY_NOT_FOUND` | 404 | supplied non-null category does not exist |

#### DELETE `/api/v1/admin/styles/{style_id}`

Returns `204 No Content`. Deletes the style, its image records/storage objects, and its variations. A style referenced by existing catalog-dependent records cannot be deleted.

| Error | Status |
|---|---:|
| `STYLE_NOT_FOUND` | 404 |
| `ENTITY_IN_USE` | 409 |

### Style image endpoints

Use the following two-step direct-upload sequence. Do not send the binary file to this API.

1. Request a short-lived pre-signed upload URL.
2. `PUT` the raw image bytes to the returned `upload_url`, using the exact `Content-Type` requested.
3. Confirm the upload with the `object_key` returned in step 1.

Supported content types are `image/jpeg`, `image/png`, and `image/webp`. Maximum file size is **5 MiB** (5,242,880 bytes); a style has a maximum of **six** persisted images. Images receive the next sequential position (`0`, `1`, ...); there is no reordering endpoint.

#### POST `/api/v1/admin/styles/{style_id}/images/upload-url`

```json
{ "content_type": "image/jpeg" }
```

Returns `200`:

```json
{
  "data": {
    "upload_url": "https://storage-provider.example/...",
    "object_key": "styles/86e11160-ee13-4a7d-884e-b4b0b89d8ec5/images/15ca...jpg",
    "expires_in": 300
  }
}
```

`upload_url` expires in 300 seconds. The frontend must use the returned `object_key` exactly, and must not construct object keys itself.

| Error | Status | When |
|---|---:|---|
| `STYLE_NOT_FOUND` | 404 | style does not exist |
| `MAX_STYLE_IMAGES_REACHED` | 400 | style already has six persisted images |
| `VALIDATION_ERROR` | 422 | unsupported/missing `content_type` |

#### POST `/api/v1/admin/styles/{style_id}/images/confirm`

Call only after the object upload has completed successfully:

```json
{ "object_key": "styles/86e11160-ee13-4a7d-884e-b4b0b89d8ec5/images/15ca...jpg" }
```

Returns `201` with `StyleImage`.

| Error | Status | When |
|---|---:|---|
| `STYLE_NOT_FOUND` | 404 | style does not exist |
| `STYLE_IMAGE_NOT_FOUND` | 404 | object was not uploaded / cannot be found in storage |
| `INVALID_STYLE_IMAGE_UPLOAD` | 400 | key does not belong to that style, image type is invalid, or file exceeds 5 MiB |
| `MAX_STYLE_IMAGES_REACHED` | 400 | six images exist by confirmation time |

The service removes the uploaded object when confirmation rejects it for invalid type/size or image-limit overflow.

#### DELETE `/api/v1/admin/styles/{style_id}/images/{image_id}`

Returns `204 No Content` and removes the image record and its storage object.

| Error | Status |
|---|---:|
| `STYLE_NOT_FOUND` | 404 |
| `STYLE_IMAGE_NOT_FOUND` | 404 (unknown image or image belongs to another style) |

### Style variation endpoints

An admin variation object:

```json
{
  "id": "d1c9c6d1-625c-43b8-8333-6893714745fb",
  "name_en": "Mid-back length",
  "name_de": null,
  "name_fr": null,
  "name_en_source": "HUMAN",
  "name_de_source": "PENDING",
  "name_fr_source": "PENDING",
  "display_order": 1,
  "is_active": true
}
```

#### POST `/api/v1/admin/styles/{style_id}/variations`

```json
{ "name": "Mid-back length", "display_order": 1 }
```

`name` is required, trimmed, non-blank, and max 150 characters. `display_order` defaults to `0`. Returns `201` with a variation object; a new variation is active by default.

| Error | Status |
|---|---:|
| `STYLE_NOT_FOUND` | 404 |

#### PUT `/api/v1/admin/styles/{style_id}/variations/{variation_id}`

```json
{ "name": "Waist length", "display_order": 2, "is_active": false }
```

All fields are optional; modified names queue translation. Returns `200` with the variation object.

| Error | Status |
|---|---:|
| `STYLE_VARIATION_NOT_FOUND` | 404 (unknown variation or wrong parent style) |

#### DELETE `/api/v1/admin/styles/{style_id}/variations/{variation_id}`

Returns `204 No Content`.

| Error | Status |
|---|---:|
| `STYLE_VARIATION_NOT_FOUND` | 404 |
| `ENTITY_IN_USE` | 409 |

### Add-on endpoints

An admin add-on object:

```json
{
  "id": "58c1dcdd-43e4-42c2-945d-7804cdb3ff6c",
  "slug": "beads",
  "name_en": "Beads",
  "name_de": null,
  "name_fr": null,
  "name_en_source": "HUMAN",
  "name_de_source": "PENDING",
  "name_fr_source": "PENDING",
  "suggested_price": "15.00",
  "is_active": true
}
```

#### GET `/api/v1/admin/addons`

Lists all add-ons, including inactive add-ons, ordered alphabetically by English name. Returns `200` with an array of admin add-on objects; it is not paginated.

#### POST `/api/v1/admin/addons`

```json
{ "name": "Beads", "suggested_price": "15.00" }
```

| Field | Type | Required | Rules |
|---|---|---:|---|
| `name` | string | yes | trimmed, non-blank, max 150 chars |
| `suggested_price` | decimal string/number or `null` | no | default `null`; must be at least zero |

Returns `201`. It is active by default. Slug is generated from the original name and remains stable.

#### PUT `/api/v1/admin/addons/{addon_id}`

```json
{ "name": "Gold beads", "suggested_price": "18.50", "is_active": true }
```

All fields are optional. A name change queues translations. Returns `200`.

**Current API limitation:** `suggested_price: null` is treated as no change, so an existing price cannot currently be cleared through this endpoint.

| Error | Status |
|---|---:|
| `ADDON_NOT_FOUND` | 404 |

#### DELETE `/api/v1/admin/addons/{addon_id}`

Returns `204 No Content`.

| Error | Status |
|---|---:|
| `ADDON_NOT_FOUND` | 404 |
| `ENTITY_IN_USE` | 409 |

## Recommended admin UI flow

1. Load `GET /api/v1/admin/style-categories`, `GET /api/v1/admin/styles`, and `GET /api/v1/admin/addons` using the admin token.
2. Create a category (optional), then create a style. Keep the new style unpublished until its content is ready.
3. Add variations and upload up to six images through the pre-signed upload flow.
4. Monitor translation-source fields if the admin interface shows multilingual catalog readiness; `PENDING` and `FAILED` indicate a locale is not ready.
5. Publish with `PUT /api/v1/admin/styles/{style_id}` and `{ "is_active": true }`.
6. For public UI, use the public list endpoints as the source of truth and pass the current application locale using `lang` or `Accept-Language`.

## Consolidated catalog error codes

| Code | HTTP status | Meaning |
|---|---:|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing, invalid, or expired admin bearer token |
| `FORBIDDEN` | 403 | token user is not an admin |
| `VALIDATION_ERROR` | 422 | malformed ID/query/body or a schema constraint failed |
| `STYLE_CATEGORY_NOT_FOUND` | 404 | category does not exist |
| `STYLE_NOT_FOUND` | 404 | style does not exist |
| `STYLE_VARIATION_NOT_FOUND` | 404 | variation does not exist under the supplied style |
| `ADDON_NOT_FOUND` | 404 | add-on does not exist |
| `STYLE_IMAGE_NOT_FOUND` | 404 | uploaded/registered image does not exist |
| `INVALID_STYLE_IMAGE_UPLOAD` | 400 | invalid style image key, type, or size |
| `MAX_STYLE_IMAGES_REACHED` | 400 | six-image limit reached |
| `ENTITY_IN_USE` | 409 | deletion blocked because another record references the entity |
| `INTERNAL_SERVER_ERROR` | 500 | unhandled server failure |
