from ebooklib import epub
import io
import textwrap
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
    background = (250, 250, 248)
    text_color = (20, 20, 20)
    accent = (60, 110, 180)

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
            fill=(60, 60, 60),
            font=author_font,
        )

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()

def create_epub(title, author, content, output_path):
    # Create the EPUB book
    book = epub.EpubBook()
    book.set_identifier("id123456")
    book.set_title(title)
    book.set_language("ru")
    book.add_author(author)

    cover_png = _render_text_cover_png(title=title, author=author)
    if cover_png:
        # Only embed cover metadata (no extra cover page), so we don't add a blank first page.
        book.set_cover("cover.png", cover_png, create_page=False)

    # Define CSS style
    style = '''
    BODY {
        color: black;
        font-family: serif;
        margin: 5%;
    }
    p {
        margin-top: 0.5em;
        margin-bottom: 0.5em;
    }
    '''
    
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)

    # Create main content without any additional formatting
    main_content = epub.EpubHtml(title=title, file_name='content.xhtml', lang='en')
    
    # Wrap content in simple HTML without adding links or list formatting
    # Just preserve the exact content formatting
    main_content.content = f'''
    <html>
        <head>
            <title>{title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css" />
        </head>
        <body>
            {content}
        </body>
    </html>
    '''

    # Add content to the book
    book.add_item(main_content)

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Add CSS file
    book.add_item(nav_css)

    # Basic spine - только контент без отдельных глав и оглавления
    book.spine = [main_content]

    # Write to the file
    epub.write_epub(output_path, book, {})

    return output_path
