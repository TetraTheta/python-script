from dataclasses import dataclass
from pathlib import Path

from library.text_file import add_file_error_note, read_text_with_fallback


@dataclass(frozen=True)
class KeyValueItem:
    key: str
    value: str | list["KeyValueItem"]


class KeyValueParseError(ValueError):
    def __init__(self, message: str, line: int | None = None, column: int | None = None) -> None:
        super().__init__(message)
        self.line = line
        self.column = column


class KeyValueParser:
    def __init__(self, text: str, allow_unclosed_blocks: bool = True) -> None:
        self.text = text
        self.length = len(text)
        self.index = 0
        self.allow_unclosed_blocks = allow_unclosed_blocks

    def parse(self) -> list[KeyValueItem]:
        items = self._parse_block(stop_at_closing_brace=False)
        self._skip_ignored()
        if self.index < self.length:
            raise self._error("Unexpected trailing content")
        return items

    def _error(self, message: str) -> KeyValueParseError:
        line = self.text.count("\n", 0, self.index) + 1
        line_start = self.text.rfind("\n", 0, self.index) + 1
        column = self.index - line_start + 1
        return KeyValueParseError(f"{message} at line {line}, column {column}", line=line, column=column)

    def _parse_block(self, stop_at_closing_brace: bool) -> list[KeyValueItem]:
        items: list[KeyValueItem] = []

        while True:
            self._skip_ignored()

            if self.index >= self.length:
                if stop_at_closing_brace:
                    if self.allow_unclosed_blocks:
                        return items
                    raise self._error("Missing closing brace")
                return items

            if self.text[self.index] == "}":
                if not stop_at_closing_brace:
                    raise self._error("Unexpected closing brace")
                self.index += 1
                return items

            key = self._read_token()
            self._skip_ignored()

            if self.index >= self.length:
                raise self._error(f"Missing value for key '{key}'")

            if self.text[self.index] == "{":
                self.index += 1
                value: str | list[KeyValueItem] = self._parse_block(stop_at_closing_brace=True)
            else:
                value = self._read_token()

            items.append(KeyValueItem(key=key, value=value))

    def _peek(self, offset: int) -> str:
        peek_index = self.index + offset
        if peek_index >= self.length:
            return ""
        return self.text[peek_index]

    def _read_quoted_token(self) -> str:
        quote = self.text[self.index]
        self.index += 1
        chars: list[str] = []

        while self.index < self.length:
            char = self.text[self.index]

            if char == quote:
                self.index += 1
                return "".join(chars)

            if char == "\\" and self._peek(1) == quote:
                chars.append(quote)
                self.index += 2
                continue

            chars.append(char)
            self.index += 1

        raise self._error("Unterminated quoted string")

    def _read_token(self) -> str:
        self._skip_ignored()

        if self.index >= self.length:
            raise self._error("Unexpected end of file")

        if self.text[self.index] in ('"', "'"):
            return self._read_quoted_token()

        start = self.index
        while self.index < self.length:
            char = self.text[self.index]
            if char.isspace() or char in "{}":
                break
            if char == "/" and self._peek(1) == "/":
                break
            self.index += 1

        if start == self.index:
            raise self._error(f"Unexpected character '{self.text[self.index]}'")

        return self.text[start : self.index]

    def _skip_ignored(self) -> None:
        while self.index < self.length:
            char = self.text[self.index]

            if char.isspace():
                self.index += 1
                continue

            if char == "/" and self._peek(1) == "/":
                self.index += 2
                while self.index < self.length and self.text[self.index] not in "\r\n":
                    self.index += 1
                continue

            break


class ValveKeyValue:
    def __init__(self, items: list[KeyValueItem]) -> None:
        self.items = items

    @classmethod
    def from_file(cls, path: Path) -> "ValveKeyValue":
        try:
            return cls.from_text(read_text_with_fallback(path))
        except KeyValueParseError as error:
            add_file_error_note(error, path, "parse")
            raise

    @classmethod
    def from_text(cls, text: str) -> "ValveKeyValue":
        return cls(KeyValueParser(text).parse())

    def block(self, key: str) -> "ValveKeyValue | None":
        item = self.find(key)
        if item is None or isinstance(item.value, str):
            return None
        return ValveKeyValue(item.value)

    def find(self, key: str) -> KeyValueItem | None:
        key_lower = key.lower()
        for item in self.items:
            if item.key.lower() == key_lower:
                return item
        return None

    def value(self, key: str) -> str | None:
        item = self.find(key)
        if item is None or not isinstance(item.value, str):
            return None
        return item.value

    def values(self, key: str) -> list[str]:
        key_lower = key.lower()
        values: list[str] = []
        for item in self.items:
            if item.key.lower() == key_lower and isinstance(item.value, str):
                values.append(item.value)
        return values


def parse_keyvalues(text: str) -> list[KeyValueItem]:
    return ValveKeyValue.from_text(text).items
