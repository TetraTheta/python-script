from __future__ import annotations

import argparse
import sys
from pathlib import Path

from valve_keyvalue import KeyValueItem, ValveKeyValue


class Color:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"


class GmodMapScriptsNamespace(argparse.Namespace):
    command: str
    input_path: Path | None
    output_path: Path | None


CLOSEDCAPTION_ALIASES = {
    "cc",
    "caption",
    "captions",
    "closedcaption",
    "closedcaptions",
    "subtitle",
    "subtitles",
}
SOUND_ALIASES = {"snd", "sound"}
PITCH_VALUES = {
    "PITCH_LOW": "95",
    "PITCH_NORM": "100",
    "PITCH_HIGH": "120",
}


def lua_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace('"', '\\"')
    )
    return f'"{escaped}"'


def normalize_lua_constant(value: str) -> str:
    normalized = value.strip()
    if normalized.upper().startswith("SNDLVL_") and normalized.upper().endswith("DB"):
        return f"{normalized[:-2]}dB"
    return normalized


def format_lua_number(value: str, default: str) -> str:
    normalized = value.strip()
    if not normalized:
        return default

    try:
        number = float(normalized)
    except ValueError:
        if normalized.upper() == "VOL_NORM":
            return "1"
        return normalized

    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def format_pitch(value: str | None) -> str:
    if value is None:
        return "100"

    normalized = value.strip()
    mapped = PITCH_VALUES.get(normalized.upper())
    if mapped is not None:
        return mapped

    parts = [part.strip() for part in normalized.split(",")]
    if len(parts) == 2 and all(parts):
        return f"{{ {format_lua_number(parts[0], '100')}, {format_lua_number(parts[1], '100')} }}"

    return format_lua_number(normalized, "100")


def write_lua(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\r\n")


def get_closedcaption_tokens(keyvalues: ValveKeyValue) -> list[KeyValueItem]:
    lang_block = keyvalues.block("lang")
    search_keyvalues = lang_block if lang_block is not None else keyvalues
    tokens = search_keyvalues.block("Tokens")
    if tokens is None:
        raise ValueError("Tokens block was not found.")
    return tokens.items


def build_closedcaption_lua(keyvalues: ValveKeyValue, addon_name: str) -> str:
    lines = [
        f'print("[{addon_name}] Registering subtitles...")',
        "local subtable = {",
    ]

    for item in get_closedcaption_tokens(keyvalues):
        if not isinstance(item.value, str):
            continue
        lines.append(
            f"  {{ snd = {lua_string(item.key)}, text = {lua_string(item.value)}, "
            "range = 9999, duration = 5, closedcaption = true },"
        )

    lines.extend(
        [
            "}",
            "table.insert(Subtitles_Table, subtable)",
            f'print("[{addon_name}] Registering subtitles... DONE")',
            "",
        ]
    )
    return "\n".join(lines)


def build_sound_field_lines(
    keyvalues: ValveKeyValue, sound_name: str
) -> list[str] | None:
    rndwave = keyvalues.block("rndwave")
    waves = rndwave.values("wave") if rndwave is not None else keyvalues.values("wave")

    if not waves:
        print(
            f"{Color.YELLOW}[WARN ]{Color.RESET} Skipping '{sound_name}' because it has no wave.",
            file=sys.stderr,
        )
        return None

    channel = normalize_lua_constant(keyvalues.value("channel") or "CHAN_AUTO")
    level = normalize_lua_constant(keyvalues.value("soundlevel") or "SNDLVL_NORM")
    volume = format_lua_number(keyvalues.value("volume") or "1", "1")
    pitch = format_pitch(keyvalues.value("pitch"))

    lines = [f"  name = {lua_string(sound_name)},"]

    if len(waves) == 1:
        lines.append(f"  sound = {lua_string(waves[0])},")
    else:
        lines.append("  sound = {")
        for wave in waves:
            lines.append(f"    {lua_string(wave)},")
        lines.append("  },")

    lines.extend(
        [
            f"  channel = {channel},",
            f"  level = {level},",
            f"  volume = {volume},",
            f"  pitch = {pitch},",
        ]
    )
    return lines


def build_sound_lua(keyvalues: ValveKeyValue, addon_name: str, source_name: str) -> str:
    lines = [f'print("[{addon_name}] Registering sounds ({source_name})...")']

    for item in keyvalues.items:
        if isinstance(item.value, str):
            continue

        field_lines = build_sound_field_lines(ValveKeyValue(item.value), item.key)
        if field_lines is None:
            continue

        lines.append("sound.Add({")
        lines.extend(field_lines)
        lines.append("})")

    lines.extend(
        [f'print("[{addon_name}] Registering sounds ({source_name})... DONE")', ""]
    )
    return "\n".join(lines)


def run_closedcaption(input_path: Path | None, output_path: Path | None) -> None:
    cwd = Path.cwd()
    source = input_path or cwd / "resource" / "closecaption_english.txt"
    output = output_path or cwd / "lua" / "subtitles" / f"{cwd.name}_subtitle.lua"
    content = build_closedcaption_lua(ValveKeyValue.from_file(source), cwd.name)
    write_lua(output, content)
    print(f"{Color.GREEN}[INFO ]{Color.RESET} Wrote '{output}'")


def run_sound(input_path: Path | None, output_path: Path | None) -> None:
    if input_path is None:
        raise ValueError(
            "The sound command requires an input file. Use '-i file_path'."
        )

    cwd = Path.cwd()
    source = input_path
    output = (
        output_path or cwd / "lua" / "autorun" / f"sound_{cwd.name}_{source.stem}.lua"
    )
    content = build_sound_lua(ValveKeyValue.from_file(source), cwd.name, source.stem)
    write_lua(output, content)
    print(f"{Color.GREEN}[INFO ]{Color.RESET} Wrote '{output}'")


def add_output_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        type=Path,
        help="Output Lua file path.",
    )


def parse_args() -> GmodMapScriptsNamespace:
    parser = argparse.ArgumentParser(
        description="Generate Garry's Mod Lua files from Source engine script files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    closedcaption_parser = subparsers.add_parser(
        "closedcaption",
        aliases=sorted(CLOSEDCAPTION_ALIASES - {"closedcaption"}),
        help="Generate a subtitle Lua file from closecaption_english.txt.",
        description="Generate a subtitle Lua file from a Source engine closed caption file.",
    )
    closedcaption_parser.add_argument(
        "-i",
        "--input",
        dest="input_path",
        type=Path,
        help="Input closed caption text file path.",
    )
    add_output_argument(closedcaption_parser)
    closedcaption_parser.set_defaults(command="closedcaption")

    sound_parser = subparsers.add_parser(
        "sound",
        aliases=sorted(SOUND_ALIASES - {"sound"}),
        help="Generate a sound.Add Lua file from a soundscript text file.",
        description="Generate a Garry's Mod sound.Add Lua file from a Source engine soundscript.",
    )
    sound_parser.add_argument(
        "-i",
        "--input",
        dest="input_path",
        type=Path,
        required=True,
        help="Input soundscript text file path.",
    )
    add_output_argument(sound_parser)
    sound_parser.set_defaults(command="sound")

    return parser.parse_args(namespace=GmodMapScriptsNamespace())


def main() -> None:
    args = parse_args()

    try:
        if args.command == "closedcaption":
            run_closedcaption(args.input_path, args.output_path)
        else:
            run_sound(args.input_path, args.output_path)
    except Exception as error:
        print(f"{Color.RED}[ERROR]{Color.RESET} {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
