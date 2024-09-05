from pydantic import BaseModel


class FeedbackCreate(BaseModel):

    name: str | None = None
    email: str | None = None
    message: str | None = None
    platform_rate: int | None = None
    intuitivity: int | None = None
    type: str
