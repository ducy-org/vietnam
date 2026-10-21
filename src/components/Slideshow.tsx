import { useState, useEffect, useRef, useCallback } from "preact/hooks";

interface SlideData {
  src: string;
  thumb: string;
  start: number;
  end: number;
  description: string;
  transcript: { start: number; end: number; text: string }[];
}

interface SlideshowData {
  id: string;
  title: string;
  subtitle: string;
  audio: string;
  slides: SlideData[];
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function Slideshow({ show }: { show: SlideshowData }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const thumbStripRef = useRef<HTMLDivElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const activeSegRef = useRef<HTMLSpanElement>(null);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [activeSeg, setActiveSeg] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const mounted = useRef(false);

  const slides = show.slides;

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    function onTimeUpdate() {
      const t = audio!.currentTime;
      for (let i = 0; i < slides.length; i++) {
        if (t >= slides[i].start && t < slides[i].end) {
          setCurrentSlide(i);
          break;
        }
      }
      const slide = slides.find((s) => t >= s.start && t < s.end);
      if (slide) {
        let found = -1;
        for (let j = 0; j < slide.transcript.length; j++) {
          if (t >= slide.transcript[j].start && t < slide.transcript[j].end) {
            found = j;
            break;
          }
        }
        setActiveSeg(found);
      }
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
  }, [slides]);

  useEffect(() => {
    if (!mounted.current) { mounted.current = true; return; }
    const thumb = thumbStripRef.current?.children[currentSlide] as HTMLElement | undefined;
    if (thumb) {
      thumb.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }, [currentSlide]);

  useEffect(() => {
    if (activeSeg >= 0 && activeSegRef.current && transcriptRef.current) {
      const box = transcriptRef.current;
      const el = activeSegRef.current;
      const boxRect = box.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      const offset = elRect.top - boxRect.top - boxRect.height / 3;
      box.scrollTo({ top: box.scrollTop + offset, behavior: "smooth" });
    }
  }, [activeSeg]);

  const seekToSlide = useCallback((i: number) => {
    setCurrentSlide(i);
    if (audioRef.current) {
      audioRef.current.currentTime = slides[i].start;
      if (!isPlaying) audioRef.current.play();
    }
  }, [slides, isPlaying]);

  const seekToSeg = useCallback((start: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = start;
      if (!isPlaying) audioRef.current.play();
    }
  }, [isPlaying]);

  const slide = slides[currentSlide];
  const allSegs = slide?.transcript || [];

  return (
    <div class="ss-viewer">
      <div class="ss-main">
        <div class="ss-slide-wrap">
          <img
            src={slide?.src}
            alt={slide?.description}
            class="ss-slide-img"
            draggable={false}
          />
          <div class="ss-slide-caption">
            <span class="ss-slide-num">{currentSlide + 1} / {slides.length}</span>
            <span class="ss-slide-desc">{slide?.description}</span>
          </div>
        </div>

        <div class="ss-sidebar">
          <audio
            ref={audioRef}
            controls
            controlsList="nodownload"
            preload="metadata"
            class="ss-audio"
            onContextMenu={(e) => e.preventDefault()}
          >
            <source src={show.audio} type="audio/mpeg" />
          </audio>

          <div ref={transcriptRef} class="ss-transcript subtitle-box">
            {allSegs.length > 0 ? allSegs.map((seg, i) => (
              <span
                key={`${currentSlide}-${i}`}
                ref={i === activeSeg ? activeSegRef : undefined}
                class={`subtitle-seg ${i === activeSeg ? "subtitle-active" : ""}`}
                onClick={() => seekToSeg(seg.start)}
                title={`${formatTime(seg.start)} — click to jump`}
              >
                {seg.text}{" "}
              </span>
            )) : (
              <span class="ss-no-transcript">Narrating slide {currentSlide + 1}...</span>
            )}
          </div>

          <div class="subtitle-hint">
            {isPlaying ? "Playing — slides advance automatically" : "Press play — slides sync to Mike's narration"}
          </div>
        </div>
      </div>

      <div class="ss-thumbstrip" ref={thumbStripRef}>
        {slides.map((s, i) => (
          <button
            key={i}
            class={`ss-thumb ${i === currentSlide ? "ss-thumb-active" : ""}`}
            onClick={() => seekToSlide(i)}
            title={s.description}
          >
            <img src={s.thumb} alt={s.description} loading="lazy" draggable={false} />
            <span class="ss-thumb-num">{i + 1}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
