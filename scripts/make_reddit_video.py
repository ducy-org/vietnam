#!/usr/bin/env python3
"""Render a captioned 4:5 video from a JSON spec: one or more tape clips over stills or film, with timed captions.

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


class VideoSource:
    """Streams square-cropped PHOTO x PHOTO frames from a film clip, read forward in time."""

    def __init__(self, path, start, dur):
        self.proc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", str(dur + 1), "-i", str(path),
             "-vf", f"crop=ih:ih,scale={PHOTO}:{PHOTO},fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE)
        self.idx = -1
        self.frame = None

    def get(self, local_t):
        target = max(int(local_t * FPS), 0)
        while self.idx < target:
            buf = self.proc.stdout.read(PHOTO * PHOTO * 3)
            if len(buf) < PHOTO * PHOTO * 3:
                break
            self.frame = Image.frombytes("RGB", (PHOTO, PHOTO), buf)
            self.idx += 1
        return self.frame

    def close(self):
        self.proc.kill()


def contain(img, t, dur):
    """Fit a non-square image inside the photo box with a gentle zoom."""
    z = 1.0 + 0.04 * min(max(t / dur, 0), 1)
    w, h = img.size
    scale = PHOTO / max(w, h) * z
    fitted = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    box = Image.new("RGB", (PHOTO, PHOTO), BG)
    box.paste(fitted, ((PHOTO - fitted.width) // 2, (PHOTO - fitted.height) // 2))
    return box


def load_parts(spec):
    """Normalize single-clip specs into the multi-part form."""
    if "parts" in spec:
        return spec["parts"]
    return [{
        "audio": spec["audio"], "clip_start": spec["clip_start"], "clip_end": spec["clip_end"],
        "header": spec["header"], "visuals": spec["slides"], "captions": spec["captions"],
    }]


def main(spec_file):
    spec = json.loads(Path(spec_file).read_text())
    out = Path(spec["out"]).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    intro, outro = spec.get("intro_seconds", 5.0), spec.get("outro_seconds", 4.0)
    gap = spec.get("part_gap_seconds", 0.6)
    parts = load_parts(spec)
    footer = spec.get("footer", "vietnam.ducy.org")

    visuals, captions = [], []
    t = intro
    for pi, part in enumerate(parts):
        cs, ce = part["clip_start"], part["clip_end"]
        part["offset"], part["dur"] = t, ce - cs
        base = base_frame(part.get("header", spec.get("header", "")), footer)
        pv = []
        for v in part["visuals"]:
            pv.append({
                "src": v["src"], "from": v.get("from", 0.0), "base": base,
                "start": max(v["start"], cs) - cs + t, "end": min(v["end"], ce) - cs + t,
            })
        pv[0]["start"] = t
        pv[-1]["end"] = t + part["dur"] + (gap if pi < len(parts) - 1 else 0)
        visuals += pv
        for c in part["captions"]:
            captions.append({"start": c["start"] - cs + t, "end": c["end"] - cs + t, "img": caption_image(c["text"])})
        t += part["dur"] + (gap if pi < len(parts) - 1 else 0)
    body_end = t
    total = body_end + outro

    for i, v in enumerate(visuals):
        v["dir"] = i
        path = media_path(v["src"])
        if path.suffix.lower() in (".mp4", ".mov"):
            v["video"] = VideoSource(path, v["from"], v["end"] - v["start"] + XFADE)
        else:
            img = Image.open(path).convert("RGB")
            v["img"] = img
            v["fit"] = "cover" if abs(img.width / img.height - 1) < 0.1 else "contain"

    intro_im = card(spec["intro"])
    outro_im = card(spec["outro"])

    # Every silence must be real samples: a delayed timestamp is ignored by Apple's players.
    inputs, chain, labels = [], [f"anullsrc=r=48000:cl=mono:d={intro}[lead]"], ["[lead]"]
    for pi, part in enumerate(parts):
        inputs += ["-ss", str(part["clip_start"]), "-t", str(part["dur"]), "-i", str(media_path(part["audio"]))]
        d = part["dur"]
        chain.append(f"[{pi + 1}:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
                     f"afade=t=in:d=0.3,afade=t=out:st={d - 0.5}:d=0.5,asetpts=N/SR/TB[p{pi}]")
        labels.append(f"[p{pi}]")
        if pi < len(parts) - 1:
            chain.append(f"anullsrc=r=48000:cl=mono:d={gap}[g{pi}]")
            labels.append(f"[g{pi}]")
    chain.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1,apad[a]")

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        *inputs,
        "-filter_complex", ";".join(chain),
        "-map", "0:v", "-map", "[a]", "-t", str(total),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def visual_frame(v, t):
        im = v["base"].copy()
        local, dur = t - v["start"], v["end"] - v["start"]
        if "video" in v:
            pic = v["video"].get(local)
        elif v["fit"] == "cover":
            pic = ken_burns(v["img"], local, dur, v["dir"])
        else:
            pic = contain(v["img"], local, dur)
        im.paste(pic, ((W - PHOTO) // 2, PHOTO_Y))
        return im

    for k in range(int(total * FPS)):
        t = k / FPS
        if t < intro - XFADE:
            frame = intro_im
        elif t < intro:
            frame = Image.blend(intro_im, visual_frame(visuals[0], intro), (t - (intro - XFADE)) / XFADE)
        elif t < body_end:
            idx = next((i for i, v in enumerate(visuals) if v["start"] <= t < v["end"]), len(visuals) - 1)
            v = visuals[idx]
            frame = visual_frame(v, t)
            if idx + 1 < len(visuals) and t > v["end"] - XFADE:
                frame = Image.blend(frame, visual_frame(visuals[idx + 1], t), (t - (v["end"] - XFADE)) / XFADE)
            cap = next((c for c in captions if c["start"] <= t < c["end"]), None)
            if cap:
                frame = frame.copy()
                frame.paste(cap["img"], (0, CAPTION_TOP), cap["img"])
        elif t < body_end + XFADE:
            frame = Image.blend(visual_frame(visuals[-1], body_end), outro_im, (t - body_end) / XFADE)
        else:
            frame = outro_im
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    for v in visuals:
        if "video" in v:
            v["video"].close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"Wrote {out} ({total:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1])
