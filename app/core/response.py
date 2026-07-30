from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    status: str = "success"
    data: DataT
    error: None = None
