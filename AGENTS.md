# Agent Instructions

Photostamp is a command-line tool that renames pictures and videos from their dates and repairs their image or video metadata. It runs locally from source on Linux, macOS, and Windows.

## Commands

- `just setup`: Install dependencies.
- `just install`: Install dependencies from the frozen lockfile with uv.
- `just start <files> [--apply] [--metadata] [--add-<unit> <n>]`: Run the CLI on files or folders. Changes are previewed unless `--apply` is passed; see [main.py](src/main.py) for all options.
- `just check`: Lint, format, and type check.
- `just test`: Run the unit tests.

## Stack

Python 3.13 with uv, Pillow, piexif, Hachoir, colorama, and an optional FFmpeg binary for video metadata, checked with Ruff and ty and tested with `unittest`.

## Rules

- Keep the preview-by-default behavior: nothing on disk changes unless `--apply` is passed.
- Write metadata through a temporary file in the same folder and replace the original, so a failure never leaves a half-written file.
- Add new file name formats as a `Pattern` subclass in [patterns.py](src/patterns.py) and register it in `NAMING_PATTERNS`.

## Documentation

- [Product Specifications](PRODUCT.md)
- [Documentation Guidelines](docs/README.md)
