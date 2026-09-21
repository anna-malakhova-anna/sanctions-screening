"""FastAPI app: the Decide stage.

Upload a counterparty file (or load the bundled demo one), screen it against
the OFAC watchlist, move the threshold slider and watch review volume and
ground-truth precision/recall update live, resolve the review queue by hand
or via the simulated reviewer, export the decision log.

Every mutating endpoint returns the same StateOut shape (summary + every row
at current thresholds + live metrics), so the frontend is a "replace state
with response" client rather than juggling partial updates.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from sanctions_screening.api.metrics import compute_ground_truth_metrics, compute_volume_breakdown
from sanctions_screening.api.schemas import (
    BatchSummary,
    DecisionRequest,
    MetricsOut,
    StateOut,
    ThresholdSettings,
    row_to_out,
)
from sanctions_screening.api.simulate import simulated_decision
from sanctions_screening.api.state import AppState, load_state

STATE: AppState | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global STATE
    STATE = load_state()
    yield


app = FastAPI(title="Sanctions Screening Demo", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_state() -> AppState:
    if STATE is None:
        raise HTTPException(status_code=503, detail="app state not initialized")
    return STATE


def _state_out(state: AppState) -> StateOut:
    summary = BatchSummary(
        batch_source=state.batch_source,
        list_name=state.list_name,
        list_version=state.list_version,
        watchlist_size=len(state.watchlist),
        total_rows=len(state.batch),
        clear_threshold=state.clear_threshold,
        escalate_threshold=state.escalate_threshold,
    )
    rows = [row_to_out(r, state.clear_threshold, state.escalate_threshold) for r in state.batch]
    ground_truth = compute_ground_truth_metrics(state.labelled_scores, state.clear_threshold, state.escalate_threshold)
    volume = compute_volume_breakdown(state.batch, state.clear_threshold, state.escalate_threshold)
    metrics = MetricsOut(
        clear_threshold=state.clear_threshold,
        escalate_threshold=state.escalate_threshold,
        ground_truth=ground_truth,
        batch_volume=volume,
    )
    return StateOut(summary=summary, rows=rows, metrics=metrics)


@app.get("/api/state", response_model=StateOut)
def get_full_state() -> StateOut:
    return _state_out(get_state())


@app.post("/api/load-demo", response_model=StateOut)
def load_demo() -> StateOut:
    state = get_state()
    state.load_demo_batch()
    return _state_out(state)


@app.post("/api/upload", response_model=StateOut)
async def upload(file: UploadFile) -> StateOut:
    state = get_state()
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="file must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    name_field = next((f for f in fieldnames if f.strip().lower() == "name"), None)
    if name_field is None:
        raise HTTPException(status_code=400, detail="CSV must have a 'name' column")

    names = [row[name_field].strip() for row in reader if row.get(name_field, "").strip()]
    if not names:
        raise HTTPException(status_code=400, detail="no rows found in uploaded file")

    state.screen(names, source=file.filename or "uploaded file")
    return _state_out(state)


@app.put("/api/thresholds", response_model=StateOut)
def set_thresholds(settings: ThresholdSettings) -> StateOut:
    if not (0.0 <= settings.clear_threshold <= settings.escalate_threshold <= 1.0):
        raise HTTPException(status_code=400, detail="require 0 <= clear_threshold <= escalate_threshold <= 1")
    state = get_state()
    state.clear_threshold = settings.clear_threshold
    state.escalate_threshold = settings.escalate_threshold
    return _state_out(state)


@app.post("/api/rows/{row_id}/decision", response_model=StateOut)
def decide_row(row_id: str, body: DecisionRequest) -> StateOut:
    state = get_state()
    row = state.decide(row_id, body.decision, decided_by="human")
    if row is None:
        raise HTTPException(status_code=404, detail=f"no row {row_id!r}")
    return _state_out(state)


@app.post("/api/simulate-review", response_model=StateOut)
def simulate_review() -> StateOut:
    state = get_state()
    for row in state.rows_in_review():
        decision, note = simulated_decision(row, state.clear_threshold, state.escalate_threshold)
        state.decide(row.row_id, decision, decided_by="simulated_reviewer", note=note)
    return _state_out(state)


@app.get("/api/decision-log/export")
def export_decision_log() -> StreamingResponse:
    state = get_state()
    csv_text = state.decision_log_csv()
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="decision-log-{state.list_version}.csv"'},
    )


# Serve the built frontend, if present, so a single `uvicorn` process is
# enough to run the whole app -- no separate frontend server needed to demo
# or host it. In dev, the frontend runs separately via `npm run dev` and
# proxies /api to this server instead; see frontend/README or vite.config.
_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
