import { useState, useEffect, useCallback, useRef } from "preact/hooks";

interface Page {
  src: string;
  thumb?: string;
  label: string;
  pageNumbers: string;
}

export default function CruiseBookViewer({ pages }: { pages: Page[] }) {
  const [current, setCurrent] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const thumbRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const mounted = useRef(false);

  const page = pages[current];

  const prev = useCallback(() => setCurrent((i) => Math.max(0, i - 1)), []);
  const next = useCallback(() => setCurrent((i) => Math.min(pages.length - 1, i + 1)), [pages.length]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
      else if (e.key === "Escape" && fullscreen) setFullscreen(false);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [prev, next, fullscreen]);

  useEffect(() => {
    if (!mounted.current) { mounted.current = true; return; }
    const thumb = thumbRef.current?.children[current] as HTMLElement | undefined;
    if (thumb) {
      thumb.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }, [current]);

  return (
    <div class="cb-viewer" ref={containerRef}>
      <div class="cb-main">
        <button class="cb-nav cb-nav-prev" onClick={prev} disabled={current === 0}>
          &#8249;
        </button>

        <div class="cb-page-wrap" onClick={() => setFullscreen(true)}>
          <img
            src={page.src}
            alt={page.label}
            class="cb-page-img"
            draggable={false}
          />
          <div class="cb-page-info">
            {page.label} &mdash; {current + 1} of {pages.length}
          </div>
        </div>

        <button class="cb-nav cb-nav-next" onClick={next} disabled={current === pages.length - 1}>
          &#8250;
        </button>
      </div>

      <div class="cb-thumbstrip" ref={thumbRef}>
        {pages.map((p, i) => (
          <button
            key={i}
            class={`cb-thumb ${i === current ? "cb-thumb-active" : ""}`}
            onClick={() => setCurrent(i)}
          >
            <img src={p.thumb || p.src} alt={p.label} loading="lazy" draggable={false} />
            <span class="cb-thumb-label">{p.pageNumbers}</span>
          </button>
        ))}
      </div>

      {fullscreen && (
        <div class="cb-fullscreen" onClick={(e) => {
          if ((e.target as HTMLElement).classList.contains("cb-fullscreen")) setFullscreen(false);
        }}>
          <button class="cb-fs-close" onClick={() => setFullscreen(false)}>&#10005;</button>
          <button class="cb-fs-nav cb-fs-prev" onClick={prev} disabled={current === 0}>&#8249;</button>
          <button class="cb-fs-nav cb-fs-next" onClick={next} disabled={current === pages.length - 1}>&#8250;</button>
          <img src={page.src} alt={page.label} class="cb-fs-img" draggable={false} />
          <div class="cb-fs-info">{page.label} &mdash; {current + 1} of {pages.length}</div>
        </div>
      )}
    </div>
  );
}
