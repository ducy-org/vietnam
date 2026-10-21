#!/usr/bin/env python3
"""Rebuild media-manifest.json by scanning public/media/ on disk."""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = PROJECT_ROOT / "public" / "media"
MANIFEST_OUT = PROJECT_ROOT / "src" / "data" / "media-manifest.json"


# Known date refinements: partial month → specific day based on timeline research
DATE_OVERRIDES = {
    "196802-jouett-visits-the-philippines": "1968-02-07",
    "196802-all-hands-uss-wainwright": "1968-02-17",
}


def extract_date(filename: str) -> str | None:
    stem = Path(filename).stem
    for prefix, date in DATE_OVERRIDES.items():
        if stem.startswith(prefix):
            return date
    m = re.match(r"(\d{8})", filename)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    m = re.match(r"(\d{6})", filename)
    if m:
        d = m.group(1)
        yr, mo = d[:4], d[4:6]
        if mo == "00":
            return f"{yr}"
        return f"{yr}-{mo}"
    return None


def extract_description(filename: str) -> str:
    stem = Path(filename).stem
    desc = re.sub(r"^\d{6,8}-?", "", stem)
    desc = desc.replace("-", " ").strip()
    return desc.title() if desc else stem


def scan_dir(base_dir: Path, category: str, subcategory: str | None = None) -> list[dict]:
    entries = []
    if not base_dir.exists():
        return entries
    for f in sorted(base_dir.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        entry = {
            "filename": f.name,
            "web_path": "/" + str(f.relative_to(PROJECT_ROOT / "public")),
            "date": extract_date(f.name),
            "description": extract_description(f.name),
            "category": category,
        }
        if subcategory:
            entry["subcategory"] = subcategory
        entries.append(entry)
    return entries


def main():
    manifest = {}

    manifest["photos"] = scan_dir(MEDIA_DIR / "photos", "photos")

    letters = []
    for sub in sorted((MEDIA_DIR / "letters").iterdir()) if (MEDIA_DIR / "letters").exists() else []:
        if sub.is_dir():
            letters.extend(scan_dir(sub, "letters", sub.name))
    manifest["letters"] = letters

    documents = []
    for sub in sorted((MEDIA_DIR / "documents").iterdir()) if (MEDIA_DIR / "documents").exists() else []:
        if sub.is_dir():
            documents.extend(scan_dir(sub, "documents", sub.name))
    manifest["documents"] = documents

    manifest["slides"] = scan_dir(MEDIA_DIR / "slides", "slides")
    manifest["video"] = scan_dir(MEDIA_DIR / "video", "video")
    manifest["audio"] = scan_dir(MEDIA_DIR / "audio", "audio")
    manifest["logbook"] = scan_dir(MEDIA_DIR / "logbook", "logbook")

    # Summary
    for k, v in manifest.items():
        dated = sum(1 for x in v if x.get("date"))
        print(f"  {k}: {len(v)} files ({dated} with dates)")

    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_OUT, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest written to {MANIFEST_OUT}")


if __name__ == "__main__":
    main()
