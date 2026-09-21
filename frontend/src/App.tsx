import { useEffect, useState } from "react";
import { api } from "./api";
import type { StateOut } from "./types";
import { UploadPanel } from "./components/UploadPanel";
import { ThresholdControl } from "./components/ThresholdControl";
import { RowsTable } from "./components/RowsTable";
import "./App.css";

export default function App() {
  const [state, setState] = useState<StateOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getState().then(setState).catch((e) => setError(String(e.message ?? e)));
  }, []);

  async function run(action: () => Promise<StateOut>) {
    setBusy(true);
    setError(null);
    try {
      setState(await action());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error && !state) {
    return (
      <div className="app-shell">
        <p className="app-error">Failed to load: {error}</p>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="app-shell">
        <p className="app-loading">Loading watchlist and screening the demo file…</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Sanctions Screening</h1>
        <p className="app-header__subtitle">
          Upload a counterparty file, screen it against {state.summary.list_name}, and decide where the auto-clear line sits.
        </p>
      </header>

      {error && <p className="app-error">{error}</p>}

      <section className="app-card">
        <h2>1. Counterparty file</h2>
        <UploadPanel
          summary={state.summary}
          busy={busy}
          onUpload={(file) => run(() => api.upload(file))}
          onLoadDemo={() => run(() => api.loadDemo())}
        />
      </section>

      <section className="app-card">
        <h2>2. Threshold</h2>
        <ThresholdControl metrics={state.metrics} onChange={(c, e) => run(() => api.setThresholds(c, e))} />
      </section>

      <section className="app-card">
        <h2>3. Review queue &amp; decision log</h2>
        <RowsTable
          rows={state.rows}
          busy={busy}
          onDecide={(rowId, decision) => run(() => api.decideRow(rowId, decision))}
          onSimulateReview={() => run(() => api.simulateReview())}
        />
      </section>

      <footer className="app-footer">
        Public data only (OFAC SDN + GLEIF LEI). This is a portfolio demo, not a compliance tool.
      </footer>
    </div>
  );
}
