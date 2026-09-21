"""Metrics for the threshold control.

Ground-truth precision/recall come from the labelled test set (the only
place we know the right answer); review-volume comes from whatever batch is
currently loaded. Both are pure functions over *precomputed* scores and the
current thresholds -- no re-matching -- so moving the threshold slider is
just re-bucketing numbers already sitting in memory, cheap enough to call on
every tick.
"""

from __future__ import annotations

from collections.abc import Sequence

from sanctions_screening.api.schemas import GroundTruthMetrics, RowStatus, ScreeningRow, VolumeBreakdown
from sanctions_screening.perturb.harness import LabelledPair


def labelled_row_status(best_score: float, clear_threshold: float, escalate_threshold: float) -> RowStatus:
    """Same three-way bucketing as ScreeningRow.status, but for a labelled
    pair, which never has a human decision to defer to."""
    if best_score < clear_threshold:
        return RowStatus.AUTO_CLEAR
    if best_score >= escalate_threshold:
        return RowStatus.AUTO_ESCALATE
    return RowStatus.REVIEW


def compute_ground_truth_metrics(
    labelled_scores: Sequence[tuple[LabelledPair, float]],
    clear_threshold: float,
    escalate_threshold: float,
) -> GroundTruthMetrics:
    n_positive = n_positive_not_missed = 0
    n_auto_escalate = n_auto_escalate_true_positive = 0
    n_negative = n_negative_auto_escalate = n_negative_review = 0

    for pair, score in labelled_scores:
        status = labelled_row_status(score, clear_threshold, escalate_threshold)
        if pair.is_positive:
            n_positive += 1
            if status is not RowStatus.AUTO_CLEAR:
                n_positive_not_missed += 1
            if status is RowStatus.AUTO_ESCALATE:
                n_auto_escalate += 1
                n_auto_escalate_true_positive += 1
        else:
            n_negative += 1
            if status is RowStatus.AUTO_ESCALATE:
                n_auto_escalate += 1
                n_negative_auto_escalate += 1
            elif status is RowStatus.REVIEW:
                n_negative_review += 1

    return GroundTruthMetrics(
        labelled_set_size=len(labelled_scores),
        recall_not_missed=(n_positive_not_missed / n_positive) if n_positive else 0.0,
        auto_escalate_precision=(n_auto_escalate_true_positive / n_auto_escalate) if n_auto_escalate else None,
        negative_auto_escalate_rate=(n_negative_auto_escalate / n_negative) if n_negative else 0.0,
        negative_review_rate=(n_negative_review / n_negative) if n_negative else 0.0,
    )


def compute_volume_breakdown(rows: Sequence[ScreeningRow], clear_threshold: float, escalate_threshold: float) -> VolumeBreakdown:
    counts = dict.fromkeys(RowStatus, 0)
    for row in rows:
        counts[row.status(clear_threshold, escalate_threshold)] += 1
    return VolumeBreakdown(
        auto_clear=counts[RowStatus.AUTO_CLEAR],
        review=counts[RowStatus.REVIEW],
        auto_escalate=counts[RowStatus.AUTO_ESCALATE],
        cleared=counts[RowStatus.CLEARED],
        escalated=counts[RowStatus.ESCALATED],
        total=len(rows),
    )
