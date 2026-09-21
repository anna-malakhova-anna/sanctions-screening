import { useMemo, useState } from "react";
import type { RowOut, RowStatus } from "../types";
import { api } from "../api";
import "./RowsTable.css";

const STATUS_META: Record<RowStatus, { label: string; tone: "good" | "warning" | "critical" | "neutral" }> = {
  auto_clear: { label: "Auto-clear", tone: "good" },
  review: { label: "Review", tone: "warning" },
  auto_escalate: { label: "Auto-escalate", tone: "critical" },
  cleared: { label: "Cleared", tone: "good" },
  escalated: { label: "Escalated", tone: "critical" },
};

const FILTERS: Array<{ key: "all" | RowStatus; label: string }> = [
  { key: "all", label: "All" },
  { key: "review", label: "Review" },
  { key: "auto_clear", label: "Auto-clear" },
  { key: "auto_escalate", label: "Auto-escalate" },
  { key: "cleared", label: "Cleared" },
  { key: "escalated", label: "Escalated" },
];

function StatusBadge({ status }: { status: RowStatus }) {
  const meta = STATUS_META[status];
  return <span className={`status-badge status-badge--${meta.tone}`}>{meta.label}</span>;
}

export function RowsTable({
  rows,
  onDecide,
  onSimulateReview,
  busy,
}: {
  rows: RowOut[];
  onDecide: (rowId: string, decision: "clear" | "escalate") => void;
  onSimulateReview: () => void;
  busy: boolean;
}) {
  const [filter, setFilter] = useState<"all" | RowStatus>("review");

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: rows.length };
    for (const r of rows) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [rows]);

  const visibleRows = filter === "all" ? rows : rows.filter((r) => r.status === filter);
  const reviewCount = counts["review"] ?? 0;

  return (
    <div className="rows-table">
      <div className="rows-table__toolbar">
        <div className="rows-table__filters">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={`filter-chip${filter === f.key ? " filter-chip--active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label} <span className="tabular">({counts[f.key] ?? 0})</span>
            </button>
          ))}
        </div>
        <div className="rows-table__actions">
          <button type="button" className="button button--secondary" onClick={onSimulateReview} disabled={busy || reviewCount === 0}>
            Simulate reviewer ({reviewCount} pending)
          </button>
          <a className="button button--secondary" href={api.decisionLogExportUrl()} download>
            Export decision log (CSV)
          </a>
        </div>
      </div>

      <div className="rows-table__scroll">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Query name</th>
              <th>Matched entity</th>
              <th>Matched alias</th>
              <th>Matcher</th>
              <th className="align-right">Score</th>
              <th>Decided by</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.row_id}>
                <td>
                  <StatusBadge status={row.status} />
                </td>
                <td>{row.query_name}</td>
                <td>{row.top_candidate?.entity_canonical_name ?? <span className="muted">no candidate</span>}</td>
                <td>{row.top_candidate?.is_alias_match ? row.top_candidate.matched_name : <span className="muted">—</span>}</td>
                <td>
                  {row.top_candidate ? (
                    <span className="matcher-tag">{row.top_candidate.matcher === "exact" ? "exact" : "Jaro-Winkler"}</span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="align-right tabular">{row.best_score.toFixed(3)}</td>
                <td>
                  {row.decided_by ? (
                    <span title={row.decision_note ?? undefined}>{row.decided_by.replace("_", " ")}</span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>
                  {row.status === "review" && (
                    <div className="row-actions">
                      <button type="button" className="button button--tiny button--good" onClick={() => onDecide(row.row_id, "clear")}>
                        Clear
                      </button>
                      <button
                        type="button"
                        className="button button--tiny button--critical"
                        onClick={() => onDecide(row.row_id, "escalate")}
                      >
                        Escalate
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {visibleRows.length === 0 && (
              <tr>
                <td colSpan={8} className="rows-table__empty">
                  No rows in this bucket at the current thresholds.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
