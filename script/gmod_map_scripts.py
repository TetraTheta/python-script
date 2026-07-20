#!/usr/bin/env python3
"""소스 엔진 게임/모드의 Closed Caption, 사운드 정의 파일을 Lua 파일로 변환한다"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from library.console import ConsoleColor, format_status
from library.text_file import write_text
from library.valve_keyvalue import ValveKeyValue

CLOSEDCAPTION_ALIASES = {"cc", "caption", "captions", "closedcaption", "closedcaptions", "subtitle", "subtitles"}
SOUND_ALIASES = {"snd", "sound"}
PITCH_VALUES = {"PITCH_LOW": "95", "PITCH_NORM": "100", "PITCH_HIGH": "120"}


class GmodMapScriptsArgs(Namespace):
    command: str
    input_path: Path | None
    output_path: Path | None


def parse_args() -> GmodMapScriptsArgs:
    parser = ArgumentParser(description="Generate Garry's Mod Lua files from Source engine script files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    closedcaption_parser = subparsers.add_parser(
        "closedcaption",
        aliases=sorted(CLOSEDCAPTION_ALIASES - {"closedcaption"}),
        help="Generate a subtitle Lua file from closecaption_english.txt.",
        description="Generate a subtitle Lua file from a Source engine closed caption file.",
    )
    closedcaption_parser.add_argument(
        "-i", "--input", dest="input_path", type=Path, help="Input closed caption text file path."
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
        "-i", "--input", dest="input_path", type=Path, required=True, help="Input soundscript text file path."
    )
    add_output_argument(sound_parser)
    sound_parser.set_defaults(command="sound")

    return parser.parse_args(namespace=GmodMapScriptsArgs())


def add_output_argument(parser: ArgumentParser) -> None:
    parser.add_argument("-o", "--output", dest="output_path", type=Path, help="Output Lua file path.")


def format_addon_name(dir: Path) -> str:
    return dir.name.lower().replace(" ", "_")


def format_lua_numeric_value(value: str, default: str) -> str:
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


def main() -> None:
    args = parse_args()
    cwd = Path.cwd()

    try:
        # ClosedCaption
        if args.command == "closedcaption":
            source = args.input_path or cwd / "resource" / "closecaption_english.txt"
            output = args.output_path or cwd / "lua" / "subtitles" / f"subtitle_{format_addon_name(cwd)}.lua"
            keyvalues = ValveKeyValue.from_file(source)

            # Closed Caption의 lang.Tokens 블록을 읽기
            lang_block = keyvalues.block("lang")
            if lang_block is None:
                raise ValueError("lang block was not found.")
            tokens = lang_block.block("Tokens")
            if tokens is None:
                raise ValueError("lang.Tokens block was not found.")

            lines = [f'print("[{cwd.name}] Registering subtitles...")', "local subtable = {"]
            for item in tokens.items:
                if isinstance(item.value, str):
                    lines.append(
                        f"  {{ snd = {quote_lua_string(item.key)}, text = {quote_lua_string(item.value)}, range = 9999, duration = 5, closedcaption = true }},"
                    )
            lines.extend(
                [
                    "}",
                    "table.insert(Subtitles_Table, subtable)",
                    f'print("[{cwd.name}] Registering subtitles... DONE")',
                    "",
                ]
            )

            write_lua_file(output, "\n".join(lines))
            print(format_status("INFO", ConsoleColor.GREEN, f"Wrote '{output}'"))
            return

        # Sound
        if args.input_path is None:
            raise ValueError("The sound command requires an input file. Use '-i file_path'.")

        source = args.input_path
        output = (
            args.output_path
            or cwd / "lua" / "autorun" / f"sound_{format_addon_name(cwd)}_{source.stem.replace('sound_', '')}.lua"
        )
        keyvalues = ValveKeyValue.from_file(source)

        # soundscript의 각 블록을 sound.Add()로 변환
        lines = [f'print("[{cwd.name}] Registering sounds ({source.stem})...")']
        for item in keyvalues.items:
            if isinstance(item.value, str):
                continue

            sound_keyvalues = ValveKeyValue(item.value)
            rndwave = sound_keyvalues.block("rndwave")
            waves = rndwave.values("wave") if rndwave is not None else sound_keyvalues.values("wave")
            if not waves:
                print(
                    format_status("WARN", ConsoleColor.YELLOW, f"Skipping '{item.key}' because it has no wave."),
                    file=sys.stderr,
                )
                continue

            channel = normalize_source_constant(sound_keyvalues.value("channel") or "CHAN_AUTO")
            level = normalize_source_constant(sound_keyvalues.value("soundlevel") or "SNDLVL_NORM")
            volume = format_lua_numeric_value(sound_keyvalues.value("volume") or "1", "1")

            pitch_value = sound_keyvalues.value("pitch")
            if pitch_value is None:
                pitch = "100"
            else:
                normalized_pitch = pitch_value.strip()
                mapped = PITCH_VALUES.get(normalized_pitch.upper())
                if mapped is not None:
                    pitch = mapped
                else:
                    parts = [part.strip() for part in normalized_pitch.split(",")]
                    if len(parts) == 2 and all(parts):
                        pitch = f"{{ {format_lua_numeric_value(parts[0], '100')}, {format_lua_numeric_value(parts[1], '100')} }}"
                    else:
                        pitch = format_lua_numeric_value(normalized_pitch, "100")

            lines.append("sound.Add({")
            lines.append(f"  name = {quote_lua_string(item.key)},")
            if len(waves) == 1:
                lines.append(f"  sound = {quote_lua_string(waves[0])},")
            else:
                lines.append("  sound = {")
                for wave in waves:
                    lines.append(f"    {quote_lua_string(wave)},")
                lines.append("  },")
            lines.extend(
                [f"  channel = {channel},", f"  level = {level},", f"  volume = {volume},", f"  pitch = {pitch},", "})"]
            )

        lines.extend([f'print("[{cwd.name}] Registering sounds ({source.stem})... DONE")', ""])
        write_lua_file(output, "\n".join(lines))
        print(format_status("INFO", ConsoleColor.GREEN, f"Wrote '{output}'"))
    except Exception:
        raise


def normalize_source_constant(value: str) -> str:
    normalized = value.strip()
    if normalized.upper().startswith("SNDLVL_") and normalized.upper().endswith("DB"):
        return f"{normalized[:-2]}dB"
    return normalized


def quote_lua_string(value: str) -> str:
    return f'"{value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t").replace('"', '\\"')}"'


def write_lua_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, content, line_ending="\r\n")


if __name__ == "__main__":
    main()
