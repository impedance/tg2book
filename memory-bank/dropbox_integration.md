# Интеграция с Dropbox

## Цель

Добавить возможность отправлять созданный файл EPUB в Dropbox, используя API Dropbox.

## Задачи

1.  Добавление переменной для токена Dropbox API в `bot.py`
    *   Найти место, где определяется токен Telegram.
    *   Добавить переменную `DROPBOX_TOKEN = os.getenv('DROPBOX_TOKEN')` рядом с токеном Telegram.
    *   Добавить проверку на наличие токена Dropbox API и логирование ошибки, если он не установлен.
2.  Изменение функции `handle_message` для загрузки EPUB в Dropbox
    *   Импортировать библиотеку `dropbox`.
    *   Создать экземпляр Dropbox API клиента, используя токен Dropbox API.
    *   Изменить функцию `handle_message` для загрузки EPUB файла в Dropbox после его создания.
    *   Добавить обработку ошибок при загрузке файла в Dropbox и логирование.
3.  Использование Dropbox API для загрузки файла
    *   Определить путь для загрузки файла в Dropbox (`All files/Apps/Dropbox PocketBook/from-bot`).
    *   Использовать метод `files_upload` из Dropbox API для загрузки файла.
