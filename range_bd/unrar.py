import argparse
import logging
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

import send2trash

BD_FOLDER = Path("D:/Bédés")
RAR_TYPES = ["[cC][bB][rR]", "[rR][aA][rR]"]


def create_cbz(book: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        if (cbz_book := book.with_suffix(".zip")).exists():
            logging.info("CBZ exists. Removing %s", book)
            send2trash.send2trash(book)
            return cbz_book

        logging.info("Extracting %s to %s", book, tmp)
        try:
            subprocess.run(
                ["unrar", "e", str(book), str(tmp)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            if b"is not RAR archive" in e.stdout:
                logging.warning("%s is not RAR archive", book)
                raise
            else:
                logging.warning(e.stdout)
                raise
        else:
            logging.info("Creating %s", cbz_book)

            with ZipFile(cbz_book, "w") as zip_:
                for file_ in Path(tmp).iterdir():
                    zip_.write(file_)

            logging.info("Removing %s", book)
            send2trash.send2trash(book)

            book = cbz_book
    return book


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

    unrar(folders)


if __name__ == "__main__":
    main()
