import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

from hachoir.core import config as hachoir_config
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

from patterns import Pattern, parse_date

IMAGE_EXTENSIONS: list[str] = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"]
VIDEO_EXTENSIONS: list[str] = [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"]
WRITABLE_METADATA_EXTENSIONS: list[str] = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"]
NAMING_PATTERNS: list[Pattern] = []
# NAMING_PATTERNS: list[Pattern] = [ScreenshotsPattern(), WhatsAppPattern()]
MIN_VALID_YEAR = 1970
MIN_VALID_DATE = datetime(MIN_VALID_YEAR, 1, 1)
EXIF_IFD_TAG = 0x8769
EXIF_DATETIME_TAG = 0x0132
EXIF_DATETIME_ORIGINAL_TAG = 0x9003
EXIF_DATETIME_DIGITIZED_TAG = 0x9004

warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
hachoir_config.quiet = True


def is_supported_media(path: Path):
    return path.suffix.lower() in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS


def can_write_metadata(path: Path):
    return path.suffix.lower() in WRITABLE_METADATA_EXTENSIONS


def is_valid_date(date_value: datetime):
    try:
        if int(date_value.timestamp()) <= 31536000:
            return False
    except (OverflowError, OSError, ValueError):
        return False
    return date_value.year > MIN_VALID_YEAR


def get_earliest_date(path: Path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
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
        if is_valid_date(candidate_date):
            return candidate_date

    return MIN_VALID_DATE


def get_picture_date(path: Path):
    date_taken = None
    try:
        with Image.open(path) as image:
            exif = image.getexif()
        if exif:
            raw_date_taken = exif.get(EXIF_DATETIME_ORIGINAL_TAG) or exif.get(EXIF_DATETIME_TAG)
            if isinstance(raw_date_taken, bytes):
                raw_date_taken = raw_date_taken.decode("ascii")
            if raw_date_taken:
                date_taken = datetime.strptime(raw_date_taken, "%Y:%m:%d %H:%M:%S")
    except Exception:
        date_taken = None
    if date_taken and is_valid_date(date_taken):
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
        if is_valid_date(media_date):
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


def write_metadata_date_from_name(path: Path):
    if not can_write_metadata(path):
        raise ValueError(f"Cannot write EXIF metadata for unsupported file type: {path}")

    date_taken = parse_date(path)
    if date_taken is None:
        return False

    exif_date = date_taken.strftime("%Y:%m:%d %H:%M:%S")
    encoded_exif_date = exif_date.encode("ascii")

    with Image.open(path) as image:
        image.load()
        exif = image.getexif()
        exif[EXIF_DATETIME_TAG] = exif_date
        exif_ifd = exif.get_ifd(EXIF_IFD_TAG)
        exif_ifd[EXIF_DATETIME_ORIGINAL_TAG] = encoded_exif_date
        exif_ifd[EXIF_DATETIME_DIGITIZED_TAG] = encoded_exif_date
        image.save(path, exif=exif)

    return True
