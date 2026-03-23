import re
import argparse
from pathlib import Path


def smart_replace(text):
    # 1. Simple symbol replacements
    # Longer/more-specific patterns first to avoid partial matches (e.g. => before >)
    text = re.sub(r"<<", "«", text)
    text = re.sub(r">>", "»", text)
    text = re.sub(r"<=", "⇐", text)
    text = re.sub(r"=>", "⇒", text)
    text = re.sub(r"<-", "←", text)
    text = re.sub(r"->", "→", text)

    # Strict 2-dash (-- but not ---)
    text = re.sub(r"(?<!-)--(?!-)", "―", text)

    # Strict 3-dot (... but not ....)
    text = re.sub(r"(?<!\.)\.\.\.(?!\.)", "…", text)

    # 2. Smart quotes — context-based, not counter-based
    #
    # Python 3's \w is Unicode-aware, so the context rules below handle Korean, CJK,
    # Cyrillic, etc. correctly without any extra flags.

    # --- Double quotes ---
    # Opening ": preceded by whitespace, opening bracket, or start-of-line
    text = re.sub(r'(^|[\s(\[{])"', lambda m: m.group(1) + '\u201c', text, flags=re.MULTILINE)
    # Closing ": all remaining "
    text = re.sub(r'"', "\u201d", text)

    # --- Single quotes ---
    # Step 1 — apostrophes between word characters (contractions, possessives,
    #           and closing quotes directly followed by a particle, e.g. '다중'은)
    text = re.sub(r"(?<=\w)'(?=\w)", "\u2019", text)
    # Step 2 — opening ': preceded by whitespace / opening bracket / start-of-line,
    #           followed by a non-space character
    text = re.sub(r"(^|[\s(\[{])'(?=\S)", lambda m: m.group(1) + '\u2018', text, flags=re.MULTILINE)
    # Step 3 — all remaining ' become closing quotes
    text = re.sub(r"'", "\u2019", text)

    return text


def smart_unreplace(text):
    # Reverse every transformation performed by smart_replace
    REVERSE_MAP = [
        ("«", "<<"),
        ("»", ">>"),
        ("⇐", "<="),
        ("⇒", "=>"),
        ("←", "<-"),
        ("→", "->"),
        ("―", "--"),
        ("…", "..."),
        ("\u201c", '"'),  # "
        ("\u201d", '"'),  # "
        ("\u2018", "'"),  # '
        ("\u2019", "'"),  # '
    ]
    for fancy, plain in REVERSE_MAP:
        text = text.replace(fancy, plain)
    return text


def transform_file(file_path, reverse=False):
    if file_path.suffix.lower() not in (".txt", ".md"):
        return

    try:
        content = file_path.read_text(encoding="utf-8")
        new_content = smart_unreplace(content) if reverse else smart_replace(content)

        if content != new_content:
            file_path.write_text(new_content, encoding="utf-8")
            print(f"✓ Processed: {file_path}")
        else:
            print(f"  No changes: {file_path}")
    except Exception as e:
        print(f"✗ Error processing {file_path}: {e}", file=__import__("sys").stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Replace ASCII typographic shortcuts with proper Unicode symbols.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python replace_character.py notes.txt
  python replace_character.py --reverse notes.md
  python replace_character.py docs/
  python replace_character.py --reverse docs/ notes.txt
""",
    )
    parser.add_argument("paths", nargs="+", metavar="PATH", help="Files or directories to process (.txt and .md only)")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse mode: convert Unicode symbols back to ASCII equivalents")

    args = parser.parse_args()

    for arg in args.paths:
        p = Path(arg)
        if p.is_file():
            transform_file(p, reverse=args.reverse)
        elif p.is_dir():
            print(f"Scanning directory: {p}")
            for file in p.rglob("*"):
                if file.is_file():
                    transform_file(file, reverse=args.reverse)
        else:
            print(f"! Path not found: {arg}", file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
