"""The match engine: score query names against every entity in a watchlist,
and return the best candidate per entity, ranked.

Two matchers run per (query, name) pair: exact on the normalized form, and
Jaro-Winkler as the fuzzy fallback. Exact wins whenever it fires (it only
fires on a literal normalized match, which Jaro-Winkler also scores at or
near 1.0, so there's no real tension in preferring it) -- that keeps "which
matcher fired" an honest, single-valued label per candidate rather than a
blend, per the doc's requirement to output "which matcher fired" alongside
the score.

A token-set-overlap matcher and an LLM adjudicator for the ambiguous band are
both named in the handover doc's architecture but out of v1 scope by
explicit decision -- exact + Jaro-Winkler is the "one matcher plus exact
match" the v1 checklist calls for.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel
from rapidfuzz import process
from rapidfuzz.distance import JaroWinkler

from sanctions_screening.match.matchers import exact_score, jaro_winkler_score
from sanctions_screening.models import AliasStrength, Entity
from sanctions_screening.normalize import normalize_name


class MatcherName(str, Enum):
    EXACT = "exact"
    JARO_WINKLER = "jaro_winkler"


@dataclass(frozen=True)
class SearchIndexEntry:
    """One comparable name string: an entity's canonical name, or one of its
    aliases. Plain dataclass, not a pydantic model -- this is an internal,
    computed structure rebuilt per snapshot load, not something we validate
    or serialize, and a watchlist the size of OFAC's produces tens of
    thousands of these."""

    entity: Entity
    name: str
    normalized_name: str
    is_alias: bool
    alias_strength: AliasStrength | None


class SearchIndex(Sequence[SearchIndexEntry]):
    """A built index: the flattened entries, plus their normalized names
    precomputed once as a parallel list so every match call can hand that
    list straight to rapidfuzz instead of rebuilding it. Behaves like a plain
    sequence of entries (len, iteration, indexing) so callers -- including
    existing tests -- can treat it exactly like the list it replaces."""

    def __init__(self, entries: list[SearchIndexEntry]):
        self._entries = entries
        self.normalized_names: list[str] = [e.normalized_name for e in entries]

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, i):
        return self._entries[i]

    def __iter__(self) -> Iterator[SearchIndexEntry]:
        return iter(self._entries)


def build_search_index(entities: Sequence[Entity]) -> SearchIndex:
    """Flatten entities and their aliases into one row per comparable name,
    normalizing once up front so matching doesn't repeat that work per query."""
    entries: list[SearchIndexEntry] = []
    for entity in entities:
        entries.append(
            SearchIndexEntry(
                entity=entity,
                name=entity.canonical_name,
                normalized_name=normalize_name(entity.canonical_name),
                is_alias=False,
                alias_strength=None,
            )
        )
        for alias in entity.aliases:
            entries.append(
                SearchIndexEntry(
                    entity=entity,
                    name=alias.name,
                    normalized_name=normalize_name(alias.name),
                    is_alias=True,
                    alias_strength=alias.strength,
                )
            )
    return SearchIndex(entries)


class MatchCandidate(BaseModel):
    """One (query, entity) result: the best-scoring name variant for that
    entity, which matcher produced the winning score, and the alias it hit
    (if it hit an alias rather than the canonical name)."""

    query_name: str
    source_id: str
    entity_canonical_name: str
    matched_name: str
    is_alias_match: bool
    alias_strength: AliasStrength | None
    matcher: MatcherName
    score: float


def score_pair(normalized_query: str, normalized_candidate: str) -> tuple[float, MatcherName]:
    exact = exact_score(normalized_query, normalized_candidate)
    if exact == 1.0:
        return exact, MatcherName.EXACT
    return jaro_winkler_score(normalized_query, normalized_candidate), MatcherName.JARO_WINKLER


def _collapse_to_top_k(
    query_name: str,
    normalized_query: str,
    entries: Sequence[SearchIndexEntry],
    row_scores,
    top_k: int,
) -> list[MatchCandidate]:
    """Reduce one query's per-name scores to the best entry per entity, then
    build MatchCandidate objects for only the top_k winners.

    Deliberately two passes: the first collapse works over plain (score, index)
    tuples rather than constructing a MatchCandidate per entity as it goes.
    Against the live ~19k-entity OFAC list, building a pydantic object for
    every entity's first-seen row (rather than just the handful actually
    returned) was the dominant per-query cost -- tens of milliseconds of
    validation overhead for results that get thrown away immediately after.
    """
    best_per_entity: dict[str, tuple[float, int]] = {}
    for i, (entry, score) in enumerate(zip(entries, row_scores, strict=True)):
        score = float(score)
        current = best_per_entity.get(entry.entity.source_id)
        if current is None or score > current[0]:
            best_per_entity[entry.entity.source_id] = (score, i)

    ranked = sorted(best_per_entity.values(), key=lambda pair: pair[0], reverse=True)[:top_k]

    results: list[MatchCandidate] = []
    for score, i in ranked:
        entry = entries[i]
        matcher = MatcherName.EXACT if normalized_query == entry.normalized_name else MatcherName.JARO_WINKLER
        results.append(
            MatchCandidate(
                query_name=query_name,
                source_id=entry.entity.source_id,
                entity_canonical_name=entry.entity.canonical_name,
                matched_name=entry.name,
                is_alias_match=entry.is_alias,
                alias_strength=entry.alias_strength,
                matcher=matcher,
                score=score,
            )
        )
    return results


def match_query(query_name: str, index: SearchIndex | Sequence[SearchIndexEntry], *, top_k: int = 5) -> list[MatchCandidate]:
    """Score `query_name` against every name in `index` and return the top_k
    entities by score, highest first. For screening more than one name at a
    time, prefer match_batch -- it scores the whole batch in a single
    rapidfuzz call instead of paying per-call overhead once per name."""
    return match_batch([query_name], index, top_k=top_k)[0]


def match_batch(
    query_names: Sequence[str], index: SearchIndex | Sequence[SearchIndexEntry], *, top_k: int = 5
) -> list[list[MatchCandidate]]:
    """Score every name in `query_names` against every name in `index` in one
    batched rapidfuzz call, then collapse each query's row to its top_k
    entities. This is the path the app's upload/screen endpoint uses."""
    if not query_names:
        return []
    if not len(index):
        return [[] for _ in query_names]

    entries = list(index)
    normalized_candidates = index.normalized_names if isinstance(index, SearchIndex) else [e.normalized_name for e in entries]
    normalized_queries = [normalize_name(q) for q in query_names]

    score_matrix = process.cdist(normalized_queries, normalized_candidates, scorer=JaroWinkler.normalized_similarity, workers=-1)

    return [
        _collapse_to_top_k(query_names[row], normalized_queries[row], entries, score_matrix[row], top_k)
        for row in range(len(query_names))
    ]
