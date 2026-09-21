import { useEffect, useRef, useState } from "react";
import type { MetricsOut } from "../types";
import { VolumeBar } from "./VolumeBar";
import { StatTile } from "./StatTile";
import "./ThresholdControl.css";

function pct(x: number | null): string {
  return x === null ? "—" : `${(x * 100).toFixed(0)}%`;
}

export function ThresholdControl({
  metrics,
  onChange,
}: {
  metrics: MetricsOut;
  onChange: (clearThreshold: number, escalateThreshold: number) => void;
}) {
  const [clearThreshold, setClearThreshold] = useState(metrics.clear_threshold);
  const [escalateThreshold, setEscalateThreshold] = useState(metrics.escalate_threshold);
  const debounceRef = useRef<number | undefined>(undefined);

  // Keep local slider position in sync when the server state changes for a
  // reason other than this slider (e.g. after upload/load-demo).
  useEffect(() => {
    setClearThreshold(metrics.clear_threshold);
    setEscalateThreshold(metrics.escalate_threshold);
  }, [metrics.clear_threshold, metrics.escalate_threshold]);

  function commit(nextClear: number, nextEscalate: number) {
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => onChange(nextClear, nextEscalate), 120);
  }

  function handleClearChange(v: number) {
    const clamped = Math.min(v, escalateThreshold);
    setClearThreshold(clamped);
    commit(clamped, escalateThreshold);
  }

  function handleEscalateChange(v: number) {
    const clamped = Math.max(v, clearThreshold);
    setEscalateThreshold(clamped);
    commit(clearThreshold, clamped);
  }

  const gt = metrics.ground_truth;

  return (
    <div className="threshold-control">
      <div className="threshold-control__sliders">
        <label className="threshold-slider">
          <span className="threshold-slider__label">
            Auto-clear below <strong className="tabular">{clearThreshold.toFixed(2)}</strong>
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={clearThreshold}
            onChange={(e) => handleClearChange(Number(e.target.value))}
          />
        </label>
        <label className="threshold-slider">
          <span className="threshold-slider__label">
            Auto-escalate at or above <strong className="tabular">{escalateThreshold.toFixed(2)}</strong>
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={escalateThreshold}
            onChange={(e) => handleEscalateChange(Number(e.target.value))}
          />
        </label>
      </div>

      <VolumeBar volume={metrics.batch_volume} />

      <div className="threshold-control__stats">
        <StatTile
          label="Recall (not missed)"
          value={pct(gt.recall_not_missed)}
          tone={gt.recall_not_missed >= 0.9 ? "good" : gt.recall_not_missed >= 0.7 ? "warning" : "critical"}
          hint="Share of known true matches in the labelled test set that are NOT silently auto-cleared -- they land in review or auto-escalate instead."
        />
        <StatTile
          label="Auto-escalate precision"
          value={pct(gt.auto_escalate_precision)}
          tone={gt.auto_escalate_precision === null ? "neutral" : gt.auto_escalate_precision >= 0.8 ? "good" : "critical"}
          hint="Of labelled rows landing in auto-escalate (flagged with no human review at all), the share that are genuinely true matches."
        />
        <StatTile
          label="Clean names auto-escalated"
          value={pct(gt.negative_auto_escalate_rate)}
          tone={gt.negative_auto_escalate_rate <= 0.02 ? "good" : "critical"}
          hint="Share of known-clean GLEIF negatives that get flagged with zero human check -- the costliest failure mode."
        />
        <StatTile
          label="Clean names sent to review"
          value={pct(gt.negative_review_rate)}
          tone="neutral"
          hint="Share of known-clean negatives that land in the review queue -- reviewer time spent on names that turn out clean."
        />
      </div>
      <p className="threshold-control__footnote">
        Ground truth from {gt.labelled_set_size} labelled rows (perturbed OFAC positives + GLEIF negatives). See README for why
        this curve is directional, not a benchmark.
      </p>
    </div>
  );
}
