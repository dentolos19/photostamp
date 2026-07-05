import re
from pathlib import Path

from media import get_media_date
from utils import generate_random_string

NAMING_PATTERN = r"\d{8}-\d{6}_[a-zA-Z0-9]{4}"


class Item:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.proposed_name = path.name
        self.is_dir = path.is_dir()
        self.items: list[Item] = []

        if self.is_dir:
            files = list(path.iterdir())
            self.items = get_items(files)
        else:
            if not re.fullmatch(NAMING_PATTERN, path.stem):
                time = get_media_date(path)
                self.proposed_name = (
                    (f"{time.strftime('%Y%m%d-%H%M%S')}_{generate_random_string(4)}{path.suffix.lower()}")
                    if time
                    else self.name
                )

    def rename(self):
        if self.is_dir or self.name == self.proposed_name:
            return False
        self.path = self.path.rename(self.path.with_name(self.proposed_name))
        self.name = self.path.name
        return True


def get_items(paths: list[Path]):
    if len(paths) == 1 and paths[0].is_dir():
        return get_items(list(paths[0].iterdir()))
    return [Item(path) for path in paths]
