#!/usr/bin/env python3
"""소스 엔진 VMF 파일의 좌표값을 정수 격자로 보정."""

import re
import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter

from library.cli import TerminalHelpFormatter
from library.console import ConsoleColor, format_status
from library.text_file import format_exception_message, print_exception, write_text
from library.valve_vmf import ValveVmf

DEFAULT_OUTPUT_SUFFIX = "_san"
DEFAULT_SAVE_LOG = True
DEFAULT_VERBOSE = False
DEFAULT_FORCE = False
LOG_FILE_NAME = "source_vmf_sanitizer.log"
OPTIMIZED_TAG = "optimized{}"
SANITIZED_TAG = "sanitized{}"
VMF_TAG_ORDER = (OPTIMIZED_TAG, SANITIZED_TAG)

# 부동소수점 문제 때문에 사실상 0인 값이 3.33786e-06로 저장되는 경우가 있음
COORDINATE_PATTERN = r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
PLANE_POINT_PATTERN = re.compile(
    rf"\((?P<x>{COORDINATE_PATTERN}) (?P<y>{COORDINATE_PATTERN}) (?P<z>{COORDINATE_PATTERN})\)"
)
ORIGIN_PATTERN = re.compile(rf"^(?P<x>{COORDINATE_PATTERN}) (?P<y>{COORDINATE_PATTERN}) (?P<z>{COORDINATE_PATTERN})$")
ROTATION_PATTERN = re.compile(rf"^{COORDINATE_PATTERN}$")


class SourceVmfSanitizerArgs(Namespace):
    target: Path | str
    recursive: bool
    inplace: bool
    suffix: str
    force: bool
    include_origin: bool
    no_tag: bool
    no_log: bool
    verbose: bool


@dataclass(frozen=True)
class SanitizerOptions:
    inplace: bool
    suffix: str
    recursive: bool
    force: bool
    include_origin: bool
    add_sanitized_tag: bool
    save_log: bool
    verbose: bool


@dataclass
class SanitizeResult:
    source: Path
    output: Path | None
    skipped: bool
    total_lines: int
    changed_values: int
    elapsed_ms: int
    message: str = ""
    verbose_events: list[str] = field(default_factory=list)


def parse_args() -> SourceVmfSanitizerArgs:
    cli = ArgumentParser(
        prog="source-vmf-sanitizer",
        description="Sanitize Source Engine VMF coordinates by rounding decimal values to integers.",
        formatter_class=TerminalHelpFormatter,
    )
    cli.add_argument("target", nargs="?", help="VMF file or directory to sanitize")
    cli.add_argument("-r", "--recursive", action="store_true", help="Process VMF files in subdirectories")
    cli.add_argument("-i", "--inplace", action="store_true", help="Replace the source VMF file")
    cli.add_argument(
        "-s", "--suffix", default=DEFAULT_OUTPUT_SUFFIX, help=f"Output suffix\n(default: {DEFAULT_OUTPUT_SUFFIX})"
    )
    cli.add_argument(
        "-F", "--force", action="store_true", default=DEFAULT_FORCE, help="Re-sanitize already tagged VMF files"
    )
    cli.add_argument(
        "-O",
        "--include-origin",
        dest="include_origin",
        action="store_true",
        help="Also round entity origin, entity angles, and brush face rotation values. This can move entities.",
    )
    cli.add_argument("-T", "--no-tag", action="store_true", help="Do not add sanitized{} tag")
    cli.add_argument("-L", "--no-log", action="store_true", help="Do not write source_vmf_sanitizer.log")
    cli.add_argument("-v", "--verbose", action="store_true", default=DEFAULT_VERBOSE, help="Print detailed output")
    return cli.parse_args(namespace=SourceVmfSanitizerArgs())


def main() -> None:
    args = parse_args()
    if args.target is None:
        print(format_status("ERROR", ConsoleColor.RED, "No VMF file or directory was provided"), file=sys.stderr)
        sys.exit(1)

    target = Path(args.target).resolve()
    files = find_vmf_files(target, args.recursive)
    if not files:
        print(format_status("ERROR", ConsoleColor.RED, "No VMF files to process"), file=sys.stderr)
        sys.exit(1)

    options = SanitizerOptions(
        inplace=args.inplace,
        suffix=args.suffix,
        recursive=args.recursive,
        force=args.force,
        include_origin=args.include_origin,
        add_sanitized_tag=not args.no_tag,
        save_log=DEFAULT_SAVE_LOG and not args.no_log,
        verbose=args.verbose,
    )

    print_current_configuration(files, options)

    results: list[SanitizeResult] = []
    for source in files:
        result = sanitize_vmf(source, options)
        results.append(result)
        print_result(result)

    if options.save_log:
        write_log(results, options)

    changed_values = sum(result.changed_values for result in results)
    processed_files = len([result for result in results if not result.skipped])
    print(
        format_status(
            "DONE", ConsoleColor.GREEN, f"Sanitized {processed_files} file(s). Changed {changed_values} value(s)."
        )
    )


def find_vmf_files(target: Path, recursive: bool) -> list[Path]:
    if target.is_file() and target.suffix.lower() == ".vmf":
        return [target]
    if target.is_dir():
        iterator = target.rglob("*.vmf") if recursive else target.glob("*.vmf")
        return sorted(path for path in iterator if path.is_file())
    return []


def print_current_configuration(files: list[Path], options: SanitizerOptions) -> None:
    output_mode = "replace source files" if options.inplace else f"create '*{options.suffix}.vmf'"
    print("Current configuration:")
    print(f"  - Target VMF files: {len(files)}")
    print(f"  - Recursive directory scan: {options.recursive}")
    print(f"  - Output mode: {output_mode}")
    print("  - Round brush plane coordinates: True")
    print(f"  - Round entity origins, entity angles, and face rotations: {options.include_origin}")
    print(f"  - Add sanitized tag: {options.add_sanitized_tag}")
    print(f"  - Re-sanitize already tagged files: {options.force}")
    print(f"  - Save log: {options.save_log}")


def sanitize_vmf(source: Path, options: SanitizerOptions) -> SanitizeResult:
    started_at = perf_counter()
    try:
        vmf = ValveVmf.from_file(source, VMF_TAG_ORDER)
    except (OSError, UnicodeError) as error:
        print_exception(error)
        return SanitizeResult(source, None, True, 0, 0, 0, f"Failed to read file: {format_exception_message(error)}")

    total_lines = vmf.line_count
    if SANITIZED_TAG in vmf.tags:
        if not options.force:
            return SanitizeResult(source, None, True, total_lines, 0, 0, "Already sanitized")

    changed_values, verbose_events = sanitize_vmf_file(vmf, options)
    if options.add_sanitized_tag:
        vmf.tags.add(SANITIZED_TAG)
    else:
        vmf.tags.discard(SANITIZED_TAG)

    output = source if options.inplace else source.with_name(f"{source.stem}{options.suffix}{source.suffix}")
    try:
        write_text(output, vmf.render_text())
    except (OSError, UnicodeError) as error:
        print_exception(error)
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        return SanitizeResult(
            source,
            output,
            True,
            total_lines,
            changed_values,
            elapsed_ms,
            f"Failed to write file: {format_exception_message(error)}",
            verbose_events,
        )

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    return SanitizeResult(source, output, False, total_lines, changed_values, elapsed_ms, verbose_events=verbose_events)


def sanitize_vmf_file(vmf: ValveVmf, options: SanitizerOptions) -> tuple[int, list[str]]:
    verbose_events: list[str] = []
    changed_values = 0

    for keyvalue in vmf.each_keyvalue():
        sanitized, changed = sanitize_keyvalue(keyvalue.key, keyvalue.value, options)
        if changed == 0:
            continue
        changed_values += changed
        if options.verbose:
            verbose_events.append(f'rounded {changed} coordinate value(s) in "{keyvalue.path}"')
        keyvalue.set(sanitized)
    return changed_values, verbose_events


def sanitize_keyvalue(key: str, value: str, options: SanitizerOptions) -> tuple[str, int]:
    key_lower = key.lower()
    if key_lower == "plane":
        sanitized, changed = sanitize_plane(value)
    # uaxis/vaxis는 텍스처 투영 축이다. sin/cos 성분을 정수화하면 텍스처 회전이 크게 망가진다.
    elif key_lower in {"angles", "origin"} and options.include_origin:
        sanitized, changed = sanitize_origin(value)
    elif key_lower == "rotation" and options.include_origin:
        sanitized, changed = sanitize_rotation(value)
    else:
        return value, 0

    return sanitized, changed


def sanitize_plane(value: str) -> tuple[str, int]:
    changed = 0

    def replace_point(match: re.Match[str]) -> str:
        nonlocal changed
        values = [match.group("x"), match.group("y"), match.group("z")]
        rounded = [round_coordinate(value) for value in values]
        changed += sum(original != sanitized for original, sanitized in zip(values, rounded, strict=True))
        return f"({rounded[0]} {rounded[1]} {rounded[2]})"

    return PLANE_POINT_PATTERN.sub(replace_point, value), changed


def sanitize_origin(value: str) -> tuple[str, int]:
    match = ORIGIN_PATTERN.match(value)
    if match is None:
        return value, 0

    values = [match.group("x"), match.group("y"), match.group("z")]
    rounded = [round_coordinate(value) for value in values]
    changed = sum(original != sanitized for original, sanitized in zip(values, rounded, strict=True))
    return " ".join(rounded), changed


def sanitize_rotation(value: str) -> tuple[str, int]:
    if ROTATION_PATTERN.match(value) is None:
        return value, 0

    rounded = round_coordinate(value)
    return rounded, int(value != rounded)


def round_coordinate(value: str) -> str:
    try:
        return str(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return value


def print_result(result: SanitizeResult) -> None:
    if result.skipped:
        color = ConsoleColor.YELLOW if result.total_lines else ConsoleColor.RED
        print(format_status("SKIP", color, f"{result.source}: {result.message}"))
        return

    print(
        format_status(
            "SANIT",
            ConsoleColor.GREEN,
            f"{result.source.name} -> {result.output} | changed {result.changed_values} value(s)",
        )
    )
    for event in result.verbose_events:
        print(format_status("VERB", ConsoleColor.BLUE, event))


def write_log(results: list[SanitizeResult], options: SanitizerOptions) -> None:
    lines = [
        "Source VMF Sanitizer Log",
        "",
        "Current configuration:",
        "  - Round brush plane coordinates: True",
        f"  - Round entity origins, entity angles, and face rotations: {options.include_origin}",
        f"  - Add sanitized tag: {options.add_sanitized_tag}",
        f"  - Re-sanitize already tagged files: {options.force}",
        "",
    ]
    for result in results:
        status = "skipped" if result.skipped else "sanitized"
        lines.append(
            f"{status}: {result.source} -> {result.output} "
            f"changed={result.changed_values} total={result.total_lines} elapsed_ms={result.elapsed_ms} {result.message}"
        )
    write_text(Path(LOG_FILE_NAME), "\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
