from pydantic import BaseModel


class PropertiesModel(BaseModel):
    name: str | None = None
    description: str | None = None
