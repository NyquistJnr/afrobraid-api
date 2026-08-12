# Admin - Platform Settings API

Base URL prefix: `/api/v1/admin/platform-settings`

## Auth

All endpoints require a Bearer JWT for a user with role `ADMIN`.

```http
Authorization: Bearer <access_token>
```

- Missing/invalid/expired token -> `401 INVALID_ACCESS_TOKEN`
- Wrong role -> `403 FORBIDDEN`

---

## Setting value types

| Type | Meaning |
|---|---|
| `PERCENTAGE` | Value is a percentage. Values must be `0` through `100`. |
| `FIXED` | Value is a fixed amount. Values must be `>= 0`. |

Decimal values are serialized as strings in responses, e.g. `"10.00"`. Request bodies may send JSON numbers or strings.

---

## GET `/api/v1/admin/platform-settings` - Get platform settings

Returns the singleton platform pricing settings row. If the row does not exist yet, the service creates it lazily with defaults and returns it.

Default values created by the service:

| Field | Default |
|---|---|
| `platform_fee_type` | `PERCENTAGE` |
| `platform_fee_value` | `10.00` |
| `vat_type` | `PERCENTAGE` |
| `vat_value` | `20.00` |
| `vat_platform_fee_type` | `PERCENTAGE` |
| `vat_platform_fee_value` | `20.00` |
| `deposit_type` | `PERCENTAGE` |
| `deposit_value` | `10.00` |

Admin reads always hit the database directly rather than the cache, so admins see their latest writes.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "97f0f9f7-87e7-4731-9786-323203b81622",
    "platform_fee_type": "PERCENTAGE",
    "platform_fee_value": "10.00",
    "vat_type": "PERCENTAGE",
    "vat_value": "20.00",
    "vat_platform_fee_type": "PERCENTAGE",
    "vat_platform_fee_value": "20.00",
    "deposit_type": "PERCENTAGE",
    "deposit_value": "10.00"
  },
  "error": null
}
```

### Response fields

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Singleton settings row id. |
| `platform_fee_type` | `SettingValueType` | How to interpret `platform_fee_value`. |
| `platform_fee_value` | decimal string | Platform fee charged by the marketplace. |
| `vat_type` | `SettingValueType` | How to interpret `vat_value`. |
| `vat_value` | decimal string | VAT charged on the braider service/subtotal. |
| `vat_platform_fee_type` | `SettingValueType` | How to interpret `vat_platform_fee_value`. |
| `vat_platform_fee_value` | decimal string | VAT charged on the platform fee. |
| `deposit_type` | `SettingValueType` | How to interpret `deposit_value`. |
| `deposit_value` | decimal string | Upfront reservation deposit value. |

---

## PATCH `/api/v1/admin/platform-settings` - Update platform settings

Partially updates the singleton platform pricing settings. Only provided fields are changed. After a successful write, platform settings cache is invalidated around the commit.

### Request body

```json
{
  "platform_fee_type": "PERCENTAGE",
  "platform_fee_value": "12.50",
  "vat_type": "PERCENTAGE",
  "vat_value": "19.00",
  "vat_platform_fee_type": "PERCENTAGE",
  "vat_platform_fee_value": "19.00",
  "deposit_type": "PERCENTAGE",
  "deposit_value": "15.00"
}
```

All fields are optional.

| Field | Type | Required | Notes |
|---|---|---|---|
| `platform_fee_type` | `SettingValueType` or null | no | `PERCENTAGE` or `FIXED`. |
| `platform_fee_value` | decimal or null | no | Must be `>= 0`; must be `<= 100` when effective type is `PERCENTAGE`. |
| `vat_type` | `SettingValueType` or null | no | `PERCENTAGE` or `FIXED`. |
| `vat_value` | decimal or null | no | Must be `>= 0`; must be `<= 100` when effective type is `PERCENTAGE`. |
| `vat_platform_fee_type` | `SettingValueType` or null | no | `PERCENTAGE` or `FIXED`. |
| `vat_platform_fee_value` | decimal or null | no | Must be `>= 0`; must be `<= 100` when effective type is `PERCENTAGE`. |
| `deposit_type` | `SettingValueType` or null | no | `PERCENTAGE` or `FIXED`. |
| `deposit_value` | decimal or null | no | Must be `>= 0`; must be `<= 100` when effective type is `PERCENTAGE`. |

Validation applies after merging the patch with existing settings. For example, changing `deposit_type` to `PERCENTAGE` while the existing `deposit_value` is `150.00` fails.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "id": "97f0f9f7-87e7-4731-9786-323203b81622",
    "platform_fee_type": "PERCENTAGE",
    "platform_fee_value": "12.50",
    "vat_type": "PERCENTAGE",
    "vat_value": "19.00",
    "vat_platform_fee_type": "PERCENTAGE",
    "vat_platform_fee_value": "19.00",
    "deposit_type": "PERCENTAGE",
    "deposit_value": "15.00"
  },
  "error": null
}
```

### Errors

| Code | Status | When |
|---|---|---|
| `INVALID_SETTING_VALUE` | 400 | an effective `PERCENTAGE` value is greater than `100` |
| `VALIDATION_ERROR` | 422 | malformed body, invalid enum, or negative decimal value |

---

## GET `/api/v1/admin/platform-settings/country-vat` - List country VAT settings

Returns all country-specific VAT overrides ordered alphabetically by country code. If a country appears here, these VAT values override the default platform `vat_*` settings for that country.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": [
    {
      "country": "DE",
      "vat_type": "PERCENTAGE",
      "vat_value": "19.00",
      "vat_platform_fee_type": "PERCENTAGE",
      "vat_platform_fee_value": "19.00"
    },
    {
      "country": "FR",
      "vat_type": "PERCENTAGE",
      "vat_value": "20.00",
      "vat_platform_fee_type": "PERCENTAGE",
      "vat_platform_fee_value": "20.00"
    }
  ],
  "error": null
}
```

---

## PUT `/api/v1/admin/platform-settings/country-vat/{country}` - Upsert country VAT settings

Creates or replaces the VAT override for one country. The country comes from the path, not the body. The service normalizes the country code by trimming whitespace and uppercasing it.

### Path params

| Param | Type | Notes |
|---|---|---|
| `country` | string | Two-letter alphabetic country code, e.g. `DE`, `FR`, `NG`. Case-insensitive. |

### Request body

```json
{
  "vat_type": "PERCENTAGE",
  "vat_value": "19.00",
  "vat_platform_fee_type": "PERCENTAGE",
  "vat_platform_fee_value": "19.00"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `vat_type` | `SettingValueType` | yes | `PERCENTAGE` or `FIXED`. |
| `vat_value` | decimal | yes | Must be `>= 0`; must be `<= 100` when `vat_type` is `PERCENTAGE`. |
| `vat_platform_fee_type` | `SettingValueType` | yes | `PERCENTAGE` or `FIXED`. |
| `vat_platform_fee_value` | decimal | yes | Must be `>= 0`; must be `<= 100` when `vat_platform_fee_type` is `PERCENTAGE`. |

This is a full replace for the country's VAT override. It does not support partial update semantics.

### Response `200`

```json
{
  "status": "success",
  "status_label": "Success",
  "data": {
    "country": "DE",
    "vat_type": "PERCENTAGE",
    "vat_value": "19.00",
    "vat_platform_fee_type": "PERCENTAGE",
    "vat_platform_fee_value": "19.00"
  },
  "error": null
}
```

### Errors

| Code | Status | When |
|---|---|---|
| `INVALID_SETTING_VALUE` | 400 | a `PERCENTAGE` value is greater than `100` |
| `INVALID_COUNTRY_CODE` | 422 | `country` is not exactly two alphabetic characters after trimming |
| `VALIDATION_ERROR` | 422 | malformed body, invalid enum, or negative decimal value |

---

## DELETE `/api/v1/admin/platform-settings/country-vat/{country}` - Delete country VAT settings

Deletes the country-specific VAT override. After deletion, pricing for that country falls back to the singleton platform VAT settings. The country cache key is invalidated around the commit.

### Path params

| Param | Type | Notes |
|---|---|---|
| `country` | string | Two-letter alphabetic country code, case-insensitive. |

### Response `204`

No response body.

### Errors

| Code | Status | When |
|---|---|---|
| `COUNTRY_VAT_SETTINGS_NOT_FOUND` | 404 | no override exists for the normalized country code |
| `INVALID_COUNTRY_CODE` | 422 | `country` is not exactly two alphabetic characters after trimming |

---

## Common error codes

| Code | HTTP status | When |
|---|---|---|
| `INVALID_ACCESS_TOKEN` | 401 | missing/invalid/expired Bearer token |
| `FORBIDDEN` | 403 | caller is not an `ADMIN` |
| `INVALID_SETTING_VALUE` | 400 | percentage value is greater than `100` |
| `INVALID_COUNTRY_CODE` | 422 | invalid country path param |
| `COUNTRY_VAT_SETTINGS_NOT_FOUND` | 404 | delete requested for a missing country VAT override |
| `VALIDATION_ERROR` | 422 | malformed path params/body |
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
