import re
from datetime import datetime
from pathlib import Path
from typing import Optional


class Pattern:
    def check_pattern(self, path: Path) -> bool:
        return False

    def get_date(self, path: Path) -> Optional[datetime]:
        return None


class ScreenshotsPattern(Pattern):
    # example: Screenshot_20240114_110317_Mobile Legends Bang Bang
    NAMING_PATTERN = r"Screenshot_\d{8}_\d{6}_.*"

    def check_pattern(self, path: Path):
        return re.fullmatch(self.NAMING_PATTERN, path.stem) is not None

    def get_date(self, path: Path):
        try:
            split = path.stem.split("_")
            time = datetime.strptime(split[1] + split[2], "%Y%m%d%H%M%S")
            return time
        except Exception:
            return None


class WhatsAppPattern(Pattern):
    # example: IMG-20210531-WA0000, VID-20210531-WA0000
    NAMING_PATTERN = r"(IMG|VID)-\d{8}-WA\d{4}"

    def check_pattern(self, path: Path):
        return re.fullmatch(self.NAMING_PATTERN, path.stem) is not None

    def get_date(self, path: Path):
        try:
            time = datetime.strptime(path.name.split("-")[1], "%Y%m%d")
            return time
        except Exception:
            return None
