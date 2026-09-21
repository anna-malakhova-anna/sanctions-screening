import { useRef, useState } from "react";
import type { BatchSummary } from "../types";
import "./UploadPanel.css";

export function UploadPanel({
  summary,
  onUpload,
  onLoadDemo,
  busy,
}: {
  summary: BatchSummary;
  onUpload: (file: File) => void;
  onLoadDemo: () => void;
  busy: boolean;
}) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFiles(files: FileList | null) {
    setError(null);
    const file = files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please upload a .csv file with a 'name' column.");
      return;
    }
    onUpload(file);
  }

  return (
    <div className="upload-panel">
      <div
        className={`upload-panel__dropzone${dragOver ? " upload-panel__dropzone--over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
        <p className="upload-panel__hint">
          Drop a CSV with a <code>name</code> column, or click to browse
        </p>
      </div>

      <div className="upload-panel__meta">
        <button type="button" className="button button--secondary" onClick={onLoadDemo} disabled={busy}>
          Load demo file
        </button>
        <div className="upload-panel__summary">
          <div>
            Source: <strong>{summary.batch_source}</strong> ({summary.total_rows} rows)
          </div>
          <div className="upload-panel__summary-muted">
            Screened against {summary.list_name} v{summary.list_version} ({summary.watchlist_size.toLocaleString()} entities)
          </div>
        </div>
      </div>

      {error && <p className="upload-panel__error">{error}</p>}
    </div>
  );
}
