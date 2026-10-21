import { useEffect, useRef, useState, useCallback, useMemo } from "preact/hooks";

interface Location {
  id: string;
  name: string;
  lat: number;
  lng: number;
  description: string;
  days: {
    date: string;
    day_number: number | null;
    entry: string;
    significant: boolean;
    media: string[];
  }[];
}

interface DayDetail {
  date: string;
  day_number: number | null;
  location: string | null;
  entries: string[];
  quotes: string[];
  significant: boolean;
  photos: { description: string; count?: number }[];
  documents: { description: string }[];
}

interface MediaEntry {
  src: string;
  thumb?: string;
  caption: string;
  type: "image" | "video";
  who?: string;
  speaker?: string;
  tape?: string;
}

function formatDate(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).toUpperCase();
}

function formatDateLong(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// Inline lightbox for the day modal
function ModalLightbox({ items, label }: { items: MediaEntry[]; label: string }) {
  const [open, setOpen] = useState(-1);

  const close = useCallback(() => setOpen(-1), []);
  const prev = useCallback(() => setOpen((i) => (i > 0 ? i - 1 : items.length - 1)), [items.length]);
  const next = useCallback(() => setOpen((i) => (i < items.length - 1 ? i + 1 : 0)), [items.length]);

  useEffect(() => {
    if (open < 0) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
    }
    document.addEventListener("keydown", handleKey, true);
    return () => document.removeEventListener("keydown", handleKey, true);
  }, [open, close, prev, next]);

  const current = open >= 0 ? items[open] : null;

  return (
    <div class="modal-media-section">
      <div class="modal-media-label">{label}</div>
      <div class="modal-media-grid">
        {items.map((item, i) => (
          <button key={i} class="modal-thumb" onClick={() => setOpen(i)}>
            {item.type === "video" ? (
              <div class="modal-thumb-video">
                {item.thumb ? (
                  <img src={item.thumb} alt={item.caption} loading="lazy" />
                ) : (
                  <video src={item.src} preload="metadata" onContextMenu={(e) => e.preventDefault()} />
                )}
                <span class="modal-play">&#9654;</span>
              </div>
            ) : item.src.endsWith(".pdf") ? (
              item.thumb ? (
                <img src={item.thumb} alt={item.caption} loading="lazy" />
              ) : (
                <div class="modal-thumb-pdf">
                  <span class="lb-pdf-icon">PDF</span>
                </div>
              )
            ) : (
              <img src={item.thumb || item.src} alt={item.caption} loading="lazy" />
            )}
            <span class="modal-thumb-cap">{item.caption}</span>
          </button>
        ))}
      </div>

      {current && (
        <div class="lb-overlay" onClick={(e) => {
          if ((e.target as HTMLElement).classList.contains("lb-overlay")) close();
        }}>
          <button class="lb-close" onClick={close}>&#10005;</button>
          {items.length > 1 && (
            <>
              <button class="lb-arrow lb-prev" onClick={prev}>&#8249;</button>
              <button class="lb-arrow lb-next" onClick={next}>&#8250;</button>
            </>
          )}
          <div class="lb-content">
            {current.type === "video" ? (
              <video key={current.src} controls controlsList="nodownload" autoplay class="lb-video" onContextMenu={(e) => e.preventDefault()}>
                <source src={current.src} type="video/mp4" />
              </video>
            ) : current.src.endsWith(".pdf") ? (
              <iframe key={current.src} src={current.src} class="lb-pdf" />
            ) : (
              <img src={current.src} alt={current.caption} class="lb-image" />
            )}
            <div class="lb-caption">
              {current.caption}
              {items.length > 1 && <span class="lb-counter">{open + 1} / {items.length}</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function ModalSyncedAudio({ src, transcript, who }: {
  src: string;
  transcript: Transcript;
  who?: string;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLSpanElement>(null);
  const [currentIdx, setCurrentIdx] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);

  const segments = transcript.segments || [];

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || segments.length === 0) return;

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

  const isMike = (who || transcript.who) === "mike";

  return (
    <div class={`modal-audio-card ${isMike ? "modal-audio-mike" : "modal-audio-family"}`}>
      <div class="modal-audio-meta">
        <span class="modal-audio-tape">{transcript.tape || "AUDIO"}</span>
        <span class="modal-audio-speaker">{transcript.label}</span>
        {!isMike && <span class="modal-audio-loc">DECATUR, IL</span>}
      </div>
      <audio ref={audioRef} controls controlsList="nodownload" preload="metadata" class="modal-audio-player" onContextMenu={(e) => e.preventDefault()}>
        <source src={src} type="audio/mpeg" />
      </audio>
      {segments.length > 0 ? (
        <div ref={boxRef} class="modal-subtitle-box subtitle-box">
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
      ) : (
        <div class="modal-subtitle-box">
          {transcript.text.split('. ').map((sentence, si) => (
            <span key={si}>{sentence.trim()}{si < transcript.text.split('. ').length - 1 ? '. ' : ''}</span>
          ))}
        </div>
      )}
      <div class="subtitle-hint">
        {isPlaying ? "▶ Playing — click any line to jump" : "Click ▶ to play — transcript scrolls automatically"}
      </div>
      {transcript.attribution && <div class="audio-transcript-attribution">{transcript.attribution}</div>}
    </div>
  );
}

interface Transcript {
  date: string;
  type: string;
  who: string;
  label: string;
  description: string;
  text: string;
  attribution?: string;
  tape?: string;
  match_key?: string;
  segments?: { start: number; end: number; text: string }[];
}

export default function DeploymentMap({ locations, route, dayDetails, mediaByDate, letterTranscripts, initialLocation }: {
  locations: Location[];
  route: [number, number][];
  dayDetails: Record<string, DayDetail>;
  mediaByDate: Record<string, Record<string, MediaEntry[]>>;
  letterTranscripts?: Record<string, Transcript[]>;
  initialLocation?: string;
}) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const [activePopup, setActivePopup] = useState<string | null>(initialLocation || null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [modalDate, setModalDate] = useState<string | null>(null);
  const [panelExpanded, setPanelExpanded] = useState(false);

  const [tutorialStep, setTutorialStep] = useState(() => {
    if (typeof window !== "undefined" && localStorage.getItem("map-tutorial-done")) return -1;
    return 0;
  });
  const pointerRef = useRef<HTMLDivElement>(null);

  const STEPS = [
    {
      title: "START HERE — JANUARY 16, 1968",
      text: "San Diego. The deployment begins. Click this date in the panel to see what happened.",
      pointerTarget: "[data-tutorial-id='panel-entry-1968-01-16']",
      action: () => { setModalDate("1968-01-16"); setTutorialStep(1); },
    },
    {
      title: "BROWSE THE DAY",
      text: "The logbook entry, letters, photos, and audio for this day. Scroll to explore, then click Next.",
      pointerTarget: null,
      modal: true,
      action: () => { setModalDate("1968-01-19"); setTutorialStep(2); },
    },
    {
      title: "NAVIGATE BETWEEN DAYS",
      text: "You jumped to January 19. Use PREV/NEXT or arrow keys to move through the deployment. Click Next to close and try another location.",
      pointerTarget: null,
      modal: true,
      action: () => { setModalDate(null); setActivePopup(null); setTutorialStep(3); },
    },
    {
      title: "EXPLORE THE MAP",
      text: "Click any pin to see the days at that location. Try Da Nang — where Mike anchored and met his brother Bill.",
      pointerTarget: ".pin-label",
      pointerMatch: "DA NANG",
      action: () => { setActivePopup("da-nang"); setTutorialStep(4); },
    },
    {
      title: "PICK A DATE",
      text: "The Da Nang panel lists every day at this port. Click June 13 to see that day's content.",
      pointerTarget: "[data-tutorial-id='panel-entry-1968-06-13']",
      action: () => { setModalDate("1968-06-13"); setTutorialStep(5); },
    },
    {
      title: "YOU'VE GOT IT",
      text: "Every pin. Every day. Every letter, tape, and logbook page. Explore freely.",
      pointerTarget: null,
      modal: true,
      action: () => {
        setTutorialStep(-1);
        if (typeof window !== "undefined") localStorage.setItem("map-tutorial-done", "1");
      },
    },
  ];

  useEffect(() => {
    if (tutorialStep < 0 || tutorialStep >= STEPS.length) return;
    const step = STEPS[tutorialStep];
    if (!step.pointerTarget || !pointerRef.current) return;

    const findTarget = () => {
      if ((step as any).pointerMatch) {
        const els = document.querySelectorAll(step.pointerTarget!);
        for (const el of els) {
          if (el.textContent?.trim().includes((step as any).pointerMatch)) return el;
        }
        return null;
      }
      return document.querySelector(step.pointerTarget!);
    };

    const position = () => {
      const el = findTarget();
      if (!el || !pointerRef.current) return;
      const rect = el.getBoundingClientRect();
      pointerRef.current.style.display = "block";
      pointerRef.current.style.top = `${rect.top + rect.height / 2 - 16}px`;
      pointerRef.current.style.left = `${rect.left - 36}px`;
    };

    const timer = setTimeout(position, 200);
    const interval = setInterval(position, 500);
    return () => { clearTimeout(timer); clearInterval(interval); };
  }, [tutorialStep]);

  useEffect(() => {
    if (tutorialStep < 0 || !STEPS[tutorialStep]?.pointerTarget) {
      if (pointerRef.current) pointerRef.current.style.display = "none";
    }
  }, [tutorialStep]);

  const dismissTutorial = () => {
    setTutorialStep(-1);
    if (typeof window !== "undefined") localStorage.setItem("map-tutorial-done", "1");
  };

  const resetTutorial = () => {
    setModalDate(null);
    setActivePopup("san-diego");
    setSelectedDay(null);
    setTutorialStep(0);
    if (typeof window !== "undefined") localStorage.removeItem("map-tutorial-done");
  };

  const sortedDates = useMemo(() => Object.keys(dayDetails).sort(), [dayDetails]);

  const dateToLocationId = useMemo(() => {
    const map: Record<string, string> = {};
    for (const loc of locations) {
      for (const day of loc.days) {
        map[day.date] = loc.id;
      }
    }
    return map;
  }, [locations]);

  const navigateModal = useCallback((direction: 1 | -1) => {
    if (!modalDate) return;
    const idx = sortedDates.indexOf(modalDate);
    const nextIdx = idx + direction;
    if (nextIdx < 0 || nextIdx >= sortedDates.length) return;
    const nextDate = sortedDates[nextIdx];
    setModalDate(nextDate);
    const nextLocId = dateToLocationId[nextDate];
    if (nextLocId && nextLocId !== activePopup) {
      setActivePopup(nextLocId);
    }
  }, [modalDate, sortedDates, dateToLocationId, activePopup]);

  useEffect(() => {
    if (!modalDate) return;
    function handleKey(e: KeyboardEvent) {
      if (document.querySelector(".lb-overlay")) return;
      if (e.key === "Escape") setModalDate(null);
      else if (e.key === "ArrowLeft") navigateModal(-1);
      else if (e.key === "ArrowRight") navigateModal(1);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [modalDate, navigateModal]);

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    import("leaflet").then((L) => {
      function initMap() {
        const map = L.map(mapRef.current!, {
        center: [20, -180],
        zoom: 3,
        zoomControl: false,
        attributionControl: false,
        worldCopyJump: false,
        maxBoundsViscosity: 0,
      });

      L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        { maxZoom: 12, attribution: "", noWrap: false }
      ).addTo(map);

      L.control.zoom({ position: "bottomright" }).addTo(map);

      if (route.length > 1) {
        L.polyline(route as L.LatLngExpression[], {
          color: "#C4953A",
          weight: 1.5,
          dashArray: "8, 6",
          opacity: 0.6,
        }).addTo(map);
      }

      for (const loc of locations) {
        const pinClass = loc.id === "gulf-of-tonkin" ? "pin-combat"
          : loc.id === "equator-dateline" ? "pin-ceremony"
          : "pin-port";
        const size = loc.id === "gulf-of-tonkin" ? 16 : 12;

        const icon = L.divIcon({
          className: "map-pin",
          html: `<div class="pin-marker ${pinClass}" data-loc="${loc.id}">
            <div class="pin-dot"></div>
            <div class="pin-ring"></div>
          </div>
          <div class="pin-label">${loc.name.toUpperCase()}</div>`,
          iconSize: [size, size],
          iconAnchor: [size / 2, size / 2],
        });

        const marker = L.marker([loc.lat, loc.lng], { icon }).addTo(map);

        marker.on("click", () => {
          const map = mapInstanceRef.current;
          if (map) {
            const container = map.getContainer();
            const w = container.clientWidth;
            const h = container.clientHeight;
            const isLandscape = window.matchMedia("(max-width: 768px) and (orientation: landscape)").matches;
            const isPortrait = window.matchMedia("(max-width: 768px) and (orientation: portrait)").matches;
            const pinPoint = map.latLngToContainerPoint([loc.lat, loc.lng]);
            let visibleCenterX = w / 2;
            let visibleCenterY = h / 2;
            if (isLandscape) {
              visibleCenterX = (w * 0.6) / 2;
            } else if (isPortrait) {
              visibleCenterY = (h * 0.5) / 2;
            }
            const offsetX = pinPoint.x - visibleCenterX;
            const offsetY = pinPoint.y - visibleCenterY;
            const newCenter = map.containerPointToLatLng(L.point(w / 2 + offsetX, h / 2 + offsetY));
            map.flyTo(newCenter, map.getZoom(), { duration: 0.5 });
          }
          setActivePopup(loc.id);
          setSelectedDay(null);
          setPanelExpanded(false);
        });
      }

      mapInstanceRef.current = map;

      const bounds = L.latLngBounds(locations.map((l) => [l.lat, l.lng]));
      map.fitBounds(bounds, { padding: [60, 60] });

      setTimeout(() => map.invalidateSize(), 100);
      }

      initMap();
    });

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (mapInstanceRef.current) {
      setTimeout(() => mapInstanceRef.current?.invalidateSize(), 50);
    }
  }, [activePopup]);

  const activeLoc = locations.find((l) => l.id === activePopup);
  const modalDay = modalDate ? dayDetails[modalDate] : null;
  const modalMedia = modalDate ? (mediaByDate[modalDate] || {}) : {};
  const allModalTranscripts: Transcript[] = modalDate && letterTranscripts ? (letterTranscripts[modalDate] || []) : [];
  const modalLetters = allModalTranscripts.filter(t => t.type === "letter");
  const modalFamilygrams = allModalTranscripts.filter(t => t.type === "familygram");
  const modalAudioTranscripts = allModalTranscripts.filter(t => t.type === "audio");
  const modalDocTranscripts = allModalTranscripts.filter(t => t.type === "document");
  const modalCruisebookTranscripts = allModalTranscripts.filter(t => t.type === "cruisebook");
  const modalVigilanceTranscripts = allModalTranscripts.filter(t => t.type === "vigilance");

  return (
    <div class="map-container">
      <div class="map-header">
        <div class="map-title">USS JOUETT (DLG-29) — WESTPAC DEPLOYMENT 1968</div>
        <div class="map-subtitle">TRACK CHART — 16 JAN TO 18 JUL 1968 — CONFIDENTIAL</div>
      </div>

      <div class="map-body">
        <div ref={mapRef} class="map-canvas" />

        {activeLoc && (
          <div class={`map-panel ${panelExpanded ? "panel-expanded" : ""}`}>
            <button class="panel-drag-handle" onClick={() => setPanelExpanded(!panelExpanded)} aria-label={panelExpanded ? "Collapse panel" : "Expand panel"}>
              <span class="drag-handle-bar" />
            </button>
            <div class="panel-header">
              <button class="panel-expand-toggle" onClick={() => setPanelExpanded(!panelExpanded)} aria-label={panelExpanded ? "Collapse panel" : "Expand panel"}>
                {panelExpanded ? "▸" : "◂"}
              </button>
              <div class="panel-title">{activeLoc.name.toUpperCase()}</div>
              <button class="panel-close" onClick={() => { setActivePopup(null); setSelectedDay(null); setPanelExpanded(false); }}>
                &#10005;
              </button>
            </div>
            <div class="panel-desc">{activeLoc.description}</div>
            <div class="panel-stats">
              {activeLoc.days.length} DAY{activeLoc.days.length !== 1 ? "S" : ""} &mdash;{" "}
              {formatDate(activeLoc.days[0].date)} TO {formatDate(activeLoc.days[activeLoc.days.length - 1].date)}
            </div>

            <div class="panel-entries">
              {activeLoc.days.map((day) => (
                <button
                  key={day.date}
                  data-tutorial-id={`panel-entry-${day.date}`}
                  class={`panel-entry ${day.significant ? "entry-sig" : ""} ${selectedDay === day.date ? "entry-active" : ""}`}
                  onMouseEnter={() => setSelectedDay(day.date)}
                  onClick={() => setModalDate(day.date)}
                >
                  <span class="entry-date">{formatDate(day.date)}</span>
                  <span class="entry-day">
                    {day.day_number != null ? `D+${day.day_number}` : ""}
                  </span>
                  <span class="entry-badges">
                    {day.significant && <span class="entry-star">★</span>}
                    {day.media.map((b) => (
                      <span key={b} class={`map-badge map-badge-${b.toLowerCase()}`}>{b}</span>
                    ))}
                  </span>
                  <span class="entry-text">{day.entry}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div class="map-legend">
        <span class="legend-item"><span class="legend-dot legend-port"></span> PORT</span>
        <span class="legend-item"><span class="legend-dot legend-combat"></span> OPERATIONS</span>
        <span class="legend-item"><span class="legend-dot legend-ceremony"></span> CEREMONY</span>
        <span class="legend-item"><span class="legend-line"></span> TRACK</span>
        <span class="legend-item"><span class="legend-star">★</span> KEY EVENT</span>
        {tutorialStep === -1 && (
          <button class="legend-item tutorial-restart" onClick={resetTutorial} title="Replay tutorial">?</button>
        )}
      </div>

      <div ref={pointerRef} class="tutorial-pointer" style="display:none">
        <span class="tutorial-pointer-arrow">▶</span>
      </div>

      {tutorialStep >= 0 && tutorialStep < STEPS.length && (
        <div class={`tutorial-overlay ${(STEPS[tutorialStep] as any).modal ? "tutorial-over-modal" : ""}`}>
          <div class="tutorial-card">
            <div class="tutorial-step-indicator">
              {STEPS.map((_, i) => (
                <span key={i} class={`tutorial-dot ${i === tutorialStep ? "active" : ""} ${i < tutorialStep ? "done" : ""}`} />
              ))}
            </div>
            <div class="tutorial-title">{STEPS[tutorialStep].title}</div>
            <div class="tutorial-text">{STEPS[tutorialStep].text}</div>
            <div class="tutorial-actions">
              <button class="tutorial-skip" onClick={dismissTutorial}>Skip tour</button>
              <button class="tutorial-next" onClick={STEPS[tutorialStep].action}>
                {tutorialStep === STEPS.length - 1 ? "Start exploring" : "Next →"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Day detail modal */}
      {modalDay && (
        <div class="day-modal-overlay" onClick={(e) => {
          if ((e.target as HTMLElement).classList.contains("day-modal-overlay")) setModalDate(null);
        }}>
          <div class="day-modal">
            <div class="day-modal-header">
              <div>
                <div class="day-modal-daynum">
                  {modalDay.day_number != null ? `DAY ${modalDay.day_number} OF 184` : ""}
                </div>
                <div class="day-modal-date">{formatDateLong(modalDay.date)}</div>
                {modalDay.location && <div class="day-modal-loc">{modalDay.location}</div>}
              </div>
              <div class="day-modal-actions">
                <div class="day-modal-nav">
                  <button
                    class="day-modal-nav-btn"
                    onClick={() => navigateModal(-1)}
                    disabled={sortedDates.indexOf(modalDay.date) === 0}
                    title="Previous day"
                  >&larr; PREV</button>
                  <button
                    class="day-modal-nav-btn"
                    onClick={() => navigateModal(1)}
                    disabled={sortedDates.indexOf(modalDay.date) === sortedDates.length - 1}
                    title="Next day"
                  >NEXT &rarr;</button>
                </div>
                <a href={`/day/${modalDay.date}`} class="day-modal-link">OPEN IN TIMELINE &rarr;</a>
                <button class="day-modal-close" onClick={() => setModalDate(null)}>&#10005;</button>
              </div>
            </div>

            <div class="day-modal-body">
              {modalDay.entries.length > 0 && (
                <div class="day-modal-logbook">
                  <div class="day-modal-label">LOGBOOK</div>
                  {modalDay.entries.map((e, i) => (
                    <p key={i}>{e}</p>
                  ))}
                </div>
              )}

              {modalMedia.logbook && modalMedia.logbook.length > 0 && (
                <ModalLightbox items={modalMedia.logbook} label="ORIGINAL LOGBOOK PAGE" />
              )}

              {modalDay.quotes.length > 0 && modalDay.quotes.map((q, i) => (
                <div key={i} class={q.startsWith("Context:") || q.startsWith("Meanwhile") ? "day-modal-context" : "day-modal-quote"}>
                  <p>{q}</p>
                </div>
              ))}

              {modalMedia.photos && modalMedia.photos.length > 0 && (
                <ModalLightbox items={modalMedia.photos} label="PHOTOS" />
              )}

              {modalMedia.video && modalMedia.video.length > 0 && (
                <ModalLightbox items={modalMedia.video} label="VIDEO" />
              )}

              {modalLetters.length > 0 && (
                <div class="modal-media-section">
                  <div class="modal-media-label">LETTERS</div>
                  {modalLetters.map((lt, i) => (
                    <details key={i} open class={`letter-transcript letter-${lt.who}`}>
                      <summary class="letter-header">
                        <span class="letter-from">{lt.label}</span>
                        <span class="letter-desc">{lt.description}</span>
                      </summary>
                      <div class="letter-body">
                        {lt.text.split('\n').map((line, j) => (
                          line.trim() === '' ? <br key={j} /> : <p key={j}>{line}</p>
                        ))}
                      </div>
                      {lt.attribution && <div class="transcript-attribution">{lt.attribution}</div>}
                    </details>
                  ))}
                </div>
              )}

              {modalMedia.letters && modalMedia.letters.length > 0 && (
                <ModalLightbox items={modalMedia.letters} label={modalLetters.length > 0 ? "ORIGINAL SCANS" : "LETTERS"} />
              )}

              {modalFamilygrams.length > 0 && (
                <div class="modal-media-section">
                  <div class="modal-media-label">FAMILYGRAM</div>
                  {modalFamilygrams.map((fg, i) => (
                    <details key={i} class={`letter-transcript letter-${fg.who}`}>
                      <summary class="letter-header">
                        <span class="letter-from">{fg.label}</span>
                        <span class="letter-desc">{fg.description}</span>
                      </summary>
                      <div class="letter-body">
                        {fg.text.split('\n').map((line, j) => (
                          line.trim() === '' ? <br key={j} /> : <p key={j}>{line}</p>
                        ))}
                      </div>
                      {fg.attribution && <div class="transcript-attribution">{fg.attribution}</div>}
                    </details>
                  ))}
                </div>
              )}

              {modalDocTranscripts.length > 0 && (
                <div class="modal-media-section">
                  <div class="modal-media-label">DOCUMENTS</div>
                  {modalDocTranscripts.map((dt, i) => (
                    <details key={i} class={`letter-transcript letter-${dt.who}`}>
                      <summary class="letter-header">
                        <span class="letter-from">{dt.label}</span>
                        <span class="letter-desc">{dt.description}</span>
                      </summary>
                      <div class="letter-body">
                        {dt.text.split('\n').map((line, j) => (
                          line.trim() === '' ? <br key={j} /> : <p key={j}>{line}</p>
                        ))}
                      </div>
                      {dt.attribution && <div class="transcript-attribution">{dt.attribution}</div>}
                    </details>
                  ))}
                </div>
              )}

              {modalMedia.documents && modalMedia.documents.length > 0 && (
                <ModalLightbox items={modalMedia.documents} label={modalDocTranscripts.length > 0 ? "DOCUMENT SCANS" : "DOCUMENTS"} />
              )}

              {modalVigilanceTranscripts.length > 0 && (
                <div class="modal-media-section">
                  <div class="modal-media-label">VIGILANCE MAGAZINE</div>
                  {modalVigilanceTranscripts.map((vt, i) => (
                    <details key={i} class="letter-transcript letter-ship">
                      <summary class="letter-header">
                        <span class="letter-from">{vt.label}</span>
                        <span class="letter-desc">{vt.description}</span>
                      </summary>
                      <div class="letter-body">
                        {vt.text.split('\n').map((line, j) => (
                          line.trim() === '' ? <br key={j} /> : <p key={j}>{line}</p>
                        ))}
                      </div>
                      {vt.attribution && <div class="transcript-attribution">{vt.attribution}</div>}
                    </details>
                  ))}
                </div>
              )}

              {modalMedia.slides && modalMedia.slides.length > 0 && (
                <ModalLightbox items={modalMedia.slides} label="SLIDES" />
              )}

              {modalCruisebookTranscripts.length > 0 && (
                <div class="modal-media-section">
                  <div class="modal-media-label">CRUISE BOOK</div>
                  {modalCruisebookTranscripts.map((ct, i) => (
                    <details key={i} class="letter-transcript letter-ship">
                      <summary class="letter-header">
                        <span class="letter-from">{ct.label}</span>
                        <span class="letter-desc">{ct.description}</span>
                      </summary>
                      <div class="letter-body">
                        {ct.text.split('\n').map((line, j) => (
                          line.trim() === '' ? <br key={j} /> : <p key={j}>{line}</p>
                        ))}
                      </div>
                      {ct.attribution && <div class="transcript-attribution">{ct.attribution}</div>}
                    </details>
                  ))}
                </div>
              )}

              {modalMedia.cruisebook && modalMedia.cruisebook.length > 0 && (
                <ModalLightbox items={modalMedia.cruisebook} label={modalCruisebookTranscripts.length > 0 ? "PAGE SCANS" : "CRUISE BOOK"} />
              )}

              {modalMedia.audio && modalMedia.audio.length > 0 && (
                <div class="modal-media-section">
                  <div class="modal-media-label">AUDIO RECORDINGS</div>
                  <div class="modal-audio-list">
                    {modalMedia.audio.map((a, i) => {
                      const at = modalAudioTranscripts.find(t =>
                        t.match_key && (a.caption?.includes(t.match_key) || t.match_key.includes(a.caption || ""))
                      ) || modalAudioTranscripts.find(t =>
                        a.caption?.includes(t.tape?.split(",")[0] || "___")
                      );
                      return at ? (
                        <ModalSyncedAudio key={i} src={a.src} transcript={at} who={a.who} />
                      ) : (
                        <div key={i} class={`modal-audio-card ${a.who === "family" ? "modal-audio-family" : "modal-audio-mike"}`}>
                          <div class="modal-audio-meta">
                            <span class="modal-audio-tape">{a.tape || "AUDIO"}</span>
                            <span class="modal-audio-speaker">{a.speaker || a.caption}</span>
                            {a.who === "family" && <span class="modal-audio-loc">DECATUR, IL</span>}
                          </div>
                          <audio controls controlsList="nodownload" preload="metadata" class="modal-audio-player" onContextMenu={(e) => e.preventDefault()}>
                            <source src={a.src} type="audio/mpeg" />
                          </audio>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
