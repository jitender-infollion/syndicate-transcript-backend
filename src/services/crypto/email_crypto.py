import hashlib
import hmac

from cryptography.fernet import Fernet

from config import get_settings


def _fernet() -> Fernet:
    return Fernet(get_settings().secrets.email_encryption_key.encode())


def encrypt_email(email: str) -> str:
    return _fernet().encrypt(email.encode()).decode()


def decrypt_email(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def hash_email(email: str) -> str:
    """Deterministic keyed hash for exact-match lookup - never decrypted, never
    used to derive the plaintext. Lowercased first so lookup stays case-insensitive."""
    secret = get_settings().secrets.email_hash_secret.encode()
    return hmac.new(secret, email.strip().lower().encode(), hashlib.sha256).hexdigest()
