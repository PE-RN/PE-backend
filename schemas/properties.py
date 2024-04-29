from pydantic import BaseModel


class Properties(BaseModel):
    name: str | None = None
    description: str | None = None
