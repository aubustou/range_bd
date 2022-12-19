import shutil
from pathlib import Path
from zipfile import ZipFile

BD_FOLDERS = [
    r"D:\Bédés\RAHAN (1DVD)",
    r"D:\Bédés\Tif et Tondu",
    r"D:\Bédés\toto",

]
TRASH_FOLDER = Path(r"D:\Bédés\Corbeille")

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
                    new_path = TRASH_FOLDER / "/".join(img_path.parts[1:])
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(img_path), new_path)

    for folder in folders:
        recurse(folder)
    folders = {}
    img_folders = {}


def main():
    for folder in BD_FOLDERS:
        recurse(Path(folder))


if __name__ == "__main__":
    main()
