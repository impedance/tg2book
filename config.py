import sys
from typing import Any, Optional

from pydantic import Field, field_validator
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
    API_ID: Optional[int] = None
    API_HASH: Optional[str] = None
    USERBOT_SESSION_STRING: Optional[str] = None

    @field_validator("ADMIN_ID", "API_ID", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v: Any) -> Any:
        """Treat empty string (from blank .env entries like ADMIN_ID=) as None."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("API_HASH", mode="before")
    @classmethod
    def _empty_api_hash_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instance
settings = Settings()  # type: ignore
