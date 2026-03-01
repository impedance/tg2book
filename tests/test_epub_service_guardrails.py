from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services import epub_service


@pytest.mark.asyncio
async def test_process_text_to_epub_offloads_blocking_work(tmp_path):
    output_path = tmp_path / "generated.epub"
    create_calls = []
    dropbox_calls = []

    def fake_create_epub(title, author, content, destination):
        Path(destination).write_bytes(b"epub-data")
        create_calls.append((title, author, content, destination))
        return destination

    def fake_upload_to_dropbox(file_path, filename):
        dropbox_calls.append((file_path, filename))
        return True

    async def tracking_to_thread(func, *args, **kwargs):
        tracking_to_thread.calls.append(func.__name__)
        return func(*args, **kwargs)

    tracking_to_thread.calls = []

    with (
        patch("services.epub_service.create_epub", new=fake_create_epub),
        patch("services.epub_service.dropbox_module.upload_to_dropbox", new=fake_upload_to_dropbox),
        patch("services.epub_service.asyncio.to_thread", side_effect=tracking_to_thread),
        patch("services.epub_service.tempfile.NamedTemporaryFile") as mock_tempfile,
        patch("services.epub_service.os.path.exists", return_value=True),
        patch("services.epub_service.os.remove"),
    ):
        temp_file = MagicMock()
        temp_file.name = str(output_path)
        mock_tempfile.return_value.__enter__.return_value = temp_file

        summary = await epub_service.process_text_to_epub(
            "Guardrail title\n\nBody",
            "Guardrail Source",
            "https://t.me/example/1",
        )

    assert tracking_to_thread.calls == ["fake_create_epub", "fake_upload_to_dropbox"]
    assert create_calls
    assert dropbox_calls
    assert "Guardrail title" in summary


@pytest.mark.asyncio
async def test_process_file_to_dropbox_uses_to_thread():
    async def tracking_to_thread(func, *args, **kwargs):
        func_name = getattr(func, "__name__", getattr(func, "_mock_name", type(func).__name__))
        tracking_to_thread.calls.append((func_name, args))
        return True

    tracking_to_thread.calls = []

    with (
        patch(
            "services.epub_service.dropbox_module.upload_to_dropbox", return_value=True
        ) as mock_upload,
        patch("services.epub_service.asyncio.to_thread", side_effect=tracking_to_thread),
    ):
        result = await epub_service.process_file_to_dropbox("/tmp/book.epub", "Book.epub")

    assert result is True
    assert tracking_to_thread.calls == [("upload_to_dropbox", ("/tmp/book.epub", "Book.epub"))]
    mock_upload.assert_not_called()
