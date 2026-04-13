"""
Fetch a YouTube video's auto-generated transcript and save it as plain text.

Usage (from repo root):
    uv run python scripts/fetch_youtube_transcript.py <youtube_url_or_video_id> [--title "Episode Title"]

Example:
    uv run python scripts/fetch_youtube_transcript.py https://www.youtube.com/watch?v=s7ki0YR4A6w
    uv run python scripts/fetch_youtube_transcript.py s7ki0YR4A6w --title "FHIR and SQL-on-FHIR"

Output: ideas/podcast-transcripts/<video_id>.txt

Requirements:
    pip install youtube-transcript-api
    # or: uv pip install youtube-transcript-api

Notes:
    - Uses YouTube's auto-generated captions (no audio transcription).
    - Quality ~95% on clean audio but mangles technical terms
      (e.g. "CQL" -> "seekwell", "FHIR" -> "fire"). A cleanup pass is usually needed.
    - For multi-speaker shows the captions won't have speaker labels.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = REPO_ROOT / "ideas" / "podcast-transcripts"


def extract_video_id(url_or_id: str) -> str:
    """Extract the 11-character YouTube video ID from a URL or pass-through."""
    # Already a bare ID
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id

    # Common URL patterns
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)

    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def fetch_transcript(video_id: str) -> list[dict]:
    """Fetch the transcript using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print(
            "ERROR: youtube-transcript-api is not installed.\n"
            "Install it with: pip install youtube-transcript-api",
            file=sys.stderr,
        )
        sys.exit(1)

    # Try English first, then fall back to any available language
    try:
        return YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US"])
    except Exception:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        return transcripts.find_transcript(
            [t.language_code for t in transcripts]
        ).fetch()


def format_timestamp(seconds: float) -> str:
    """Format seconds as [HH:MM:SS]."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]"


def write_transcript(
    video_id: str,
    title: str | None,
    entries: list[dict],
    output_dir: Path,
) -> Path:
    """Write transcript to a plain-text file with timestamps."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_id}.txt"

    lines: list[str] = []
    if title:
        lines.append(f"# {title}")
    lines.append(f"Video ID: {video_id}")
    lines.append(f"URL: https://www.youtube.com/watch?v={video_id}")
    lines.append(f"Source: YouTube auto-generated captions")
    lines.append("")
    lines.append("---")
    lines.append("")

    for entry in entries:
        ts = format_timestamp(entry["start"])
        text = entry["text"].replace("\n", " ").strip()
        if text:
            lines.append(f"{ts} {text}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch YouTube transcript and save to ideas/podcast-transcripts/"
    )
    parser.add_argument("url", help="YouTube URL or 11-character video ID")
    parser.add_argument(
        "--title",
        default=None,
        help="Optional episode title to include in the file header",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    print(f"Fetching transcript for video: {video_id}")

    entries = fetch_transcript(video_id)
    print(f"Got {len(entries)} caption entries")

    output_path = write_transcript(video_id, args.title, entries, args.output_dir)
    print(f"Wrote transcript to: {output_path.relative_to(REPO_ROOT)}")
    print(f"Size: {output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
