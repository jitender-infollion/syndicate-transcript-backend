_AUTH = "/api/auth"
_USERS = "/api/users"


class P:
    class auth:
        BASE = _AUTH
        REGISTER = "/register"
        REGISTER_VERIFY_OTP = "/register/verify-otp"
        REGISTER_RESEND_OTP = "/register/resend-otp"
        LOGIN = "/login"
        LOGOUT = "/logout"
        FORGOT_PASSWORD = "/forgot-password"
        RESET_PASSWORD = "/reset-password"

    class users:
        BASE = _USERS
        ME = "/me"
