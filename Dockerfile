FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# No system-level build deps needed: Pillow/lxml/ebooklib are removed
RUN useradd -m botuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R botuser:botuser /app

USER botuser

CMD ["python", "bot.py"]
