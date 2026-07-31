from pydantic import BaseModel


class ProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    companyName: str | None = None
