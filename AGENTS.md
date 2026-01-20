# Repository Guidelines

## Memory Bank First
Always review the knowledge base in `memory-bank/*.md` before acting on this guide. Those files hold the canonical product vision, technical decisions, and in-flight priorities; refresh them whenever you open `AGENTS.md` so your work aligns with current context.

## Project Structure & Module Organization
Core bot logic lives in `bot.py`, delegating EPUB creation to `epub_functions.py` and Dropbox syncing to `dropbox_module.py`. Reusable scripts (`dropbox-loader.py`, `exchange_code.py`) support credential flow. Tests sit in `test_bot.py`, configs in `pytest.ini` and `requirements*.txt`, and operational notes under `memory-bank/`. The `start.sh` wrapper launches the bot with environment variables.

## Build, Test, and Development Commands
Всегда работайте в локальном виртуальном окружении: `python -m venv .venv`, затем `source .venv/bin/activate`. После активации устанавливайте зависимости `pip install -r requirements.txt`. Запускайте бота через `./start.sh` или `python bot.py`, когда заданы `TELEGRAM_BOT_TOKEN` и Dropbox секреты. Для загрузки файлов в Dropbox используйте `python dropbox-loader.py <local_path>`. Логи смотрите командой `tail -f bot.log`.

## Coding Style & Naming Conventions
Follow PEP 8: four-space indents, snake_case for functions, and CapWords for classes. Keep user-facing copy in Russian to match current responses. Prefer docstrings for public methods and concise logging with the shared `logger`. When touching filters or formatters, mirror existing naming such as `sanitize_filename` and reserve `create_*` for EPUB builders.

## Testing Guidelines
Pytest drives coverage; add new cases in modules named `test_*.py` and functions prefixed with `test_`. Reuse the async fixtures and mocks in `test_bot.py` to isolate Telegram and Dropbox dependencies. Run `pytest` for the suite, `pytest -k <keyword>` to focus, and `pytest --cov` before large refactors. Aim to exercise error paths and media handling branches, updating mocks if new integrations appear.

## Commit & Pull Request Guidelines
Commits are short, imperative phrases (e.g., `update naming`, `fix test`). Scope each commit to a logical change and include relevant tests. Pull requests should describe the bot behavior change, list test evidence (commands run or screenshots of EPUB output), and reference any product briefs in `memory-bank/`. Flag security-sensitive updates (tokens, Dropbox flow) so reviewers can double-check configuration.
