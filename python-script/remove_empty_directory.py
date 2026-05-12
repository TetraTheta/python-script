from __future__ import annotations

import os
import platform
import shutil
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path


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


class RemoveEmptyDirectoryNamespace(Namespace):
    target: str | Path = Path.cwd()
    yes: bool = False


def get_exclusion_paths() -> list[Path]:
    opsys = platform.system()
    if opsys == "Windows":
        raw_exclusion = [
            r"%AppData%\\Microsoft",
            r"%LocalAppData%\\Microsoft",
        ]
    else:
        return []
    return [Path(os.path.expandvars(p)).resolve() for p in raw_exclusion]


def remove_empty_directory(current: Path, root: Path, exclusion: list[Path]) -> None:
    if not current.is_dir():
        return

    try:
        is_junction = current.is_junction() if platform.system() == "Windows" else False
        is_symlink = current.is_symlink()

        if is_symlink or is_junction:
            print(f"{Color.BLUE}[SYMLINK]{Color.RESET} {current}")
            return

        for child in current.iterdir():
            if child.is_dir():
                try:
                    resolved = child.resolve(strict=False)
                    if any(resolved.is_relative_to(exc) for exc in exclusion):
                        print(f"{Color.BLUE}[ SKIP  ]{Color.RESET} {child}")
                        continue
                except OSError:
                    pass
                remove_empty_directory(child, root, exclusion)

        if current != root:
            try:
                current.rmdir()
                print(
                    f"{Color.YELLOW}[REMOVE ]{Color.RESET} "
                    f"{current.parent}{os.sep}{Color.YELLOW}{current.name}{Color.RESET}"
                )
            except OSError:
                pass

    except PermissionError:
        print(f"{Color.RED}[PERMERR]{Color.RESET} {current}")
    except NotADirectoryError:
        pass


def main() -> None:
    # Path.is_junction() is available on Python 3.12 and newer.
    if sys.version_info < (3, 12):
        print(f"{Color.RED}[ ERROR ]{Color.RESET} This script requires Python version above 3.12")
        sys.exit(1)

    cli = ArgumentParser(
        prog="remove-empty-directory",
        description="Remove empty directories from given path",
        formatter_class=CustomFormatter,
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

    args = cli.parse_args(namespace=RemoveEmptyDirectoryNamespace())
    target = Path(args.target).resolve()

    if not target.is_dir():
        print(f"{Color.RED}[ ERROR ]{Color.RESET} '{target}' is not a directory")
        sys.exit(1)

    if not args.yes:
        print(f"{Color.GREEN}[TARGET ]{Color.RESET} {target}")
        result = input("Do you want to remove empty directories from this path? (yes/no): ").strip().lower()
        if not result.startswith("y"):
            print(f"{Color.RED}[CANCEL ]{Color.RESET} Operation canceled")
            sys.exit(1)

    exclusions = get_exclusion_paths()
    remove_empty_directory(target, target, exclusions)


if __name__ == "__main__":
    main()
