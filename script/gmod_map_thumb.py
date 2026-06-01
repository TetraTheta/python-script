#!/usr/bin/env python3
"""맵 스크린샷에서 게리 모드 애드온의 맵 썸네일을 생성한다"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from subprocess import CalledProcessError, run

from library.console import ConsoleColor, format_status

EXTS = (".bmp", ".jpg", ".jpeg", ".png", ".webp")


class GmodMapThumbArgs(Namespace):
    target: Path | str


def parse_args() -> GmodMapThumbArgs:
    parser = ArgumentParser(description="Convert Source Engine screenshots to Garry's Mod map thumbnails.")
    parser.add_argument("target", nargs="?", default=str(Path.cwd()), help="Image file or directory")
    return parser.parse_args(namespace=GmodMapThumbArgs())


def convert_thumbnail(image_path: Path, output_dir: Path) -> None:
    print(format_status("INFO", ConsoleColor.GREEN, f"Converting '{image_path}'"))
    output_path = output_dir / f"{image_path.stem}.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(image_path),
                "-vf",
                "crop='if(gt(iw,ih),ih,iw):if(gt(iw,ih),ih,iw)',scale=512:512",
                "-y",
                str(output_path),
            ],
            check=True,
        )
    except (FileNotFoundError, CalledProcessError) as error:
        print(format_status("ERROR", ConsoleColor.RED, f"Failed to convert '{image_path}': {error}"), file=sys.stderr)


def is_supported_image(file: Path) -> bool:
    return file.is_file() and file.suffix.lower() in EXTS


def main() -> None:
    args = parse_args()
    target = Path(args.target)

    if target.is_dir():
        output_dir = target / "thumb"
        for file_path in target.iterdir():
            if is_supported_image(file_path):
                convert_thumbnail(file_path, output_dir)
    elif is_supported_image(target):
        convert_thumbnail(target, target.parent / "thumb")
    else:
        print(format_status("ERROR", ConsoleColor.RED, "No image file was found."), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
