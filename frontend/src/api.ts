import type { StateOut } from "./types";

const BASE = "/api";

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(body.detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  getState: (): Promise<StateOut> => fetch(`${BASE}/state`).then((r) => handle<StateOut>(r)),

  loadDemo: (): Promise<StateOut> => fetch(`${BASE}/load-demo`, { method: "POST" }).then((r) => handle<StateOut>(r)),

  upload: (file: File): Promise<StateOut> => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE}/upload`, { method: "POST", body: form }).then((r) => handle<StateOut>(r));
  },

  setThresholds: (clearThreshold: number, escalateThreshold: number): Promise<StateOut> =>
    fetch(`${BASE}/thresholds`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clear_threshold: clearThreshold, escalate_threshold: escalateThreshold }),
    }).then((r) => handle<StateOut>(r)),

  decideRow: (rowId: string, decision: "clear" | "escalate"): Promise<StateOut> =>
    fetch(`${BASE}/rows/${encodeURIComponent(rowId)}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    }).then((r) => handle<StateOut>(r)),

  simulateReview: (): Promise<StateOut> => fetch(`${BASE}/simulate-review`, { method: "POST" }).then((r) => handle<StateOut>(r)),

  decisionLogExportUrl: (): string => `${BASE}/decision-log/export`,
};
