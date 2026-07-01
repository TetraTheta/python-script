#!/usr/bin/env python3
"""소스 엔진 게임/모드를 게리 모드 애드온으로 변환한다"""

import os
import platform
import re
import stat
import sys
from argparse import ArgumentParser, Namespace
from fnmatch import fnmatch
from pathlib import Path
from shutil import move, rmtree
from typing import Callable

from library.console import ConsoleColor, format_status
from library.text_file import read_text_with_fallback, write_text


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
            rmtree(path, onerror=retry_after_remove_readonly)

    print(format_status("INFO", ConsoleColor.GREEN, "Remove files"))
    remove_files_matching_patterns(
        target,
        [
            "*.bak",
            "*.cache",
            "*.db",
            "*.image",
            "*.raw",
            "*.tga",
            "*.sw.vtx",
            "*.xbox.vtx",
            "desktop.ini",
        ],
    )
    remove_files_except_patterns(target / "materials", ["*.vmt", "*.vtf"])
    remove_files_matching_patterns(target / "models", ["*.vtf", "*.vmt", "*.jpg", "*.png"])
    remove_files_matching_patterns(target / "particles", ["particles_manifest.txt"])
    remove_files_except_patterns(target / "resource", ["*.txt"])
    remove_files_matching_patterns(target / "scripts", ["*manifest.txt", "chapterbackgrounds.txt"])

    # MapBase 전용 셰이더명을 일반 Source Engine/GMod 셰이더명으로 치환
    print(format_status("INFO", ConsoleColor.GREEN, "Modifying material files"))
    for vmt in (target / "materials").rglob("*.vmt"):
        try:
            remove_readonly(vmt)
            content = read_text_with_fallback(vmt)
            content = content.replace('"SDK_LightmappedGeneric"', '"LightmappedGeneric"')
            content = content.replace('"SDK_Sprite"', '"Sprite"')
            content = content.replace('"SDK_VertexLitGeneric"', '"VertexLitGeneric"')
            write_text(vmt, content)
        except OSError as error:
            print(format_status("ERROR", ConsoleColor.RED, f"Failed to process '{vmt}': {error}"))

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
    gamemode_txt.write_text(f""""{safe_name}"
{{
  "title" "{dir_name}"
  "maps" "{maps_str}"
  "menusystem" "0"
  "source" ""
}}
""")

    # addon.json 파일 생성
    print(format_status("INFO", ConsoleColor.GREEN, "Creating 'addon.json' file"))
    (target / "addon.json").write_text(f"""{{
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
    "maps_original/*",
    "mapsrc/*",
    "modelsrc/*",
  ]
}}
""")

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


def remove_files_except_patterns(target: Path, patterns: list[str]) -> None:
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        keep = any(fnmatch(path.name.lower(), pattern) for pattern in patterns)
        if keep:
            continue
        print(format_status("REMOVE", ConsoleColor.YELLOW, str(path)))
        try:
            remove_readonly(path)
            path.unlink()
        except OSError as error:
            print(format_status("ERROR", ConsoleColor.RED, f"Failed to delete '{path}': {error}"))


def remove_files_matching_patterns(target: Path, patterns: list[str]) -> None:
    for pattern in patterns:
        for path in target.rglob(pattern):
            if not path.is_file():
                continue
            print(format_status("REMOVE", ConsoleColor.YELLOW, str(path)))
            try:
                remove_readonly(path)
                path.unlink()
            except OSError as error:
                print(format_status("ERROR", ConsoleColor.RED, f"Failed to delete '{path}': {error}"))


def remove_readonly(path: Path) -> None:
    if path.exists():
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IWRITE)


def retry_after_remove_readonly(
    func: Callable[[str], object],
    path: str,
    _: tuple[type[BaseException], BaseException, object],
) -> None:
    remove_readonly(Path(path))
    func(path)


def sanitize_source_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_").lower()


if __name__ == "__main__":
    main()
