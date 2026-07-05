from argparse import ArgumentParser
from pathlib import Path

from colorama import Fore

from engine import Item, get_items


def init():
    parser = ArgumentParser(description="Rename media files from EXIF dates, or write EXIF dates from stamped names.")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag, only preview changes.")
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Write image EXIF dates from Photostamp filenames instead of renaming files.",
    )
    args = parser.parse_args()
    main(args.files, apply=args.apply, write_metadata=args.metadata)


def main(files: list[str], apply: bool = False, write_metadata: bool = False):
    items = get_items([Path(file) for file in files])
    if write_metadata:
        process_metadata(items, apply=apply)
    else:
        process(items, apply=apply)

    if not apply:
        print(f"{Fore.YELLOW}Dry run only. Re-run with --apply to make changes.{Fore.RESET}")


def process(items: list[Item], count: int = 0, indent: int = 0, apply: bool = False):
    for item in items:
        count = count + 1
        print(" " * indent, end="")
        print(f"[{Fore.BLUE}#{count}{Fore.RESET}] ", end="")
        if item.is_dir:
            print(f"{Fore.CYAN}{item.name}{Fore.RESET}")
            count = process(item.items, count=count, indent=indent + 2, apply=apply)
        else:
            if item.proposed_name == item.name:
                print(f"{Fore.GREEN}{item.name}{Fore.RESET}")
            else:
                print(f"{Fore.YELLOW}{item.name}{Fore.RESET} -> {Fore.GREEN}{item.proposed_name}{Fore.RESET}")
            if apply:
                try:
                    item.rename()
                except FileExistsError as error:
                    print(f"{' ' * (indent + 2)}{Fore.YELLOW}Skipped: {error}{Fore.RESET}")
    return count


def process_metadata(items: list[Item], count: int = 0, indent: int = 0, apply: bool = False):
    for item in items:
        count = count + 1
        print(" " * indent, end="")
        print(f"[{Fore.BLUE}#{count}{Fore.RESET}] ", end="")
        if item.is_dir:
            print(f"{Fore.CYAN}{item.name}{Fore.RESET}")
            count = process_metadata(item.items, count=count, indent=indent + 2, apply=apply)
        elif item.filename_date is None:
            print(f"{Fore.GREEN}{item.name}{Fore.RESET}")
        elif not item.can_write_metadata:
            print(f"{Fore.YELLOW}{item.name}{Fore.RESET} metadata writing is unsupported for this file type")
        else:
            print(f"{Fore.YELLOW}{item.name}{Fore.RESET} -> {Fore.GREEN}EXIF date{Fore.RESET}")
            if apply:
                item.write_metadata_from_name()
    return count


if __name__ == "__main__":
    init()
