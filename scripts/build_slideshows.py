#!/usr/bin/env python3
"""
Build slideshows.json from the TIMING-GUIDE and Whisper transcripts.

Maps each slide to: image path, audio time range, transcript segments.
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SLIDESHOW_DIR = Path("/Users/michael/Movies/Home Movies/Vietnam Project/Photos/Slides/slideshow")
TRANSCRIPT_DIR = Path("/Users/michael/Movies/Home Movies/Vietnam Project/Audio Cassettes/denoised recordings/transcripts")
MEDIA_SLIDES = PROJECT_ROOT / "public" / "media" / "slides"
OUTPUT = PROJECT_ROOT / "src" / "data" / "slideshows.json"


def parse_timing(line: str):
    """Parse a timing guide line like: 001-yokosuka-harbor-crane.JPG | 0:00:14 | 18s | desc"""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 4:
        return None
    filename = parts[0]
    if not filename.endswith(".JPG"):
        return None

    time_match = re.match(r"(\d+):(\d+):(\d+)", parts[1])
    if not time_match:
        return None
    start = int(time_match.group(1)) * 3600 + int(time_match.group(2)) * 60 + int(time_match.group(3))

    dur_match = re.match(r"(\d+)s", parts[2])
    duration = int(dur_match.group(1)) if dur_match else 10

    description = parts[3] if len(parts) > 3 else ""

    return {
        "filename": filename,
        "start": start,
        "duration": duration,
        "end": start + duration,
        "description": description,
    }


def _slide_prefix(filename: str) -> str | None:
    """Extract 'NNN-' prefix from a slide filename like '002-foo.JPG' -> '002-'."""
    m = re.match(r"^(\d+-)", Path(filename).stem)
    return m.group(1).lower() if m else None


def find_web_path(filename: str) -> str | None:
    """Find the web path for a slide image by matching slide number prefix."""
    prefix = _slide_prefix(filename)
    if not prefix:
        return None
    for f in MEDIA_SLIDES.iterdir():
        if f.is_file() and f.suffix == ".jpg" and f.name.startswith(prefix):
            return f"/media/slides/{f.name}"
    return None


def find_thumb_path(filename: str) -> str | None:
    """Find the thumbnail path for a slide image by matching slide number prefix."""
    prefix = _slide_prefix(filename)
    if not prefix:
        return None
    thumbs = MEDIA_SLIDES / "thumbs"
    if thumbs.exists():
        for f in thumbs.iterdir():
            if f.is_file() and f.name.startswith(prefix):
                return f"/media/slides/thumbs/{f.name}"
    return None


def get_whisper_segments(transcript_path: Path, start: float, end: float) -> list[dict]:
    """Get Whisper transcript segments that fall within a time range."""
    with open(transcript_path) as f:
        data = json.load(f)

    segments = []
    for seg in data.get("segments", []):
        seg_start = seg["start"]
        seg_end = seg["end"]
        # Include segment if it overlaps with our range
        if seg_start < end and seg_end > start:
            segments.append({
                "start": seg_start,
                "end": seg_end,
                "text": seg["text"].strip(),
            })
    return segments


def build_slideshow(name: str, slide_dir: str, audio_web_path: str, transcript_json: str):
    """Build a single slideshow definition."""
    timing_file = SLIDESHOW_DIR / "TIMING-GUIDE.txt"
    transcript_path = TRANSCRIPT_DIR / transcript_json

    with open(timing_file) as f:
        timing_text = f.read()

    # Find the section for this slideshow
    slides = []
    in_section = False
    for line in timing_text.splitlines():
        # Detect section headers
        if f"TAPE 3 - JAPAN" in line and name == "japan":
            in_section = True
            continue
        elif f"TAPE 3a - VIETNAM" in line and name == "vietnam":
            in_section = True
            continue
        elif line.startswith("====") and in_section and slides:
            break

        if not in_section:
            continue

        parsed = parse_timing(line)
        if parsed:
            web_path = find_web_path(parsed["filename"])
            thumb_path = find_thumb_path(parsed["filename"])
            if web_path:
                whisper_segs = get_whisper_segments(
                    transcript_path, parsed["start"], parsed["end"]
                )
                slides.append({
                    "src": web_path,
                    "thumb": thumb_path or web_path,
                    "start": parsed["start"],
                    "end": parsed["end"],
                    "description": parsed["description"],
                    "transcript": whisper_segs,
                })
            else:
                print(f"  WARNING: No web image found for {parsed['filename']}")

    return {
        "id": name,
        "title": "Japan Shore Leave" if name == "japan" else "Vietnam — Da Nang & SAR Operations",
        "subtitle": "Tape 3, Side 2 — Yokosuka, Tokyo, Kamakura" if name == "japan" else "Tape 3a, Side 2 — Da Nang Harbor, USO Show, SAR Rescue",
        "date": "1968-05-16" if name == "japan" else "1968-05-20",
        "date_label": "Recorded 16 May 1968" if name == "japan" else "Recorded 20 May 1968",
        "audio": audio_web_path,
        "slides": slides,
    }


def main():
    slideshows = []

    japan = build_slideshow(
        "japan",
        "tape3-japan",
        "/media/audio/tape-3-side-2-slide-narration-for-slideshow-tokyo.mp3",
        "Tape 3 - Side 2 - Slide Narration for Slideshow - Tokyo .json",
    )
    print(f"Japan: {len(japan['slides'])} slides")
    slideshows.append(japan)

    vietnam = build_slideshow(
        "vietnam",
        "tape3a-vietnam",
        "/media/audio/tape-3a-side-2-mike-ducy-slide-narration.mp3",
        "Tape 3a - Side 2 - Mike Ducy Slide Narration.json",
    )
    print(f"Vietnam: {len(vietnam['slides'])} slides")
    slideshows.append(vietnam)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(slideshows, f, indent=2)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\nWritten to {OUTPUT}")
    print(f"File size: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
