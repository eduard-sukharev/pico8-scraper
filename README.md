# PICO-8 ROM Downloader

Download PICO-8 cartridges from Lexaloffle BBS.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python download_carts.py --help
```

### Options

- `--filter {featured,new,popular}` - Sort order (default: featured)
- `--exclude-mouse` - Skip mouse-only games
- `--output-dir PATH` - Output directory (default: ./roms)
- `--max-pages N` - Limit pages for testing
- `--dry-run` - Show what would be downloaded without downloading

### Examples

```bash
# Download featured carts
python download_carts.py

# Download newest carts, skip mouse games
python download_carts.py --filter new --exclude-mouse

# Test with 1 page
python download_carts.py --max-pages 1 --dry-run
```

## Output

Downloads `.p8.png` cartridges to the specified directory, skipping already-downloaded files.
