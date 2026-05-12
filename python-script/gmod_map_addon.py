from __future__ import annotations

import os
import platform
import re
import stat
import sys
from fnmatch import fnmatch
from pathlib import Path
from shutil import move, rmtree
from typing import Callable


class Color:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"


def lowercase_names(directory: Path) -> None:
    items = sorted(directory.rglob("*"), key=lambda path: len(path.parts), reverse=True)

    for item in items:
        new_name = item.name.lower()
        if item.name != new_name:
            new_path = item.with_name(new_name)
            print(
                f"{Color.YELLOW}[RENAME ]{Color.RESET} "
                f"{item.parent}{os.sep}{{{Color.YELLOW}{item.name}{Color.RESET} → "
                f"{Color.YELLOW}{new_name}{Color.RESET}}}"
            )
            try:
                make_writable(item)
                item.rename(new_path)
            except OSError as error:
                print(f"{Color.RED}[ ERROR ]{Color.RESET} Failed to rename '{item}': {error}")


def make_writable(path: Path) -> None:
    if path.exists():
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IWRITE)


def remove_dirs(target: Path, names: list[str]) -> None:
    for name in names:
        path = target.joinpath(*Path(name).parts).resolve()
        if path.exists() and path.is_dir():
            print(f"{Color.YELLOW}[REMOVE ]{Color.RESET} {path}")
            rmtree(path, onerror=remove_readonly)


def remove_readonly(
    func: Callable[[str], object],
    path: str,
    excinfo: tuple[type[BaseException], BaseException, object],
) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_empty_directory(current: Path, root: Path) -> None:
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
                remove_empty_directory(child, root)

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


def remove_files_by_patterns(target: Path, patterns: list[str]) -> None:
    for pattern in patterns:
        for path in target.rglob(pattern):
            if path.is_file():
                print(f"{Color.YELLOW}[REMOVE ]{Color.RESET} {path}")
                try:
                    make_writable(path)
                    path.unlink()
                except OSError as error:
                    print(f"{Color.RED}[ ERROR ]{Color.RESET} Failed to delete '{path}': {error}")


def remove_files_by_exception(target: Path, exceptions: list[str]) -> None:
    for path in target.rglob("*"):
        if path.is_file():
            name = path.name.lower()
            keep = False
            for ex in exceptions:
                if fnmatch(name, ex):
                    keep = True
                    break
            if not keep:
                print(f"{Color.YELLOW}[REMOVE ]{Color.RESET} {path}")
                try:
                    make_writable(path)
                    path.unlink()
                except OSError as error:
                    print(f"{Color.RED}[ ERROR ]{Color.RESET} Failed to delete '{path}': {error}")


def replace_material_shader(materials_dir: Path) -> None:
    for vmt in materials_dir.rglob("*.vmt"):
        try:
            make_writable(vmt)
            content = vmt.read_text()
            content = content.replace('"SDK_LightmappedGeneric"', '"LightmappedGeneric"')
            content = content.replace('"SDK_Sprite"', '"Sprite"')
            content = content.replace('"SDK_VertexLitGeneric"', '"VertexLitGeneric"')
            vmt.write_text(content)
        except OSError as error:
            print(f"{Color.RED}[ ERROR ]{Color.RESET} Failed to process '{vmt}': {error}")


def sanitize_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_").lower()


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    # Check 'maps' dir or BSP file
    maps_dir = target / "maps"

    if not maps_dir.is_dir():
        bsp_files = list(target.glob("*.bsp"))
        if not bsp_files:
            print(f"{Color.RED}[ ERROR ]{Color.RESET} 'maps' directory not found. Aborting.")
            sys.exit(1)
        maps_dir.mkdir(exist_ok=True)
        for bsp in bsp_files:
            move(str(bsp), maps_dir / bsp.name)

    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Processing '{target.name}'")

    # Sanitize BSP/AIN file name
    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Sanitize BSP/AIN file name")
    for bsp_path in maps_dir.glob("*.bsp"):
        new_name = sanitize_name(bsp_path.stem) + bsp_path.suffix
        new_path = bsp_path.with_name(new_name)
        if new_path != bsp_path:
            print(f"{Color.YELLOW}[RENAME ]{Color.RESET} {bsp_path.name} → {new_name}")
            bsp_path.rename(new_path)

    graphs_dir = maps_dir / "graphs"
    if graphs_dir.is_dir():
        for ain_path in graphs_dir.glob("*.ain"):
            new_name = sanitize_name(ain_path.stem) + ain_path.suffix
            new_path = ain_path.with_name(new_name)
            if new_path != ain_path:
                print(f"{Color.YELLOW}[RENAME ]{Color.RESET} {ain_path.name} → {new_name}")
                ain_path.rename(new_path)

    # Lowercase file/dir names
    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Lowercase file/dir names")
    lowercase_names(target)

    # Create 'data_static' dir
    data_static = target / "data_static"
    data_static.mkdir(exist_ok=True)

    # Move every files under 'readme' and 'readmes' to 'data_static'
    readme = target / "readme"
    readmes = target / "readmes"
    for f in (readme, readmes):
        if f.is_dir():
            for file in f.iterdir():
                if file.is_file():
                    dest = data_static / file.name
                    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} {file} -> {dest}")
                    move(file, dest)

    # Remove directories
    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Remove directories")
    remove_dirs(
        target,
        [
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
        ],
    )

    # Remove files
    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Remove files")
    remove_files_by_patterns(
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

    # Remove files in 'materials' dir
    remove_files_by_exception(target / "materials", ["*.vmt", "*.vtf"])

    # Remove files in 'models' dir
    remove_files_by_patterns(target / "models", ["*.vtf", "*.vmt", "*.jpg", "*.png"])

    # Remove files in 'particles' dir
    remove_files_by_patterns(target / "particles", ["particles_manifest.txt"])

    # Remove files in 'resource' dir
    remove_files_by_exception(target / "resource", ["*.txt"])

    # Remove files in 'scripts' dir
    remove_files_by_patterns(target / "scripts", ["*manifest.txt", "chapterbackgrounds.txt"])

    # Replace MapBase shader
    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Modifying material files")
    replace_material_shader(target / "materials")

    # Move 'readme*' files to 'data_static'
    for file in target.glob("readme*"):
        if file.is_file():
            print(f"{Color.GREEN}[ MOVE  ]{Color.RESET} {file.name} to 'data_static'")
            move(str(file), data_static / file.name)

    # Create gamemode file
    gamemodes_dir = target / "gamemodes"
    gamemodes_dir.mkdir(exist_ok=True)

    dir_name = target.name
    safe_name = sanitize_name(dir_name)

    maps = sorted([p.stem for p in maps_dir.glob("*.bsp")])
    maps_str = "|".join(maps)

    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Creating Gamemode file ({safe_name}.txt)")

    gamemode_txt = gamemodes_dir / safe_name / f"{safe_name}.txt"
    gamemode_txt.parent.mkdir(parents=True, exist_ok=True)
    gamemode_txt_content = f""""{safe_name}"
{{
  "title" "{dir_name}"
  "maps" "{maps_str}"
  "menusystem" "0"
  "source" ""
}}
"""
    gamemode_txt.write_text(gamemode_txt_content)

    # Create 'addon.json' file
    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Creating 'addon.json' file")
    addon_json_content = f"""{{
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
"""
    (target / "addon.json").write_text(addon_json_content)

    # Remove empty directories
    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} Remove empty directories")
    remove_empty_directory(target, target)

    print(f"{Color.GREEN}[ INFO  ]{Color.RESET} DONE")


if __name__ == "__main__":
    main()
