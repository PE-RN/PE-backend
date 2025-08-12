from pydantic import BaseModel
from typing_extensions import TypedDict


class LayerGroupCreate(BaseModel):
    name: str
    layer_group_id: str | None = None

class LayerCreate(BaseModel):
    name: str
    path: str | None = None
    path_icon: str | None = None
    subtitle: str | None = None
    layer_group_id: str
