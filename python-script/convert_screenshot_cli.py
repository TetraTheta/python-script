import argparse
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import List, Literal, Optional

CONFIG = {
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
                "blur": [[40, 1054, 330, 22], [1733, 1058, 140, 22]],
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

ALL_OPERATION = [
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

################################################################################
# Helper
################################################################################


def has_images(path: Path) -> bool:
    # double check for directory
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


def write_job_json(job: dict) -> Path:
    temp_dir = ensure_temp_dir()
    name = f"cs-{uuid.uuid4().hex}.json"
    path = temp_dir / name
    with path.open("w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)
    return path


def spawn_gui(json_path: Path):
    gui_script = Path(__file__).with_name("convert_screenshot_gui.pyw")
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS
    subprocess.Popen([sys.executable, str(gui_script), str(json_path)], **kwargs)


def create_directories(target: Path):
    for _, name in CONFIG["general"]["folder_name"].items():
        out = target / name
        out.mkdir(parents=True, exist_ok=True)


def parse_blur(s: str):
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("blur must be in form of 'x,y,w,h'")
    return [int(p) for p in parts]


################################################################################
# Helper
################################################################################


class ConvertScreenshotNamespace(argparse.Namespace):
    target: Path
    game: Literal["none", "wuwa", "endfield"]
    operation: str
    blur: Optional[List[List[int]]]
    crop_height: Optional[int]
    crop_pos: Optional[Literal["bottom", "center", "full"]]
    width_from: Optional[int]
    width_to: Optional[int]


def main():
    parser = argparse.ArgumentParser(prog="cs")
    parser.add_argument("target", nargs="?", default=".", help="Target directory (default: CWD)")
    parser.add_argument("-g", "--game", default="none", choices=["none", "wuwa", "endfield"], help="Game preset")
    parser.add_argument("-o", "--operation", default="full", help="Operation or 'all' or 'create-directory'")
    parser.add_argument("--blur", action="append", type=parse_blur, help="Manual override: blur (x,y,w,h)")
    parser.add_argument("--crop-height", type=int, help="Manual override: crop height")
    parser.add_argument("--crop-pos", choices=["bottom", "center", "full"], help="Manual override: crop position")
    parser.add_argument("--width-from", type=int, help="Manual override: source width")
    parser.add_argument("--width-to", type=int, help="Manual override target width")
    args = parser.parse_args(namespace=ConvertScreenshotNamespace)

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

    # determine which operations to run
    if op == "all":
        operation_list = ALL_OPERATION.copy()
    else:
        operation_list = [op]

    # find directories to process
    job_dirs = []
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

            preset = None

            if args.game != "none":
                preset = CONFIG["game"].get(args.game, {}).get(op_name)

            # build job dict with safe fallbacks
            job = {
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

            # apply manual overrides
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
