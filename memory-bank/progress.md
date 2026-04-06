# Progress

## What Works

- Основной Telegram-бот отвечает на `/start` и `/help`.
- Пересланные текстовые сообщения и подписи обрабатываются через общий EPUB pipeline.
- Загруженные `.epub` документы отправляются обратно пользователю и синхронизируются в Dropbox.
- Dropbox upload path используется как для text-to-EPUB, так и для direct-EPUB сценария.
- Реестр отслеживаемых каналов хранится в SQLite через `channel_registry.py`.
- Admin-команды `/add_channel`, `/del_channel`, `/list_channels` реализованы.
- `userbot_listener.py` принимает channel posts и маршрутизирует их в shared processing seam.
- Есть baseline и unit-тесты для bot, channel registry, userbot listener и Dropbox pipeline.

## What Is Still Weak

- Нет поддержки channel posts без текста.
- Runtime state уже вынесен в bind mount `./runtime`.
- В `requirements.txt` смешаны runtime и test dependencies.
- Docker bootstrap Telethon session пока требует ручной операционной дисциплины.

## Current Status

Проект находится в рабочем состоянии для bot + userbot схемы.
Основной риск сместился с разработки функциональности на эксплуатационную надёжность деплоя и сохранность runtime state.

## Known Issues

- Потеря Telethon session после неудачного обновления может остановить `tg2book-userbot`.
- При отсутствии `ADMIN_ID`, `API_ID` или `API_HASH` userbot не стартует.
- Media-only channel posts пропускаются намеренно.
- Dropbox по-прежнему является single delivery dependency.

## Evolution of Project Decisions

- Сохранили `python-telegram-bot` как основной пользовательский интерфейс.
- Userbot добавили как sidecar вместо крупного архитектурного переписывания.
- Критический pipeline вынесли в общий метод `_process_text_to_dropbox(...)`.
- Для списка каналов выбрали SQLite, а не env-based конфиг.

## 2024-06-18 - Initial Implementation

- Создан основной Telegram to EPUB bot.
- Реализованы `/start`, `/help`, обработка forwarded messages и базовая генерация EPUB.

## 2025-05-14 - EPUB Generation Refinements

- Обновлена логика генерации EPUB.
- Добавлена текстовая cover PNG.
- Сохранён минималистичный single-content spine.

## 2026-04-05 - Shared Pipeline, Channel Registry, Userbot Path

### Implemented

- Общий processing seam для text-to-EPUB доставки.
- SQLite registry для monitored channels.
- Admin-команды управления каналами.
- `userbot_listener.py` на Telethon.
- Baseline black-box тесты Dropbox pipeline.

### Next Steps

1. Добавить более явный bootstrap/restore сценарий для Telethon session.
2. Проверить VDS deploy c bind-mounted `runtime/`.
3. Расширить channel ingestion на media-only кейсы при сохранении текущей Dropbox-гарантии.
