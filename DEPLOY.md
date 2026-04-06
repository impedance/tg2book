# Деплой tg2book на VDS

Ниже описан актуальный сценарий деплоя для текущего состояния проекта: на сервере запускаются два контейнера, основной бот и userbot-listener.

## Что должно быть на сервере

- Linux VDS с SSH-доступом.
- Docker и Docker Compose plugin:
  - `docker --version`
  - `docker compose version`
- Git.
- Готовый `.env` с Telegram и Dropbox секретами.

## Что именно разворачивается

`docker-compose.yml` поднимает:

- `tg2book` — основной Telegram-бот.
- `tg2book-userbot` — Telethon userbot, который читает посты каналов.

Оба сервиса собираются из одного `Dockerfile`, но стартуют с разными командами.
Runtime state хранится через bind mount `./runtime:/app/runtime`.

## Обязательные секреты

Минимум для полного режима:

```dotenv
TELEGRAM_BOT_TOKEN=...
ADMIN_ID=123456789
API_ID=...
API_HASH=...
USERBOT_SESSION=tg2book_userbot
CHANNEL_REGISTRY_DB=channels.db
DROPBOX_APP_KEY=...
DROPBOX_APP_SECRET=...
DROPBOX_REFRESH_TOKEN=...
```

Для Docker можно вообще не задавать `USERBOT_SESSION` и `CHANNEL_REGISTRY_DB` в `.env`: compose по умолчанию направит их в `/app/runtime/tg2book_userbot` и `/app/runtime/channels.db`.

Если нужен только основной бот без userbot, `API_ID` и `API_HASH` можно не задавать, но тогда сервис `tg2book-userbot` запускать не надо.

## Первый деплой по SSH

1. Подключиться к серверу:

```bash
ssh user@your-vds
```

2. Клонировать проект:

```bash
git clone https://github.com/impedance/tg2book.git
cd tg2book
```

3. Создать `.env`:

```bash
nano .env
```

4. Собрать и поднять сервисы:

```bash
docker compose up -d --build
```

5. Проверить статус:

```bash
docker compose ps
docker compose logs -f --tail=100 tg2book
docker compose logs -f --tail=100 tg2book-userbot
```

## Если контейнер уже существует на сервере

Обычное обновление такое:

```bash
ssh user@your-vds
cd ~/tg2book
git pull
docker compose up -d --build
docker compose ps
```

Если менялся только Python-код, без зависимостей, чаще всего достаточно:

```bash
docker compose up -d
```

Но безопаснее для ручного релиза использовать `docker compose up -d --build`.

## Важный момент про Telethon session

`userbot_listener.py` использует Telethon session-файл. На практике есть два рабочих варианта:

### Вариант A. Авторизовать userbot прямо на сервере

1. Временно зайти в контейнер или запустить `python userbot_listener.py` локально на сервере.
2. Пройти интерактивную авторизацию по номеру телефона и коду.
3. Убедиться, что session-файл сохранился.
4. После этого обычный `docker compose up -d` сможет переиспользовать сессию.

Минус: session-файл должен переживать пересборки и быть доступным контейнеру.

### Вариант B. Подложить готовый session-файл

Если session уже создан локально, его можно перенести в runtime-директорию проекта:

```bash
scp tg2book_userbot.session user@your-vds:~/tg2book/runtime/
```

Текущий compose уже монтирует `~/tg2book/runtime` в контейнер, поэтому `.session` и `channels.db` переживают пересоздание контейнеров.

## Команды для повседневного управления

```bash
make build
make run
make logs
make test
```

Либо напрямую:

```bash
docker compose up -d --build
docker compose logs -f --tail=200
docker compose restart
docker compose down
```

## Что проверить после релиза

1. Бот отвечает на `/start`.
2. Админ-команда `/list_channels` отрабатывает без ошибки.
3. Добавление канала через `/add_channel testchannel` сохраняется.
4. Пересланное в бота текстовое сообщение уходит в Dropbox.
5. Если включён userbot, новый пост из зарегистрированного канала вызывает summary-сообщение админу.

## Типовые проблемы

- `TELEGRAM_BOT_TOKEN environment variable not set`
  - Не загружен `.env` или переменная не заполнена.
- `Не заданы API_ID/API_HASH для userbot`
  - Поднят `tg2book-userbot`, но в `.env` нет Telethon credentials.
- `ADMIN_ID должен быть числом`
  - В `.env` попал username вместо numeric Telegram user id.
- Ошибки Dropbox `401`, `Invalid token`
  - Проверить `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`.
- Userbot не стартует после rebuild
  - Обычно отсутствует `runtime/tg2book_userbot.session` или у контейнера нет прав на `runtime/`.
