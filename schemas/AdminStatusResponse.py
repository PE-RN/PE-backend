from pydantic import BaseModel

class AdminStatusResponse(BaseModel):
    is_admin: bool