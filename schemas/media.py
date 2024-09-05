from pydantic import BaseModel


class MediaCreate(BaseModel):
    path: str
    category: str
    name: str


class CreatePdf(MediaCreate):
    pass


class CreateVideo(MediaCreate):
    pass
