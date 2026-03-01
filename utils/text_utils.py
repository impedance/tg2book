import re
from html import escape as html_escape
from typing import Optional


def strip_emojis(text: str) -> str:
    """Removes emojis and other special characters from text."""
    if not text:
        return ""
    # Match anything that is NOT a basic character (simplified regex for now)
    clean = re.sub(r"[^\w\s\-_.,()!?:;а-яёА-ЯЁ/]", "", text)
    # Also collapse multiple spaces
    return re.sub(r"\s+", " ", clean).strip()


def extract_title(text: Optional[str]) -> str:
    """Берёт заголовок как первый абзац (до пустой строки)."""
    text = (text or "").strip()
    if not text:
        return "Untitled"
    paragraphs = re.split(r"\n\s*\n", text, maxsplit=1)
    title = (paragraphs[0] or "").strip()
    return title or "Untitled"


def sanitize_filename(title: str, max_words: int = 4) -> str:
    """Create a safe filename from post title (limited to max_words)"""
    if not title or title == "Untitled":
        return "message"

    # Take first line or first sentence as filename
    clean_title = title.split("\n", maxsplit=1)[0].strip()
    if not clean_title:
        clean_title = title.strip()

    # Remove or replace unsafe characters
    clean_title = re.sub(r"[^\w\s\-_а-яё]", "", clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r"\s+", " ", clean_title.strip())

    # Limit to max_words
    words = clean_title.split()
    if len(words) > max_words:
        words = words[:max_words]

    # Join with underscores
    clean_title = "_".join(words)

    return clean_title if clean_title else "message"


def format_message(text: str) -> str:
    """
    Сохраняет структуру исходного текста, списки, абзацы.
    Все упоминания файлов .md подчёркивает (например, _plan.md_).
    Преобразует переносы строк в <br> и абзацы в <p> для корректного отображения в EPUB.
    """
    link_pattern = re.compile(r"\b[\w\-/]+\.md\b", re.IGNORECASE)

    def underline_md(match: re.Match) -> str:
        return f"<u>{match.group(0)}</u>"

    # Разбиваем на абзацы по двойному переносу
    paragraphs = text.split("\n\n")
    formatted_paragraphs = []
    for para in paragraphs:
        # Экранируем пользовательский текст, затем возвращаем безопасную разметку
        formatted_para = html_escape(para, quote=False)
        formatted_para = link_pattern.sub(underline_md, formatted_para)
        formatted_para = formatted_para.replace("\n", "<br>")
        formatted_paragraphs.append(f"<p>{formatted_para}</p>")
    return "\n".join(formatted_paragraphs)
