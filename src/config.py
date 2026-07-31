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
    jwt_expiry_hours: int
    # Additional signing secrets this service will also accept on incoming
    # Bearer tokens (e.g. tokens issued by the main Infollion platform during
    # the SSO handoff). No live integration exists yet; this is a structural
    # placeholder until that platform side is coordinated.
    trusted_jwt_secrets: list = field(default_factory=list)


@dataclass
class ServicesConfig:
    cors_origins: list
    frontend_base_url: str


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
class Settings:
    database: DatabaseConfig
    auth: AuthConfig
    services: ServicesConfig
    email: EmailConfig

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
                jwt_expiry_hours=int(get_env("JWT_EXPIRY_HOURS", default="24", required=False)),
                trusted_jwt_secrets=trusted_secrets,
            ),
            services=ServicesConfig(
                cors_origins=cors_origins,
                frontend_base_url=get_env("FRONTEND_BASE_URL"),
            ),
            email=EmailConfig(
                smtp_host=get_env("SMTP_HOST", default="", required=False),
                smtp_port=int(get_env("SMTP_PORT", default="587", required=False)),
                smtp_username=get_env("SMTP_USER", default="", required=False),
                smtp_password=get_env("SMTP_PASS", default="", required=False),
                from_email=get_env("SMTP_FROM", default="", required=False),
                use_tls=get_bool_env("SMTP_USE_TLS", default=True),
            ),
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
