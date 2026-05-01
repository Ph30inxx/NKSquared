from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

# bcrypt itself caps inputs at 72 bytes. Match that limit at the boundary so we
# fail with a clear API error instead of a backend exception.
_BCRYPT_MAX_BYTES = 72


def _to_bytes(plain: str) -> bytes:
    encoded = plain.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        raise ValueError("password cannot be longer than 72 bytes")
    return encoded


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_to_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def _build_token(claims: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**claims, "iat": int(now.timestamp()), "exp": int((now + expires_delta).timestamp())}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(*, user_id: int, email: str, role: str) -> str:
    return _build_token(
        {"sub": str(user_id), "email": email, "role": role, "type": ACCESS_TOKEN_TYPE},
        timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MIN),
    )


def create_refresh_token(*, user_id: int) -> str:
    return _build_token(
        {"sub": str(user_id), "type": REFRESH_TOKEN_TYPE},
        timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRES_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
