#!/usr/bin/env python3
import os
import requests
import sys

# Load .env
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

if len(sys.argv) != 2:
    print("Использование: python3 exchange_code.py YOUR_AUTH_CODE")
    sys.exit(1)

auth_code = sys.argv[1]
app_key = os.getenv('DROPBOX_APP_KEY')
app_secret = os.getenv('DROPBOX_APP_SECRET')

token_url = 'https://api.dropbox.com/oauth2/token'
data = {
    'code': auth_code,
    'grant_type': 'authorization_code',
    'client_id': app_key,
    'client_secret': app_secret
}

response = requests.post(token_url, data=data)

if response.status_code == 200:
    tokens = response.json()
    refresh_token = tokens['refresh_token']
    
    # Read current .env file
    env_lines = []
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            env_lines = f.readlines()
    
    # Update or add DROPBOX_REFRESH_TOKEN
    updated = False
    for i, line in enumerate(env_lines):
        if line.startswith('DROPBOX_REFRESH_TOKEN='):
            env_lines[i] = f'DROPBOX_REFRESH_TOKEN={refresh_token}\n'
            updated = True
            break
    
    if not updated:
        env_lines.append(f'DROPBOX_REFRESH_TOKEN={refresh_token}\n')
    
    # Write back to .env
    with open('.env', 'w') as f:
        f.writelines(env_lines)
    
    print(f"✅ Refresh Token получен и записан в .env: {refresh_token[:20]}...")
    print("Теперь можете запускать бота!")
else:
    print(f"❌ Ошибка: {response.status_code}")
    print(response.text)