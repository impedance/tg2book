# Руководство по эксплуатации контейнера tg2book

## Подготовка окружения
- создать файл `.env` рядом с `docker-compose.yml` с обязательными переменными:
  - `TELEGRAM_BOT_TOKEN`
  - `DROPBOX_APP_KEY`
  - `DROPBOX_APP_SECRET`
  - `DROPBOX_REFRESH_TOKEN`
- файл `.env` не попадает в образ благодаря `.dockerignore`, не коммитить его.
- убедиться, что демон Docker запущен (`systemctl status docker`), иначе `docker compose` команды падают.

## Повседневные операции
1. `make run` — перезапустить контейнер для применения изменений кода (быстрый рестарт).
2. `make test` — запустить тесты внутри контейнера.
3. `make logs` — смотреть логи.
4. `make build` — пересобрать контейнер заново (если изменились зависимости).
5. `docker compose up -d --build` — собрать образ и запустить сервис, применив новые переменные/код.
6. `docker compose logs -f --tail=200` — смотреть поток логов (логгер теперь печатает в stdout).
7. `docker compose restart` — перезапустить контейнер, чтобы применить обновлённую конфигурацию.
8. `docker compose down` — аккуратно остановить и удалить контейнер.
9. `docker compose ps` — проверить, что сервис в статусе `running`.
10. `docker compose exec tg2book sh` — попасть внутрь контейнера для диагностики (по необходимости).

## Обновления
- используйте `make run` для применения изменений в коде.
- используйте `make build`, если изменили `requirements.txt` или `Dockerfile`.
- после изменений в коде или зависимостях использовать `docker compose up -d --build`.
- если меняется только код, кэш слоя с зависимостями ускорит сборку.
- новые переменные в `.env` требуют перезапуска: `docker compose restart` или `docker compose up -d --build`.

## Типичные отказные сценарии и проверки
- **Нет Telegram токена**: `docker compose logs` покажет ошибку `TELEGRAM_BOT_TOKEN environment variable not set` → заполнить `.env`.
- **Отсутствуют Dropbox данные**: загрузка в Dropbox выкинет ошибку `401` или `Invalid token` → проверить ключи `DROPBOX_*` и `dropbox-loader.py` отдельно.
- **Проблемы с сетью**: бот не подключается к Telegram/Dropbox, проверять сетевые настройки хоста, прокси, доступ к `api.telegram.org`.
- **OOM/killed**: `docker compose logs` или `docker events` покажут `Out of memory` → `docker stats` подтвердит, что контейнер упирается в `mem_limit 768m`; уменьшить объём входных данных или временно увеличить лимиты в `docker-compose.yml` (скопировать конфиг и пересобрать).
- **Контейнер не стартует после ребута**: `docker compose ps` вернёт `exited`; `restart: unless-stopped` поднимает его только если демон Docker включён, проверить `systemctl is-active docker`.

## Быстрый доступ к диагностике
- `docker compose logs -f --tail=50 --timestamps` — посмотреть недавние ошибки.
- `docker compose exec tg2book python -m pytest` — запустить тесты внутри контейнера (если нужно воспроизвести баг).
