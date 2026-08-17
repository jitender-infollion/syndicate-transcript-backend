_AUTH = "/api/auth"
_USERS = "/api/users"
_TRANSCRIPTS = "/api/transcripts"
_CART = "/api/cart"
_ORDERS = "/api/orders"
_SUPPORT = "/api/support"
_TOPICS = "/api/topics"


class P:
    class system:
        HEALTH = "/health"

    class auth:
        BASE = _AUTH
        REGISTER = "/register"
        REGISTER_VERIFY_OTP = "/register/verify-otp"
        REGISTER_RESEND_OTP = "/register/resend-otp"
        LOGIN = "/login"
        LOGIN_OTP_SEND = "/login/otp/send"
        LOGIN_OTP_VERIFY = "/login/otp/verify"
        REFRESH = "/refresh"
        LOGOUT = "/logout"
        FORGOT_PASSWORD = "/forgot-password"
        RESET_PASSWORD = "/reset-password"

    class users:
        BASE = _USERS
        ME = "/me"

    class transcripts:
        BASE = _TRANSCRIPTS
        LIST = ""
        FILTER = "/filter"
        MY_PURCHASED = "/me/purchased"
        DOMAINS = "/domains"
        DETAIL = "/{transcript_id}"
        VIEW = "/{transcript_id}/view"
        DOWNLOAD = "/{transcript_id}/download"
        FULL_TEXT = "/{transcript_id}/full-text"

    class cart:
        BASE = _CART
        ROOT = ""
        ITEMS = "/items"
        ITEM_DETAIL = "/items/{transcript_id}"
        MERGE = "/merge"

    class orders:
        BASE = _ORDERS
        ROOT = ""
        VERIFY = "/verify"
        DETAIL = "/{order_id}"
        RECEIPT = "/{order_id}/receipt"
        WEBHOOK = "/webhook/{gateway}"

    class support:
        BASE = _SUPPORT
        ROOT = ""

    class topics:
        BASE = _TOPICS
        REQUEST = "/request"
        MY_REQUESTS = "/my-requests"
