import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


def _sha256_hex_for_bcrypt(password: str) -> str:
    """Bcrypt only accepts <=72 bytes; SHA-256 hex fits and removes length limits."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    secret = _sha256_hex_for_bcrypt(password).encode("utf-8")
    return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    h = hashed.encode("ascii")
    for candidate in (_sha256_hex_for_bcrypt(plain).encode("utf-8"), plain.encode("utf-8")):
        try:
            if bcrypt.checkpw(candidate, h):
                return True
        except ValueError:
            continue
    return False


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "exp": expire,
        "iat": now,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(jti: str, subject: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": subject,
        "jti": jti,
        "type": "refresh",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def safe_decode_token(token: str) -> dict[str, Any] | None:
    try:
        return decode_token(token)
    except JWTError:
        return None


def new_jti() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_otp_code(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
