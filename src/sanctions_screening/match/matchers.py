"""Individual matchers. Each takes two already-normalized names (see
normalize.normalize_name) and returns a similarity score in [0, 1].

Kept as small, named, separately-callable functions rather than folded into
the engine -- the whole point of running more than one matcher is being able
to say which one contributed a given match, which only works if each one is
independently inspectable.
"""

from __future__ import annotations

from rapidfuzz.distance import JaroWinkler


def exact_score(normalized_query: str, normalized_candidate: str) -> float:
    """1.0 if the two normalized forms are identical, 0.0 otherwise."""
    return 1.0 if normalized_query == normalized_candidate else 0.0


def jaro_winkler_score(normalized_query: str, normalized_candidate: str) -> float:
    """String-distance similarity, tolerant of typos and small transliteration
    differences. Jaro-Winkler weights matching prefixes more heavily, which
    suits names: two names sharing a first few characters are more likely to
    be the same name than two sharing the same number of characters scattered
    throughout."""
    return JaroWinkler.normalized_similarity(normalized_query, normalized_candidate)
