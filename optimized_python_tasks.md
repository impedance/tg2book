# 🏗️ Task plan for Optimized Python Refactoring

- [ ] Создание базового замера `docker stats` до начала работ
- [ ] Очистка `dropbox_module.py` и удаление `dropbox-loader.py`
    - [ ] Написать прямые HTTP запросы к Dropbox API
    - [ ] Удалить subprocess
- [ ] Рефакторинг `epub_functions.py`
    - [ ] Заменить генерацию обложки с Pillow (PNG) на SVG (строки)
    - [ ] Заменить генерацию EPUB через ebooklib на нативный `zipfile` сборщик
- [ ] Чистка `requirements.txt` и `Dockerfile`
    - [ ] Удалить `Pillow`, `ebooklib`, `lxml` и `bs4`
    - [ ] Очистить Dockerfile от системных зависимостей для сборки C-модулей
- [ ] Адаптация `bot.py`
    - [ ] Подключить новые функции генерации и загрузки
- [ ] Обновление тестов в `test_bot.py`
    - [ ] Обновить mock-и (HTTP, zipfile)
    - [ ] Добиться coverage > 95%
- [ ] Финальная проверка тестов `pytest` и повторный замер потребления памяти
