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
