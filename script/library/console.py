import re

ANSI_ESCAPE_PATTERN = re.compile(r"\033\[[0-9;]*m")


class ConsoleColor:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"


def format_status(label: str, color: str, message: str = "") -> str:
    status = f"{color}[{label:<6}]{ConsoleColor.RESET}"
    if not message:
        return status
    return f"{status} {message}"


def format_box(text: str, border_color: str = "", horizontal_padding: int = 2) -> str:
    if horizontal_padding < 0:
        raise ValueError("horizontal_padding must be greater than or equal to 0")

    reset = ConsoleColor.RESET if border_color else ""
    padding = " " * horizontal_padding
    visible_width = len(ANSI_ESCAPE_PATTERN.sub("", text))
    line_width = visible_width + horizontal_padding * 2

    return "\n".join(
        [
            f"{border_color}┌{'─' * line_width}┐{reset}",
            f"{border_color}│{reset}{padding}{text}{padding}{border_color}│{reset}",
            f"{border_color}└{'─' * line_width}┘{reset}",
        ]
    )
