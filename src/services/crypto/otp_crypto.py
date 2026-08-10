import hashlib
import hmac

from config import get_settings


def hash_otp(code: str) -> str:
    # Keyed hash - a bare hash of a 6-digit code is brute-forceable offline from a DB dump.
    secret = get_settings().secrets.otp_hash_secret.encode()
    return hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()
