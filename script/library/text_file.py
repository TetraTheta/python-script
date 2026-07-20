import os
import subprocess
import sys
import traceback
from pathlib import Path
from types import TracebackType

UTF8_BOM = b"\xef\xbb\xbf"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"
TEXT_ENCODINGS = ("utf-8",)
TRACEBACK_ENV_VAR = "PYTHON_SCRIPT_TRACEBACK"
_ORIGINAL_EXCEPTHOOK = sys.excepthook
_TRACEBACK_ENABLED = False


def read_text(path: Path, encoding: str = "utf-8") -> str:
    try:
        data = path.read_bytes()
    except OSError as error:
        add_file_error_note(error, path, "read")
        raise

    try:
        return normalize_newlines(data.decode(encoding))
    except UnicodeDecodeError as error:
        add_file_error_note(error, path, "read", encoding=encoding, data=data)
        raise


def write_text(path: Path, data: str, encoding: str = "utf-8", line_ending: str | None = None) -> None:
    """Write text with Git attributes, unless `line_ending` is explicitly set."""
    newline = git_line_ending_or_default(path) if line_ending is None else line_ending
    normalized = normalize_newlines(data)
    try:
        path.write_text(normalized, encoding=encoding, newline=newline)
    except UnicodeEncodeError as error:
        add_file_error_note(error, path, "write", encoding=encoding, text=normalized)
        raise
    except OSError as error:
        add_file_error_note(error, path, "write", encoding=encoding)
        raise


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text_with_fallback(path: Path, fallback_encoding: str = "cp949") -> str:
    try:
        data = path.read_bytes()
    except OSError as error:
        add_file_error_note(error, path, "read")
        raise

    detected_encoding = detect_unicode_encoding(data)
    if detected_encoding is not None:
        try:
            return data.decode(detected_encoding)
        except UnicodeDecodeError as error:
            add_file_error_note(error, path, "read", encoding=detected_encoding, data=data)
            raise

    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    try:
        return data.decode(fallback_encoding)
    except UnicodeDecodeError as error:
        add_file_error_note(error, path, "read", encoding=fallback_encoding, data=data)
        raise


def is_traceback_enabled() -> bool:
    return _TRACEBACK_ENABLED



def set_traceback_enabled(enabled: bool) -> None:
    global _TRACEBACK_ENABLED
    _TRACEBACK_ENABLED = enabled



def add_file_error_note(
    error: BaseException,
    path: Path,
    operation: str,
    *,
    encoding: str | None = None,
    line: int | None = None,
    column: int | None = None,
    text: str | None = None,
    data: bytes | None = None,
) -> None:
    if line is None or column is None:
        derived_line, derived_column = _derive_line_and_column(error, text=text, data=data, encoding=encoding)
        if line is None:
            line = derived_line
        if column is None:
            column = derived_column

    note = f"FileError: operation={operation} path='{path}'"
    if line is not None:
        note += f" line={line}"
    if column is not None:
        note += f" column={column}"
    if encoding is not None:
        note += f" encoding={encoding}"

    notes = getattr(error, "__notes__", None)
    if isinstance(notes, list) and note in notes:
        return

    add_note = getattr(error, "add_note", None)
    if callable(add_note):
        add_note(note)



def _derive_line_and_column(
    error: BaseException,
    *,
    text: str | None = None,
    data: bytes | None = None,
    encoding: str | None = None,
) -> tuple[int | None, int | None]:
    line = getattr(error, "line", None)
    column = getattr(error, "column", None)
    if isinstance(line, int) and line > 0:
        return line, column if isinstance(column, int) and column > 0 else None

    if isinstance(error, UnicodeEncodeError) and text is not None:
        return _line_and_column_from_text_index(text, error.start)

    if isinstance(error, UnicodeDecodeError) and data is not None and encoding is not None:
        try:
            prefix = data[: error.start].decode(encoding)
        except UnicodeError:
            return None, None
        return _line_and_column_from_text_index(prefix, len(prefix))

    return None, None



def _line_and_column_from_text_index(text: str, index: int) -> tuple[int, int]:
    bounded = max(0, min(index, len(text)))
    line = text.count("\n", 0, bounded) + 1
    line_start = text.rfind("\n", 0, bounded) + 1
    column = bounded - line_start + 1
    return line, column



def format_exception_message(error: BaseException) -> str:
    message = str(error)
    notes = getattr(error, "__notes__", ())
    if notes:
        return f"{message} ({'; '.join(notes)})"
    return message



def print_exception(error: BaseException) -> None:
    if is_traceback_enabled():
        traceback.print_exception(error, file=sys.stderr)
        return
    print(f"{type(error).__name__}: {format_exception_message(error)}", file=sys.stderr)



def _parse_traceback_bool(value: str) -> bool:
    return value.strip().lower() not in {"", "0", "false", "no", "off"}



def _configure_traceback_mode(argv: list[str]) -> None:
    env_value = os.environ.get(TRACEBACK_ENV_VAR)
    if env_value is not None:
        set_traceback_enabled(_parse_traceback_bool(env_value))

    filtered_argv: list[str] = []
    for arg in argv:
        if arg == "--traceback":
            set_traceback_enabled(True)
            continue
        if arg == "--no-traceback":
            set_traceback_enabled(False)
            continue
        filtered_argv.append(arg)
    argv[:] = filtered_argv



def _exception_hook(exc_type: type[BaseException], error: BaseException, tb: TracebackType | None) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        _ORIGINAL_EXCEPTHOOK(exc_type, error, tb)
        return
    if is_traceback_enabled():
        traceback.print_exception(exc_type, error, tb, file=sys.stderr)
        return
    print(f"{exc_type.__name__}: {format_exception_message(error)}", file=sys.stderr)



_configure_traceback_mode(sys.argv)
sys.excepthook = _exception_hook



def git_line_ending_or_default(path: Path) -> str:
    """Return the Git-configured line ending for a file, or the host OS default."""
    resolved = path.resolve()
    repo = _find_git_root(resolved.parent)
    if repo is None:
        return _default_line_ending()

    try:
        attr = subprocess.run(
            ["git", "-C", str(repo), "check-attr", "eol", "--", str(resolved.relative_to(repo))],
            capture_output=True,
            check=False,
            encoding="utf-8",
        ).stdout.strip()
    except (OSError, ValueError):
        return _default_line_ending()
    if attr.endswith(": eol: crlf"):
        return "\r\n"
    if attr.endswith(": eol: lf"):
        return "\n"
    return _default_line_ending()


def _default_line_ending() -> str:
    if sys.platform == "win32":
        return "\r\n"
    if sys.platform == "darwin":
        return "\r"
    return "\n"


def _find_git_root(path: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
            encoding="utf-8",
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def detect_unicode_encoding(data: bytes) -> str | None:
    if data.startswith(UTF8_BOM):
        return "utf-8-sig"
    if data.startswith(UTF16_LE_BOM):
        return "utf-16"
    if data.startswith(UTF16_BE_BOM):
        return "utf-16"

    even_nulls = data[0::2].count(0)
    odd_nulls = data[1::2].count(0)
    if odd_nulls > even_nulls and odd_nulls > len(data) // 8:
        return "utf-16-le"
    if even_nulls > odd_nulls and even_nulls > len(data) // 8:
        return "utf-16-be"
    return None
