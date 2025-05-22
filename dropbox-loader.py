# -*- coding: utf-8 -*-
import dropbox
import sys

def upload_file(local_path, dropbox_path):
    """
    Uploads file to Dropbox with overwrite mode
    local_path: must exist locally
    dropbox_path: must start with '/'
    """
    try:
        dbx = dropbox.Dropbox("sl.u.AFsiN39lQLVFZCCg-FbdRtwUQwyHIcwo_EHGdxV6VvXtUZwcWVX1m6zW1ZIcj5aShoIwPOzLWqBFXe7TnEQi2osguQd3il80i-NuW8eLFDX68intrPYAe1r2-JXbCdlJvf96_NgbeLbhnQb_veYvj3H1Asdvy32ufAVzqNmZ9ErzO4dz-uhzUevfdYKDwNHpfDEn4zQy_NNTKJ0PMr6doVZsyWzfKoL4CqfCFmIWOolwiJzQSXOcEb1NvNUovgS2hwGMwrUVoTRgF8jjekYHZMd5d1560ltNCA3-m9KnqgvaVKQqqn28T9ldIzbTiW45UtrdtTfH2QrKIVniYFwlUUJJ_mn-Q2kY4Yu8zTJVsesPtBDUYua3ywmn9gzCHwfzdfnTzPGkFuKXFb31ddxqobxtGnjFPv970Tuj651Np5vhg7-5g-Rh2sz8VhzkKtMGuaqWhbfLobii1Th78RPaJJPexEZlVXr3MRm-mYsambWb47MaOAD8gQDCpOtPiRpuJolblFbZO_sUmXFsFIR2AKJoSnHGUbZ7avx62OySshdoMj08Mtt1LLLOg09NizWTd3e27iBWendS-K-u24JtATUYLAKwwyUWMqqrJ8DBCyutJJU3lEhtuCgNJZnjVYtguMWm_ixGgpvF_W5t4jAi-J_Wk01BEAOMYA4XmbK85v1erNToa0cjYJGSPyT1xn79qvohiynyUkjcVTjJc6WW1mQgY0dEsHHaeqtQ_qs9IyF2m8ZGElreWZpkTts-3F-VKUbeR5MGcYK3Nkn9Rbg4TQDa82C6RCAdgim1pQNJlOz66fhSRit03-_vYsghP5LdO-1e91KBYFuC0w8gkgStzoO7L2RctOhxmqYV_Kvx7RMVzWoMZWb_qYkfuMGnDadnPM7GFISn-9chG8q0xJXN0iHw-f8-pOsQUjTqMH4EzKgO-H-Z5z9b7L6Kphxl6axEktENqsvmGLC8AnqcUYMuaXbGIeeDzuS50y_biuOI4LPeDFdPFyQ2aqejb1EnmCIfP64opLPdDzqdQtOBp-rY5CH0s1x8hkaG-h9-p6Cm_jqnkI7vokAX_tBkFLnVnv2kKcUFVtqwQ0EU_JlXUQE374Epqzd5pNLiGDyAcKQf271XzCHNfFle_chrIJacIuJSmrbyDlAAkYwgVvIC0ecgY1X2B3hOPyhwTXhVpqc5tNAX3aoJLi09TJFmFx2xND28aFjqZPKm2PyHeN1aicYApr9AGcabPP8nadbO911lIUaWnUOP0fZnto_oFLy426-mjfs")
        with open(local_path, "rb") as f:
            dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)
        print("Upload successful: {} -> {}".format(local_path, dropbox_path))
        return True
    except dropbox.exceptions.ApiError as e:
        print("Dropbox error: {}".format(e.error), file=sys.stderr)
    except Exception as e:
        print("Fatal error: {}".format(e), file=sys.stderr)
    return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: {} <local_file> <dropbox_path>".format(sys.argv[0]), file=sys.stderr)
        print("Example: python dropbox-loader.py file.txt '/remote/file.txt'", file=sys.stderr)
        sys.exit(1)
        
    upload_file(sys.argv[1], sys.argv[2])