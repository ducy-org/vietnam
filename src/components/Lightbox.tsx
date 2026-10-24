import { useState, useEffect, useCallback } from "preact/hooks";

interface LightboxItem {
  src: string;
  thumb?: string;
  caption: string;
  type: "image" | "video" | "pdf";
}

export default function Lightbox({ items }: { items: LightboxItem[] }) {
  const [open, setOpen] = useState(-1);

  const close = useCallback(() => setOpen(-1), []);
  const prev = useCallback(
    () => setOpen((i) => (i > 0 ? i - 1 : items.length - 1)),
    [items.length]
  );
  const next = useCallback(
    () => setOpen((i) => (i < items.length - 1 ? i + 1 : 0)),
    [items.length]
  );

  useEffect(() => {
    if (open < 0) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
    }
    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [open, close, prev, next]);

  useEffect(() => {
    if (open >= 0 && items[open] && (window as any).gtag) {
      const item = items[open];
      (window as any).gtag("event", "lightbox_view", { event_category: "media", media_type: item.type, media_url: item.src, media_caption: item.caption });
    }
  }, [open]);

  const current = open >= 0 ? items[open] : null;

  return (
    <>
      <div class="lb-grid">
        {items.map((item, i) => (
          <button
            key={i}
            class="lb-thumb"
            onClick={() => setOpen(i)}
            aria-label={`Open ${item.caption}`}
          >
            {item.type === "video" ? (
              <div class="lb-thumb-video">
                {item.thumb ? (
                  <img src={item.thumb} alt={item.caption} loading="lazy" />
                ) : (
                  <video src={item.src} preload="metadata" onContextMenu={(e) => e.preventDefault()} />
                )}
                <span class="lb-play">&#9654;</span>
              </div>
            ) : item.type === "pdf" ? (
              item.thumb ? (
                <img src={item.thumb} alt={item.caption} loading="lazy" />
              ) : (
                <div class="lb-thumb-pdf">
                  <span class="lb-pdf-icon">PDF</span>
                </div>
              )
            ) : (
              <img src={item.thumb || item.src} alt={item.caption} loading="lazy" />
            )}
            <span class="lb-thumb-caption">{item.caption}</span>
          </button>
        ))}
      </div>

      {current && (
        <div class="lb-overlay" onClick={(e) => {
          if ((e.target as HTMLElement).classList.contains("lb-overlay")) close();
        }}>
          <button class="lb-close" onClick={close} aria-label="Close">&#10005;</button>

          {items.length > 1 && (
            <>
              <button class="lb-arrow lb-prev" onClick={prev} aria-label="Previous">&#8249;</button>
              <button class="lb-arrow lb-next" onClick={next} aria-label="Next">&#8250;</button>
            </>
          )}

          <div class="lb-content">
            {current.type === "video" ? (
              <video
                key={current.src}
                controls
                controlsList="nodownload"
                autoplay
                class="lb-video"
                onContextMenu={(e) => e.preventDefault()}
              >
                <source src={current.src} type="video/mp4" />
              </video>
            ) : current.type === "pdf" ? (
              <iframe
                key={current.src}
                src={current.src}
                class="lb-pdf"
              />
            ) : (
              <img src={current.src} alt={current.caption} class="lb-image" />
            )}
            <div class="lb-caption">
              {current.caption}
              {items.length > 1 && (
                <span class="lb-counter">{open + 1} / {items.length}</span>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
