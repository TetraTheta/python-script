#!/usr/bin/env python3
"""소스 엔진 게임/모드를 게리 모드 애드온으로 변환한다"""

import os
import platform
import re
import stat
import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from fnmatch import fnmatch
from pathlib import Path
from shutil import move, rmtree

from library.console import ConsoleColor, format_status
from library.text_file import (
    normalize_newlines,
    print_exception,
    read_text_with_fallback,
    write_text,
)

SDK_SHADER_REPLACEMENTS = (
    (re.compile("SDK_LightmappedGeneric", re.IGNORECASE), "LightmappedGeneric"),
    (re.compile("SDK_Sprite", re.IGNORECASE), "Sprite"),
    (re.compile("SDK_VertexLitGeneric", re.IGNORECASE), "VertexLitGeneric"),
)
QUOTED_TEXT_PATTERN = re.compile(r'"([^"]*)"')
QUOTED_WHITESPACE_PATTERN = re.compile(r"[\t ]+")
NON_CRLF_NEWLINE_PATTERN = re.compile(r"(?<!\r)\n|\r(?!\n)")
GMAD_ADDON_WHITELIST = (
    "lua/*.lua",
    "scenes/*.vcd",
    "particles/*.pcf",
    "resource/fonts/*.ttf",
    "scripts/vehicles/*.txt",
    "resource/localization/*/*.properties",
    "maps/*.bsp",
    "maps/*.lmp",
    "maps/*.nav",
    "maps/*.ain",
    "maps/thumb/*.png",
    "sound/*.wav",
    "sound/*.mp3",
    "sound/*.ogg",
    "materials/*.vmt",
    "materials/*.vtf",
    "materials/*.png",
    "materials/*.jpg",
    "materials/*.jpeg",
    "materials/colorcorrection/*.raw",
    "models/*.mdl",
    "models/*.phy",
    "models/*.ani",
    "models/*.vvd",
    "models/*.vtx",
    "!models/*.sw.vtx",
    "!models/*.360.vtx",
    "!models/*.xbox.vtx",
    "gamemodes/*/*.txt",
    "!gamemodes/*/*/*.txt",
    "gamemodes/*/*.fgd",
    "!gamemodes/*/*/*.fgd",
    "gamemodes/*/logo.png",
    "gamemodes/*/icon24.png",
    "gamemodes/*/gamemode/*.lua",
    "gamemodes/*/entities/effects/*.lua",
    "gamemodes/*/entities/weapons/*.lua",
    "gamemodes/*/entities/entities/*.lua",
    "gamemodes/*/backgrounds/*.png",
    "gamemodes/*/backgrounds/*.jpg",
    "gamemodes/*/backgrounds/*.jpeg",
    "gamemodes/*/content/models/*.mdl",
    "gamemodes/*/content/models/*.phy",
    "gamemodes/*/content/models/*.ani",
    "gamemodes/*/content/models/*.vvd",
    "gamemodes/*/content/models/*.vtx",
    "!gamemodes/*/content/models/*.sw.vtx",
    "!gamemodes/*/content/models/*.360.vtx",
    "!gamemodes/*/content/models/*.xbox.vtx",
    "gamemodes/*/content/materials/*.vmt",
    "gamemodes/*/content/materials/*.vtf",
    "gamemodes/*/content/materials/*.png",
    "gamemodes/*/content/materials/*.jpg",
    "gamemodes/*/content/materials/*.jpeg",
    "gamemodes/*/content/materials/colorcorrection/*.raw",
    "gamemodes/*/content/scenes/*.vcd",
    "gamemodes/*/content/particles/*.pcf",
    "gamemodes/*/content/resource/fonts/*.ttf",
    "gamemodes/*/content/scripts/vehicles/*.txt",
    "gamemodes/*/content/resource/localization/*/*.properties",
    "gamemodes/*/content/maps/*.bsp",
    "gamemodes/*/content/maps/*.nav",
    "gamemodes/*/content/maps/*.ain",
    "gamemodes/*/content/maps/thumb/*.png",
    "gamemodes/*/content/sound/*.wav",
    "gamemodes/*/content/sound/*.mp3",
    "gamemodes/*/content/sound/*.ogg",
    "data_static/*.txt",
    "data_static/*.dat",
    "data_static/*.json",
    "data_static/*.xml",
    "data_static/*.csv",
    "shaders/fxc/*.vcs",
)
TOP_LEVEL_CUSTOM_FILE_POLICY_DIRS = {"resource", "scripts"}
PRESERVED_EMPTY_DIRS = {"resource", "scripts"}
SCRIPT_REMOVE_PATTERNS = ("*manifest.txt", "chapterbackgrounds.txt")


class GmodMapAddonArgs(Namespace):
    target: Path | str


def parse_args() -> GmodMapAddonArgs:
    parser = ArgumentParser(description="Clean a SourceMod folder so it can be packed as a Garry's Mod addon.")
    parser.add_argument("target", nargs="?", default=str(Path.cwd()), help="Addon directory")
    return parser.parse_args(namespace=GmodMapAddonArgs())


def main() -> None:
    args = parse_args()
    target = Path(args.target)

    # maps 폴더 사전 확인
    maps_dir = target / "maps"
    if not maps_dir.is_dir():
        bsp_files = list(target.glob("*.bsp"))
        if not bsp_files:
            print(format_status("ERROR", ConsoleColor.RED, "'maps' directory not found. Aborting..."))
            sys.exit(1)
        maps_dir.mkdir(exist_ok=True)
        for bsp in bsp_files:
            move(str(bsp), maps_dir / bsp.name)

    print(format_status("INFO", ConsoleColor.GREEN, f"Processing '{target.name}'"))

    # BSP/AIN 파일명을 소문자로 변경
    print(format_status("INFO", ConsoleColor.GREEN, "Sanitize BSP/AIN file name"))
    for bsp_path in maps_dir.glob("*.bsp"):
        new_name = sanitize_source_name(bsp_path.stem) + bsp_path.suffix
        new_path = bsp_path.with_name(new_name)
        if new_path != bsp_path:
            print(format_status("RENAME", ConsoleColor.YELLOW, f"{bsp_path.name} -> {new_name}"))
            bsp_path.rename(new_path)

    graphs_dir = maps_dir / "graphs"
    if graphs_dir.is_dir():
        for ain_path in graphs_dir.glob("*.ain"):
            new_name = sanitize_source_name(ain_path.stem) + ain_path.suffix
            new_path = ain_path.with_name(new_name)
            if new_path != ain_path:
                print(format_status("RENAME", ConsoleColor.YELLOW, f"{ain_path.name} -> {new_name}"))
                ain_path.rename(new_path)

    # 모든 파일/폴더명을 소문자로 변경
    print(format_status("INFO", ConsoleColor.GREEN, "Lowercase file/dir names"))
    items = sorted(target.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for item in items:
        new_name = item.name.lower()
        if item.name == new_name:
            continue
        new_path = item.with_name(new_name)
        print(
            format_status(
                "RENAME",
                ConsoleColor.YELLOW,
                f"{item.parent}{os.sep}{{{ConsoleColor.YELLOW}{item.name}{ConsoleColor.RESET} -> {ConsoleColor.YELLOW}{new_name}{ConsoleColor.RESET}}}",
            )
        )
        try:
            remove_readonly(item)
            item.rename(new_path)
        except OSError as error:
            print(format_status("ERROR", ConsoleColor.RED, f"Failed to rename '{item}': {error}"))

    # data_static 폴더 생성
    data_static = target / "data_static"
    data_static.mkdir(exist_ok=True)

    # readme/readmes 폴더 아래의 파일을 모두 data_static으로 이동
    for readme_dir in (target / "readme", target / "readmes"):
        if readme_dir.is_dir():
            for file in readme_dir.iterdir():
                if file.is_file():
                    dest = data_static / file.name
                    print(format_status("MOVE", ConsoleColor.GREEN, f"{file} -> {dest}"))
                    move(file, dest)
    # readme 파일을 data_static으로 이동
    for file in target.glob("readme*"):
        if file.is_file():
            print(format_status("MOVE", ConsoleColor.GREEN, f"{file.name} -> data_static/{file.name}"))
            move(str(file), data_static / file.name)

    # 불필요한 파일/폴더 제거
    print(format_status("INFO", ConsoleColor.GREEN, "Remove directories"))
    for name in [
        "bin",
        "cfg",
        "downloadlists",
        "materials/console",
        "materials/vgui",
        "materialsrc",
        "media",
        "save",
        "screenshots",
        "sound/ui",
        "steam-grid-view-images",
        "steam-gridview-icons",
        "steam-gridview-images",
    ]:
        path = target.joinpath(*Path(name).parts).resolve()
        if path.exists() and path.is_dir():
            print(format_status("REMOVE", ConsoleColor.YELLOW, str(path)))
            rmtree(path, onexc=retry_after_remove_readonly)

    print(format_status("INFO", ConsoleColor.GREEN, "Remove files"))
    remove_files_by_policy(target, should_remove_by_gmad_whitelist(target))
    remove_files_by_policy(target / "resource", lambda path: not fnmatch(path.name.lower(), "*.txt"))
    remove_files_by_policy(
        target / "scripts",
        lambda path: any(fnmatch(path.name.lower(), pattern) for pattern in SCRIPT_REMOVE_PATTERNS),
    )

    # MapBase 전용 셰이더명을 일반 Source Engine/GMod 셰이더명으로 치환
    print(format_status("INFO", ConsoleColor.GREEN, "Modifying material files"))
    for vmt in (target / "materials").rglob("*.vmt"):
        try:
            remove_readonly(vmt)
            content = read_text_with_fallback(vmt)
            normalized_content = normalize_vmt_content(content)
            if content_needs_vmt_update(content, normalized_content):
                write_text(vmt, normalized_content, line_ending="\r\n")
        except OSError as error:
            print_exception(error)

    # gamemode 파일 생성
    gamemodes_dir = target / "gamemodes"
    gamemodes_dir.mkdir(exist_ok=True)

    dir_name = target.name
    safe_name = sanitize_source_name(dir_name)
    maps = sorted(path.stem for path in maps_dir.glob("*.bsp"))
    maps_str = "|".join(maps)

    print(format_status("INFO", ConsoleColor.GREEN, f"Creating Gamemode file ({safe_name}.txt)"))
    gamemode_txt = gamemodes_dir / safe_name / f"{safe_name}.txt"
    gamemode_txt.parent.mkdir(parents=True, exist_ok=True)
    write_text(
        gamemode_txt,
        f""""{safe_name}"
{{
  "title" "{dir_name}"
  "maps" "{maps_str}"
  "menusystem" "0"
  "source" ""
}}
""",
    )

    # addon.json 파일 생성
    print(format_status("INFO", ConsoleColor.GREEN, "Creating 'addon.json' file"))
    write_text(
        target / "addon.json",
        f"""{{
  "title": "{dir_name}",
  "type": "map",
  "tags": [
    "scenic",
    "realism"
  ],
  "ignore": [
    "*.log",
    "*.vmf",
    "*.vmx",
    ".ignore/*",
    "AGENTS.md",
    "README.md",
    "fgd/*",
    "lua/.ignore/*",
    "lua/weapons/.ignore/*",
    "maps_original/*",
    "mapsrc/*",
    "models/.ignore/*",
    "modelsrc/*",
    "thumb.jpg",
    "thumb.png"
  ]
}}
""",
    )

    # 빈 폴더 정리
    print(format_status("INFO", ConsoleColor.GREEN, "Remove empty directories"))
    remove_empty_directory(target, target)
    print(format_status("INFO", ConsoleColor.GREEN, "DONE"))


def remove_empty_directory(current: Path, root: Path) -> None:
    if not current.is_dir():
        return

    try:
        is_junction = current.is_junction() if platform.system() == "Windows" else False
        if current.is_symlink() or is_junction:
            print(format_status("SYMLNK", ConsoleColor.BLUE, str(current)))
            return

        for child in current.iterdir():
            if child.is_dir():
                remove_empty_directory(child, root)

        if current != root:
            if current.parent == root and current.name in PRESERVED_EMPTY_DIRS:
                return
            try:
                current.rmdir()
                print(
                    format_status(
                        "REMOVE",
                        ConsoleColor.YELLOW,
                        f"{current.parent}{os.sep}{ConsoleColor.YELLOW}{current.name}{ConsoleColor.RESET}",
                    )
                )
            except OSError:
                pass
    except PermissionError:
        print(format_status("PERM", ConsoleColor.RED, str(current)))
    except NotADirectoryError:
        pass


def remove_files_by_policy(target: Path, should_remove: Callable[[Path], bool]) -> None:
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        if not should_remove(path):
            continue
        print(format_status("REMOVE", ConsoleColor.YELLOW, str(path)))
        try:
            remove_readonly(path)
            path.unlink()
        except OSError as error:
            print(format_status("ERROR", ConsoleColor.RED, f"Failed to delete '{path}': {error}"))


def should_remove_by_gmad_whitelist(root: Path) -> Callable[[Path], bool]:
    def should_remove(path: Path) -> bool:
        relative_path = path.relative_to(root)
        if len(relative_path.parts) > 1 and relative_path.parts[0] in TOP_LEVEL_CUSTOM_FILE_POLICY_DIRS:
            return False
        return not is_gmad_whitelisted(relative_path.as_posix().lower())

    return should_remove


def is_gmad_whitelisted(path: str) -> bool:
    valid = False
    for pattern in GMAD_ADDON_WHITELIST:
        if pattern.startswith("!"):
            if fnmatch(path, pattern[1:]):
                valid = False
            continue
        if not valid:
            valid = fnmatch(path, pattern)
    return valid


def remove_readonly(path: Path) -> None:
    if path.exists():
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IWRITE)


def retry_after_remove_readonly(
    func: Callable[[str], object],
    path: str,
    _: BaseException,
) -> None:
    remove_readonly(Path(path))
    func(path)


def normalize_vmt_content(content: str) -> str:
    normalized = normalize_newlines(content)
    for pattern, replacement in SDK_SHADER_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    normalized = "\n".join(line for line in normalized.splitlines() if line.strip())
    return QUOTED_TEXT_PATTERN.sub(normalize_quoted_whitespace, normalized)


def normalize_quoted_whitespace(match: re.Match[str]) -> str:
    return f'"{QUOTED_WHITESPACE_PATTERN.sub(" ", match.group(1))}"'


def content_needs_vmt_update(content: str, normalized_content: str) -> bool:
    return normalize_newlines(content) != normalized_content or NON_CRLF_NEWLINE_PATTERN.search(content) is not None


def sanitize_source_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_").lower()


if __name__ == "__main__":
    main()
