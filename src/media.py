import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from subprocess import CalledProcessError, run
from tempfile import NamedTemporaryFile

import piexif
from hachoir.core import config as hachoir_config
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

from patterns import parse_date

IMAGE_EXTENSIONS: list[str] = [".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"]
JPEG_EXTENSIONS: list[str] = [".jpeg", ".jpg"]
VIDEO_EXTENSIONS: list[str] = [".avi", ".flv", ".mkv", ".mov", ".mp4", ".webm", ".wmv"]
WRITABLE_IMAGE_METADATA_EXTENSIONS: list[str] = [".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"]
MIN_VALID_YEAR = 1970
MIN_VALID_DATE = datetime(MIN_VALID_YEAR, 1, 1)
EXIF_IFD_TAG = 0x8769
EXIF_DATETIME_TAG = 0x0132
EXIF_DATETIME_ORIGINAL_TAG = 0x9003
EXIF_DATETIME_DIGITIZED_TAG = 0x9004

warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
setattr(hachoir_config, "quiet", True)


def is_supported_media(path: Path):
    return path.suffix.lower() in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS


def can_write_metadata(path: Path):
    suffix = path.suffix.lower()
    return suffix in WRITABLE_IMAGE_METADATA_EXTENSIONS or (suffix in VIDEO_EXTENSIONS and which("ffmpeg") is not None)


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
    birthtime = getattr(stat, "st_birthtime", None)
    if sys.platform == "win32" or birthtime is not None:
        date_created = datetime.fromtimestamp(birthtime)
    else:
        date_created = datetime.fromtimestamp(stat.st_ctime)

    candidate_dates = sorted((date_created, date_modified), key=lambda date: date.timestamp())

    for candidate_date in candidate_dates:
        # Skip unset timestamps and dates older than the minimum supported year.
        if is_valid_date(candidate_date):
            return candidate_date

    return MIN_VALID_DATE


def get_image_date(path: Path):
    date_taken = None
    try:
        with Image.open(path) as image:
            exif = image.getexif()
        if exif:
            raw_date_taken = (
                exif.get(EXIF_DATETIME_ORIGINAL_TAG)
                or exif.get(EXIF_DATETIME_DIGITIZED_TAG)
                or exif.get(EXIF_DATETIME_TAG)
            )
            if isinstance(raw_date_taken, bytes):
                raw_date_taken = raw_date_taken.decode("ascii")
            if raw_date_taken:
                date_taken = datetime.strptime(raw_date_taken, "%Y:%m:%d %H:%M:%S")
    except Exception:
        date_taken = None
    if date_taken and is_valid_date(date_taken):
        return date_taken
    return None


def get_video_date(path: Path):
    try:
        parser = createParser(str(path))
        if not parser:
            return None
        with parser:
            metadata = extractMetadata(parser)
        if not metadata:
            return None

        # Prefer the creation date embedded in the container (e.g. QuickTime/MP4
        # "mvhd" box) over the modification date.
        media_date: datetime | None = metadata.get("creation_date")
        if not media_date:
            media_date = metadata.get("last_modification")
        if not media_date:
            return None

        # hachoir returns naive datetimes in UTC for container timestamps.
        if media_date.tzinfo is None:
            media_date = media_date.replace(tzinfo=timezone.utc)
        media_date = media_date.astimezone()
        if is_valid_date(media_date):
            return media_date
        return None
    except Exception:
        return None


def get_metadata_date(path: Path):
    if path.suffix.lower() in VIDEO_EXTENSIONS:
        return get_video_date(path)
    return get_image_date(path)


def get_media_date(path: Path):
    metadata_date = get_metadata_date(path)
    if metadata_date:
        return metadata_date
    filename_date = parse_date(path)
    if filename_date:
        return filename_date
    return get_earliest_date(path)


def write_image_date(path: Path, date_taken: datetime):
    exif_date = date_taken.strftime("%Y:%m:%d %H:%M:%S")

    if path.suffix.lower() in JPEG_EXTENSIONS:
        encoded_exif_date = exif_date.encode("ascii")
        exif = piexif.load(str(path))
        exif["0th"][piexif.ImageIFD.DateTime] = encoded_exif_date
        exif["Exif"][piexif.ExifIFD.DateTimeOriginal] = encoded_exif_date
        exif["Exif"][piexif.ExifIFD.DateTimeDigitized] = encoded_exif_date
        piexif.insert(piexif.dump(exif), str(path))
        return

    with Image.open(path) as image:
        image.load()
        exif = image.getexif()
        exif[EXIF_DATETIME_TAG] = exif_date
        exif_ifd = exif.get_ifd(EXIF_IFD_TAG)
        exif_ifd[EXIF_DATETIME_ORIGINAL_TAG] = exif_date
        exif_ifd[EXIF_DATETIME_DIGITIZED_TAG] = exif_date
        image.save(path, exif=exif)


def write_video_date(path: Path, date_taken: datetime):
    with NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.stem}-", suffix=path.suffix, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    # Container creation timestamps are UTC, while stamped filenames use local time.
    creation_time = date_taken.astimezone().astimezone(timezone.utc).isoformat(timespec="seconds")
    try:
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-map",
                "0",
                "-map_metadata",
                "0",
                "-c",
                "copy",
                "-metadata",
                f"creation_time={creation_time}",
                "-metadata",
                f"date={date_taken.isoformat(timespec='seconds')}",
                str(temporary_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        temporary_path.replace(path)
    except CalledProcessError as error:
        temporary_path.unlink(missing_ok=True)
        raise ValueError(f"Could not write video metadata for {path}: {error.stderr.strip()}") from error


def write_metadata_date(path: Path, date_taken: datetime):
    if not can_write_metadata(path):
        raise ValueError(f"Cannot write metadata for unsupported file type: {path}")

    if path.suffix.lower() in VIDEO_EXTENSIONS:
        write_video_date(path, date_taken)
    else:
        write_image_date(path, date_taken)

    return True


def write_named_date(path: Path):
    date_taken = parse_date(path)
    if date_taken is None:
        return False
    return write_metadata_date(path, date_taken)
