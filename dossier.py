import shutil
from pathlib import Path
from zipfile import ZipFile

BD_FOLDERS = [
    r"D:\Bédés\Historique\Il était une fois\La vie",
    r"D:\Bédés\Historique\Il était une fois\L'homme",
    r"D:\Bédés\Historique\Buck Danny - [1 à 50 + 9 HS]\Hors Série",
    r"D:\Bédés\Historique\Buck Danny - [1 à 50 + 9 HS]",
    r"D:\Bédés\Manga\Manga\Angelheart",
    r"D:\Bédés\Manga\Manga\Cat'SEye - [Tsukasa Hojo 1 à 10]",
    r"D:\Bédés\Manga\Manga\City Hunter",
    r"D:\Bédés\Manga\Manga\DNA",
    r"D:\Bédés\Manga\Manga\Dragon Ball",
    r"D:\Bédés\Manga\Manga\Ghost in the shell",
    r"D:\Bédés\Manga\Manga\Hoshin",
    r"D:\Bédés\Manga\Manga\Hunter X Hunter\Hunter X Hunter - T17 a 18",
    r"D:\Bédés\Manga\Manga\Ken le Survivant",
    r"D:\Bédés\Manga\Manga\Kenshin",
    r"D:\Bédés\Manga\Manga\Le gardien des ames\Yuyu Hakusho - Le gardien des ames",
    r"D:\Bédés\Manga\Manga\Le gardien des ames - [Yuyu Hakusho]",
    r"D:\Bédés\Manga\Manga\Domu",
    r"D:\Bédés\Manga\Manga\Ranma- [Rumiko Takahashi 1 à 38]",
    r"D:\Bédés\Manga\Manga\Dragon Ball\11 tomes (jpg)",

]
TRASH_FOLDER = Path(r"D:\Bédés\Corbeille")

IMG_FILETYPES = {".png", ".jpg", ".gif"}
for folder in BD_FOLDERS:
    for path in Path(folder).iterdir():
        cbz_path = path.with_suffix(".cbz")
        if not path.is_dir():
            continue

        has_img = False
        for img_path in path.iterdir():
            if img_path.suffix.lower() in IMG_FILETYPES:
                has_img = True

        if not has_img:
            continue

        print(path)
        with ZipFile(cbz_path, "w") as cbz_file:
            for img_path in path.iterdir():
                if img_path.suffix.lower() in IMG_FILETYPES:
                    cbz_file.write(str(img_path), img_path.name)
                    new_path = TRASH_FOLDER / "/".join(img_path.parts[1:])
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(img_path), new_path)
