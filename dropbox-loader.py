# -*- coding: utf-8 -*-
import dropbox
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def upload_file(local_path, dropbox_path, access_token):
    """
    Загружает файл в ЛЮБУЮ папку Dropbox
    Пример пути: "/Work/Project/docs/file.txt"
    """
    try:
        print(f"[LOADER] Инициализация Dropbox клиента...")
        dbx = dropbox.Dropbox(access_token)
        
        print(f"[LOADER] Локальный файл: {local_path}")
        print(f"[LOADER] Исходный путь Dropbox: {dropbox_path}")
        
        # Проверка существования локального файла
        if not os.path.exists(local_path):
            print(f"[LOADER] ОШИБКА: Локальный файл не найден: {local_path}", file=sys.stderr)
            return False
            
        file_size = os.path.getsize(local_path)
        print(f"[LOADER] Размер локального файла: {file_size} байт")
        
        # Проверка и нормализация пути
        if not dropbox_path.startswith('/'):
            dropbox_path = '/' + dropbox_path
            print(f"[LOADER] Путь нормализован: {dropbox_path}")
        else:
            print(f"[LOADER] Путь уже корректный: {dropbox_path}")
            
        print(f"[LOADER] Финальный путь в Dropbox: {dropbox_path}")
        print(f"[LOADER] Начинаем загрузку...")
        
        with open(local_path, "rb") as f:
            file_content = f.read()
            print(f"[LOADER] Файл прочитан, размер: {len(file_content)} байт")
            
            result = dbx.files_upload(
                file_content,
                dropbox_path,
                mode=dropbox.files.WriteMode.overwrite
            )
            
            print(f"[LOADER] Загрузка завершена успешно!")
            print(f"[LOADER] Dropbox file ID: {result.id}")
            print(f"[LOADER] Dropbox file size: {result.size}")
            print(f"[LOADER] Dropbox path confirmed: {result.path_display}")
            print(f"Файл загружен в: {result.path_display}")
            return True
            
    except dropbox.exceptions.ApiError as e:
        print(f"[LOADER] Ошибка Dropbox API: {e.error}", file=sys.stderr)
        print(f"[LOADER] Тип ошибки: {type(e.error)}", file=sys.stderr)
        if hasattr(e.error, 'get_upload_error'):
            print(f"[LOADER] Детали ошибки загрузки: {e.error.get_upload_error()}", file=sys.stderr)
    except FileNotFoundError as e:
        print(f"[LOADER] Файл не найден: {e}", file=sys.stderr)
    except PermissionError as e:
        print(f"[LOADER] Нет прав доступа к файлу: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[LOADER] Неожиданная ошибка: {e}", file=sys.stderr)
        print(f"[LOADER] Тип ошибки: {type(e)}", file=sys.stderr)
    return False

import argparse

def main():
    parser = argparse.ArgumentParser(description="Загрузка файла в Dropbox.")
    parser.add_argument("local_path", help="Путь к локальному файлу")
    parser.add_argument("dropbox_path", help="Полный путь в Dropbox")
    parser.add_argument("--access-token", help="Доступный токен Dropbox", required=True)
    args = parser.parse_args()

    print(f"[LOADER] Запуск с параметрами:")
    print(f"[LOADER] local_path: {args.local_path}")
    print(f"[LOADER] dropbox_path: {args.dropbox_path}")
    print(f"[LOADER] access_token: {'***' + args.access_token[-3:] if len(args.access_token) > 3 else '***'}")

    success = upload_file(args.local_path, args.dropbox_path, args.access_token)
    if success:
        print(f"[LOADER] Успешно завершено!")
    else:
        print(f"[LOADER] Завершено с ошибкой!", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()