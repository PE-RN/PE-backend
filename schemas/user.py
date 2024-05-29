from pydantic import BaseModel
from enums.ocupation_enum import OcupationEnum


class UserCreate(BaseModel):

    email: str
    ocupation: OcupationEnum
    password: str
    group_id: int | None = None
