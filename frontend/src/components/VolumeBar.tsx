import type { VolumeBreakdown } from "../types";
import "./VolumeBar.css";

interface Segment {
  key: string;
  label: string;
  count: number;
  color: string;
}

export function VolumeBar({ volume }: { volume: VolumeBreakdown }) {
  const segments: Segment[] = [
    { key: "clear", label: "Clear", count: volume.auto_clear + volume.cleared, color: "var(--status-good)" },
    { key: "review", label: "Review", count: volume.review, color: "var(--status-warning)" },
    { key: "escalate", label: "Escalate", count: volume.auto_escalate + volume.escalated, color: "var(--status-critical)" },
  ];
  const total = volume.total || 1;

  return (
    <div className="volume-bar-wrap">
      <div className="volume-bar" role="img" aria-label={segments.map((s) => `${s.label}: ${s.count}`).join(", ")}>
        {segments.map((s) => {
          const pct = (s.count / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={s.key}
              className="volume-bar__segment"
              style={{ width: `${pct}%`, background: s.color }}
              title={`${s.label}: ${s.count} rows (${pct.toFixed(0)}%)`}
            >
              {pct >= 10 && <span className="volume-bar__segment-label tabular">{s.count}</span>}
            </div>
          );
        })}
      </div>
      <div className="volume-bar__legend">
        {segments.map((s) => (
          <span key={s.key} className="volume-bar__legend-item">
            <span className="volume-bar__swatch" style={{ background: s.color }} />
            {s.label} <span className="tabular">({s.count})</span>
          </span>
        ))}
      </div>
    </div>
  );
}
