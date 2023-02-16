import argparse
import logging
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

import send2trash

BD_FOLDER = Path("D:/Bédés")
RAR_TYPES = ["cbr", "rar"]


def create_cbz(book: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        if (cbz_book := book.with_suffix(".zip")).exists():
            logging.info("CBZ exists. Removing %s", book)
            send2trash.send2trash(book)
            return

        logging.info("Extracting {book.name} to {tmp}")
        try:
            subprocess.run(
                ["unrar", "e", str(book), str(tmp)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            if b"is not RAR archive" in e.stdout:
                logging.warning("%s is not RAR archive", book)
                return
            else:
                logging.warning(e.stdout)
        else:
            logging.info("Creating %s", cbz_book)

            with ZipFile(cbz_book, "w") as zip_:
                for file_ in Path(tmp).iterdir():
                    zip_.write(file_)

            logging.info("Removing %s", book)
            send2trash.send2trash(book)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "folders",
        type=Path,
        help="Folders containing the books",
        default=BD_FOLDER,
        nargs="?",
    )

    args = parser.parse_args()

    folders = args.folders

    logging.basicConfig(level=logging.INFO)

    for type_ in RAR_TYPES:
        for folder in folders:
            for book in folder.rglob(f"*.{type_}"):
                create_cbz(book)


if __name__ == "__main__":
    main()
