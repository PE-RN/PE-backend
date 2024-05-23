from pydantic import BaseModel


class EmailMessage(BaseModel):
    subject: str
    to_email: str
    html_content: str
