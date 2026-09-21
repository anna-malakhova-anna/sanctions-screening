"""Name normalization rules.

Each rule is a small, named, independently testable function. They compose into
`normalize_name`, which produces the canonical form used for exact-match
comparison. Keeping them separate (rather than one regex blob) is deliberate:
when the matcher misses something, the failure should trace to one named rule,
not to an opaque pipeline.
"""

from __future__ import annotations

import re

from unidecode import unidecode

# Legal-entity suffixes normalized away when they appear as trailing tokens.
# Not exhaustive — extend as real OFAC/GLEIF data surfaces more variants.
LEGAL_SUFFIXES: frozenset[str] = frozenset(
    {
        "ltd",
        "limited",
        "llc",
        "llp",
        "lp",
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "co",
        "company",
        "plc",
        "gmbh",
        "sa",
        "srl",
        "sarl",
        "bv",
        "nv",
        "ag",
        "pty",
        "pte",
        "kg",
        "oy",
        "ab",
        "as",
    }
)

_PUNCTUATION_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def strip_diacritics(name: str) -> str:
    """Collapse transliteration variants: Muhammad / Muḥammad / Mühammad -> same ASCII form."""
    return unidecode(name)


def fold_case(name: str) -> str:
    return name.casefold()


def strip_punctuation(name: str) -> str:
    """Replace punctuation with spaces (not delete) so 'Smith-Jones' -> 'smith jones',
    not 'smithjones'; the two should still compare as a token match."""
    return _PUNCTUATION_RE.sub(" ", name)


def collapse_whitespace(name: str) -> str:
    return _WHITESPACE_RE.sub(" ", name).strip()


def strip_legal_suffixes(name: str) -> str:
    """Drop trailing legal-form tokens (Ltd, Limited, LLC, ...), repeatedly, so
    'Acme Trading Co Ltd' -> 'acme trading' rather than stopping after one hit."""
    tokens = name.split()
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_name(name: str) -> str:
    """Full pipeline producing the canonical form used for exact-match comparison.

    Order matters: diacritics and case are stripped first so downstream string
    ops are ASCII/lowercase; punctuation becomes whitespace before suffix
    stripping so 'Acme, Ltd.' and 'Acme Ltd' collapse to the same tokens.
    """
    result = strip_diacritics(name)
    result = fold_case(result)
    result = strip_punctuation(result)
    result = collapse_whitespace(result)
    result = strip_legal_suffixes(result)
    result = collapse_whitespace(result)
    return result
