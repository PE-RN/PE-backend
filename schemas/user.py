from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    email: str
    ocupation: str
    group_id: int

    class config:
        orm_mode = True


class UserCreate(User):

    id: int
    name: str
    email: str
    ocupation: str
    password: str
    group_id: int
