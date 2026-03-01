import re
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'(?:(?:https?|ftp):\/\/)?'  # optional scheme
    r'(?:\S+(?::\S*)?@)?'  # user:pass authentication
    r'(?:'
    r'(?P<private_ip>'  # private IP addresses
    r'(?:(?:10|127)(?:\.\d{1,3}){3})|'
    r'(?:(?:169\.254|192\.168)(?:\.\d{1,3}){2})|'
    r'(?:172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})'
    r')|'
    r'(?P<public_ip>'  # public IP addresses
    r'(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])'
    r'(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}'
    r'(?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))'
    r')|'
    r'(?:(?:[a-z\u00a1-\uffff0-9]-*)*[a-z\u00a1-\uffff0-9]+)'  # host name
    r'(?:\.(?:[a-z\u00a1-\uffff0-9]-*)*[a-z\u00a1-\uffff0-9]+)*'  # domain name
    r'(?:\.(?:[a-z\u00a1-\uffff]{2,}))'  # TLD identifier
    r')'
    r'(?::\d{2,5})?'  # port number
    r'(?:[/?#]\S*)?',  # resource path
    re.IGNORECASE
)

def extract_url(text: str) -> str | None:
    if not text:
        return None
    match = URL_REGEX.search(text)
    if match:
        return match.group(0)
    return None

def parse_article(url: str) -> tuple[str, str] | None:
    """
    Скачивает веб-страницу по URL и парсит заголовок и текстовое содержимое.
    Возвращает (title, content) или None, если парсинг не удался.
    """
    try:
        if not url.startswith("http"):
            url = "http://" + url
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Получаем заголовок
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        else:
            # Fallback к h1
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)

        if not title:
            title = "Processed Article"

        # Пытаемся взять основной контент (article или body)
        article = soup.find('article')
        if article:
            content = article.get_text(separator=' ', strip=True)
        else:
            # Если нет тега article, берём body и чистим его от скриптов/стилей
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.extract()
            body = soup.find('body')
            content = body.get_text(separator=' ', strip=True) if body else ""

        if not content:
            logger.warning(f"Не удалось извлечь контент со страницы: {url}")
            return None

        return title, content
    except Exception as e:
        logger.warning(f"Ошибка при парсинге URL {url}: {e}")
        return None
