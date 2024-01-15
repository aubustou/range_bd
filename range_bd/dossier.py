from __future__ import annotations

import shutil
from pathlib import Path
from zipfile import ZipFile

from send2trash import send2trash

BD_FOLDERS = [
    r"M:\Bédés\usb1",
]

IMG_FILETYPES = {".png", ".jpg", ".gif"}


def recurse(top_path: Path):
    folders = set()
    img_folders = set()
    for subpath in top_path.iterdir():
        if subpath.is_dir():
            folders.add(subpath)
        elif subpath.suffix.lower() in IMG_FILETYPES:
            img_folders.add(subpath.parent)

    for subpath in img_folders:
        print(subpath)
        cbz_path = subpath.with_suffix(".cbz")
        if cbz_path.exists():
            continue
        with ZipFile(cbz_path, "w") as cbz_file:
            for img_path in subpath.iterdir():
                if img_path.suffix.lower() in IMG_FILETYPES:
                    cbz_file.write(str(img_path), img_path.name)
                    send2trash(str(img_path))

    for folder in folders:
        recurse(folder)


def main():
    for folder in BD_FOLDERS:
        recurse(Path(folder))


if __name__ == "__main__":
    main()
