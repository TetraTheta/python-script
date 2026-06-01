import shutil
import sys
from argparse import RawTextHelpFormatter

from library.console import ConsoleColor, format_status


# 출력 너비를 터미널 너비로 확장
class TerminalHelpFormatter(RawTextHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, width=max(80, shutil.get_terminal_size().columns - 2))


def confirm_or_exit(message: str, cancel_message: str = "Operation canceled") -> None:
    result = input(message).strip().lower()
    if not result.startswith("y"):
        print(format_status("ERROR", ConsoleColor.RED, cancel_message))
        sys.exit(1)
