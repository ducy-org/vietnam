#!/usr/bin/env python3
"""
Copy, rename, watermark, and manifest Vietnam Project media into public/media/.

Usage:
    python3 scripts/copy_media.py [--dry-run] [--force] [--category CATEGORY]
    python3 scripts/copy_media.py --dry-run --category photos
    python3 scripts/copy_media.py --force --category all

Categories: photos, letters, documents, logbook, slides, video, audio, all
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEDIA_OUT = PROJECT_ROOT / "public" / "media"
MANIFEST_OUT = PROJECT_ROOT / "src" / "data" / "media-manifest.json"

SOURCE_BASE = Path("/Users/michael/Movies/Home Movies/Vietnam Project")

WATERMARK_LEFT = "vietnam.ducy.org"
WATERMARK_RIGHT = "Ducy Family Archives"
IMAGE_EXTS = {".jpg", ".jpeg", ".heic", ".png", ".tif", ".tiff"}
SKIP_EXTS = {".txt", ".md", ".json", ".py", ".csv", ".ds_store"}
SKIP_DIRS = {"transcripts", "__pycache__", ".DS_Store"}

WEB_MAX_PX = 1600      # longest edge for web-sized images
WEB_QUALITY = 85
THUMB_WIDTH = 400       # thumbnail width
THUMB_QUALITY = 75

SSN_WARNING_FILES = [
    "19681118 - Record of Discharge DD-214N.jpeg",
    "19700320 - ACDUTRA orders & Pay Voucher Mike Ducy.jpeg",
    "19700320 - ACDUTRA orders & Pay Voucher Mike Ducy 1.jpeg",
]

# WAV files are copied as-is for now; MP3 conversion is a future step
AUDIO_NOTE = "Audio files copied as WAV. Convert to MP3 with ffmpeg before deploy."

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


def web_safe_name(filename: str) -> str:
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()
    if ext in (".jpeg", ".jpg"):
        ext = ".jpg"
    elif ext == ".heic":
        ext = ".jpg"
    name = stem.lower()
    name = re.sub(r"[,()\"‘’“”'`!?&;#@\[\]]", "", name)
    name = name.replace(":", "-")
    name = name.replace(" ", "-")
    name = name.replace("_", "-")
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name + ext


def extract_date(filename: str) -> str | None:
    m = re.match(r"(\d{8})", filename)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    m = re.match(r"(\d{6})", filename)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-01"
    tape_date_patterns = [
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
    for pattern, date in tape_date_patterns:
        if pattern in filename:
            return date
    return None


def extract_description(filename: str) -> str:
    stem = Path(filename).stem
    desc = re.sub(r"^\d{6,8}\s*-\s*", "", stem)
    return desc.strip() if desc else stem


def _draw_watermark_text(draw, text, x, y, font, font_size, avg_brightness):
    shadow_offset = max(1, font_size // 12)
    if avg_brightness > 140:
        draw.text((x + shadow_offset, y + shadow_offset), text,
                  font=font, fill=(255, 255, 255, 80))
        draw.text((x, y), text,
                  font=font, fill=(80, 80, 80, 130))
    else:
        draw.text((x + shadow_offset, y + shadow_offset), text,
                  font=font, fill=(0, 0, 0, 100))
        draw.text((x, y), text,
                  font=font, fill=(255, 255, 255, 130))


def apply_watermark(img_path: Path) -> None:
    if not HAS_PILLOW:
        return
    try:
        img = Image.open(img_path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        draw = ImageDraw.Draw(img)
        w, h = img.size
        font_size = max(12, min(36, int(w * 0.02)))

        try:
            font = ImageFont.truetype("/System/Library/Fonts/Courier New.ttf", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/Library/Fonts/Courier New.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        pad_x = max(5, int(w * 0.015))
        pad_y = max(5, int(h * 0.015))

        # Lower-left: vietnam.ducy.org
        bbox_l = draw.textbbox((0, 0), WATERMARK_LEFT, font=font)
        th_l = bbox_l[3] - bbox_l[1]
        x_l = pad_x
        y_l = h - th_l - pad_y

        sample_l = img.crop((max(0, x_l - 10), max(0, y_l - 10),
                             min(w, x_l + (bbox_l[2] - bbox_l[0]) + 10),
                             min(h, y_l + th_l + 10)))
        bright_l = sum(sample_l.resize((1, 1)).getpixel((0, 0))[:3]) / 3
        _draw_watermark_text(draw, WATERMARK_LEFT, x_l, y_l, font, font_size, bright_l)

        # Lower-right: Ducy Family Archives
        bbox_r = draw.textbbox((0, 0), WATERMARK_RIGHT, font=font)
        tw_r, th_r = bbox_r[2] - bbox_r[0], bbox_r[3] - bbox_r[1]
        x_r = w - tw_r - pad_x
        y_r = h - th_r - pad_y

        sample_r = img.crop((max(0, x_r - 10), max(0, y_r - 10),
                             min(w, x_r + tw_r + 10), min(h, y_r + th_r + 10)))
        bright_r = sum(sample_r.resize((1, 1)).getpixel((0, 0))[:3]) / 3
        _draw_watermark_text(draw, WATERMARK_RIGHT, x_r, y_r, font, font_size, bright_r)

        if img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(img_path, "JPEG", quality=92)
    except Exception as e:
        print(f"  WARNING: Watermark failed for {img_path.name}: {e}")


def apply_video_watermark(video_path: Path) -> None:
    """Burn watermark into video using ffmpeg overlay with a Pillow-generated PNG."""
    if not HAS_PILLOW:
        print(f"  WARNING: Pillow not available, skipping video watermark for {video_path.name}")
        return
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(video_path)],
            capture_output=True, text=True, timeout=15,
        )
        import json as _json
        streams = _json.loads(probe.stdout)
        vstream = next(s for s in streams["streams"] if s["codec_type"] == "video")
        w, h = int(vstream["width"]), int(vstream["height"])

        font_size = max(12, min(36, int(w * 0.02)))
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Courier.ttc", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/Library/Fonts/Courier New.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        pad_x = max(5, int(w * 0.015))
        pad_y = max(5, int(h * 0.015))

        bbox_l = draw.textbbox((0, 0), WATERMARK_LEFT, font=font)
        th_l = bbox_l[3] - bbox_l[1]
        x_l, y_l = pad_x, h - th_l - pad_y
        shadow = max(1, font_size // 12)
        draw.text((x_l + shadow, y_l + shadow), WATERMARK_LEFT, font=font, fill=(0, 0, 0, 100))
        draw.text((x_l, y_l), WATERMARK_LEFT, font=font, fill=(255, 255, 255, 130))

        bbox_r = draw.textbbox((0, 0), WATERMARK_RIGHT, font=font)
        tw_r, th_r = bbox_r[2] - bbox_r[0], bbox_r[3] - bbox_r[1]
        x_r, y_r = w - tw_r - pad_x, h - th_r - pad_y
        draw.text((x_r + shadow, y_r + shadow), WATERMARK_RIGHT, font=font, fill=(0, 0, 0, 100))
        draw.text((x_r, y_r), WATERMARK_RIGHT, font=font, fill=(255, 255, 255, 130))

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
            overlay.save(tmp_png.name, "PNG")
            tmp_out = video_path.with_suffix(".tmp.mp4")
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(video_path), "-i", tmp_png.name,
                 "-filter_complex", "overlay=0:0",
                 "-c:a", "copy", "-movflags", "+faststart",
                 str(tmp_out)],
                capture_output=True, text=True, timeout=600,
            )
            Path(tmp_png.name).unlink(missing_ok=True)
            if result.returncode == 0:
                tmp_out.replace(video_path)
                print(f"  [watermark] {video_path.name}")
            else:
                tmp_out.unlink(missing_ok=True)
                print(f"  WARNING: Video watermark failed for {video_path.name}: {result.stderr[-200:]}")
    except Exception as e:
        print(f"  WARNING: Video watermark failed for {video_path.name}: {e}")


def convert_heic(src: Path, dst: Path) -> bool:
    try:
        result = subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92",
             str(src), "--out", str(dst)],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  WARNING: HEIC conversion failed for {src.name}: {e}")
        return False


def bake_orientation(img_path: Path) -> None:
    """Apply EXIF orientation to pixel data so browsers render correctly."""
    try:
        result = subprocess.run(
            ["sips", "-g", "orientation", str(img_path)],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            if "orientation" in line:
                val = line.split(":")[-1].strip()
                rotation = {
                    "6": 90,    # rotated 90° CW — rotate pixels 90° CW
                    "8": 270,   # rotated 90° CCW — rotate pixels 270° CW
                    "3": 180,   # upside down
                }.get(val)
                if rotation:
                    subprocess.run(
                        ["sips", "--rotate", str(rotation), str(img_path)],
                        capture_output=True, text=True, timeout=15
                    )
                    subprocess.run(
                        ["sips", "--setProperty", "orientation", "1", str(img_path)],
                        capture_output=True, text=True, timeout=10
                    )
    except Exception:
        pass


def resize_for_web(img_path: Path) -> None:
    """Resize image so longest edge is at most WEB_MAX_PX."""
    try:
        result = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(img_path)],
            capture_output=True, text=True, timeout=10
        )
        w = h = 0
        for line in result.stdout.splitlines():
            if "pixelWidth" in line:
                w = int(line.split(":")[-1].strip())
            elif "pixelHeight" in line:
                h = int(line.split(":")[-1].strip())

        if max(w, h) <= WEB_MAX_PX:
            return

        subprocess.run(
            ["sips", "--resampleHeightWidthMax", str(WEB_MAX_PX),
             "-s", "formatOptions", str(WEB_QUALITY), str(img_path)],
            capture_output=True, text=True, timeout=30
        )
    except Exception as e:
        print(f"  WARNING: Resize failed for {img_path.name}: {e}")


def generate_thumbnail(img_path: Path, thumb_dir: Path) -> str | None:
    """Generate a thumbnail in thumb_dir. Returns web path to thumb or None."""
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / img_path.name
    try:
        shutil.copy2(img_path, thumb_path)
        subprocess.run(
            ["sips", "--resampleWidth", str(THUMB_WIDTH),
             "-s", "formatOptions", str(THUMB_QUALITY), str(thumb_path)],
            capture_output=True, text=True, timeout=30
        )
        return "/" + str(thumb_path.relative_to(PROJECT_ROOT / "public"))
    except Exception as e:
        print(f"  WARNING: Thumbnail failed for {img_path.name}: {e}")
        return None


def generate_pdf_thumbnail(pdf_path: Path, thumb_dir: Path) -> str | None:
    """Generate a JPEG thumbnail from the first page of a PDF."""
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_name = pdf_path.stem + ".jpg"
    thumb_path = thumb_dir / thumb_name
    try:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["qlmanage", "-t", "-s", str(THUMB_WIDTH), "-o", tmp, str(pdf_path)],
                capture_output=True, text=True, timeout=30
            )
            png_files = list(Path(tmp).glob("*.png"))
            if not png_files:
                return None
            subprocess.run(
                ["sips", "-s", "format", "jpeg", "-s", "formatOptions",
                 str(THUMB_QUALITY), str(png_files[0]), "--out", str(thumb_path)],
                capture_output=True, text=True, timeout=30
            )
        return "/" + str(thumb_path.relative_to(PROJECT_ROOT / "public"))
    except Exception as e:
        print(f"  WARNING: PDF thumbnail failed for {pdf_path.name}: {e}")
        return None


def generate_video_thumbnail(video_path: Path, thumb_dir: Path) -> str | None:
    """Generate a JPEG thumbnail from a video frame using ffmpeg."""
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / (video_path.stem + ".jpg")
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path),
             "-vf", f"select=eq(n\\,30),scale={THUMB_WIDTH}:-1",
             "-frames:v", "1", "-q:v", "5", str(thumb_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and thumb_path.exists():
            return "/" + str(thumb_path.relative_to(PROJECT_ROOT / "public"))
        return None
    except Exception as e:
        print(f"  WARNING: Video thumbnail failed for {video_path.name}: {e}")
        return None


def collect_files(src_dir: Path, recurse: bool = False) -> list[Path]:
    if not src_dir.exists():
        return []
    files = []
    items = src_dir.rglob("*") if recurse else src_dir.iterdir()
    for p in items:
        if not p.is_file():
            continue
        if p.name.startswith(".") or p.name.startswith("._"):
            continue
        if p.suffix.lower() in SKIP_EXTS:
            continue
        if any(skip in p.parts for skip in SKIP_DIRS):
            continue
        files.append(p)
    return sorted(files)


def process_file(src: Path, dst_dir: Path, dry_run: bool, force: bool,
                 watermark: bool, sub_key: str | None = None) -> dict | None:
    web_name = web_safe_name(src.name)
    dst = dst_dir / web_name
    is_heic = src.suffix.lower() == ".heic"
    is_image = src.suffix.lower() in IMAGE_EXTS

    skipped = dst.exists() and not force

    # Per-file and per-subcategory watermark overrides
    should_watermark = watermark
    if web_name in NO_WATERMARK_FILES:
        should_watermark = False
    if sub_key and sub_key in NO_WATERMARK_SUBCATEGORIES:
        should_watermark = False

    # HC-7 rescue date mapping
    also_dates = []
    file_date = extract_date(src.name)
    stem = Path(src.name).stem
    stem_lower = stem.lower().replace(" ", "-").replace("_", "-")
    for prefix, rescue_date in HC7_RESCUE_DATES.items():
        if prefix in stem_lower:
            file_date = rescue_date
            break

    # Cruise book date mapping (sub_key is None for top-level categories, check dst path)
    if "cruisebook" in str(dst_dir):
        cb_val = CRUISE_BOOK_DATES.get(stem, CRUISE_BOOK_DEFAULT_DATE)
        if isinstance(cb_val, list):
            file_date = cb_val[0]
            also_dates = cb_val[1:]
        else:
            file_date = cb_val

    if dry_run or skipped:
        if not skipped:
            action = "convert+copy" if is_heic else "copy"
            if should_watermark and is_image:
                action += "+watermark"
            action += "+resize+thumb"
            print(f"  [{action}] {src.name} → {web_name}")
        thumb_dir = dst_dir / "thumbs"
        result = {
            "original": str(src.relative_to(SOURCE_BASE)),
            "web_path": "/" + str(dst.relative_to(PROJECT_ROOT / "public")),
            "date": file_date,
            "description": extract_description(src.name),
            "_skipped": skipped,
        }
        if also_dates:
            result["also_dates"] = also_dates
        is_vid = src.suffix.lower() in {".mp4", ".webm", ".mov"}
        if is_image or src.suffix.lower() == ".pdf" or is_vid:
            thumb_name = web_name if is_image else Path(web_name).stem + ".jpg"
            result["thumb_path"] = "/" + str((thumb_dir / thumb_name).relative_to(PROJECT_ROOT / "public"))
        return result

    dst_dir.mkdir(parents=True, exist_ok=True)

    if is_heic:
        if not convert_heic(src, dst):
            return None
        bake_orientation(dst)
    else:
        shutil.copy2(src, dst)
        if is_image:
            bake_orientation(dst)

    # Logbook pages are photographed sideways — rotate 90° CW
    if "logbook" in str(dst_dir) and is_image:
        subprocess.run(
            ["sips", "--rotate", "90", str(dst)],
            capture_output=True, text=True, timeout=15
        )

    # Resize for web, then watermark, then generate thumbnail
    is_pdf = dst.suffix.lower() == ".pdf"
    thumb_web_path = None

    is_video = dst.suffix.lower() in {".mp4", ".webm", ".mov"}

    if is_image:
        resize_for_web(dst)
        if should_watermark and HAS_PILLOW:
            apply_watermark(dst)
        thumb_dir = dst_dir / "thumbs"
        thumb_web_path = generate_thumbnail(dst, thumb_dir)
    elif is_video:
        if should_watermark:
            apply_video_watermark(dst)
        thumb_dir = dst_dir / "thumbs"
        thumb_web_path = generate_video_thumbnail(dst, thumb_dir)
    elif is_pdf:
        thumb_dir = dst_dir / "thumbs"
        thumb_web_path = generate_pdf_thumbnail(dst, thumb_dir)

    result = {
        "original": str(src.relative_to(SOURCE_BASE)),
        "web_path": "/" + str(dst.relative_to(PROJECT_ROOT / "public")),
        "date": file_date,
        "description": extract_description(src.name),
    }
    if also_dates:
        result["also_dates"] = also_dates
    if thumb_web_path:
        result["thumb_path"] = thumb_web_path
    return result


NO_WATERMARK_FILES = {
    "end-of-big-mothers.pdf",
    "uss-jouett-1968-cor.pdf",
    "horizontal-tree-view---ancestry.pdf",
}
NO_WATERMARK_SUBCATEGORIES = {"hc7", "vigilance", "cruisebook"}

HC7_RESCUE_DATES = {
    "rescue-034": "1968-04-28",
    "rescue-036": "1968-05-07",
    "rescue-037": "1968-05-08",
    "rescue-041": "1968-06-04",
    "rescue-043": "1968-06-19",
}

CRUISE_BOOK_DATES = {
    "pg64-65": "1968-01-16",
    "pg66-67": "1968-01-16",
    "pg68-69": "1968-01-25",
    "pg70-71": "1968-01-28",
    "pg72-73": "1968-02-06",
    "pg74-75": "1968-02-07",
    "pg76-77": "1968-02-14",
    "pg78-79": "1968-02-29",
    "pg80-81": "1968-02-29",
    "pg82-83": "1968-03-01",
    "pg84-85": "1968-03-01",
    "pg86-87": "1968-03-16",
    "pg88-89": "1968-03-16",
    "pg90-91": "1968-03-16",
    "pg92-93": "1968-04-14",
    "pg94-95": "1968-04-18",
    "pg96-97": "1968-04-16",
    "pg98-99": "1968-04-16",
    "pg100-101": "1968-06-03",
    "pg102-103": "1968-06-03",
    "pg104-105": "1968-06-04",
    "pg106-107": ["1968-06-19","1968-04-28"],
    "pg108-109": "1968-05-07",
    "pg110-111": ["1968-06-04","1968-05-08"],
    "pg112-113": "1968-06-26",
    "pg116-117": "1968-01-16",
    "pg118-119": "1968-06-18",
    "pg120-121": "1968-06-13",
    "pg122-123": "1968-06-21",
    "pg124-125": "1968-06-28",
    "pg126-127": "1968-06-30",
    "pg128-129": "1968-06-30",
    "pg134-135": ["1968-01-21" , "1968-07-13"],
    "pg136-137": ["1968-02-03","1968-07-05","1968-02-07","1968-07-02","1968-02-15"],
    "pg138-139": "1968-03-28",
    "pg144-145": "1968-05-21",
    "pg146-147": "1968-05-21",
    "pg148-149": ["1968-05-21","1968-02-07","1968-07-02"],
    "pg150-151": "1968-07-04",
    "pg156-157": "1968-07-10",
    "pg158-159": "1968-07-10",
    "pg160-161": "1968-07-10",
    "pg162-163": "1968-07-18",
    "pg164-165": "1968-07-18",
    "pg166-167": "1968-07-18",
}
CRUISE_BOOK_DEFAULT_DATE = None

CATEGORIES = {
    "photos": {
        "sources": [
            ("Photos/Sorted:Dated", "photos", False),
            ("Photos/Bill Ducy", "photos/bill", False),
            ("Photos/Mike Ducy", "photos/mike", False),
        ],
        "watermark": True,
    },
    "letters": {
        "sources": [
            ("Documentation/Letters/Mike to Home", "letters/mike", False),
            ("Documentation/Letters/Bill to Mike", "letters/bill", False),
            ("Documentation/Letters/Given, WF 7942408 FTG-3 to Mike", "letters/given", False),
            ("Documentation/Letters/Norris, AR FTG 3 6775199 to Mike", "letters/norris", False),
        ],
        "watermark": True,
    },
    "documents": {
        "sources": [
            ("Documentation/DLG-29 Family Grams", "documents/familygrams", False),
            ("Documentation/DLG-29 Ship Publications", "documents/ship-pubs", False),
            ("Documentation/DLG-29 Ship Publications/196808 - Vigilance Magazine", "documents/vigilance", False),
            ("Documentation/Plans of the Day", "documents/plans-of-the-day", False),
            ("Documentation/Training & Service Records", "documents/service-records", False),
            ("Documentation/Newspaper Clippings", "documents/newspaper", False),
            ("Documentation/Misc", "documents/misc", False),
            ("Documentation/HC-7 Seadevils", "documents/hc7", False),
        ],
        "watermark": True,
    },
    "logbook": {
        "sources": [("Documentation/Mike Ducy Log Book", "logbook", False)],
        "watermark": True,
        "filter_exts": IMAGE_EXTS,
    },
    "slides": {
        "sources": [("Photos/Slides", "slides", True)],
        "watermark": True,
    },
    "video": {
        "sources": [("Videos", "video", False)],
        "watermark": True,
    },
    "audio": {
        "sources": [("Audio Cassettes/denoised recordings", "audio", False)],
        "watermark": False,
        "filter_exts": {".wav", ".mp3"},
    },
    "cruisebook": {
        "sources": [("Cruise Book - 1968", "cruisebook", False)],
        "watermark": False,
        "filter_exts": IMAGE_EXTS,
    },
}


def process_category(cat_name: str, cat_config: dict, dry_run: bool,
                     force: bool) -> dict:
    results = {}
    total_copied = 0
    total_skipped = 0
    total_bytes = 0
    watermark = cat_config.get("watermark", False)
    filter_exts = cat_config.get("filter_exts", None)

    for src_rel, dst_rel, recurse in cat_config["sources"]:
        src_dir = SOURCE_BASE / src_rel
        dst_dir = MEDIA_OUT / dst_rel

        sub_key = dst_rel.split("/")[-1] if "/" in dst_rel else None
        files = collect_files(src_dir, recurse=recurse)

        if filter_exts:
            files = [f for f in files if f.suffix.lower() in filter_exts]

        entries = []
        for f in files:
            if f.suffix.lower() in SKIP_EXTS:
                continue

            # For slides in subdirectories, flatten into one output dir
            if recurse:
                actual_dst = dst_dir
            else:
                actual_dst = dst_dir

            result = process_file(f, actual_dst, dry_run, force, watermark, sub_key)
            if result is None:
                continue
            was_skipped = result.pop("_skipped", False)
            result["category"] = cat_name
            if sub_key:
                result["subcategory"] = sub_key
            entries.append(result)
            if was_skipped:
                total_skipped += 1
            else:
                total_copied += 1
                if not dry_run:
                    total_bytes += f.stat().st_size

        if sub_key:
            if cat_name not in results:
                results[cat_name] = {}
            elif isinstance(results[cat_name], list):
                existing = results[cat_name]
                results[cat_name] = {"_root": existing}
            results[cat_name][sub_key] = entries
        else:
            if cat_name in results and isinstance(results[cat_name], dict):
                results[cat_name]["_root"] = entries
            else:
                results[cat_name] = entries

    return {
        "entries": results,
        "copied": total_copied,
        "skipped": total_skipped,
        "bytes": total_bytes,
    }


def format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    elif nbytes < 1024 * 1024 * 1024:
        return f"{nbytes / (1024 * 1024):.1f} MB"
    else:
        return f"{nbytes / (1024 * 1024 * 1024):.2f} GB"


def main():
    parser = argparse.ArgumentParser(description="Copy and process Vietnam Project media")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--category", default="all",
                        choices=list(CATEGORIES.keys()) + ["all"],
                        help="Process specific category (default: all)")
    args = parser.parse_args()

    if not HAS_PILLOW:
        print("WARNING: Pillow not installed. Images will be copied without watermarks.")
        print("  Install with: pip3 install Pillow\n")

    if args.dry_run:
        print("=== DRY RUN — no files will be copied ===\n")

    cats_to_process = CATEGORIES if args.category == "all" else {
        args.category: CATEGORIES[args.category]
    }

    manifest = {}
    if args.category != "all" and MANIFEST_OUT.exists():
        with open(MANIFEST_OUT) as f:
            manifest = json.load(f)
    grand_copied = 0
    grand_skipped = 0
    grand_bytes = 0
    ssn_warnings = []

    for cat_name, cat_config in cats_to_process.items():
        print(f"\n{'='*60}")
        print(f"  {cat_name.upper()}")
        print(f"{'='*60}")

        result = process_category(cat_name, cat_config, args.dry_run, args.force)

        entries = result["entries"]
        for k, v in (entries.items() if isinstance(entries, dict) else [(cat_name, entries)]):
            if isinstance(v, dict):
                for sk, sv in v.items():
                    if not sv:
                        continue
                    if k in manifest and isinstance(manifest[k], list):
                        existing = manifest[k]
                        manifest[k] = {"_root": existing}
                    manifest.setdefault(k, {})[sk] = sv
            elif isinstance(v, list):
                if not v:
                    continue
                if k in manifest and isinstance(manifest[k], dict):
                    manifest[k]["_root"] = v
                else:
                    manifest[k] = v

        grand_copied += result["copied"]
        grand_skipped += result["skipped"]
        grand_bytes += result["bytes"]

        print(f"\n  Processed: {result['copied']}, Skipped: {result['skipped']}")
        if not args.dry_run and result["bytes"] > 0:
            print(f"  Size: {format_size(result['bytes'])}")

        # Check for SSN files
        if cat_name == "documents":
            for src_rel, dst_rel, _ in cat_config["sources"]:
                if "Service Records" in src_rel:
                    src_dir = SOURCE_BASE / src_rel
                    for warn_file in SSN_WARNING_FILES:
                        if (src_dir / warn_file).exists():
                            ssn_warnings.append(warn_file)

    # Write manifest
    if not args.dry_run:
        MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(MANIFEST_OUT, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nManifest written to {MANIFEST_OUT}")
    else:
        print(f"\nManifest would be written to {MANIFEST_OUT}")

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Files processed: {grand_copied}")
    print(f"  Files skipped:   {grand_skipped}")
    if not args.dry_run:
        print(f"  Total size:      {format_size(grand_bytes)}")

    if ssn_warnings:
        print(f"\n  *** SSN REDACTION WARNING ***")
        print(f"  The following files contain Mike's SSN in the IMAGE.")
        print(f"  Redact manually in Preview before publishing:")
        for w in ssn_warnings:
            print(f"    - {w}")

    if not HAS_PILLOW and grand_copied > 0:
        print(f"\n  Images were copied WITHOUT watermarks (Pillow not installed)")

    if "audio" in cats_to_process:
        print(f"\n  NOTE: {AUDIO_NOTE}")

    print()


if __name__ == "__main__":
    main()
