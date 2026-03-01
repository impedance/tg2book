import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import pytest

from epub_functions import create_epub
from utils.text_utils import extract_title, format_message

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("fixture_name", "expected_title", "expected_snippet"),
    [
        ("basic_post.txt", "Простой заголовок", "Первый абзац с обычным текстом."),
        ("html_entities.txt", "Заголовок & <проверка>", "Текст с символами &lt;, &gt; и &amp;"),
        ("list_like_post.txt", "Список задач", "- Первый пункт"),
    ],
)
def test_epub_golden_inputs(tmp_path, fixture_name, expected_title, expected_snippet):
    raw_text = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")
    title = extract_title(raw_text)
    output_path = tmp_path / f"{fixture_name}.epub"

    create_epub(
        title=title,
        author="Golden Fixture",
        content=format_message(raw_text),
        output_path=str(output_path),
    )

    with zipfile.ZipFile(output_path) as epub:
        names = epub.namelist()
        assert names[0] == "mimetype"
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert "OEBPS/content.xhtml" in names

        mimetype_info = epub.getinfo("mimetype")
        assert mimetype_info.compress_type == zipfile.ZIP_STORED

        xhtml = epub.read("OEBPS/content.xhtml").decode("utf-8")
        assert f"<title>{xml_escape(expected_title)}</title>" in xhtml
        assert expected_snippet in xhtml
