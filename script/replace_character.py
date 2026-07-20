#!/usr/bin/env python3
"""텍스트 파일의 특정 문자열을 특수 문자로 변환하거나 역으로 되돌린다"""

import re
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from pathlib import Path

from library.text_file import print_exception, read_text, write_text


class ReplaceCharacterArgs(Namespace):
    paths: list[str]
    reverse: bool


def parse_args() -> ReplaceCharacterArgs:
    parser = ArgumentParser(
        description="Replace ASCII typographic shortcuts with proper Unicode symbols.",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python replace_character.py notes.txt
  python replace_character.py --reverse notes.md
  python replace_character.py docs/
  python replace_character.py --reverse docs/ notes.txt
""",
    )
    parser.add_argument("paths", nargs="+", metavar="PATH", help="Files or directories to process (.txt and .md only)")
    parser.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="Reverse mode: convert Unicode symbols back to ASCII equivalents",
    )
    return parser.parse_args(namespace=ReplaceCharacterArgs())


def main() -> None:
    args = parse_args()

    for raw_path in args.paths:
        path = Path(raw_path)
        if path.is_file():
            transform_text_file(path, reverse=args.reverse)
        elif path.is_dir():
            print(f"Scanning directory: {path}")
            for file in path.rglob("*"):
                if file.is_file():
                    transform_text_file(file, reverse=args.reverse)
        else:
            print(f"! Path not found: {raw_path}", file=sys.stderr)


def replace_typographic_shortcuts(text: str) -> str:
    # 긴 기호를 먼저 바꿔야 짧은 패턴이 일부만 소비하는 일을 피할 수 있음
    text = re.sub(r"<<", "«", text)
    text = re.sub(r">>", "»", text)
    text = re.sub(r"<=", "⇐", text)
    text = re.sub(r"=>", "⇒", text)
    text = re.sub(r"<-", "←", text)
    text = re.sub(r"->", "→", text)

    # 정확히 두 개의 대시와 세 개의 점만 typographic 문자로 바꿈
    text = re.sub(r"(?<!-)--(?!-)", "―", text)
    text = re.sub(r"(?<!\.)\.\.\.(?!\.)", "…", text)

    # Python의 \w는 유니코드를 인식하므로 한글/CJK 주변 따옴표도 같은 규칙으로 처리
    text = re.sub(r'(^|[\s(\[{])"', lambda match: match.group(1) + "\u201c", text, flags=re.MULTILINE)
    text = re.sub(r'"', "\u201d", text)
    text = re.sub(r"(?<=\w)'(?=\w)", "\u2019", text)
    text = re.sub(
        r"(^|[\s(\[{])'(?=\S)",
        lambda match: match.group(1) + "\u2018",
        text,
        flags=re.MULTILINE,
    )
    return re.sub(r"'", "\u2019", text)


def restore_typographic_shortcuts(text: str) -> str:
    reverse_map = [
        ("«", "<<"),
        ("»", ">>"),
        ("⇐", "<="),
        ("⇒", "=>"),
        ("←", "<-"),
        ("→", "->"),
        ("―", "--"),
        ("…", "..."),
        ("\u201c", '"'),
        ("\u201d", '"'),
        ("\u2018", "'"),
        ("\u2019", "'"),
    ]
    for fancy, plain in reverse_map:
        text = text.replace(fancy, plain)
    return text


def transform_text_file(file_path: Path, reverse: bool = False) -> None:
    if file_path.suffix.lower() not in (".txt", ".md"):
        return

    try:
        content = read_text(file_path, encoding="utf-8")
        new_content = restore_typographic_shortcuts(content) if reverse else replace_typographic_shortcuts(content)

        if content != new_content:
            write_text(file_path, new_content, encoding="utf-8")
            print(f"Processed: {file_path}")
        else:
            print(f"No changes: {file_path}")
    except OSError as error:
        print_exception(error)


if __name__ == "__main__":
    main()
