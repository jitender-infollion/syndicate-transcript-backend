from fastapi import HTTPException

MIN_PASSWORD_LENGTH = 8


def validate_password(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")


def validate_otp_format(otp: str) -> None:
    if not otp or not otp.isdigit() or len(otp) != 6:
        raise HTTPException(status_code=400, detail="Invalid OTP format.")
