import os
from functools import lru_cache


class Settings:
    """Application settings from environment."""

    def __init__(self):
        self.app_name = os.getenv("APP_NAME", "Event Board")
        self.secret_key = os.getenv("SECRET_KEY", "change-me-in-production-use-env")
        self.algorithm = os.getenv("ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
        self.database_url = os.getenv("DATABASE_URL", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
