"""
Shared JWT auth dependency used by both server.py and voice/router.py.
Extracted to avoid a circular import between server.py and voice/router.py.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from chatbot.config import JWT_ALGORITHM, JWT_SECRET_KEY

_bearer = HTTPBearer()


def get_current_user_id(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> int:
    try:
        payload = jwt.decode(
            creds.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
