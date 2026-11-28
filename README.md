<img alt="Photostamp" src="banner.png">

---

Photostamp is a command-line tool that renames pictures and videos after the date they were taken and repairs the dates stored in their metadata. It is for anyone tidying a photo library from cameras, phone screenshots, and WhatsApp exports into one consistent naming scheme.

Each file is named `YYYYMMDD-HHMMSS_XXXX` from its embedded metadata date, a date found in its file name, or its file system timestamps, in that order. Every run is a dry run that previews the changes until you pass `--apply`.

## Features

- **Date Renaming**: Renames files to `YYYYMMDD-HHMMSS_XXXX` with a random suffix, recursing into folders.
- **Name Patterns**: Reads dates from Photostamp, Android screenshot, and WhatsApp file names.
- **Metadata Repair**: Writes the file name date into EXIF or video container metadata when it is missing.
- **Date Offsets**: Shifts embedded dates by years, months, days, hours, or minutes to fix wrong camera clocks.
- **Safe Previews**: Shows every rename and metadata change before anything is written.
- **Link Handling**: Keeps symbolic links pointing at renamed targets and skips cyclic folder links.
- **Format Preservation**: Keeps animated PNG and WebP images intact, and renames multi-page TIFF files without changing their contents.

## Tech Stack

- [Pillow](https://python-pillow.github.io) and [piexif](https://github.com/hMatoba/Piexif) for reading and writing image EXIF dates.
- [Hachoir](https://hachoir.readthedocs.io) for reading video container dates.
- [FFmpeg](https://ffmpeg.org) for writing video metadata without re-encoding.
- [colorama](https://github.com/tartley/colorama) for colored terminal output.
- [uv](https://docs.astral.sh/uv), [Ruff](https://docs.astral.sh/ruff), and [ty](https://docs.astral.sh/ty) for dependencies, linting, formatting, and type checking.

## Getting Started

### Prerequisites

- [uv](https://docs.astral.sh/uv) with Python 3.13 or newer
- [Just](https://just.systems)
- [FFmpeg](https://ffmpeg.org) on `PATH`, only for writing video metadata

### Setup

1. Install the dependencies.

   ```sh
   just setup
   ```

2. Preview the changes for a folder or a set of files.

   ```sh
   just start ~/Pictures/Camera
   ```

3. Apply the changes once the preview looks right.

   ```sh
   just start ~/Pictures/Camera --apply
   ```

Pass `--metadata` to write metadata dates without renaming, or `--add-<unit> <n>`, such as `--add-hours -8`, to shift embedded dates. Run `just start --help` for every option.

## Documentation

- [Agent Instructions](AGENTS.md)
- [Product Specifications](PRODUCT.md)
- [Documentation Guidelines](docs/README.md)

## License

Licensed under the [MIT License](LICENSE).
