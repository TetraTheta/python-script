import subprocess
import sys
from pathlib import Path

UTF8_BOM = b"\xef\xbb\xbf"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"
TEXT_ENCODINGS = ("utf-8",)


def write_text(path: Path, data: str, encoding: str = "utf-8", line_ending: str | None = None) -> None:
    """Write text with Git attributes, unless `line_ending` is explicitly set."""
    newline = git_line_ending_or_default(path) if line_ending is None else line_ending
    path.write_text(normalize_newlines(data), encoding=encoding, newline=newline)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text_with_fallback(path: Path, fallback_encoding: str = "cp949") -> str:
    data = path.read_bytes()
    detected_encoding = detect_unicode_encoding(data)
    if detected_encoding is not None:
        return data.decode(detected_encoding)

    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode(fallback_encoding)


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
