import os
from unittest.mock import patch

from config import Settings


def test_config_parsing_from_env():
    """Test that config.py correctly parses values from environment variables."""
    target_env = {
        "TELEGRAM_BOT_TOKEN": "env_token",
        "DROPBOX_APP_KEY": "env_key",
        "DROPBOX_APP_SECRET": "env_secret",
        "DROPBOX_REFRESH_TOKEN": "env_refresh",
        "ADMIN_ID": "1001",
    }

    with patch.dict(os.environ, target_env, clear=True):
        # Instantiate Settings to check reading from env
        settings = Settings()
        assert settings.TELEGRAM_BOT_TOKEN == "env_token"
        assert settings.DROPBOX_APP_KEY == "env_key"
        assert settings.DROPBOX_APP_SECRET == "env_secret"
        assert settings.DROPBOX_REFRESH_TOKEN == "env_refresh"
        assert settings.ADMIN_ID == 1001
