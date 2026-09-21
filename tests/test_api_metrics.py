from sanctions_screening.api.metrics import (
    compute_ground_truth_metrics,
    compute_volume_breakdown,
    labelled_row_status,
)
from sanctions_screening.api.schemas import RowStatus, ScreeningRow
from sanctions_screening.match.engine import MatcherName, MatchCandidate
from sanctions_screening.perturb.harness import LabelledPair, PerturbationType


def pair(is_positive, score) -> tuple[LabelledPair, float]:
    p = LabelledPair(
        pair_id="p1",
        query_name="Some Name",
        is_positive=is_positive,
        perturbation_type=PerturbationType.EXACT if is_positive else PerturbationType.NEGATIVE_CONTROL,
        source_id="OFAC-1" if is_positive else "GLEIF-1",
        source_canonical_name="Some Name",
    )
    return p, score


def candidate(score) -> MatchCandidate:
    return MatchCandidate(
        query_name="q",
        source_id="OFAC-1",
        entity_canonical_name="Canonical",
        matched_name="Canonical",
        is_alias_match=False,
        alias_strength=None,
        matcher=MatcherName.JARO_WINKLER,
        score=score,
    )


def row(score, row_id="row-1", decision=None, decided_by=None) -> ScreeningRow:
    return ScreeningRow(
        row_id=row_id,
        query_name="q",
        candidates=[candidate(score)] if score else [],
        best_score=score,
        decision=decision,
        decided_by=decided_by,
    )


class TestLabelledRowStatus:
    def test_buckets_match_screening_row_thresholds(self):
        assert labelled_row_status(0.5, 0.8, 0.97) is RowStatus.AUTO_CLEAR
        assert labelled_row_status(0.85, 0.8, 0.97) is RowStatus.REVIEW
        assert labelled_row_status(0.99, 0.8, 0.97) is RowStatus.AUTO_ESCALATE


class TestComputeGroundTruthMetrics:
    def test_all_positives_auto_cleared_gives_zero_recall(self):
        scores = [pair(True, 0.1), pair(True, 0.2)]
        m = compute_ground_truth_metrics(scores, 0.8, 0.97)
        assert m.recall_not_missed == 0.0

    def test_all_positives_above_clear_threshold_gives_full_recall(self):
        scores = [pair(True, 0.85), pair(True, 0.99)]
        m = compute_ground_truth_metrics(scores, 0.8, 0.97)
        assert m.recall_not_missed == 1.0

    def test_auto_escalate_precision_counts_only_that_bucket(self):
        scores = [pair(True, 0.99), pair(False, 0.99), pair(True, 0.85)]
        m = compute_ground_truth_metrics(scores, 0.8, 0.97)
        # 2 rows land in auto_escalate (one true positive, one negative)
        assert m.auto_escalate_precision == 0.5

    def test_auto_escalate_precision_none_when_bucket_empty(self):
        scores = [pair(True, 0.5), pair(False, 0.5)]
        m = compute_ground_truth_metrics(scores, 0.8, 0.97)
        assert m.auto_escalate_precision is None

    def test_negative_auto_escalate_rate(self):
        scores = [pair(False, 0.99), pair(False, 0.5), pair(False, 0.5), pair(False, 0.5)]
        m = compute_ground_truth_metrics(scores, 0.8, 0.97)
        assert m.negative_auto_escalate_rate == 0.25

    def test_negative_review_rate(self):
        scores = [pair(False, 0.85), pair(False, 0.5)]
        m = compute_ground_truth_metrics(scores, 0.8, 0.97)
        assert m.negative_review_rate == 0.5

    def test_empty_set_gives_zero_rates_and_none_precision(self):
        m = compute_ground_truth_metrics([], 0.8, 0.97)
        assert m.recall_not_missed == 0.0
        assert m.auto_escalate_precision is None
        assert m.negative_auto_escalate_rate == 0.0
        assert m.labelled_set_size == 0


class TestComputeVolumeBreakdown:
    def test_buckets_undecided_rows_by_score(self):
        rows = [row(0.5), row(0.85), row(0.99)]
        v = compute_volume_breakdown(rows, 0.8, 0.97)
        assert v.auto_clear == 1
        assert v.review == 1
        assert v.auto_escalate == 1
        assert v.cleared == 0
        assert v.escalated == 0
        assert v.total == 3

    def test_decided_rows_counted_as_cleared_or_escalated_regardless_of_score(self):
        rows = [
            row(0.5, decision="escalate", decided_by="human"),
            row(0.99, decision="clear", decided_by="simulated_reviewer"),
        ]
        v = compute_volume_breakdown(rows, 0.8, 0.97)
        assert v.escalated == 1
        assert v.cleared == 1
        assert v.auto_clear == 0
        assert v.auto_escalate == 0

    def test_empty_batch(self):
        v = compute_volume_breakdown([], 0.8, 0.97)
        assert v.total == 0
