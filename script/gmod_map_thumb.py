#!/usr/bin/env python3
"""맵 스크린샷에서 게리 모드 애드온의 맵 썸네일을 생성한다"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Final

from library.console import ConsoleColor, format_status

EXTS = (".bmp", ".jpg", ".jpeg", ".png", ".webp")
FULL_TEXT_SIZE: Final[int] = 64
FULL_TEXT_PADDING: Final[int] = 16
WINDOWS_DRAW_FONT: Final[Path] = Path("C:/Windows/Fonts/Cascadia Mono-Regular.ttf")


class GmodMapThumbArgs(Namespace):
    target: Path | str


def parse_args() -> GmodMapThumbArgs:
    parser = ArgumentParser(description="Convert Source Engine screenshots to Garry's Mod map thumbnails.")
    parser.add_argument("target", nargs="?", default=str(Path.cwd()), help="Image file or directory")
    return parser.parse_args(namespace=GmodMapThumbArgs())


def escape_drawtext_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("'", r"\'").replace(":", r"\:").replace("%", r"\%").replace(",", r"\,")


def get_drawtext_font_filter() -> str:
    if sys.platform == "win32" and WINDOWS_DRAW_FONT.is_file():
        font_path = WINDOWS_DRAW_FONT.as_posix().replace(":", r"\:")
        return f"fontfile='{font_path}':"
    return ""


def run_ffmpeg(image_path: Path, output_path: Path, video_filter: str, *, codec_args: list[str] | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(image_path),
        "-vf",
        video_filter,
    ]
    if codec_args:
        command.extend(codec_args)
    command.extend(["-y", str(output_path)])
    run(command, check=True)


def convert_thumbnail(image_path: Path, output_dir: Path) -> None:
    output_path = output_dir / f"{image_path.stem}.png"
    run_ffmpeg(image_path, output_path, "crop='if(gt(iw,ih),ih,iw):if(gt(iw,ih),ih,iw)',scale=512:512")


def convert_full(image_path: Path, output_dir: Path) -> None:
    output_path = output_dir / f"{image_path.stem}.jpg"
    text = escape_drawtext_text(image_path.stem)
    video_filter = (
        "drawtext="
        f"{get_drawtext_font_filter()}"
        f"text='{text}':"
        f"fontsize={FULL_TEXT_SIZE}:"
        "fontcolor=white:"
        f"x={FULL_TEXT_PADDING}:"
        f"y={FULL_TEXT_PADDING}:"
        "box=1:"
        "boxcolor=black:"
        f"boxborderw={FULL_TEXT_PADDING}"
    )
    run_ffmpeg(image_path, output_path, video_filter, codec_args=["-q:v", "2"])


def convert_image(image_path: Path, thumb_dir: Path, full_dir: Path) -> None:
    print(format_status("INFO", ConsoleColor.GREEN, f"Converting '{image_path}'"))
    try:
        convert_thumbnail(image_path, thumb_dir)
        convert_full(image_path, full_dir)
    except (FileNotFoundError, CalledProcessError) as error:
        print(format_status("ERROR", ConsoleColor.RED, f"Failed to convert '{image_path}': {error}"), file=sys.stderr)


def is_supported_image(file: Path) -> bool:
    return file.is_file() and file.suffix.lower() in EXTS


def main() -> None:
    args = parse_args()
    target = Path(args.target)

    if target.is_dir():
        thumb_dir = target / "thumb"
        full_dir = target / "full"
        for file_path in target.iterdir():
            if is_supported_image(file_path):
                convert_image(file_path, thumb_dir, full_dir)
    elif is_supported_image(target):
        convert_image(target, target.parent / "thumb", target.parent / "full")
    else:
        print(format_status("ERROR", ConsoleColor.RED, "No image file was found."), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
