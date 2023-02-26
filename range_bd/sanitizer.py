from __future__ import annotations

import argparse
import logging
import re
import shutil
from pathlib import Path
from typing import Callable, TypedDict
from zipfile import ZipFile

from send2trash import send2trash
from unrar import create_cbz

IGNORED_FOLDERS = ["__MACOSX", "._.DS_Store", ".DS_Store", "@eaDir"]

ZIP_SUFFIX = "*.[zZ][iI][pP]"
CBZ_SUFFIX = "*.[cC][bB][zZ]"
CBR_SUFFIX = "*.[cC][bB][rR]"
RAR_SUFFIX = "*.[rR][aA][rR]"
PDF_SUFFIX = "*.[pP][dD][fF]"
EPUB_SUFFIX = "*.[eE][pP][uU][bB]"
SUFFIXES = [ZIP_SUFFIX, CBZ_SUFFIX, CBR_SUFFIX, RAR_SUFFIX, PDF_SUFFIX, EPUB_SUFFIX]

FOLLOWED_FOLDERS: list[Path]
MANAGED_FOLDER: Path

SUCCESS_FOLDER: Path

EPUB_FOLDER: Path


class ActionReturn(TypedDict):
    success: list[Path]
    failed: list[Path]


def initiate(folders: list[Path]) -> ActionReturn:
    global FOLLOWED_FOLDERS

    files: list[Path] = []
    for folder in folders:
        for suffix in SUFFIXES:
            files.extend(folder.rglob(suffix))
    return ActionReturn(success=files, failed=[])


def rename_cbz(folders: list[Path]) -> ActionReturn:
    result = ActionReturn(success=[], failed=[])

    for folder in folders:
        for cbz in folder.rglob(CBZ_SUFFIX):
            logging.info("Renaming %s", cbz)
            new_path = cbz.with_suffix(".cbz")
            try:
                cbz.rename(new_path)
            except Exception as e:
                logging.error("Error renaming %s: %s", cbz, e)
                result["failed"].append(cbz)
            else:
                result["success"].append(new_path)

    return result


def remove_mac_folders(folders: list[Path]) -> ActionReturn:
    result = ActionReturn(success=[], failed=[])

    for folder in folders:
        for path in folder.rglob(ZIP_SUFFIX):
            try:
                remove_mac_folder_from_zip(path)
            except Exception as e:
                logging.error("Error removing __MACOSX folder from %s: %s", path, e)
                result["failed"].append(path)
            else:
                result["success"].append(path)

    return result


def unrar(folders: list[Path]) -> ActionReturn:
    result = ActionReturn(success=[], failed=[])

    for type_ in [CBR_SUFFIX, RAR_SUFFIX]:
        for folder in folders:
            for book in folder.rglob(type_):
                try:
                    book = create_cbz(book)
                except Exception as e:
                    logging.error("Error creating cbz from %s: %s", book, e)
                    result["failed"].append(book)
                else:
                    result["success"].append(book)

    return result


def remove_mac_folder_from_zip(path: Path) -> Path:
    with ZipFile(path, "r") as zip_:
        if any("__MACOSX" in name for name in zip_.namelist()):
            logging.info("Removing __MACOSX folder from %s", path)

            new_path = path.with_stem(path.stem + "_REMOVE_MACOSX")

            with ZipFile(new_path, "w") as new_zip:
                for name in zip_.namelist():
                    if "__MACOSX" in name:
                        continue
                    new_zip.writestr(name, zip_.read(name))
            path.unlink()
            new_path.rename(path)
            path = new_path
    return path


NAME_PATTERN = re.compile(r" T(\d+) ")


def clean_name(path: Path) -> Path:
    for pattern, replacement in [
        ("(c2c) ", ""),
        ("One Shot", ""),
    ]:
        path = path.rename(path.with_name(path.name.replace(pattern, replacement)))

    # Regex in order to change T01 to #01
    if match := NAME_PATTERN.search(path.name):
        number = match.group(1)
        path = path.rename(
            path.with_name(path.name.replace(f"T{number}", f"#{number}"))
        )

    return path


def remove_useless_junk_from_name(folders: list[Path]) -> ActionReturn:
    result = ActionReturn(success=[], failed=[])

    for folder in folders:
        for suffix in SUFFIXES:
            for path in folder.rglob(suffix):
                try:
                    clean_name(path)
                except Exception as e:
                    logging.error(
                        "Error removing useless junk from name from %s: %s", path, e
                    )
                    result["failed"].append(path)
                else:
                    result["success"].append(path)

    return result


def move_epub(folders: list[Path]) -> ActionReturn:
    result = ActionReturn(success=[], failed=[])

    for folder in folders:
        for path in folder.rglob(EPUB_SUFFIX):
            try:
                new_path = EPUB_FOLDER / remove_parents_from_path(path, folder)
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(path, new_path)
            except Exception as e:
                logging.error("Error moving %s: %s", path, e)
                result["failed"].append(path)

    return result


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
            if file_.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
                continue

            new_name = f"P{index:05d}{file_.suffix}"
            logging.info("Renaming %s to %s", file_, new_name)

            with ZipFile(tmp_path, "a") as new_zip:
                new_zip.writestr(new_name, zip_.read(str(file_)))

    send2trash(path)
    tmp_path.rename(path)

    return path


def rename_images_in_zip_files(folders: list[Path]) -> ActionReturn:
    result = ActionReturn(success=[], failed=[])

    for folder in folders:
        for path in folder.rglob(ZIP_SUFFIX):
            try:
                rename_images_in_zip_file(path)
            except Exception as e:
                logging.error("Error renaming images in %s: %s", path, e)
                result["failed"].append(path)
            else:
                result["success"].append(path)

    return result


def remove_parents_from_path(path: Path, root_folder: Path) -> Path:
    return Path(*path.parts[len(root_folder.parts) :])


def manage_action(
    index: int,
    action: Callable[[list[Path]], ActionReturn],
    previous_folders: list[Path],
) -> Path:
    logging.info("Running %s", action.__name__)
    logging.info("Input folders: %s", previous_folders)

    global MANAGED_FOLDER, SUCCESS_FOLDER

    success_folder = SUCCESS_FOLDER / f"{index:02d}_{action.__name__}"
    success_folder.mkdir(exist_ok=True)

    logging.info("Output folder: %s", success_folder)

    failed_folder = MANAGED_FOLDER / f"{index:02d}_{action.__name__}_failed"
    failed_folder.mkdir(exist_ok=True)

    for folder in previous_folders:
        result = action([folder])

        if result["failed"]:
            logging.error("Failed to run %s on %s", action.__name__, folder)

        for path in result["failed"]:
            new_path = failed_folder / remove_parents_from_path(path, folder)
            new_path.parent.mkdir(parents=True, exist_ok=True)
            path.rename(new_path)

        for path in result["success"]:
            new_path = success_folder / remove_parents_from_path(path, folder)
            new_path.parent.mkdir(exist_ok=True, parents=True)
            path.rename(new_path)

    return success_folder


def recurse_remove_empty_folder(folder: Path) -> None:
    for child in folder.iterdir():
        if child.is_dir() and child.name not in IGNORED_FOLDERS:
            recurse_remove_empty_folder(child)

    if not any(x for x in folder.iterdir() if x.name not in IGNORED_FOLDERS):
        logging.info("Removing empty folder %s", folder)
        shutil.rmtree(folder)


def remove_empty_folders(folders: list[Path]) -> None:
    for folder in folders:
        recurse_remove_empty_folder(folder)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    working_dir = Path.cwd()

    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, default=working_dir, nargs="?")
    args = parser.parse_args()

    path = args.path

    global EPUB_FOLDER, MANAGED_FOLDER, SUCCESS_FOLDER

    MANAGED_FOLDER = path.parent / "Bédés gérées"
    MANAGED_FOLDER.mkdir(exist_ok=True)
    SUCCESS_FOLDER = MANAGED_FOLDER / "success"
    SUCCESS_FOLDER.mkdir(exist_ok=True)
    EPUB_FOLDER = path.parent / "EPUB"
    EPUB_FOLDER.mkdir(exist_ok=True)

    folders = [path]

    pipeline: list[Callable[[list[Path]], ActionReturn]] = [
        initiate,
        rename_cbz,
        unrar,
        remove_mac_folders,
        # remove_useless_junk_from_name,
        move_epub,
        rename_images_in_zip_files,
    ]

    for index, action in enumerate(pipeline):
        folders.append(manage_action(index, action, folders))

    remove_empty_folders(folders + [MANAGED_FOLDER])


if __name__ == "__main__":
    main()
