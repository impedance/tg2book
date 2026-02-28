"""
One-time script to authorize the Pyrogram userbot via QR code.

Usage:
    1. pip install "qrcode[pil]"
    2. python3 login_qr.py
    3. Scan the QR code with your Telegram app.
    4. Copy the printed SESSION STRING into .env as USERBOT_SESSION_STRING.

The script does NOT store a .session file on disk — it works entirely
in-memory and exports a portable string session at the end.
"""

import asyncio
import sys

# --- Dependency guard: fail loudly and early if qrcode is missing ---
try:
    import qrcode  # noqa: F401
except ImportError:
    print(
        "❌ Ошибка: библиотека 'qrcode[pil]' не установлена.\n"
        "   Выполните:  pip install \"qrcode[pil]\"\n"
        "   Затем снова запустите скрипт."
    )
    sys.exit(1)

from pyrogram import Client
from pyrogram import raw as raw_types
from pyrogram.raw import functions

from config import settings
from src.qr_utils import generate_qr_image, generate_qr_link

# How often to poll Telegram for confirmation (seconds)
POLL_INTERVAL = 3
# QR code image saved next to the script
QR_IMAGE_PATH = "login_qr.png"


async def main() -> None:
    api_id = settings.API_ID
    api_hash = settings.API_HASH

    if not api_id or not api_hash:
        print("❌ Ошибка: API_ID или API_HASH не заданы в .env")
        sys.exit(1)

    print(f"✅ Используем API_ID: {api_id}")

    # Use in_memory=True — no .session file, only a string at the end
    app = Client(
        name="qr_login_temp",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
        device_model="Desktop",
        system_version="Windows 10",
        app_version="4.9.4",
    )

    # Use connect() manually to bypass Pyrogram's default phone number prompt
    await app.connect()
    
    try:
        print("\n🔄 Получаем QR-токен от Telegram...\n")

        result = await app.invoke(
            functions.auth.ExportLoginToken(
                api_id=api_id,
                api_hash=api_hash,
                except_ids=[],
            )
        )

        if not isinstance(result, raw_types.types.auth.LoginToken):
            print(f"⚠️  Неожиданный ответ от Telegram: {result}")
            sys.exit(1)

        token: bytes = result.token
        link = generate_qr_link(token)

        # --- Output method 1: ready-to-click tg:// link ---
        print("━" * 60)
        print("🔗 Ссылка (кликните на Desktop или откройте в браузере):")
        print(f"   {link}")
        print("━" * 60)

        # --- Output method 2: PNG image ---
        generate_qr_image(link, QR_IMAGE_PATH)
        print(f"🖼️  QR-код сохранён в файл: {QR_IMAGE_PATH}")

        # --- Output method 3: ASCII QR in terminal ---
        qr = qrcode.QRCode(  # type: ignore[name-defined]
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # type: ignore[attr-defined]
            box_size=1,
            border=2,
        )
        qr.add_data(link)
        qr.make(fit=True)
        print("\n📱 Отсканируйте QR-код в Telegram (Настройки → Устройства → Войти):\n")
        qr.print_ascii(invert=True)
        print()

        # --- Polling loop: wait for the user to scan the QR ---
        print("⏳ Ожидаем сканирования QR-кода...")
        
        from pyrogram.errors import SessionPasswordNeeded
        import getpass
        
        while True:
            await asyncio.sleep(POLL_INTERVAL)

            try:
                status = await app.invoke(
                    functions.auth.ExportLoginToken(
                        api_id=api_id,
                        api_hash=api_hash,
                        except_ids=[],
                    )
                )
            except SessionPasswordNeeded:
                print("\n🔐 На аккаунте включен Облачный пароль (двухэтапная аутентификация).")
                while True:
                    password = getpass.getpass("Введите облачный пароль: ")
                    try:
                        await app.check_password(password)
                        print("\n✅ Пароль принят! Авторизация подтверждена.")
                        break
                    except Exception as pwd_e:
                        print(f"❌ Ошибка пароля: {pwd_e}. Попробуйте снова.")
                break
            except Exception as e:
                # Session may have been accepted — catch auth errors gracefully
                print(f"   (poll error, continuing: {e})")
                continue

            if isinstance(status, raw_types.types.auth.LoginTokenSuccess):
                print("\n✅ QR-код успешно отсканирован! Авторизация подтверждена.")
                break
            elif isinstance(status, raw_types.types.auth.LoginTokenMigrateTo):
                # Telegram wants us to reconnect to a different DC
                print("   ↩️  Перенаправление на другой DC, переподключаемся...")
                status = await app.invoke(
                    functions.auth.ImportLoginToken(token=status.token)
                )
                if isinstance(status, raw_types.types.auth.LoginTokenSuccess):
                    print("\n✅ QR-код успешно отсканирован! Авторизация подтверждена.")
                    break
            # else: still LoginToken — keep polling

        # --- Export session string ---
        session_string = await app.export_session_string()
        
        # After successful QR login, pyrogram might need a moment to register auth state completely
        # But we can try to get the user info
        try:
            me = await app.get_me()
            print(f"\n👤 Аккаунт: {me.first_name} (@{me.username})")
        except Exception:
            # get_me is just a nice-to-have, don't fail if it doesn't work right after connect
            pass

        print("\n" + "=" * 60)
        print("🔑  ВАША СТРОКА СЕССИИ (SESSION STRING):")
        print("=" * 60)
        print(session_string)
        print("=" * 60)
        print(
            "\n📋 Скопируйте строку выше и вставьте её в .env:\n"
            "   USERBOT_SESSION_STRING=<вставьте строку>\n"
            "\n⚠️  НЕ КОММИТЬТЕ ЭТУ СТРОКУ В GIT!"
        )
    finally:
        await app.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
