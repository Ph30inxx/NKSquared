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


settings = Settings()
