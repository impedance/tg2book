# This module contains functions for interacting with Dropbox.
import os
import subprocess
import logging
import requests
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import re

def redact_access_token(text):
    """Redacts the access token from the given text."""
    return re.sub(r'"access_token": ".*?"', '"access_token": "..."', text)

def refresh_access_token():
    """Refreshes the Dropbox access token."""
    url = "https://api.dropbox.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": os.getenv("DROPBOX_REFRESH_TOKEN")
    }
    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")

    logging.info("DROPBOX_APP_KEY: {}".format(app_key))
    logging.info("DROPBOX_APP_SECRET: {}".format(app_secret))
    logging.info("DROPBOX_REFRESH_TOKEN: {}".format(os.getenv("DROPBOX_REFRESH_TOKEN")))

    logging.info("Requesting new access token from Dropbox...")
    response = requests.post(url, data=data, auth=(app_key, app_secret))
    logging.info(f"Dropbox API response: {response.status_code} - {redact_access_token(response.text)}")
    if response.status_code == 200:
        access_token = response.json()["access_token"]
        logging.info("Successfully obtained access token.")
        return access_token
    else:
        logging.error(f"Failed to refresh access token: {response.status_code} - {response.text}")
        return None

def upload_to_dropbox(file_path):
    """Uploads a file to Dropbox."""
    try:
        # Refresh access token
        logging.info("Refreshing access token...")
        access_token = refresh_access_token()

        if not access_token:
            logging.error("Failed to obtain access token. Aborting upload.")
            return False

        logging.info(f"Access token: {access_token[:3] + '...' if access_token else access_token}")

        # Construct the upload command
        logging.info("Constructing upload command...")
        # Redact access token in log
        redacted_token = access_token[:3] + "..." if access_token else access_token
        command = [
            "python3",
            "dropbox-loader.py",
            file_path,
            "'/Apps/Dropbox PocketBook/from-bot/'",
            "--access-token",
            access_token
        ]
        logging.info(f"Upload command: {command[:5] + [redacted_token]}")

        # Execute the command
        logging.info("Executing upload command...")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("Upload command executed.")
        stdout, stderr = process.communicate()

        logging.info(f"Stdout: {stdout.decode()}")
        logging.info(f"Stderr: {stderr.decode()}")

        if stderr:
            logging.error(f"Dropbox upload failed.")
            return False
        else:
            logging.info(f"Dropbox upload successful.")
            return True

    except Exception as e:
        logging.error(f"Error uploading to Dropbox: {e}. Access token may be invalid.")
        return False

def manual_upload(file_path):
    """Manually triggers a Dropbox upload and displays logs."""
    logging.info(f"Starting manual upload for: {file_path}")
    success = upload_to_dropbox(file_path)
    if success:
        logging.info(f"Manual upload for {file_path} completed successfully.")
    else:
        logging.error(f"Manual upload for {file_path} failed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manually upload a file to Dropbox.")
    parser.add_argument("file_path", help="The path to the file to upload.")
    args = parser.parse_args()

    manual_upload(args.file_path)
