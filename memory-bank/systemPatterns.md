# System Patterns

## System Architecture

Система состоит из следующих компонентов:

- `bot.py`
  - Telegram Bot API polling process.
  - Обрабатывает пользовательские сообщения и admin-команды.
- `userbot_listener.py`
  - Telethon-based listener для channel posts.
  - Не делает свою доставку отдельно, а вызывает общий pipeline из `bot.py`.
- `channel_registry.py`
  - SQLite-backed storage для monitored channel identifiers.
- `epub_functions.py`
  - Генерация EPUB и текстовой cover PNG.
- `dropbox_module.py`
  - Refresh Dropbox access token и загрузка файла через `dropbox-loader.py`.

## Key Technical Decisions

- Не переписывать основной бот, а расширить его через shared internal seam.
- Использовать sidecar-userbot вместо замены основной bot-архитектуры.
- Считать Dropbox delivery критическим неизменяемым инвариантом.
- Хранить monitored channels в SQLite.

## Core Processing Paths

### Path 1. Forwarded/User Message

1. `bot.py` получает сообщение.
2. `handle_message()` извлекает текст, источник и ссылку.
3. Вызывается `_process_text_to_dropbox(...)`.
4. Создаётся EPUB.
5. EPUB загружается в Dropbox.
6. Пользователь получает summary reply.

### Path 2. Uploaded EPUB

1. `bot.py` получает документ `.epub`.
2. Временный файл скачивается из Telegram.
3. Файл отправляется обратно пользователю.
4. Те же байты загружаются в Dropbox.

### Path 3. Channel Post via Userbot

1. `userbot_listener.py` принимает `NewMessage`.
2. `parse_channel_post()` извлекает текст, source identifier и public link.
3. `process_channel_post()` проверяет, что канал есть в SQLite registry.
4. Для разрешённого канала вызывается `_process_text_to_dropbox(...)`.
5. Summary отправляется админу по `ADMIN_ID`.

## Design Patterns in Use

- Facade-like role: `TelegramToEpub` собирает message processing, EPUB generation и Dropbox upload.
- Shared internal seam: `_process_text_to_dropbox(...)` используется несколькими entry paths.
- Sidecar pattern: userbot живёт отдельным процессом рядом с основным ботом.

## Testing Approach

- Unit tests с моками для Telegram/Dropbox integration points.
- Black-box baseline tests для Dropbox delivery path.
- Отдельные тесты для SQLite registry normalization и listener parsing.

Критический regression target:

- не ломать путь `входное сообщение -> EPUB/EPUB bytes -> Dropbox`.
