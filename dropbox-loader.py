# -*- coding: utf-8 -*-
import dropbox
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def upload_file(local_path, dropbox_path):
    """
    Загружает файл в ЛЮБУЮ папку Dropbox
    Пример пути: "/Work/Project/docs/file.txt"
    """
    try:
        dbx_token = os.getenv("DROPBOX_TOKEN")
        if not dbx_token:
            print("Ошибка: Не найден токен Dropbox в файле .env", file=sys.stderr)
            return False
        dbx = dropbox.Dropbox(dbx_token)
        
        # Проверка и нормализация пути
        if not dropbox_path.startswith('/'):
            dropbox_path = '/' + dropbox_path
            
        with open(local_path, "rb") as f:
            dbx.files_upload(
                f.read(),
                dropbox_path,
                mode=dropbox.files.WriteMode.overwrite
            )
            print(f"Файл загружен в: {dropbox_path}")
            return True
            
    except dropbox.exceptions.ApiError as e:
        print(f"Ошибка Dropbox: {e.error}", file=sys.stderr)
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
    return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python script.py <локальный_файл> <полный_путь_на_dropbox>")
        print('Пример: python script.py report.pdf "/Финансы/2023/Отчеты/report.pdf"')
        sys.exit(1)
    
    upload_file(sys.argv[1], sys.argv[2])
