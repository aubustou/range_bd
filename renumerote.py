from pathlib import Path
import re


BD_FOLDER = Path(r"D:\Bédés\Coeurs Vaillants 1953 [CBZ]")
FILENAME_PATTERN = re.compile(r"(\d{4}) (\d{2})\.cbz")

PREFIX = "Coeurs Vaillants"

for path in BD_FOLDER.iterdir():
    year, month = FILENAME_PATTERN.findall(path.name)[0]
    month = month.zfill(2)

    new_filename = f"{PREFIX} #{year}{month} ({year})"

    print(str(path) + " -> " + new_filename)
    path.rename(path.with_stem(new_filename))