import re
from pathlib import Path

BD_FOLDER = Path(r"D:\Bédés")
NAME_PATTERN = re.compile(r" - T(\d+) - ")


def recurse(top_path: Path):
    if top_path.is_dir():
        for path in top_path.iterdir():
            recurse(path)
    else:
        if not NAME_PATTERN.search(top_path.stem):
            return
        new_name = NAME_PATTERN.sub(r" - \g<1> - ", top_path.stem)
        top_path.rename(top_path.with_stem(new_name))

def main():
    for path in BD_FOLDER.iterdir():
        recurse(path)

if __name__ == "__main__":
    main()