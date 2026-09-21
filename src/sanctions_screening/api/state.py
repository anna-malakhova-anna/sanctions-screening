"""In-memory application state.

No database -- an explicit non-goal in the handover doc ("a database beyond
local files") -- and this is a single-process, single-session demo app:
state lives in memory for the life of the server, and the decision-log CSV
export is the durable artifact, not a background store. Restarting the
server resets to the bundled demo batch.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sanctions_screening.api.schemas import DecisionLogEntry, RowStatus, ScreeningRow, row_to_decision_log_entry
from sanctions_screening.match.engine import SearchIndex, build_search_index, match_batch
from sanctions_screening.models import Entity
from sanctions_screening.perturb.harness import LabelledPair, read_labelled_set
from sanctions_screening.snapshot import read_snapshot

BUNDLED_DIR = Path(__file__).resolve().parents[3] / "data" / "bundled"

DEFAULT_CLEAR_THRESHOLD = 0.80
DEFAULT_ESCALATE_THRESHOLD = 0.97
DEFAULT_TOP_K = 3


def _latest(pattern: str, directory: Path = BUNDLED_DIR) -> Path:
    matches = sorted(directory.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"no file matching {pattern!r} in {directory}")
    return matches[-1]


@dataclass
class AppState:
    watchlist: list[Entity]
    index: SearchIndex
    list_name: str
    list_version: str
    labelled_pairs: list[LabelledPair]
    labelled_scores: list[tuple[LabelledPair, float]]

    batch: list[ScreeningRow] = field(default_factory=list)
    batch_source: str = "(none loaded)"
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD
    escalate_threshold: float = DEFAULT_ESCALATE_THRESHOLD

    def screen(self, names: list[str], *, source: str) -> None:
        results = match_batch(names, self.index, top_k=DEFAULT_TOP_K)
        self.batch = [
            ScreeningRow(
                row_id=f"row-{i:05d}",
                query_name=name,
                candidates=candidates,
                best_score=candidates[0].score if candidates else 0.0,
            )
            for i, (name, candidates) in enumerate(zip(names, results, strict=True))
        ]
        self.batch_source = source

    def get_row(self, row_id: str) -> ScreeningRow | None:
        return next((r for r in self.batch if r.row_id == row_id), None)

    def decide(self, row_id: str, decision: str, decided_by: str, note: str | None = None) -> ScreeningRow | None:
        row = self.get_row(row_id)
        if row is None:
            return None
        row.decision = decision
        row.decided_by = decided_by
        row.decided_at = datetime.now(UTC).isoformat()
        row.decision_note = note
        return row

    def load_demo_batch(self, bundled_dir: Path = BUNDLED_DIR) -> None:
        demo_csv_path = bundled_dir / "demo_counterparties.csv"
        with demo_csv_path.open(encoding="utf-8", newline="") as f:
            names = [row["name"] for row in csv.DictReader(f)]
        self.screen(names, source="demo")

    def rows_in_review(self) -> list[ScreeningRow]:
        return [r for r in self.batch if r.status(self.clear_threshold, self.escalate_threshold) is RowStatus.REVIEW]

    def decision_log(self) -> list[DecisionLogEntry]:
        return [
            row_to_decision_log_entry(
                row,
                list_name=self.list_name,
                list_version=self.list_version,
                clear_threshold=self.clear_threshold,
                escalate_threshold=self.escalate_threshold,
            )
            for row in self.batch
        ]

    def decision_log_csv(self) -> str:
        buf = io.StringIO()
        fieldnames = list(DecisionLogEntry.model_fields.keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for entry in self.decision_log():
            writer.writerow({k: ("" if v is None else v) for k, v in entry.model_dump().items()})
        return buf.getvalue()


def load_state(bundled_dir: Path = BUNDLED_DIR) -> AppState:
    ofac_path = _latest("ofac_sdn_*.jsonl", bundled_dir)
    labelled_path = bundled_dir / "labelled_test_set.jsonl"

    watchlist = list(read_snapshot(ofac_path))
    index = build_search_index(watchlist)
    list_name = watchlist[0].list_name if watchlist else "OFAC SDN"
    list_version = watchlist[0].list_version if watchlist else "unknown"

    labelled_pairs = list(read_labelled_set(labelled_path))
    labelled_results = match_batch([p.query_name for p in labelled_pairs], index, top_k=1)
    labelled_scores = [
        (pair, results[0].score if results else 0.0) for pair, results in zip(labelled_pairs, labelled_results, strict=True)
    ]

    state = AppState(
        watchlist=watchlist,
        index=index,
        list_name=list_name,
        list_version=list_version,
        labelled_pairs=labelled_pairs,
        labelled_scores=labelled_scores,
    )

    state.load_demo_batch(bundled_dir)
    return state
