# PICO-8 ROM Downloader

Download PICO-8 cartridges from Lexaloffle BBS.

## Installation

```bash
pip install -r requirements.txt
```

## Download Script

```bash
python download_carts.py --help
```

### Options

- `--filter {featured,new,popular}` - Sort order (default: featured)
- `--exclude-mouse` - Skip mouse-only games (uses STAT(30-33))
- `--anbernic` - Store in Anbernic layout (roms/ + Imgs/)
- `--output-dir PATH` - Output directory (default: ./roms)
- `--max-pages N` - Limit pages for testing

### Examples

```bash
# Download featured carts
python download_carts.py

# Download newest carts, skip mouse games
python download_carts.py --filter new --exclude-mouse

# Download with Anbernic layout (for handheld devices)
python download_carts.py --anbernic --output-dir ./pico8
```

## Convert to Anbernic Layout

Convert existing `.p8.png` cartridges to Anbernic-compatible format:

```bash
python convert_to_anbernic.py --help
```

### Options

- `--source-dir PATH` - Source directory with .p8.png files (default: ./roms)
- `--output-dir PATH` - Output directory for Anbernic layout (default: ./pico8)
- `--exclude-mouse` - Skip mouse-only games

### Examples

```bash
# Convert all cartridges
python convert_to_anbernic.py

# Convert, skipping mouse-only games
python convert_to_anbernic.py --exclude-mouse

# Custom source and output directories
python convert_to_anbernic.py --source-dir ./roms --output-dir /media/sdcard/PICO8
```

## Anbernic Layout

When using `--anbernic` or the conversion script, the output structure is:

```
pico8/
├── game1.p8          # Cartridge files
├── game2.p8
└── Imgs/
    ├── game1.png     # 256x256 thumbnails
    └── game2.png
```

The thumbnails are created by cropping the cart image at position (16,24) to 128x128, then upscaling 2x to 256x256 using nearest-neighbor interpolation to preserve pixel-art quality.

## Mouse Detection

The script parses Lua code from each cartridge's PNG steganography to detect mouse usage. Games that call `STAT(30)`, `STAT(31)`, `STAT(32)`, or `STAT(33)` are considered mouse-only and skipped when `--exclude-mouse` is used.
