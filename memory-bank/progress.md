# Progress

## What Works

*   Basic bot functionality is implemented and working.
*   Core commands (start, help) are functional.
*   Forwarded message handling is implemented.
*   EPUB generation from forwarded messages works.
*   Direct EPUB upload flow is implemented.
*   Dropbox upload integration is wired in both text and direct EPUB paths.
*   Basic test suite with pytest is in place.

## What's Left to Build

*   Userbot listener for channel ingestion (iterative rollout).
*   Persistent channel registry (SQLite).
*   Admin commands for channel management (`/add_channel`, `/del_channel`, `/list_channels`).
*   Simulated channel-post ingestion seam before real userbot activation.
*   Enhanced formatting options and media handling improvements (outside first userbot iteration).

## Current Status

Проект находится в начале userbot-интеграции по фазам.
На текущем этапе усиливается тестовая защита существующего Dropbox pipeline (Phase 0).

## Known Issues

*   Нет поддержки media-only сценариев в userbot потоке (ещё не реализован).
*   Ограниченные возможности форматирования EPUB.
*   Нужна более строгая baseline-проверка Dropbox пути перед архитектурными изменениями.

## Evolution of Project Decisions

*   Using Python for backend development due to its extensive libraries.
*   Using `python-telegram-bot` for Telegram API integration.
*   Using `ebooklib` for EPUB file generation.
*   Using temporary directories for file operations to ensure proper cleanup.

## 2024-06-18 - Initial Implementation

- Created a project structure for the Telegram to EPUB bot
- Implemented core functionality:
  - Start command
  - Help command
  - EPUB creation from forwarded messages
  - Handling different types of forwarded origins (user, chat, hidden_user)
  - Basic error handling
- Used python-telegram-bot for Telegram API integration
- Used ebooklib for EPUB file generation
- Set up test infrastructure with pytest

## 2025-05-14 - EPUB Structure Optimization

### Implemented
- Added analysis phase for EPUB structure:
  - Verified EpubHtml parameters
  - Audited spine/navigation structure
- Prepared refactoring plan:
  - Content unification strategy
  - HTML cleanup requirements

### Next Steps
1. Code modifications:
   - Merge title and content in create_epub method (lines 47-54)
   - Remove duplicate HTML tags
   - Adjust section metadata

2. Validation steps:
   - Generate test EPUB files
   - Verify in Calibre, Apple Books, FBReader
   - Run epubcheck 4.2.6 validation

3. Additional improvements:
   - CSS normalization
   - Whitespace optimization in generated HTML

## 2026-04-05 - Userbot Iterative Plan Kickoff (Phase 0)

### Implemented
- Зафиксирован фазовый план интеграции userbot:
  - `docs/tasks/userbot_iterative_integration_plan.md`
- Добавлен аудит существующих тестов:
  - `docs/tasks/phase0_test_audit.md`
- Добавлен baseline black-box модуль для Dropbox pipeline:
  - `tests/test_dropbox_pipeline_baseline.py`
  - Сценарии:
    - текстовое сообщение -> генерация EPUB -> загрузка в Dropbox;
    - входной `.epub` -> загрузка точных байтов в Dropbox;
    - сбой Dropbox -> ошибка наблюдаема в логах, бот остаётся responsive.

### Next Steps
1. Закрыть верификацию Phase 0 прогонами baseline-тестов.
2. Перейти к Phase 1: выделение internal processing seam в `bot.py`.
