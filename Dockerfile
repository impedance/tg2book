FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd -m botuser

WORKDIR /app

COPY requirements.txt requirements-test.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt


FROM base AS dev

RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .
RUN chown -R botuser:botuser /app

USER botuser

CMD ["python", "bot.py"]


FROM base AS prod

COPY . .
RUN chown -R botuser:botuser /app

USER botuser

CMD ["python", "bot.py"]
