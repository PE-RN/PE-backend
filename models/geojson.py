from pydantic import BaseModel
from models.feature import FeatureModel

class GeoJSONModel(BaseModel):
    type: str
    features: list[FeatureModel]
