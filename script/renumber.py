#!/usr/bin/env python3
"""현재 폴더에 있는 특정 확장자를 가진 파일의 이름을 정렬 후 순번으로 변경한다"""

import sys
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path
from re import compile, split

from library.cli import TerminalHelpFormatter, confirm_or_exit
from library.console import ConsoleColor, format_status


class RenumberArgs(Namespace):
    digit: int
    ext: str
    start: int
    target: Path | str
    yes: bool


def parse_args() -> RenumberArgs:
    cli = ArgumentParser(
        prog="renumber",
        description="Rename image files in a directory with sequential numbering.",
        formatter_class=TerminalHelpFormatter,
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
        type=lambda value: parse_int(value, non_negative=True),
        default=1,
        help="Starting number (non-negative)\n(default: 1)",
    )
    cli.add_argument(
        "-d",
        "--digit",
        type=lambda value: parse_int(value, positive=True),
        default=3,
        help="Number of digits in renamed files\n(default: 3)",
    )
    cli.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt\n(default: False)")
    cli.add_argument("target", default=str(Path.cwd()), nargs="?", help=f"Target directory\n(default: {Path.cwd()})")
    return cli.parse_args(namespace=RenumberArgs())


def main() -> None:
    args = parse_args()
    target = Path(args.target).resolve()

    if not target.is_dir():
        print(format_status("ERROR", ConsoleColor.RED, f"'{target}' is not a directory"))
        sys.exit(1)

    if not args.yes:
        print(format_status("TARGET", ConsoleColor.GREEN, str(target)))
        confirm_or_exit("Do you want to renumber image files of this directory? (yes/no): ")

    exts = [f".{extension.strip().lower()}" for extension in args.ext.split(",")]
    regex = compile(r"(\d+)")
    files = sorted(
        [file for file in target.iterdir() if file.suffix.lower() in exts and file.is_file()],
        key=lambda path: [int(part) if part.isdigit() else part.lower() for part in split(regex, str(path))],
    )

    if not files:
        print(format_status("ERROR", ConsoleColor.RED, f"No files with extension(s) {exts} in '{target}'."))
        return

    # 최종 이름과 충돌하지 않도록 먼저 임시 이름으로 모두 이동
    temp_files: list[tuple[str, Path]] = []
    for file in files:
        temp_path = target / f"rntmp-{file.name}"
        file.rename(temp_path)
        temp_files.append((file.name, temp_path))

    # 정렬된 순서를 기준으로 0-padding된 번호를 부여
    for index, (original, temp_path) in enumerate(temp_files, start=args.start):
        new_name = f"{str(index).zfill(args.digit)}{temp_path.suffix.lower()}"
        temp_path.rename(target / new_name)
        print(format_status("RENAME", ConsoleColor.YELLOW, f"{original} -> {new_name}"))

    print(format_status("INFO", ConsoleColor.GREEN, "Renumber complete."))


def parse_int(value: str, *, positive: bool = False, non_negative: bool = False) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise ArgumentTypeError(f"{value} is not a valid integer") from error

    if positive and number <= 0:
        raise ArgumentTypeError(f"{number} must be positive ({number} > 0)")
    if non_negative and number < 0:
        raise ArgumentTypeError(f"{number} must be non-negative ({number} >= 0)")
    return number


if __name__ == "__main__":
    main()
