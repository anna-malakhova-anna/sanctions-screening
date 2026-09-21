from sanctions_screening.match.engine import (
    MatcherName,
    build_search_index,
    match_batch,
    match_query,
    score_pair,
)
from sanctions_screening.models import Alias, AliasStrength, Entity, EntityType


def entity(source_id, name, aliases=None, entity_type=EntityType.INDIVIDUAL) -> Entity:
    return Entity(
        source_id=source_id,
        list_name="OFAC SDN",
        list_version="2026-09-18",
        canonical_name=name,
        entity_type=entity_type,
        aliases=aliases or [],
    )


WATCHLIST = [
    entity(
        "OFAC-1",
        "Mohammed Abdul Karim Hassan",
        aliases=[
            Alias(name="Karim Hassan", strength=AliasStrength.STRONG),
            Alias(name="M. Hassan", strength=AliasStrength.WEAK),
        ],
    ),
    entity("OFAC-2", "Acme Trading Ltd", entity_type=EntityType.COMPANY),
    entity("OFAC-3", "Zakaria Trading Company", entity_type=EntityType.COMPANY),
]


class TestScorePair:
    def test_exact_match_returns_exact_matcher(self):
        score, matcher = score_pair("acme trading", "acme trading")
        assert score == 1.0
        assert matcher is MatcherName.EXACT

    def test_near_match_returns_jaro_winkler_matcher(self):
        score, matcher = score_pair("mohammed hassan", "muhammad hassan")
        assert matcher is MatcherName.JARO_WINKLER
        assert 0.0 < score < 1.0


class TestBuildSearchIndex:
    def test_one_row_per_canonical_name_plus_alias(self):
        index = build_search_index(WATCHLIST)
        # entity 1: canonical + 2 aliases = 3 rows; entities 2 and 3: 1 row each
        assert len(index) == 3 + 1 + 1

    def test_normalized_name_precomputed(self):
        index = build_search_index(WATCHLIST)
        acme_row = next(e for e in index if e.entity.source_id == "OFAC-2")
        assert acme_row.normalized_name == "acme trading"

    def test_alias_rows_flagged(self):
        index = build_search_index(WATCHLIST)
        alias_rows = [e for e in index if e.entity.source_id == "OFAC-1" and e.is_alias]
        assert len(alias_rows) == 2
        assert {r.name for r in alias_rows} == {"Karim Hassan", "M. Hassan"}
        assert {r.alias_strength for r in alias_rows} == {AliasStrength.STRONG, AliasStrength.WEAK}

    def test_canonical_row_not_flagged_as_alias(self):
        index = build_search_index(WATCHLIST)
        canonical_row = next(e for e in index if e.entity.source_id == "OFAC-2")
        assert canonical_row.is_alias is False
        assert canonical_row.alias_strength is None


class TestMatchQuery:
    def test_exact_query_matches_canonical_name(self):
        index = build_search_index(WATCHLIST)
        results = match_query("Acme Trading Ltd", index)
        assert results[0].source_id == "OFAC-2"
        assert results[0].score == 1.0
        assert results[0].matcher is MatcherName.EXACT
        assert results[0].is_alias_match is False

    def test_query_matches_via_alias(self):
        index = build_search_index(WATCHLIST)
        results = match_query("Karim Hassan", index)
        assert results[0].source_id == "OFAC-1"
        assert results[0].score == 1.0
        assert results[0].matched_name == "Karim Hassan"
        assert results[0].is_alias_match is True
        assert results[0].alias_strength is AliasStrength.STRONG

    def test_perturbed_query_matches_fuzzily(self):
        index = build_search_index(WATCHLIST)
        results = match_query("Muhammad Abdul Karim Hassan", index)
        assert results[0].source_id == "OFAC-1"
        assert results[0].matcher is MatcherName.JARO_WINKLER
        assert results[0].score > 0.8

    def test_best_row_wins_when_alias_beats_canonical(self):
        # "M. Hassan" is closer to the weak alias than to the canonical name
        index = build_search_index(WATCHLIST)
        results = match_query("M. Hassan", index)
        top = next(r for r in results if r.source_id == "OFAC-1")
        assert top.matched_name == "M. Hassan"
        assert top.score == 1.0

    def test_results_ranked_descending_by_score(self):
        index = build_search_index(WATCHLIST)
        results = match_query("Zakaria Trading Co", index)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_one_result_per_entity_even_with_multiple_alias_hits(self):
        index = build_search_index(WATCHLIST)
        results = match_query("Karim Hassan", index, top_k=10)
        source_ids = [r.source_id for r in results]
        assert len(source_ids) == len(set(source_ids))

    def test_top_k_limits_results(self):
        index = build_search_index(WATCHLIST)
        results = match_query("Acme Trading", index, top_k=1)
        assert len(results) == 1

    def test_completely_unrelated_query_still_returns_ranked_low_scores(self):
        index = build_search_index(WATCHLIST)
        results = match_query("Totally Unrelated Fish Market", index)
        assert len(results) > 0
        assert all(r.score < 0.8 for r in results)

    def test_empty_index_returns_no_results(self):
        assert match_query("Acme Trading", build_search_index([])) == []


class TestMatchBatch:
    def test_returns_one_result_list_per_query(self):
        index = build_search_index(WATCHLIST)
        results = match_batch(["Acme Trading Ltd", "Karim Hassan"], index)
        assert len(results) == 2

    def test_matches_match_query_for_the_same_input(self):
        index = build_search_index(WATCHLIST)
        batched = match_batch(["Muhammad Abdul Karim Hassan"], index)[0]
        single = match_query("Muhammad Abdul Karim Hassan", index)
        assert [(r.source_id, r.score, r.matcher) for r in batched] == [
            (r.source_id, r.score, r.matcher) for r in single
        ]

    def test_empty_query_list_returns_empty(self):
        index = build_search_index(WATCHLIST)
        assert match_batch([], index) == []

    def test_empty_index_returns_empty_result_per_query(self):
        results = match_batch(["Acme Trading", "Karim Hassan"], build_search_index([]))
        assert results == [[], []]

    def test_top_k_applies_per_query(self):
        index = build_search_index(WATCHLIST)
        results = match_batch(["Acme Trading", "Karim Hassan"], index, top_k=1)
        assert all(len(r) == 1 for r in results)
