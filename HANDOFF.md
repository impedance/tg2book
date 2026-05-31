# Handoff: проблема с reauth userbot

## Статус на 2026-05-30

Автоотправка статей не работает с 7 мая — Telethon-сессия userbot'а отозвана Telegram'ом.
Бот (конвертация вручную) работает нормально. Деплой через GitHub Actions работает.

## Что было сделано

### Исправлено и работает
- **Retry-loop** с exponential backoff вместо одноразового падения (bot.py)
- **Уведомление админу** когда userbot падает
- **`/reauth` команда** — ConversationHandler для переавторизации через бота
- Телефон захардкожен (`USERBOT_PHONE=79296212402`), шаг с вводом номера убран
- Временная сессия при reauth чтобы не конфликтовать со старой
- `async with client:` заменён на `connect() + is_user_authorized()` чтобы не триггерить автоматический `send_code_request` из retry-loop

### РЕШЕНО (2026-05-30)
`/reauth` отдавал `The confirmation code has expired (caused by SignInRequest)` — **мгновенно**.

**Настоящая причина:** не anti-spam и не истечение по времени. Это защита Telegram:
если логин-код проходит через сообщение в Telegram, сервер детектит паттерн кода
и **немедленно его аннулирует**. Админ вбивал 5 цифр слитно в чат с ботом → код
инвалидировался на лету. Именно поэтому локальная авторизация (способ 1) и SSH
(способ 3) работали — там код не идёт через Telegram-сообщение.

**Фикс:** теперь `/reauth` просит вводить код **с разделителями** (`1 2 3 4 5`
или `1-2-3-4-5`), а `reauth_code` выкидывает всё кроме цифр перед `sign_in`.
Разделители ломают паттерн, Telegram не распознаёт код в сообщении.
Тесты: `test_reauth_code_strips_separators`, `test_reauth_code_no_digits_reprompts`.

## Запасные способы (если /reauth всё же не сработает)

**Способ 1 — авторизовать сессию локально и скопировать на VDS:**

```bash
# Локально (на машине где есть доступ к аккаунту)
pip install telethon
python3 - <<'EOF'
import asyncio
from telethon import TelegramClient

async def main():
    # Создаём новую сессию
    client = TelegramClient('tg2book_userbot_new', 22903075, '1c00b7cb3e92bd146f683924e422cc58')
    await client.start(phone='+79296212402')
    print("Авторизован!")
    await client.disconnect()

asyncio.run(main())
EOF

# После успешной авторизации скопировать на VDS
scp tg2book_userbot_new.session spec@168.222.253.240:/home/spec/work/tg2book/runtime/tg2book_userbot.session -P 6397
```

После копирования контейнер подхватит сессию автоматически (volume смонтирован).

**Способ 2 — подождать сутки и попробовать `/reauth` снова:**

Telegram снимает флаг после паузы. Просто отправить `/reauth` завтра.

**Способ 3 — через SSH на VDS интерактивно:**

```bash
ssh vds
cd ~/work/tg2book
docker compose exec tg2book python3 userbot_listener.py
# Ввести номер и код вручную
```

## Переменные окружения (.env на VDS)

```
TELEGRAM_BOT_TOKEN=...
ADMIN_ID=98161553
API_ID=22903075
API_HASH=1c00b7cb3e92bd146f683924e422cc58
USERBOT_SESSION=/app/runtime/tg2book_userbot
USERBOT_PHONE=79296212402
DROPBOX_APP_KEY=...
DROPBOX_APP_SECRET=...
DROPBOX_REFRESH_TOKEN=...
```

## Инфраструктура

- VDS: `168.222.253.240`, user `spec`, port `6397`
- Проект: `~/work/tg2book`
- Контейнер: `tg2book-tg2book-1`
- Session файл: `~/work/tg2book/runtime/tg2book_userbot.session`
- Деплой: push в master → GitHub Actions → SSH → `docker compose up -d --build`
- Репо: `github.com/impedance/tg2book`

## Архитектура после изменений

```
bot.py (run_bot)
  └── retry-loop (30s→1800s backoff)
        └── run_userbot_listener()
              └── connect() + is_user_authorized()  ← НЕ вызывает send_code_request
                    ├── if authorized → run_until_disconnected()
                    └── if not → raise EOFError → notify admin → wait for /reauth

/reauth ConversationHandler
  └── reauth_start: создаёт TelegramClient(_reauth_tmp), send_code_request
  └── reauth_code: sign_in, replace session, set restart_event
  └── reauth_2fa: sign_in(password=...), replace session, set restart_event
```
