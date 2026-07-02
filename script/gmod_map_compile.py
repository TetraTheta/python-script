#!/usr/bin/env python3
"""Compile Garry's Mod VMF maps with Source compile tools."""

import ctypes
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from time import perf_counter
from typing import Sequence

from library.console import ConsoleColor, format_box, format_status

GAME_DIR = r"E:/Program Files/Steam/steamapps/common/GarrysMod/garrysmod"
VBSP = r"E:/Program Files/Steam/steamapps/common/GarrysMod/bin/win64/vbspplusplus.exe"
VVIS = r"E:/Program Files/Steam/steamapps/common/GarrysMod/bin/win64/vvisplusplus.exe"
VRAD = r"E:/Program Files/Steam/steamapps/common/GarrysMod/bin/win64/vradplusplus.exe"


class GmodMapCompileArgs(Namespace):
    targets: list[str]


def parse_args() -> GmodMapCompileArgs:
    parser = ArgumentParser(description="Compile Garry's Mod VMF map source.")
    parser.add_argument("targets", nargs="*", default=["."])
    return parser.parse_args(namespace=GmodMapCompileArgs())


def resolve_targets(args: GmodMapCompileArgs) -> list[Path]:
    targets = [Path(target).resolve() for target in args.targets]
    files = [target for target in targets if target.is_file()]
    directories = [target for target in targets if target.is_dir()]

    if len(files) + len(directories) != len(targets):
        missing = next(target for target in targets if not target.exists())
        raise ValueError(f"'{missing}' does not exist")

    if files and directories:
        raise ValueError("Files and directories cannot be mixed")

    if files:
        invalid = next((target for target in files if target.suffix.lower() != ".vmf"), None)
        if invalid:
            raise ValueError(f"'{invalid}' is not a VMF file")
        return files

    if len(directories) > 1:
        raise ValueError("Only one directory can be compiled at a time")

    sources = sorted(directories[0].glob("*.vmf"))
    if not sources:
        raise ValueError(f"No VMF files found in '{directories[0]}'")
    return sources


def enable_virtual_terminal() -> None:
    if sys.platform != "win32":
        return

    kernel32 = ctypes.windll.kernel32
    for stream in (-11, -12):
        handle = kernel32.GetStdHandle(stream)
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)


def format_duration(seconds: float) -> str:
    elapsed = int(seconds)
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def run_tool(command: Sequence[str]) -> None:
    print(f"{ConsoleColor.YELLOW}{subprocess.list2cmdline(command)}{ConsoleColor.RESET}", flush=True)
    try:
        subprocess.run(command, check=False)
    except FileNotFoundError as error:
        print(format_status("ERROR", ConsoleColor.RED, str(error)), file=sys.stderr)


def compile_map(source: Path) -> None:
    map_name = source.stem
    vmf = str(source.with_suffix(".vmf"))
    bsp = str(source.with_suffix(".bsp"))
    start = perf_counter()

    print(format_box(f"Compiling {ConsoleColor.YELLOW}{map_name}{ConsoleColor.RESET}", ConsoleColor.GREEN), flush=True)
    print(f"{ConsoleColor.BLUE}================ 01: VBSP ================{ConsoleColor.RESET}", flush=True)
    run_tool(
        [
            VBSP,
            "-threads",
            "12",
            "-leaktest",
            "-allowdynamicpropsasstatic",
            "-showineligiblevertexlitprops",
            "-blocksize",
            "2048",
            "-game",
            GAME_DIR,
            vmf,
        ]
    )

    print(f"{ConsoleColor.BLUE}================ 02: VVIS ================{ConsoleColor.RESET}", flush=True)
    run_tool([VVIS, "-threads", "12", "-game", GAME_DIR, bsp])

    print(f"{ConsoleColor.BLUE}================ 03: VRAD ================{ConsoleColor.RESET}", flush=True)
    run_tool(
        [
            VRAD,
            "-threads",
            "12",
            "-hdr",
            "-final",
            "-StaticPropLighting",
            "-staticproppolys",
            "-textureshadows",
            "-worldtextureshadows",
            "-translucentshadows",
            "-supportslightprojected",
            "-supportslightdirectional",
            "-ao",
            "-forcetextureshadows",
            "-game",
            GAME_DIR,
            bsp,
        ]
    )

    print(f"{ConsoleColor.BLUE}================ DONE ================{ConsoleColor.RESET}", flush=True)
    subprocess.run("nircmd stdbeep", shell=True, check=False)
    print(
        format_status(
            "INFO",
            ConsoleColor.GREEN,
            f"Compile finished in {ConsoleColor.YELLOW}{format_duration(perf_counter() - start)}{ConsoleColor.RESET}",
        )
    )


def main() -> None:
    args = parse_args()
    enable_virtual_terminal()

    try:
        sources = resolve_targets(args)
    except ValueError as error:
        print(format_status("ERROR", ConsoleColor.RED, str(error)), file=sys.stderr)
        sys.exit(1)

    for source in sources:
        compile_map(source)

    subprocess.run("pause", shell=True, check=False)


if __name__ == "__main__":
    main()
