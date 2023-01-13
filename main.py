from pathlib import Path
import re
import os
from zipfile import ZipFile
import subprocess
import glob
import send2trash

BD_FOLDER = Path(r"D:\Bédés\PDF")
FILENAME_PATTERN = re.compile(r"(.*)_Page\.pdf-\d+\.(?:png|jpg)")


def main():
    for pdf_file in BD_FOLDER.glob("*.pdf"):
        print(str(pdf_file))
        subprocess.run(["pdftoppm", "-png", str(pdf_file), str(pdf_file.with_stem(pdf_file.stem + "_Page"))], check=True)

    file_list = os.listdir(BD_FOLDER)
    bd_names = set(FILENAME_PATTERN.findall("\n".join(file_list)))
    # print(bd_names)

    for bd_name in sorted(bd_names):
        print(bd_name)
        root_path = BD_FOLDER / bd_name
        cbz_file_path = root_path.with_suffix(".cbz")
        if cbz_file_path.exists():
            continue

        to_trash: list[Path] = []

        with ZipFile(cbz_file_path, "w") as cbz_file:
            for path in BD_FOLDER.glob(glob.escape(bd_name) + "_Page*"):
                if path.suffix in {".png", ".jpg"}:
                    cbz_file.write(str(path), path.name)
                    to_trash.append(path)
        
        for path in to_trash:
            send2trash.send2trash(path)
        

if __name__ == '__main__':
    main()