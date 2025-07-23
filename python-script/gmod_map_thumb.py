import sys
from pathlib import Path
from subprocess import run


class Color:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"


EXTS = (".bmp", ".jpg", ".jpeg", ".png", ".webp")


def convert(image_path: Path, output_dir: Path):
    print(f"{Color.GREEN}[INFO]{Color.RESET} Converting '{image_path}'")
    output_path = output_dir / f"{image_path.stem}.png"
    output_dir.mkdir(parents=True, exist_ok=True)
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
        ]
    )


def is_image(file: Path) -> bool:
    return file.is_file() and file.suffix.lower() in EXTS


##########
#  MAIN  #
##########
def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    if target.is_dir():
        output_dir = target / "thumb"
        for file_path in target.iterdir():
            if is_image(file_path):
                convert(file_path, output_dir)
    elif is_image(target):
        convert(target, target.parent / "thumb")


if __name__ == "__main__":
    main()
