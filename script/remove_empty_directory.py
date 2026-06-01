#!/usr/bin/env python3
"""주어진 경로 아래의 모든 빈 폴더를 제거한다"""

import os
import platform
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from library.cli import TerminalHelpFormatter, confirm_or_exit
from library.console import ConsoleColor, format_status


class RemoveEmptyDirectoryArgs(Namespace):
    target: Path | str
    yes: bool


def parse_args() -> RemoveEmptyDirectoryArgs:
    cli = ArgumentParser(
        prog="remove-empty-directory",
        description="Remove empty directories from given path",
        formatter_class=TerminalHelpFormatter,
    )
    cli.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt\n(default: False)")
    cli.add_argument("target", default=str(Path.cwd()), nargs="?", help=f"Target directory\n(default: {Path.cwd()})")
    return cli.parse_args(namespace=RemoveEmptyDirectoryArgs())


def main() -> None:
    # Windows junction 판별에 Path.is_junction()을 사용하므로 3.12 이상이 필요함
    if sys.version_info < (3, 12):
        print(format_status("ERROR", ConsoleColor.RED, "This script requires Python version above 3.12"))
        sys.exit(1)

    args = parse_args()
    target = Path(args.target).resolve()

    if not target.is_dir():
        print(format_status("ERROR", ConsoleColor.RED, f"'{target}' is not a directory"))
        sys.exit(1)

    if not args.yes:
        print(format_status("TARGET", ConsoleColor.GREEN, str(target)))
        confirm_or_exit(
            "Do you want to remove empty directories from this path? (yes/no): ",
            cancel_message="Operation canceled",
        )

    if platform.system() == "Windows":
        raw_exclusion = [r"%AppData%\\Microsoft", r"%LocalAppData%\\Microsoft"]
        exclusions = [Path(os.path.expandvars(path)).resolve() for path in raw_exclusion]
    else:
        exclusions = []

    remove_empty_directories(target, target, exclusions)


def remove_empty_directories(current: Path, root: Path, exclusions: list[Path]) -> None:
    if not current.is_dir():
        return

    try:
        is_junction = current.is_junction() if platform.system() == "Windows" else False
        is_symlink = current.is_symlink()

        if is_symlink or is_junction:
            print(format_status("SYMLNK", ConsoleColor.BLUE, str(current)))
            return

        for child in current.iterdir():
            if not child.is_dir():
                continue
            try:
                resolved = child.resolve(strict=False)
                if any(resolved.is_relative_to(exclusion) for exclusion in exclusions):
                    print(format_status("SKIP", ConsoleColor.BLUE, str(child)))
                    continue
            except OSError:
                pass
            remove_empty_directories(child, root, exclusions)

        if current != root:
            try:
                current.rmdir()
                print(format_status("REMOVE", ConsoleColor.YELLOW, f"{current.parent}{os.sep}{current.name}"))
            except OSError:
                pass
    except PermissionError:
        print(format_status("PERM", ConsoleColor.RED, str(current)))
    except NotADirectoryError:
        pass


if __name__ == "__main__":
    main()
