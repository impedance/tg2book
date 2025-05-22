# -*- coding: utf-8 -*-
import dropbox
import sys

def upload_file(local_path, dropbox_path):
    """
    Загружает файл в ЛЮБУЮ папку Dropbox
    Пример пути: "/Work/Project/docs/file.txt"
    """
    try:
        dbx = dropbox.Dropbox("sl.u.AFtS6VaDRDHFbQ_67o0FdDw_MjFY4ESyxdW1ke3AwToFlo0DrYRojkJ-uQhN-R1WBgLKt0Z2Nkc9VkFzQU6oTv3ycGzI1LansLGlIVZO6-I3PXbYLkSB4q4A331Dsg_98lAZlfImeSM2GjbnvpymH5n0gzGUIFKvPg3Q3mu3Z4Ic7AOqk03tqWe9NBJ4xbrze2YcBZ4h5TdRdcWP7aCH9UsDOzNwV7WTA2yEb38E38tm0fWf26sM7R2NkFKL6wmbQaRPyxxkUHpBHeUtq227LSAfBpQjhcXcmP72o5vR3yuM2UICqyQgquitXn0-jtdVCk_ihsxAt4OJ7jxxM3H1Pz4fYbeZVcLzfHiLyTCy7lYg0pHR4AnzCxwiFWgRbD_SaQyp37wY_xNsMfaw7fCs11lIAsUKmmGHltNKNcsMeJaTBM36-lzCffeCDlPmx4vCPGeHdOwe6KM06o_ZS6cmvCNTIC7kcvp9iQ5eb0PMH1Sna5r2BwI-gceRsL1911tFwrrj00F7VlUoG5TMeklsJ6NMhyiJtrOYCrRVPX59MDxrH99pMGsLDJ1SLw_iYSEoybskxMlDkJU1yWefzOtCtDYw6uo6KBZmaQ8eQZ67C5Hlu2yeiuWlv3uadUy_OgJw9NXlq33sdUCooFeAn7ywGyADNls0kAfPMB_jmmBrQrZVB2SNoApkqUwsBUHdS-jCAWA9kAzmY5q_xi4FplQ7UN8nWxBSb--eyo5kEfLuPOzL0LxDfChl1-KU3ae2WOx04lzBjwPZjUIaRA4qDgRapq1Letbk6Q1GyXPHIWQuTbxlzTKp6Z45BPgSvUby7EFTItTbwhDEkCwZNB1Kev4qv40BD4sQYA_PTyKhUAYscIwWRRSGt9S5XZAFPf4kzQ9Vc_xTQ_FymNyeHeUASzVVY9EFNZQhONWbowad0I0pRVVPIVaVl7i7yBSxr9SZDUj9DavsM9EEm4aBKiLwqo5suFrbkl58xBQNjZ3HJgXQQyPTzoWQt8Et9K9e9y3JDdDGpNiVE-f95ET_XPJbinUNx_nE6NVrH7UoKwkFfuU7sw0RRJL_lq23HZmo-_Gpn5MCzQi6yXNTWzRDoXr62UpvSq9y8XdbPkqum_DwB5mbnoR70do37AiRERslUIbESbDlkFEIqstGlh7C1SKDZAJOcsBPnU3S8E51WaYW74o5JmBP3nZoF_6vVVIFYzvTNhPZ72BfzhczAXHtcocNVXaJT-4qObrvK9w7BIikiCdInRLvBDPFpt1SH6EF0SSdXaxTA0U")  # Токен с полным доступом
        
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