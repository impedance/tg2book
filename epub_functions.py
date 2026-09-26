from ebooklib import epub
import html
import io
import textwrap
import uuid
from typing import Optional


def _load_font(size: int, bold: bool = False):
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    candidates = []
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ]
        )
    candidates.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )

    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue

    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _render_text_cover_png(title: str, author: str) -> Optional[bytes]:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    title = (title or "Untitled").strip()
    author = (author or "").strip()

    width, height = 1600, 2560
    # E-ink grayscale discipline: pure white bg, near-black text, gray accent
    # (PB970: 16 gray levels — blue accent would flatten into meaningless gray).
    background = (255, 255, 255)
    text_color = (20, 20, 20)
    accent = (110, 110, 110)

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    margin_x = int(width * 0.10)
    top_y = int(height * 0.18)

    # Small accent line
    draw.rectangle(
        (margin_x, top_y - 50, margin_x + int(width * 0.22), top_y - 30),
        fill=accent,
    )

    title_font = _load_font(size=110, bold=True)
    author_font = _load_font(size=56, bold=False)
    if title_font is None or author_font is None:
        return None

    max_chars = 120
    title_short = title.replace("\n", " ").strip()
    if len(title_short) > max_chars:
        title_short = title_short[: max_chars - 1] + "…"

    # Rough wrap: adjust by characters; we avoid font metrics dependencies.
    wrap_width = 22
    title_lines = textwrap.wrap(title_short, width=wrap_width)[:8]
    title_text = "\n".join(title_lines)

    draw.multiline_text(
        (margin_x, top_y),
        title_text,
        fill=text_color,
        font=title_font,
        spacing=18,
    )

    if author:
        # Place author near bottom
        author_y = int(height * 0.85)
        author_text = f"Источник: {author}"
        draw.text(
            (margin_x, author_y),
            author_text,
            fill=(40, 40, 40),
            font=author_font,
        )

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()

# E-ink profile `send-to-book/inkpad-lite-970 v1` (approved in san-obsid #169):
# static XHTML/CSS only, serif body, grayscale discipline, narrow-screen safe.
EINK_CSS = """
body { color: #000; background: #fff; font-family: Georgia, "Times New Roman", serif; margin: 5%; line-height: 1.6; text-align: left; }
h1 { font-size: 1.5em; line-height: 1.25; }
h2 { font-size: 1.3em; }
h3 { font-size: 1.15em; }
h1, h2, h3 { font-weight: bold; page-break-after: avoid; margin: 1em 0 0.5em; }
p, li { font-size: 1em; }
p { margin-top: 0.5em; margin-bottom: 0.5em; }
blockquote { margin: 0.8em 0; padding-left: 0.8em; border-left: 2px solid #666; color: #222; }
code, pre { font-family: monospace; font-size: 0.9em; white-space: pre-wrap; word-wrap: break-word; }
pre { border: 1px solid #999; padding: 6px; }
img { max-width: 100%; height: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.85em; margin: 0.8em 0; }
th, td { border: 1px solid #666; padding: 4px; text-align: left; word-break: break-word; }
a { color: #000; text-decoration: underline; }
"""

# Tables wider than this are stacked into h4+ul blocks (no horizontal scroll on 825px panel).
MAX_TABLE_COLS = 3


def adapt_content_for_eink(content):
    """Per-type branching for the 825px grayscale panel (V1).

    - narrow tables (<=3 cols): kept, styled by EINK_CSS;
    - wide tables: converted to stacked ``h4`` + ``ul`` blocks;
    - remote <img> (http/https src): replaced with ``[image: URL]`` placeholder
      (no arbitrary URL fetching in V1); local images stay, CSS constrains them.
    Falls back to the original content if parsing fails.
    """
    if not content or "<table" not in content and "<img" not in content:
        return content
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return content
    try:
        soup = BeautifulSoup(f"<div>{content}</div>", "lxml")
        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip()
            if src.startswith("http://") or src.startswith("https://"):
                img.replace_with(f"[image: {src}]")
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            ncols = max((len(r.find_all(["th", "td"])) for r in rows), default=0)
            if ncols <= MAX_TABLE_COLS or not rows:
                continue
            header = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
            replacement = []
            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if not any(cells):
                    continue
                title = cells[0] or "Запись"
                items = "".join(
                    f"<li><b>{html.escape(header[i] if i < len(header) else '')}</b>: "
                    f"{html.escape(val)}</li>"
                    for i, val in enumerate(cells[1:]) if val
                )
                replacement.append(f"<h4>{html.escape(title)}</h4><ul>{items}</ul>")
            if replacement:
                table.replace_with(BeautifulSoup("".join(replacement), "lxml"))
        body = soup.find("div")
        return "".join(str(c) for c in body.contents) if body else content
    except Exception:
        return content


def create_epub(title, author, content, output_path, source_url=None):
    # Create the EPUB book
    book = epub.EpubBook()
    # Stable unique identifier per book (was a constant "id123456" shared by all books).
    book.set_identifier(f"tg2book-{uuid.uuid4().hex}")
    book.set_title(title or "Untitled")
    book.set_language("ru")
    book.add_author(author or "")

    cover_png = _render_text_cover_png(title=title, author=author)
    if cover_png:
        # Only embed cover metadata (no extra cover page), so we don't add a blank first page.
        book.set_cover("cover.png", cover_png, create_page=False)

    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=EINK_CSS)

    # Create main content, adapted for the e-ink panel
    main_content = epub.EpubHtml(title=title, file_name='content.xhtml', lang='ru')

    safe_title = html.escape(title or "Untitled")
    body_html = adapt_content_for_eink(content or "")
    source_section = ""
    if source_url:
        source_section = f"<section><h2>Источник</h2><p><a href=\"{html.escape(source_url, quote=True)}\">{html.escape(source_url)}</a></p></section>"

    main_content.content = f'''
    <html lang="ru">
        <head>
            <title>{safe_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css" />
        </head>
        <body>
            {body_html}
            {source_section}
        </body>
    </html>
    '''

    # Add content to the book
    book.add_item(main_content)

    # TOC + navigation (Nav is part of the spine, so the TOC actually opens on device).
    nav = epub.EpubNav()
    book.add_item(nav)
    book.add_item(epub.EpubNcx())
    book.toc = [main_content]

    # Add CSS file
    book.add_item(nav_css)

    book.spine = ['nav', main_content]

    # Write to the file
    epub.write_epub(output_path, book, {})

    return output_path
