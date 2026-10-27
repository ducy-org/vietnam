#!/usr/bin/env python3
"""Render a captioned 4:5 slideshow video from a JSON spec (stills + tape audio + timed captions).

Usage: python scripts/make_reddit_video.py scripts/reddit_videos/<spec>.json
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1350, 30
PHOTO = 1000
PHOTO_Y = 105
CAPTION_TOP = PHOTO_Y + PHOTO + 22
XFADE = 0.6

BG = (19, 40, 65)
AMBER = (212, 169, 78)
WHITE = (255, 255, 255)
MUTED = (170, 182, 196)

TYPEWRITER = "/System/Library/Fonts/Supplemental/AmericanTypewriter.ttc"
SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
SERIF_BOLD = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"


def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def media_path(web_path):
    return ROOT / "public" / web_path.lstrip("/")


def draw_centered(draw, lines, y, fnt, fill, spacing=1.35):
    for line in lines:
        w = draw.textlength(line, font=fnt)
        draw.text(((W - w) / 2, y), line, font=fnt, fill=fill)
        y += int(fnt.size * spacing)
    return y


def card(spec_lines):
    """Full-frame text card: list of {text, style} where style is eyebrow|title|body|url."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    styles = {
        "eyebrow": (font(SERIF_BOLD, 34), AMBER, 44),
        "title": (font(SERIF_BOLD, 62), WHITE, 26),
        "body": (font(SERIF, 42), WHITE, 34),
        "url": (font(TYPEWRITER, 46), AMBER, 40),
        "small": (font(SERIF, 32), MUTED, 30),
    }
    blocks = []
    for item in spec_lines:
        fnt, fill, wrap = styles[item["style"]]
        wrapped = textwrap.wrap(item["text"], wrap) or [""]
        blocks.append((wrapped, fnt, fill))
    total = sum(len(b[0]) * int(b[1].size * 1.35) + 40 for b in blocks)
    y = (H - total) / 2
    for wrapped, fnt, fill in blocks:
        y = draw_centered(d, wrapped, y, fnt, fill) + 40
    return im


def base_frame(header, footer):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    f = font(SERIF_BOLD, 32)
    w = d.textlength(header, font=f)
    d.text(((W - w) / 2, 40), header, font=f, fill=AMBER)
    f2 = font(TYPEWRITER, 30)
    w2 = d.textlength(footer, font=f2)
    d.text(((W - w2) / 2, H - 58), footer, font=f2, fill=MUTED)
    return im


def ken_burns(src, t, dur, direction):
    """Return PHOTO x PHOTO crop of src at time t within a slide of length dur."""
    p = min(max(t / dur, 0), 1)
    z0, z1 = (1.0, 1.08) if direction % 2 == 0 else (1.08, 1.0)
    z = z0 + (z1 - z0) * p
    sw, sh = src.size
    side = min(sw, sh) / z
    cx = sw / 2 + (sw - side) / 2 * 0.25 * (1 if direction % 4 < 2 else -1) * (p - 0.5)
    cy = sh / 2
    box = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    return src.resize((PHOTO, PHOTO), Image.LANCZOS, box=box)


def caption_image(text):
    f = font(TYPEWRITER, 40)
    lines = textwrap.wrap(text, 42)[:3]
    im = Image.new("RGBA", (W, 190), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    draw_centered(d, lines, 0, f, WHITE, spacing=1.3)
    return im


def main(spec_file):
    spec = json.loads(Path(spec_file).read_text())
    out = Path(spec["out"]).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    clip_start, clip_end = spec["clip_start"], spec["clip_end"]
    intro, outro = spec.get("intro_seconds", 5.0), spec.get("outro_seconds", 4.0)
    body = clip_end - clip_start
    total = intro + body + outro

    intro_im = card(spec["intro"])
    outro_im = card(spec["outro"])
    frame_base = base_frame(spec["header"], spec.get("footer", "vietnam.ducy.org"))

    slides = []
    for i, s in enumerate(spec["slides"]):
        slides.append({
            "img": Image.open(media_path(s["src"])).convert("RGB"),
            "start": max(s["start"], clip_start) - clip_start + intro,
            "end": min(s["end"], clip_end) - clip_start + intro,
            "dir": i,
        })
    slides[0]["start"] = intro
    slides[-1]["end"] = intro + body

    captions = []
    for c in spec["captions"]:
        captions.append({
            "start": c["start"] - clip_start + intro,
            "end": c["end"] - clip_start + intro,
            "img": caption_image(c["text"]),
        })

    audio = media_path(spec["audio"])
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-ss", str(clip_start), "-t", str(body), "-i", str(audio),
        "-filter_complex",
        f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.4,afade=t=out:st={body - 0.8}:d=0.8,adelay={int(intro * 1000)}:all=1,apad[a]",
        "-map", "0:v", "-map", "[a]", "-t", str(total),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def slide_frame(s, t):
        im = frame_base.copy()
        im.paste(ken_burns(s["img"], t - s["start"], s["end"] - s["start"], s["dir"]), ((W - PHOTO) // 2, PHOTO_Y))
        return im

    n = int(total * FPS)
    for k in range(n):
        t = k / FPS
        if t < intro - XFADE:
            frame = intro_im
        elif t < intro:
            frame = Image.blend(intro_im, slide_frame(slides[0], intro), (t - (intro - XFADE)) / XFADE)
        elif t < intro + body:
            idx = next((i for i, s in enumerate(slides) if s["start"] <= t < s["end"]), len(slides) - 1)
            s = slides[idx]
            frame = slide_frame(s, t)
            if idx + 1 < len(slides) and t > s["end"] - XFADE:
                frame = Image.blend(frame, slide_frame(slides[idx + 1], t), (t - (s["end"] - XFADE)) / XFADE)
            cap = next((c for c in captions if c["start"] <= t < c["end"]), None)
            if cap:
                frame = frame.copy()
                frame.paste(cap["img"], (0, CAPTION_TOP), cap["img"])
        elif t < intro + body + XFADE:
            last = slide_frame(slides[-1], intro + body)
            frame = Image.blend(last, outro_im, (t - intro - body) / XFADE)
        else:
            frame = outro_im
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"Wrote {out} ({total:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1])
