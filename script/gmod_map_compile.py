#!/usr/bin/env python3
"""Compile Garry's Mod VMF maps with Source compile tools."""

import ctypes
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from time import perf_counter
from typing import Sequence

from library.console import ConsoleColor, format_status

GAME_DIR = r"E:/Program Files/Steam/steamapps/common/GarrysMod/garrysmod"
VBSP = r"E:/Program Files/Steam/steamapps/common/GarrysMod/bin/win64/vbspplusplus.exe"
VVIS = r"E:/Program Files/Steam/steamapps/common/GarrysMod/bin/win64/vvisplusplus.exe"
VRAD = r"E:/Program Files/Steam/steamapps/common/GarrysMod/bin/win64/vradplusplus.exe"


class GmodMapCompileArgs(Namespace):
    target: str | None


def parse_args() -> GmodMapCompileArgs:
    parser = ArgumentParser(description="Compile Garry's Mod VMF map source.")
    parser.add_argument("target", nargs="?")
    return parser.parse_args(namespace=GmodMapCompileArgs())


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


def main() -> None:
    args = parse_args()

    if not args.target:
        print(format_status("ERROR", ConsoleColor.RED, "No argument is provided"))
        sys.exit(1)

    source = Path(args.target).resolve()
    if source.suffix.lower() != ".vmf":
        print(format_status("ERROR", ConsoleColor.RED, "The file is not map source file (.vmf)"))
        sys.exit(1)

    enable_virtual_terminal()

    map_name = source.stem
    vmf = str(source.with_suffix(".vmf"))
    bsp = str(source.with_suffix(".bsp"))
    start = perf_counter()

    print(
        format_status("INFO", ConsoleColor.GREEN, f"Compiling {ConsoleColor.YELLOW}{map_name}{ConsoleColor.RESET}"),
        flush=True,
    )
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
    subprocess.run("pause", shell=True, check=False)


if __name__ == "__main__":
    main()
