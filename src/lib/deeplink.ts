// Deep links use the URL hash: #<key>/<target>, e.g. #vietnam/slide-17, #audio/tape-2-side-1-..., #<tape-slug>/4:02

export function readHash(): { key: string; target: string } {
  if (typeof window === "undefined") return { key: "", target: "" };
  const raw = decodeURIComponent(window.location.hash.replace(/^#/, ""));
  const i = raw.indexOf("/");
  return i < 0 ? { key: raw, target: "" } : { key: raw.slice(0, i), target: raw.slice(i + 1) };
}

/** "4:02", "1:04:02", "242", "242s" → seconds; null if not a time. */
export function parseTime(s: string): number | null {
  const m = s.trim().match(/^(?:(\d+):)?(\d+):(\d{1,2})$/);
  if (m) return (Number(m[1] || 0) * 3600) + Number(m[2]) * 60 + Number(m[3]);
  const n = s.trim().match(/^(\d+(?:\.\d+)?)s?$/);
  return n ? Number(n[1]) : null;
}

/** Media file basename without extension — the stable id used in deep links. */
export function mediaSlug(path: string | undefined): string {
  if (!path) return "";
  return (path.split("/").pop() || "").replace(/\.[^.]+$/, "");
}

/** Cue an audio element to t seconds once it can seek, without starting playback. */
export function cueAudio(audio: HTMLAudioElement, t: number) {
  const apply = () => { audio.currentTime = t; };
  if (audio.readyState >= 1) apply();
  else audio.addEventListener("loadedmetadata", apply, { once: true });
}

export function scrollToEl(el: Element | null) {
  if (!el) return;
  requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "start" }));
}
