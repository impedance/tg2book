"""
dropbox_module.py — Dropbox uploader via direct HTTP (no SDK, no subprocess).

Uses only `requests` (already a dependency) and stdlib.
"""

import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

_DROPBOX_FOLDER = "/Apps/Dropbox PocketBook/from-bot/"
_TOKEN_URL = "https://api.dropbox.com/oauth2/token"
_UPLOAD_URL = "https://content.dropboxapi.com/2/files/upload"

CONNECT_TIMEOUT = 5   # seconds to establish a TCP connection
READ_TIMEOUT = 30     # seconds to wait for the server to send data


def redact_access_token(text: str) -> str:
    """Redact access token value from log strings."""
    return re.sub(r'"access_token":\s*"[^"]+"', '"access_token": "***"', text)


def refresh_access_token() -> str | None:
    """Obtain a short-lived access token via OAuth2 refresh-token grant.

    Returns the token string on success, or *None* on failure.
    """
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")

    try:
        response = requests.post(
            _TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(app_key, app_secret),
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except requests.exceptions.Timeout:
        logger.error(
            "Dropbox token refresh timed out (connect=%ss, read=%ss).",
            CONNECT_TIMEOUT,
            READ_TIMEOUT,
        )
        return None
    except Exception as exc:
        logger.error("Failed to request Dropbox token: %s", exc)
        return None

    if response.status_code == 200:
        token = response.json().get("access_token")
        logger.info("Dropbox access token refreshed successfully.")
        return token

    logger.error("Dropbox token refresh failed: HTTP %s", response.status_code)
    return None


def upload_to_dropbox(file_path: str, custom_filename: str | None = None) -> bool:
    """Upload *file_path* to the configured Dropbox folder.

    Uses the Dropbox Content API v2 directly via HTTP — no subprocess,
    no Dropbox SDK.  Returns True on success, False on any failure.
    """
    logger.info("Starting Dropbox upload: %s", file_path)

    if not os.path.exists(file_path):
        logger.error("Local file does not exist: %s", file_path)
        return False

    file_size = os.path.getsize(file_path)
    logger.info("File size: %d bytes", file_size)

    access_token = refresh_access_token()
    if not access_token:
        logger.error("Cannot obtain access token — aborting upload.")
        return False

    filename = custom_filename if custom_filename else os.path.basename(file_path)
    dropbox_path = _DROPBOX_FOLDER + filename
    logger.info("Uploading to Dropbox path: %s", dropbox_path)

    api_arg = json.dumps(
        {
            "path": dropbox_path,
            "mode": "overwrite",
            "autorename": False,
            "mute": False,
        }
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": api_arg,
    }

    try:
        with open(file_path, "rb") as fh:
            data = fh.read()

        response = requests.post(
            _UPLOAD_URL,
            headers=headers,
            data=data,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except requests.exceptions.Timeout:
        logger.error(
            "Dropbox upload timed out (connect=%ss, read=%ss).",
            CONNECT_TIMEOUT,
            READ_TIMEOUT,
        )
        return False
    except Exception as exc:
        logger.error("Error during Dropbox HTTP upload: %s", exc)
        return False

    if response.status_code == 200:
        logger.info("Dropbox upload succeeded.")
        return True

    logger.error("Dropbox upload failed: HTTP %s — %s", response.status_code, response.text[:200])
    return False


def manual_upload(file_path: str) -> None:
    """CLI helper: upload a file and print result to stdout."""
    success = upload_to_dropbox(file_path)
    if success:
        logger.info("Manual upload for %s completed successfully.", file_path)
    else:
        logger.error("Manual upload for %s failed.", file_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload a file to Dropbox.")
    parser.add_argument("file_path", help="Path to the local file.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    manual_upload(args.file_path)