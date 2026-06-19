from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    AUTH_MODE: Literal["mock", "email"] = "mock"
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/user_salse"
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    INVITE_CODE_SECRET: str = "invite-secret-change-me"

    model_config = {"env_file": ".env"}


settings = Settings()
