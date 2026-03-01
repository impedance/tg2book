# Deployment Guide for tg2book

This guide describes how to deploy the `tg2book` bot to a remote VPS (Virtual Private Server) using the production Docker stack.

## Prerequisites

1.  **VPS**: A server running Linux (Ubuntu/Debian recommended) with SSH access.
2.  **Docker**: Installed on the VPS.
    *   Command to check: `docker --version`
    *   If not installed, follow [official instructions](https://docs.docker.com/engine/install/ubuntu/) or run: `curl -fsSL https://get.docker.com | sh`
3.  **Git**: Installed on the VPS (`sudo apt update && sudo apt install git`).
4.  **Bot Tokens**: You will need your `.env` file content.

## Deployment Methods

### Method 1: Using Git via Manual Setup (Recommended)

1.  **SSH into your VPS**:
    ```bash
    ssh user@your-vps-ip
    ```

2.  **Clone the repository**:
    ```bash
    git clone https://github.com/impedance/tg2book.git
    cd tg2book
    ```

3.  **Create the environment file**:
    Create a `.env` file in the project directory:
    ```bash
    nano .env
    ```
    Paste the content from your local `.env` file (TELEGRAM_BOT_TOKEN, DROPBOX_* keys).
    Press `Ctrl+X`, then `Y`, then `Enter` to save.

4.  **Start the bot**:
    ```bash
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
    ```

## How to Update the Bot (CI/CD Manual Workflow)

When you make changes to the code (e.g., in `bot.py`):

1.  **On your Local Machine**:
    *   Commit and push changes to GitHub:
        ```bash
        git add .
        git commit -m "New features"
        git push origin main
        ```

2.  **On the VPS**:
    *   Pull the new code:
        ```bash
        cd tg2book
        git pull
        ```
    *   Rebuild and restart the container:
        ```bash
        docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
        ```
        *   `--build` ensures the Docker image is recreated with the new code.
        *   `-d` runs it in the background.

### Method 2: Manual Copy (SCP)

Use this if you don't want to use Git on the server.

1.  **Run this command from your LOCAL machine**:
    ```bash
    # Adjust the path and user@ip accordingly
    scp -r /home/spec/work/tg2book remote_user@remote_ip:~/tg2book
    ```

2.  **SSH into VPS and start**:
    ```bash
    ssh remote_user@remote_ip
    cd tg2book
    nano .env  # Paste secrets here
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
    ```

## Post-Deployment Checks

1.  **Check status**:
    ```bash
    docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
    ```
    Should show `tg2book` as `Up`.

2.  **Check logs**:
    ```bash
    docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=50
    ```
