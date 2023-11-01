from __future__ import annotations

import json
import logging
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

import cv2
import numpy as np
from bs4 import BeautifulSoup
from selenium.webdriver import Firefox, FirefoxOptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

BASE_URL = "https://www.izneo.com"
LOGIN_URL = "https://www.izneo.com/fr/login"

BASE_SERIES_URLS = []
URLS = []


BEDE_FOLDER = Path.home() / "Bédés"
BEDE_FOLDER.mkdir(exist_ok=True)

TMP_FOLDER = BEDE_FOLDER / "izneo_temp"
TMP_FOLDER.mkdir(exist_ok=True)


def get_all_tomes_from_series(driver: Firefox, url: str) -> list[str]:
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    tomes = soup.find_all("div", class_="album-data")

    urls: list[str] = []
    for tome in tomes:
        urls.append(BASE_URL + tome.find("a")["href"].split("?")[0])

    logging.info("Found %s tomes", len(urls))
    logging.debug("Tomes: %s", urls)

    return urls


def login(driver: Firefox, username: str, password: str):
    driver.get(LOGIN_URL)
    driver.find_element(By.NAME, "login").send_keys(username)
    driver.find_element(By.NAME, "password").send_keys(password)
    driver.find_element(By.CLASS_NAME, "button").click()


def get_details_from_url(
    driver: Firefox, url: str
) -> tuple[list[str], str, str, str, Optional[str]]:
    logging.info("Fetching BD details...")

    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    series_h1 = soup.find("h1", class_="heading heading--xl--album heading--black")
    header = series_h1.text.strip()
    if len(series := header.split(maxsplit=1)) == 2:
        first, second = series
        if first.startswith("T") and int(first[1:]):
            number = first.replace("T", "")
            series = second
        else:
            number = None
            series = header
    else:
        number = None
        series = header

    tome_div = soup.find("div", class_="text text--md text--bold album-to-serie")
    tome_span = tome_div.find("span")
    tome = tome_span.text.strip()
    tome_id = url.split("/")[-1].rsplit("-", maxsplit=1)[1]

    category_div = soup.find("div", class_="for_genres items")
    categories: list[str] = category_div.find("a").text.strip().split(" / ")

    logging.info("Series: %s", series)
    logging.info("Tome: %s", tome)
    logging.info("Tome ID: %s", tome_id)
    logging.info("Number: %s", number)
    logging.info("Categories: %s", categories)

    return categories, series, tome, tome_id, number


def download(driver: Firefox, url: str) -> Path | None:
    (
        categories,
        series,
        tome,
        tome_id,
        number,
    ) = get_details_from_url(driver, url)

    reader_url = url + "/read/1"

    if any(x in {"seinen", "shonen", "shojo", "manga"} for x in categories):
        arrow = Keys.ARROW_LEFT
        back_arrow = Keys.ARROW_RIGHT
    else:
        arrow = Keys.ARROW_RIGHT
        back_arrow = Keys.ARROW_LEFT

    path = Path(f"{series}/{tome} - {tome_id}")
    path.mkdir(parents=True, exist_ok=True)

    actions = ActionChains(driver)

    driver.get(reader_url)
    logging.info("Downloading: %s", reader_url)
    # driver.fullscreen_window()

    # Wait for div iz_OpenSliderLast to appears
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.ID, "iz_OpenSliderLast")))

    # Catch value of iz_OpenSliderLast
    soup = BeautifulSoup(driver.page_source, "html.parser")
    current_page = soup.find(id="iz_OpenSliderCurrent").text.strip()

    if current_page != "1":
        logging.info("Current page: %s. Back to page #1", current_page)
        for _ in range(int(current_page) - 1):
            actions.send_keys(back_arrow)
            time.sleep(0.2)
        current_page = "1"

    last_page = soup.find(id="iz_OpenSliderLast").text
    if last_page == "10":
        # Assume not paid
        logging.info("Not paid. Skipping")
        return None

    logging.info("Last page: %s", last_page)
    number_length = len(last_page)
    number_of_pages = int(last_page)

    # Zoom in
    actions.send_keys("w")
    actions.perform()

    # Wait for footer/header to disappear
    time.sleep(5)

    for index in range(number_of_pages):
        time.sleep(2)
        driver.save_screenshot(
            path
            / f"{series} {('#' + number + ' - ') if number is not None else '- '}{str(index).zfill(number_length)}.png"
        )

        # press LEFT arrow
        actions.send_keys(arrow)
        actions.perform()
    # move_images(path, BEDE_FOLDER)

    create_cbz(path, series, number)

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
    logging.info("Cropping edges on %s", image_path)

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


def create_cbz(download_path: Path, series: str, number: Optional[str]) -> None:
    series_folder = BEDE_FOLDER / series
    series_folder.mkdir(parents=True, exist_ok=True)
    cbz_file_path = series_folder / f"{series} #{number}.zip"

    crop: Crop | None = None

    logging.info("Creating cbz file %s", cbz_file_path)

    with ZipFile(cbz_file_path, "w") as cbz_file:
        for image in download_path.glob("*.png"):
            crop = crop_edges(image, crop)

            cbz_file.write(str(image), image.name)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    credentials = json.load((Path(__file__).parent / "credentials.json").open())
    username = credentials["importer"]["username"]
    password = credentials["importer"]["password"]

    options = FirefoxOptions()

    options.add_argument("-headless")
    options.add_argument("window-size=4000x4000")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")

    driver = Firefox(options=options)

    with driver:
        login(driver, username, password)

        driver.set_window_size(4000, 4000)

        urls = URLS

        for base_series_url in BASE_SERIES_URLS:
            urls.extend(get_all_tomes_from_series(driver, base_series_url))

        for url in URLS:
            download(driver, url)


if __name__ == "__main__":
    main()
