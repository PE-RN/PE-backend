from pydantic import BaseModel
from enums.ocupation_enum import OcupationEnum


class UserCreate(BaseModel):

    email: str
    ocupation: OcupationEnum
    password: str
    group_id: int | None = '5c190872-1800-4c8c-9411-23937d0a8d52'
    gender: str
    education: str
    institution: str
    age: str
    user: str
