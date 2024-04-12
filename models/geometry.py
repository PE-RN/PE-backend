from pydantic import BaseModel

class GeometryModel(BaseModel):
    type: str
    coordinates: list
