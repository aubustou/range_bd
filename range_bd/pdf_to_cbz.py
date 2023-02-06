from pathlib import Path
import re

from zipfile import ZipFile
import subprocess
import glob
import send2trash

BDS = [

]
BD_FOLDER = Path(r"D:\Bédés")
FILENAME_PATTERN = re.compile(r"(.*)_Page\.pdf-\d+\.(?:png|jpg)")
MAX_PER_RUN = 10

def main():
    visited_paths: set[Path] = set()

    if BDS:
        visited_paths = set(Path(path) for path in BDS)
    else:
        for index, pdf_file in enumerate(BD_FOLDER.rglob("*.pdf")):
            print(f"To IMG: {pdf_file}")
            subprocess.run(["pdftoppm", "-r", "300", "-png", str(pdf_file), str(pdf_file.with_stem(pdf_file.stem + "_Page"))], check=True)
            visited_paths.add(pdf_file)
            if index > MAX_PER_RUN:
                break

    for bd_path in visited_paths:

        bd_name = bd_path.stem

        images: list[Path] = []
        for img_path in bd_path.parent.glob(glob.escape(bd_name) + "_Page.pdf-*.png"):
            images.append(img_path)

        cbz_file_path = bd_path.with_suffix(".zip")
        if not cbz_file_path.exists():
            print(f"To CBZ: {cbz_file_path}")

            with ZipFile(cbz_file_path, "w") as cbz_file:
                for image in images:
                    cbz_file.write(str(image), image.name)
        else:
            print(f"CBZ already exists: {cbz_file_path}")

        for image in images:
            try:
                send2trash.send2trash(images)
            except FileNotFoundError:
                pass
        

if __name__ == '__main__':
    main()