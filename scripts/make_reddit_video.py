#!/usr/bin/env python3
"""Render a 4:5 Reddit video in the Letters Home teletype style from a JSON spec.

Usage: python scripts/make_reddit_video.py scripts/reddit_videos/<spec>.json
Style and spec reference: Vietnam Project/Documentation/reddit-video-style.md
"""
import json
import subprocess
import sys
import tempfile
import textwrap
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS, SR = 1080, 1350, 30, 48000
PHOTO = 960
PHOTO_X, PHOTO_Y = (W - PHOTO) // 2, 178
CAPTION_TOP = PHOTO_Y + PHOTO + 18
XFADE = 0.5

BG = (10, 14, 18)
PAPER = (236, 233, 224)
AMBER = (242, 180, 60)
MUTED = (140, 148, 156)

MONO_BOLD = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

CARD_CPS, STAMP_CPS = 32, 38
LINE_PAUSE, CARD_HOLD, CARD_LEAD = 0.15, 1.3, 0.6
CARD_X = 70

# (size, color) per teletype line style
CARD_STYLES = {"white": (48, PAPER), "amber": (48, AMBER), "muted": (36, MUTED), "big": (76, AMBER)}
STAMP_STYLES = [(36, AMBER), (36, PAPER), (26, MUTED)]

_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(MONO_BOLD, size)
    return _fonts[size]


def media_path(web_path):
    return ROOT / "public" / web_path.lstrip("/")


# ---------- teletype text ----------

class Teletype:
    """Lines typed one character at a time from `start`; records sound events."""

    def __init__(self, lines, start, cps, width=None):
        self.lines = []
        for text, style in lines:
            text = text.upper()
            chars = int(width / font(CARD_STYLES[style][0]).getlength("M")) if width else 0
            chunks = textwrap.wrap(text, chars) if (chars and text) else [text]
            self.lines += [(c, style) for c in chunks]
        self.start, self.schedule, self.events = start, [], []
        t = start
        for text, _ in self.lines:
            times = []
            for ch in text:
                times.append(t)
                if ch != " ":
                    self.events.append((t, "key"))
                t += 1 / cps
            self.schedule.append((times, t))
            if text:
                self.events.append((t, "cr"))
            t += LINE_PAUSE
        self.end = t

    def visible(self, t):
        """[(visible_text, style)] for lines started by time t, and the index still typing (or None)."""
        out = []
        for i, ((text, style), (times, line_end)) in enumerate(zip(self.lines, self.schedule)):
            first = times[0] if times else line_end
            if first > t and i > 0:
                return out, None
            n = sum(1 for x in times if x <= t)
            out.append((text[:n], style))
            if t < line_end:
                return out, i
        return out, None


def draw_cursor(d, x, y, size, color):
    cw = font(size).getlength("M")
    d.rectangle([x, y + size * 0.1, x + cw, y + size * 1.05], fill=color)


def card_frame(tt, t, base):
    im = base.copy()
    d = ImageDraw.Draw(im)
    heights = [CARD_STYLES[s][0] * 1.45 for _, s in tt.lines]
    y = (H - sum(heights)) / 2
    vis, typing = tt.visible(t)
    for i, (text, style) in enumerate(vis):
        size, color = CARD_STYLES[style]
        d.text((CARD_X, y), text, font=font(size), fill=color)
        last = i == len(vis) - 1
        if typing == i or (last and typing is None and int(t * 2) % 2 == 0):
            draw_cursor(d, CARD_X + font(size).getlength(text), y, size, AMBER)
        y += heights[i]
    return im


def stamp_draw(d, tt, t):
    vis, typing = tt.visible(t)
    y = 24
    for i, (text, _) in enumerate(vis):
        size, color = STAMP_STYLES[min(i, 2)]
        d.text((PHOTO_X, y), text, font=font(size), fill=color)
        if typing == i:
            draw_cursor(d, PHOTO_X + font(size).getlength(text), y, size, AMBER)
        y += size * 1.3


# ---------- visuals ----------

class VideoSource:
    """Streams square-cropped PHOTO x PHOTO frames from a film clip, read forward in time."""

    def __init__(self, path, start, dur):
        self.proc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", str(dur + 1), "-i", str(path),
             "-vf", f"crop=ih:ih,scale={PHOTO}:{PHOTO},fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE)
        self.idx, self.frame = -1, None

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


def ken_burns(src, t, dur, direction):
    p = min(max(t / dur, 0), 1)
    z0, z1 = (1.0, 1.08) if direction % 2 == 0 else (1.08, 1.0)
    z = z0 + (z1 - z0) * p
    sw, sh = src.size
    side = min(sw, sh) / z
    cx = sw / 2 + (sw - side) / 2 * 0.25 * (1 if direction % 4 < 2 else -1) * (p - 0.5)
    cy = sh / 2
    return src.resize((PHOTO, PHOTO), Image.LANCZOS, box=(cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2))


def contain(img, t, dur):
    z = 1.0 + 0.04 * min(max(t / dur, 0), 1)
    w, h = img.size
    scale = PHOTO / max(w, h) * z
    fitted = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    box = Image.new("RGB", (PHOTO, PHOTO), BG)
    box.paste(fitted, ((PHOTO - fitted.width) // 2, (PHOTO - fitted.height) // 2))
    return box


def caption_image(text):
    lines = textwrap.wrap(text, 42)[:3]
    im = Image.new("RGBA", (W, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 0
    for line in lines:
        w = d.textlength(line, font=font(36))
        d.text(((W - w) / 2, y), line, font=font(36), fill=PAPER)
        y += 46
    return im


def vignette():
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    ov = np.zeros((H, W, 4), np.uint8)
    ov[..., 3] = (np.clip((r - 0.9) / 0.7, 0, 1) ** 1.5 * 70).astype(np.uint8)
    return Image.fromarray(ov, "RGBA")


# ---------- teletype sound (synthesized, no samples) ----------

rng = np.random.default_rng(1968)


def _env(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def key_sound():
    n = int(0.045 * SR)
    t = np.arange(n) / SR
    noise = np.convolve(rng.standard_normal(n) * _env(n, 0.004), np.ones(14) / 14, "same")
    click = np.sin(2 * np.pi * rng.uniform(700, 1100) * t) * _env(n, 0.003)
    thunk = np.sin(2 * np.pi * rng.uniform(85, 130) * t) * _env(n, 0.018)
    s = 0.5 * noise + 0.35 * click + 1.0 * thunk
    return s / np.abs(s).max() * rng.uniform(0.7, 1.0)


def cr_sound():
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for k in range(9):
        i, m = int((0.012 + k * 0.02) * SR), int(0.01 * SR)
        s[i:i + m] += np.convolve(rng.standard_normal(m), np.ones(10) / 10, "same") * _env(m, 0.002) * 0.5
    i = int(0.21 * SR)
    m = n - i
    s[i:] += np.sin(2 * np.pi * 95 * t[:m]) * _env(m, 0.02) + rng.standard_normal(m) * _env(m, 0.003) * 0.6
    return s / np.abs(s).max()


def bell_sound():
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * 1180 * t) + 0.3 * np.sin(2 * np.pi * 2360 * t)) * _env(n, 0.3)
    return s / np.abs(s).max()


def motor_hum(n):
    t = np.arange(n) / SR
    s = 0.5 * np.sin(2 * np.pi * 60 * t) + 0.3 * np.sin(2 * np.pi * 120 * t) + 0.15 * np.sin(2 * np.pi * 180 * t)
    s += np.convolve(rng.standard_normal(n), np.ones(40) / 40, "same") * 0.6
    fade = min(int(0.25 * SR), n // 2)
    ramp = np.ones(n)
    ramp[:fade], ramp[-fade:] = np.linspace(0, 1, fade), np.linspace(1, 0, fade)
    return s / np.abs(s).max() * ramp


def write_sfx(path, total, typed, bells, quiet):
    """typed: [(Teletype, gain)] → clacks, carriage returns, motor hum. quiet: (start, end) forced silent."""
    track = np.zeros(int(total * SR) + SR)

    def add(sig, at, gain):
        i = max(int(at * SR), 0)
        j = min(len(track), i + len(sig))
        track[i:j] += sig[: j - i] * gain

    for tt, gain in typed:
        add(motor_hum(int((tt.end - tt.start + 0.3) * SR)), tt.start - 0.1, gain * 0.12)
        for at, kind in tt.events:
            add(key_sound() if kind == "key" else cr_sound(), at, gain * (1.0 if kind == "key" else 0.8))
    for at, gain in bells:
        add(bell_sound(), at, gain)
    a, b = int(quiet[0] * SR), int(quiet[1] * SR)
    fade = int(0.03 * SR)
    track[a - fade:a] *= np.linspace(1, 0, fade)
    track[a:b] = 0
    spec = np.fft.rfft(track)
    f = np.fft.rfftfreq(len(track), 1 / SR)
    track = np.fft.irfft(spec / np.sqrt(1 + (f / 2000) ** 4), len(track))  # roll off the squeaky highs
    track = np.tanh(track * 1.2) / np.tanh(1.2)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((track[: int(total * SR)] * 32767 * 0.9).astype("<i2").tobytes())


# ---------- render ----------

DEFAULT_OUTRO = [
    "FULL TAPE. LOGBOOK. 184 DAYS:", "",
    {"text": "VIETNAM.DUCY.ORG", "style": "big"}, "",
    "LETTERS HOME", {"text": "A SAILOR'S PERSPECTIVE OF THE VIETNAM WAR IN 1968", "style": "muted"}, "",
    {"text": "NNNN", "style": "muted"},
]


def card_lines(lines):
    return [(l, "white") if isinstance(l, str) else (l["text"], l.get("style", "white")) for l in lines]


def main(spec_file):
    spec = json.loads(Path(spec_file).read_text())
    out = Path(spec["out"]).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    gap = spec.get("part_gap_seconds", 0.6)
    footer = spec.get("footer", "VIETNAM.DUCY.ORG")

    intro = Teletype(card_lines(spec["intro"]), CARD_LEAD, CARD_CPS, W - 2 * CARD_X)
    intro_end = intro.end + CARD_HOLD

    visuals, captions, typed = [], [], [(intro, 0.3)]
    t, prev_key, stamp = intro_end, None, None
    parts = spec["parts"]
    for pi, part in enumerate(parts):
        cs = part.get("clip_start", 0.0)
        ce = part.get("clip_end", cs + part.get("duration", 0))
        part["dur"] = ce - cs
        tail = gap if pi < len(parts) - 1 else 0
        st = part["stamp"]
        key = (st["when"], st["where"], st.get("audio", ""))
        if key != prev_key:
            lines = [(st["when"], "s"), (st["where"], "s")] + ([(st["audio"], "s")] if st.get("audio") else [])
            stamp = Teletype(lines, t + 0.15, STAMP_CPS)
            prev_key = key
        pv = [{"src": v["src"], "from": v.get("from", 0.0), "stamp": stamp,
               "start": max(v["start"], cs) - cs + t, "end": min(v["end"], ce) - cs + t} for v in part["visuals"]]
        pv[0]["start"], pv[-1]["end"] = t, t + part["dur"] + tail
        visuals += pv
        for c in part.get("captions", []):
            captions.append({"start": c["start"] - cs + t, "end": c["end"] - cs + t, "img": caption_image(c["text"])})
        t += part["dur"] + tail
    body_end = t

    outro_lines = spec.get("outro") or DEFAULT_OUTRO
    if not spec.get("outro") and not any(p.get("audio") for p in parts):
        outro_lines = ["FULL REEL. LOGBOOK. 184 DAYS:"] + outro_lines[1:]
    outro = Teletype(card_lines(outro_lines), body_end + 0.3, CARD_CPS, W - 2 * CARD_X)
    typed.append((outro, 0.26))
    total = outro.end + CARD_HOLD

    for i, v in enumerate(visuals):
        v["dir"] = i
        path = media_path(v["src"])
        if path.suffix.lower() in (".mp4", ".mov"):
            v["video"] = VideoSource(path, v["from"], v["end"] - v["start"] + XFADE)
        else:
            img = Image.open(path).convert("RGB")
            v["img"], v["fit"] = img, ("cover" if abs(img.width / img.height - 1) < 0.1 else "contain")

    sfx = Path(tempfile.mkdtemp()) / "sfx.wav"
    write_sfx(sfx, total, typed, [(max(intro.start - 0.4, 0), 0.22)], (intro_end, outro.start - 0.05))

    # Every silence must be real samples: a delayed timestamp is ignored by Apple's players.
    inputs, chain, labels, n_in = [], [f"anullsrc=r={SR}:cl=mono:d={intro_end}[lead]"], ["[lead]"], 1
    for pi, part in enumerate(parts):
        d = part["dur"]
        if part.get("audio"):
            inputs += ["-ss", str(part["clip_start"]), "-t", str(d), "-i", str(media_path(part["audio"]))]
            chain.append(f"[{n_in}:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample={SR},"
                         f"afade=t=in:d=0.3,afade=t=out:st={d - 0.5}:d=0.5,asetpts=N/SR/TB[p{pi}]")
            n_in += 1
        else:
            chain.append(f"anullsrc=r={SR}:cl=mono:d={d}[p{pi}]")
        labels.append(f"[p{pi}]")
        if pi < len(parts) - 1:
            chain.append(f"anullsrc=r={SR}:cl=mono:d={gap}[g{pi}]")
            labels.append(f"[g{pi}]")
    chain.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1,apad[narr]")
    chain.append(f"[{n_in}:a]aresample={SR}[sfx]")
    chain.append("[narr][sfx]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.95[a]")
    inputs += ["-i", str(sfx)]

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", *inputs,
           "-filter_complex", ";".join(chain), "-map", "0:v", "-map", "[a]", "-t", str(total),
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    base = Image.new("RGB", (W, H), BG)
    body_base = base.copy()
    fd = ImageDraw.Draw(body_base)
    fd.text((W - PHOTO_X - fd.textlength(footer, font=font(22)), H - 44), footer, font=font(22), fill=MUTED)
    vig = vignette()

    def picture(v, t):
        local, dur = t - v["start"], v["end"] - v["start"]
        if "video" in v:
            return v["video"].get(local)
        return ken_burns(v["img"], local, dur, v["dir"]) if v["fit"] == "cover" else contain(v["img"], local, dur)

    def body_frame(t):
        idx = next((i for i, v in enumerate(visuals) if v["start"] <= t < v["end"]), len(visuals) - 1)
        v = visuals[idx]
        pic = picture(v, t)
        if idx + 1 < len(visuals) and t > v["end"] - XFADE:
            pic = Image.blend(pic, picture(visuals[idx + 1], t), (t - (v["end"] - XFADE)) / XFADE)
        im = body_base.copy()
        im.paste(pic, (PHOTO_X, PHOTO_Y))
        stamp_draw(ImageDraw.Draw(im), v["stamp"], t)
        cap = next((c for c in captions if c["start"] <= t < c["end"]), None)
        if cap:
            im.paste(cap["img"], (0, CAPTION_TOP), cap["img"])
        return im

    for k in range(int(total * FPS)):
        t = k / FPS
        if t < intro_end:
            frame = card_frame(intro, t, base)
        elif t < body_end:
            frame = body_frame(t)
        else:
            frame = card_frame(outro, t, base)
        proc.stdin.write(Image.alpha_composite(frame.convert("RGBA"), vig).convert("RGB").tobytes())
    proc.stdin.close()
    for v in visuals:
        if "video" in v:
            v["video"].close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"Wrote {out} ({total:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1])
