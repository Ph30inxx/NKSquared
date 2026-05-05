from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://nksquared_user:dev@postgres:5432/nksquared"
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES_MIN: int = 15
    JWT_REFRESH_TOKEN_EXPIRES_DAYS: int = 7

    FRONTEND_URL: str = "http://localhost:5173"

    SMTP_HOST: str = "mailhog"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = False
    EMAIL_FROM: str = "noreply@nksquared.local"
    EMAIL_FROM_NAME: str = "NKSquared"
    FUND_NAME: str = "NKSquared"
    PUBLIC_UPLOAD_BASE_URL: str = "http://localhost:5173"
    REMINDER_TOKEN_TTL_DAYS: int = 30


settings = Settings()
