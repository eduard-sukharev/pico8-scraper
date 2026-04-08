# PICO-8 ROM Downloader

Python script to download PICO-8 cartridges from Lexaloffle BBS.

## Quick Start

```bash
pip install -r requirements.txt
python download_carts.py --help
```

## CLI Options

- `--filter {featured,new,popular}` - Sort order (default: featured)
- `--exclude-mouse` - Skip mouse-only games  
- `--output-dir PATH` - Output directory (default: ./roms)
- `--max-pages N` - Limit pages (for testing)
- `--dry-run` - Show what would be downloaded without downloading
