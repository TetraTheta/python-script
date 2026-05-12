from __future__ import annotations

import base64
import platform
import shutil
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from subprocess import CalledProcessError, run


class Color:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"


class CustomFormatter(RawTextHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, width=max(80, shutil.get_terminal_size().columns - 2))


class Base64Namespace(Namespace):
    command: str
    input: str


def copy_to_clipboard(content: str) -> None:
    # tkinter is intentionally avoided because it cannot reliably set clipboard text.
    opsys = platform.system()
    command = {
        "Windows": ["clip"],
        "Linux": ["xclip", "-selection", "clipboard"],
        "Darwin": ["pbcopy"],
    }.get(opsys)

    if not command:
        print(f"{Color.RED}[ERROR]{Color.RESET} Unsupported OS: {opsys}", file=sys.stderr)
        return

    try:
        run(command, input=content.encode(), check=True)
        print(f"{Color.GREEN}[INFO ]{Color.RESET} Copied to clipboard using '{' '.join(command)}'", file=sys.stderr)
    except FileNotFoundError:
        print(f"{Color.RED}[ERROR]{Color.RESET} Clipboard utility not found: {command[0]}", file=sys.stderr)
    except CalledProcessError as error:
        print(f"{Color.RED}[ERROR]{Color.RESET} Clipboard command failed: {error}", file=sys.stderr)


def encode_input(input_value: str) -> None:
    input_path = Path(input_value)

    try:
        if input_path.is_file():
            content = input_path.read_bytes()
        else:
            content = input_value.encode()
        encoded = base64.b64encode(content).decode()
    except OSError as error:
        print(f"{Color.RED}[ERROR]{Color.RESET} Failed to encode: {error}", file=sys.stderr)
        sys.exit(1)

    print(encoded)
    copy_to_clipboard(encoded)


def decode_input(input_value: str) -> None:
    try:
        decoded = base64.b64decode(input_value, validate=True)
    except ValueError as error:
        print(f"{Color.RED}[ERROR]{Color.RESET} Could not decode: {error}", file=sys.stderr)
        sys.exit(1)

    try:
        text = decoded.decode()
        print(text)
        copy_to_clipboard(text)
    except UnicodeDecodeError:
        filename = "base64_decoded"
        try:
            Path(filename).write_bytes(decoded)
            print(f"{Color.GREEN}[INFO ]{Color.RESET} Binary file written to './{filename}'", file=sys.stderr)
            return
        except OSError:
            fallback_path = Path.home() / filename
            try:
                fallback_path.write_bytes(decoded)
                print(f"{Color.GREEN}[INFO ]{Color.RESET} Binary file written to '{fallback_path}'", file=sys.stderr)
            except OSError as error:
                print(f"{Color.RED}[ERROR]{Color.RESET} Failed to write decoded data: {error}", file=sys.stderr)
                sys.exit(1)


def main() -> None:
    cli = ArgumentParser(prog="base64", description="Encode or Decode BASE64 string", formatter_class=CustomFormatter)
    cli.add_argument("command", choices=["e", "encode", "d", "decode"], help="(E)ncode or (D)ecode")
    cli.add_argument("input", help="String or File path")

    args = cli.parse_args(namespace=Base64Namespace())

    if args.command in ("e", "encode"):
        encode_input(args.input)
    elif args.command in ("d", "decode"):
        decode_input(args.input)


if __name__ == "__main__":
    main()
