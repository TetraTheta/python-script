#!/usr/bin/env python3
"""
소스 엔진 맵의 소스 코드에 있는 불필요한 대문자를 제거한다
모든 문자를 소문자로 변환한 후, 핵심적인 요소만 다시 CamelCase로 변환한다
"""

import csv
import sys
from argparse import ArgumentParser, Namespace
from io import StringIO
from pathlib import Path

from library.console import ConsoleColor, format_status
from library.text_file import add_file_error_note, print_exception, read_text, read_text_with_fallback, write_text

DATA_DIR = Path(__file__).with_name("library") / "data"


def load_map_source_pairs(filename: str) -> tuple[tuple[str, str], ...]:
    path = DATA_DIR / filename
    file = StringIO(read_text(path, encoding="utf-8"), newline="")
    reader = csv.reader(file)
    try:
        next(reader, None)
        return tuple((old, new) for old, new in reader)
    except csv.Error as error:
        add_file_error_note(error, path, "parse", line=reader.line_num or None, column=1)
        raise


INPUT_GENERIC = load_map_source_pairs("mapsrc_input.csv")
INPUT_MOD = [("env_textgal", "game_text")]
OUTPUT_GENERIC = load_map_source_pairs("mapsrc_output.csv")
OUTPUT_MOD = [("displaytext", "Display")]
ENTITY_MOD = [("env_textgal", "game_text")]

INPUTS = (*INPUT_GENERIC, *INPUT_MOD, *ENTITY_MOD)
OUTPUTS = (*OUTPUT_GENERIC, *OUTPUT_MOD)


class GmodMapSourceArgs(Namespace):
    target: Path | str


def parse_args() -> GmodMapSourceArgs:
    parser = ArgumentParser(description="Normalize Source Engine VMF entity input/output casing.")
    parser.add_argument("target", nargs="?", default=str(Path.cwd()), help="VMF file or directory")
    return parser.parse_args(namespace=GmodMapSourceArgs())


def main() -> None:
    args = parse_args()
    target = Path(args.target)

    if target.is_file() and target.suffix == ".vmf":
        print(format_status("INFO", ConsoleColor.GREEN, f"Processing '{target.name}'"))
        normalize_vmf_entities(target)
    elif target.is_dir():
        for source in target.glob("*.vmf"):
            print(format_status("INFO", ConsoleColor.GREEN, f"Processing '{source.name}'"))
            normalize_vmf_entities(source)
    else:
        print(format_status("ERROR", ConsoleColor.RED, "There is no file to process"), file=sys.stderr)


def normalize_vmf_entities(target: Path) -> None:
    if target.suffix != ".vmf":
        print(format_status("ERROR", ConsoleColor.RED, f"'{target.name}' is not a VMF file"), file=sys.stderr)
        sys.exit(1)

    try:
        content = read_text_with_fallback(target).lower()
        # VMF 소문자 -> CamelCase 변환
        for old, new in INPUTS:
            content = content.replace(f'"{old}"', f'"{new}"')
        separator = chr(27)  # ESC
        for old, new in OUTPUTS:
            content = content.replace(f"{separator}{old}{separator}", f"{separator}{new}{separator}")
        write_text(target, content)
    except OSError as error:
        print_exception(error)


if __name__ == "__main__":
    main()
