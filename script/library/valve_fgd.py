import re
from dataclasses import dataclass, field
from pathlib import Path

from library.text_file import read_text_with_fallback

INCLUDE_PATTERN = re.compile(r'^\s*@include\s+"([^"]+)"', re.IGNORECASE)
CLASS_PATTERN = re.compile(
    r"^\s*@(BaseClass|PointClass|SolidClass|NPCClass|FilterClass|KeyFrameClass|MoveClass|ExtendClass)\b"
    r"(?P<header>.*?)=\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
BASE_PATTERN = re.compile(r"\bbase\s*\((?P<bases>[^)]*)\)", re.IGNORECASE)
PROPERTY_PATTERN = re.compile(
    r"^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*:"
    r'\s*(?:"(?:\\.|[^"])*"|[^:]*)\s*:'
    r"\s*(?P<default>.*)$",
)
PROPERTY_NAME_PATTERN = re.compile(r"^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)")


class FgdParseError(ValueError):
    pass


@dataclass
class FgdClass:
    name: str
    bases: list[str] = field(default_factory=list)
    defaults: dict[str, str] = field(default_factory=dict)
    properties: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class FgdEntityDefinition:
    defaults: dict[str, str]
    properties: set[str]


class FgdParser:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.classes: dict[str, FgdClass] = {}
        self.loaded_files: set[Path] = set()

    def parse_definitions(self) -> dict[str, FgdEntityDefinition]:
        for path in self._load_order(self.root):
            self._parse_file(path)
        return {name.lower(): self._resolve_definition(name, set()) for name in self.classes}

    def _load_order(self, path: Path) -> list[Path]:
        resolved = path.resolve()
        if resolved in self.loaded_files:
            return []
        self.loaded_files.add(resolved)

        text = read_text_with_fallback(resolved)
        paths: list[Path] = []
        for line in text.splitlines():
            match = INCLUDE_PATTERN.match(line)
            if match is None:
                continue
            paths.extend(self._load_order(resolved.parent / match.group(1)))
        paths.append(resolved)
        return paths

    def _parse_file(self, path: Path) -> None:
        lines = read_text_with_fallback(path).splitlines()
        index = 0
        while index < len(lines):
            match = CLASS_PATTERN.match(lines[index])
            if match is None:
                index += 1
                continue

            name = match.group("name")
            bases = parse_base_names(match.group("header"))
            body, next_index = self._collect_fgd_body(lines, index + 1)
            properties, defaults = parse_fgd_properties(body)
            if match.group(1).lower() == "extendclass" and name in self.classes:
                self.classes[name].bases.extend(base for base in bases if base not in self.classes[name].bases)
                self.classes[name].defaults.update(defaults)
                self.classes[name].properties.update(properties)
            else:
                self.classes[name] = FgdClass(name=name, bases=bases, defaults=defaults, properties=properties)
            index = next_index

    def _collect_fgd_body(self, lines: list[str], start: int) -> tuple[list[str], int]:
        body: list[str] = []
        index = start
        while index < len(lines) and lines[index].strip() != "[":
            index += 1
        if index >= len(lines):
            return body, index

        depth = 0
        while index < len(lines):
            stripped = strip_line_comment(lines[index]).strip()
            if stripped == "[":
                depth += 1
                if depth > 1:
                    body.append(lines[index])
            elif stripped == "]":
                depth -= 1
                if depth == 0:
                    return body, index + 1
                body.append(lines[index])
            elif depth >= 1:
                body.append(lines[index])
            index += 1

        raise FgdParseError("FGD class block is missing a closing bracket")

    def _resolve_definition(self, name: str, resolving: set[str]) -> FgdEntityDefinition:
        class_info = self.classes.get(name)
        if class_info is None:
            class_info = self._find_class_case_insensitive(name)
        if class_info is None:
            return FgdEntityDefinition(defaults={}, properties=set())
        class_key = class_info.name
        if class_key in resolving:
            return FgdEntityDefinition(defaults={}, properties=set())

        resolving.add(class_key)
        defaults: dict[str, str] = {}
        properties: set[str] = set()
        for base in class_info.bases:
            base_definition = self._resolve_definition(base, resolving)
            defaults.update(base_definition.defaults)
            properties.update(base_definition.properties)
        defaults.update(class_info.defaults)
        properties.update(class_info.properties)
        resolving.remove(class_key)
        return FgdEntityDefinition(defaults=defaults, properties=properties)

    def _find_class_case_insensitive(self, name: str) -> FgdClass | None:
        name_lower = name.lower()
        for class_name, class_info in self.classes.items():
            if class_name.lower() == name_lower:
                return class_info
        return None


def parse_base_names(header: str) -> list[str]:
    bases: list[str] = []
    for match in BASE_PATTERN.finditer(header):
        for raw_base in match.group("bases").split(","):
            base = raw_base.strip()
            if base:
                bases.append(base)
    return bases


def parse_fgd_properties(lines: list[str]) -> tuple[set[str], dict[str, str]]:
    properties: set[str] = set()
    defaults: dict[str, str] = {}
    nested_depth = 0
    for line in lines:
        stripped = strip_line_comment(line).strip()
        if not stripped:
            continue
        if stripped == "[":
            nested_depth += 1
            continue
        if stripped == "]":
            nested_depth = max(0, nested_depth - 1)
            continue
        if nested_depth > 0 or stripped.lower().startswith(("input ", "output ")):
            continue

        property_name = PROPERTY_NAME_PATTERN.match(stripped)
        if property_name is not None:
            properties.add(property_name.group("key").lower())

        match = PROPERTY_PATTERN.match(stripped)
        if match is None:
            if stripped.endswith("["):
                nested_depth += 1
            continue
        default = normalize_fgd_default(match.group("default"))
        if default is None:
            if stripped.endswith("["):
                nested_depth += 1
            continue
        defaults[match.group("key").lower()] = default

        if stripped.endswith("["):
            nested_depth += 1

    return properties, defaults


def normalize_fgd_default(raw_default: str) -> str | None:
    default = raw_default.strip()
    if not default:
        return None
    if default.endswith("="):
        default = default[:-1].strip()
    parts = split_fgd_columns(default)
    if parts:
        default = parts[0].strip()
    if not default:
        return None
    if default.startswith('"'):
        return read_fgd_quoted(default)
    return default.split()[0]


def split_fgd_columns(value: str) -> list[str]:
    columns: list[str] = []
    current: list[str] = []
    quote_open = False
    index = 0
    while index < len(value):
        char = value[index]
        if char == '"' and (index == 0 or value[index - 1] != "\\"):
            quote_open = not quote_open
        if char == ":" and not quote_open:
            columns.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    columns.append("".join(current))
    return columns


def read_fgd_quoted(value: str) -> str:
    chars: list[str] = []
    index = 1
    while index < len(value):
        char = value[index]
        if char == '"' and value[index - 1] != "\\":
            return "".join(chars)
        if char == "\\" and index + 1 < len(value) and value[index + 1] == '"':
            chars.append('"')
            index += 2
            continue
        chars.append(char)
        index += 1
    return "".join(chars)


def strip_line_comment(line: str) -> str:
    quote_open = False
    index = 0
    while index < len(line):
        char = line[index]
        if char == '"' and (index == 0 or line[index - 1] != "\\"):
            quote_open = not quote_open
        if not quote_open and char == "/" and index + 1 < len(line) and line[index + 1] == "/":
            return line[:index]
        index += 1
    return line
