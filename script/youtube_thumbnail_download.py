#!/usr/bin/env python3
"""YouTube 썸네일을 다운로드받는다"""

import re
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import urlopen

from library.text_file import add_file_error_note, print_exception


class YoutubeThumbnailArgs(Namespace):
    input: str


def parse_args() -> YoutubeThumbnailArgs:
    parser = ArgumentParser(description="Download YouTube max resolution thumbnail image.")
    parser.add_argument("input", help="YouTube URL or YouTube Video ID")
    return parser.parse_args(namespace=YoutubeThumbnailArgs())


def main() -> None:
    args = parse_args()
    raw_input = args.input

    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", raw_input):
        video_id = raw_input
    else:
        video_id = ""
        try:
            # 공유 URL에 섞이는 추적/중첩 URL 요소를 단순화한 뒤 v 파라미터를 우선 확인
            normalized_url = re.sub(
                r"(attribution_link|uploademail|youtube-nocookie)",
                "x",
                raw_input,
                flags=re.IGNORECASE,
            )
            parsed = urlparse(normalized_url)
            query = parse_qs(parsed.query)
            embed = query.get("url")
            if embed:
                parsed = urlparse(embed[0])
                query = parse_qs(parsed.query)

            values = query.get("v")
            if values:
                video_id = values[0]
            else:
                # 일반적이지 않은 공유 URL은 불필요한 query를 지운 뒤 11자 ID 패턴을 마지막으로 찾음
                remove_params = {"a", "app", "list", "feature", "rel", "si"}
                filtered_query = {key: value for key, value in query.items() if key not in remove_params}
                rebuilt_url = urlunparse(parsed._replace(query=urlencode(filtered_query, doseq=True))).replace(
                    "%3D", "="
                )
                match = re.search(r"[a-zA-Z0-9_-]{11}", rebuilt_url)
                if match:
                    video_id = match.group(0)
        except ValueError:
            video_id = ""

    if len(video_id) != 11:
        print("Failed to parse valid YouTube Video ID", file=sys.stderr)
        sys.exit(1)

    url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    output_path = Path.cwd() / f"{video_id}.jpg"

    try:
        with urlopen(url) as response:
            if response.status != 200:
                print(f"Thumbnail not available (HTTP {response.status})", file=sys.stderr)
                sys.exit(1)
            output_path.write_bytes(response.read())
        print(f"Downloaded: {output_path}")
    except OSError as error:
        add_file_error_note(error, output_path, "write")
        print_exception(error)
        sys.exit(1)


if __name__ == "__main__":
    main()
