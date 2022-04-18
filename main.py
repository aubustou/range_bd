from pathlib import Path
import re
import os
from zipfile import ZipFile
import glob

BD_FOLDER = Path(r"D:\Bédés\Conversion_RAR")
FILENAME_PATTERN = re.compile(r"(.*)_Page_\d+_Image_\d+\.(?:png|jpg)")


def main():
    file_list = os.listdir(BD_FOLDER)
    bd_names = set(FILENAME_PATTERN.findall("\n".join(file_list)))
    print(bd_names)

    for bd_name in bd_names:
        print(bd_name)
        root_path = BD_FOLDER / bd_name
        cbz_file_path = root_path.with_suffix(".cbz")
        if cbz_file_path.exists():
            continue

        with ZipFile(cbz_file_path, "w") as cbz_file:
            for path in BD_FOLDER.glob(glob.escape(bd_name) + "*"):
                if path.suffix in {".png", ".jpg"}:
                    cbz_file.write(str(path), path.name)


if __name__ == '__main__':
    main()