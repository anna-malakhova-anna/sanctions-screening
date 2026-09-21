"""A simulated reviewer for the review queue.

Resolves the handover doc's open question -- "whether the reviewer is
simulated or you click through it yourself in the demo" -- in favor of
simulation: the review queue supports real clicks too (POST a decision per
row), but a live demo shouldn't require clicking through fifty rows one at a
time to show the decision log working end to end.

The heuristic is deliberately simple and stated plainly here rather than
dressed up as real analyst judgment: within the review band, a row's
position between the two thresholds stands in for "how suspicious," and a
hit on a STRONG OFAC alias (a corroborated alternate identity, not a loose
near-miss) pushes toward escalate regardless of position. This is a
placeholder for a human, not a claim about what a real reviewer would do.
"""

from __future__ import annotations

from sanctions_screening.api.schemas import ScreeningRow
from sanctions_screening.models import AliasStrength

# Position within the review band (0 = right at clear_threshold, 1 = right at
# escalate_threshold) at or above which the simulated reviewer escalates.
ESCALATE_POSITION_CUTOFF = 0.6


def simulated_decision(row: ScreeningRow, clear_threshold: float, escalate_threshold: float) -> tuple[str, str]:
    """Decide a row currently sitting in the review band. Returns
    (decision, note); the note is shown in the UI so the "simulated" label
    doesn't read as a black box."""
    band = escalate_threshold - clear_threshold
    position = (row.best_score - clear_threshold) / band if band > 0 else 1.0

    top = row.top_candidate
    strong_alias_hit = bool(top and top.is_alias_match and top.alias_strength is AliasStrength.STRONG)

    if position >= ESCALATE_POSITION_CUTOFF or strong_alias_hit:
        reason = f"score {position:.0%} through the review band"
        if strong_alias_hit:
            reason += ", hit a strong OFAC alias"
        return "escalate", f"simulated reviewer: {reason}"

    return "clear", f"simulated reviewer: score only {position:.0%} through the review band, no strong alias hit"
