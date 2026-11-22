# Agent Instructions

Photostamp is a command-line tool that renames pictures and videos from their dates and repairs their image or video metadata. Changes are previewed by default and applied only with `--apply`.

**Stack**: Python 3.13 with uv, Pillow, piexif, hachoir, and colorama, checked with Ruff and ty.

## Commands

- `just setup`: Install dependencies with uv.
- `just start <files> [--apply] [--metadata] [--add-<unit> <n>]`: Run the CLI. See [main.py](src/main.py) for all options.
- `just check`: Lint, format, and type check.
- `uv run python -m unittest discover -s tests`: Run the unit tests.

## Code Map

- [main.py](src/main.py): Arguments, dry-run and apply flow, and output.
- [engine.py](src/engine.py): Item discovery, name generation, date offsets, and symlink handling.
- [media.py](src/media.py): Reading and writing image and video dates.
- [patterns.py](src/patterns.py): Recognized file name patterns.

## Documentation

- [README](README.md)
- [Documentation Guidelines](docs/README.md)
