import { useState, useRef, useEffect } from "preact/hooks";

interface Person {
  id: string;
  name: string;
  rank: string | null;
  role: string;
  group: string;
}

const GROUP_LABELS: Record<string, string> = {
  "ducy-family": "The Ducy Family",
  "jouett-command": "Jouett Command",
  "jouett-crew": "Jouett Crew",
  "sar-crews": "SAR Helicopter Crews",
};

const GROUP_ORDER = [
  "ducy-family",
  "jouett-command",
  "sar-crews",
  "jouett-crew",
];

export default function PeopleXray({ people }: { people: Person[] }) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  const grouped = GROUP_ORDER.map((g) => ({
    key: g,
    label: GROUP_LABELS[g] || g,
    members: people.filter((p) => p.group === g),
  })).filter((g) => g.members.length > 0);

  return (
    <div class="xray-container" ref={panelRef}>
      <button
        class="xray-trigger"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label="People"
      >
        People
      </button>

      {open && (
        <div class="xray-panel">
          <div class="xray-header">
            <span>People</span>
            <a href="/people" class="xray-see-all">
              See all &rarr;
            </a>
          </div>
          <div class="xray-list">
            {grouped.map((group) => (
              <div key={group.key} class="xray-group">
                <div class="xray-group-label">{group.label}</div>
                {group.members.map((person) => (
                  <a
                    key={person.id}
                    href={`/people#${person.id}`}
                    class="xray-person"
                    onClick={() => setOpen(false)}
                  >
                    <div class="xray-avatar">
                      {person.name
                        .split(" ")
                        .map((w) => w[0])
                        .slice(0, 2)
                        .join("")}
                    </div>
                    <div class="xray-info">
                      <div class="xray-name">
                        {person.rank && (
                          <span class="xray-rank">{person.rank}</span>
                        )}{" "}
                        {person.name}
                      </div>
                      <div class="xray-role">{person.role}</div>
                    </div>
                  </a>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
