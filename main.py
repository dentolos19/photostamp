from argparse import ArgumentParser
from pathlib import Path

from colorama import Fore

from engine import Item, get_items


def init():
    parser = ArgumentParser()
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    main(args.files)


def main(files: list[str], test: bool = False):
    items = get_items([Path(file) for file in files])
    process(items, test=test)
    input()


def process(items: list[Item], count: int = 0, indent: int = 0, test: bool = False):
    for item in items:
        count = count + 1
        print(" " * indent, end="")
        print(f"[{Fore.BLUE}#{count}{Fore.RESET}] ", end="")
        if item.is_dir:
            print(f"{Fore.CYAN}{item.name}{Fore.RESET}")
            count = process(item.items, count=count, indent=indent + 2, test=test)
        else:
            if item.proposed_name == item.name:
                print(f"{Fore.GREEN}{item.name}{Fore.RESET}")
            else:
                print(f"{Fore.YELLOW}{item.name}{Fore.RESET} -> {Fore.GREEN}{item.proposed_name}{Fore.RESET}")
            if not test:
                item.rename()
    return count


if __name__ == "__main__":
    init()
