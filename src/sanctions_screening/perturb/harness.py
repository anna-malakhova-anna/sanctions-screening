"""Build a labelled test set: known positives (perturbed OFAC names) salted
into known negatives (real GLEIF company names), each row tagged with which
perturbation produced it.

That tag is the point. A single precision/recall number says nothing about
*why* the matcher misses cases; being able to say "it's weak on word-order
swaps and dropped middle names, fine everywhere else" is what turns this into
an interview-ready diagnostic instead of a vanity metric.

Caveat this harness cannot fix, and shouldn't hide: these perturbations are
easier than real-world noisy data -- a human, not an adversary, produced them,
and there's no compounding of multiple failure modes in one name the way real
sanctions-list data entry error often does. Treat any curve built from this
set as directional, not a benchmark.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator, Sequence
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from sanctions_screening.models import Entity
from sanctions_screening.perturb import perturbations as p


class PerturbationType(str, Enum):
    EXACT = "exact"
    TRANSLITERATION_VARIANT = "transliteration_variant"
    CHARACTER_TYPO = "character_typo"
    DOUBLED_LETTER = "doubled_letter"
    WORD_ORDER_SWAP = "word_order_swap"
    DROPPED_MIDDLE_NAME = "dropped_middle_name"
    INITIALS_FOR_GIVEN_NAME = "initials_for_given_name"
    LEGAL_SUFFIX_CHANGE = "legal_suffix_change"
    ADD_DIACRITICS = "add_diacritics"
    REMOVE_DIACRITICS = "remove_diacritics"
    NEGATIVE_CONTROL = "negative_control"


PERTURBATION_FUNCS: dict[PerturbationType, Callable[[str, random.Random], str | None]] = {
    PerturbationType.TRANSLITERATION_VARIANT: p.transliteration_variant,
    PerturbationType.CHARACTER_TYPO: p.character_typo,
    PerturbationType.DOUBLED_LETTER: p.doubled_letter,
    PerturbationType.WORD_ORDER_SWAP: p.word_order_swap,
    PerturbationType.DROPPED_MIDDLE_NAME: p.dropped_middle_name,
    PerturbationType.INITIALS_FOR_GIVEN_NAME: p.initials_for_given_name,
    PerturbationType.LEGAL_SUFFIX_CHANGE: p.legal_suffix_change,
    PerturbationType.ADD_DIACRITICS: p.add_diacritics,
    PerturbationType.REMOVE_DIACRITICS: p.remove_diacritics,
}


class LabelledPair(BaseModel):
    """One row of the labelled test set: a name to screen, and the ground truth
    about what screening it should produce."""

    pair_id: str
    query_name: str
    is_positive: bool
    perturbation_type: PerturbationType
    source_id: str
    source_canonical_name: str


def _make_positive(entity: Entity, ptype: PerturbationType, query_name: str) -> LabelledPair:
    return LabelledPair(
        pair_id="",
        query_name=query_name,
        is_positive=True,
        perturbation_type=ptype,
        source_id=entity.source_id,
        source_canonical_name=entity.canonical_name,
    )


def _make_negative(entity: Entity) -> LabelledPair:
    return LabelledPair(
        pair_id="",
        query_name=entity.canonical_name,
        is_positive=False,
        perturbation_type=PerturbationType.NEGATIVE_CONTROL,
        source_id=entity.source_id,
        source_canonical_name=entity.canonical_name,
    )


def build_labelled_test_set(
    positive_source: Sequence[Entity],
    negative_source: Sequence[Entity],
    *,
    pairs_per_type: int = 20,
    negative_ratio: float = 1.0,
    seed: int = 42,
) -> list[LabelledPair]:
    """Generate a labelled test set.

    For each perturbation type (including an unperturbed EXACT baseline), scans
    a shuffled copy of `positive_source` and keeps applying the perturbation
    until `pairs_per_type` usable rows are collected or the source is
    exhausted -- entities the perturbation doesn't apply to (e.g. a
    single-token vessel name for dropped_middle_name) are skipped rather than
    forced, so some types may come up short if the source population doesn't
    support them. Negatives are drawn unperturbed from `negative_source`
    (real company names should already look like plausible counterparties)
    at `negative_ratio` times the total positive count.

    Deterministic for a given seed and given source lists/order.

    Note on REMOVE_DIACRITICS specifically: against the live OFAC SDN feed it
    collects zero rows, because OFAC ASCII-normalizes every canonical name and
    alias on publication (verified: 0/19,393 entries contain a diacritic as of
    the 2026-09-18 snapshot). That's a real property of this source, not a bug
    in the harness -- "diacritics stripped" would be a realistic failure mode
    against raw counterparty upload data or a source like the EU/UK lists,
    just not against OFAC's own text. The function stays registered so it
    activates automatically if a diacritic-bearing source is added later.
    """
    master_rng = random.Random(seed)
    pairs: list[LabelledPair] = []

    exact_candidates = list(positive_source)
    master_rng.shuffle(exact_candidates)
    for entity in exact_candidates[:pairs_per_type]:
        pairs.append(_make_positive(entity, PerturbationType.EXACT, entity.canonical_name))

    for ptype, func in PERTURBATION_FUNCS.items():
        candidates = list(positive_source)
        master_rng.shuffle(candidates)
        type_rng = random.Random(master_rng.random())
        collected = 0
        for entity in candidates:
            if collected >= pairs_per_type:
                break
            perturbed = func(entity.canonical_name, type_rng)
            if not perturbed or perturbed == entity.canonical_name:
                continue
            pairs.append(_make_positive(entity, ptype, perturbed))
            collected += 1

    n_negatives = round(len(pairs) * negative_ratio)
    negative_candidates = list(negative_source)
    master_rng.shuffle(negative_candidates)
    for entity in negative_candidates[:n_negatives]:
        pairs.append(_make_negative(entity))

    master_rng.shuffle(pairs)
    for i, pair in enumerate(pairs):
        pair.pair_id = f"pair-{i:05d}"

    return pairs


def write_labelled_set(pairs: Sequence[LabelledPair], out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(pair.model_dump_json())
            f.write("\n")
    return out_path


def read_labelled_set(path: Path | str) -> Iterator[LabelledPair]:
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield LabelledPair.model_validate_json(line)
