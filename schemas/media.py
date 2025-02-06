from pydantic import BaseModel
from typing_extensions import TypedDict


class MediaCreate(BaseModel):
    path: str
    category: str
    sub_category: str
    name: str


class MediaUpdate(TypedDict, total=False):
    path: str | None
    category: str | None
    sub_category: str
    name: str | None


class CreatePdf(MediaCreate):
    pass


class CreateVideo(MediaCreate):
    pass
