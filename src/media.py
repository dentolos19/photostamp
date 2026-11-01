import logging
import sys
import warnings
import zlib
from datetime import UTC, datetime
from pathlib import Path
from shutil import copystat, which
from subprocess import CalledProcessError, run
from tempfile import NamedTemporaryFile

import piexif
from hachoir.core import config as hachoir_config
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

from patterns import parse_date

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS: list[str] = [".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"]
JPEG_EXTENSIONS: list[str] = [".jpeg", ".jpg"]
VIDEO_EXTENSIONS: list[str] = [".avi", ".flv", ".mkv", ".mov", ".mp4", ".webm", ".wmv"]
WRITABLE_IMAGE_METADATA_EXTENSIONS: list[str] = [
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
]
MIN_VALID_YEAR = 1970
MIN_VALID_DATE = datetime(MIN_VALID_YEAR, 1, 1).astimezone()
EXIF_IFD_TAG = 0x8769
EXIF_DATETIME_TAG = 0x0132
EXIF_DATETIME_ORIGINAL_TAG = 0x9003
EXIF_DATETIME_DIGITIZED_TAG = 0x9004

warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
hachoir_config.quiet = True  # ty: ignore[invalid-assignment] - Hachoir exposes a mutable runtime flag.


def is_supported_media(path: Path):
    return path.suffix.lower() in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS


def can_write_metadata(path: Path):
    suffix = path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        try:
            with Image.open(path) as image:
                return getattr(image, "n_frames", 1) == 1
        except OSError:
            return False
    return suffix in WRITABLE_IMAGE_METADATA_EXTENSIONS or (
        suffix in VIDEO_EXTENSIONS and which("ffmpeg") is not None
    )


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
    date_modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC).astimezone()

    # st_birthtime is only available on Windows and macOS; Linux exposes st_ctime
    # (inode change time) instead, which is not the true creation time, so we
    # treat it as a candidate alongside the modification time and pick the earliest.
    birthtime = getattr(stat, "st_birthtime", None)
    if sys.platform == "win32" or birthtime is not None:
        date_created = datetime.fromtimestamp(birthtime, tz=UTC).astimezone()
    else:
        date_created = datetime.fromtimestamp(stat.st_ctime, tz=UTC).astimezone()

    candidate_dates = sorted(
        (date_created, date_modified), key=lambda date: date.timestamp()
    )

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
            exif_ifd = exif.get_ifd(EXIF_IFD_TAG)
            raw_date_taken = (
                exif_ifd.get(EXIF_DATETIME_ORIGINAL_TAG)
                or exif.get(EXIF_DATETIME_ORIGINAL_TAG)
                or exif_ifd.get(EXIF_DATETIME_DIGITIZED_TAG)
                or exif.get(EXIF_DATETIME_DIGITIZED_TAG)
                or exif.get(EXIF_DATETIME_TAG)
            )
        if raw_date_taken:
            if isinstance(raw_date_taken, bytes):
                raw_date_taken = raw_date_taken.decode("ascii")
            date_taken = datetime.strptime(
                raw_date_taken, "%Y:%m:%d %H:%M:%S"
            ).astimezone()
    except Exception:
        logger.exception("Could not read image metadata for %s", path)
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
            media_date = media_date.replace(tzinfo=UTC)
        media_date = media_date.astimezone()
        if is_valid_date(media_date):
            return media_date
        return None
    except Exception:
        logger.exception("Could not read video metadata for %s", path)
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
    # Replace the target, rather than a symlink pointing to it.
    suffix = path.suffix.lower()
    path = path.resolve(strict=True)
    exif_date = date_taken.strftime("%Y:%m:%d %H:%M:%S")
    with NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.stem}-", suffix=suffix, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        if suffix in JPEG_EXTENSIONS:
            encoded_exif_date = exif_date.encode("ascii")
            exif = piexif.load(str(path))
            exif["0th"][piexif.ImageIFD.DateTime] = encoded_exif_date
            exif["Exif"][piexif.ExifIFD.DateTimeOriginal] = encoded_exif_date
            exif["Exif"][piexif.ExifIFD.DateTimeDigitized] = encoded_exif_date
            piexif.insert(piexif.dump(exif), str(path), str(temporary_path))
        else:
            with Image.open(path) as image:
                if suffix in {".tif", ".tiff"} and getattr(image, "n_frames", 1) > 1:
                    raise ValueError(
                        f"Cannot safely write metadata to a multi-frame image: {path}"
                    )
                image.load()
                exif = image.getexif()
                exif[EXIF_DATETIME_TAG] = exif_date
                exif_ifd = exif.get_ifd(EXIF_IFD_TAG)
                exif_ifd[EXIF_DATETIME_ORIGINAL_TAG] = exif_date
                exif_ifd[EXIF_DATETIME_DIGITIZED_TAG] = exif_date
                if suffix == ".webp":
                    # Inserting an EXIF chunk avoids recompressing lossy image data.
                    with path.open("rb") as source:
                        header = source.read(30)
                    piexif.insert(exif.tobytes(), str(path), str(temporary_path))
                    if header[12:20] == b"VP8X\x0a\x00\x00\x00":
                        # piexif rebuilds VP8X from individual animation frames;
                        # keep the original canvas and flags, adding only EXIF.
                        with temporary_path.open("r+b") as output:
                            output.seek(20)
                            output.write(bytes([header[20] | 0x08]) + header[21:30])
                elif suffix == ".png":
                    # Copy every other chunk verbatim, including animation and
                    # application-specific metadata, without recompressing pixels.
                    exif_chunk = b"eXIf" + exif.tobytes()[6:]
                    with path.open("rb") as source, temporary_path.open("wb") as output:
                        signature = source.read(8)
                        if signature != b"\x89PNG\r\n\x1a\n":
                            raise ValueError(f"Not a PNG image: {path}")
                        output.write(signature)
                        written = False
                        while True:
                            header = source.read(8)
                            if len(header) != 8:
                                raise ValueError(f"Incomplete PNG image: {path}")
                            length = int.from_bytes(header[:4], "big")
                            chunk_type = header[4:]
                            if chunk_type == b"IDAT" and not written:
                                output.write((len(exif_chunk) - 4).to_bytes(4, "big"))
                                output.write(exif_chunk)
                                output.write(zlib.crc32(exif_chunk).to_bytes(4, "big"))
                                written = True
                            if chunk_type != b"eXIf":
                                output.write(header)
                            remaining = length + 4
                            while remaining:
                                chunk = source.read(min(remaining, 1024 * 1024))
                                if not chunk:
                                    raise ValueError(f"Incomplete PNG image: {path}")
                                if chunk_type != b"eXIf":
                                    output.write(chunk)
                                remaining -= len(chunk)
                            if chunk_type == b"IEND":
                                if not written:
                                    raise ValueError(f"PNG has no image data: {path}")
                                while chunk := source.read(1024 * 1024):
                                    output.write(chunk)
                                break
                else:
                    image.save(temporary_path, exif=exif)
        copystat(path, temporary_path)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_video_date(path: Path, date_taken: datetime):
    suffix = path.suffix
    path = path.resolve(strict=True)
    with NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.stem}-", suffix=suffix, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    # Container creation timestamps are UTC, while stamped filenames use local time.
    creation_time = (
        date_taken.astimezone().astimezone(UTC).isoformat(timespec="seconds")
    )
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
        copystat(path, temporary_path)
        temporary_path.replace(path)
    except CalledProcessError as error:
        raise ValueError(
            f"Could not write video metadata for {path}: {error.stderr.strip()}"
        ) from error
    finally:
        temporary_path.unlink(missing_ok=True)


def write_metadata_date(path: Path, date_taken: datetime):
    if not can_write_metadata(path):
        raise ValueError(f"Cannot write metadata for unsupported media: {path}")

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
