import hashlib
import hmac

from config import get_settings


def hash_otp(code: str) -> str:
    """Keyed hash (HMAC pepper) rather than a bare hash - a 6-digit code has only
    1M possible values, trivially brute-forced offline from a stolen DB dump
    without the server-side secret."""
    secret = get_settings().secrets.otp_hash_secret.encode()
    return hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()
