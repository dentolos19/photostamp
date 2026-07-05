import sys
from datetime import datetime, timezone
from pathlib import Path

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

from patterns import Pattern

VIDEO_EXTENSIONS: list[str] = [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"]
NAMING_PATTERNS: list[Pattern] = []
# NAMING_PATTERNS: list[Pattern] = [ScreenshotsPattern(), WhatsAppPattern()]
MIN_VALID_YEAR = 1970
MIN_VALID_DATE = datetime(MIN_VALID_YEAR, 1, 1)


def is_valid_media_date(date_value: datetime):
    try:
        if int(date_value.timestamp()) <= 31536000:
            return False
    except (OverflowError, OSError, ValueError):
        return False
    return date_value.year > MIN_VALID_YEAR


def get_earliest_date(path: Path):
    stat = path.stat()
    date_modified = datetime.fromtimestamp(stat.st_mtime)

    # st_birthtime is only available on Windows and macOS; Linux exposes st_ctime
    # (inode change time) instead, which is not the true creation time, so we
    # treat it as a candidate alongside the modification time and pick the earliest.
    if sys.platform == "win32" or hasattr(stat, "st_birthtime"):
        date_created = datetime.fromtimestamp(stat.st_birthtime)  # type: ignore
    else:
        date_created = datetime.fromtimestamp(stat.st_ctime)

    candidate_dates = sorted((date_created, date_modified), key=lambda date: date.timestamp())

    for candidate_date in candidate_dates:
        # Skip unset timestamps and dates older than the minimum supported year.
        if is_valid_media_date(candidate_date):
            return candidate_date

    return MIN_VALID_DATE


def get_picture_date(path: Path):
    try:
        exif = Image.open(path).getexif()
        if not exif:
            date_taken = None
        date_taken = datetime.strptime(exif[36867], "%Y:%m:%d %H:%M:%S")
    except Exception:
        date_taken = None
    if date_taken and is_valid_media_date(date_taken):
        return date_taken
    else:
        return get_earliest_date(path)


def get_video_date(path: Path):
    try:
        parser = createParser(str(path))
        if not parser:
            return get_picture_date(path)
        with parser:
            metadata = extractMetadata(parser)
        if not metadata:
            return get_picture_date(path)

        # Prefer the creation date embedded in the container (e.g. QuickTime/MP4
        # "mvhd" box) over the modification date.
        media_date: datetime | None = metadata.get("creation_date")
        if not media_date:
            media_date = metadata.get("last_modification")
        if not media_date:
            return get_picture_date(path)

        # hachoir returns naive datetimes in UTC for container timestamps.
        if media_date.tzinfo is None:
            media_date = media_date.replace(tzinfo=timezone.utc)
        media_date = media_date.astimezone()
        if is_valid_media_date(media_date):
            return media_date
        return get_picture_date(path)
    except Exception:
        return get_picture_date(path)


def get_media_date(path: Path):
    for pattern in NAMING_PATTERNS:
        if pattern.check_pattern(path):
            return pattern.get_date(path)
    if path.suffix.lower() in VIDEO_EXTENSIONS:
        return get_video_date(path)
    return get_picture_date(path)
