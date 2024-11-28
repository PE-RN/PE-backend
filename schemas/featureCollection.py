from pydantic import BaseModel
from typing import List
from schemas.feature import Feature


class FeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[Feature]
