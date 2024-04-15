from pydantic import BaseModel
from models.geometry import GeometryModel
from models.properties import PropertiesModel


class FeatureModel(BaseModel):
    type: str
    properties: PropertiesModel
    geometry: GeometryModel
