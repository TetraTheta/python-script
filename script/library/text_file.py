from pathlib import Path

UTF8_BOM = b"\xef\xbb\xbf"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"
TEXT_ENCODINGS = ("utf-8",)


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
