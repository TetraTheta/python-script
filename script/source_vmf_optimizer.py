#!/usr/bin/env python3
"""소스 엔진의 VMF 파일 최적화."""

import re
import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from library.cli import TerminalHelpFormatter
from library.console import ConsoleColor, format_status
from library.text_file import read_text_with_fallback, write_text
from library.valve_fgd import FgdEntityDefinition, FgdParseError, FgdParser

DEFAULT_FGD_PATH = Path(r"E:\Program Files\Steam\steamapps\common\GarrysMod\bin\garrysmod.fgd")
DEFAULT_OUTPUT_SUFFIX = "_opti"
DEFAULT_REMOVE_WHITESPACE = True
DEFAULT_REMOVE_VERTICES_PLUS = True
DEFAULT_ADD_OPTIMIZED_TAG = True
DEFAULT_SAVE_LOG = True
DEFAULT_VERBOSE = False
DEFAULT_REMOVE_LIGHTMAP = False
DEFAULT_FORCE = False
DEFAULT_REMOVE_UNKNOWN_KEYS = False
LOG_FILE_NAME = "source_vmf_optimizer.log"
OPTIMIZED_TAG = "optimized{}"
ALWAYS_KEEP_ENTITY_KEYS = {"classname", "id", "origin"}

VMF_KEYVALUE_PATTERN = re.compile(r'^\s*"(?P<key>[^"]+)"\s+"(?P<value>(?:\\.|[^"])*)"\s*$')
BSPSOURCE_COMMENT_PATTERN = re.compile(r"^Decompiled by BSPSource(?: v\d+(?:\.\d+)*)?(?: from .+)?$")

BRUSH_DEFAULTS = {
    "rotation": "0",
    "smoothing_groups": "0",
    "elevation": "0",
    "subdiv": "0",
}
LIGHTMAP_DEFAULTS = {"lightmapscale": "16"}
BRUSH_LIGHTMAP_DEFAULTS = BRUSH_DEFAULTS | LIGHTMAP_DEFAULTS


class SourceVmfOptimizerArgs(Namespace):
    target: Path | str
    recursive: bool
    fgd: Path | str
    inplace: bool
    suffix: str
    force: bool
    keep_whitespace: bool
    keep_vertices_plus: bool
    remove_lightmap: bool
    remove_unknown_keys: bool
    no_tag: bool
    no_log: bool
    verbose: bool


@dataclass(frozen=True)
class OptimizerOptions:
    fgd_path: Path
    inplace: bool
    suffix: str
    recursive: bool
    force: bool
    remove_whitespace: bool
    remove_vertices_plus: bool
    remove_lightmap: bool
    remove_unknown_keys: bool
    add_optimized_tag: bool
    save_log: bool
    verbose: bool
    use_fgd_defaults: bool


@dataclass
class OptimizeResult:
    source: Path
    output: Path | None
    skipped: bool
    total_lines: int
    removed_lines: int
    elapsed_ms: int
    message: str = ""
    verbose_events: list[str] = field(default_factory=list)


@dataclass
class VmfBlockContext:
    name: str
    block_id: str | None = None
    classname: str | None = None


@dataclass(frozen=True)
class VmfContext:
    description: str
    top_level_name: str | None


@dataclass(frozen=True)
class LineAction:
    remove: bool = False
    removed_lines: int = 0
    skip_to: int | None = None
    verbose_events: list[str] = field(default_factory=list)


def parse_args() -> SourceVmfOptimizerArgs:
    cli = ArgumentParser(
        prog="source-vmf-optimizer",
        description="Optimize Source Engine VMF files by removing redundant default values.",
        formatter_class=TerminalHelpFormatter,
    )
    cli.add_argument("target", help="VMF file or directory to optimize")
    cli.add_argument("-r", "--recursive", action="store_true", help="Process VMF files in subdirectories")
    cli.add_argument("-f", "--fgd", default=DEFAULT_FGD_PATH, help=f"FGD file path\n(default: {DEFAULT_FGD_PATH})")
    cli.add_argument("-i", "--inplace", action="store_true", help="Replace the source VMF file")
    cli.add_argument(
        "-s", "--suffix", default=DEFAULT_OUTPUT_SUFFIX, help=f"Output suffix\n(default: {DEFAULT_OUTPUT_SUFFIX})"
    )
    cli.add_argument(
        "-F", "--force", action="store_true", default=DEFAULT_FORCE, help="Re-optimize already tagged VMF files"
    )
    cli.add_argument(
        "-W",
        "--keep-whitespace",
        action="store_true",
        help=f"Keep whitespace, tabs, and newlines\n(default: {not DEFAULT_REMOVE_WHITESPACE})",
    )
    cli.add_argument(
        "-V",
        "--keep-vertices-plus",
        action="store_true",
        help=f"Keep Hammer++ vertices_plus data\n(default: {not DEFAULT_REMOVE_VERTICES_PLUS})",
    )
    cli.add_argument(
        "-m",
        "--remove-lightmap",
        action="store_true",
        default=DEFAULT_REMOVE_LIGHTMAP,
        help="Remove default lightmap values",
    )
    cli.add_argument(
        "-U",
        "--remove-unknown-keys",
        action="store_true",
        default=DEFAULT_REMOVE_UNKNOWN_KEYS,
        help="Remove top-level entity keys that are not defined in the FGD file",
    )
    cli.add_argument("-T", "--no-tag", action="store_true", help="Do not add optimized{} tag")
    cli.add_argument("-L", "--no-log", action="store_true", help="Do not write source_vmf_optimizer.log")
    cli.add_argument("-v", "--verbose", action="store_true", default=DEFAULT_VERBOSE, help="Print detailed output")
    return cli.parse_args(namespace=SourceVmfOptimizerArgs())


def main() -> None:
    args = parse_args()
    target = Path(args.target).resolve()
    files = find_vmf_files(target, args.recursive)

    if not files:
        print(format_status("ERROR", ConsoleColor.RED, "No VMF files to process"), file=sys.stderr)
        sys.exit(1)

    fgd_path = Path(args.fgd).resolve()
    definitions_by_class: dict[str, FgdEntityDefinition] = {}
    use_fgd_defaults = True
    try:
        definitions_by_class = FgdParser(fgd_path).parse_definitions()
    except (OSError, FgdParseError) as error:
        use_fgd_defaults = False
        print(
            format_status(
                "WARN",
                ConsoleColor.YELLOW,
                f"FGD defaults are disabled because '{fgd_path}' could not be parsed: {error}",
            )
        )

    options = OptimizerOptions(
        fgd_path=fgd_path,
        inplace=args.inplace,
        suffix=args.suffix,
        recursive=args.recursive,
        force=args.force,
        remove_whitespace=DEFAULT_REMOVE_WHITESPACE and not args.keep_whitespace,
        remove_vertices_plus=DEFAULT_REMOVE_VERTICES_PLUS and not args.keep_vertices_plus,
        remove_lightmap=args.remove_lightmap,
        remove_unknown_keys=args.remove_unknown_keys,
        add_optimized_tag=DEFAULT_ADD_OPTIMIZED_TAG and not args.no_tag,
        save_log=DEFAULT_SAVE_LOG and not args.no_log,
        verbose=args.verbose,
        use_fgd_defaults=use_fgd_defaults,
    )

    print_current_configuration(files, options)

    results: list[OptimizeResult] = []
    for source in files:
        result = optimize_vmf(source, definitions_by_class, options)
        results.append(result)
        print_result(result)

    if options.save_log:
        write_log(results, options)

    removed_lines = sum(result.removed_lines for result in results)
    total_lines = sum(result.total_lines for result in results)
    processed_files = len([result for result in results if not result.skipped])
    percent = removed_lines / total_lines * 100 if total_lines else 0
    print(
        format_status(
            "DONE",
            ConsoleColor.GREEN,
            f"Optimized {processed_files} file(s). Removed {removed_lines} out of {total_lines} lines ({percent:.2f}%).",
        )
    )


def find_vmf_files(target: Path, recursive: bool) -> list[Path]:
    if target.is_file() and target.suffix.lower() == ".vmf":
        return [target]
    if target.is_dir():
        iterator = target.rglob("*.vmf") if recursive else target.glob("*.vmf")
        return sorted(path for path in iterator if path.is_file())
    return []


def print_current_configuration(files: list[Path], options: OptimizerOptions) -> None:
    output_mode = "replace source files" if options.inplace else f"create '*{options.suffix}.vmf'"
    print("Current configuration:")
    print(f"  - Target VMF files: {len(files)}")
    print(f"  - Recursive directory scan: {options.recursive}")
    print(f"  - Output mode: {output_mode}")
    print(f"  - FGD default removal: {options.use_fgd_defaults}")
    print(f"  - FGD file: {options.fgd_path}")
    print(f"  - Remove whitespace: {options.remove_whitespace}")
    print(f"  - Remove vertices_plus: {options.remove_vertices_plus}")
    print(f"  - Remove lightmap values: {options.remove_lightmap}")
    print(f"  - Remove FGD-unknown entity keys: {options.remove_unknown_keys and options.use_fgd_defaults}")
    print(f"  - Add optimized tag: {options.add_optimized_tag}")
    print(f"  - Re-optimize already tagged files: {options.force}")
    print(f"  - Save log: {options.save_log}")


def optimize_vmf(
    source: Path, definitions_by_class: dict[str, FgdEntityDefinition], options: OptimizerOptions
) -> OptimizeResult:
    started_at = perf_counter()
    try:
        original_text = read_text_with_fallback(source)
    except OSError as error:
        return OptimizeResult(source, None, True, 0, 0, 0, f"Failed to read file: {error}")

    lines = original_text.splitlines()
    total_lines = len(lines)
    if lines and lines[0].strip() == OPTIMIZED_TAG:
        if not options.force:
            return OptimizeResult(source, None, True, total_lines, 0, 0, "Already optimized")
        lines = lines[1:]
        total_lines -= 1

    output_lines, removed_lines, verbose_events = optimize_lines(lines, definitions_by_class, options)
    if options.add_optimized_tag:
        output_lines.insert(0, OPTIMIZED_TAG)

    output_text = format_output(output_lines, options.remove_whitespace)
    output = source if options.inplace else source.with_name(f"{source.stem}{options.suffix}{source.suffix}")

    try:
        write_text(output, output_text)
    except OSError as error:
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        return OptimizeResult(
            source,
            output,
            True,
            total_lines,
            removed_lines,
            elapsed_ms,
            f"Failed to write file: {error}",
            verbose_events,
        )

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    return OptimizeResult(source, output, False, total_lines, removed_lines, elapsed_ms, verbose_events=verbose_events)


def optimize_lines(
    lines: list[str],
    definitions_by_class: dict[str, FgdEntityDefinition],
    options: OptimizerOptions,
) -> tuple[list[str], int, list[str]]:
    output: list[str] = []
    verbose_events: list[str] = []
    contexts = build_vmf_contexts(lines, options.verbose)
    removed_lines = 0
    index = 0

    while index < len(lines):
        line = lines[index]
        if line.strip() == "entity" and index + 1 < len(lines) and lines[index + 1].strip() == "{":
            block, next_index = collect_vmf_block(lines, index)
            optimized_block, removed, events = optimize_entity_block(block, definitions_by_class, options)
            output.extend(optimized_block)
            removed_lines += removed
            verbose_events.extend(events)
            index = next_index
            continue

        action = process_special_line(lines, index, options, contexts)
        if action.skip_to is not None:
            removed_lines += action.removed_lines
            verbose_events.extend(action.verbose_events)
            index = action.skip_to
            continue
        if action.remove:
            removed_lines += 1
            verbose_events.extend(action.verbose_events)
        else:
            output.append(line)
        index += 1

    return output, removed_lines, verbose_events


def process_special_line(
    lines: list[str],
    index: int,
    options: OptimizerOptions,
    contexts: list[VmfContext],
) -> LineAction:
    if index >= len(lines):
        return LineAction()

    stripped = lines[index].strip()

    # vertices_plus 제거 (선택)
    if options.remove_vertices_plus and stripped == "vertices_plus":
        next_index = collect_named_vmf_block(lines, index)
        if next_index is not None:
            removed_lines = next_index - index
            return LineAction(
                removed_lines=removed_lines,
                skip_to=next_index,
                verbose_events=make_verbose_events(
                    contexts, index, f"removed Hammer++ vertices_plus block ({removed_lines} lines)"
                ),
            )
    # palette_plus 제거
    if stripped == "palette_plus":
        next_index = collect_named_vmf_block(lines, index)
        if next_index is not None:
            removed_lines = next_index - index
            return LineAction(
                removed_lines=removed_lines,
                skip_to=next_index,
                verbose_events=make_verbose_events(
                    contexts, index, f"removed Hammer++ palette_plus block ({removed_lines} lines)"
                ),
            )
    # colorcorrection_plus 제거
    if stripped == "colorcorrection_plus":
        next_index = collect_named_vmf_block(lines, index)
        if next_index is not None:
            removed_lines = next_index - index
            return LineAction(
                removed_lines=removed_lines,
                skip_to=next_index,
                verbose_events=make_verbose_events(
                    contexts, index, f"removed Hammer++ colorcorrection_plus block ({removed_lines} lines)"
                ),
            )
    # light_plus 제거
    if stripped == "light_plus":
        next_index = collect_named_vmf_block(lines, index)
        if next_index is not None:
            removed_lines = next_index - index
            return LineAction(
                removed_lines=removed_lines,
                skip_to=next_index,
                verbose_events=make_verbose_events(
                    contexts, index, f"removed Hammer++ light_plus block ({removed_lines} lines)"
                ),
            )
    # postprocess_plus 제거
    if stripped == "postprocess_plus":
        next_index = collect_named_vmf_block(lines, index)
        if next_index is not None:
            removed_lines = next_index - index
            return LineAction(
                removed_lines=removed_lines,
                skip_to=next_index,
                verbose_events=make_verbose_events(
                    contexts, index, f"removed Hammer++ postprocess_plus block ({removed_lines} lines)"
                ),
            )
    # bgimages_plus 제거
    if stripped == "bgimages_plus":
        next_index = collect_named_vmf_block(lines, index)
        if next_index is not None:
            removed_lines = next_index - index
            return LineAction(
                removed_lines=removed_lines,
                skip_to=next_index,
                verbose_events=make_verbose_events(
                    contexts, index, f"removed Hammer++ bgimages_plus block ({removed_lines} lines)"
                ),
            )

    keyvalue = parse_vmf_keyvalue(stripped)
    if keyvalue is None:
        return LineAction()
    key, value = keyvalue

    # versioninfo.mapversion, world.mapversion, world.comment 제거
    block = contexts[index].top_level_name if index < len(contexts) else None
    if block == "versioninfo":
        if key == "mapversion":
            return LineAction(
                remove=True, verbose_events=make_verbose_events(contexts, index, 'removed versioninfo "mapversion"')
            )
    elif block == "world":
        if key == "mapversion":
            return LineAction(
                remove=True, verbose_events=make_verbose_events(contexts, index, 'removed world "mapversion"')
            )
        elif key == "comment" and BSPSOURCE_COMMENT_PATTERN.fullmatch(value):
            return LineAction(
                remove=True, verbose_events=make_verbose_events(contexts, index, "removed BSPSource comment")
            )

    # 기본값 제거
    defaults = BRUSH_LIGHTMAP_DEFAULTS if options.remove_lightmap else BRUSH_DEFAULTS
    if defaults.get(key) == value:
        return LineAction(
            remove=True,
            verbose_events=make_verbose_events(
                contexts,
                index,
                f'removed brush default "{key}"="{value}"',
            ),
        )

    return LineAction()


def optimize_entity_block(
    block: list[str],
    definitions_by_class: dict[str, FgdEntityDefinition],
    options: OptimizerOptions,
) -> tuple[list[str], int, list[str]]:
    classname = find_classname(block)
    definition = definitions_by_class.get(classname.lower()) if classname and options.use_fgd_defaults else None
    defaults = definition.defaults if definition is not None else {}
    properties = definition.properties if definition is not None else set()
    output: list[str] = []
    verbose_events: list[str] = []
    contexts = build_vmf_contexts(block, include_description=options.verbose)
    removed_lines = 0
    index = 0
    depth = 0

    while index < len(block):
        stripped = block[index].strip()
        current_depth = depth
        if stripped == "{":
            depth += 1
        elif stripped == "}":
            depth = max(0, depth - 1)

        action = process_special_line(block, index, options, contexts)
        if action.skip_to is not None:
            removed_lines += action.removed_lines
            verbose_events.extend(action.verbose_events)
            index = action.skip_to
            continue

        line = block[index]
        keyvalue = parse_vmf_keyvalue(line.strip())
        if keyvalue is not None:
            key, value = keyvalue
            key_lower = key.lower()
            if key_lower != "classname" and defaults.get(key_lower) == value:
                removed_lines += 1
                verbose_events.extend(make_verbose_events(contexts, index, f'removed FGD default "{key}"="{value}"'))
                index += 1
                continue
            if (
                options.remove_unknown_keys
                and options.use_fgd_defaults
                and definition is not None
                and current_depth == 1
                and key_lower not in properties
                and key_lower not in ALWAYS_KEEP_ENTITY_KEYS
            ):
                removed_lines += 1
                verbose_events.extend(
                    make_verbose_events(contexts, index, f'removed FGD-unknown key "{key}"="{value}"')
                )
                index += 1
                continue

        if action.remove:
            removed_lines += 1
            verbose_events.extend(action.verbose_events)
        else:
            output.append(line)
        index += 1

    return output, removed_lines, verbose_events


def collect_vmf_block(lines: list[str], start: int) -> tuple[list[str], int]:
    block: list[str] = []
    depth = 0
    index = start
    seen_open = False

    while index < len(lines):
        line = lines[index]
        block.append(line)
        stripped = line.strip()
        if stripped == "{":
            depth += 1
            seen_open = True
        elif stripped == "}":
            depth -= 1
            if seen_open and depth <= 0:
                return block, index + 1
        index += 1

    return block, index


def collect_named_vmf_block(lines: list[str], start: int) -> int | None:
    if start + 1 >= len(lines) or lines[start + 1].strip() != "{":
        return None

    depth = 0
    index = start + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped == "{":
            depth += 1
        elif stripped == "}":
            depth -= 1
            if depth <= 0:
                return index + 1
        index += 1

    return None


def make_verbose_events(contexts: list[VmfContext], index: int, detail: str) -> list[str]:
    if index >= len(contexts) or not contexts[index].description:
        return []
    return [make_verbose_event(contexts, index, detail)]


def make_verbose_event(contexts: list[VmfContext], index: int, detail: str) -> str:
    context = contexts[index].description if index < len(contexts) else ""
    return f"{context}: {detail}" if context else detail


def build_vmf_contexts(lines: list[str], include_description: bool) -> list[VmfContext]:
    def current_context(stack: list[VmfBlockContext]) -> VmfContext:
        description = format_vmf_context(stack) if include_description else ""
        top_level_name = stack[0].name if stack else None
        return VmfContext(description, top_level_name)

    stack: list[VmfBlockContext] = []
    pending_name: str | None = None
    contexts: list[VmfContext] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            contexts.append(current_context(stack))
            continue
        if stripped == "{":
            name = pending_name or "block"
            stack.append(VmfBlockContext(name))
            pending_name = None
            contexts.append(current_context(stack))
            continue
        if stripped == "}":
            contexts.append(current_context(stack))
            if stack:
                stack.pop()
            pending_name = None
            continue

        contexts.append(current_context(stack))
        keyvalue = parse_vmf_keyvalue(stripped)
        if keyvalue is not None:
            key, value = keyvalue
            if stack:
                if key.lower() == "id":
                    stack[-1].block_id = value
                elif key.lower() == "classname":
                    stack[-1].classname = value
            pending_name = None
            continue

        pending_name = stripped

    return contexts


def format_vmf_context(stack: list[VmfBlockContext]) -> str:
    parts: list[str] = []
    for context in stack:
        label = context.name
        if context.block_id is not None:
            label = f"{label} id={context.block_id}"
        if context.classname is not None:
            label = f"{label} classname={context.classname}"
        parts.append(label)
    return " > ".join(parts)


def find_classname(lines: list[str]) -> str | None:
    for line in lines:
        keyvalue = parse_vmf_keyvalue(line.strip())
        if keyvalue is None:
            continue
        key, value = keyvalue
        if key.lower() == "classname":
            return value
    return None


def parse_vmf_keyvalue(line: str) -> tuple[str, str] | None:
    match = VMF_KEYVALUE_PATTERN.match(line)
    if match is None:
        return None
    return match.group("key"), match.group("value")


def format_output(lines: list[str], remove_whitespace: bool) -> str:
    if remove_whitespace:
        if lines and lines[0] == OPTIMIZED_TAG:
            return f"{OPTIMIZED_TAG}\n{''.join(remove_extra_chars(line) for line in lines[1:])}"
        return "".join(remove_extra_chars(line) for line in lines)
    return "\n".join(lines) + "\n"


def remove_extra_chars(line: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(line):
        if line[index : index + 3] == '" "':
            result.append('""')
            index += 3
            continue
        if line[index] not in "\r\n\t":
            result.append(line[index])
        index += 1
    return "".join(result)


def print_result(result: OptimizeResult) -> None:
    if result.skipped:
        color = ConsoleColor.YELLOW if result.total_lines else ConsoleColor.RED
        print(format_status("SKIP", color, f"{result.source}: {result.message}"))
        return

    percent = result.removed_lines / result.total_lines * 100 if result.total_lines else 0
    print(
        format_status(
            "OPTIM",
            ConsoleColor.GREEN,
            f"{result.source.name} -> {result.output} | removed {result.removed_lines}/{result.total_lines} ({percent:.2f}%)",
        )
    )
    if result.verbose_events:
        for event in result.verbose_events:
            if event:
                print(format_status("VERB", ConsoleColor.BLUE, event))


def write_log(results: list[OptimizeResult], options: OptimizerOptions) -> None:
    lines = [
        "Source VMF Optimizer Log",
        "",
        "Current configuration:",
        f"  - FGD default removal: {options.use_fgd_defaults}",
        f"  - FGD file: {options.fgd_path}",
        f"  - Remove whitespace: {options.remove_whitespace}",
        f"  - Remove vertices_plus: {options.remove_vertices_plus}",
        f"  - Remove lightmap values: {options.remove_lightmap}",
        f"  - Remove FGD-unknown entity keys: {options.remove_unknown_keys and options.use_fgd_defaults}",
        f"  - Add optimized tag: {options.add_optimized_tag}",
        f"  - Re-optimize already tagged files: {options.force}",
        "",
    ]
    for result in results:
        status = "skipped" if result.skipped else "optimized"
        lines.append(
            f"{status}: {result.source} -> {result.output} "
            f"removed={result.removed_lines} total={result.total_lines} elapsed_ms={result.elapsed_ms} {result.message}"
        )
    Path(LOG_FILE_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
