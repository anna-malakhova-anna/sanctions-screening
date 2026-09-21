"""Name perturbations used to generate known positives for the labelled test set.

Each function takes a clean source name and a seeded `random.Random`, and
returns a plausibly-real variant of it, or `None` if the perturbation doesn't
apply to this particular name (you can't drop a middle name from a name that
doesn't have one, or change a legal suffix a name doesn't carry). The caller
is expected to skip to another source name on `None` rather than force one --
see harness.py.

Same discipline as normalize.py: each perturbation is small, named, and
independently testable, so when the matcher's recall breaks down on one
failure mode later, the failure traces to one named function, not an opaque
generator.
"""

from __future__ import annotations

import random
import string

from unidecode import unidecode

# Common alternate transliterations of the same underlying name, grouped.
# Deliberately skewed toward Arabic-origin names since that's what dominates
# the OFAC SDN source population this harness draws from -- matches the
# doc's own example (Mohammed / Muhammad / Mohamad).
TRANSLITERATION_VARIANT_GROUPS: list[list[str]] = [
    ["MOHAMMED", "MUHAMMAD", "MOHAMED", "MOHAMAD", "MUHAMMED"],
    ["HUSSEIN", "HUSAYN", "HUSSAIN", "HUSEIN"],
    ["ALI", "ALY"],
    ["ABDULLAH", "ABDALLAH", "ABDULLA"],
    ["IBRAHIM", "IBRAHEEM"],
    ["OMAR", "UMAR"],
    ["HASSAN", "HASAN"],
    ["KHALED", "KHALID"],
    ["YOUSSEF", "YUSUF", "YUSSEF", "YOUSEF"],
    ["ABDEL", "ABDUL"],
    ["AHMED", "AHMAD"],
    ["MUSTAFA", "MUSTAPHA"],
    ["SALEH", "SALIH"],
    ["KARIM", "KAREEM"],
    ["ZAKARIA", "ZACHARIA"],
]

_VARIANT_GROUP_BY_TOKEN: dict[str, list[str]] = {
    token: group for group in TRANSLITERATION_VARIANT_GROUPS for token in group
}

_LEGAL_SUFFIX_BARE_FORMS = {"ltd", "limited", "llc", "inc", "incorporated", "corp", "corporation", "co", "company"}
_LEGAL_SUFFIX_DISPLAY_FORMS = ["Ltd", "Limited", "LLC", "Inc", "Corp", "Corporation", "Co"]

_DIACRITIC_VARIANTS: dict[str, str] = {
    "a": "áà", "e": "éè", "i": "íì", "o": "óö", "u": "úü",
    "A": "ÁÀ", "E": "ÉÈ", "I": "ÍÌ", "O": "ÓÖ", "U": "ÚÜ",
}


def transliteration_variant(name: str, rng: random.Random) -> str | None:
    """Swap one token for a differently-spelled transliteration of the same name."""
    tokens = name.split()
    candidate_positions = [i for i, t in enumerate(tokens) if t.strip(string.punctuation).upper() in _VARIANT_GROUP_BY_TOKEN]
    if not candidate_positions:
        return None

    pos = rng.choice(candidate_positions)
    token = tokens[pos]
    stripped = token.strip(string.punctuation)
    group = _VARIANT_GROUP_BY_TOKEN[stripped.upper()]
    alternatives = [g for g in group if g != stripped.upper()]
    if not alternatives:
        return None

    replacement = rng.choice(alternatives)
    replacement = replacement if stripped.isupper() else replacement.capitalize()
    tokens[pos] = token.replace(stripped, replacement)
    return " ".join(tokens)


def character_typo(name: str, rng: random.Random) -> str | None:
    """Substitute one letter for a different one, simulating a data-entry typo."""
    letter_positions = [i for i, c in enumerate(name) if c.isalpha()]
    if len(letter_positions) < 3:
        return None

    pos = rng.choice(letter_positions)
    original = name[pos]
    alphabet = string.ascii_lowercase if original.islower() else string.ascii_uppercase
    replacement = rng.choice([c for c in alphabet if c.lower() != original.lower()])
    return name[:pos] + replacement + name[pos + 1 :]


def doubled_letter(name: str, rng: random.Random) -> str | None:
    """Duplicate one letter, simulating a keystroke error."""
    letter_positions = [i for i, c in enumerate(name) if c.isalpha()]
    if not letter_positions:
        return None

    pos = rng.choice(letter_positions)
    return name[: pos + 1] + name[pos] + name[pos + 1 :]


def word_order_swap(name: str, rng: random.Random) -> str | None:
    """Swap two tokens, simulating e.g. surname-first data entry."""
    tokens = name.split()
    if len(tokens) < 2:
        return None

    i, j = rng.sample(range(len(tokens)), 2)
    tokens[i], tokens[j] = tokens[j], tokens[i]
    return " ".join(tokens)


def dropped_middle_name(name: str, rng: random.Random) -> str | None:
    """Drop one interior token, keeping the first and last."""
    tokens = name.split()
    if len(tokens) < 3:
        return None

    drop_idx = rng.choice(range(1, len(tokens) - 1))
    del tokens[drop_idx]
    return " ".join(tokens)


def initials_for_given_name(name: str, rng: random.Random) -> str | None:
    """Replace every token but the last with its initial, keeping the surname whole."""
    tokens = name.split()
    if len(tokens) < 2:
        return None

    *given, surname = tokens
    initials = [f"{t[0].upper()}." for t in given if t]
    if not initials:
        return None
    return " ".join([*initials, surname])


def legal_suffix_change(name: str, rng: random.Random) -> str | None:
    """Swap a trailing legal-form suffix (Ltd/Limited/LLC/...) for a different
    one, or drop it entirely. Not a claim that these are legally equivalent --
    it's testing the matcher's tolerance to entity-suffix noise, and OFAC and
    counterparty data both contain plenty of it regardless of which form is
    technically correct."""
    tokens = name.split()
    if not tokens:
        return None

    bare = tokens[-1].strip(string.punctuation).lower()
    if bare not in _LEGAL_SUFFIX_BARE_FORMS:
        return None

    if rng.random() < 0.5:
        remainder = tokens[:-1]
        if remainder and remainder[-1].endswith(","):
            remainder[-1] = remainder[-1].rstrip(",")
        return " ".join(remainder) if remainder else None

    alternatives = [f for f in _LEGAL_SUFFIX_DISPLAY_FORMS if f.lower() != bare]
    tokens[-1] = rng.choice(alternatives)
    return " ".join(tokens)


def add_diacritics(name: str, rng: random.Random) -> str | None:
    """Add an accent to a random vowel, simulating inconsistent transliteration."""
    vowel_positions = [i for i, c in enumerate(name) if c in _DIACRITIC_VARIANTS]
    if not vowel_positions:
        return None

    pos = rng.choice(vowel_positions)
    variant = rng.choice(_DIACRITIC_VARIANTS[name[pos]])
    return name[:pos] + variant + name[pos + 1 :]


def remove_diacritics(name: str, rng: random.Random) -> str | None:
    """Strip accents from a name that has them. Only applicable to names that
    actually carry diacritics -- most OFAC SDN entries are plain ASCII, so
    this mostly fires on GLEIF-sourced or non-English-origin names."""
    plain = unidecode(name)
    return plain if plain != name else None
