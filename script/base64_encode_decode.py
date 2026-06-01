#!/usr/bin/env python3
"""파일 혹은 문자열을 BASE64로 인코딩하거나, BASE64 문자열을 파일 혹은 문자열로 디코딩한다"""

import base64
import platform
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from subprocess import CalledProcessError, run

from library.cli import TerminalHelpFormatter
from library.console import ConsoleColor, format_status


class Base64Args(Namespace):
    command: str
    input: str


def parse_args() -> Base64Args:
    cli = ArgumentParser(
        prog="base64", description="Encode or Decode BASE64 string", formatter_class=TerminalHelpFormatter
    )
    cli.add_argument("command", choices=["e", "encode", "d", "decode"], help="(E)ncode or (D)ecode")
    cli.add_argument("input", help="String or File path")
    return cli.parse_args(namespace=Base64Args())


def copy_text_to_clipboard(content: str) -> None:
    # tkinter는 일부 환경에서 클립보드 반영이 늦거나 실패하므로 OS별 도구를 직접 호출
    opsys = platform.system()  # sys.platform, os.name과 다르게 런타임 시점에 판단함
    command = {
        "Windows": ["clip"],
        "Linux": ["xclip", "-selection", "clipboard"],
        "Darwin": ["pbcopy"],
    }.get(opsys)

    if not command:
        print(format_status("ERROR", ConsoleColor.RED, f"Unsupported OS: {opsys}"), file=sys.stderr)
        return

    try:
        run(command, input=content.encode(), check=True)
        print(
            format_status("INFO", ConsoleColor.GREEN, f"Copied to clipboard using '{' '.join(command)}'"),
            file=sys.stderr,
        )
    except FileNotFoundError:
        print(format_status("ERROR", ConsoleColor.RED, f"Clipboard utility not found: {command[0]}"), file=sys.stderr)
    except CalledProcessError as error:
        print(format_status("ERROR", ConsoleColor.RED, f"Clipboard command failed: {error}"), file=sys.stderr)


def main() -> None:
    args = parse_args()

    if args.command in ("e", "encode"):
        input_path = Path(args.input)

        try:
            # 파일 경로: 해당 파일 bytes를 인코딩 / 그 외: 입력 문자열 자체를 인코딩
            content = input_path.read_bytes() if input_path.is_file() else args.input.encode()
            encoded = base64.b64encode(content).decode()
        except OSError as error:
            print(format_status("ERROR", ConsoleColor.RED, f"Failed to encode: {error}"), file=sys.stderr)
            sys.exit(1)

        print(encoded)
        copy_text_to_clipboard(encoded)
        return

    # decode는 텍스트와 바이너리 결과를 모두 허용하므로 먼저 유효한 BASE64 문자열인지 확인
    try:
        decoded = base64.b64decode(args.input, validate=True)
    except ValueError as error:
        print(format_status("ERROR", ConsoleColor.RED, f"Could not decode: {error}"), file=sys.stderr)
        sys.exit(1)

    try:
        text = decoded.decode()
        print(text)
        copy_text_to_clipboard(text)
    except UnicodeDecodeError:
        filename = "base64_decoded"
        try:
            # 현재 폴더(cwd)에 파일 생성
            Path(filename).write_bytes(decoded)
            print(format_status("INFO", ConsoleColor.GREEN, f"Binary file written to './{filename}'"), file=sys.stderr)
            return
        except OSError:
            # 사용자 폴더에 파일 생성
            fallback_path = Path.home() / filename
            try:
                fallback_path.write_bytes(decoded)
                print(
                    format_status("INFO", ConsoleColor.GREEN, f"Binary file written to '{fallback_path}'"),
                    file=sys.stderr,
                )
            except OSError as error:
                print(
                    format_status("ERROR", ConsoleColor.RED, f"Failed to write decoded data: {error}"), file=sys.stderr
                )
                sys.exit(1)


if __name__ == "__main__":
    main()
