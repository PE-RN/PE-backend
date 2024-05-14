from pydantic import BaseModel

from schemas.geometry import Geometry
from schemas.properties import Properties


class Feature(BaseModel):
    type: str
    properties: Properties
    geometry: Geometry
