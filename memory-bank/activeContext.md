# Active Context

## Current Focus

Текущий фокус смещён на итеративный план интеграции userbot:

1. Зафиксировать baseline существующего pipeline:
   - `сообщение -> EPUB -> Dropbox -> ответ пользователю`.
2. Добавлять userbot-часть только после усиления тестовой защиты Dropbox-пути.

## Recent Changes

- Подготовлен план поэтапной интеграции в `docs/tasks/userbot_iterative_integration_plan.md`.
- В Phase 0 добавлен аудит текущих тестов: `docs/tasks/phase0_test_audit.md`.
- Добавлен baseline набор black-box тестов Dropbox pipeline:
  - `tests/test_dropbox_pipeline_baseline.py`.

## Next Steps

1. Закрыть Phase 0 (подтвердить прохождение baseline-тестов).
2. Перейти к Phase 1: минимальный internal seam в `bot.py` для повторного использования pipeline.
3. После этого — Phase 2: SQLite-реестр каналов.

## Active Decisions and Considerations

- Основной `python-telegram-bot` pipeline сохраняется без архитектурной замены.
- Любые userbot-изменения делаются аддитивно, через общий internal processing path.
- Dropbox-путь считается критическим и должен быть защищён отдельными baseline-тестами.
