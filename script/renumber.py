from __future__ import annotations

import shutil
import sys
from argparse import ArgumentParser, ArgumentTypeError, Namespace, RawTextHelpFormatter
from pathlib import Path
from re import compile, split


class Color:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"


class CustomFormatter(RawTextHelpFormatter):
    def __init__(self, prog: str) -> None:
        width = max(80, shutil.get_terminal_size().columns - 2)
        super().__init__(prog, width=width)


class RenumberNamespace(Namespace):
    digit: int
    ext: str
    start: int
    target: str | Path
    yes: bool


def check_int(value: str, *, positive: bool = False, non_negative: bool = False) -> int:
    try:
        number = int(value)
        if positive and number <= 0:
            raise ArgumentTypeError(f"{number} must be positive ({number} > 0)")
        if non_negative and number < 0:
            raise ArgumentTypeError(f"{number} must be non-negative ({number} >= 0)")
        return number
    except ValueError as error:
        raise ArgumentTypeError(f"{value} is not a valid integer") from error


def natural_sort(lst: list[Path]) -> list[Path]:
    regex = compile(r"(\d+)")
    return sorted(
        lst,
        key=lambda p: [int(s) if s.isdigit() else s.lower() for s in split(regex, str(p))],
    )


def renumber(directory: Path, ext: str, digit: int, start: int) -> None:
    exts = [f".{e.strip().lower()}" for e in ext.split(",")]
    files = natural_sort([file for file in directory.iterdir() if file.suffix.lower() in exts and file.is_file()])

    if not files:
        print(f"{Color.RED}[ERROR ]{Color.RESET} No files with extension(s) {exts} in '{directory}'.")
        return

    temp_files: list[tuple[str, Path]] = []
    for file in files:
        temp_path = directory / f"rntmp-{file.name}"
        file.rename(temp_path)
        temp_files.append((file.name, temp_path))
    for index, (original, temp_path) in enumerate(temp_files, start=start):
        new_name = f"{str(index).zfill(digit)}{temp_path.suffix.lower()}"
        temp_path.rename(directory / new_name)
        print(f"{Color.YELLOW}[RENAME]{Color.RESET} {original} → {new_name}")

    print(f"{Color.GREEN}[ INFO ]{Color.RESET} Renumber complete.")


def main() -> None:
    cli = ArgumentParser(
        prog="renumber",
        description="Rename image files in a directory with sequential numbering.",
        formatter_class=CustomFormatter,
    )
    cli.add_argument(
        "-e",
        "--ext",
        type=str,
        default="webp",
        choices=["bmp", "gif", "jpg", "png", "webp"],
        help="Extension(s) of image files to rename, separated by commas\n(default: webp)",
    )
    cli.add_argument(
        "-s",
        "--start",
        type=lambda v: check_int(v, non_negative=True),
        default=1,
        help="Starting number (non-negative)\n(default: 1)",
    )
    cli.add_argument(
        "-d",
        "--digit",
        type=lambda v: check_int(v, positive=True),
        default=3,
        help="Number of digits in renamed files\n(default: 3)",
    )
    cli.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt\n(default: False)",
    )
    cli.add_argument(
        "target",
        default=str(Path.cwd()),
        nargs="?",
        help=f"Target directory\n(default: {Path.cwd()})",
    )

    args = cli.parse_args(namespace=RenumberNamespace())
    args.target = Path(args.target).resolve()

    if not args.target.is_dir():
        print(f"{Color.RED}[ERROR ]{Color.RESET} '{args.target}' is not a directory")
        sys.exit(1)

    if not args.yes:
        print(f"{Color.GREEN}[TARGET]{Color.RESET} {args.target}")
        result = input("Do you want to renumber image files of this directory? (yes/no): ").strip().lower()
        if not result.startswith("y"):
            print(f"{Color.RED}[ERROR ]{Color.RESET} Operation canceled")
            sys.exit(1)

    renumber(args.target, args.ext, args.digit, args.start)


if __name__ == "__main__":
    main()
