# Project Brief: tg2book

## Core Requirements

- Пользователь отправляет боту пересланное сообщение с текстом или готовый `.epub`.
- Бот подготавливает EPUB или принимает уже готовый файл.
- Результат синхронизируется в Dropbox для дальнейшей доставки в PocketBook.

## Extended Requirements

- Администратор может управлять списком каналов для автоматической обработки.
- Userbot слушает новые посты каналов и пропускает дальше только разрешённые источники.
- Общий pipeline для bot и userbot должен оставаться единым и предсказуемым.

## Key Features

- EPUB generation from text posts.
- Direct EPUB pass-through with Dropbox sync.
- SQLite registry for monitored channels.
- Admin commands for channel management.
- Telethon-based channel ingestion sidecar.

## Success Criteria

- Пользователь может получить или инициировать доставку EPUB без ручной сборки файла.
- Канальные посты из разрешённых источников обрабатываются автоматически.
- Dropbox upload стабильно срабатывает для обоих основных сценариев.
- После рестарта или деплоя проект можно предсказуемо вернуть в рабочее состояние.
