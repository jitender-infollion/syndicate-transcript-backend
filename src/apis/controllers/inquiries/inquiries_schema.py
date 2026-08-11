from pydantic import BaseModel, EmailStr, Field


class SupportMessagePayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    message: str = Field(min_length=1, max_length=5000)


class TopicRequestPayload(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    topic: str = Field(min_length=1, max_length=300)
    domain: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    remark: str | None = Field(default=None, max_length=2000)
    suggestedExpertName: str | None = Field(default=None, max_length=200)
    suggestedExpertLinkedin: str | None = Field(default=None, max_length=500)
