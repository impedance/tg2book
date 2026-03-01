# Project Architecture and Documentation

**Target Audience:** AI Agents, LLM Coding Assistants, and Human Developers.
**Purpose:** Provides context on product requirements, high-level architecture, and technical decisions for the `tg2book` Telegram bot.

---

## 1. Product Specifications

### Core Product Description
A Telegram bot designed to convert Telegram posts and external web articles (from URLs within posts) into **EPUB** format. The generated EPUB files are automatically synchronized to a connected **Dropbox** account, allowing seamless integration with e-readers (e.g., PocketBook).

### Key Supported Use Cases

1. **Interactive Mode (Manual Forwarding & Text Input)**
   - **Trigger:** User forwards a text post from any channel/chat or sends direct text.
   - **Action:** Bot extracts text and URLs, converts content to EPUB, sends the file back to the user via Telegram, and uploads it to Dropbox.

2. **Direct EPUB File Uploads**
   - **Trigger:** User sends a pre-generated `.epub` document.
   - **Action:** Bot downloads the file, sanitizes the filename, syncs it to Dropbox, and replies with a success confirmation.

3. **Auto-Forwarding (Channel Monitoring)**
   - **Trigger:** A new post is published in one of the monitored channels.
   - **Action:** The Bot utilizes a secondary MTProto **Userbot** client to read messages (including from private channels). Post is converted to EPUB, synced to Dropbox, and a summary report is sent to the configured `ADMIN_ID`.

4. **Admin Subscription Management**
   - **Trigger:** Admin issues bot commands (`/add_channel`, `/del_channel`, `/list_channels`).
   - **Action:** Bot updates the monitored channels database (`SQLite`) and the in-memory cache dynamically without requiring a restart.

---

## 2. High-Level Architecture

The system is built on the **Pyrogram** framework utilizing Python's `asyncio` for high concurrency and non-blocking operations.

### Component Layers

1. **Client / Input Layer**
   - **Standard Bot API Client:** Handles direct user interactions (commands, direct messages, file uploads) via the standard bot token.
   - **MTProto Userbot Client:** Authorized via a user session string. Monitors explicitly defined channels using a custom Pyrogram `filter`. Passes incoming messages to the orchestration queue.

2. **Orchestration & Queue Layer**
   - Implements a *Producer-Consumer* pattern (`asyncio.Queue`).
   - The Userbot (Producer) pushes incoming posts to the queue.
   - A background worker (`_channel_worker`) consumes events sequentially. This manages traffic spikes and prevents rate limits/bans from Dropbox and EPUB generation constraints by limiting concurrency to `1`.

3. **Business Logic / Services Layer**
   - **`epub_service.py`:** The main coordinator. Orchestrates parsing, EPUB generation, and Dropbox uploads. Offloads blocking synchronous operations to thread pools using `asyncio.to_thread()`.
   - **`parser_service.py`:** Extracts URLs. Uses `requests` and `BeautifulSoup4` to fetch external pages, falling back to core content tags (`<article>`, `<body>`), while stripping out scripts and repetitive navigation elements.
   - **`epub_functions.py`:** A custom, low-level, zero-dependency EPUB generator. It builds a valid EPUB 3 structure from scratch using Python's built-in `zipfile` and `xml.sax.saxutils`. It also dynamically generates an SVG cover image (`<svg>`) for the book instead of using external image libraries like `Pillow`.
   - **`dropbox_module.py`:** A custom, lightweight HTTP client for the Dropbox API v2.
   - **`utils/text_utils.py`:** Provides basic text sanitization, emoji stripping (for safe filenames), and primitive HTML paragraph formatting (`<p>`, `<br>`).

4. **Data Access Layer**
   - **`userbot_db.py`:** Local SQLite database powered by `aiosqlite`. Stores the `username` or numerical IDs of channels tracked by the Userbot.

---

## 3. Design Principles & Technical Decisions

### 3.1. Dual Pyrogram Clients (Single Event Loop)
- **Decision:** The project avoids mixing different Telegram frameworks (e.g., dropping `python-telegram-bot`) in favor of using **Pyrogram strictly for both clients**.
- **Agent Context:** Both `bot` and `userbot` share a single `asyncio` event loop. This significantly reduces resource overhead, ensures code consistency, and simplifies concurrent programming state (e.g., shared variables natively).

### 3.2. Asynchronous I/O vs Blocking I/O Isolation
- **Decision:** Pyrogram and `aiosqlite` rely entirely on `async/await`. However, HTML parsing (`BeautifulSoup`), EPUB compiling (File I/O), and HTTP transfers (`requests` to Dropbox) are natively synchronous.
- **Agent Context:** All synchronous functions that take time are strictly offloaded using `asyncio.to_thread()`. *AI Agents should preserve this pattern when adding new heavy processing logic.*

### 3.3. In-Memory Database Caching
- **Decision:** Fast-path chat filters use RAM instead of Disk I/O.
- **Agent Context:** The Userbot receives *all* incoming messages. Executing an SQLite query on every message is an I/O bottleneck. Instead, the channel list is loaded `userbot_db.sqlite` -> `self._monitored_channels_cache` (Python `set`) on startup. The Pyrogram custom filter checks this cache in `O(1)` time. 

### 3.4. SQLite Optimization (WAL Mode)
- **Decision:** `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;` are explicitly enabled in the init phase.
- **Agent Context:** Crucial for `aiosqlite` to prevent `database is locked` exceptions during concurrent read/write states between the Bot handling Admin commands and the Userbot.

### 3.5. Zero-Dependency & Lightweight Philosophy
- **Decision:** Heavy libraries like `ebooklib`, `lxml`, `Pillow`, and the official `dropbox` SDK have been explicitly removed from the project.
- **Agent Context:** 
  - **Dropbox** integration is implemented via direct HTTP calls to Content API v2 via `requests`. 
  - **EPUB** generation leverages the standard `zipfile` library and dynamic SVG covers (`epub_functions.py`), drastically reducing container size and memory usage. Keep this minimal approach if extending capabilities.

### 3.6. Infrastructure & Docker Optimization
- **Decision:** The bot runs in a highly restricted `python:3.11-slim` Docker container.
- **Agent Context:** `docker-compose.yml` explicitly sets strict resource limits (`mem_limit: 768m`, `cpus: 0.75`). System-level build dependencies (like `gcc`, `libjpeg-dev`) are absent because pure-Python solutions are used instead. Ensure any new Python packages added do not require compilation of C-extensions unless absolutely necessary.

### 3.7. QR Code Userbot Authorization
- **Decision:** TTY-less authentication. 
- **Agent Context:** Since the bot runs in a headless Docker environment, traditional CLI-based phone number login fails. Authentication is solved with `login_qr.py`, outputting a session string that is added to `.env`. `qrcode[pil]` should remain an optional/side dependency, not in the core `requirements.txt`.

### 3.8. Session Robustness & Cache Syncing
- **Decision:** Mitigation for Telegram's `Peer id invalid` API Error.
- **Agent Context:** The Userbot cannot forward or interact with channels lacking local peers. A background task `_dialogs_sync_worker` periodically fetches `get_dialogs()` to refresh Pyrogram's internal SQLite session cache, preserving stability for auto-forwarding from newly joined private channels.
