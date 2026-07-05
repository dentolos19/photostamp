import os
from pathlib import Path

from media import can_write_metadata, get_media_date, is_supported_media, write_metadata_date_from_name
from patterns import parse_date
from utils import generate_random_string

MAX_NAME_ATTEMPTS = 1000


def dates_match(first, second):
    return first.strftime("%Y%m%d-%H%M%S") == second.strftime("%Y%m%d-%H%M%S")


def generate_media_name(path: Path, reserved_names: set[str], media_date):
    suffix = path.suffix.lower()

    for _ in range(MAX_NAME_ATTEMPTS):
        candidate = f"{media_date.strftime('%Y%m%d-%H%M%S')}_{generate_random_string(4)}{suffix}"
        if candidate == path.name:
            return candidate
        if candidate not in reserved_names and not path.with_name(candidate).exists():
            return candidate

    raise FileExistsError(f"Could not find an available target name for {path}")


def set_linked_name(
    linked_path: Path,
    name: str,
    linked_names: dict[Path, str],
    linked_items: dict[Path, list["Item"]],
):
    linked_names[linked_path] = name
    for item in linked_items.get(linked_path, []):
        item.proposed_name = name


def symlink_target_for_path(current_symlink_path: Path, new_symlink_path: Path, target_path: Path):
    current_target = os.readlink(current_symlink_path)
    if Path(current_target).is_absolute():
        return target_path
    return Path(os.path.relpath(target_path, new_symlink_path.parent))


class Item:
    def __init__(
        self,
        path: Path,
        reserved_names: set[str] | None = None,
        linked_names: dict[Path, str] | None = None,
        linked_items: dict[Path, list["Item"]] | None = None,
        linked_target_paths: dict[Path, Path] | None = None,
    ):
        self.path = path
        self.name = path.name
        self.proposed_name = path.name
        self.is_dir = path.is_dir()
        self.is_supported_media = False
        self.filename_date = None
        self.can_write_metadata = False
        self.linked_path: Path | None = None
        self.linked_target_paths: dict[Path, Path] = {}
        self.items: list[Item] = []
        if linked_names is None:
            linked_names = {}
        if linked_items is None:
            linked_items = {}
        if linked_target_paths is None:
            linked_target_paths = {}
        self.linked_target_paths = linked_target_paths

        if self.is_dir:
            files = list(path.iterdir())
            self.items = get_items(
                files,
                linked_names=linked_names,
                linked_items=linked_items,
                linked_target_paths=linked_target_paths,
            )
        else:
            self.is_supported_media = is_supported_media(path)
            self.filename_date = parse_date(path)
            self.can_write_metadata = can_write_metadata(path)

            if not self.is_supported_media:
                return

            media_date = get_media_date(path)
            if not media_date:
                return

            linked_path = path.resolve()
            self.linked_path = linked_path
            linked_items.setdefault(linked_path, []).append(self)
            has_current_name = self.filename_date and dates_match(media_date, self.filename_date)
            has_normalized_suffix = path.suffix == path.suffix.lower()
            if has_current_name and has_normalized_suffix:
                set_linked_name(linked_path, self.name, linked_names, linked_items)
                if not path.is_symlink():
                    linked_target_paths[linked_path] = path
                return

            if reserved_names is None:
                reserved_names = set()
            linked_name = linked_names.get(linked_path)
            if linked_name is None:
                linked_name = generate_media_name(path, reserved_names, media_date)
                set_linked_name(linked_path, linked_name, linked_names, linked_items)
                reserved_names.add(linked_name)
            self.proposed_name = linked_name
            if not path.is_symlink():
                linked_target_paths[linked_path] = path.with_name(linked_name)

    def rename(self):
        if self.is_dir:
            return False
        if self.path.is_symlink():
            return self.rename_symlink()
        if self.name == self.proposed_name:
            return False
        target = self.path.with_name(self.proposed_name)
        if target.exists():
            try:
                if target.samefile(self.path):
                    return False
            except FileNotFoundError:
                return False
            raise FileExistsError(f"Cannot rename {self.path} because {target} already exists")
        self.path = self.path.rename(target)
        self.name = self.path.name
        return True

    def rename_symlink(self):
        if self.linked_path is None:
            return False
        target = self.path.with_name(self.proposed_name)
        if os.path.lexists(target) and target != self.path:
            raise FileExistsError(f"Cannot rename {self.path} because {target} already exists")

        linked_target = self.linked_target_paths.get(self.linked_path)
        if linked_target is None:
            linked_target = self.linked_path.with_name(self.proposed_name)
        symlink_target = symlink_target_for_path(self.path, target, linked_target)

        self.path.unlink()
        target.symlink_to(symlink_target)
        self.path = target
        self.name = self.path.name
        return True

    def write_metadata_from_name(self):
        if self.is_dir or self.filename_date is None:
            return False
        return write_metadata_date_from_name(self.path)


def get_items(
    paths: list[Path],
    linked_names: dict[Path, str] | None = None,
    linked_items: dict[Path, list[Item]] | None = None,
    linked_target_paths: dict[Path, Path] | None = None,
):
    if linked_names is None:
        linked_names = {}
    if linked_items is None:
        linked_items = {}
    if linked_target_paths is None:
        linked_target_paths = {}
    if len(paths) == 1 and paths[0].is_dir():
        return get_items(
            list(paths[0].iterdir()),
            linked_names=linked_names,
            linked_items=linked_items,
            linked_target_paths=linked_target_paths,
        )
    reserved_names = {path.name for path in paths}
    return [
        Item(
            path,
            reserved_names=reserved_names,
            linked_names=linked_names,
            linked_items=linked_items,
            linked_target_paths=linked_target_paths,
        )
        for path in paths
    ]
