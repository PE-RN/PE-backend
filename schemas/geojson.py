from pydantic import BaseModel

from schemas.feature import Feature


class GeoJSON(BaseModel):
    type: str
    features: list[Feature]
