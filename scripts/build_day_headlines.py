#!/usr/bin/env python3
"""Build src/data/day-headlines.json: a short, searchable headline per day page.

Hand-written headlines (OVERRIDES) win; otherwise a headline is derived from the
day's logbook entry. Used for page <title>, meta description, and a visible subhead.

Usage: python scripts/build_day_headlines.py [--print]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMELINE = ROOT / "src" / "data" / "timeline.json"
MANIFEST = ROOT / "src" / "data" / "media-manifest.json"
OUT = ROOT / "src" / "data" / "day-headlines.json"

OVERRIDES = {
    "1967-08-22": "First letter home from Treasure Island, San Francisco",
    "1967-08-30": "Treasure Island: hippies, mess cooking, and a camera",
    "1967-09-06": "Reporting aboard USS Jouett",
    "1967-09-17": "USS Enterprise arrives in San Diego",
    "1967-10-05": "USS Jouett at Bremerton, Washington",
    "1967-10-12": "Heading south from Bremerton to San Diego",
    "1967-10-19": "First days in San Diego",
    "1967-10-24": "A quick note home from San Diego",
    "1967-10-31": "Halloween letter: home for Christmas?",
    "1967-11-12": "A brothers' weekend and the Enterprise escort",
    "1967-11-20": "Promoted to third class petty officer",
    "1967-12-05": "Last sea exercise before the deployment",
    "1967-12-06": "The brothers meet in San Diego",
    "1968-01-04": "Final preparations: loading out for Vietnam",
    "1968-01-14": "Last letter home before departure",
    "1968-01-28": "Steaming for Guam; refueling at sea",
    "1968-01-29": "Crossing the date line: a day that never happened",
    "1968-02-02": "Bill Ducy arrives in Da Nang",
    "1968-02-13": "Missile shoots, then course for Da Nang",
    "1968-01-16": "USS Jouett departs San Diego for Vietnam",
    "1968-02-15": "First day in Vietnamese waters: Da Nang Harbor",
    "1968-03-11": "SAR alert: Air Force F-4 down inland, crew not found",
    "1968-03-18": "SAR alert: plane down 5 miles from Jouett, no survivors",
    "1968-01-20": "Steaming with USS Preble toward Pearl Harbor",
    "1968-01-23": "Liberty in Waikiki",
    "1968-01-24": "Last day at Pearl Harbor",
    "1968-01-31": "Highline transfer at sea en route to Guam",
    "1968-02-03": "Arriving at Guam",
    "1968-02-07": "Arriving at Subic Bay",
    "1968-03-28": "Arriving at Yokosuka, Japan",
    "1968-03-31": "Day tour of Tokyo: Tokyo Tower, sukiyaki, and a floor show",
    "1968-04-04": "Kamakura: the Great Buddha and cherry blossoms",
    "1968-04-06": "Leaving Yokosuka",
    "1968-05-01": "USO show on South SAR station: Chico and Chili",
    "1968-04-01": "USS Kitty Hawk arrives in Yokosuka",
    "1968-04-12": "Subic Bay: aboard the submarine USS Swordfish",
    "1968-04-16": "Two brothers meet in Da Nang: Bill Ducy (USMC) visits Jouett",
    "1968-04-28": "First rescue: two VF-21 F-4B pilots saved near Vinh",
    "1968-05-07": "Big Mother 71 rescues two VF-92 F-4B pilots near Vinh",
    "1968-05-08": "Deepest inland rescue: A-4E pilot saved 18 miles into North Vietnam",
    "1968-05-17": "Enterprise pilots fly by to thank Jouett; 300th helo landing",
    "1968-05-21": "Hong Kong liberty; Mike buys a Super 8 camera",
    "1968-06-04": "F-4J 'Root Beer 204' down: one pilot rescued, one lost",
    "1968-06-11": "A-7 Corsair down; pilot captured",
    "1968-06-13": "Da Nang: Flying Crane lifts Big Mother off the flight deck",
    "1968-06-17": "Terrier missiles fired at MiGs",
    "1968-06-19": "Medal of Honor night rescue: Lassen lands on Jouett with 5 minutes of fuel",
    "1968-06-21": "Three admirals visit Jouett",
    "1968-06-22": "Five Terrier missiles fired at MiGs",
    "1968-06-26": "MiG-21 shot down with help from Jouett's CIC",
    "1968-06-30": "Relieved on South SAR station; heading for Subic Bay",
    "1968-07-03": "Active volcano in the San Bernardino Strait",
    "1968-07-04": "Independence Day at sea: 21-gun salute and flight deck frolic",
    "1968-07-10": "Golden Shellback: crossing the equator at the date line",
    "1968-07-18": "Homecoming: USS Jouett returns to San Diego",
}

PORTS = ["SUBIC BAY", "PEARL HARBOR", "GUAM", "YOKOSUKA", "HONG KONG", "SAN DIEGO", "DA NANG", "DANANG", "OLONGAPO"]
AIRCRAFT = r"(AIR FORCE F-4|F-4[BJ]?|F4[BJ]?|A-4E?|A4E?|A-7|A7|A-5|A5|F-8|RA-5C|PHANTOM|SKYHAWK|CORSAIR|PLANE|PILOT|AIRCRAFT)"


def title_case_place(p):
    p = p.replace("DANANG", "DA NANG").title()
    return p.replace("Of", "of")


def media_for(manifest):
    by = {}

    def add(date, kind, item):
        if date and len(date) == 10:
            by.setdefault(date, {}).setdefault(kind, []).append(item)

    for sub, items in manifest["letters"].items():
        for i in items:
            add(i.get("date"), "letter_" + sub, i)
    for i in manifest["audio"]:
        add(i.get("date"), "audio", i)
    for items in manifest["photos"].values():
        for i in items:
            add(i.get("date"), "photo", i)
    return by


def derive(day, media):
    text = " ".join(e if isinstance(e, str) else e.get("text", "") for e in day.get("entries", [])).upper()
    loc = (day.get("location") or "").strip()
    on_station = "SAR" in text or "SAR" in loc.upper()

    def port():
        for p in PORTS:
            if p in text:
                return title_case_place(p)
        return None

    # 1. Events
    if "SAR ALERT" in text:
        m = re.search(r"SAR ALERT[^.]*?" + AIRCRAFT, text)
        craft = m.group(1) if m else None
        if craft:
            craft = craft.replace("F4", "F-4").replace("A4", "A-4").replace("A7", "A-7").replace("A5", "A-5")
        craft = {"PHANTOM": "F-4 Phantom", "SKYHAWK": "A-4 Skyhawk", "CORSAIR": "A-7 Corsair", "AIR FORCE F-4": "Air Force F-4"}.get(craft, craft)
        if craft in ("PLANE", "PILOT", "AIRCRAFT", None):
            return "SAR alert in the Gulf of Tonkin"
        return f"SAR alert: {craft} down in the Gulf of Tonkin"
    if "TERRIER" in text:
        return "Terrier missiles fired at MiGs"
    if "MIG" in text and ("GENERAL QUARTERS" in text or "G.Q." in text or "GQ" in text):
        m = re.search(r"(\d{2,3}) MILES", text)
        return f"General quarters: MiGs within {m.group(1)} miles" if m else "General quarters: MiGs in the area"

    # 2. Where the ship is
    underway = None
    m = re.search(r"UNDERWAY FOR ([A-Z .]+?)(?:[.,]|\s+CONDITION|\s+\d|$)", text)
    if m:
        dest = re.sub(r"\s+(S\.? VIET ?NAM|VIET ?NAM|SET|S)$", "", m.group(1).strip().rstrip("."))
        if dest.startswith("S") and ("SAR" in dest or dest in ("S", "S.")):
            underway = "South SAR station"
        elif "MISS" in dest or "GUN" in dest:
            underway = None
        else:
            underway = title_case_place(dest)
    in_port = port() if re.search(r"\b(ANCHOR|ANCHORED|MOOR|MOORED|IN PORT|INPORT|LIBERTY)\b", text) else None
    if loc.lower().startswith("underway for") and underway:
        in_port = None
    if on_station and not in_port:
        place_from = "from the Gulf of Tonkin"
    elif in_port:
        place_from = f"from {in_port}"
    elif underway:
        place_from = f"en route to {underway}"
    else:
        place_from = "from sea"

    # 3. What survives from that day
    md = media.get(day["date"], {})
    for a in md.get("audio", []):
        desc = a.get("description", "")
        if "Mike Ducy" in desc and "Dorothea" not in desc and "Dan" not in desc.split("Mike")[0]:
            return f"Mike's cassette tape home {place_from}"
        return "A cassette tape from home in Decatur"
    if md.get("letter_mike"):
        return f"Letter home {place_from}"
    if md.get("letter_bill"):
        return "Letter from Bill Ducy in Da Nang"
    if md.get("photo"):
        cap = re.sub(r"\s+\d+$", "", md["photo"][0].get("description", "").split(",")[0])
        return f"Photos: {cap}"

    # 4. Routine
    if "LIBERTY" in text and in_port:
        return f"Liberty in {in_port}"
    if in_port:
        return f"In port at {in_port}"
    if underway:
        return f"Underway for {underway}"
    if any(k in text for k in ("REFUEL", "UNREP", "REPLENISH")):
        return "Refueling at sea on South SAR station" if on_station else "Refueling at sea"
    if "PAY DAY" in text or "PAYDAY" in text:
        return "Payday on South SAR station" if on_station else "Payday at sea"
    if "MAIL" in text:
        return "Mail call by helicopter on South SAR station" if on_station else "Mail call at sea"
    if on_station:
        return "On South SAR station, Gulf of Tonkin"
    return loc


def main():
    t = json.loads(TIMELINE.read_text())
    media = media_for(json.loads(MANIFEST.read_text()))
    out = {}
    for e in t.get("pre_deployment", {}).get("entries", []):
        out[e["date"]] = OVERRIDES.get(e["date"]) or e.get("title") or ""
    for m in t["months"]:
        for d in m["days"]:
            out[d["date"]] = OVERRIDES.get(d["date"]) or derive(d, media)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    if "--print" in sys.argv:
        for k in sorted(out):
            print(k, "|", out[k])
    print(f"Wrote {OUT} ({len(out)} days)", file=sys.stderr)


if __name__ == "__main__":
    main()
