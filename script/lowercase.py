#!/usr/bin/env python3
"""주어진 경로 아래의 모든 파일/폴더 이름을 소문자로 변경한다"""

import os
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from library.cli import TerminalHelpFormatter, confirm_or_exit
from library.console import ConsoleColor, format_status


class LowercaseArgs(Namespace):
    target: Path | str
    yes: bool


def parse_args() -> LowercaseArgs:
    cli = ArgumentParser(
        prog="lowercase",
        description="Convert uppercase characters to lowercase in file and directory names.",
        formatter_class=TerminalHelpFormatter,
    )
    cli.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt\n(default: False)")
    cli.add_argument("target", default=str(Path.cwd()), nargs="?", help=f"Target directory\n(default: {Path.cwd()})")
    return cli.parse_args(namespace=LowercaseArgs())


def main() -> None:
    args = parse_args()
    target = Path(args.target).resolve()

    if not target.is_dir():
        print(format_status("ERROR", ConsoleColor.RED, f"'{args.target}' is not a directory"))
        sys.exit(1)

    if not args.yes:
        print(format_status("TARGET", ConsoleColor.GREEN, str(args.target)))
        confirm_or_exit("Do you want to lowercase all subdirectory and files in this path? (yes/no): ")

    # 깊은 경로부터 처리
    items = sorted(target.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for item in items:
        new_name = item.name.lower()
        if item.name == new_name:
            continue

        new_path = item.with_name(new_name)
        print(
            f"{format_status('RENAME', ConsoleColor.YELLOW)} "
            f"{item.parent}{os.sep}{{{ConsoleColor.YELLOW}{item.name}{ConsoleColor.RESET} -> "
            f"{ConsoleColor.YELLOW}{new_name}{ConsoleColor.RESET}}}"
        )
        try:
            item.rename(new_path)
        except OSError as error:
            print(format_status("ERROR", ConsoleColor.RED, f"Failed to rename '{item}': {error}"))


if __name__ == "__main__":
    main()
