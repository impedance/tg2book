# RUNBOOK: tg2book

## Рантайм-артефакты

Во время работы проекта появляются:

- `.env`
- `runtime/channels.db`
- `runtime/tg2book_userbot.session`
- `bot.log`
- `userbot.log`

Их нельзя терять при обновлениях, если нужен непрерывный runtime state.

## Базовые операции

Сборка и запуск:

```bash
make build
make run
```

Просмотр логов:

```bash
make logs
make logs-bot
make logs-userbot
```

Тесты:

```bash
make test
```

Прямые docker compose команды:

```bash
docker compose ps
docker compose up -d --build
docker compose up -d tg2book tg2book-userbot
docker compose restart
docker compose down
```

## Какие сервисы должны быть запущены

- `tg2book`
- `tg2book-userbot`

Если userbot не нужен, можно поднимать только основной бот:

```bash
docker compose up -d tg2book
```

## Операционные проверки

После старта:

```bash
docker compose ps
docker compose logs -f --tail=100 tg2book
docker compose logs -f --tail=100 tg2book-userbot
```

Ожидаемое поведение:

- `tg2book` не падает сразу после старта.
- `tg2book-userbot` не падает на проверке env и session.
- В логах нет повторяющихся ошибок авторизации Telegram/Dropbox.

## Рабочий сценарий администратора

1. Открыть диалог с ботом.
2. Проверить `/list_channels`.
3. Добавить канал:

```text
/add_channel testchannel
```

Поддерживаются:

- `@username`
- `https://t.me/username`
- numeric channel id вида `-100...`

4. Убедиться, что канал появился в `/list_channels`.
5. Дождаться нового текстового поста в канале и проверить summary у администратора.

## Диагностика

Войти в контейнер:

```bash
docker compose exec tg2book sh
docker compose exec tg2book-userbot sh
```

Запустить тесты вручную:

```bash
docker compose exec tg2book pytest
```

Посмотреть содержимое runtime state:

```bash
ls -la runtime
```

Особенно проверить наличие:

- `runtime/channels.db`
- `runtime/tg2book_userbot.session`
- `runtime/` должен существовать на хосте до первого production-запуска.

## Частые инциденты

### Основной бот не стартует

Проверить:

- `TELEGRAM_BOT_TOKEN` в `.env`
- логи `tg2book`

Типичный симптом:

```text
TELEGRAM_BOT_TOKEN environment variable not set
```

### Userbot падает сразу после старта

Проверить:

- `API_ID`
- `API_HASH`
- `ADMIN_ID`
- наличие Telethon session-файла

Типичные симптомы:

- `Не заданы API_ID/API_HASH для userbot`
- `ADMIN_ID должен быть числом`

### Канал добавлен, но посты не обрабатываются

Проверить:

- канал точно есть в `/list_channels`
- идентификатор нормализован корректно
- пост содержит текст
- userbot действительно видит этот канал и имеет к нему доступ

Важно: media-only посты сейчас пропускаются по дизайну.

### EPUB создаётся, но Dropbox не принимает файл

Проверить:

- `DROPBOX_APP_KEY`
- `DROPBOX_APP_SECRET`
- `DROPBOX_REFRESH_TOKEN`
- сетевой доступ до Dropbox API

Типичные симптомы:

- `Failed to refresh access token`
- `Загрузка в Dropbox не удалась`

### После обновления пропал runtime state

Потеряны или перезаписаны:

- `runtime/tg2book_userbot.session`
- `runtime/channels.db`

Это операционный риск текущей схемы. Для production-режима лучше вынести эти файлы в volume или bind mount.
Текущая схема уже использует bind mount `./runtime:/app/runtime`; если state пропал, значит был потерян сам каталог `runtime/` на хосте или изменились права доступа.
