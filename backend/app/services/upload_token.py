from itsdangerous import URLSafeTimedSerializer

from app.config import settings


_SALT = "mis-upload"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=_SALT)


def make_upload_token(company_id: int, period: tuple[int, int]) -> str:
    return _serializer().dumps(
        {"company_id": company_id, "year": period[0], "month": period[1]}
    )


def verify_upload_token(token: str, max_age: int | None = None) -> dict:
    if max_age is None:
        max_age = settings.REMINDER_TOKEN_TTL_DAYS * 86400
    return _serializer().loads(token, max_age=max_age)
