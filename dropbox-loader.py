import dropbox
import sys

def upload_file(local_path, dropbox_path):
    """
    Загружает файл на Dropbox с перезаписью существующего.
    Требования к путям:
    - local_path: должен существовать
    - dropbox_path: должен начинаться с /
    """
    try:
        dbx = dropbox.Dropbox("<ACCESS_TOKEN>")  # Замените на свой токен
        with open(local_path, "rb") as f:
            dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)
        print(f"Успешно загружено: {local_path} -> {dropbox_path}")
        return True
    except dropbox.exceptions.ApiError as e:
        print(f"Ошибка Dropbox: {e.error}", file=sys.stderr)
    except Exception as e:
        print(f"Фатальная ошибка: {e}", file=sys.stderr)
    return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Использование: {sys.argv[0]} <локальный_файл> <путь_на_dropbox>", file=sys.stderr)
        print("Пример: python script.py file.txt '/remote/file.txt'", file=sys.stderr)
        sys.exit(1)
        
    upload_file(sys.argv[1], sys.argv[2])