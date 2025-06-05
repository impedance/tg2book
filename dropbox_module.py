# This module contains functions for interacting with Dropbox.
import os
import subprocess
import logging
import requests
import argparse
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

    response = requests.post(url, data=data, auth=(app_key, app_secret))
    
    if response.status_code == 200:
        access_token = response.json()["access_token"]
        return access_token
    else:
        logging.error(f"Failed to refresh access token: {response.status_code}")
        return None

def upload_to_dropbox(file_path):
    """Uploads a file to Dropbox."""
    try:
        logging.info(f"Начинаем загрузку файла: {file_path}")
        
        # Проверяем существование локального файла
        if not os.path.exists(file_path):
            logging.error(f"Локальный файл не существует: {file_path}")
            return False
        
        file_size = os.path.getsize(file_path)
        logging.info(f"Размер файла: {file_size} байт")

        # Refresh access token
        logging.info("Получаем access token...")
        access_token = refresh_access_token()

        if not access_token:
            logging.error("Failed to obtain access token. Aborting upload.")
            return False

        logging.info("Access token получен успешно")

        # Формируем путь в Dropbox (добавляем имя файла к папке)
        filename = os.path.basename(file_path)
        dropbox_folder = "/Apps/Dropbox PocketBook/from-bot/"
        dropbox_full_path = dropbox_folder + filename
        
        logging.info(f"Локальный файл: {file_path}")
        logging.info(f"Папка в Dropbox: {dropbox_folder}")
        logging.info(f"Полный путь в Dropbox: {dropbox_full_path}")

        # Construct the upload command
        command = [
            "python3",
            "dropbox-loader.py",
            file_path,
            dropbox_full_path,
            "--access-token",
            access_token
        ]
        
        # Логируем команду (без токена)
        safe_command = command.copy()
        safe_command[-1] = "***HIDDEN***"
        logging.info(f"Команда для выполнения: {safe_command}")

        # Execute the command
        logging.info("Выполняем команду загрузки...")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        # Decode bytes to string if needed
        if isinstance(stdout, bytes):
            stdout = stdout.decode()
        if isinstance(stderr, bytes):
            stderr = stderr.decode()

        logging.info(f"Stdout: {stdout.strip()}")
        if stderr:
            logging.error(f"Stderr: {stderr.strip()}")
            return False
        else:
            logging.info(f"Dropbox upload completed successfully")
            return True

    except Exception as e:
        logging.error(f"Error uploading to Dropbox: {e}")
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