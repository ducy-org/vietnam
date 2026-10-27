import { useEffect, useRef, useState, useCallback } from "preact/hooks";
import { readHash, parseTime, mediaSlug, cueAudio, scrollToEl } from "../lib/deeplink";

interface Segment {
  start: number;
  end: number;
  text: string;
}

interface AudioTranscriptProps {
  src: string;
  label: string;
  description: string;
  who: string;
  tape?: string;
  segments: Segment[];
  fullText: string;
  attribution?: string;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function AudioWithTranscript({
  src, label, description, who, tape, segments, fullText, attribution,
}: AudioTranscriptProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLSpanElement>(null);
  const [currentIdx, setCurrentIdx] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const anchor = mediaSlug(src);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { key, target } = readHash();
    if (!anchor || key !== anchor) return;
    scrollToEl(rootRef.current);
    const t = target ? parseTime(target) : null;
    if (t != null && audioRef.current) cueAudio(audioRef.current, t);
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    function onTimeUpdate() {
      const t = audio!.currentTime;
      let found = -1;
      for (let i = 0; i < segments.length; i++) {
        if (t >= segments[i].start && t < segments[i].end) {
          found = i;
          break;
        }
      }
      setCurrentIdx(found);
    }

    function onPlay() { setIsPlaying(true); }
    function onPause() { setIsPlaying(false); }

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
    };
  }, [segments]);

  useEffect(() => {
    if (currentIdx >= 0 && activeRef.current && boxRef.current) {
      const box = boxRef.current;
      const el = activeRef.current;
      const boxRect = box.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      const offset = elRect.top - boxRect.top - boxRect.height / 3;
      box.scrollTo({ top: box.scrollTop + offset, behavior: "smooth" });
    }
  }, [currentIdx]);

  const seekTo = useCallback((start: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = start;
      if (!isPlaying) audioRef.current.play();
    }
  }, [isPlaying]);

  const isMike = who === "mike";

  return (
    <div id={anchor || undefined} ref={rootRef} class={`audio-transcript-block ${isMike ? "audio-mike" : "audio-family"}`}>
      <div class="audio-transcript-header">
        <span class="audio-tape">{tape || "AUDIO"}</span>
        <span class="audio-speaker">{label}</span>
        {!isMike && <span class="audio-location">Recorded in Decatur, IL</span>}
      </div>
      <audio
        ref={audioRef}
        controls
        controlsList="nodownload"
        preload="metadata"
        class="audio-player"
        onContextMenu={(e) => e.preventDefault()}
      >
        <source src={src} type="audio/mpeg" />
      </audio>
      <div ref={boxRef} class="subtitle-box">
        {segments.map((seg, i) => (
          <span
            key={i}
            ref={i === currentIdx ? activeRef : undefined}
            class={`subtitle-seg ${i === currentIdx ? "subtitle-active" : ""}`}
            onClick={() => seekTo(seg.start)}
            title={`${formatTime(seg.start)} — click to jump`}
          >
            {seg.text}{" "}
          </span>
        ))}
      </div>
      <div class="subtitle-hint">
        {isPlaying ? "▶ Playing — click any line to jump" : "Click ▶ to play — transcript scrolls automatically"}
      </div>
      {attribution && <div class="audio-transcript-attribution">{attribution}</div>}
    </div>
  );
}
