"""
Black-box tests for architecture optimizations.

Plan reference: docs/architecture_optimization_plan.md

Test 3 (§2.1): Изоляция CPU — бот отвечает мгновенно, пока EPUB обрабатывается в фоне.
Test 4 (§3.1): WAL-режим SQLite — ни одна из 10 конкурентных задач не падает с "database is locked".
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out heavy optional dependencies before importing bot / userbot_db
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))


class _MockModule:
    pass


if "telegram" not in sys.modules:
    _tg = _MockModule()
    _tg.Update = MagicMock
    _tg.Message = MagicMock
    _tg_ext = _MockModule()
    _tg_ext.Application = MagicMock
    _tg_ext.CommandHandler = MagicMock
    _tg_ext.MessageHandler = MagicMock
    _tg_ext.ContextTypes = MagicMock
    _tg_ext.ContextTypes.DEFAULT_TYPE = MagicMock
    _tg_ext.filters = MagicMock()
    _tg_ext.filters.ALL = MagicMock()
    sys.modules["telegram"] = _tg
    sys.modules["telegram.ext"] = _tg_ext

if "pyrogram" not in sys.modules:
    _pyro = _MockModule()
    _pyro.Client = MagicMock
    _pyro_filters = MagicMock()
    _pyro_filters.channel = MagicMock()
    _pyro.filters = _pyro_filters
    _pyro_types = MagicMock()
    _pyro_types.BotCommand = MagicMock
    _pyro.types = _pyro_types
    sys.modules["pyrogram"] = _pyro
    sys.modules["pyrogram.filters"] = _pyro_filters
    sys.modules["pyrogram.types"] = _pyro_types


import userbot_db  # noqa: E402
from bot import TelegramToEpub, _QueueItem  # noqa: E402

# ===========================================================================
# Тест 4 (план §3.1) — WAL: параллельные чтение и запись без "database is locked"
# ===========================================================================


@pytest.mark.asyncio
async def test_concurrent_db_no_locked_error(tmp_path):
    """
    10 конкурентных задач: половина пишет (add_channel), вторая читает (get_channels).
    Ни одна не должна упасть с OperationalError("database is locked").
    """
    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "wal_test.sqlite"
    await userbot_db.init_db()  # включает WAL-режим

    errors = []

    async def writer(i: int):
        try:
            await userbot_db.add_channel(f"channel_{i}")
        except Exception as e:
            errors.append(f"writer {i}: {e}")

    async def reader():
        try:
            await userbot_db.get_channels()
        except Exception as e:
            errors.append(f"reader: {e}")

    tasks = [writer(i) for i in range(5)] + [reader() for _ in range(5)]
    await asyncio.gather(*tasks)

    userbot_db.DB_PATH = original_path

    assert not errors, "Конкурентные запросы упали с ошибками:\n" + "\n".join(errors)


# ===========================================================================
# Тест 4b — WAL активирован: PRAGMA journal_mode возвращает 'wal'
# ===========================================================================


@pytest.mark.asyncio
async def test_wal_mode_is_enabled(tmp_path):
    """
    После init_db() база должна работать в WAL-режиме.
    """
    import aiosqlite

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "wal_check.sqlite"
    await userbot_db.init_db()

    async with aiosqlite.connect(userbot_db.DB_PATH) as db:
        async with db.execute("PRAGMA journal_mode;") as cursor:
            row = await cursor.fetchone()
    mode = row[0] if row else ""

    userbot_db.DB_PATH = original_path

    assert mode == "wal", f"Ожидался WAL-режим, получен: {mode!r}"


# ===========================================================================
# Тест 3 (план §2.1) — CPU изоляция: event loop не блокируется во время EPUB
# ===========================================================================


@pytest.mark.asyncio
async def test_epub_processing_does_not_block_event_loop(tmp_path):
    """
    Пока 3 «тяжёлых» EPUB-задачи обрабатываются в фоне (имитация через asyncio.sleep),
    вызов converter.start() должен завершиться мгновенно (< 0.5 сек).
    """
    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "cpu_test.sqlite"
    await userbot_db.init_db()

    converter = TelegramToEpub()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    # Имитируем долгую обработку EPUB (3 сек каждая задача)
    async def slow_epub(text, source, link):
        await asyncio.sleep(3.0)
        return "<b>Done</b>"

    with patch("services.epub_service.process_text_to_epub", side_effect=slow_epub):
        # Запускаем воркер и кладём в очередь 3 задачи
        worker_task = asyncio.create_task(converter._channel_worker())

        for i in range(3):
            item = _QueueItem(
                text=f"Текст {i}",
                source_name="TestChannel",
                post_link="https://t.me/test/1",
                reply_chat_id=42,
                bot=mock_bot,
            )
            await converter.processing_queue.put(item)

        # Вызов команды /start должен выполниться немедленно
        message = MagicMock()
        message.reply = AsyncMock()
        client = MagicMock()

        t0 = asyncio.get_event_loop().time()
        await converter.cmd_start(client, message)
        elapsed = asyncio.get_event_loop().time() - t0

        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    userbot_db.DB_PATH = original_path

    assert elapsed < 0.5, f"converter.cmd_start() заняло {elapsed:.3f}с — event loop заблокирован!"
    message.reply.assert_called_once()


# ===========================================================================
# Тест 3b — воркер корректно вызывает task_done() даже при исключении
# ===========================================================================


@pytest.mark.asyncio
async def test_worker_calls_task_done_on_exception(tmp_path):
    """
    Если обработка EPUB выбросила исключение, воркер:
    - логирует ошибку
    - вызывает task_done()
    - продолжает работу (не падает целиком)
    """
    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "worker_test.sqlite"
    await userbot_db.init_db()

    converter = TelegramToEpub()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    call_count = 0

    async def failing_epub(text, source, link):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Симуляция ошибки EPUB")
        return "<b>OK</b>"

    with patch("services.epub_service.process_text_to_epub", side_effect=failing_epub):
        worker_task = asyncio.create_task(converter._channel_worker())

        # Кладём 2 задачи: первая упадёт, вторая должна обработаться
        for i in range(2):
            item = _QueueItem(
                text=f"Текст {i}",
                source_name="Chan",
                post_link="",
                reply_chat_id=42,
                bot=mock_bot,
            )
            await converter.processing_queue.put(item)

        # Ждём пока обе задачи будут обработаны
        await asyncio.wait_for(converter.processing_queue.join(), timeout=5.0)

        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    userbot_db.DB_PATH = original_path

    # Вторая задача дошла до send_message несмотря на ошибку первой
    assert (
        mock_bot.send_message.call_count == 1
    ), "Воркер должен продолжить обработку после ошибки в первой задаче"
    assert call_count == 2, "epub_service должен был вызваться дважды"
