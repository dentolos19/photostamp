import os
from calendar import monthrange
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from media import (
    can_write_metadata,
    get_media_date,
    get_metadata_date,
    is_supported_media,
    write_metadata_date,
    write_named_date,
)
from patterns import is_photostamp_name, parse_date
from utils import generate_random_string

MAX_NAME_ATTEMPTS = 1000


def dates_match(first, second):
    return first.strftime("%Y%m%d-%H%M%S") == second.strftime("%Y%m%d-%H%M%S")


def add_date_offset(date_value, offset: tuple[int, int, int, int, int] | None):
    if offset is None or date_value is None:
        return None

    years, months, days, hours, minutes = offset
    month_index = (date_value.year + years) * 12 + date_value.month - 1 + months
    adjusted_year, adjusted_month_index = divmod(month_index, 12)
    adjusted_month = adjusted_month_index + 1
    if not 1 <= adjusted_year <= 9999:
        raise ValueError(
            f"Date offset moves {date_value:%Y-%m-%d %H:%M:%S} outside the supported year range"
        )

    adjusted_day = min(date_value.day, monthrange(adjusted_year, adjusted_month)[1])
    try:
        return date_value.replace(
            year=adjusted_year, month=adjusted_month, day=adjusted_day
        ) + timedelta(
            days=days,
            hours=hours,
            minutes=minutes,
        )
    except (OverflowError, ValueError) as error:
        raise ValueError(
            f"Cannot apply date offset to {date_value:%Y-%m-%d %H:%M:%S}"
        ) from error


def generate_media_name(path: Path, reserved_names: set[str], media_date):
    suffix = path.suffix.lower()

    for _ in range(MAX_NAME_ATTEMPTS):
        candidate = f"{media_date.strftime('%Y%m%d-%H%M%S')}_{generate_random_string(4)}{suffix}"
        if candidate == path.name:
            return candidate
        if candidate not in reserved_names and not os.path.lexists(
            path.with_name(candidate)
        ):
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


def get_symlink_target(
    current_symlink_path: Path, new_symlink_path: Path, target_path: Path
):
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
        date_offset: tuple[int, int, int, int, int] | None = None,
        ancestors: frozenset[Path] = frozenset(),
    ):
        self.path = path
        self.name = path.name
        self.proposed_name = path.name
        self.is_dir = path.is_dir()
        self.is_cycle = self.is_dir and path.resolve() in ancestors
        self.is_supported_media = False
        self.filename_date = None
        self.can_write_metadata = False
        self.should_write_metadata = False
        self.adjusted_metadata_date = None
        self.metadata_date_to_write = None
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
            if self.is_cycle:
                return
            files = list(path.iterdir())
            self.items = get_items(
                files,
                linked_names=linked_names,
                linked_items=linked_items,
                linked_target_paths=linked_target_paths,
                date_offset=date_offset,
                ancestors=ancestors | {path.resolve()},
            )
        else:
            self.is_supported_media = is_supported_media(path)
            self.filename_date = parse_date(path)
            self.can_write_metadata = can_write_metadata(path)

            if not self.is_supported_media:
                return

            metadata_date = get_metadata_date(path)
            media_date = get_media_date(path)
            if not media_date:
                return
            self.adjusted_metadata_date = add_date_offset(metadata_date, date_offset)
            if self.adjusted_metadata_date is not None:
                media_date = self.adjusted_metadata_date
                self.metadata_date_to_write = self.adjusted_metadata_date
            elif self.filename_date is not None and metadata_date is None:
                self.metadata_date_to_write = self.filename_date
            self.should_write_metadata = (
                self.metadata_date_to_write is not None and self.can_write_metadata
            )

            linked_path = path.resolve()
            self.linked_path = linked_path
            has_current_name = is_photostamp_name(path) and dates_match(
                media_date, self.filename_date
            )
            has_normalized_suffix = path.suffix == path.suffix.lower()
            if reserved_names is None:
                reserved_names = set()

            # A link and its target in the same directory cannot share a name.
            if path.is_symlink() and path.parent.resolve() == linked_path.parent:
                if not (has_current_name and has_normalized_suffix):
                    self.proposed_name = generate_media_name(
                        path, reserved_names, media_date
                    )
                    reserved_names.add(self.proposed_name)
                return

            linked_items.setdefault(linked_path, []).append(self)
            if has_current_name and has_normalized_suffix:
                set_linked_name(linked_path, self.name, linked_names, linked_items)
                if not path.is_symlink():
                    linked_target_paths[linked_path] = path
                return

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
        if os.path.lexists(target):
            try:
                if target.samefile(self.path):
                    return False
            except FileNotFoundError:
                pass
            raise FileExistsError(
                f"Cannot rename {self.path} because {target} already exists"
            )
        self.path = self.path.rename(target)
        self.name = self.path.name
        return True

    def rename_symlink(self):
        if self.linked_path is None:
            return False
        target = self.path.with_name(self.proposed_name)
        if os.path.lexists(target) and target != self.path:
            raise FileExistsError(
                f"Cannot rename {self.path} because {target} already exists"
            )

        linked_target = self.linked_target_paths.get(self.linked_path)
        if linked_target is None:
            linked_target = self.linked_path
        symlink_target = get_symlink_target(self.path, target, linked_target)

        if target == self.path:
            if Path(os.readlink(self.path)) == symlink_target:
                return False
            with TemporaryDirectory(
                dir=self.path.parent, prefix=f".{self.path.stem}-"
            ) as directory:
                temporary_link = Path(directory) / self.path.name
                temporary_link.symlink_to(symlink_target)
                temporary_link.replace(self.path)
        else:
            target.symlink_to(symlink_target)
            self.path.unlink()
        self.path = target
        self.name = self.path.name
        return True

    def write_named_metadata(self):
        if self.is_dir or self.filename_date is None:
            return False
        return write_named_date(self.path)

    def write_metadata(self):
        if self.is_dir or self.metadata_date_to_write is None:
            return False
        path = self.path
        if path.is_symlink() and not path.exists() and self.linked_path is not None:
            path = self.linked_path
        return write_metadata_date(path, self.metadata_date_to_write)


def get_items(
    paths: list[Path],
    linked_names: dict[Path, str] | None = None,
    linked_items: dict[Path, list[Item]] | None = None,
    linked_target_paths: dict[Path, Path] | None = None,
    date_offset: tuple[int, int, int, int, int] | None = None,
    ancestors: frozenset[Path] = frozenset(),
):
    if linked_names is None:
        linked_names = {}
    if linked_items is None:
        linked_items = {}
    if linked_target_paths is None:
        linked_target_paths = {}
    if len(paths) == 1 and paths[0].is_dir() and paths[0].resolve() not in ancestors:
        return get_items(
            list(paths[0].iterdir()),
            linked_names=linked_names,
            linked_items=linked_items,
            linked_target_paths=linked_target_paths,
            date_offset=date_offset,
            ancestors=ancestors | {paths[0].resolve()},
        )
    reserved_names = {path.name for path in paths}
    return [
        Item(
            path,
            reserved_names=reserved_names,
            linked_names=linked_names,
            linked_items=linked_items,
            linked_target_paths=linked_target_paths,
            date_offset=date_offset,
            ancestors=ancestors,
        )
        for path in paths
    ]
