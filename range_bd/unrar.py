import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

import send2trash

BD_FOLDER = Path("D:/Bédés")


def main():
    for type_ in ["cbr", "rar"]:
        for book in BD_FOLDER.rglob(f"*.{type_}"):
            tmp = tempfile.mkdtemp()
            print(f"{book.name} to {tmp}")
            if (cbz_book := book.with_suffix(".zip")).exists():
                send2trash.send2trash(book)
                continue
            try:
                subprocess.run(["unrar", "e", str(book), str(tmp)], check=True,
                               capture_output=True)
            except subprocess.CalledProcessError as e:
                if b"is not RAR archive" in e.stdout:
                    print(f"{book} is not a RAR archive")
                    continue
                else:
                    print(e.stdout)
                    raise
            else:
                with ZipFile(cbz_book, "w") as zip_:
                    for file_ in Path(tmp).iterdir():
                        zip_.write(file_)
                send2trash.send2trash(book)


if __name__ == '__main__':
    main()
