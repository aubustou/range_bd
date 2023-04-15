from __future__ import annotations

import argparse
import atexit
import glob
import logging
import re
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, TypedDict, TypeVar
from zipfile import ZipFile

from PIL import Image
from send2trash import send2trash

from range_bd.unrar import create_cbz

logger = logging.getLogger("Sanitizer")
IGNORED_FOLDERS = ["__MACOSX", "._.DS_Store", ".DS_Store", "@eaDir"]

ZIP_SUFFIX = ".zip"
CBZ_SUFFIX = ".cbz"
CBR_SUFFIX = ".cbr"
RAR_SUFFIX = ".rar"
PDF_SUFFIX = ".pdf"
EPUB_SUFFIX = ".epub"


SUFFIXES = [ZIP_SUFFIX, CBZ_SUFFIX, CBR_SUFFIX, RAR_SUFFIX, PDF_SUFFIX, EPUB_SUFFIX]

FOLLOWED_FOLDERS: list[Path]
MANAGED_FOLDER: Path

SUCCESS_FOLDER: Path

EPUB_FOLDER: Path


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    _format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + _format + reset,
        logging.INFO: grey + _format + reset,
        logging.WARNING: yellow + _format + reset,
        logging.ERROR: red + _format + reset,
        logging.CRITICAL: bold_red + _format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)

        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def remove_mac_folder_from_zip(path: Path) -> Path:
    with ZipFile(path, "r") as zip_:
        if any("__MACOSX" in name for name in zip_.namelist()):
            logger.info("Removing __MACOSX folder from %s", path)

            new_path = path.with_stem(path.stem + "_REMOVE_MACOSX")

            with ZipFile(new_path, "w") as new_zip:
                for name in zip_.namelist():
                    if "__MACOSX" in name:
                        continue
                    new_zip.writestr(name, zip_.read(name))
            path.unlink()
            new_path.rename(path)
    return path


NAME_PATTERN = re.compile(r"[\s\-\._\()]+(?:T|tome|Tome)[\s\-\._]*(\d+)[\s\-\._\)]+")

JUNK = [
    r"^BD ",
    r"  - Complet - $",
    r"One Shot",
    r"^BD-FR-",
    r".FRENCH.HYBRiD.eBook-PRESSECiTRON$",
    r".FRENCH.HYBRiD.COMiC.CBZ.eBook-TONER",
    r" \[Digital\-[0-9]{4}\] \([0-9a-zA-Z-_\d]+\)$",
    r"^\[BD Fr OS\] ",
    r"^\[BD Fr\] - ",
    r"^\[BD Fr\] ",
    r"^\[BD\]-* ",
    r"^BD-*\s+",
    r"^BD.FR.-.",
    r"^BDFR -\d*",
    r"\d*\[One-Shot\]",
]
JUNK_PATTERNS = [re.compile(x) for x in JUNK]


def clean_name(path: Path) -> Path:
    # Ensure no space at the end or beginning of the name
    path = path.rename(path.with_stem(path.stem.strip()))

    for pattern in JUNK_PATTERNS:
        path = path.rename(path.with_stem(pattern.sub("", path.stem)))

    # Regex in order to change T01 to #01
    if match := NAME_PATTERN.search(path.stem):
        number = match.group(1)
        path = path.rename(path.with_stem(NAME_PATTERN.sub(f" #{number} ", path.stem)))

    return path


def natural_sort(files: list[Path]) -> list[Path]:
    def convert(text: str) -> int | str:
        return int(text) if text.isdigit() else text

    def alphanum_key(key: Path) -> list[int | str]:
        return [convert(c) for c in re.split("([0-9]+)", key.stem)]

    return sorted(files, key=alphanum_key)


def rename_images_in_zip_file(path: Path) -> Path:
    tmp_path = path.with_stem(path.stem + "_TMP")

    with ZipFile(path) as zip_:
        files = natural_sort([Path(name) for name in zip_.namelist()])

        for index, file_ in enumerate(files):
            if file_.suffix.lower() not in [".jpg", ".jpeg", ".png", ".webp"]:
                continue

            new_name = f"P{index:05d}{file_.suffix}"
            logger.debug("Renaming %s to %s", file_, new_name)

            with ZipFile(tmp_path, "a") as new_zip:
                new_zip.writestr(new_name, zip_.read(str(file_)))

    if tmp_path.exists():
        send2trash(path)
        tmp_path.rename(path)

    return path


def remove_parents_from_path(path: Path, root_folder: Path) -> Path:
    return Path(*path.parts[len(root_folder.parts) :])


def recurse_remove_empty_folder(folder: Path) -> None:
    for child in folder.iterdir():
        if child.is_dir() and child.name not in IGNORED_FOLDERS:
            recurse_remove_empty_folder(child)

    if not any(x for x in folder.iterdir() if x.name not in IGNORED_FOLDERS):
        logger.info("Removing empty folder %s", folder)
        shutil.rmtree(folder)


def remove_empty_folders(folders: list[Path]) -> None:
    for folder in folders:
        recurse_remove_empty_folder(folder)


def rename_cbz(file_: Path) -> Path:
    if file_.suffix.lower() != CBZ_SUFFIX:
        return file_

    logger.info("Renaming %s", file_)
    new_path = file_.with_suffix(ZIP_SUFFIX)
    shutil.move(file_, new_path)

    return new_path


def unrar(file_: Path) -> Path:
    if file_.suffix.lower() not in {RAR_SUFFIX, CBR_SUFFIX}:
        return file_
    else:
        logger.info("Unrar %s", file_)
        return create_cbz(file_)


def remove_mac_folders(file_: Path) -> Path:
    if file_.suffix.lower() != ZIP_SUFFIX:
        return file_
    else:
        return remove_mac_folder_from_zip(file_)


def rename_images_in_zip_files(file_: Path) -> Path:
    if file_.suffix.lower() != ZIP_SUFFIX:
        return file_
    else:
        return rename_images_in_zip_file(file_)


def change_tome_number_in_files(file_: Path) -> Path:
    return clean_name(file_)


# PDF conversion
DPI = 300
MAX_HEIGHT = 4000


def convert_to_img(pdf_file: Path, output_folder: Path) -> Path:
    logger.info("Converting %s to images in output %s", pdf_file, output_folder)
    subprocess.run(
        [
            "pdftoppm",
            "-scale-to",
            str(MAX_HEIGHT),
            "-r",
            str(DPI),
            "-png",
            str(pdf_file),
            str(output_folder / pdf_file.name),
        ],
        check=True,
    )
    return pdf_file


def compress(bd_path: Path, image_folder: Path) -> Path:
    cbz_file_path = bd_path.with_suffix(".zip")

    logger.info("Creating %s", cbz_file_path)

    with ZipFile(cbz_file_path, "w") as cbz_file:
        for image_path in image_folder.glob("*.png"):
            new_path = image_path.with_suffix(".jpg")

            image = Image.open(str(image_path))
            buffer = resize_jpg(image)
            cbz_file.writestr(str(new_path), buffer.getvalue())

    return cbz_file_path


def convert_pdf(file_: Path) -> Path:
    if file_.suffix.lower() != PDF_SUFFIX:
        return file_

    with TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        convert_to_img(file_, tmp_dir)
        new_path = compress(file_, tmp_dir)
    return new_path


# JPG resize
EXPECTED_DPI = 120
EXPECTED_HEIGHT = 2388
JPG_QUALITY = 90
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def resize_jpg(img: Image.Image) -> BytesIO:
    buffer = BytesIO()
    width, height = img.size
    if height > EXPECTED_HEIGHT:
        new_height = EXPECTED_HEIGHT
        new_width = int((new_height / height) * width)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    if img.mode in {"RGBA", "P"}:
        img = img.convert("RGB")
        # some minor case, resulting jpg file is larger one, should meet your expectation

    img.save(
        buffer,
        format="JPEG",
        optimize=True,
        quality=JPG_QUALITY,
        dpi=(EXPECTED_DPI, EXPECTED_DPI),
    )
    return buffer


def resize_jpg_in_zip(path: Path) -> Path:
    if not path.suffix.lower() == ZIP_SUFFIX:
        return path

    with ZipFile(path, "r") as zip_:
        logger.info("Resize images from %s", path)

        new_path = path.with_stem(path.stem + "_RESIZED")

        with ZipFile(new_path, "w") as new_zip:
            for name in zip_.namelist():
                data = zip_.read(name)

                if Path(name).suffix.lower() in IMAGE_EXTENSIONS:
                    image = Image.open(BytesIO(data))
                    buffer = resize_jpg(image)
                    new_zip.writestr(name, buffer.getvalue())
                else:
                    new_zip.writestr(name, data)
    path.unlink()
    new_path.rename(path)

    return path


ACTIONS: list[Callable[[Path], Path]] = [
    change_tome_number_in_files,
    rename_cbz,
    unrar,
    remove_mac_folders,
    convert_pdf,
    rename_images_in_zip_files,
    resize_jpg_in_zip,
]


def per_file_pipeline(
    file_: Path,
    remote_folder: Path,
    success_folder: Path,
    failure_folder: Path,
) -> None:
    if not file_.is_file():
        return

    if file_.suffix.lower() not in SUFFIXES:
        return

    former_path = file_

    relative_path = remove_parents_from_path(file_, remote_folder)

    with TemporaryDirectory() as tmp_dir:
        working_folder = Path(tmp_dir)

        working_path = working_folder / relative_path
        working_path.parent.mkdir(exist_ok=True, parents=True)
        logger.info("Move file %s to new path %s", file_, working_path)
        file_ = shutil.copy(file_, working_path)

        success = False
        new_path: Path | None = None
        for index, action in enumerate(ACTIONS):
            try:
                file_ = action(file_)
            except Exception as e:
                logger.error("Error running %s on %s: %s", action.__name__, file_, e)
                success = False
                new_path = (
                    failure_folder / f"{index:02d}_{action.__name__}" / relative_path
                ).with_name(file_.name)
                break
            else:
                success = True

        if success:
            logger.info("Success running pipeline on %s", file_)
            new_path = (success_folder / relative_path).with_name(file_.name)

        if new_path is None:
            raise RuntimeError("new_path should not be None")

        new_path.parent.mkdir(exist_ok=True, parents=True)
        logger.info("Move file %s back to remote %s", file_, new_path)
        if new_path.exists():
            raise RuntimeError(f"File {new_path} already exists")

        try:
            file_ = shutil.move(file_, new_path)
        except Exception:
            raise
        else:
            logger.info("Remove former file %s", former_path)
            send2trash(str(former_path))


def main() -> None:
    logger = logging.getLogger("Sanitizer")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

    handler.setFormatter(CustomFormatter())

    logger.addHandler(handler)

    working_dir = Path.cwd()

    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, default=working_dir, nargs="?")
    parser.add_argument("--debug", action="store_true", default=False)
    args = parser.parse_args()

    path = args.path
    debug = args.debug

    global EPUB_FOLDER, MANAGED_FOLDER, SUCCESS_FOLDER

    MANAGED_FOLDER = path.parent / "Bédés gérées"
    MANAGED_FOLDER.mkdir(exist_ok=True)
    SUCCESS_FOLDER = MANAGED_FOLDER / "success"
    SUCCESS_FOLDER.mkdir(exist_ok=True)
    EPUB_FOLDER = path.parent / "EPUB"
    EPUB_FOLDER.mkdir(exist_ok=True)

    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob("*"))

    atexit.register(remove_empty_folders, [path, MANAGED_FOLDER, SUCCESS_FOLDER])

    if debug:
        parallel = False
        handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        parallel = True

    if parallel:
        with ProcessPoolExecutor() as executor:
            futures = [
                executor.submit(
                    per_file_pipeline, file_, path, SUCCESS_FOLDER, MANAGED_FOLDER
                )
                for file_ in files
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.error("Error running pipeline: %s", exc)
                    continue
    else:
        for file_ in files:
            try:
                if not file_.is_file():
                    continue

                per_file_pipeline(
                    file_,
                    remote_folder=path,
                    success_folder=SUCCESS_FOLDER,
                    failure_folder=MANAGED_FOLDER,
                )
            except OSError as exc:
                logger.error("Error reading %s: %s", file_, exc)
                continue


if __name__ == "__main__":
    main()
