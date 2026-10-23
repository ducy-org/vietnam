#!/usr/bin/env python3
"""Parse deployment-timeline.md and pre-deployment-timeline.md into timeline.json."""

import json
import re
import sys
from pathlib import Path

TIMELINE_DIR = Path("/Users/michael/Movies/Home Movies/Vietnam Project/Documentation/Mike Ducy Log Book")
OUTPUT = Path("/Users/michael/dev/ducy-vietnam/src/data/timeline.json")

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

LOCATION_PATTERNS = [
    (r"[Uu]nderway for ((?:Pearl Harbor|Subic Bay|Da Nang|Yokosuka|Hong Kong|Guam|San Diego|San Bernardino))", None),
    (r"[Aa]rrive.*Pearl Harbor", "Pearl Harbor"),
    (r"[Ii]n port Pearl Harbor", "Pearl Harbor"),
    (r"Waikiki", "Pearl Harbor"),
    (r"[Aa]rrive.*Subic Bay", "Subic Bay"),
    (r"[Ii]n port Subic Bay", "Subic Bay"),
    (r"[Aa]nchored in Subic", "Subic Bay"),
    (r"Olongapo", "Subic Bay"),
    (r"[Aa]nchor(?:ed)? in Da Nang", "Da Nang"),
    (r"[Ii]n port Yokosuka", "Yokosuka"),
    (r"[Aa]nchored? in Hong Kong", "Hong Kong"),
    (r"Hong Kong", "Hong Kong"),
    (r"[Aa]rrive Guam|[Ii]n port Guam|[Aa]rrive.*Guam", "Guam"),
    (r"SAR/AAW station", "SAR/AAW Station, Gulf of Tonkin"),
    (r"SAR station", "SAR Station, Gulf of Tonkin"),
    (r"AAW station", "AAW Station, Gulf of Tonkin"),
    (r"Tonkin", "Gulf of Tonkin"),
    (r"ARRIVE AND MOOR.*SAN DIEGO", "San Diego"),
    (r"San Bernardino", "San Bernardino Straits"),
    (r"Seal Beach", "Seal Beach"),
    (r"Treasure Island", "Treasure Island, San Francisco"),
    (r"Bremerton", "Bremerton"),
    (r"Pearl Harbor", "Pearl Harbor"),
    (r"Da Nang", "Da Nang"),
    (r"Subic Bay", "Subic Bay"),
    (r"\bGuam\b", "Guam"),
    (r"San Diego", "San Diego"),
]


def strip_md(text):
    """Remove markdown bold/italic markers."""
    text = re.sub(r'\*{1,3}', '', text)
    return text.strip()


def extract_sources(text):
    """Extract [Source] tags from entry text."""
    sources = []
    for m in re.finditer(r'\[([^\]]+)\]', text):
        tag = m.group(1)
        if tag.startswith(("Logbook", "Letter", "Familygram", "Stars & Stripes",
                           "Jouett Jargon", "Evening News", "Bill's letter",
                           "Given's letter", "Norris's letter", "HC-7",
                           "San Diego Union", "Plan of the Day", "COR",
                           "Video", "Photo")):
            sources.append(tag)
    return sources if sources else ["Logbook"]


def clean_entry(text):
    """Clean entry text: strip markdown, remove trailing source tags."""
    text = strip_md(text)
    text = re.sub(r'\s*\[[^\]]*\]\s*$', '', text)
    text = re.sub(r'\s*\[Logbook\]', '', text)
    text = re.sub(r'\s*\[Letter\]', '', text)
    text = re.sub(r'\s*\[Familygram[^\]]*\]', '', text)
    text = re.sub(r'\s*\[HC-7[^\]]*\]', '', text)
    text = re.sub(r'\s*\[COR[^\]]*\]', '', text)
    text = re.sub(r'\s*\[Evening News\]', '', text)
    text = re.sub(r'\s*\[Stars & Stripes\]', '', text)
    text = re.sub(r'\s*\[Jouett Jargon[^\]]*\]', '', text)
    text = re.sub(r'\s*\[San Diego Union\]', '', text)
    text = re.sub(r'\s*\[Plan of the Day\]', '', text)
    text = re.sub(r'\s*\[Bill\'s letter[^\]]*\]', '', text)
    text = re.sub(r'\s*\[Given\'s letter[^\]]*\]', '', text)
    text = re.sub(r'\s*\[Norris\'s letter[^\]]*\]', '', text)
    text = re.sub(r'\s*\[Video\]', '', text)
    return text.strip()


def infer_location(text):
    """Infer location from entry text."""
    for pattern, location in LOCATION_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if location is None:
                return f"Underway for {m.group(1)}"
            return location
    if re.search(r'(?:at sea|underway)', text, re.IGNORECASE):
        return "At Sea"
    if re.search(r'(?:in port|anchored|moor)', text, re.IGNORECASE):
        return "In Port"
    return None


def parse_date(date_str, default_year=1968):
    """Parse 'Tue 16 Jan' into ISO date string."""
    date_str = strip_md(date_str).strip()
    m = re.match(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+(\w{3})', date_str)
    if not m:
        return None, None
    day_num = int(m.group(1))
    month_abbr = m.group(2)
    month = MONTH_MAP.get(month_abbr)
    if month is None:
        return None, None
    dow = date_str.split()[0]
    return f"{default_year}-{month:02d}-{day_num:02d}", dow


def parse_day_number(day_str):
    """Parse day number from table column (unused for final output, kept for parsing)."""
    day_str = strip_md(day_str).strip()
    if day_str in ('—', '-', ''):
        return None
    m = re.match(r'(\d+)', day_str)
    if m:
        return int(m.group(1))
    return None


def parse_photo_line(line):
    """Extract photo info from a > **Photos...** line."""
    m = re.search(r'\[(\d+)\s+photos?', line)
    count = int(m.group(1)) if m else 1
    desc = strip_md(line)
    desc = re.sub(r'^>\s*', '', desc)
    desc = re.sub(r'\[\d+\s+photos?,.*?\]', '', desc).strip()
    desc = re.sub(r'^Photos?\s*\([^)]*\):\s*', '', desc).strip()
    return {"description": desc, "count": count}


def parse_document_line(line):
    """Extract document info from a > **Document...** line."""
    text = strip_md(line)
    text = re.sub(r'^>\s*', '', text)
    text = re.sub(r'\[[^\]]*\]\s*$', '', text).strip()
    text = re.sub(r'^Document(?:\s*\([^)]*\))?:\s*', '', text).strip()
    return {"description": text}


def parse_quote_line(line):
    """Extract a cleaned quote from a > block."""
    text = line.lstrip('> ').strip()
    text = strip_md(text)
    return text


def parse_table_row(line):
    """Parse a markdown table row into cells."""
    line = line.strip()
    if not line.startswith('|'):
        return None
    cells = line.split('|')
    if len(cells) < 4:
        return None
    cells = [c.strip() for c in cells[1:-1]]
    return cells


def is_significant_row(line):
    """Check if the entire row is wrapped in bold+italic (***...***)."""
    cells = line.split('|')
    if len(cells) < 4:
        return False
    date_cell = cells[1].strip()
    return date_cell.startswith('***') or date_cell.startswith('**')


def parse_deployment_timeline(filepath):
    """Parse the deployment timeline markdown into structured data."""
    lines = filepath.read_text().splitlines()

    months = []
    current_month = None
    current_days = []
    last_day = None
    in_table = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Month headers: ## January 1968 — ...
        m = re.match(r'^##\s+(.+)$', stripped)
        if m and not stripped.startswith('###'):
            title = strip_md(m.group(1))
            # Skip "Pre-Deployment" and non-month sections
            if any(kw in title for kw in ['Deployment Statistics', 'Key Personnel',
                                           'Sources', 'Research', 'Pre-Deployment']):
                # Save current month if any
                if current_month and current_days:
                    current_month['days'] = current_days
                    months.append(current_month)
                current_month = None
                current_days = []
                last_day = None
                continue

            # Extract month/year from title
            month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', title)
            if month_match:
                month_name = month_match.group(1)
                year = int(month_match.group(2))
                month_num = {
                    'January': 1, 'February': 2, 'March': 3, 'April': 4,
                    'May': 5, 'June': 6, 'July': 7, 'August': 8,
                    'September': 9, 'October': 10, 'November': 11, 'December': 12
                }[month_name]

                if current_month and current_days:
                    current_month['days'] = current_days
                    months.append(current_month)

                current_month = {
                    'month': f"{year}-{month_num:02d}",
                    'title': title,
                }
                current_days = []
                last_day = None

            # Handle multi-month headers like "Late February – March 1968"
            elif re.search(r'Late\s+\w+\s*[–—-]\s*(\w+)\s+(\d{4})', title):
                mm = re.search(r'[–—-]\s*(\w+)\s+(\d{4})', title)
                if mm:
                    if current_month and current_days:
                        current_month['days'] = current_days
                        months.append(current_month)
                    month_name = mm.group(1)
                    year = int(mm.group(2))
                    month_num = {
                        'January': 1, 'February': 2, 'March': 3, 'April': 4,
                        'May': 5, 'June': 6, 'July': 7, 'August': 8,
                        'September': 9, 'October': 10, 'November': 11, 'December': 12
                    }.get(month_name, 0)
                    if month_num:
                        current_month = {
                            'month': f"{year}-{month_num:02d}",
                            'title': title,
                        }
                        current_days = []
                        last_day = None
            # Handle "Late May – June 1968"
            elif re.search(r'Late\s+(\w+)\s*[–—-]\s*(\w+)\s+(\d{4})', title):
                mm = re.search(r'[–—-]\s*(\w+)\s+(\d{4})', title)
                if mm:
                    if current_month and current_days:
                        current_month['days'] = current_days
                        months.append(current_month)
                    current_month = {
                        'month': f"{year}-{month_num:02d}",
                        'title': title,
                    }
                    current_days = []
                    last_day = None

            continue

        # Table header/separator lines
        if re.match(r'^\|[-\s|]+\|$', stripped) or re.match(r'^\|\s*Date\s*\|', stripped):
            in_table = True
            continue

        # Table data rows
        if stripped.startswith('|') and in_table:
            cells = parse_table_row(stripped)
            if cells and len(cells) >= 3:
                date_str, dow = parse_date(cells[0])
                if date_str:
                    day_num = parse_day_number(cells[1])
                    entry_raw = cells[2] if len(cells) >= 3 else ''
                    # Join extra cells (entries with | in them)
                    if len(cells) > 3:
                        entry_raw = ' | '.join(cells[2:])
                    significant = is_significant_row(stripped)
                    sources = extract_sources(entry_raw)
                    entry_clean = clean_entry(entry_raw)
                    location = infer_location(entry_raw)

                    day_entry = {
                        'date': date_str,
                        'day_number': day_num,
                        'day_of_week': dow,
                        'entries': [entry_clean],
                        'sources': sources,
                        'significant': significant,
                        'location': location,
                        'quotes': [],
                        'photos': [],
                        'documents': [],
                    }
                    current_days.append(day_entry)
                    last_day = day_entry
            continue

        # Non-table content
        if not stripped.startswith('|'):
            in_table = False

        # Photo references
        if stripped.startswith('> **Photo'):
            if last_day:
                last_day['photos'].append(parse_photo_line(stripped))
            continue

        # Document references
        if stripped.startswith('> **Document'):
            if last_day:
                last_day['documents'].append(parse_document_line(stripped))
            continue

        # Quote blocks (letters, familygrams, context, etc.)
        if stripped.startswith('> '):
            if last_day:
                quote = parse_quote_line(stripped)
                if quote:
                    last_day['quotes'].append(quote)
            continue

        # Standalone italic blocks (ship's newspaper, stars & stripes, etc.)
        if stripped.startswith('***') and not stripped.startswith('### ***'):
            if last_day:
                last_day['quotes'].append(strip_md(stripped))
            continue

    # Save final month
    if current_month and current_days:
        current_month['days'] = current_days
        months.append(current_month)

    return months


def parse_predeployment_timeline(filepath):
    """Parse the narrative pre-deployment timeline."""
    lines = filepath.read_text().splitlines()

    entries = []
    current_entry = None
    in_summary_table = False
    in_sources = False

    for line in lines:
        stripped = line.strip()

        # Stop at Key Events Summary or Sources
        if stripped.startswith('## Key Events Summary') or stripped.startswith('## Sources'):
            if current_entry:
                entries.append(current_entry)
                current_entry = None
            in_summary_table = True
            continue

        if in_summary_table:
            continue

        # Month headers: ## August 1967 — ...
        m = re.match(r'^##\s+(.+)$', stripped)
        if m and not stripped.startswith('###'):
            continue

        # Date headers: ### Aug 22, 1967 — First Letter Home
        m = re.match(r'^###\s+(.+)$', stripped)
        if m:
            header = strip_md(m.group(1))
            # Try to parse date
            date_match = re.match(r'(\w{3})\s+(\d{1,2}),?\s+(\d{4})', header)
            if date_match:
                if current_entry:
                    entries.append(current_entry)

                month_abbr = date_match.group(1)
                day = int(date_match.group(2))
                year = int(date_match.group(3))
                month = MONTH_MAP.get(month_abbr, 0)

                title = header
                title_m = re.match(r'\w{3}\s+\d{1,2},?\s+\d{4}\s*[–—-]\s*(.+)', header)
                section_title = title_m.group(1) if title_m else header

                current_entry = {
                    'date': f"{year}-{month:02d}-{day:02d}",
                    'day_number': None,
                    'day_of_week': None,
                    'title': section_title,
                    'entries': [],
                    'sources': ['Letter'],
                    'significant': False,
                    'location': None,
                    'quotes': [],
                    'photos': [],
                    'documents': [],
                }
                continue

            # Non-date headers (like "Blue Lotus Exercise", "Dependents' Cruise")
            non_date_m = re.match(r'(.+?)(?:\s*\((.+?)\))?$', header)
            if non_date_m and current_entry is None:
                # Try to extract a date range
                continue
            elif non_date_m:
                # Attach to current entry as context
                continue

        # Narrative text
        if current_entry and stripped and not stripped.startswith('#') and not stripped.startswith('---'):
            # Photo references
            if stripped.startswith('> **Photo'):
                current_entry['photos'].append(parse_photo_line(stripped))
                continue

            # Document references
            if stripped.startswith('> **Document'):
                current_entry['documents'].append(parse_document_line(stripped))
                continue

            # Quotes
            if stripped.startswith('> '):
                quote = parse_quote_line(stripped)
                if quote:
                    current_entry['quotes'].append(quote)
                continue

            # Regular narrative — add as entry text
            if not stripped.startswith('- ') and not stripped.startswith('|'):
                current_entry['entries'].append(stripped)
                # Infer location
                loc = infer_location(stripped)
                if loc and current_entry['location'] is None:
                    current_entry['location'] = loc

    if current_entry:
        entries.append(current_entry)

    return entries


def merge_duplicate_dates(days):
    """Merge days with the same date (e.g., Date Line crossing)."""
    merged = {}
    order = []
    for day in days:
        date = day['date']
        if date in merged:
            existing = merged[date]
            existing['entries'].extend(day['entries'])
            existing['quotes'].extend(day['quotes'])
            existing['photos'].extend(day['photos'])
            existing['documents'].extend(day['documents'])
            for s in day['sources']:
                if s not in existing['sources']:
                    existing['sources'].append(s)
            if day['significant']:
                existing['significant'] = True
            if day['day_number'] and not existing['day_number']:
                existing['day_number'] = day['day_number']
        else:
            merged[date] = day
            order.append(date)
    return [merged[d] for d in order]


def main():
    dep_file = TIMELINE_DIR / "deployment-timeline.md"
    pre_file = TIMELINE_DIR / "pre-deployment-timeline.md"

    if not dep_file.exists():
        print(f"ERROR: {dep_file} not found")
        sys.exit(1)

    # Parse deployment timeline
    months = parse_deployment_timeline(dep_file)

    # Merge duplicate dates within each month
    for month in months:
        month['days'] = merge_duplicate_dates(month['days'])

    # Parse pre-deployment timeline
    pre_entries = []
    if pre_file.exists():
        pre_entries = parse_predeployment_timeline(pre_file)

    # Compute day numbers from calendar: Jan 16 = Day 0, Jan 17 = Day 1, etc.
    from datetime import date as dt_date
    deployment_start = dt_date(1968, 1, 16)
    for month in months:
        for day in month['days']:
            parts = day['date'].split('-')
            d = dt_date(int(parts[0]), int(parts[1]), int(parts[2]))
            day['day_number'] = (d - deployment_start).days

    # Compute stats
    total_days = sum(len(m['days']) for m in months)
    significant = sum(1 for m in months for d in m['days'] if d['significant'])
    total_photos = sum(
        sum(p.get('count', 1) for p in d['photos'])
        for m in months for d in m['days']
    )
    total_documents = sum(
        len(d['documents'])
        for m in months for d in m['days']
    )
    total_quotes = sum(len(d['quotes']) for m in months for d in m['days'])
    pre_photos = sum(sum(p.get('count', 1) for p in e['photos']) for e in pre_entries)
    pre_documents = sum(len(e['documents']) for e in pre_entries)

    # Build output
    output = {
        'deployment': {
            'start': '1968-01-16',
            'end': '1968-07-18',
            'total_days': 184,
        },
        'months': months,
        'pre_deployment': {
            'start': '1967-08-16',
            'end': '1968-01-14',
            'entries': pre_entries,
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    # Print summary
    print(f"Deployment timeline parsed:")
    print(f"  Months:           {len(months)}")
    print(f"  Days:             {total_days}")
    print(f"  Significant:      {significant}")
    print(f"  Photos:           {total_photos} (across {sum(len(d['photos']) for m in months for d in m['days'])} references)")
    print(f"  Documents:        {total_documents}")
    print(f"  Quotes:           {total_quotes}")
    print()
    print(f"Pre-deployment timeline parsed:")
    print(f"  Entries:          {len(pre_entries)}")
    print(f"  Photos:           {pre_photos}")
    print(f"  Documents:        {pre_documents}")
    print()
    print(f"Output: {OUTPUT}")

    # Month breakdown
    print("\nMonth breakdown:")
    for m in months:
        days = len(m['days'])
        sig = sum(1 for d in m['days'] if d['significant'])
        print(f"  {m['month']} ({m['title']}): {days} days, {sig} significant")


if __name__ == '__main__':
    main()
