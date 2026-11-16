#!/usr/bin/env python3
"""Source 모드의 gameinfo.txt를 정리하고 검색 경로를 설정한다."""

from argparse import ArgumentParser, Namespace
from dataclasses import replace
from os import link
from pathlib import Path
from tempfile import TemporaryDirectory

from library.cli import TerminalHelpFormatter
from library.text_file import normalize_newlines, read_text_with_fallback, write_text
from library.valve_vmt import KeyValueBlock, KeyValueEntry, parse_keyvalue_document

APP_ID = "243730"
TAB_WIDTH = 4
LEFTOVERS = "// Leftovers"
SEARCH_PATHS = """\
// User customizations
game+mod |gameinfo_path|custom/*
game+mod |all_source_engine_paths|ep2/custom/*
game+mod |all_source_engine_paths|episodic/custom/*
game+mod |all_source_engine_paths|hl2/custom/*
// Loose files of MOD
game+mod+mod_write+default_write_path |gameinfo_path|.
gamebin |gameinfo_path|bin
// Mapbase
gamebin |gameinfo_path|../mapbase_episodic/bin
game+mod |gameinfo_path|../mapbase_episodic
game+mod |gameinfo_path|../mapbase_episodic/content/*
game+mod |gameinfo_path|../mapbase_hl2
game+mod |gameinfo_path|../mapbase_hl2/content/*
game+mod |gameinfo_path|../mapbase_shared/shared_misc
gamebin |gameinfo_path|../mapbase_shared/shared_misc/bin
game+mod |gameinfo_path|../mapbase_shared/shared_content_v7_0.vpk
// Mapbase (internal)
game+mod |all_source_engine_paths|mapbase/css_weapons_in_hl2/content/*
game+mod |all_source_engine_paths|mapbase/css_weapons_in_hl2
// HL2/EP1/EP2
game_lv hl2/hl2_lv.vpk
game+mod ep2/ep2_english.vpk
game+mod ep2/ep2_pak.vpk
game |all_source_engine_paths|episodic/ep1_english.vpk
game |all_source_engine_paths|episodic/ep1_pak.vpk
game |all_source_engine_paths|hl2/hl2_english.vpk
game |all_source_engine_paths|hl2/hl2_pak.vpk
game |all_source_engine_paths|hl2/hl2_textures.vpk
game |all_source_engine_paths|hl2/hl2_sound_vo_english.vpk
game |all_source_engine_paths|hl2/hl2_sound_misc.vpk
game |all_source_engine_paths|hl2/hl2_misc.vpk
game |all_source_engine_paths|sourcetest/sourcetest_pak.vpk
game |all_source_engine_paths|lostcoast/lostcoast_pak.vpk
platform |all_source_engine_paths|platform/platform_misc.vpk
game+game_write ep2
gamebin episodic/bin
// Loose files of HL2/EP1/EP2
game |all_source_engine_paths|episodic
game |all_source_engine_paths|hl2
platform |all_source_engine_paths|platform
"""


class GameInfoArgs(Namespace):
    target: Path


def parse_args() -> GameInfoArgs:
    """입력 파일이나 모드 디렉터리 경로를 받는다."""
    parser = ArgumentParser(description=__doc__, formatter_class=TerminalHelpFormatter)
    parser.add_argument("target", type=Path, help="gameinfo.txt 또는 모드 디렉터리")
    return parser.parse_args(namespace=GameInfoArgs())


def find_gameinfo(target: Path) -> Path:
    """디렉터리에서 유일한 gameinfo.txt를 찾는다."""
    if target.is_file() and target.name.casefold() == "gameinfo.txt":
        return target.resolve()
    if target.is_dir():
        matches = [path for path in target.iterdir() if path.name.casefold() == "gameinfo.txt" and path.is_file()]
        if len(matches) == 1:
            return matches[0].resolve()
    raise ValueError(f"gameinfo.txt 파일을 하나만 지정해야 합니다. ({target})")


def quote_token(token: str) -> str:
    """따옴표 없이 표현할 수 있는 토큰은 그대로 출력한다."""
    has_syntax = "//" in token or any(char.isspace() or char in "{}\"'" for char in token)
    if token and not has_syntax:
        return token
    escaped = token.replace('"', '\\"')
    return f'"{escaped}"'


def render_value(entry: KeyValueEntry, key: str, column: int = 0) -> str:
    """값과 조건, 인라인 주석을 한 줄로 출력한다."""
    if not isinstance(entry.value, str):
        raise TypeError(f"문자열 값이 필요합니다. ({entry.key})")
    tabs = "\t" * max(1, column // TAB_WIDTH - len(key) // TAB_WIDTH)
    line = f"{key}{tabs}{quote_token(entry.value)}"
    if entry.condition is not None:
        line += f" {entry.condition}"
    if entry.trailing_comment is not None:
        line += f" {entry.trailing_comment}"
    return line


def render_block(block: KeyValueBlock, depth: int, aligned: KeyValueBlock | None) -> list[str]:
    """항목과 주석의 순서를 유지하며 블록을 출력한다."""
    indent = "\t" * depth
    lines: list[str] = []
    column = 0
    leftover_start = len(block.trailing_comments)
    if block is aligned:
        if LEFTOVERS in block.trailing_comments:
            leftover_start = block.trailing_comments.index(LEFTOVERS) + 1
        widths = [len(quote_token(entry.key)) for entry in block.entries]
        widths.extend(len(comment.partition("\t")[0]) for comment in block.trailing_comments[leftover_start:] if "\t" in comment)
        column = (max(widths, default=0) // TAB_WIDTH + 1) * TAB_WIDTH
    for entry in block.entries:
        lines.extend(f"{indent}{comment}" for comment in entry.comments)
        key = quote_token(entry.key)
        if isinstance(entry.value, str):
            lines.append(f"{indent}{render_value(entry, key, column)}")
            continue
        lines.extend((f"{indent}{key}", f"{indent}{{"))
        lines.extend(render_block(entry.value, depth + 1, aligned))
        closing = f"{indent}}}"
        if entry.condition is not None:
            closing += f" {entry.condition}"
        if entry.trailing_comment is not None:
            closing += f" {entry.trailing_comment}"
        lines.append(closing)
    for index, comment in enumerate(block.trailing_comments):
        if index >= leftover_start and "\t" in comment:
            key, _, value = comment.partition("\t")
            tabs = "\t" * (column // TAB_WIDTH - len(key) // TAB_WIDTH)
            value = value.lstrip("\t")
            comment = f"{key}{tabs}{value}"
        lines.append(f"{indent}{comment}")
    return lines


def require_entry(block: KeyValueBlock, key: str) -> KeyValueEntry:
    """지정된 이름을 가진 유일한 항목을 찾는다."""
    matches = [entry for entry in block.entries if entry.key.casefold() == key.casefold()]
    if len(matches) != 1:
        raise ValueError(f"{key} 항목이 정확히 하나 필요합니다.")
    return matches[0]


def replace_entry(block: KeyValueBlock, original: KeyValueEntry, updated: KeyValueEntry) -> KeyValueBlock:
    """블록 안의 대상 항목만 교체한다."""
    return replace(block, entries=tuple(updated if entry is original else entry for entry in block.entries))


def update_search_paths(block: KeyValueBlock) -> KeyValueBlock:
    """표준 검색 경로를 배치하고 나머지 경로를 주석 처리한다."""
    template = parse_keyvalue_document(f"SearchPaths\n{{\n{SEARCH_PATHS}}}").block
    headings = {comment for entry in template.entries for comment in entry.comments}
    pending = list(block.entries)
    entries: list[KeyValueEntry] = []

    for standard in template.entries:
        for index, entry in enumerate(pending):
            if entry.key.casefold() == standard.key.casefold() and entry.value == standard.value and entry.condition is None:
                pending.pop(index)
                comments = tuple(comment for comment in entry.comments if comment not in headings)
                standard = replace(
                    standard,
                    comments=standard.comments + comments,
                    trailing_comment=entry.trailing_comment,
                )
                break
        entries.append(standard)

    comments = list(block.trailing_comments)
    if pending and LEFTOVERS not in comments:
        comments.append(LEFTOVERS)
    for entry in pending:
        comments.extend(comment for comment in entry.comments if comment not in headings)
        comments.append(render_value(entry, f"// {quote_token(entry.key)}"))
    return KeyValueBlock(tuple(entries), tuple(comments))


def format_gameinfo(text: str) -> tuple[str, str]:
    """포맷팅한 백업 텍스트와 설정을 변경한 텍스트를 반환한다."""
    document = parse_keyvalue_document(normalize_newlines(text))
    if document.shader.casefold() != "gameinfo":
        raise ValueError("최상위 GameInfo 블록이 필요합니다.")

    fs_entry = require_entry(document.block, "FileSystem")
    filesystem = fs_entry.value
    if isinstance(filesystem, str):
        raise TypeError("FileSystem 블록이 필요합니다.")
    paths_entry = require_entry(filesystem, "SearchPaths")
    app = require_entry(filesystem, "SteamAppId")
    if isinstance(paths_entry.value, str) or not isinstance(app.value, str):
        raise TypeError("SearchPaths 블록과 SteamAppId 값이 필요합니다.")

    root = quote_token(document.shader)
    if document.shader_comment is not None:
        root += f" {document.shader_comment}"
    header = [*document.leading_comments, root, *document.comments_before_brace, "{"]
    footer = ["}", *document.trailing_comments, ""]
    backup = "\n".join([*header, *render_block(document.block, 1, None), *footer])

    paths = update_search_paths(paths_entry.value)
    updated = replace_entry(filesystem, paths_entry, replace(paths_entry, value=paths))
    if app.value != APP_ID:
        comment = f"// SG: was {quote_token(app.value)}"
        if app.trailing_comment is not None:
            comment = f"{app.trailing_comment} {comment}"
        updated = replace_entry(updated, app, replace(app, value=APP_ID, trailing_comment=comment))
    block = replace_entry(document.block, fs_entry, replace(fs_entry, value=updated))
    return backup, "\n".join([*header, *render_block(block, 1, paths), *footer])


def main() -> None:
    """백업을 확보한 뒤 수정본으로 원본을 교체한다."""
    target = find_gameinfo(parse_args().target)
    backup, updated = format_gameinfo(read_text_with_fallback(target))
    backup_path = target.with_name("gameinfo.bak.txt")
    with TemporaryDirectory(dir=target.parent) as directory:
        staged = Path(directory) / target.name
        write_text(staged, updated, line_ending="\r\n")
        if not backup_path.is_file():
            staged_backup = Path(directory) / backup_path.name
            write_text(staged_backup, backup, line_ending="\r\n")
            try:
                link(staged_backup, backup_path)
            except FileExistsError:
                if not backup_path.is_file():
                    raise
        staged.replace(target)
    print(target)


if __name__ == "__main__":
    main()
