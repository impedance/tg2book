# Руководство по эксплуатации контейнера tg2book

## Подготовка окружения
- создать файл `.env` рядом с `docker-compose.yml` с обязательными переменными:
  - `TELEGRAM_BOT_TOKEN`
  - `DROPBOX_APP_KEY`
  - `DROPBOX_APP_SECRET`
  - `DROPBOX_REFRESH_TOKEN`
  - `API_ID` и `API_HASH` (с [my.telegram.org](https://my.telegram.org))
  - `USERBOT_SESSION_STRING` (генерируется один раз скриптом `login_qr.py`, см. ниже)
- файл `.env` не попадает в образ благодаря `.dockerignore`, не коммитить его.
- убедиться, что демон Docker запущен (`systemctl status docker`), иначе `docker compose` команды падают.

## Первичная авторизация юзербота (генерация сессии через QR-код)

Выполняется **один раз** на локальной машине администратора перед первым деплоем.

```bash
# 1. Установить временную зависимость (не нужна в Docker)
pip install "qrcode[pil]"

# 2. Запустить скрипт авторизации
python3 login_qr.py
```

Скрипт выведет:
- **Ссылку** `tg://login?token=...` — кликните на Desktop.
- **QR-код** прямо в терминале (псевдографикой).
- **Файл** `login_qr.png` — откройте, если терминальный QR не читается.

Отсканируйте QR через **Настройки → Устройства → Войти** в мобильном Telegram.  
Скрипт автоматически выведет `USERBOT_SESSION_STRING` — скопируйте её в `.env`.

> ⚠️ Не коммитьте `USERBOT_SESSION_STRING` в git!  
> `login_qr.png` игнорируется через `.gitignore` (`*.png`).

## Повседневные операции
1. `make build` — собрать и поднять dev-контейнер с bind mount исходников.
2. `make run` — перезапустить dev-контейнер для применения изменений кода без rebuild образа.
3. `make test` — запустить тесты внутри dev-контейнера.
4. `make smoke` / `make preflight` — быстрый и полный регрессионный прогон внутри dev-контейнера.
5. `make logs` — смотреть логи dev-контейнера.
6. `make prod-up` — собрать и поднять production-контейнер без dev-зависимостей и тестов.
7. `make prod-logs` — смотреть логи production-контейнера.
8. `make down` / `make prod-down` — остановить и удалить соответствующий стек.
9. `docker compose -f docker-compose.yml -f docker-compose.dev.yml exec tg2book sh` — попасть внутрь dev-контейнера.

## Обновления
- используйте `make run` для применения обычных изменений в коде без rebuild.
- используйте `make build`, если изменили `requirements*.txt`, `Dockerfile` или dev compose-конфиг.
- используйте `make prod-up`, если меняется production-образ или переменные production-запуска.
- новые переменные в `.env` требуют `make run`/`make build` для dev или `make prod-up` для prod.

## Типичные отказные сценарии и проверки
- **Нет Telegram токена**: `make logs` или `make prod-logs` покажет ошибку `TELEGRAM_BOT_TOKEN environment variable not set` → заполнить `.env`.
- **Отсутствуют Dropbox данные**: загрузка в Dropbox выкинет ошибку `401` или `Invalid token` → проверить ключи `DROPBOX_*` и `dropbox_module.py` отдельно.
- **Проблемы с сетью**: бот не подключается к Telegram/Dropbox, проверять сетевые настройки хоста, прокси, доступ к `api.telegram.org`.
- **OOM/killed**: compose-логи или `docker events` покажут `Out of memory` → `docker stats` подтвердит, что контейнер упирается в `mem_limit 768m`; уменьшить объём входных данных или временно увеличить лимиты в compose-файлах.
- **Контейнер не стартует после ребута**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` вернёт `exited`; `restart: unless-stopped` поднимает его только если демон Docker включён, проверить `systemctl is-active docker`.

## Быстрый доступ к диагностике
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f --tail=50 --timestamps` — посмотреть недавние ошибки в dev.
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml exec tg2book python -m pytest tests` — запустить тесты внутри dev-контейнера.
