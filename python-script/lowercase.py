import os
import shutil
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path


class Color:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"


class CustomFormatter(RawTextHelpFormatter):
    def __init__(self, prog):
        width = max(80, shutil.get_terminal_size().columns - 2)
        super().__init__(prog, width=width)


class LowercaseNamespace:
    target: str | Path
    yes: bool


def lowercase_names(dir: Path):
    items = sorted(dir.rglob("*"), key=lambda p: len(p.parts), reverse=True)

    for item in items:
        new_name = item.name.lower()
        if item.name != new_name:
            new_path = item.with_name(new_name)
            print(
                f"{Color.YELLOW}[RENAME]{Color.RESET} {item.parent}{os.sep}{{{Color.YELLOW}{item.name}{Color.RESET} → {Color.YELLOW}{new_name}{Color.RESET}}}"
            )
            try:
                item.rename(new_path)
            except OSError as e:
                print(f"{Color.RED}[ERROR ]{Color.RESET} Failed to rename '{item}': {e}")


##########
#  MAIN  #
##########
def main():
    cli = ArgumentParser(
        prog="lowercase",
        description="Convert uppercase characters to lowercase in file and directory names.",
        formatter_class=CustomFormatter,
    )
    cli.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt\n(default: False)")
    cli.add_argument(
        "target", default=str(Path.cwd()), nargs="?", help=f"Target directory\n(default: {Path.cwd()})"
    )  # I can't use 'type=Path' because it can't handle '.' being passed to it

    args = cli.parse_args(namespace=LowercaseNamespace())
    target = Path(args.target).resolve()

    if not target.is_dir():
        print(f"{Color.RED}[ERROR ]{Color.RESET} '{args.target}' is not a directory")
        sys.exit(1)

    if not args.yes:
        print(f"{Color.GREEN}[TARGET]{Color.RESET} {args.target}")
        result = input("Do you want to lowercase all subdirectory and files in this path? (yes/no): ").strip().lower()
        if not result.startswith("y"):
            print(f"{Color.RED}[ERROR ]{Color.RESET} Operation canceled")
            sys.exit(1)

    lowercase_names(target)


if __name__ == "__main__":
    main()
