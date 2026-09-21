from sanctions_screening.api.schemas import (
    RowStatus,
    ScreeningRow,
    row_to_decision_log_entry,
    row_to_out,
)
from sanctions_screening.match.engine import MatcherName, MatchCandidate
from sanctions_screening.models import AliasStrength


def candidate(score, *, is_alias=False, alias_strength=None, matcher=MatcherName.JARO_WINKLER) -> MatchCandidate:
    return MatchCandidate(
        query_name="Query Name",
        source_id="OFAC-1",
        entity_canonical_name="Canonical Name",
        matched_name="Matched Alias" if is_alias else "Canonical Name",
        is_alias_match=is_alias,
        alias_strength=alias_strength,
        matcher=matcher,
        score=score,
    )


def row(score, *, candidates=None, decision=None, decided_by=None) -> ScreeningRow:
    return ScreeningRow(
        row_id="row-00000",
        query_name="Query Name",
        candidates=candidates if candidates is not None else [candidate(score)],
        best_score=score,
        decision=decision,
        decided_by=decided_by,
    )


class TestScreeningRowStatus:
    def test_below_clear_threshold_is_auto_clear(self):
        assert row(0.5).status(0.8, 0.97) is RowStatus.AUTO_CLEAR

    def test_between_thresholds_is_review(self):
        assert row(0.85).status(0.8, 0.97) is RowStatus.REVIEW

    def test_at_or_above_escalate_threshold_is_auto_escalate(self):
        assert row(0.97).status(0.8, 0.97) is RowStatus.AUTO_ESCALATE
        assert row(0.99).status(0.8, 0.97) is RowStatus.AUTO_ESCALATE

    def test_at_clear_threshold_is_review_not_auto_clear(self):
        assert row(0.8).status(0.8, 0.97) is RowStatus.REVIEW

    def test_human_decision_overrides_score_bucket(self):
        # score would be auto_clear, but a human already cleared it explicitly
        r = row(0.1, decision="clear", decided_by="human")
        assert r.status(0.8, 0.97) is RowStatus.CLEARED

    def test_human_escalate_overrides_even_a_low_score(self):
        r = row(0.1, decision="escalate", decided_by="human")
        assert r.status(0.8, 0.97) is RowStatus.ESCALATED

    def test_moving_threshold_changes_undecided_row_status(self):
        r = row(0.85)
        assert r.status(0.8, 0.97) is RowStatus.REVIEW
        assert r.status(0.9, 0.97) is RowStatus.AUTO_CLEAR

    def test_moving_threshold_does_not_change_decided_row_status(self):
        r = row(0.85, decision="clear", decided_by="human")
        assert r.status(0.8, 0.97) is RowStatus.CLEARED
        assert r.status(0.9, 0.97) is RowStatus.CLEARED


class TestTopCandidate:
    def test_first_candidate_is_top(self):
        c1, c2 = candidate(0.9), candidate(0.5)
        r = row(0.9, candidates=[c1, c2])
        assert r.top_candidate is c1

    def test_no_candidates_top_is_none(self):
        r = row(0.0, candidates=[])
        assert r.top_candidate is None


class TestRowToOut:
    def test_carries_status_and_top_candidate(self):
        r = row(0.5)
        out = row_to_out(r, 0.8, 0.97)
        assert out.status is RowStatus.AUTO_CLEAR
        assert out.top_candidate.score == 0.5


class TestRowToDecisionLogEntry:
    def test_auto_clear_reviewer_label(self):
        r = row(0.5)
        entry = row_to_decision_log_entry(r, list_name="OFAC SDN", list_version="2026-09-18", clear_threshold=0.8, escalate_threshold=0.97)
        assert entry.reviewer == "auto_clear_threshold"
        assert entry.status is RowStatus.AUTO_CLEAR

    def test_auto_escalate_reviewer_label(self):
        r = row(0.99)
        entry = row_to_decision_log_entry(r, list_name="OFAC SDN", list_version="2026-09-18", clear_threshold=0.8, escalate_threshold=0.97)
        assert entry.reviewer == "auto_escalate_threshold"

    def test_unreviewed_band_label(self):
        r = row(0.85)
        entry = row_to_decision_log_entry(r, list_name="OFAC SDN", list_version="2026-09-18", clear_threshold=0.8, escalate_threshold=0.97)
        assert entry.reviewer == "unreviewed"
        assert entry.status is RowStatus.REVIEW

    def test_human_reviewer_label(self):
        r = row(0.85, decision="clear", decided_by="human")
        entry = row_to_decision_log_entry(r, list_name="OFAC SDN", list_version="2026-09-18", clear_threshold=0.8, escalate_threshold=0.97)
        assert entry.reviewer == "human"
        assert entry.status is RowStatus.CLEARED

    def test_matched_alias_only_set_for_alias_hits(self):
        alias_row = row(0.9, candidates=[candidate(0.9, is_alias=True, alias_strength=AliasStrength.STRONG)])
        entry = row_to_decision_log_entry(
            alias_row, list_name="OFAC SDN", list_version="2026-09-18", clear_threshold=0.8, escalate_threshold=0.97
        )
        assert entry.matched_alias == "Matched Alias"

        canonical_row = row(0.9)
        entry2 = row_to_decision_log_entry(
            canonical_row, list_name="OFAC SDN", list_version="2026-09-18", clear_threshold=0.8, escalate_threshold=0.97
        )
        assert entry2.matched_alias is None

    def test_no_candidates_gives_none_match_fields(self):
        r = row(0.0, candidates=[])
        entry = row_to_decision_log_entry(r, list_name="OFAC SDN", list_version="2026-09-18", clear_threshold=0.8, escalate_threshold=0.97)
        assert entry.matched_entity_source_id is None
        assert entry.matcher is None
