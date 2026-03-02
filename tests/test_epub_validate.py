import io
import zipfile

import pytest

from epub_functions import create_epub
from utils.epub_validate import EpubValidationError, validate_epub_bytes, validate_epub_path


def test_validate_epub_path_ok(tmp_path):
    out = tmp_path / "ok.epub"
    create_epub(title="T", author="A", content="<p>Hello</p>", output_path=str(out))
    validate_epub_path(out)


def test_validate_epub_bytes_rejects_bad_mimetype():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        mi = zipfile.ZipInfo("mimetype")
        mi.compress_type = zipfile.ZIP_STORED
        zf.writestr(mi, "application/zip")

    with pytest.raises(EpubValidationError, match="mimetype payload"):
        validate_epub_bytes(buf.getvalue())
