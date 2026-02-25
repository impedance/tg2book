"""
epub_functions.py — lightweight EPUB generator.

Dependencies: stdlib only (zipfile, io, xml.sax.saxutils, textwrap, uuid, datetime).
No Pillow, no ebooklib, no lxml, no beautifulsoup4.
"""

import io
import textwrap
import uuid
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape


# ---------------------------------------------------------------------------
# SVG cover generator
# ---------------------------------------------------------------------------

def _render_svg_cover(title: str, author: str) -> bytes:
    """Return an SVG book cover as UTF-8 bytes.

    The cover uses a simple gradient background with the title and author
    rendered as SVG text elements. All special XML characters are escaped.
    """
    title = (title or "Untitled").strip()
    author = (author or "").strip()

    # Truncate / wrap title
    MAX_CHARS = 200
    if len(title) > MAX_CHARS:
        title = title[: MAX_CHARS - 1] + "…"

    # Wrap into lines of ~30 chars each (max 8 lines)
    title_lines = textwrap.wrap(title, width=30)[:8]

    title_svg_lines = ""
    line_height = 72
    title_y_start = 320
    for i, line in enumerate(title_lines):
        y = title_y_start + i * line_height
        title_svg_lines += (
            f'  <text x="120" y="{y}" '
            f'font-family="Georgia,serif" font-size="60" font-weight="bold" '
            f'fill="#1a1a2e">{xml_escape(line)}</text>\n'
        )

    author_part = ""
    if author:
        author_part = (
            f'  <text x="120" y="1150" '
            f'font-family="Arial,sans-serif" font-size="40" '
            f'fill="#444466">{xml_escape(author)}</text>\n'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1280" viewBox="0 0 800 1280">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#eef2ff"/>
      <stop offset="100%" stop-color="#c7d2fe"/>
    </linearGradient>
  </defs>
  <rect width="800" height="1280" fill="url(#bg)"/>
  <rect x="80" y="240" width="180" height="10" rx="5" fill="#6366f1"/>
{title_svg_lines}{author_part}</svg>"""

    return svg.encode("utf-8")


# ---------------------------------------------------------------------------
# Low-level ZIP / EPUB builder
# ---------------------------------------------------------------------------

_CSS = """\
body { font-family: serif; margin: 5%; color: #111; }
p    { margin-top: 0.5em; margin-bottom: 0.5em; }
"""

_CONTAINER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _make_opf(book_id: str, title: str, author: str, has_cover: bool) -> bytes:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cover_meta = (
        '<meta name="cover" content="cover-image"/>' if has_cover else ""
    )
    cover_item = (
        '<item id="cover-image" href="cover.svg" media-type="image/svg+xml" properties="cover-image"/>'
        if has_cover
        else ""
    )
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">{xml_escape(book_id)}</dc:identifier>
    <dc:title>{xml_escape(title or "Untitled")}</dc:title>
    <dc:creator>{xml_escape(author or "")}</dc:creator>
    <dc:language>ru</dc:language>
    <dc:date>{now}</dc:date>
    {cover_meta}
  </metadata>
  <manifest>
    <item id="ncx"       href="toc.ncx"       media-type="application/x-dtbncx+xml"/>
    <item id="content"   href="content.xhtml"  media-type="application/xhtml+xml"/>
    <item id="css"       href="style.css"      media-type="text/css"/>
    {cover_item}
  </manifest>
  <spine toc="ncx">
    <itemref idref="content"/>
  </spine>
</package>
""".encode("utf-8")


def _make_ncx(book_id: str, title: str) -> bytes:
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
  "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{xml_escape(book_id)}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNum" content="0"/>
  </head>
  <docTitle><text>{xml_escape(title or "Untitled")}</text></docTitle>
  <navMap>
    <navPoint id="navpoint-1" playOrder="1">
      <navLabel><text>{xml_escape(title or "Untitled")}</text></navLabel>
      <content src="content.xhtml"/>
    </navPoint>
  </navMap>
</ncx>
""".encode("utf-8")


def _make_xhtml(title: str, content: str) -> bytes:
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ru">
  <head>
    <meta charset="UTF-8"/>
    <title>{xml_escape(title or "")}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
  </head>
  <body>
    {content}
  </body>
</html>
""".encode("utf-8")


def _build_epub_zip(dest, *, title: str, author: str, content: str) -> None:
    """Write a valid EPUB 3 archive to *dest* (file path or writable file-like object).

    The EPUB spec requires:
    - ``mimetype`` is the **first** entry and stored uncompressed.
    - ``META-INF/container.xml`` describes the package document location.
    """
    book_id = str(uuid.uuid4())
    svg_cover = _render_svg_cover(title, author)

    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. mimetype — MUST be first, MUST be stored (no compression)
        mi = zipfile.ZipInfo("mimetype")
        mi.compress_type = zipfile.ZIP_STORED
        zf.writestr(mi, "application/epub+zip")

        # 2. META-INF/container.xml
        zf.writestr("META-INF/container.xml", _CONTAINER_XML)

        # 3. OEBPS payload
        zf.writestr("OEBPS/content.opf", _make_opf(book_id, title, author, has_cover=True))
        zf.writestr("OEBPS/toc.ncx", _make_ncx(book_id, title))
        zf.writestr("OEBPS/content.xhtml", _make_xhtml(title, content))
        zf.writestr("OEBPS/style.css", _CSS)
        zf.writestr("OEBPS/cover.svg", svg_cover)


# ---------------------------------------------------------------------------
# Public API (kept identical to old signature for bot.py compatibility)
# ---------------------------------------------------------------------------

def create_epub(title: str, author: str, content: str, output_path: str) -> str:
    """Create an EPUB file at *output_path* and return the path.

    Uses stdlib zipfile + SVG cover — no Pillow, no ebooklib.
    """
    _build_epub_zip(output_path, title=title, author=author, content=content)
    return output_path
