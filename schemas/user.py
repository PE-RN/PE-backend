from pydantic import BaseModel
from enums.ocupation_enum import OcupationEnum
from typing_extensions import TypedDict


class UserCreate(BaseModel):

    email: str
    ocupation: OcupationEnum
    password: str
    group_id: str | None = None
    gender: str
    education: str
    institution: str
    age: str
    user: str


class UserUpdate(TypedDict, total=False):

    email: str | None
    ocupation: OcupationEnum | None
    current_password: str | None
    new_password: str | None
    group_id: str | None
    gender: str | None
    education: str | None
    institution: str | None
    age: str | None
    user: str | None
