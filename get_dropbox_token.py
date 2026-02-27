#!/usr/bin/env python3
"""
Script to get Dropbox refresh token using OAuth2 flow
"""

import os
import webbrowser
from urllib.parse import parse_qs, urlparse

import requests


def get_dropbox_refresh_token():
    # Get credentials from .env
    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")

    if not app_key or not app_secret:
        print("Загрузите DROPBOX_APP_KEY и DROPBOX_APP_SECRET из .env файла")
        return

    # Step 1: Generate authorization URL
    auth_url = (
        f"https://www.dropbox.com/oauth2/authorize?"
        f"client_id={app_key}&"
        f"response_type=code&"
        f"token_access_type=offline"
    )

    print("1. Откройте эту ссылку в браузере:")
    print(f"{auth_url}")
    print()

    # Open browser automatically
    webbrowser.open(auth_url)

    # Step 2: Get authorization code from user
    redirect_url = input("2. После авторизации скопируйте полную URL страницу сюда: ")

    # Parse authorization code from redirect URL
    parsed_url = urlparse(redirect_url)
    query_params = parse_qs(parsed_url.query)

    if "code" not in query_params:
        print("Ошибка: не найден код авторизации в URL")
        return

    auth_code = query_params["code"][0]

    # Step 3: Exchange authorization code for tokens
    token_url = "https://api.dropbox.com/oauth2/token"
    data = {
        "code": auth_code,
        "grant_type": "authorization_code",
        "client_id": app_key,
        "client_secret": app_secret,
    }

    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        tokens = response.json()
        print("\n✅ Успешно получены токены:")
        print(f"Access Token: {tokens['access_token'][:20]}...")
        print(f"Refresh Token: {tokens['refresh_token']}")
        print("\nОбновите .env файл:")
        print(f"DROPBOX_REFRESH_TOKEN={tokens['refresh_token']}")
    else:
        print(f"❌ Ошибка получения токенов: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    # Load .env
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

    get_dropbox_refresh_token()
