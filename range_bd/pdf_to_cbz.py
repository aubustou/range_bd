import argparse
from pathlib import Path
import re
import time

from zipfile import ZipFile
import subprocess
import glob
import send2trash

BDS = []
BD_FOLDER = Path(r"D:\Bédés")
FILENAME_PATTERN = re.compile(r"(.*)_Page\.pdf-\d+\.(?:png|jpg)")
MAX_PER_RUN = 10
DPI = 300


def compress(bd_path: Path, output_folder: Path | None = None) -> list[Path]:
    bd_name = bd_path.stem

    cbz_file_path = ((output_folder or bd_path.parent) / bd_name).with_suffix(".zip")

    images: list[Path] = []
    for img_path in bd_path.parent.glob(glob.escape(bd_name) + "_Page.pdf-*.png"):
        images.append(img_path)

    if not cbz_file_path.exists():
        print(f"To CBZ: {cbz_file_path}")

        with ZipFile(cbz_file_path, "w") as cbz_file:
            for image in images:
                cbz_file.write(str(image), image.name)
    else:
        print(f"CBZ already exists: {cbz_file_path}")

    return images


def convert_to_img(pdf_file: Path) -> Path:
    print(f"To IMG: {pdf_file}")
    subprocess.run(
        [
            "pdftoppm",
            "-r",
            str(DPI),
            "-png",
            str(pdf_file),
            str(pdf_file.with_stem(pdf_file.stem + "_Page")),
        ],
        check=True,
    )
    return pdf_file


def remove_images(images: list[Path], to_trash: bool = True) -> None:
    try:
        if to_trash:
            send2trash.send2trash(images)
        else:
            for image in images:
                image.unlink()
    except FileNotFoundError:
        pass


def convert_from_list(bds: list[str]) -> None:
    for bd in bds:
        bd_path = Path(bd)
        images = compress(bd_path)
        remove_images(images)


def convert_loop() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_folder", type=Path, help="Folder containing BDs")
    parser.add_argument(
        "output_folder",
        type=Path,
        help="Folder to output CBZs",
    )

    args = parser.parse_args()
    input_folder = args.input_folder
    output_folder = args.output_folder

    while True:
        for pdf_file in input_folder.rglob("*.pdf"):
            bd_path = convert_to_img(pdf_file)
            images = compress(bd_path, output_folder)
            remove_images(images)
            pdf_file.move_to(output_folder / pdf_file.name)

        print("Waiting for new files...")
        time.sleep(30)


def main():
    if BDS:
        return convert_from_list(BDS)

    for index, pdf_file in enumerate(BD_FOLDER.rglob("*.pdf")):
        bd_path = convert_to_img(pdf_file)
        images = compress(bd_path)
        remove_images(images)

        if index > MAX_PER_RUN:
            break


if __name__ == "__main__":
    main()
