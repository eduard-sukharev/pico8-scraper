# PICO-8 ROM Downloader

Python script to download PICO-8 cartridges from Lexaloffle BBS.

## Quick Start

```bash
pip install -r requirements.txt
python download_carts.py --help
```

## CLI Options

- `--filter {featured,new,popular}` - Sort order (default: featured)
- `--exclude-mouse` - Skip mouse-only games (uses STAT(30-33))
- `--output-dir PATH` - Output directory (default: ./roms)
- `--max-pages N` - Limit pages (for testing)
- `--dry-run` - Show what would be downloaded without downloading

## Mouse Detection

The script parses the Lua code from each cartridge's PNG steganography data to detect mouse usage. Games that call `STAT(30)`, `STAT(31)`, `STAT(32)`, or `STAT(33)` are considered mouse-only and will be skipped when `--exclude-mouse` is used.

Note: Some games may use mouse position via custom objects (not STAT calls) - these will not be detected.

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `pypng` - PNG steganography extraction (for mouse detection)
- Pico-8 manual - Included as `pico8_manual.txt` for reference
