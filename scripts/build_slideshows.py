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


def _web_name(filename: str) -> str:
    """Lowercased .jpg name, as copy_media.py's web_safe_name() writes slide files."""
    return Path(filename).stem.lower() + ".jpg"


def _find_slide(directory: Path, filename: str, folder: str) -> str | None:
    """Find a copied slide in directory, considering only files from this show's source folder.

    All shows flatten into public/media/slides and their numbers overlap (Bill's 001-040,
    Japan's 001-055), so a bare 'NNN-' prefix match could pick another show's slide.
    Tries the exact name first, then the 'NNN-' prefix (older guides list draft names).
    """
    src_dir = SLIDESHOW_DIR / folder
    if not directory.exists() or not src_dir.exists():
        return None
    candidates = [
        _web_name(f.name) for f in sorted(src_dir.iterdir())
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg")
    ]
    candidates = [c for c in candidates if (directory / c).is_file()]
    name = _web_name(filename)
    if name in candidates:
        return name
    prefix = _slide_prefix(filename)
    if not prefix:
        return None
    for c in candidates:
        if c.startswith(prefix):
            return c
    return None


def find_web_path(filename: str, folder: str) -> str | None:
    """Find the web path for a slide image."""
    name = _find_slide(MEDIA_SLIDES, filename, folder)
    return f"/media/slides/{name}" if name else None


def find_thumb_path(filename: str, folder: str) -> str | None:
    """Find the thumbnail path for a slide image."""
    name = _find_slide(MEDIA_SLIDES / "thumbs", filename, folder)
    return f"/media/slides/thumbs/{name}" if name else None


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


# Each show is a section of TIMING-GUIDE.txt. The page lists shows in date order.
SHOWS = [
    {
        "id": "japan",
        "section": "TAPE 3 - JAPAN",
        "folder": "tape3-japan",
        "title": "Japan Shore Leave",
        "subtitle": "Tape 3, Side 2 — Yokosuka, Tokyo, Kamakura",
        "date": "1968-05-16",
        "date_label": "Recorded 16 May 1968",
        "audio": "/media/audio/tape-3-side-2-slide-narration-for-slideshow-tokyo.mp3",
        "transcript": "Tape 3 - Side 2 - Slide Narration for Slideshow - Tokyo .json",
    },
    {
        "id": "vietnam",
        "section": "TAPE 3a - VIETNAM",
        "folder": "tape3a-vietnam",
        "title": "Vietnam — Da Nang & SAR Operations",
        "subtitle": "Tape 3a, Side 2 — Da Nang Harbor, USO Show, SAR Rescue",
        "date": "1968-05-20",
        "date_label": "Recorded 20 May 1968",
        "audio": "/media/audio/tape-3a-side-2-mike-ducy-slide-narration.mp3",
        "transcript": "Tape 3a - Side 2 - Mike Ducy Slide Narration.json",
    },
    {
        "id": "bill",
        "section": "BILL - DA NANG",
        "folder": "bill-danang",
        "title": "Bill's Slides: Da Nang, February 1968",
        "subtitle": "Narrated by PFC Bill Ducy, USMC — sandbagging after the rocket attack, a USO show, bunker watch",
        "date": "1968-02-26",
        "date_label": "Recorded 26 February 1968",
        "audio": "/media/audio/19680226-bill-ducy-to-mike-ducy-to-john-and-georgia-mae-pritchett-to-home.mp3",
        "transcript": "19680226 - Bill Ducy to Mike Ducy to John and Georgia Mae Pritchett to Home.json",
    },
]


def build_slideshow(show: dict):
    """Build a single slideshow definition."""
    timing_file = SLIDESHOW_DIR / "TIMING-GUIDE.txt"
    transcript_path = TRANSCRIPT_DIR / show["transcript"]

    with open(timing_file) as f:
        timing_text = f.read()

    # Find the section for this slideshow
    slides = []
    in_section = False
    parsed_any = False
    for line in timing_text.splitlines():
        if show["section"] in line:
            in_section = True
            continue
        elif line.startswith("====") and in_section and parsed_any:
            break

        if not in_section:
            continue

        parsed = parse_timing(line)
        if parsed:
            parsed_any = True
            web_path = find_web_path(parsed["filename"], show["folder"])
            thumb_path = find_thumb_path(parsed["filename"], show["folder"])
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
        "id": show["id"],
        "title": show["title"],
        "subtitle": show["subtitle"],
        "date": show["date"],
        "date_label": show["date_label"],
        "audio": show["audio"],
        "slides": slides,
    }


def main():
    slideshows = []

    for show in sorted(SHOWS, key=lambda s: s["date"]):
        built = build_slideshow(show)
        print(f"{show['id']}: {len(built['slides'])} slides")
        if not built["slides"]:
            print(f"  SKIPPED {show['id']}: no slides in public/media/slides yet "
                  f"(run copy_media.py --category slides)")
            continue
        slideshows.append(built)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(slideshows, f, indent=2)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\nWritten to {OUTPUT}")
    print(f"File size: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
