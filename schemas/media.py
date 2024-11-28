from pydantic import BaseModel
from typing_extensions import TypedDict


class MediaCreate(BaseModel):
    path: str
    category: str
    name: str


class MediaUpdate(TypedDict, total=False):
    path: str | None
    category: str | None
    name: str | None


class CreatePdf(MediaCreate):
    pass


class CreateVideo(MediaCreate):
    pass
