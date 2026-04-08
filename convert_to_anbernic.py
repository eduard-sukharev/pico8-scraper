#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

from PIL import Image

from download_carts import sanitize_filename
from pico8_utils import check_mouse_usage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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


def convert_to_anbernic(
    source_dir: Path,
    output_dir: Path,
    exclude_mouse: bool = False,
):
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "Imgs").mkdir(parents=True, exist_ok=True)

    carts = list(source_dir.glob("*.p8.png"))
    logger.info(f"Found {len(carts)} cartridges in {source_dir}")

    converted = 0
    skipped_mouse = 0
    skipped = 0

    for cart_path in carts:
        title = cart_path.stem.replace(".p8", "").replace("_", " ")
        sanitized = sanitize_filename(title)

        if exclude_mouse:
            if check_mouse_usage(cart_path):
                logger.info(f"Skipping (mouse): {sanitized}")
                skipped_mouse += 1
                continue

        create_anbernic_files(cart_path, output_dir)
        logger.info(f"Converted: {sanitized}")
        converted += 1

    logger.info(f"Done! Converted: {converted}, Skipped (mouse): {skipped_mouse}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert PICO-8 cartridges to Anbernic layout"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("./roms"),
        help="Source directory with .p8.png files (default: ./roms)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./pico8"),
        help="Output directory for Anbernic layout (default: ./pico8)",
    )
    parser.add_argument(
        "--exclude-mouse",
        action="store_true",
        help="Skip mouse-only games",
    )

    args = parser.parse_args()

    logger.info(
        f"Converting {args.source_dir} -> {args.output_dir}, exclude_mouse={args.exclude_mouse}"
    )

    convert_to_anbernic(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        exclude_mouse=args.exclude_mouse,
    )


if __name__ == "__main__":
    main()
