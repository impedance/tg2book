# Исправление обработки пересланных сообщений

## Корневая причина

Telegram **не передаёт `fwd_from` header** для сообщений из каналов с включённой защитой контента («Restrict Saving Content»). В результате Pyrogram не заполняет ни одного forward-атрибута (`forward_date`, `forward_from`, `forward_from_chat`, `forward_sender_name`) — все остаются `None`.

Код в [handle_message](file:///home/spec/work/tg2book/bot.py#L409-L481) определяет пересылку так:
```python
is_forwarded = any(val is not None for val in forward_values.values())
```
Когда все атрибуты `None` → `is_forwarded = False` → сообщение обрабатывается как обычный текст с `source_name = "Unknown Source"` и без ссылки на оригинал.

> [!IMPORTANT]
> Атрибут `forward_origin` (строка 419) **не существует** в Pyrogram 2.0.106 — `getattr` всегда возвращает `None`.

## Решение принято

> [!NOTE]
> **Вариант C (подтверждён)**: пересланные сообщения с недоступными forward-атрибутами обрабатываются с `source = "Forwarded"`. EPUB создаётся, source честно отражает статус пересылки.

## Proposed Changes

### Фаза 1: Диагностическое логирование

Перед исправлением нужно убедиться, что проблема именно в отсутствии `fwd_from`. Добавим лог сырого Pyrogram-объекта.

#### [MODIFY] [bot.py](file:///home/spec/work/tg2book/bot.py)

**Изменение 1 — расширенный лог при входе в `handle_message`** (строки 411-424):

```diff
 async def handle_message(self, client: Client, message: Message) -> None:
     logger.info(f"Вход в handle_message: chat_id={message.chat.id}, message_id={message.id}")
-    logger.debug(f"Полный объект сообщения: {message}")
+    # Логируем ключевые атрибуты для диагностики пересылки
+    logger.debug(
+        f"Message attrs: text={bool(message.text)}, caption={bool(message.caption)}, "
+        f"document={bool(message.document)}, "
+        f"forward_date={message.forward_date}, "
+        f"forward_from={getattr(message, 'forward_from', 'MISSING')}, "
+        f"forward_from_chat={getattr(message, 'forward_from_chat', 'MISSING')}, "
+        f"forward_sender_name={getattr(message, 'forward_sender_name', 'MISSING')}"
+    )
```

Это позволит в логах видеть, какие атрибуты реально приходят при пересылке.

---

### Фаза 2: Исправление определения пересылки

#### [MODIFY] [bot.py](file:///home/spec/work/tg2book/bot.py)

**Изменение 2 — удалить несуществующий `forward_origin` из проверки** (строки 416-423):

```diff
-    forward_attrs = [
-        "forward_date", "forward_from", "forward_from_chat",
-        "forward_sender_name", "forward_origin"
-    ]
+    forward_attrs = [
+        "forward_date", "forward_from", "forward_from_chat",
+        "forward_sender_name"
+    ]
```

**Изменение 3 — удалить мёртвые проверки `forward_origin`** (строки 578-579, 597-598):

В `_get_source_info`:
```diff
-    if getattr(message, "forward_origin", None):
-        logger.info(f"Найден атрибут forward_origin: {message.forward_origin}, но он не обрабатывается!")
```

В `_get_post_link`:
```diff
-    if getattr(message, "forward_origin", None):
-        logger.info(f"Найден атрибут forward_origin при попытке создать ссылку: {message.forward_origin}")
```

**Изменение 4 — Улучшить `_get_source_info` для случая «всё None»** (зависит от выбранного варианта A/B/C):

Если выбран **Вариант C** (рекомендуемый):
```diff
     logger.info("Источник не определен, возвращаем 'Unknown Source'")
-    return "Unknown Source"
+    return "Forwarded" if getattr(message, "forward_date", None) else "Unknown Source"
```

> [!NOTE]
> `forward_date` — единственный атрибут, который Telegram **всегда** передаёт для пересланных сообщений (даже с защитой контента). Если `forward_date is not None` — значит это точно пересылка, даже если другие атрибуты скрыты.

---

### Фаза 3: Обновление тестов

#### [MODIFY] [test_bot.py](file:///home/spec/work/tg2book/tests/test_bot.py)

**Изменение 5 — дополнить `mock_message` fixture** (строка 86-99):

```diff
 @pytest.fixture
 def mock_message(self):
     msg = MagicMock()
     msg.reply = AsyncMock()
     msg.reply_document = AsyncMock()
     msg.delete = AsyncMock()
     msg.chat.id = 12345
+    msg.id = 1
     msg.text = None
     msg.caption = None
     msg.document = None
     msg.forward_date = None
     msg.forward_from = None
     msg.forward_from_chat = None
     msg.forward_sender_name = None
     return msg
```

**Изменение 6 — добавить тест для пересылки с privacy protection** (новый тест):

```python
@pytest.mark.asyncio
@patch("services.epub_service.process_text_to_epub", new_callable=AsyncMock)
async def test_handle_forwarded_privacy_protected(self, mock_process, mock_client, mock_message):
    """Forwarded message where Telegram strips all forward info except forward_date."""
    mock_message.text = "Текст из защищённого канала"
    mock_message.forward_date = MagicMock()  # Telegram always sends this
    mock_message.forward_from = None         # stripped by privacy
    mock_message.forward_from_chat = None    # stripped by privacy
    mock_message.forward_sender_name = None  # stripped by privacy
    mock_process.return_value = "<b>Done</b>"

    converter = TelegramToEpub()
    await converter.handle_message(mock_client, mock_message)

    assert mock_message.reply.called
    # Verify process_text_to_epub was called (message was treated as forwarded text)
    mock_process.assert_called_once()
```

**Изменение 7 — добавить тест для обычного текста (не пересылка)**:

```python
@pytest.mark.asyncio
@patch("services.epub_service.process_text_to_epub", new_callable=AsyncMock)
async def test_handle_plain_text_message(self, mock_process, mock_client, mock_message):
    """Plain text message (not forwarded) should still produce EPUB."""
    mock_message.text = "Просто текст от пользователя"
    mock_message.forward_date = None
    mock_process.return_value = "<b>Done</b>"

    converter = TelegramToEpub()
    await converter.handle_message(mock_client, mock_message)

    assert mock_message.reply.called
    mock_process.assert_called_once()
```

## Verification Plan

### Automated Tests

```bash
# Запуск всех тестов через Docker (как в Makefile)
make test

# Или локально, если Docker недоступен
.venv/bin/python -m pytest tests/test_bot.py -v
```

Ожидаемый результат:
- `test_handle_forwarded_message_success` — ✅ PASS
- `test_handle_forwarded_privacy_protected` — ✅ PASS (новый)
- `test_handle_plain_text_message` — ✅ PASS (новый)
- `test_handle_epub_document` — ✅ PASS
- `test_extract_title` — ✅ PASS

### Lint & Typecheck

```bash
make lint
make typecheck
```

### Manual Verification

1. **Пересобрать и перезапустить бота**: `make build`
2. **Переслать сообщение из обычного канала** (без защиты контента) → бот должен создать EPUB с правильным source
3. **Переслать сообщение из канала с «Restrict Saving Content»** → бот должен создать EPUB с source = `"Forwarded"` (или иной, в зависимости от выбранного варианта)
4. **Проверить логи**: `make logs` — убедиться, что диагностический лог показывает forwarding-атрибуты
5. **Отправить обычный текст** (не пересылка) → бот должен создать EPUB с source = `"Unknown Source"`
