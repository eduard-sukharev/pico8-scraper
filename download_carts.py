#!/usr/bin/env python3
import argparse
import io
import os
import re
import struct
import time
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import png
from PIL import Image

import pico8_decoder
from pico8_utils import check_mouse_usage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.lexaloffle.com"
LISTING_URL_TEMPLATE = (
    BASE_URL
    + "/bbs/lister.php?use_hurl=1&sub=2&cat=7&mode=carts&orderby={filter}&page={page}"
)
CART_DOWNLOAD_TEMPLATE = BASE_URL + "/bbs/cposts/{folder}/{pid}.p8.png"

REQUEST_DELAY = 1.5
MAX_RETRIES = 3
RETRY_BACKOFF = 2

CODE_OFFSET = 0x4300
CODE_END = 0x8000


def extract_hidden_data(cart_path: Path) -> bytes | None:
    try:
        with open(cart_path, "rb") as f:
            reader = png.Reader(file=f)
            width, height, rows, info = reader.read()
            if width != 160 or height != 205:
                return None
            rows = list(rows)
            hidden = bytearray()
            for row in rows:
                for col in range(width):
                    idx = col * 4
                    r = row[idx + 0] & 3
                    g = row[idx + 1] & 3
                    b = row[idx + 2] & 3
                    a = row[idx + 3] & 3
                    byte_val = (a << 6) | (r << 4) | (g << 2) | b
                    hidden.append(byte_val)
            return bytes(hidden)
    except Exception as e:
        logger.debug(f"Could not extract hidden data from {cart_path}: {e}")
        return None


def decompress_lua_new(data: bytes, decompressed_len: int) -> str:
    result = []
    mtf = list(range(256))

    stream = []
    for b in data:
        stream.append(format(b, "08b")[::-1])
    stream_str = "".join(stream)
    stream_pos = 0

    def read_bit():
        nonlocal stream_pos
        if stream_pos >= len(stream_str):
            return None
        bit = stream_str[stream_pos]
        stream_pos += 1
        return bit

    def read_bits(n):
        nonlocal stream_pos
        if stream_pos + n > len(stream_str):
            return None
        inv_bits = stream_str[stream_pos : stream_pos + n][::-1]
        stream_pos += n
        return inv_bits

    while len(result) < decompressed_len:
        if stream_pos >= len(stream_str):
            break
        header = read_bit()
        if header is None:
            break
        if header == "1":
            unary = 0
            while read_bit() == "1":
                unary += 1
            unary_mask = (1 << unary) - 1
            bin_str = read_bits(4 + unary)
            if bin_str is None:
                break
            index = int(bin_str, 2) + (unary_mask << 4)
            if index >= len(mtf):
                break
            byte = mtf[index]
            result.append(chr(byte))
            mtf.pop(index)
            mtf.insert(0, byte)
        else:
            b1 = read_bit()
            b2 = read_bit()
            if b1 == "1" and b2 == "1":
                offset_bits = 5
            elif b1 == "1" and b2 == "0":
                offset_bits = 10
            else:
                offset_bits = 15

            if offset_bits is None:
                break

            offset_bits_str = read_bits(offset_bits)
            if offset_bits_str is None:
                break
            offset = int(offset_bits_str, 2) + 1
            if offset_bits == 10 and offset == 1:
                while True:
                    b = read_bits(8)
                    if b is None or b == "00000000":
                        break
                    result.append(chr(int(b, 2)))
                    if len(result) >= decompressed_len:
                        break
            else:
                length = 3
                while True:
                    part_str = read_bits(3)
                    if part_str is None:
                        break
                    part = int(part_str, 2)
                    length += part
                    if part != 7:
                        break
                for _ in range(length):
                    if offset > len(result):
                        break
                    result.append(result[-offset])

    return "".join(result)


def decompress_lua_old(data: bytes, decompressed_len: int) -> str:
    lookup = "\n 0123456789abcdefghijklmnopqrstuvwxyz!#%(){}[]<>+=/*:;.,~_"
    result = bytearray()
    idx = 0
    while len(result) < decompressed_len and idx < len(data):
        v = data[idx]
        idx += 1
        if v == 0x00:
            if idx < len(data):
                result.append(data[idx])
                idx += 1
        elif v <= 0x3B:
            result.append(lookup[v].encode("latin-1")[0])
        elif idx < len(data):
            next_v = data[idx]
            idx += 1
            offset = (v - 0x3C) * 16 + (next_v & 0xF)
            length = (next_v >> 4) + 2
            if offset <= len(result):
                for _ in range(length):
                    result.append(result[-offset])
    return bytes(result).decode("latin-1", errors="replace")


def extract_lua_code(cart_path: Path) -> str | None:
    try:
        return pico8_decoder.extract_code(str(cart_path))
    except Exception as e:
        logger.debug(f"Could not extract Lua code from {cart_path}: {e}")
    return None


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "", name)
    name = name.replace(" ", "_")
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")
    if not name:
        name = "unnamed"
    return name


def fetch_url(url: str, retries: int = MAX_RETRIES) -> str | None:
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            if attempt < retries - 1:
                wait_time = RETRY_BACKOFF**attempt
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{retries}): {e}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Request failed after {retries} attempts: {e}")
                return None
    return None


def download_file(url: str, retries: int = MAX_RETRIES) -> bytes | None:
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            if attempt < retries - 1:
                wait_time = RETRY_BACKOFF**attempt
                logger.warning(
                    f"Download failed (attempt {attempt + 1}/{retries}): {e}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Download failed after {retries} attempts: {e}")
                return None
    return None


def parse_listing_page(html: str) -> tuple[list[dict], int | None]:
    soup = BeautifulSoup(html, "html.parser")
    carts = []

    links = soup.find_all("a", href=True)
    seen_titles = set()
    for a in links:
        href = a.get("href", "")
        title = a.get_text(strip=True)

        if "tid=" in href and title and title not in seen_titles:
            tid_match = re.search(r"tid=(\d+)", href)
            if tid_match:
                seen_titles.add(title)
                carts.append({"title": title, "tid": tid_match.group(1), "pid": None})

    next_links = soup.select("a:has(div)")
    next_page = None
    for a in next_links:
        href = a.get("href", "")
        if "page=" in href and "sub=2" in href and "mode=carts" in href:
            match = re.search(r"page=(\d+)", href)
            if match:
                candidate = int(match.group(1))
                if next_page is None or candidate > next_page:
                    next_page = candidate

    return carts, next_page


def create_anbernic_files(cart_path: Path, output_dir: Path) -> None:
    base_name = cart_path.stem.replace(".p8", "")
    p8_path = output_dir / f"{base_name}.p8"
    img_path = output_dir / "Imgs" / f"{base_name}.png"

    with open(cart_path, "rb") as f:
        data = f.read()

    with open(p8_path, "wb") as f:
        f.write(data)

    with Image.open(cart_path) as img:
        cropped = img.crop((16, 24, 16 + 128, 24 + 128))
        upscaled = cropped.resize((256, 256), Image.NEAREST)
        upscaled.save(img_path, "PNG")


def download_carts(
    output_dir: Path,
    filter_type: str = "featured",
    exclude_mouse: bool = False,
    max_pages: int | None = None,
    anbernic: bool = False,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    if anbernic:
        (output_dir / "Imgs").mkdir(parents=True, exist_ok=True)

    existing_files = set()
    for f in output_dir.glob("*.p8.png"):
        existing_files.add(f.name)

    logger.info(f"Found {len(existing_files)} existing cartridges in {output_dir}")

    page = 1
    total_downloaded = 0
    total_skipped = 0
    total_mouse_skipped = 0
    total_failed = 0

    while True:
        if max_pages and page > max_pages:
            logger.info(f"Reached max pages limit ({max_pages})")
            break

        url = LISTING_URL_TEMPLATE.format(filter=filter_type, page=page)
        logger.info(f"Fetching page {page}: {url}")

        html = fetch_url(url)
        if not html:
            logger.error(f"Failed to fetch page {page}")
            total_failed += 1
            break

        carts, next_page = parse_listing_page(html)
        if not carts:
            logger.info(f"No carts found on page {page}, stopping")
            break

        logger.info(f"Found {len(carts)} carts on page {page}")

        for cart in carts:
            sanitized_name = sanitize_filename(cart["title"]) + ".p8.png"

            if sanitized_name in existing_files:
                logger.debug(f"Skipping existing: {sanitized_name}")
                total_skipped += 1
                continue

            cart_page_url = f"{BASE_URL}/bbs/?tid={cart['tid']}"
            cart_page_html = fetch_url(cart_page_url)
            download_url = None

            if cart_page_html:
                cart_soup = BeautifulSoup(cart_page_html, "html.parser")
                cart_links = cart_soup.find_all(
                    "a", href=lambda h: h and ".p8.png" in h
                )
                if cart_links:
                    href = cart_links[0].get("href", "")
                    if href.startswith("/"):
                        download_url = BASE_URL + href
                    else:
                        download_url = href

            if not download_url:
                logger.error(f"Could not find download URL for: {cart['title']}")
                total_failed += 1
                continue

            logger.info(f"Downloading: {cart['title']} -> {sanitized_name}")

            content = download_file(download_url)
            if not content:
                logger.error(f"Failed to download: {cart['title']}")
                total_failed += 1
                continue

            cart_path = output_dir / sanitized_name
            try:
                with open(cart_path, "wb") as f:
                    f.write(content)
            except IOError as e:
                logger.error(f"Failed to save {sanitized_name}: {e}")
                total_failed += 1
                continue

            if exclude_mouse:
                if check_mouse_usage(cart_path):
                    logger.info(f"Skipping (mouse required): {cart['title']}")
                    cart_path.unlink()
                    total_mouse_skipped += 1
                    continue

            if anbernic:
                create_anbernic_files(cart_path, output_dir)

            existing_files.add(sanitized_name)
            total_downloaded += 1
            logger.info(f"Downloaded: {sanitized_name}")

        if next_page is None:
            logger.info("No more pages to fetch")
            break

        page = next_page
        time.sleep(REQUEST_DELAY)

    logger.info(
        f"Done! Downloaded: {total_downloaded}, Skipped: {total_skipped}, Mouse-skipped: {total_mouse_skipped}, Failed: {total_failed}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Download PICO-8 cartridges from Lexaloffle"
    )
    parser.add_argument(
        "--filter",
        choices=["featured", "new", "popular"],
        default="featured",
        help="Cartridge filter (default: featured)",
    )
    parser.add_argument(
        "--exclude-mouse", action="store_true", help="Skip mouse-only games"
    )
    parser.add_argument(
        "--anbernic",
        action="store_true",
        help="Store in Anbernic layout (roms/ + Imgs/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./roms"),
        help="Output directory for cartridges (default: ./roms)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of pages to fetch (for testing)",
    )

    args = parser.parse_args()

    logger.info(
        f"Starting download with filter={args.filter}, exclude_mouse={args.exclude_mouse}, anbernic={args.anbernic}, output_dir={args.output_dir}"
    )

    download_carts(
        output_dir=args.output_dir,
        filter_type=args.filter,
        exclude_mouse=args.exclude_mouse,
        max_pages=args.max_pages,
        anbernic=args.anbernic,
    )


if __name__ == "__main__":
    main()
