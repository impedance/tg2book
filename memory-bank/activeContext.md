# Active Context

## Current Focus

Текущий фокус проекта уже не в проектировании userbot-интеграции, а в стабилизации и эксплуатации существующей связки:

1. `bot.py` как основной пользовательский вход.
2. `userbot_listener.py` как channel-ingestion sidecar.
3. SQLite-реестр `runtime/channels.db` и admin-команды для управления каналами.
4. Dropbox pipeline как критический delivery path.

## Current Reality

- В проекте уже есть internal processing seam:
  - `_process_text_to_dropbox(...)`
- Userbot уже подключён и вызывает:
  - `TelegramToEpub.process_channel_post(...)`
- Реестр каналов уже вынесен в:
  - `channel_registry.py`
- Есть baseline-тесты критического Dropbox pipeline:
  - `tests/test_dropbox_pipeline_baseline.py`

## Recent Changes

- Добавлен `userbot_listener.py` на Telethon.
- Добавлен SQLite-реестр каналов `channel_registry.py`.
- Добавлены admin-команды:
  - `/add_channel`
  - `/del_channel`
  - `/list_channels`
- Docker runtime сейчас состоит из двух сервисов:
  - `tg2book`
  - `tg2book-userbot`

## Next Steps

1. Проверить production bootstrap на VDS уже с `./runtime:/app/runtime`.
2. Добавить явную документацию по bootstrap Telethon session в Docker.
3. Закрыть пробел по media-only channel posts.
4. При необходимости отделить testing dependencies от runtime dependencies.

## Active Decisions and Considerations

- Основной pipeline `текст -> EPUB -> Dropbox -> summary` остаётся общим для bot и userbot.
- SQLite достаточно для реестра каналов; отдельная БД не нужна.
- Summary для channel ingestion отправляется админу по `ADMIN_ID`.
- Runtime state теперь закреплён через bind mount `./runtime:/app/runtime`, что снижает риск потери state при пересоздании контейнеров.
