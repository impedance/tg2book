"""
Black-box tests for src/qr_utils.py.
These tests use a fake token and do NOT call any Telegram APIs.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is on the path so we can import src.qr_utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.qr_utils import generate_qr_link, generate_qr_image  # noqa: E402

FAKE_TOKEN = b"fake_token_data"


class TestGenerateQrLink:
    def test_returns_tg_login_scheme(self):
        link = generate_qr_link(FAKE_TOKEN)
        assert link.startswith("tg://login?token="), f"Unexpected scheme: {link}"

    def test_base64url_encoded(self):
        """Verify the token part is valid base64url (no + / = chars)."""
        link = generate_qr_link(FAKE_TOKEN)
        token_part = link.split("token=", 1)[1]
        # base64url uses - and _ instead of + and /; no padding =
        assert "+" not in token_part
        assert "/" not in token_part
        assert "=" not in token_part

    def test_decoded_matches_original(self):
        """Round-trip: decode the link back and compare to original token."""
        import base64

        link = generate_qr_link(FAKE_TOKEN)
        encoded = link.split("token=", 1)[1]
        # Restore padding
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        decoded = base64.urlsafe_b64decode(encoded)
        assert decoded == FAKE_TOKEN

    def test_different_tokens_give_different_links(self):
        link1 = generate_qr_link(b"token_one")
        link2 = generate_qr_link(b"token_two")
        assert link1 != link2


class TestGenerateQrImage:
    def test_creates_png_file(self, tmp_path):
        """generate_qr_image should save a valid PNG file."""
        pytest.importorskip("qrcode", reason="qrcode[pil] not installed")

        link = generate_qr_link(FAKE_TOKEN)
        output = tmp_path / "test_login_qr.png"
        generate_qr_image(link, str(output))

        assert output.exists(), "PNG file was not created"
        assert output.stat().st_size > 0, "PNG file is empty"

    def test_png_has_correct_magic_bytes(self, tmp_path):
        """Verify the file starts with PNG magic bytes."""
        pytest.importorskip("qrcode", reason="qrcode[pil] not installed")

        link = generate_qr_link(FAKE_TOKEN)
        output = tmp_path / "magic_test.png"
        generate_qr_image(link, str(output))

        with open(output, "rb") as f:
            header = f.read(8)
        assert header == b"\x89PNG\r\n\x1a\n", "File is not a valid PNG"

    def test_default_filename(self, tmp_path, monkeypatch):
        """Test that the default filename 'login_qr.png' is used when not specified."""
        pytest.importorskip("qrcode", reason="qrcode[pil] not installed")

        monkeypatch.chdir(tmp_path)
        link = generate_qr_link(FAKE_TOKEN)
        generate_qr_image(link)  # uses default filename

        assert (tmp_path / "login_qr.png").exists()
