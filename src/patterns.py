import re
from datetime import datetime
from pathlib import Path


class Pattern:
    naming_pattern = ""
    date_format = ""
    date_groups: tuple[str, ...] = ()

    def match(self, path: Path):
        return re.fullmatch(self.naming_pattern, path.stem)

    def check_pattern(self, path: Path):
        return self.match(path) is not None

    def get_date(self, path: Path):
        match = self.match(path)
        if match is None:
            return None

        try:
            value = "".join(match.group(group) for group in self.date_groups)
            return datetime.strptime(value, self.date_format)
        except ValueError:
            return None


class PhotostampPattern(Pattern):
    # Example: 20260605-104448_XTMS
    naming_pattern = r"(?P<date>\d{8})-(?P<time>\d{6})_[a-zA-Z0-9]{4}"
    date_format = "%Y%m%d%H%M%S"
    date_groups = ("date", "time")


class ScreenshotsPattern(Pattern):
    # Example: Screenshot_20240114_110317_Mobile Legends Bang Bang
    naming_pattern = r"Screenshot_(?P<date>\d{8})_(?P<time>\d{6})(?:_.*)?"
    date_format = "%Y%m%d%H%M%S"
    date_groups = ("date", "time")


class WhatsAppPattern(Pattern):
    # Example: IMG-20210531-WA0000, VID-20210531-WA0000
    naming_pattern = r"(?:IMG|VID)-(?P<date>\d{8})-WA\d{4}"
    date_format = "%Y%m%d"
    date_groups = ("date",)


PHOTOSTAMP_PATTERN = PhotostampPattern()
NAMING_PATTERNS: tuple[Pattern, ...] = (
    PHOTOSTAMP_PATTERN,
    ScreenshotsPattern(),
    WhatsAppPattern(),
)


def parse_date(path: Path):
    for pattern in NAMING_PATTERNS:
        date = pattern.get_date(path)
        if date is not None:
            return date
    return None


def is_photostamp_name(path: Path):
    return PHOTOSTAMP_PATTERN.get_date(path) is not None
