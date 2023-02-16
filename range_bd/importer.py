from __future__ import annotations
from dataclasses import dataclass
import platform

import json
import subprocess
import time
from pathlib import Path
from typing import Literal
from zipfile import ZipFile

from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Chrome, Chromi
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
import cv2
import numpy as np
from selenium.webdriver.common.action_chains import ActionChains
import rotatescreen

LOGIN_URL = "https://www.izneo.com/fr/login"
URLS = [
    # "https://www.izneo.com/fr/bd/seinen/insomniaques-43556/insomniaques-t01-94528/read/1",
    "https://www.izneo.com/fr/comics/science-fiction/universal-war-two-24959/universal-war-two-tome-3-l-exode-15477/read/1",
]

BEDE_FOLDER = Path(r"D:\Bédés")
TMP_FOLDER = Path(r"D:\Bédés\izneo_temp")
TMP_FOLDER.mkdir(exist_ok=True)


def login(driver: Chrome, username: str, password: str):
    driver.get(LOGIN_URL)
    driver.find_element(By.ID, "form_username").send_keys(username)
    driver.find_element(By.ID, "form_password").send_keys(password)
    driver.find_element(By.ID, "btnLogin").click()


def get_details_from_url(url: str) -> tuple[str, str, str, str, str, str]:
    """['https:', '', 'www.izneo.com', 'fr', 'bd', 'seinen', 'insomniaques-43556', 'insomniaques-t01-94528',
    'read', '1']"""
    _, _, _, _, type, category, series, tome, _, _ = url.split("/")
    series, series_id = series.rsplit("-", 1)
    _, tome, tome_id = tome.rsplit("-", 2)
    tome = tome.replace("t", "")

    return type, category, series, series_id, tome, tome_id


def download(driver: Chrome, url: str, username: str, password: str) -> Path:
    type, category, series, series_id, tome, tome_id = get_details_from_url(url)

    if category in {"seinen", "shonen", "shojo", "manga"}:
        arrow = Keys.ARROW_LEFT
    else:
        arrow = Keys.ARROW_RIGHT

    path = Path(f"{series} - {series_id}/{tome} - {tome_id}")
    path.mkdir(parents=True, exist_ok=True)

    actions = ActionChains(driver)

    driver.get(url)
    # driver.fullscreen_window()

    # Wait for div iz_OpenSliderLast to appears
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.ID, "iz_OpenSliderLast")))

    # Catch value of iz_OpenSliderLast
    soup = BeautifulSoup(driver.page_source, "html.parser")
    last_page = soup.find(id="iz_OpenSliderLast").text
    print(f"Last page: {last_page}")
    number_length = len(last_page)

    # Wait for footer/header to disappear
    time.sleep(5)

    for index in range(int(last_page)):
        # for index in range(10):
        time.sleep(2)
        driver.save_screenshot(
            f"{series} - {series_id}/{tome} - {tome_id}/{series} #{tome} - {str(index).zfill(number_length)}.png"
        )

        # press LEFT arrow
        actions.send_keys(arrow)
        actions.perform()

    # move_images(path, BEDE_FOLDER)

    create_cbz(path, series, tome)

    return path


def move_images(path: Path, new_path: Path) -> None:
    for image in path.glob("*.png"):
        image.rename(new_path / image.name)
    path.rmdir()


@dataclass
class Crop:
    min_x_nonzero: int
    max_x_nonzero: int
    min_y_nonzero: int
    max_y_nonzero: int


def crop_edges(image_path: Path, crop: Crop | None) -> Crop:
    print(f"Cropping {image_path}")

    image = cv2.imread(str(image_path))

    if not crop:
        y_nonzero, x_nonzero, _ = np.nonzero(image)
        crop = Crop(
            np.min(x_nonzero), np.max(x_nonzero), np.min(y_nonzero), np.max(y_nonzero)
        )

    cropped_image = image[
        crop.min_y_nonzero : crop.max_y_nonzero, crop.min_x_nonzero : crop.max_x_nonzero
    ]

    cv2.imwrite(str(image_path), cropped_image)

    return crop


def create_cbz(download_path: Path, series: str, tome: str) -> None:
    series_folder = BEDE_FOLDER / series
    series_folder.mkdir(parents=True, exist_ok=True)
    cbz_file_path = series_folder / f"{series} #{tome}.cbz"

    crop: Crop | None = None

    with ZipFile(cbz_file_path, "w") as cbz_file:
        for image in download_path.glob("*.png"):
            crop = crop_edges(image, crop)

            cbz_file.write(str(image), image.name)


class ScreenOperation:
    operating_system: str
    display: str
    mode_name: str = "4000x4000_60.00"
    mode: str = f'"{mode_name}"  1394.75  4000 4360 4808 5616  4000 4003 4013 4140 -hsync +vsync'
    previous_resolution: str

    def __init__(self) -> None:
        self.operating_system = platform.system()
        if self.operating_system == "Windows":
            import rotatescreen

            self.screen = rotatescreen.get_primary_display()
        elif self.operating_system == "Linux":
            self.add_custom_resolution()
            self.get_previous_resolution()

    def add_custom_resolution(self) -> None:
        subprocess.run(["xrandr", "--newmode", self.mode], check=True)
        subprocess.run(["xrandr", "--addmode", "eDP-1", self.mode_name], check=True)

    def remove_custom_resolution(self) -> None:
        subprocess.run(["xrandr", "--delmode", "eDP-1", self.mode_name], check=True)
        subprocess.run(["xrandr", "--rmmode", self.mode_name], check=True)

    def get_previous_resolution(self) -> None:
        output = subprocess.run(["xrandr"], capture_output=True, check=True)
        for line in output.stdout.decode().splitlines():
            if "connected primary" in line:
                self.display, _, _, mode = line.split(maxsplit=3)
                self.previous_resolution = mode.split("+", maxsplit=1)[0].strip()
        else:
            raise RuntimeError("Could not find display")

    def increase_resolution(self) -> None:
        subprocess.run(
            ["xrandr", "--output", self.display, "--mode", self.mode_name],
            check=True,
        )

    def set_previous_resolution(self) -> None:
        subprocess.run(
            ["xrandr", "--output", self.display, "--mode", self.previous_resolution],
            check=True,
        )

    def __enter__(self) -> None:
        if self.operating_system == "Windows":
            self.screen.set_portrait()
        elif self.operating_system == "Linux":
            self.increase_resolution()

        time.sleep(3)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.operating_system == "Windows":
            self.screen.set_landscape()
        elif self.operating_system == "Linux":
            self.set_previous_resolution()
            self.remove_custom_resolution()


def main() -> None:

    credentials = json.load((Path(__file__).parent / "credentials.json").open())
    username = credentials["importer"]["username"]
    password = credentials["importer"]["password"]

    chrome_options = Options()
    chrome_options.add_argument("--window-size=4000,4000")
    driver = Chrome(chrome_options=chrome_options)

    with ScreenOperation(), driver:
        login(driver, username, password)

        driver.set_window_size(4000, 4000)

        for url in URLS:
            download(driver, url, username, password)


if __name__ == "__main__":
    main()
