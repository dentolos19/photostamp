# Product Specifications

## Purpose

Photostamp gives a photo and video library one consistent, sortable naming scheme based on when each file was taken, and repairs the dates stored inside the files so other photo apps sort them correctly too.

## Users

- **Library Owners**: People organizing pictures and videos from cameras, phones, screenshots, and messaging apps who are comfortable running a command in a terminal.

## Core Features

- **Date Renaming**: Renames each supported file to `YYYYMMDD-HHMMSS_XXXX` plus its lowercase extension, where `XXXX` is a random four-character suffix that avoids name collisions. Files already named this way with a matching date keep their names.
- **Date Sources**: Uses the embedded metadata date first, then a date in the file name, then the earlier of the file's created and modified times.
- **Name Patterns**: Recognizes Photostamp names, Android screenshots such as `Screenshot_20240114_110317`, and WhatsApp media such as `IMG-20210531-WA0000`. Patterns live in [patterns.py](src/patterns.py).
- **Metadata Repair**: When renaming, writes the file name date into the metadata of files that have none. With `--metadata`, writes metadata dates without renaming.
- **Date Offsets**: `--add-years`, `--add-months`, `--add-days`, `--add-hours`, and `--add-minutes` shift embedded metadata dates, and the new names follow the shifted dates.
- **Previews**: Every run prints a numbered tree of proposed changes and only changes files when `--apply` is passed.
- **Folders and Links**: Recurses into folders, keeps symbolic links pointing at renamed targets, and skips cyclic folder links.
- **Supported Formats**: Images in JPEG, PNG, TIFF, and WebP, and videos in AVI, FLV, MKV, MOV, MP4, WebM, and WMV.

## Scope

- Image dates are read and written as EXIF `DateTime`, `DateTimeOriginal`, and `DateTimeDigitized` without recompressing pixels for JPEG, PNG, and WebP.
- Video dates are read with Hachoir and written with FFmpeg using stream copy, so writing video metadata needs `ffmpeg` on `PATH`.
- Animated PNG and WebP images keep their animation when metadata is written.

### Out of Scope

- Multi-page TIFF metadata is never modified; those files are only renamed.
- Unsupported file types, such as HEIC and RAW formats, are listed but left untouched.
- There is no graphical interface, packaged installer, or undo; preview with a dry run before applying.
- Files are not moved into dated folders or deduplicated.
