#!/usr/bin/env python3
"""Update deployment-timeline.md logbook entries with corrected transcription text.

Reads logbook-transcripts.json (parsed from the Claude vision transcription)
and replaces [Logbook]-tagged table entries in deployment-timeline.md with
the corrected text.
"""

import json
import re
from pathlib import Path

TRANSCRIPTS = Path("/Users/michael/dev/ducy-vietnam/src/data/logbook-transcripts.json")
TIMELINE = Path("/Users/michael/Movies/Home Movies/Vietnam Project/Documentation/Mike Ducy Log Book/deployment-timeline.md")

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_row_date(cell):
    """Parse 'Tue 16 Jan' or '***Tue 16 Jan***' into ISO date."""
    cell = re.sub(r'\*+', '', cell).strip()
    m = re.match(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+(\w{3})', cell)
    if not m:
        return None
    day = int(m.group(1))
    month = MONTH_MAP.get(m.group(2))
    if not month:
        return None
    return f"1968-{month:02d}-{day:02d}"


def format_entry(raw_text):
    """Convert multi-line logbook transcription into a single-line timeline entry."""
    lines = raw_text.strip().split('\n')
    parts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Convert time stamps: "1440- Arrive..." → "1440 — Arrive..."
        line = re.sub(r'^(\d{3,4})\s*-\s*', r'\1 — ', line)
        # Convert time ranges: "1600-1800 -" → "1600–1800 —"
        line = re.sub(r'^(\d{3,4})\s*-\s*(\d{3,4})\s*-\s*', r'\1–\2 — ', line)
        parts.append(line)

    result = '. '.join(parts)
    # Clean up join artifacts
    result = re.sub(r'\.\s*—', ' —', result)  # ". —" → " —"
    result = re.sub(r'\.\.\s', '. ', result)   # ".. " → ". "
    result = re.sub(r'-\.\s', '- ', result)    # "-. " → "- " (hyphenated word split)
    result = re.sub(r',\.\s', ', ', result)     # ",. " → ", "
    result = re.sub(r'\.\s+\.', '.', result)   # ". ." → "."
    return result.rstrip('.')


def main():
    transcripts = json.loads(TRANSCRIPTS.read_text())
    print(f"Loaded {len(transcripts)} logbook transcripts")

    lines = TIMELINE.read_text().splitlines()
    updated_count = 0
    unchanged_count = 0
    diff_lines = []

    new_lines = []
    for line in lines:
        stripped = line.strip()

        # Only process table data rows with [Logbook]
        if not stripped.startswith('|') or '[Logbook]' not in stripped:
            new_lines.append(line)
            continue

        cells = stripped.split('|')
        if len(cells) < 5:  # |date|day|entry|
            new_lines.append(line)
            continue

        date_cell = cells[1].strip()
        date = parse_row_date(date_cell)
        if not date or date not in transcripts:
            new_lines.append(line)
            unchanged_count += 1
            continue

        # Get the corrected entry text
        new_entry = format_entry(transcripts[date]["text"])

        # Preserve bold/italic wrapping if the row is significant (***...*** style)
        old_entry = cells[3].strip()
        is_significant = date_cell.startswith('***')

        if is_significant:
            entry_text = f"***{new_entry}*** [Logbook]"
        else:
            entry_text = f"{new_entry}. [Logbook]"

        # Check if entry also has non-logbook sources mixed in
        # If so, we only replace the logbook portion
        non_logbook = re.findall(r'\[(?:Letter|Familygram|HC-7|Stars & Stripes|Jouett Jargon|Video|Photo|COR|Bill|Given|Norris|San Diego|Plan|Evening)[^\]]*\]', old_entry)
        if non_logbook:
            # Entry has mixed sources — preserve those parts
            # Find the logbook portion and replace just that
            # This is tricky, so just prepend the new logbook text
            other_text = old_entry
            # Remove old logbook-only text (before first non-logbook source tag)
            # Actually, these mixed entries are complex — skip for now and flag
            diff_lines.append(f"MIXED: {date} — has {non_logbook}, skipping auto-update")
            new_lines.append(line)
            unchanged_count += 1
            continue

        # Reconstruct the row
        cells[3] = f" {entry_text} "
        new_line = '|'.join(cells)
        new_lines.append(new_line)

        # Track changes
        old_clean = re.sub(r'\*+', '', old_entry).strip()
        new_clean = re.sub(r'\*+', '', entry_text).strip()
        if old_clean != new_clean:
            updated_count += 1
            diff_lines.append(f"  {date}:")
            diff_lines.append(f"    OLD: {old_clean[:100]}")
            diff_lines.append(f"    NEW: {new_clean[:100]}")
        else:
            unchanged_count += 1

    # Write updated timeline
    TIMELINE.write_text('\n'.join(new_lines) + '\n')

    print(f"\nUpdated {updated_count} entries")
    print(f"Unchanged: {unchanged_count}")
    print(f"\nChanges:")
    for d in diff_lines[:60]:
        print(d)
    if len(diff_lines) > 60:
        print(f"  ... and {len(diff_lines) - 60} more")


if __name__ == '__main__':
    main()
