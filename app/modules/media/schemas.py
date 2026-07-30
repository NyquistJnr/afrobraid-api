from pydantic import BaseModel


class DeleteMediaRequest(BaseModel):
    object_key: str


class DeleteMediaResponse(BaseModel):
    message: str
