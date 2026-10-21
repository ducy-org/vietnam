#!/usr/bin/env python3
"""Build unified transcripts.json from all transcript sources."""

import json
import os
import re
import sys
from pathlib import Path

PROJECT = Path("/Users/michael/Movies/Home Movies/Vietnam Project")
OUT = Path("/Users/michael/dev/ducy-vietnam/src/data/transcripts.json")

LETTER_TRANSCRIPTS = Path("/Users/michael/dev/ducy-vietnam/src/data/letter-transcripts.json")

FAMILYGRAM_DIR = PROJECT / "Documentation/DLG-29 Family Grams/transcripts"
CRUISEBOOK_DIR = PROJECT / "Cruise Book - 1968/transcripts"
MANIFEST_PATH = Path("/Users/michael/dev/ducy-vietnam/src/data/media-manifest.json")
AUDIO_DIR = PROJECT / "Audio Cassettes/denoised recordings/transcripts"
MISC_DIR = PROJECT / "Documentation/Misc/transcripts"
VIGILANCE_FILE = PROJECT / "Documentation/DLG-29 Ship Publications/transcripts/196808 - Vigilance Magazine.txt"

DOC_TRANSCRIPT_DIRS = [
    (PROJECT / "Documentation/Misc/transcripts", "document", "misc"),
    (PROJECT / "Documentation/DLG-29 Ship Publications/transcripts", "document", "ship-pubs"),
    (PROJECT / "Documentation/Newspaper Clippings/transcripts", "document", "newspaper"),
    (PROJECT / "Documentation/Training & Service Records/transcripts", "document", "service-records"),
    (PROJECT / "Documentation/Plans of the Day/transcripts", "document", "plans-of-the-day"),
]

# Files to skip in document transcript processing
SKIP_DOC_TRANSCRIPTS = {
    "Ducy Family Research.txt",
    "196808 - Vigilance Magazine.txt",  # handled separately as per-page split
}

# Audio files to skip (slide narrations — deferred for special feature)
SKIP_AUDIO = {
    "Tape 3 - Side 2 - Slide Narration for Slideshow - Tokyo ",
    "Tape 3a - Side 2 - Mike Ducy Slide Narration",
}


# Map audio filenames to who/label info
def parse_audio_people(filename):
    """Extract who recorded and label from audio filename."""
    name = filename.replace(".json", "").replace(".txt", "")

    people_map = {
        "Dan, Dorothea, David Ducy": ("family", "Dan, Dorothea & David Ducy"),
        "Dorothea Dan David Ducy": ("family", "Dorothea, Dan & David Ducy"),
        "Dorothea David Dan Ducy": ("family", "Dorothea, David & Dan Ducy"),
        "Dorothea David Daniel Ducy": ("family", "Dorothea, David & Daniel Ducy"),
        "Dorothea Ducy": ("family", "Dorothea Ducy"),
        "David Dan Dorothea Ducy": ("family", "David, Dan & Dorothea Ducy"),
        "David Ducy": ("family", "David Ducy"),
        "Mike Ducy Bill Ducy": ("mike", "Mike & Bill Ducy"),
        "Mike Ducy": ("mike", "Mike Ducy"),
    }

    for pattern, (who, label) in people_map.items():
        if pattern in name:
            return who, label
    return "unknown", name


def parse_audio_date(filename):
    """Extract date from audio filename."""
    date_patterns = [
        (r"April 3rd 1968", "1968-04-03"),
        (r"April 14th to 16th 1968", "1968-04-14"),
        (r"April 16th 1968", "1968-04-16"),
        (r"May 16 1968", "1968-05-16"),
        (r"May 20th 1968", "1968-05-20"),
        (r"May 25th 1968", "1968-05-25"),
        (r"May 31st 1968", "1968-05-31"),
        (r"June 1st 1968", "1968-06-01"),
        (r"June 8th 1968", "1968-06-08"),
        (r"June 14th 1968", "1968-06-14"),
        (r"June 22 1968", "1968-06-22"),
        (r"June 23 1968", "1968-06-23"),
        (r"July 11 1968", "1968-07-11"),
        (r"July 13th 1968", "1968-07-13"),
        (r"July 28th 1968", "1968-07-28"),
        (r"July 31st 1968", "1968-07-31"),
        (r"August 20th 1968", "1968-08-20"),
        (r"August 28th 1968", "1968-08-28"),
        (r"Aug 28th 1968", "1968-08-28"),
    ]
    for pattern, date in date_patterns:
        if pattern in filename:
            return date
    m = re.match(r"(\d{8})", filename)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return None


def parse_tape_label(filename):
    """Extract tape number from filename."""
    m = re.match(r"(Tape \d+a?)\s*-\s*(Side \d+)?\s*-?\s*", filename)
    if m:
        tape = m.group(1)
        side = m.group(2) or ""
        return f"{tape}{', ' + side if side else ''}"
    return filename


def build_familygrams():
    """Build familygram transcripts keyed by date."""
    entries = {}
    for f in sorted(FAMILYGRAM_DIR.glob("*.txt")):
        datestr = f.name[:8]
        if datestr == "19680600":
            iso = "1968-06-01"  # approximate — no exact day
        else:
            iso = f"{datestr[:4]}-{datestr[4:6]}-{datestr[6:8]}"

        text = f.read_text(encoding="utf-8").strip()

        entry = {
            "date": iso,
            "type": "familygram",
            "who": "hayes",
            "label": "Familygram — Capt. Robert S. Hayes, CO",
            "description": f"USS Jouett (DLG-29) Familygram, {iso}",
            "attribution": "USS Jouett (DLG-29) Familygram, Capt. Robert S. Hayes, Commanding Officer — Ducy Family Archives",
            "text": text,
        }

        if iso not in entries:
            entries[iso] = []
        entries[iso].append(entry)

    return entries


def build_audio_transcripts():
    """Build audio transcripts with timestamped segments."""
    entries = {}

    for f in sorted(AUDIO_DIR.glob("*.json")):
        stem = f.stem
        if stem in SKIP_AUDIO:
            continue

        date = parse_audio_date(stem)
        if not date:
            print(f"WARNING: Could not parse date from {f.name}", file=sys.stderr)
            continue

        who, people_label = parse_audio_people(stem)
        tape_label = parse_tape_label(stem)

        with open(f) as fh:
            data = json.load(fh)

        segments = []
        for seg in data.get("segments", []):
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
            })

        full_text = data.get("text", "").strip()

        location = "Decatur, IL" if who == "family" else "USS Jouett (DLG-29)"

        entry = {
            "date": date,
            "type": "audio",
            "who": who,
            "label": f"{tape_label} — {people_label}",
            "description": f"Recorded {date}, {location}",
            "attribution": f"Audio cassette recording, {tape_label} — {people_label}. Transcribed by OpenAI Whisper. Ducy Family Archives",
            "tape": tape_label,
            "match_key": stem,
            "segments": segments,
            "text": full_text,
        }

        if date not in entries:
            entries[date] = []
        entries[date].append(entry)

    return entries


def extract_doc_date(filename):
    """Extract date from document transcript filename."""
    m = re.match(r"(\d{8})", filename)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    m = re.match(r"(\d{6})", filename)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-01"
    return None


def extract_doc_label(filename):
    """Extract human-readable label from transcript filename."""
    stem = Path(filename).stem
    label = re.sub(r"^\d{6,8}\s*-\s*", "", stem)
    return label.strip() if label else stem


def build_doc_transcripts():
    """Build document transcripts from all transcript directories."""
    entries = {}

    for src_dir, doc_type, subcategory in DOC_TRANSCRIPT_DIRS:
        if not src_dir.exists():
            continue

        for f in sorted(src_dir.glob("*.txt")):
            if f.name in SKIP_DOC_TRANSCRIPTS:
                continue

            text = f.read_text(encoding="utf-8").strip()
            if not text:
                continue

            date = extract_doc_date(f.name)
            if not date:
                continue

            # Skip dates with "00" day — can't place on timeline
            if date.endswith("-00"):
                continue

            label = extract_doc_label(f.name)
            who = "mike" if "mike" in f.name.lower() or "ducy" in f.name.lower() else "ship"

            entry = {
                "date": date,
                "type": doc_type,
                "who": who,
                "label": label,
                "description": f"{subcategory.replace('-', ' ').title()}",
                "attribution": f"{label} — Ducy Family Archives",
                "text": text,
            }

            if date not in entries:
                entries[date] = []
            entries[date].append(entry)

    return entries


def build_cruisebook_transcripts():
    """Build cruise book transcripts keyed by date from manifest."""
    entries = {}

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    cb_items = manifest.get("cruisebook", [])
    date_by_desc = {}
    for item in cb_items:
        desc = item.get("description", "")
        date = item.get("date")
        if desc and date:
            date_by_desc[desc] = date

    for f in sorted(CRUISEBOOK_DIR.glob("*.txt")):
        text = f.read_text(encoding="utf-8").strip()
        if not text:
            continue

        stem = f.stem
        desc = stem
        if stem == "Inside Cover":
            desc = "Pg0 Inside Cover"
        elif stem == "Inside Back":
            desc = "pg201 Inside Back"

        date = date_by_desc.get(desc)
        if not date:
            for manifest_desc, d in date_by_desc.items():
                if stem.lower() in manifest_desc.lower() or manifest_desc.lower() in stem.lower():
                    date = d
                    break
        if not date:
            continue

        page_label = stem.replace("pg", "Pages ").replace("-", "–")
        if stem.startswith("pg"):
            page_label = f"Pages {stem[2:]}" if "-" in stem else f"Page {stem[2:]}"

        entry = {
            "date": date,
            "type": "cruisebook",
            "who": "ship",
            "label": f"Cruise Book — {page_label}",
            "description": "USS Jouett (DLG-29) 1968 Cruise Book",
            "attribution": "USS Jouett (DLG-29) 1968 WestPac Cruise Book — Ducy Family Archives",
            "text": text,
        }

        if date not in entries:
            entries[date] = []
        entries[date].append(entry)

    return entries


def build_vigilance_transcripts():
    """Build Vigilance magazine transcripts, one entry per page.

    Dates come from the manifest (which reads from renamed source filenames).
    """
    entries = {}

    if not VIGILANCE_FILE.exists():
        print("WARNING: Vigilance transcript file not found", file=sys.stderr)
        return entries

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    vig_items = []
    docs = manifest.get("documents", {})
    if isinstance(docs, dict):
        vig_items = docs.get("vigilance", [])

    # Map page number to date from manifest descriptions
    page_date = {}
    for item in vig_items:
        desc = item.get("description", "")
        date = item.get("date")
        if not date or len(date) < 10:
            continue
        # Extract page reference: "Pg 16", "Cover", etc.
        m = re.search(r"Pg\s*(\d+)", desc, re.IGNORECASE)
        if m:
            page_date[m.group(1)] = date
        if "Cover" in desc:
            page_date["Cover"] = date

    raw = VIGILANCE_FILE.read_text(encoding="utf-8")
    sections = re.split(r"={40,}\n(COVER|PAGE \d+)\n={40,}", raw)

    i = 1
    while i < len(sections):
        page_header = sections[i].strip()
        page_text = sections[i + 1].strip() if i + 1 < len(sections) else ""
        i += 2

        if not page_text:
            continue

        if page_header == "COVER":
            page_key = "Cover"
            page_label = "Cover"
        else:
            page_key = page_header.replace("PAGE ", "")
            page_label = f"Page {page_key}"

        date = page_date.get(page_key, "1968-07-18")

        entry = {
            "date": date,
            "type": "vigilance",
            "who": "ship",
            "label": f"Vigilance — {page_label}",
            "description": "Cruiser-Destroyer Group, August 1968",
            "attribution": "Vigilance, Cruiser-Destroyer Group publication, August 1968 — Ducy Family Archives",
            "text": page_text,
        }

        if date not in entries:
            entries[date] = []
        entries[date].append(entry)

    return entries


def main():
    # Start with existing letter transcripts
    with open(LETTER_TRANSCRIPTS) as f:
        result = json.load(f)

    # Add type and attribution fields to existing letters
    for date, items in result.items():
        for item in items:
            if "type" not in item:
                item["type"] = "letter"
            if "attribution" not in item:
                who = item.get("who", "")
                if who == "mike":
                    item["attribution"] = "Letter, Mike Ducy — Ducy Family Archives"
                elif who == "bill":
                    item["attribution"] = "Letter, Bill Ducy — Ducy Family Archives"
                elif who == "given":
                    item["attribution"] = "Letter, W.F. Given FTG-3 — Ducy Family Archives"
                elif who == "norris":
                    item["attribution"] = "Letter, A.R. Norris FTG-3 — Ducy Family Archives"
                else:
                    item["attribution"] = "Ducy Family Archives"

    letter_count = sum(len(v) for v in result.values())
    print(f"Letters: {letter_count} transcripts across {len(result)} dates")

    # Add familygrams
    familygrams = build_familygrams()
    fg_count = 0
    for date, items in familygrams.items():
        if date not in result:
            result[date] = []
        result[date].extend(items)
        fg_count += len(items)
    print(f"Familygrams: {fg_count} transcripts across {len(familygrams)} dates")

    # Add audio transcripts
    audio = build_audio_transcripts()
    audio_count = 0
    for date, items in audio.items():
        if date not in result:
            result[date] = []
        result[date].extend(items)
        audio_count += len(items)
    print(f"Audio: {audio_count} transcripts across {len(audio)} dates")

    # Add document transcripts (all subcategories)
    docs = build_doc_transcripts()
    doc_count = 0
    for date, items in docs.items():
        if date not in result:
            result[date] = []
        result[date].extend(items)
        doc_count += len(items)
    print(f"Documents: {doc_count} transcripts across {len(docs)} dates")

    # Add cruise book transcripts
    cruisebook = build_cruisebook_transcripts()
    cb_count = 0
    for date, items in cruisebook.items():
        if date not in result:
            result[date] = []
        result[date].extend(items)
        cb_count += len(items)
    print(f"Cruise Book: {cb_count} transcripts across {len(cruisebook)} dates")

    # Add Vigilance transcripts
    vigilance = build_vigilance_transcripts()
    vig_count = 0
    for date, items in vigilance.items():
        if date not in result:
            result[date] = []
        result[date].extend(items)
        vig_count += len(items)
    print(f"Vigilance: {vig_count} transcripts across {len(vigilance)} dates")

    # Sort by date
    result = dict(sorted(result.items()))

    total = sum(len(v) for v in result.values())
    print(f"\nTotal: {total} transcripts across {len(result)} dates")

    with open(OUT, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Written to {OUT}")
    print(f"File size: {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
