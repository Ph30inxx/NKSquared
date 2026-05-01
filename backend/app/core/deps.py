import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        raise _credentials_exc from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise _credentials_exc

    sub = payload.get("sub")
    if sub is None:
        raise _credentials_exc

    user = db.get(User, int(sub))
    if user is None or not user.is_active:
        raise _credentials_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def require_role(allowed: list[str]):
    """Dependency factory: gate a route on one of `allowed` role names."""
    allowed_set = frozenset(allowed)

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role in {sorted(allowed_set)}",
            )
        return user

    return _checker
