import { useState, useMemo, useEffect } from "preact/hooks";
import { readHash, mediaSlug, scrollToEl } from "../lib/deeplink";

type ArchiveItem = {
  id: string;
  category: string;
  subcategory?: string;
  date: string | null;
  description: string;
  web_path: string;
  thumb_path?: string;
  transcript?: {
    label: string;
    who: string;
    text: string;
    attribution?: string;
  };
  pageCount?: number;
  timelineDate?: string;
};

type Props = {
  items: ArchiveItem[];
  mediaUrl: string;
};

const TABS = [
  { key: "letters", label: "Letters", icon: "✉" },
  { key: "audio", label: "Audio", icon: "♪" },
  { key: "logbook", label: "Logbook", icon: "📓" },
  { key: "documents", label: "Documents", icon: "📄" },
  { key: "photos", label: "Photos", icon: "📷" },
  { key: "slides", label: "Slides", icon: "🎞" },
  { key: "video", label: "Video", icon: "🎬" },
  { key: "cruisebook", label: "Cruise Book", icon: "📖" },
];

const WHO_LABELS: Record<string, string> = {
  mike: "Mike Ducy",
  bill: "Bill Ducy",
  family: "Family",
  given: "W.F. Given",
  norris: "A.R. Norris",
  ship: "USS Jouett",
};

function formatDate(d: string | null): string {
  if (!d) return "Date unknown";
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const [y, m, day] = d.split("-");
  return `${months[parseInt(m) - 1]} ${parseInt(day)}, ${y}`;
}

function m(path: string, mediaUrl: string): string {
  if (!mediaUrl) return path;
  return mediaUrl + path.replace(/^\/media/, "");
}

const VALID_TABS = new Set(TABS.map(t => t.key));

function getInitialTab(): string {
  if (typeof window !== "undefined") {
    const { key } = readHash();
    if (VALID_TABS.has(key)) return key;
  }
  return "letters";
}

export default function MediaArchive({ items, mediaUrl }: Props) {
  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"date" | "description">("date");
  const [pendingTarget, setPendingTarget] = useState(() => readHash().target);

  useEffect(() => {
    if (lightboxSrc && (window as any).gtag) {
      const isVideo = lightboxSrc.endsWith(".mp4") || lightboxSrc.endsWith(".webm");
      (window as any).gtag("event", "lightbox_view", { event_category: "media", media_type: isVideo ? "video" : "image", media_url: lightboxSrc });
    }
  }, [lightboxSrc]);

  function switchTab(key: string) {
    setActiveTab(key);
    setExpandedId(null);
    window.history.replaceState(null, "", `#${key}`);
  }

  useEffect(() => {
    const { key } = readHash();
    if (VALID_TABS.has(key) && key !== activeTab) {
      setActiveTab(key);
      setExpandedId(null);
    }
    function onHashChange() {
      const { key: k, target } = readHash();
      if (VALID_TABS.has(k)) {
        setActiveTab(k);
        setExpandedId(null);
        setPendingTarget(target);
      }
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const item of items) {
      c[item.category] = (c[item.category] || 0) + 1;
    }
    return c;
  }, [items]);

  const filtered = useMemo(() => {
    let f = items.filter((i) => i.category === activeTab);
    if (sortBy === "date") {
      f.sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999"));
    } else {
      f.sort((a, b) => a.description.localeCompare(b.description));
    }

    if (activeTab === "letters") {
      const grouped: Record<string, ArchiveItem[]> = {};
      for (const item of f) {
        const dateKey = item.date || "unknown";
        if (!grouped[dateKey]) grouped[dateKey] = [];
        grouped[dateKey].push(item);
      }
      return { type: "grouped" as const, groups: grouped, flat: f };
    }
    return { type: "flat" as const, flat: f, groups: {} };
  }, [items, activeTab, sortBy]);

  const isGrid = ["photos", "slides", "video"].includes(activeTab);

  useEffect(() => {
    if (!pendingTarget) return;
    const target = pendingTarget;
    setPendingTarget("");
    if (filtered.type === "grouped" && filtered.groups[target]) {
      setExpandedId(target);
      scrollToEl(document.querySelector(`[data-anchor="${CSS.escape(target)}"]`));
      return;
    }
    const item = filtered.flat.find((i) => mediaSlug(i.web_path) === target)
      || filtered.flat.find((i) => i.date === target);
    if (!item) return;
    if (isGrid) {
      setLightboxSrc(m(item.web_path, mediaUrl));
    } else if (item.transcript) {
      setExpandedId(item.id);
    }
    scrollToEl(document.querySelector(`[data-anchor="${CSS.escape(mediaSlug(item.web_path))}"]`));
  }, [pendingTarget, filtered]);

  return (
    <div class="archive-container">
      <div class="archive-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            class={`archive-tab ${activeTab === tab.key ? "active" : ""}`}
            onClick={() => switchTab(tab.key)}
          >
            <span class="tab-label">{tab.label}</span>
            {counts[tab.key] && <span class="tab-count">{counts[tab.key]}</span>}
          </button>
        ))}
      </div>

      <div class="archive-toolbar">
        <span class="archive-result-count">
          {filtered.flat.length} item{filtered.flat.length !== 1 ? "s" : ""}
        </span>
        <div class="archive-sort">
          <label>Sort:</label>
          <select value={sortBy} onChange={(e) => setSortBy((e.target as HTMLSelectElement).value as any)}>
            <option value="date">Date</option>
            <option value="description">Description</option>
          </select>
        </div>
      </div>

      <div class={`archive-content ${isGrid ? "archive-grid" : "archive-list"}`}>
        {isGrid ? (
          filtered.flat.map((item) => {
            const isVideo = item.web_path.endsWith(".mp4") || item.web_path.endsWith(".webm");
            const src = m(item.thumb_path || item.web_path, mediaUrl);
            return (
              <div key={item.id} data-anchor={mediaSlug(item.web_path)} class={`archive-grid-item ${isVideo ? "archive-grid-video-item" : ""}`} onClick={() => setLightboxSrc(m(item.web_path, mediaUrl))}>
                <img src={src} alt={item.description} loading="lazy" />
                {isVideo && <span class="grid-play-badge">&#9654;</span>}
                <div class="grid-item-caption">
                  <span class="grid-item-date">{formatDate(item.date)}</span>
                  <span class="grid-item-desc">{item.description}</span>
                </div>
              </div>
            );
          })
        ) : activeTab === "letters" && filtered.type === "grouped" ? (
          Object.entries(filtered.groups).map(([date, group]) => {
            const first = group[0];
            const transcript = first.transcript;
            const isExpanded = expandedId === date;
            return (
              <div key={date} data-anchor={date} class={`archive-list-item ${transcript ? "has-transcript" : ""}`}>
                <div class="list-item-main" onClick={() => setExpandedId(isExpanded ? null : date)}>
                  <div class="list-item-thumb-stack">
                    <img
                      src={m(first.thumb_path || first.web_path, mediaUrl)}
                      alt={first.description}
                      loading="lazy"
                    />
                    {group.length > 1 && <span class="page-count">{group.length} pages</span>}
                  </div>
                  <div class="list-item-info">
                    <div class="list-item-title">
                      {transcript ? transcript.label : first.description}
                    </div>
                    <div class="list-item-date">{formatDate(date)}</div>
                    {transcript && (
                      <div class="list-item-preview">
                        {transcript.text.substring(0, 150).replace(/\n/g, " ")}...
                      </div>
                    )}
                    <div class="list-item-meta">
                      {transcript && <span class="meta-tag">Transcript</span>}
                      {first.subcategory && (
                        <span class="meta-who">{WHO_LABELS[first.subcategory] || first.subcategory}</span>
                      )}
                      {first.timelineDate && (
                        <a
                          href={`/day/${first.timelineDate}`}
                          class="meta-timeline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          View in timeline →
                        </a>
                      )}
                    </div>
                  </div>
                  <span class={`list-item-chevron ${isExpanded ? "expanded" : ""}`}>▾</span>
                </div>
                {isExpanded && transcript && (
                  <div class="list-item-transcript">
                    <div class="transcript-text">
                      {transcript.text.split("\n").map((line, i) =>
                        line.trim() === "" ? <br key={i} /> : <p key={i}>{line}</p>
                      )}
                    </div>
                    {transcript.attribution && (
                      <div class="transcript-attribution">{transcript.attribution}</div>
                    )}
                    {group.length > 0 && (
                      <div class="transcript-scans">
                        <h4>Original Scans</h4>
                        <div class="scan-thumbs">
                          {group.map((page, i) => (
                            <img
                              key={i}
                              src={m(page.thumb_path || page.web_path, mediaUrl)}
                              alt={`Page ${i + 1}`}
                              loading="lazy"
                              onClick={() => setLightboxSrc(m(page.web_path, mediaUrl))}
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          filtered.flat.map((item) => {
            const isExpanded = expandedId === item.id;
            const transcript = item.transcript;
            return (
              <div key={item.id} data-anchor={mediaSlug(item.web_path)} class={`archive-list-item ${transcript ? "has-transcript" : ""}`}>
                <div class="list-item-main" onClick={() => transcript && setExpandedId(isExpanded ? null : item.id)}>
                  {activeTab !== "audio" && (
                    <div class="list-item-thumb-stack">
                      <img
                        src={m(item.thumb_path || item.web_path, mediaUrl)}
                        alt={item.description}
                        loading="lazy"
                        onClick={(e) => {
                          if (activeTab !== "audio") {
                            e.stopPropagation();
                            setLightboxSrc(m(item.web_path, mediaUrl));
                          }
                        }}
                      />
                    </div>
                  )}
                  <div class="list-item-info">
                    <div class="list-item-title">
                      {transcript ? transcript.label : item.description}
                    </div>
                    <div class="list-item-date">{formatDate(item.date)}</div>
                    {activeTab === "audio" && (
                      <audio controls controlsList="nodownload" preload="metadata" class="archive-audio" onContextMenu={(e) => e.preventDefault()}>
                        <source src={m(item.web_path, mediaUrl)} type="audio/mpeg" />
                      </audio>
                    )}
                    {transcript && !isExpanded && (
                      <div class="list-item-preview">
                        {transcript.text.substring(0, 120).replace(/\n/g, " ")}...
                      </div>
                    )}
                    <div class="list-item-meta">
                      {transcript && <span class="meta-tag">Transcript</span>}
                      {item.subcategory && (
                        <span class="meta-who">
                          {WHO_LABELS[item.subcategory] || item.subcategory}
                        </span>
                      )}
                      {item.timelineDate && (
                        <a
                          href={`/day/${item.timelineDate}`}
                          class="meta-timeline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          View in timeline →
                        </a>
                      )}
                    </div>
                  </div>
                  {transcript && <span class={`list-item-chevron ${isExpanded ? "expanded" : ""}`}>▾</span>}
                </div>
                {isExpanded && transcript && (
                  <div class="list-item-transcript">
                    <div class="transcript-text">
                      {transcript.text.split("\n").map((line, i) =>
                        line.trim() === "" ? <br key={i} /> : <p key={i}>{line}</p>
                      )}
                    </div>
                    {transcript.attribution && (
                      <div class="transcript-attribution">{transcript.attribution}</div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {lightboxSrc && (
        <div class="archive-lightbox" onClick={() => setLightboxSrc(null)}>
          {lightboxSrc.endsWith(".mp4") || lightboxSrc.endsWith(".webm") ? (
            <video src={lightboxSrc} controls controlsList="nodownload" autoplay class="archive-lb-video" onClick={(e) => e.stopPropagation()} onContextMenu={(e) => e.preventDefault()} />
          ) : (
            <img src={lightboxSrc} alt="" onClick={(e) => e.stopPropagation()} />
          )}
          <button class="archive-lb-close" onClick={() => setLightboxSrc(null)}>✕</button>
        </div>
      )}
    </div>
  );
}
