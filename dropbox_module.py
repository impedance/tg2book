# This module contains functions for interacting with Dropbox.
import os
import subprocess
import logging
import requests

def refresh_access_token():
    """Refreshes the Dropbox access token."""
    url = "https://api.dropbox.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": os.getenv("DROPBOX_REFRESH_TOKEN")
    }
    response = requests.post(url, data=data, auth=(os.getenv("DROPBOX_APP_KEY"), os.getenv("DROPBOX_APP_SECRET")))
    return response.json()["access_token"]

def upload_to_dropbox(file_path):
    """Uploads a file to Dropbox."""
    try:
        # Refresh access token
        access_token = refresh_access_token()

        # Construct the upload command
        command = [
            "python3",
            "dropbox-loader.py",
            file_path,
            "'/Apps/Dropbox PocketBook/from-bot/'",
            "--access-token",
            access_token
        ]

        # Execute the command
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if stderr:
            logging.error(f"Dropbox upload failed: {stderr.decode()}")
            return False
        else:
            logging.info(f"Dropbox upload successful: {stdout.decode()}")
            return True

    except Exception as e:
        logging.error(f"Error uploading to Dropbox: {e}")
        return False
