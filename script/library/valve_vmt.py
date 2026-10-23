"""Parse and format Valve Material Type files."""

from __future__ import annotations

from dataclasses import dataclass


class VmtParseError(ValueError):
    """Raised when VMT text does not contain one shader block."""


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    line: int


@dataclass(frozen=True)
class _Entry:
    comments: tuple[str, ...]
    condition: str | None
    key: str
    trailing_comment: str | None
    value: str | _Block


@dataclass(frozen=True)
class _Block:
    entries: tuple[_Entry, ...]
    trailing_comments: tuple[str, ...]


@dataclass(frozen=True)
class _Document:
    block: _Block
    comments_before_brace: tuple[str, ...]
    leading_comments: tuple[str, ...]
    shader: str
    shader_comment: str | None
    trailing_comments: tuple[str, ...]


class _Parser:
    def __init__(self, text: str) -> None:
        self.tokens = _tokenize(text)
        self.index = 0

    def parse(self) -> _Document:
        leading_comments = self._read_comments()
        shader = self._expect("text")
        comments_before_brace = self._read_comments()
        shader_comment = None
        if comments_before_brace and comments_before_brace[0].line == shader.line:
            shader_comment = comments_before_brace.pop(0).text

        self._expect("{")
        block, _ = self._parse_block()
        trailing_comments = self._read_comments()
        if self.index != len(self.tokens):
            raise self._error("Unexpected content after shader block")

        return _Document(
            block=block,
            comments_before_brace=tuple(token.text for token in comments_before_brace),
            leading_comments=tuple(token.text for token in leading_comments),
            shader=shader.text,
            shader_comment=shader_comment,
            trailing_comments=tuple(token.text for token in trailing_comments),
        )

    def _parse_block(self) -> tuple[_Block, int]:
        entries: list[_Entry] = []

        while True:
            comments = self._read_comments()
            if self._peek_kind() == "}":
                closing_brace = self._expect("}")
                return (
                    _Block(
                        entries=tuple(entries),
                        trailing_comments=tuple(token.text for token in comments),
                    ),
                    closing_brace.line,
                )
            if self.index >= len(self.tokens):
                raise self._error("Missing closing brace")

            key = self._expect("text")
            comments.extend(self._read_comments())
            value_token = self._next()
            if value_token.kind == "text":
                value: str | _Block = value_token.text
                value_end_line = value_token.line
            elif value_token.kind == "{":
                value, value_end_line = self._parse_block()
            else:
                raise self._error(f"Expected value for key '{key.text}'", value_token)

            condition = None
            if self._peek_kind() == "text" and _is_condition(self.tokens[self.index].text):
                condition_token = self._next()
                condition = condition_token.text
                value_end_line = condition_token.line

            trailing_comment = None
            if self._peek_kind() == "comment" and self.tokens[self.index].line == value_end_line:
                trailing_comment = self._next().text

            entries.append(
                _Entry(
                    comments=tuple(token.text for token in comments),
                    condition=condition,
                    key=key.text,
                    trailing_comment=trailing_comment,
                    value=value,
                )
            )

    def _error(self, message: str, token: _Token | None = None) -> VmtParseError:
        current = token
        if current is None and self.index < len(self.tokens):
            current = self.tokens[self.index]
        if current is None:
            return VmtParseError(f"{message} at end of file")
        return VmtParseError(f"{message} at line {current.line}")

    def _expect(self, kind: str) -> _Token:
        token = self._next()
        if token.kind != kind:
            raise self._error(f"Expected '{kind}'", token)
        return token

    def _next(self) -> _Token:
        if self.index >= len(self.tokens):
            raise self._error("Unexpected end of file")
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _peek_kind(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index].kind

    def _read_comments(self) -> list[_Token]:
        comments: list[_Token] = []
        while self._peek_kind() == "comment":
            comments.append(self._next())
        return comments


def format_vmt(text: str) -> str:
    """Return canonical VMT text with recursively sorted keys and preserved comments."""
    document = _Parser(text).parse()
    lines = [*document.leading_comments]
    shader_line = _render_shader(document.shader)
    if document.shader_comment is not None:
        shader_line += f" {document.shader_comment}"
    lines.append(shader_line)
    lines.extend(document.comments_before_brace)
    lines.append("{")
    lines.extend(_render_block(document.block, 1))
    lines.append("}")
    lines.extend(document.trailing_comments)
    return "\n".join(lines) + "\n"


def _render_block(block: _Block, depth: int) -> list[str]:
    indent = "\t" * depth
    lines: list[str] = []
    for entry in sorted(block.entries, key=lambda item: item.key.casefold()):
        lines.extend(f"{indent}{comment}" for comment in entry.comments)
        if isinstance(entry.value, str):
            value = entry.value.replace("\\", "/")
            line = f"{indent}{_quote(entry.key)}\t\t{_quote(value)}"
            if entry.condition is not None:
                line += f" {entry.condition}"
            if entry.trailing_comment is not None:
                line += f" {entry.trailing_comment}"
            lines.append(line)
            continue

        lines.append(f"{indent}{_quote(entry.key)}")
        lines.append(f"{indent}{{")
        lines.extend(_render_block(entry.value, depth + 1))
        closing_line = f"{indent}}}"
        if entry.condition is not None:
            closing_line += f" {entry.condition}"
        if entry.trailing_comment is not None:
            closing_line += f" {entry.trailing_comment}"
        lines.append(closing_line)

    lines.extend(f"{indent}{comment}" for comment in block.trailing_comments)
    return lines


def _quote(value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _is_condition(value: str) -> bool:
    return value.startswith("[") and value.endswith("]")


def _render_shader(shader: str) -> str:
    if shader and not any(char.isspace() or char in '{}"' for char in shader) and "//" not in shader:
        return shader
    return _quote(shader)


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    line = 1

    while index < len(text):
        char = text[index]
        if char.isspace():
            if char == "\n":
                line += 1
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index)
            if end == -1:
                end = len(text)
            tokens.append(_Token("comment", text[index:end].rstrip(), line))
            index = end
            continue
        if char in "{}":
            tokens.append(_Token(char, char, line))
            index += 1
            continue
        if char in "\"'":
            value, index = _read_quoted(text, index, line)
            tokens.append(_Token("text", value, line))
            continue

        start = index
        while index < len(text):
            if text[index].isspace() or text[index] in "{}" or text.startswith("//", index):
                break
            index += 1
        tokens.append(_Token("text", text[start:index], line))

    return tokens


def _read_quoted(text: str, index: int, line: int) -> tuple[str, int]:
    quote = text[index]
    index += 1
    chars: list[str] = []
    while index < len(text):
        char = text[index]
        if char == quote:
            return "".join(chars), index + 1
        if char == "\\" and index + 1 < len(text) and text[index + 1] == quote:
            chars.append(quote)
            index += 2
            continue
        if char == "\n":
            raise VmtParseError(f"Unterminated quoted string at line {line}")
        chars.append(char)
        index += 1
    raise VmtParseError(f"Unterminated quoted string at line {line}")
