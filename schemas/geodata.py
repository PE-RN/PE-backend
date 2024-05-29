from pydantic import BaseModel


class Geodata(BaseModel):
    id: int
    name: str
    email: str
    ocupation: str
    group_id: int

    class config:
        orm_mode = True


class Geodata(Geodata):

    id: int
    name: str
    email: str
    ocupation: str
    password: str
    group_id: int
