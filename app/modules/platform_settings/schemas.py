import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.platform_settings.models import SettingValueType


class PlatformSettingsResponse(BaseModel):
    id: uuid.UUID
    platform_fee_type: SettingValueType
    platform_fee_value: Decimal
    vat_type: SettingValueType
    vat_value: Decimal
    vat_platform_fee_type: SettingValueType
    vat_platform_fee_value: Decimal
    deposit_type: SettingValueType
    deposit_value: Decimal


class PlatformSettingsUpdateRequest(BaseModel):
    platform_fee_type: SettingValueType | None = None
    platform_fee_value: Decimal | None = Field(default=None, ge=0)
    vat_type: SettingValueType | None = None
    vat_value: Decimal | None = Field(default=None, ge=0)
    vat_platform_fee_type: SettingValueType | None = None
    vat_platform_fee_value: Decimal | None = Field(default=None, ge=0)
    deposit_type: SettingValueType | None = None
    deposit_value: Decimal | None = Field(default=None, ge=0)


class CountryVatSettingsResponse(BaseModel):
    country: str
    vat_type: SettingValueType
    vat_value: Decimal
    vat_platform_fee_type: SettingValueType
    vat_platform_fee_value: Decimal


class CountryVatSettingsUpsertRequest(BaseModel):
    """PUT body for `.../country-vat/{country}` - the country itself comes
    from the path, not the body, so this is a full replace of that
    country's rates (no partial-update semantics, unlike the singleton
    PlatformSettings PATCH)."""

    vat_type: SettingValueType
    vat_value: Decimal = Field(ge=0)
    vat_platform_fee_type: SettingValueType
    vat_platform_fee_value: Decimal = Field(ge=0)
