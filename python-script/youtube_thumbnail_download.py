import argparse
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import urlopen


def get_youtube_id(url: str) -> str:
    # YouTube video ID only
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", url):
        return url

    try:
        # normalize url
        url = re.sub(r"(attribution_link|uploademail|youtube-nocookie)", "x", url, flags=re.IGNORECASE)
        parsed = urlparse(url)

        # check embed case (?=url=...)
        query = parse_qs(parsed.query)
        embed = query.get("url")
        if embed:
            parsed = urlparse(embed[0])
            query = parse_qs(parsed.query)

        # standard ?v= parameter
        v = query.get("v")
        if v:
            return v[0]

        # remove unwanted parameters
        del_params = ["a", "app", "list", "feature", "rel", "si"]
        filtered_query = {k: v for k, v in query.items() if k not in del_params}
        rebuilt_url = urlunparse(parsed._replace(query=urlencode(filtered_query, doseq=True)))

        # replace encoded '='
        rebuilt_url = rebuilt_url.replace("%3D", "=")

        # find first 11-char ID
        match = re.search(r"[a-zA-Z0-9_-]{11}", rebuilt_url)
        if match:
            return match.group(0)

        return ""
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="Download YouTube max resolution thumbnail image.")
    parser.add_argument("input", help="YouTube URL or YouTube Video ID")

    args = parser.parse_args()

    video_id = get_youtube_id(args.input)

    if len(video_id) != 11:
        print("Failed to parse valid YouTube Video ID", file=sys.stderr)
        sys.exit(1)

    url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    output_path = Path.cwd() / f"{video_id}.jpg"

    try:
        with urlopen(url) as response:
            if response.status != 200:
                print(f"Thumbnail not avilable (HTTP {response.status})", file=sys.stderr)
                sys.exit(1)
            data = response.read()
            output_path.write_bytes(data)
        print(f"Downloaded: {output_path}")
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
