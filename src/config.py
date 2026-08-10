import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def get_env(key: str, default: str = "", required: bool = True) -> str:
    value = os.getenv(key, default).strip()
    if required and not value:
        raise RuntimeError(f"Required environment variable '{key}' is not set. App cannot start.")
    return value


def get_bool_env(key: str, default: bool = False) -> bool:
    value = os.getenv(key, "").strip().lower()
    if not value:
        return default
    return value == "true"


@dataclass
class DatabaseConfig:
    url: str


@dataclass
class AuthConfig:
    jwt_secret: str
    access_token_expiry_minutes: int
    refresh_token_expiry_days: int
    cookie_secure: bool  # false only for local http dev
    trusted_jwt_secrets: list = field(default_factory=list)  # e.g. Infollion SSO tokens


@dataclass
class ServicesConfig:
    cors_origins: list
    frontend_base_url: str
    enable_docs: bool = False  # exposes the full API surface with no auth of its own


@dataclass
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    from_email: str
    use_tls: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password and self.from_email)


@dataclass
class SecretsConfig:
    email_encryption_key: str
    email_hash_secret: str
    otp_hash_secret: str


@dataclass
class SigningServiceConfig:
    base_url: str  # endpoint/auth contract not finalized yet - placeholders
    api_key: str

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)


@dataclass
class PaymentConfig:
    razorpay_key_id: str
    razorpay_key_secret: str
    razorpay_webhook_secret: str
    currency: str

    @property
    def is_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret and self.razorpay_webhook_secret)


@dataclass
class Settings:
    database: DatabaseConfig
    auth: AuthConfig
    services: ServicesConfig
    email: EmailConfig
    secrets: SecretsConfig
    signing_service: SigningServiceConfig
    payment: PaymentConfig

    @classmethod
    def from_env(cls) -> "Settings":
        raw_origins = get_env("CORS_ALLOWED_ORIGINS")
        cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        if not cors_origins:
            raise RuntimeError("CORS_ALLOWED_ORIGINS must contain at least one origin. App cannot start.")

        raw_trusted_secrets = get_env("JWT_TRUSTED_SECRETS", default="", required=False)
        trusted_secrets = [s.strip() for s in raw_trusted_secrets.split(",") if s.strip()]

        return cls(
            database=DatabaseConfig(
                url=get_env("DATABASE_URL"),
            ),
            auth=AuthConfig(
                jwt_secret=get_env("JWT_SECRET"),
                access_token_expiry_minutes=int(get_env("ACCESS_TOKEN_EXPIRY_MINUTES", default="15", required=False)),
                refresh_token_expiry_days=int(get_env("REFRESH_TOKEN_EXPIRY_DAYS", default="30", required=False)),
                cookie_secure=get_bool_env("COOKIE_SECURE", default=True),
                trusted_jwt_secrets=trusted_secrets,
            ),
            services=ServicesConfig(
                cors_origins=cors_origins,
                frontend_base_url=get_env("FRONTEND_BASE_URL"),
                enable_docs=get_bool_env("ENABLE_DOCS", default=False),
            ),
            email=EmailConfig(
                smtp_host=get_env("SMTP_HOST", default="", required=False),
                smtp_port=int(get_env("SMTP_PORT", default="587", required=False)),
                smtp_username=get_env("SMTP_USER", default="", required=False),
                smtp_password=get_env("SMTP_PASS", default="", required=False),
                from_email=get_env("SMTP_FROM", default="", required=False),
                use_tls=get_bool_env("SMTP_USE_TLS", default=True),
            ),
            secrets=SecretsConfig(
                email_encryption_key=get_env("EMAIL_ENCRYPTION_KEY"),
                email_hash_secret=get_env("EMAIL_HASH_SECRET"),
                otp_hash_secret=get_env("OTP_HASH_SECRET"),
            ),
            signing_service=SigningServiceConfig(
                base_url=get_env("SIGNING_SERVICE_URL", default="", required=False),
                api_key=get_env("SIGNING_SERVICE_API_KEY", default="", required=False),
            ),
            payment=PaymentConfig(
                razorpay_key_id=get_env("RAZORPAY_KEY_ID", default="", required=False),
                razorpay_key_secret=get_env("RAZORPAY_KEY_SECRET", default="", required=False),
                razorpay_webhook_secret=get_env("RAZORPAY_WEBHOOK_SECRET", default="", required=False),
                currency=get_env("PAYMENT_CURRENCY", default="USD", required=False),
            ),
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
