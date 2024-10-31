from pydantic import BaseModel
from typing import Union, List
from schemas.geometry import Geometry
from schemas.properties import Properties


class Feature(BaseModel):
    type: str
    properties: Properties
    geometry: Geometry

class FeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[Feature]

# Union type to allow either a Feature or a FeatureCollection
GeoJSONInput = Union[Feature, FeatureCollection]
