from pydantic import BaseModel


class UserCreate(BaseModel):

    email: str
    ocupation: str
    password: str
    group_id: int | None = None
