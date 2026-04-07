# tg2book

`tg2book` это Telegram-бот и sidecar-userbot для доставки постов в PocketBook через Dropbox.

Проект сейчас состоит из двух независимых процессов:

- `bot.py`:
  - принимает пересланные сообщения и загруженные `.epub`,
  - умеет управлять списком каналов через `/add_channel`, `/del_channel`, `/list_channels`,
  - отправляет пользователю или админу короткий summary-ответ.
- `userbot_listener.py`:
  - слушает новые посты каналов через Telethon,
  - пропускает дальше только каналы из SQLite-реестра,
  - использует тот же pipeline `текст -> EPUB -> Dropbox`, что и основной бот.

## Что реально работает

- Пересланный текст или подпись -> генерация EPUB -> загрузка в Dropbox -> summary в Telegram.
- Загруженный `.epub` -> обратная отправка файла в Telegram -> синхронизация в Dropbox.
- Реестр отслеживаемых каналов в `runtime/channels.db`.
- Админ-команды:
  - `/add_channel <channel>`
  - `/del_channel <channel>`
  - `/list_channels`
- Userbot ingestion для текстовых постов из каналов.

## Ограничения текущей версии

- Userbot пока обрабатывает только посты, где есть текст.
- Media-only посты из каналов пропускаются.
- Dropbox остаётся обязательной частью delivery pipeline.
- `.env`, `runtime/`, `bot.log`, `userbot.log` являются runtime-артефактами и не должны коммититься.

## Структура проекта

- `bot.py` — основной Telegram-бот на `python-telegram-bot`.
- `userbot_listener.py` — Telethon-listener для каналов.
- `channel_registry.py` — SQLite-реестр каналов.
- `epub_functions.py` — сборка EPUB и обложки.
- `dropbox_module.py` — refresh токена и загрузка файла в Dropbox.
- `dropbox-loader.py` — низкоуровневый CLI uploader.
- `tests/` и `test_bot.py` — unit и baseline-тесты.
- `memory-bank/` — актуальный контекст, решения и статус проекта.
- `docs/tasks/` — рабочие плановые документы; это не всегда описание текущего production state.

## Переменные окружения

Обязательные для `bot.py`:

- `TELEGRAM_BOT_TOKEN`
- `DROPBOX_APP_KEY`
- `DROPBOX_APP_SECRET`
- `DROPBOX_REFRESH_TOKEN`

Обязательные для admin/userbot функциональности:

- `ADMIN_ID` — Telegram user id администратора, который получает summary от userbot и может управлять каналами.
- `API_ID` — Telegram API ID для Telethon.
- `API_HASH` — Telegram API hash для Telethon.

Опциональные:

- `USERBOT_SESSION` — путь без суффикса `.session` для Telethon, по умолчанию `/app/runtime/tg2book_userbot` в Docker и `tg2book_userbot` в локальном shell-режиме.
- `CHANNEL_REGISTRY_DB` — путь к SQLite базе, по умолчанию `/app/runtime/channels.db` в Docker и `channels.db` в локальном shell-режиме.

Пример `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=...
ADMIN_ID=123456789
API_ID=...
API_HASH=...
USERBOT_SESSION=/app/runtime/tg2book_userbot
CHANNEL_REGISTRY_DB=/app/runtime/channels.db
DROPBOX_APP_KEY=...
DROPBOX_APP_SECRET=...
DROPBOX_REFRESH_TOKEN=...
```

## Локальный запуск без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

Для отдельного userbot-процесса:

```bash
source .venv/bin/activate
./start_userbot.sh
```

Важно: при первом запуске `userbot_listener.py` Telethon попросит интерактивную авторизацию и создаст файл сессии.

## Docker

В `docker-compose.yml` сейчас два сервиса:

- `tg2book` -> `python bot.py`
- `tg2book-userbot` -> `python userbot_listener.py`

Оба сервиса монтируют `./runtime` с хоста в `/app/runtime` внутри контейнера. Там сохраняются:

- `channels.db`
- `tg2book_userbot.session`

Основные команды:

```bash
make build
make run
make logs
make test
make userbot-login
```

Что делают команды:

- `make build` — пересобирает и поднимает оба сервиса.
- `make run` — поднимает оба сервиса без принудительного rebuild.
- `make logs` — показывает логи обоих сервисов.
- `make test` — запускает `pytest` внутри контейнера `tg2book`.
- `make userbot-login` — одноразовая интерактивная авторизация Telethon и создание session в `runtime/`.

Если `runtime/tg2book_userbot.session` ещё нет, сервис `tg2book-userbot` не падает в цикл рестартов, а остаётся в idle-режиме и пишет в лог, что нужно выполнить `make userbot-login`.

## Проверка после старта

1. `docker compose ps`
2. `docker compose logs -f --tail=100 tg2book`
3. `docker compose logs -f --tail=100 tg2book-userbot`
4. В боте:
   - отправить `/list_channels`,
   - добавить тестовый канал,
   - переслать в бот сообщение с текстом,
   - проверить, что файл появился в Dropbox.

## Тесты

Локально:

```bash
source .venv/bin/activate
pytest
```

Ключевые наборы:

- `test_bot.py` — unit-level проверки handlers и shared pipeline.
- `tests/test_channel_registry.py` — SQLite registry.
- `tests/test_userbot_listener.py` — разбор channel events.
- `tests/test_dropbox_pipeline_baseline.py` — baseline проверка Dropbox pipeline.

## Получение Dropbox refresh token

1. Создать Dropbox App в https://www.dropbox.com/developers/apps
2. Открыть ссылку:

```text
https://www.dropbox.com/oauth2/authorize?client_id=YOUR_APP_KEY&response_type=code&token_access_type=offline
```

3. После авторизации обменять code:

```bash
python exchange_code.py YOUR_AUTHORIZATION_CODE
```

Скрипт ожидает, что `DROPBOX_APP_KEY` и `DROPBOX_APP_SECRET` уже доступны в окружении или `.env`.
