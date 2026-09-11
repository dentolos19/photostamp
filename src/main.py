from argparse import ArgumentParser
from pathlib import Path

from colorama import Fore

from engine import Item, get_items


def init():
    parser = ArgumentParser(description="Rename media files from dates and repair image or video metadata.")
    parser.add_argument("files", nargs="+")
    parser.add_argument(
        "--apply", action="store_true", help="Apply file and metadata changes. Without this flag, only preview changes."
    )
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Write metadata without renaming files.",
    )
    parser.add_argument("--add-years", type=int, default=0, help="Add years to embedded metadata dates.")
    parser.add_argument("--add-months", type=int, default=0, help="Add months to embedded metadata dates.")
    parser.add_argument("--add-days", type=int, default=0, help="Add days to embedded metadata dates.")
    parser.add_argument("--add-hours", type=int, default=0, help="Add hours to embedded metadata dates.")
    parser.add_argument("--add-minutes", type=int, default=0, help="Add minutes to embedded metadata dates.")
    args = parser.parse_args()
    date_offset = (args.add_years, args.add_months, args.add_days, args.add_hours, args.add_minutes)
    main(args.files, apply=args.apply, write_metadata=args.metadata, date_offset=date_offset)


def main(
    files: list[str],
    apply: bool = False,
    write_metadata: bool = False,
    date_offset: tuple[int, int, int, int, int] | None = None,
):
    if date_offset == (0, 0, 0, 0, 0):
        date_offset = None
    items = get_items([Path(file) for file in files], date_offset=date_offset)
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
            if item.should_write_metadata:
                print(
                    f"{Fore.YELLOW}{item.name}{Fore.RESET} -> {Fore.GREEN}{item.proposed_name}{Fore.RESET} "
                    f"and metadata date"
                )
            elif item.proposed_name == item.name:
                print(f"{Fore.GREEN}{item.name}{Fore.RESET}")
            else:
                print(f"{Fore.YELLOW}{item.name}{Fore.RESET} -> {Fore.GREEN}{item.proposed_name}{Fore.RESET}")
            if apply:
                try:
                    item.rename()
                    if item.should_write_metadata:
                        item.write_metadata()
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
        elif item.adjusted_metadata_date is not None:
            if not item.can_write_metadata:
                print(f"{Fore.YELLOW}{item.name}{Fore.RESET} metadata writing is unsupported for this file type")
            else:
                adjusted_date = item.adjusted_metadata_date.strftime("%Y-%m-%d %H:%M:%S")
                print(f"{Fore.YELLOW}{item.name}{Fore.RESET} -> {Fore.GREEN}{adjusted_date}{Fore.RESET}")
                if apply:
                    item.write_metadata()
        elif item.filename_date is None:
            print(f"{Fore.GREEN}{item.name}{Fore.RESET}")
        elif not item.can_write_metadata:
            print(f"{Fore.YELLOW}{item.name}{Fore.RESET} metadata writing is unsupported for this file type")
        else:
            print(f"{Fore.YELLOW}{item.name}{Fore.RESET} -> {Fore.GREEN}metadata date{Fore.RESET}")
            if apply:
                item.write_named_metadata()
    return count


if __name__ == "__main__":
    init()
