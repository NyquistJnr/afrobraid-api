from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.i18n import get_current_locale, t

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    status: str = "success"
    status_label: str = Field(
        default_factory=lambda: t("status.success", get_current_locale())
    )
    data: DataT
    error: None = None
