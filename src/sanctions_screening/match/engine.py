"""The match engine: score a query name against every entity in a watchlist,
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

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel

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


def build_search_index(entities: Sequence[Entity]) -> list[SearchIndexEntry]:
    """Flatten entities and their aliases into one row per comparable name,
    normalizing once up front so matching doesn't repeat that work per query."""
    index: list[SearchIndexEntry] = []
    for entity in entities:
        index.append(
            SearchIndexEntry(
                entity=entity,
                name=entity.canonical_name,
                normalized_name=normalize_name(entity.canonical_name),
                is_alias=False,
                alias_strength=None,
            )
        )
        for alias in entity.aliases:
            index.append(
                SearchIndexEntry(
                    entity=entity,
                    name=alias.name,
                    normalized_name=normalize_name(alias.name),
                    is_alias=True,
                    alias_strength=alias.strength,
                )
            )
    return index


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


def match_query(query_name: str, index: Sequence[SearchIndexEntry], *, top_k: int = 5) -> list[MatchCandidate]:
    """Score `query_name` against every name in `index`, collapse to the
    best-scoring name variant per entity, and return the top_k entities by
    score, highest first."""
    normalized_query = normalize_name(query_name)

    best_per_entity: dict[str, MatchCandidate] = {}
    for entry in index:
        score, matcher = score_pair(normalized_query, entry.normalized_name)
        existing = best_per_entity.get(entry.entity.source_id)
        if existing is not None and score <= existing.score:
            continue
        best_per_entity[entry.entity.source_id] = MatchCandidate(
            query_name=query_name,
            source_id=entry.entity.source_id,
            entity_canonical_name=entry.entity.canonical_name,
            matched_name=entry.name,
            is_alias_match=entry.is_alias,
            alias_strength=entry.alias_strength,
            matcher=matcher,
            score=score,
        )

    ranked = sorted(best_per_entity.values(), key=lambda c: c.score, reverse=True)
    return ranked[:top_k]
