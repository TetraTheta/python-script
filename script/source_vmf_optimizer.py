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
from library.text_file import format_exception_message, print_exception, write_text
from library.valve_fgd import FgdEntityDefinition, FgdParseError, FgdParser
from library.valve_vmf import ValveVmf, VmfBlock, VmfKeyValue

GMOD_BIN_PATH = Path(r"E:\Program Files\Steam\steamapps\common\GarrysMod\bin")
DEFAULT_FGD_PATH = GMOD_BIN_PATH / ("sctools.fgd" if (GMOD_BIN_PATH / "sctools.fgd").exists() else "garrysmod.fgd")
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
SANITIZED_TAG = "sanitized{}"
VMF_TAG_ORDER = (OPTIMIZED_TAG, SANITIZED_TAG)
ALWAYS_KEEP_ENTITY_KEYS = {"classname", "id", "origin"}

BSPSOURCE_COMMENT_PATTERN = re.compile(r"^Decompiled by BSPSource(?: v\d+(?:\.\d+)*)?(?: from .+)?$")

# VMF에서 제거하는 대상:
# - Hammer++ 보조 블록: vertices_plus(선택), palette_plus, colorcorrection_plus,
#   light_plus, postprocess_plus, bgimages_plus
# - 버전/디컴파일 흔적: versioninfo.mapversion, versioninfo.editorbuild,
#   world.mapversion, BSPSource world.comment
# - 브러시 기본값: rotation, smoothing_groups, elevation, subdiv,
#   lightmapscale(선택)
# - 엔티티 기본값: FGD 기본값, FGD에 없는 최상위 엔티티 키(선택)
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
        print_exception(error)
        print(
            format_status(
                "WARN",
                ConsoleColor.YELLOW,
                f"FGD defaults are disabled because '{fgd_path}' could not be parsed: {format_exception_message(error)}",
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
        vmf = ValveVmf.from_file(source, VMF_TAG_ORDER)
    except (OSError, UnicodeError) as error:
        print_exception(error)
        return OptimizeResult(source, None, True, 0, 0, 0, f"Failed to read file: {format_exception_message(error)}")

    total_lines = vmf.line_count
    if OPTIMIZED_TAG in vmf.tags:
        if not options.force:
            return OptimizeResult(source, None, True, total_lines, 0, 0, "Already optimized")

    removed_lines, verbose_events = optimize_vmf_file(vmf, definitions_by_class, options)
    if options.add_optimized_tag:
        vmf.tags.add(OPTIMIZED_TAG)
    else:
        vmf.tags.discard(OPTIMIZED_TAG)

    output_text = vmf.render_text(options.remove_whitespace)
    output = source if options.inplace else source.with_name(f"{source.stem}{options.suffix}{source.suffix}")

    try:
        write_text(output, output_text)
    except (OSError, UnicodeError) as error:
        print_exception(error)
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        return OptimizeResult(
            source,
            output,
            True,
            total_lines,
            removed_lines,
            elapsed_ms,
            f"Failed to write file: {format_exception_message(error)}",
            verbose_events,
        )

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    return OptimizeResult(source, output, False, total_lines, removed_lines, elapsed_ms, verbose_events=verbose_events)


def optimize_vmf_file(
    vmf: ValveVmf,
    definitions_by_class: dict[str, FgdEntityDefinition],
    options: OptimizerOptions,
) -> tuple[int, list[str]]:
    verbose_events: list[str] = []
    removed_lines = 0

    removed, events = remove_special_blocks(vmf, options)
    removed_lines += removed
    verbose_events.extend(events)

    for keyvalue in list(vmf.each_keyvalue()):
        if should_remove_top_level_key(keyvalue) or should_remove_brush_default(keyvalue, options):
            removed_lines += keyvalue.line_count
            verbose_events.extend(
                make_verbose_events(
                    options.verbose,
                    keyvalue,
                    f'removed "{keyvalue.key}"="{keyvalue.value}"',
                )
            )
            keyvalue.remove()

    for entity in vmf.blocks("entity"):
        removed, events = optimize_entity_block(entity, definitions_by_class, options)
        removed_lines += removed
        verbose_events.extend(events)

    return removed_lines, verbose_events


def remove_special_blocks(block: VmfBlock, options: OptimizerOptions) -> tuple[int, list[str]]:
    removed_lines = 0
    verbose_events: list[str] = []
    for child in list(block.children):
        if not isinstance(child, VmfBlock):
            continue
        if should_remove_block(child, options):
            removed = child.line_count
            removed_lines += removed
            verbose_events.extend(
                make_verbose_events(
                    options.verbose,
                    child,
                    f"removed Hammer++ {child.name} block ({removed} lines)",
                )
            )
            child.remove()
            continue
        removed, events = remove_special_blocks(child, options)
        removed_lines += removed
        verbose_events.extend(events)
    return removed_lines, verbose_events


def should_remove_block(block: VmfBlock, options: OptimizerOptions) -> bool:
    removable = {"palette_plus", "colorcorrection_plus", "light_plus", "postprocess_plus", "bgimages_plus"}
    if options.remove_vertices_plus:
        removable.add("vertices_plus")
    return (block.name or "").lower() in removable


def should_remove_top_level_key(keyvalue: VmfKeyValue) -> bool:
    block = keyvalue.parent
    if block is None or block.parent is None or block.parent.name is not None:
        return False
    block_name = (block.name or "").lower()
    key = keyvalue.key.lower()
    if block_name == "versioninfo":
        return key in {"mapversion", "editorbuild"}
    if block_name == "world":
        return key == "mapversion" or (
            key == "comment" and BSPSOURCE_COMMENT_PATTERN.fullmatch(keyvalue.value) is not None
        )
    return False


def should_remove_brush_default(keyvalue: VmfKeyValue, options: OptimizerOptions) -> bool:
    defaults = BRUSH_LIGHTMAP_DEFAULTS if options.remove_lightmap else BRUSH_DEFAULTS
    return defaults.get(keyvalue.key.lower()) == keyvalue.value


def optimize_entity_block(
    entity: VmfBlock,
    definitions_by_class: dict[str, FgdEntityDefinition],
    options: OptimizerOptions,
) -> tuple[int, list[str]]:
    classname = entity.key("classname")
    definition = (
        definitions_by_class.get(classname.value.lower())
        if classname is not None and options.use_fgd_defaults
        else None
    )
    defaults = definition.defaults if definition is not None else {}
    properties = definition.properties if definition is not None else set()
    verbose_events: list[str] = []
    removed_lines = 0

    for keyvalue in list(entity.each_keyvalue()):
        key_lower = keyvalue.key.lower()
        if key_lower != "classname" and defaults.get(key_lower) == keyvalue.value:
            removed_lines += keyvalue.line_count
            verbose_events.extend(
                make_verbose_events(
                    options.verbose,
                    keyvalue,
                    f'removed FGD default "{keyvalue.key}"="{keyvalue.value}"',
                )
            )
            keyvalue.remove()

    if not (options.remove_unknown_keys and options.use_fgd_defaults and definition is not None):
        return removed_lines, verbose_events

    for keyvalue in list(entity.keys()):
        key_lower = keyvalue.key.lower()
        if key_lower not in properties and key_lower not in ALWAYS_KEEP_ENTITY_KEYS:
            removed_lines += keyvalue.line_count
            verbose_events.extend(
                make_verbose_events(
                    options.verbose,
                    keyvalue,
                    f'removed FGD-unknown key "{keyvalue.key}"="{keyvalue.value}"',
                )
            )
            keyvalue.remove()

    return removed_lines, verbose_events


def make_verbose_events(verbose: bool, node: VmfBlock | VmfKeyValue, detail: str) -> list[str]:
    if not verbose:
        return []
    return [f"{format_vmf_context(node)}: {detail}"]


def format_vmf_context(node: VmfBlock | VmfKeyValue) -> str:
    parts: list[str] = []
    block = node if isinstance(node, VmfBlock) else node.parent
    stack: list[VmfBlock] = []
    while block is not None and block.name is not None:
        stack.append(block)
        block = block.parent
    for item in reversed(stack):
        label = item.name or "block"
        block_id = item.key("id")
        classname = item.key("classname")
        if block_id is not None:
            label = f"{label} id={block_id.value}"
        if classname is not None:
            label = f"{label} classname={classname.value}"
        parts.append(label)
    return " > ".join(parts) or node.path


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
    write_text(Path(LOG_FILE_NAME), "\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
