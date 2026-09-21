"""API-facing models: the Decide stage's data shapes.

ScreeningRow is the server's internal record of one screened row. Its status
is *derived*, not stored, from (best_score, current thresholds) -- unless a
human or the simulated reviewer has already resolved it, in which case that
decision is authoritative no matter where the threshold sliders sit
afterward. That split is what makes "move the slider, watch the
auto-clear/review/escalate counts update live" possible without re-running
the matcher, while never silently overturning a decision someone already
made.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from sanctions_screening.match.engine import MatchCandidate


class RowStatus(str, Enum):
    AUTO_CLEAR = "auto_clear"
    REVIEW = "review"
    AUTO_ESCALATE = "auto_escalate"
    CLEARED = "cleared"
    ESCALATED = "escalated"


class ScreeningRow(BaseModel):
    row_id: str
    query_name: str
    candidates: list[MatchCandidate]
    best_score: float
    decision: Literal["clear", "escalate"] | None = None
    decided_by: Literal["human", "simulated_reviewer"] | None = None
    decided_at: str | None = None
    decision_note: str | None = None

    def status(self, clear_threshold: float, escalate_threshold: float) -> RowStatus:
        if self.decision == "clear":
            return RowStatus.CLEARED
        if self.decision == "escalate":
            return RowStatus.ESCALATED
        if self.best_score < clear_threshold:
            return RowStatus.AUTO_CLEAR
        if self.best_score >= escalate_threshold:
            return RowStatus.AUTO_ESCALATE
        return RowStatus.REVIEW

    @property
    def top_candidate(self) -> MatchCandidate | None:
        return self.candidates[0] if self.candidates else None


class RowOut(BaseModel):
    row_id: str
    query_name: str
    best_score: float
    status: RowStatus
    top_candidate: MatchCandidate | None
    candidates: list[MatchCandidate]
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None


def row_to_out(row: ScreeningRow, clear_threshold: float, escalate_threshold: float) -> RowOut:
    return RowOut(
        row_id=row.row_id,
        query_name=row.query_name,
        best_score=row.best_score,
        status=row.status(clear_threshold, escalate_threshold),
        top_candidate=row.top_candidate,
        candidates=row.candidates,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        decision_note=row.decision_note,
    )


class ThresholdSettings(BaseModel):
    clear_threshold: float
    escalate_threshold: float


class BatchSummary(BaseModel):
    batch_source: str
    list_name: str
    list_version: str
    watchlist_size: int
    total_rows: int
    clear_threshold: float
    escalate_threshold: float


class VolumeBreakdown(BaseModel):
    auto_clear: int
    review: int
    auto_escalate: int
    cleared: int
    escalated: int
    total: int


class GroundTruthMetrics(BaseModel):
    """Computed against the labelled test set (perturbed OFAC positives +
    GLEIF negatives) -- the only place we actually know the right answer."""

    labelled_set_size: int
    recall_not_missed: float
    auto_escalate_precision: float | None
    negative_auto_escalate_rate: float
    negative_review_rate: float


class MetricsOut(BaseModel):
    clear_threshold: float
    escalate_threshold: float
    ground_truth: GroundTruthMetrics
    batch_volume: VolumeBreakdown


class StateOut(BaseModel):
    """The full picture the frontend needs after any mutating call (upload,
    load-demo, threshold change, decision, simulate-review): summary, every
    row at the current thresholds, and the live metrics. Returning all three
    together keeps the frontend a dumb "replace state with response" client
    rather than juggling partial updates."""

    summary: BatchSummary
    rows: list[RowOut]
    metrics: MetricsOut


class DecisionRequest(BaseModel):
    decision: Literal["clear", "escalate"]


class DecisionLogEntry(BaseModel):
    """One row of the exportable decision log: list version, matched alias,
    rule (matcher), score, and reviewer -- per the handover doc's "export
    showing list version, matched alias, rule, score and reviewer per row.\""""

    row_id: str
    query_name: str
    list_name: str
    list_version: str
    matched_entity_source_id: str | None
    matched_entity_name: str | None
    matched_alias: str | None
    matcher: str | None
    score: float
    status: RowStatus
    reviewer: str
    decided_at: str | None


def row_to_decision_log_entry(
    row: ScreeningRow, *, list_name: str, list_version: str, clear_threshold: float, escalate_threshold: float
) -> DecisionLogEntry:
    top = row.top_candidate
    status = row.status(clear_threshold, escalate_threshold)
    if row.decided_by:
        reviewer = row.decided_by
    elif status is RowStatus.AUTO_CLEAR:
        reviewer = "auto_clear_threshold"
    elif status is RowStatus.AUTO_ESCALATE:
        reviewer = "auto_escalate_threshold"
    else:
        reviewer = "unreviewed"

    return DecisionLogEntry(
        row_id=row.row_id,
        query_name=row.query_name,
        list_name=list_name,
        list_version=list_version,
        matched_entity_source_id=top.source_id if top else None,
        matched_entity_name=top.entity_canonical_name if top else None,
        matched_alias=top.matched_name if top and top.is_alias_match else None,
        matcher=top.matcher.value if top else None,
        score=row.best_score,
        status=status,
        reviewer=reviewer,
        decided_at=row.decided_at,
    )
