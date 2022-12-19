from pathlib import Path
import re
import subprocess

ROOT = Path(r"D:\Bédés\L Attaque des Titans Before the Fall -  T01 a T09")



PATTERN = re.compile(r".*_(\d+).jpg")
TOME_PATTERN = re.compile(r".*T(\d+)\.cbr$")

def rename(root: Path):
    for path in root.iterdir():
        if found := PATTERN.search(path.name):
            print(found.group(1))
            new_name = f"{found.group(1).zfill(5)}.jpg"
            path.rename(path.with_name(new_name))


def unrar(root: Path):
    for path in root.iterdir():
        if path.suffix == ".cbr":
            print(root)
            print(path.name)
            tome_number = TOME_PATTERN.search(path.name).group(1)
            print(root / tome_number)
            subprocess.run(["unrar", "x", path.name, tome_number + "/"], check=True, cwd=root)
            rename(root / tome_number)

if __name__ == "__main__":
    unrar(ROOT)