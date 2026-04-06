# Phase 0 Test Audit (`test_bot.py`)

## Command behavior
- `test_main_function`
- `test_main_function_no_token`

## Forwarded-message conversion behavior
- `test_handle_message_no_text`
- `test_handle_forwarded_message_no_text`
- `test_handle_forwarded_message_success`
- `test_handle_message_title_is_first_paragraph`
- `test_handle_message_with_caption`
- `test_handle_message_exception`
- `test_handle_forwarded_from_channel`
- `test_get_message_text`
- `test_extract_title_first_paragraph`
- `test_format_message`
- `test_strip_emojis`

## Direct EPUB upload behavior
- `test_handle_epub_document`
- `test_handle_non_epub_document`

## Dropbox-related behavior
- `test_upload_to_dropbox`
- `test_refresh_access_token`
- (косвенно) `test_handle_epub_document`
- (косвенно) `test_handle_forwarded_message_success`

## Gaps this audit confirms
- Нет black-box теста, который проверяет реальные байты EPUB, переданные в Dropbox для текстового сценария.
- Нет black-box теста, который проверяет точное совпадение байтов исходного EPUB и загружаемого файла.
- Нет отдельного baseline-теста на наблюдаемое поведение при сбое Dropbox в основном pipeline.
