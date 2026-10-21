#!/usr/bin/env python3
"""Generate Astro content collection .md files from timeline.json."""

import json
import sys
from pathlib import Path

DATA = Path("/Users/michael/dev/ducy-vietnam/src/data/timeline.json")
CONTENT_DIR = Path("/Users/michael/dev/ducy-vietnam/src/content/days")


def escape_yaml(text):
    """Escape text for YAML string values."""
    if not text:
        return '""'
    text = text.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{text}"'


def generate_day_file(day, month_title):
    """Generate a .md file for a single day."""
    date = day['date']
    day_num = day.get('day_number')
    location = day.get('location', '')
    significant = day.get('significant', False)
    entries = day.get('entries', [])
    quotes = day.get('quotes', [])
    photos = day.get('photos', [])
    documents = day.get('documents', [])
    sources = day.get('sources', [])

    lines = ['---']
    lines.append(f'date: "{date}"')
    if day_num:
        lines.append(f'dayNumber: {day_num}')
    if location:
        lines.append(f'location: {escape_yaml(location)}')
    lines.append(f'significant: {str(significant).lower()}')
    lines.append(f'month: {escape_yaml(month_title)}')

    if sources:
        lines.append('sources:')
        for s in sources:
            lines.append(f'  - {escape_yaml(s)}')

    if photos:
        total_photos = sum(p.get('count', 1) for p in photos)
        lines.append(f'photoCount: {total_photos}')

    if documents:
        lines.append(f'documentCount: {len(documents)}')

    lines.append('---')
    lines.append('')

    # Logbook entries
    if entries:
        lines.append('## Logbook')
        lines.append('')
        for entry in entries:
            lines.append(entry)
            lines.append('')

    # Quotes (letters, familygrams, context)
    if quotes:
        lines.append('## Sources')
        lines.append('')
        for quote in quotes:
            lines.append(f'> {quote}')
            lines.append('')

    # Photos
    if photos:
        lines.append('## Photos')
        lines.append('')
        for photo in photos:
            desc = photo.get('description', '')
            count = photo.get('count', 1)
            lines.append(f'- {desc} ({count} photo{"s" if count != 1 else ""})')
            lines.append('')

    # Documents
    if documents:
        lines.append('## Documents')
        lines.append('')
        for doc in documents:
            lines.append(f'- {doc.get("description", "")}')
            lines.append('')

    return '\n'.join(lines)


def main():
    if not DATA.exists():
        print(f"ERROR: {DATA} not found. Run parse_timeline.py first.")
        sys.exit(1)

    data = json.load(DATA.open())
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    # Clean existing files
    for f in CONTENT_DIR.glob('*.md'):
        f.unlink()

    count = 0
    for month in data['months']:
        month_title = month['title']
        for day in month['days']:
            content = generate_day_file(day, month_title)
            filepath = CONTENT_DIR / f"{day['date']}.md"
            filepath.write_text(content)
            count += 1

    # Also generate pre-deployment entries
    pre_count = 0
    for entry in data.get('pre_deployment', {}).get('entries', []):
        content = generate_day_file(entry, 'Pre-Deployment')
        filepath = CONTENT_DIR / f"{entry['date']}.md"
        filepath.write_text(content)
        pre_count += 1

    print(f"Generated {count} deployment day pages")
    print(f"Generated {pre_count} pre-deployment pages")
    print(f"Total: {count + pre_count} content files in {CONTENT_DIR}")


if __name__ == '__main__':
    main()
