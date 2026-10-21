#!/usr/bin/env python3
"""Parse logbook-transcription.txt into logbook-transcripts.json keyed by ISO date.

Uses HEIC filenames from the logbook directory for date mapping (YYYYMMDD - IMG_XXXX).
"""

import json
import re
from pathlib import Path

LOGBOOK_DIR = Path("/Users/michael/Movies/Home Movies/Vietnam Project/Documentation/Mike Ducy Log Book")
TRANSCRIPTION = LOGBOOK_DIR / "logbook-transcription.txt"
OUTPUT = Path("/Users/michael/dev/ducy-vietnam/src/data/logbook-transcripts.json")


def build_img_to_date():
    """Map IMG_XXXX → ISO date from HEIC filenames."""
    mapping = {}
    for f in LOGBOOK_DIR.glob("*.HEIC"):
        m = re.match(r'(\d{8}) - (IMG_\d+)', f.name)
        if m:
            raw_date = m.group(1)
            img_id = m.group(2)
            iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            mapping[img_id] = iso
    return mapping


def normalize_text(lines):
    """Join continuation lines (indented) and clean up."""
    result = []
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            continue
        if stripped.startswith('       ') or stripped.startswith('\t'):
            if result:
                result[-1] += ' ' + stripped.strip()
            else:
                result.append(stripped.strip())
        else:
            result.append(stripped.strip())
    return '\n'.join(result)


def is_date_line(line):
    """Check if a line is a date header (e.g., 'Tues. 16 Jan, 1968')."""
    return bool(re.match(
        r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\.?\s+\d{1,2}[,.]?\s+\w+',
        line.strip(), re.IGNORECASE
    ))


def main():
    img_to_date = build_img_to_date()
    print(f"Built date mapping for {len(img_to_date)} HEIC files")

    text = TRANSCRIPTION.read_text()
    pages = re.split(r'^=== (IMG_\d+) ===$', text, flags=re.MULTILINE)

    by_date = {}
    matched = 0
    unmatched = []

    for i in range(1, len(pages), 2):
        img_id = pages[i].strip()
        content = pages[i + 1].strip() if i + 1 < len(pages) else ""
        if not content:
            continue

        date = img_to_date.get(img_id)
        if not date:
            unmatched.append(img_id)
            continue

        # Skip the date header line, keep the rest as logbook content
        body_lines = []
        for line in content.split('\n'):
            if not body_lines and is_date_line(line):
                continue
            body_lines.append(line)

        body = normalize_text(body_lines)
        if not body:
            continue

        matched += 1

        if date not in by_date:
            by_date[date] = {
                "date": date,
                "pages": [],
                "text": "",
            }

        by_date[date]["pages"].append(img_id)
        if by_date[date]["text"]:
            by_date[date]["text"] += '\n' + body
        else:
            by_date[date]["text"] = body

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(by_date, indent=2, ensure_ascii=False))

    print(f"Parsed {matched} pages into {len(by_date)} dates")
    if unmatched:
        print(f"WARNING: {len(unmatched)} pages had no HEIC match: {', '.join(unmatched)}")
    print(f"Output: {OUTPUT}")

    for date in sorted(by_date.keys())[:5]:
        entry = by_date[date]
        preview = entry["text"][:80].replace('\n', ' | ')
        print(f"  {date}: {preview}...")


if __name__ == '__main__':
    main()
