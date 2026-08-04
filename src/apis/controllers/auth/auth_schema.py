from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    companyName: str | None = None


class PendingAuthResponse(BaseModel):
    tempToken: str


class VerifyOtpRequest(BaseModel):
    tempToken: str
    otp: str


class ResendOtpRequest(BaseModel):
    tempToken: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginOtpSendRequest(BaseModel):
    email: EmailStr


class LoginOtpVerifyRequest(BaseModel):
    tempToken: str
    otp: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class AuthUserResponse(BaseModel):
    id: str
    name: str
    email: str
    companyName: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: AuthUserResponse
