import sys
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_is_test = "pytest" in sys.modules


class Settings(BaseSettings):
    """
    Application settings using pydantic-settings.
    Automatically loads from .env file if present.
    """

    TELEGRAM_BOT_TOKEN: str = Field(default="test_token" if _is_test else ...)  # type: ignore
    DROPBOX_APP_KEY: str = Field(default="test_key" if _is_test else ...)  # type: ignore
    DROPBOX_APP_SECRET: str = Field(default="test_secret" if _is_test else ...)  # type: ignore
    DROPBOX_REFRESH_TOKEN: str = Field(default="test_refresh" if _is_test else ...)  # type: ignore
    ADMIN_ID: Optional[int] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instance
settings = Settings()  # type: ignore
