from sanctions_screening.api.schemas import ScreeningRow
from sanctions_screening.api.simulate import simulated_decision
from sanctions_screening.match.engine import MatcherName, MatchCandidate
from sanctions_screening.models import AliasStrength


def candidate(score, *, is_alias=False, alias_strength=None) -> MatchCandidate:
    return MatchCandidate(
        query_name="q",
        source_id="OFAC-1",
        entity_canonical_name="Canonical",
        matched_name="Alias" if is_alias else "Canonical",
        is_alias_match=is_alias,
        alias_strength=alias_strength,
        matcher=MatcherName.JARO_WINKLER,
        score=score,
    )


def row(score, *, is_alias=False, alias_strength=None) -> ScreeningRow:
    return ScreeningRow(
        row_id="row-1",
        query_name="q",
        candidates=[candidate(score, is_alias=is_alias, alias_strength=alias_strength)],
        best_score=score,
    )


class TestSimulatedDecision:
    def test_low_position_in_band_clears(self):
        # band is [0.8, 0.97]; 0.81 is ~6% through
        decision, note = simulated_decision(row(0.81), 0.8, 0.97)
        assert decision == "clear"
        assert "simulated" in note.lower()

    def test_high_position_in_band_escalates(self):
        # ~95% through the band
        decision, note = simulated_decision(row(0.96), 0.8, 0.97)
        assert decision == "escalate"

    def test_strong_alias_hit_escalates_even_at_low_position(self):
        decision, _ = simulated_decision(row(0.81, is_alias=True, alias_strength=AliasStrength.STRONG), 0.8, 0.97)
        assert decision == "escalate"

    def test_weak_alias_hit_does_not_force_escalate(self):
        decision, _ = simulated_decision(row(0.81, is_alias=True, alias_strength=AliasStrength.WEAK), 0.8, 0.97)
        assert decision == "clear"

    def test_zero_width_band_always_escalates(self):
        decision, _ = simulated_decision(row(0.8), 0.8, 0.8)
        assert decision == "escalate"

    def test_note_mentions_position(self):
        _, note = simulated_decision(row(0.885), 0.8, 0.97)  # ~50% through
        assert "%" in note
