from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias, override

from .text_file import read_text_with_fallback

VmfNode: TypeAlias = "VmfBlock | VmfKeyValue"


class VmfParseError(ValueError):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"{message} at line {line}, column {column}")
        self.line: int = line
        self.column: int = column


@dataclass
class VmfKeyValue:
    key: str
    value: str
    parent: "VmfBlock | None" = field(default=None, repr=False)

    @property
    def line_count(self) -> int:
        return 1

    @property
    def path(self) -> str:
        if self.parent is None or self.parent.name is None:
            return self.key
        return f"{self.parent.path}.{self.key}"

    def remove(self) -> None:
        if self.parent is not None:
            self.parent.children.remove(self)

    def set(self, value: str) -> None:
        self.value = value


@dataclass
class VmfBlock:
    name: str | None = None
    parent: "VmfBlock | None" = field(default=None, repr=False)
    children: list[VmfNode] = field(default_factory=list)

    @property
    def line_count(self) -> int:
        return 2 + sum(child.line_count for child in self.children)

    @property
    def path(self) -> str:
        if self.parent is None or self.parent.name is None:
            return self.name or ""
        return f"{self.parent.path}.{self.name}"

    def blocks(self, name: str | None = None) -> list["VmfBlock"]:
        name_lower = name.lower() if name is not None else None
        return [
            child
            for child in self.children
            if isinstance(child, VmfBlock) and block_name_matches(child, name_lower)
        ]

    def each_keyvalue(self) -> list[VmfKeyValue]:
        values: list[VmfKeyValue] = []
        for child in self.children:
            if isinstance(child, VmfKeyValue):
                values.append(child)
            else:
                values.extend(child.each_keyvalue())
        return values

    def find(self, name: str) -> VmfNode | None:
        name_lower = name.lower()
        for child in self.children:
            if isinstance(child, VmfBlock) and block_name_matches(child, name_lower):
                return child
            if isinstance(child, VmfKeyValue) and child.key.lower() == name_lower:
                return child
        return None

    def key(self, name: str) -> VmfKeyValue | None:
        node = self.find(name)
        if isinstance(node, VmfKeyValue):
            return node
        return None

    def keys(self, name: str | None = None) -> list[VmfKeyValue]:
        name_lower = name.lower() if name is not None else None
        return [
            child
            for child in self.children
            if isinstance(child, VmfKeyValue) and (name_lower is None or child.key.lower() == name_lower)
        ]

    def remove(self) -> None:
        if self.parent is not None:
            self.parent.children.remove(self)


class ValveVmf(VmfBlock):
    def __init__(self, tags: set[str], tag_order: tuple[str, ...]) -> None:
        super().__init__()
        self.tags: set[str] = tags
        self.tag_order: tuple[str, ...] = tag_order

    @classmethod
    def from_file(cls, path: Path, tag_order: tuple[str, ...] = ()) -> "ValveVmf":
        return cls.from_text(read_text_with_fallback(path), tag_order)

    @classmethod
    def from_text(cls, text: str, tag_order: tuple[str, ...] = ()) -> "ValveVmf":
        tags, body = split_header(text, tag_order)
        vmf = cls(tags, tag_order)
        parser = VmfParser(body)
        vmf.children = parser.parse(vmf)
        return vmf

    @property
    @override
    def line_count(self) -> int:
        return sum(child.line_count for child in self.children)

    def render_text(self, compact: bool = False) -> str:
        header = "".join(tag for tag in self.tag_order if tag in self.tags)
        body = "".join(render_compact(child) for child in self.children) if compact else render_pretty(self.children)
        if not header:
            return body
        return f"{header}\n{body}"


class VmfParser:
    def __init__(self, text: str) -> None:
        self.text: str = text
        self.index: int = 0
        self.length: int = len(text)

    def parse(self, parent: VmfBlock) -> list[VmfNode]:
        children = self.parse_block(parent, stop_at_closing_brace=False)
        self.skip_ignored()
        if self.index < self.length:
            raise self.error("Unexpected trailing content")
        return children

    def parse_block(
        self,
        parent: VmfBlock,
        stop_at_closing_brace: bool,
    ) -> list[VmfNode]:
        children: list[VmfNode] = []
        while True:
            self.skip_ignored()
            if self.index >= self.length:
                if stop_at_closing_brace:
                    raise self.error("Missing closing brace")
                return children
            if self.text[self.index] == "}":
                if not stop_at_closing_brace:
                    raise self.error("Unexpected closing brace")
                self.index += 1
                return children

            key = self.read_token()
            self.skip_ignored()
            if self.index < self.length and self.text[self.index] == "{":
                self.index += 1
                block = VmfBlock(name=key, parent=parent)
                block.children = self.parse_block(block, stop_at_closing_brace=True)
                children.append(block)
                continue

            value = self.read_token()
            children.append(VmfKeyValue(key=key, value=value, parent=parent))

    def error(self, message: str) -> VmfParseError:
        line = self.text.count("\n", 0, self.index) + 1
        line_start = self.text.rfind("\n", 0, self.index) + 1
        return VmfParseError(message, line, self.index - line_start + 1)

    def peek(self, offset: int) -> str:
        index = self.index + offset
        if index >= self.length:
            return ""
        return self.text[index]

    def read_token(self) -> str:
        self.skip_ignored()
        if self.index >= self.length:
            raise self.error("Unexpected end of file")
        if self.text[self.index] == '"':
            return self.read_quoted_token()

        start = self.index
        while self.index < self.length:
            char = self.text[self.index]
            if char.isspace() or char in "{}":
                break
            if char == "/" and self.peek(1) == "/":
                break
            self.index += 1
        if start == self.index:
            raise self.error(f"Unexpected character '{self.text[self.index]}'")
        return self.text[start : self.index]

    def read_quoted_token(self) -> str:
        self.index += 1
        chars: list[str] = []
        while self.index < self.length:
            char = self.text[self.index]
            if char == '"':
                self.index += 1
                return "".join(chars)
            if char == "\\" and self.peek(1) == '"':
                chars.append('"')
                self.index += 2
                continue
            chars.append(char)
            self.index += 1
        raise self.error("Unterminated quoted string")

    def skip_ignored(self) -> None:
        while self.index < self.length:
            char = self.text[self.index]
            if char.isspace():
                self.index += 1
                continue
            if char == "/" and self.peek(1) == "/":
                self.index += 2
                while self.index < self.length and self.text[self.index] not in "\r\n":
                    self.index += 1
                continue
            break


def block_name_matches(block: VmfBlock, name_lower: str | None) -> bool:
    block_name = block.name
    if block_name is None:
        return False
    return name_lower is None or block_name.lower() == name_lower


def render_pretty(nodes: list[VmfNode], depth: int = 0) -> str:
    lines: list[str] = []
    indent = "\t" * depth
    for node in nodes:
        if isinstance(node, VmfKeyValue):
            lines.append(f'{indent}"{escape_token(node.key)}" "{escape_token(node.value)}"')
            continue
        lines.append(f"{indent}{node.name}")
        lines.append(f"{indent}{{")
        lines.append(render_pretty(node.children, depth + 1).removesuffix("\n"))
        lines.append(f"{indent}}}")
    return "\n".join(line for line in lines if line != "") + "\n"


def render_compact(node: VmfNode) -> str:
    if isinstance(node, VmfKeyValue):
        return f'"{escape_token(node.key)}""{escape_token(node.value)}"'
    return f"{node.name}{{{''.join(render_compact(child) for child in node.children)}}}"


def split_header(text: str, tag_order: tuple[str, ...]) -> tuple[set[str], str]:
    tags: set[str] = set()
    index = 0

    while True:
        while index < len(text) and text[index] in "\ufeff\r\n\t ":
            index += 1

        for tag in tag_order:
            if text.startswith(tag, index):
                tags.add(tag)
                index += len(tag)
                break
        else:
            return tags, text[index:]


def escape_token(value: str) -> str:
    return value.replace('"', '\\"')
