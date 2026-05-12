from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, TypedDict

CropPosition = Literal["bottom", "center", "full"]
GameName = Literal["none", "wuwa", "endfield"]
OperationName = Literal[
    "background",
    "center",
    "cutscene",
    "foreground0",
    "foreground1",
    "foreground2",
    "foreground3",
    "foreground4",
    "foreground5",
    "full",
]


class PresetConfig(TypedDict):
    crop_height: int
    crop_position: CropPosition
    blur: list[list[int]]


class GeneralConfig(TypedDict):
    folder_name: dict[OperationName, str]


class AppConfig(TypedDict):
    game: dict[Literal["wuwa", "endfield"], dict[OperationName, PresetConfig]]
    general: GeneralConfig


CONFIG: AppConfig = {
    "game": {
        "wuwa": {
            "background": {
                "crop_height": 360,
                "crop_position": "bottom",
                "blur": [[40, 1054, 330, 22], [1733, 1058, 140, 22]],
            },
            "center": {
                "crop_height": 200,
                "crop_position": "center",
                "blur": [],
            },
            "cutscene": {
                "crop_height": 810,
                "crop_position": "center",
                "blur": [[1781, 929, 110, 16]],
            },
            "foreground0": {
                "crop_height": 310,
                "crop_position": "bottom",
                "blur": [[1733, 1058, 140, 22]],
            },
            "foreground1": {
                "crop_height": 420,
                "crop_position": "bottom",
                "blur": [[1733, 1058, 140, 22]],
            },
            "foreground2": {
                "crop_height": 505,
                "crop_position": "bottom",
                "blur": [[1733, 1058, 140, 22]],
            },
            "foreground3": {
                "crop_height": 580,
                "crop_position": "bottom",
                "blur": [[1733, 1058, 140, 22]],
            },
            "foreground4": {
                "crop_height": 655,
                "crop_position": "bottom",
                "blur": [[1733, 1058, 140, 22]],
            },
            "foreground5": {
                "crop_height": 730,
                "crop_position": "bottom",
                "blur": [[1733, 1058, 140, 22]],
            },
            "full": {
                "crop_height": 0,
                "crop_position": "full",
                # "blur": [[40, 1054, 330, 22], [1733, 1058, 140, 22]],
                "blur": [[1733, 1058, 140, 22]],
            },
        },
        "endfield": {
            "background": {
                "crop_height": 360,
                "crop_position": "bottom",
                "blur": [[109, 1049, 134, 15]],
            },
            "center": {
                "crop_height": 200,
                "crop_position": "center",
                "blur": [],
            },
            "cutscene": {
                "crop_height": 810,
                "crop_position": "center",
                "blur": [[109, 1049, 134, 15]],
            },
            "foreground0": {
                "crop_height": 310,
                "crop_position": "bottom",
                "blur": [[109, 1049, 134, 15]],
            },
            "foreground1": {
                "crop_height": 420,
                "crop_position": "bottom",
                "blur": [[109, 1049, 134, 15]],
            },
            "foreground2": {
                "crop_height": 505,
                "crop_position": "bottom",
                "blur": [[109, 1049, 134, 15]],
            },
            "foreground3": {
                "crop_height": 580,
                "crop_position": "bottom",
                "blur": [[109, 1049, 134, 15]],
            },
            "foreground4": {
                "crop_height": 655,
                "crop_position": "bottom",
                "blur": [[109, 1049, 134, 15]],
            },
            "foreground5": {
                "crop_height": 730,
                "crop_position": "bottom",
                "blur": [[109, 1049, 134, 15]],
            },
            "full": {
                "crop_height": 0,
                "crop_position": "full",
                "blur": [[109, 1049, 134, 15]],
            },
        },
    },
    "general": {
        "folder_name": {
            "background": "CS-Background",
            "center": "CS-Center",
            "cutscene": "CS-Cutscene",
            "foreground0": "CS-Foreground-0",
            "foreground1": "CS-Foreground-1",
            "foreground2": "CS-Foreground-2",
            "foreground3": "CS-Foreground-3",
            "foreground4": "CS-Foreground-4",
            "foreground5": "CS-Foreground-5",
            "full": "CS-Full",
        }
    },
}

ALL_OPERATION: list[OperationName] = [
    "background",
    "center",
    "cutscene",
    "foreground0",
    "foreground1",
    "foreground2",
    "foreground3",
    "foreground4",
    "foreground5",
    "full",
]

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")


def has_images(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        for p in path.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                return True
    except PermissionError:
        return False
    return False


def ensure_temp_dir() -> Path:
    base = Path(tempfile.gettempdir()) / "convert-screenshot"
    base.mkdir(parents=True, exist_ok=True)
    return base


def write_job_json(job: JobPayload) -> Path:
    temp_dir = ensure_temp_dir()
    name = f"cs-{uuid.uuid4().hex}.json"
    path = temp_dir / name
    with path.open("w", encoding="utf-8") as file:
        json.dump(job, file, indent=2)
    return path


def spawn_gui(json_path: Path) -> None:
    gui_script = Path(__file__).with_name("convert_screenshot_gui.pyw")
    command = [sys.executable, str(gui_script), str(json_path)]
    if sys.platform == "win32":
        subprocess.Popen(command, creationflags=subprocess.DETACHED_PROCESS)
        return
    subprocess.Popen(command)


def create_directories(target: Path) -> None:
    for _, name in CONFIG["general"]["folder_name"].items():
        out = target / name
        out.mkdir(parents=True, exist_ok=True)


def parse_blur(value: str) -> list[int]:
    parts = value.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("blur must be in form of 'x,y,w,h'")
    try:
        return [int(part) for part in parts]
    except ValueError as error:
        raise argparse.ArgumentTypeError("blur values must be integers") from error


class ConvertScreenshotNamespace(argparse.Namespace):
    target: Path
    game: GameName
    operation: str
    blur: list[list[int]] | None
    crop_height: int | None
    crop_pos: CropPosition | None
    width_from: int | None
    width_to: int | None


class JobPayload(TypedDict):
    operation: str
    game: GameName
    blur: list[list[int]]
    crop_height: int
    crop_pos: CropPosition
    save_at_parent: bool
    target: str
    width_from: int
    width_to: int
    delete_job_file: bool


def get_operation_list(operation: str) -> Sequence[OperationName | str]:
    if operation == "all":
        return ALL_OPERATION.copy()
    return [operation]


def main() -> None:
    parser = argparse.ArgumentParser(prog="cs")
    parser.add_argument("target", nargs="?", default=".", help="Target directory (default: CWD)")
    parser.add_argument(
        "-g",
        "--game",
        default="none",
        choices=["none", "wuwa", "endfield"],
        help="Game preset",
    )
    parser.add_argument(
        "-o",
        "--operation",
        default="full",
        help="Operation or 'all' or 'create-directory'",
    )
    parser.add_argument(
        "--blur",
        action="append",
        type=parse_blur,
        help="Manual override: blur (x,y,w,h)",
    )
    parser.add_argument("--crop-height", type=int, help="Manual override: crop height")
    parser.add_argument(
        "--crop-pos",
        choices=["bottom", "center", "full"],
        help="Manual override: crop position",
    )
    parser.add_argument("--width-from", type=int, help="Manual override: source width")
    parser.add_argument("--width-to", type=int, help="Manual override target width")
    args = parser.parse_args(namespace=ConvertScreenshotNamespace())

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"Target does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    op = args.operation.lower()
    if op in ("create-directory", "cd"):
        create_directories(target)
        return

    if args.game == "none" and op not in ("full",):
        print("Game must be specified for this operation", file=sys.stderr)
        sys.exit(1)

    operation_list = get_operation_list(op)

    job_dirs: list[Path] = []
    if target.is_dir():
        if has_images(target):
            job_dirs.append(target)
        else:
            for p in target.iterdir():
                if p.is_dir() and has_images(p):
                    job_dirs.append(p)

    if not job_dirs:
        print("No directories with images found")
        return

    # process each directory
    for job_dir in job_dirs:
        for op_name in operation_list:
            if op_name not in ALL_OPERATION:
                print(f"Unknown operation: {op_name}", file=sys.stderr)
                continue

            preset: PresetConfig | None = None

            if args.game != "none":
                preset = CONFIG["game"].get(args.game, {}).get(op_name)

            job: JobPayload = {
                "operation": op_name,
                "game": args.game,
                "blur": preset.get("blur", [])[:] if preset else [],
                "crop_height": preset.get("crop_height", 0) if preset else 0,
                "crop_pos": preset.get("crop_position", "full") if preset else "full",
                "save_at_parent": False,
                "target": str(job_dir),
                "width_from": args.width_from if args.width_from is not None else 1920,
                "width_to": args.width_to if args.width_to is not None else 1280,
                "delete_job_file": True,
            }

            if args.blur:
                job["blur"] = args.blur
            if args.crop_height is not None:
                job["crop_height"] = args.crop_height
            if args.crop_pos is not None:
                job["crop_pos"] = args.crop_pos

            json_path = write_job_json(job)
            spawn_gui(json_path)


if __name__ == "__main__":
    main()
