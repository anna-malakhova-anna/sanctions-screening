import random

from sanctions_screening.models import Entity, EntityType
from sanctions_screening.perturb.harness import (
    PERTURBATION_FUNCS,
    PerturbationType,
    build_labelled_test_set,
    read_labelled_set,
    write_labelled_set,
)


def ofac_entity(idx: int, name: str) -> Entity:
    return Entity(
        source_id=f"OFAC-{idx}",
        list_name="OFAC SDN",
        list_version="2026-09-18",
        canonical_name=name,
        entity_type=EntityType.INDIVIDUAL,
    )


def gleif_entity(idx: int, name: str) -> Entity:
    return Entity(
        source_id=f"GLEIF-{idx}",
        list_name="GLEIF LEI",
        list_version="2026-09-21",
        canonical_name=name,
        entity_type=EntityType.COMPANY,
    )


# Rich, multi-token names so every perturbation type (word-order swap, dropped
# middle name, legal suffix change, transliteration variant, ...) has
# something to apply to.
POSITIVE_SOURCE = [
    ofac_entity(1, "Mohammed Abdul Karim Hassan"),
    ofac_entity(2, "Ahmed Youssef Al-Zomor"),
    ofac_entity(3, "Acme Trading Ltd"),
    ofac_entity(4, "Zakaria Trading Company"),
    ofac_entity(5, "Khaled Ibrahim Mustafa"),
    ofac_entity(6, "Global Shipping Corp"),
    ofac_entity(7, "Omar Saleh Karim"),
    ofac_entity(8, "Hussein Abdullah Ali"),
    ofac_entity(9, "José García Muñoz"),
]

NEGATIVE_SOURCE = [gleif_entity(i, f"Real Company {i} GmbH") for i in range(50)]


class TestBuildLabelledTestSet:
    def test_generates_exact_baseline(self):
        pairs = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=3, seed=1)
        exact_rows = [p for p in pairs if p.perturbation_type is PerturbationType.EXACT]
        assert len(exact_rows) == 3
        assert all(row.query_name == row.source_canonical_name for row in exact_rows)

    def test_every_positive_row_traces_to_a_source_entity(self):
        pairs = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=3, seed=1)
        source_ids = {e.source_id: e for e in POSITIVE_SOURCE}
        for row in pairs:
            if row.is_positive:
                assert row.source_id in source_ids
                assert row.source_canonical_name == source_ids[row.source_id].canonical_name

    def test_negative_rows_are_unperturbed_gleif_names(self):
        pairs = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=3, seed=1)
        negative_ids = {e.source_id for e in NEGATIVE_SOURCE}
        for row in pairs:
            if not row.is_positive:
                assert row.perturbation_type is PerturbationType.NEGATIVE_CONTROL
                assert row.source_id in negative_ids
                assert row.query_name == row.source_canonical_name

    def test_negative_ratio_controls_negative_count(self):
        pairs = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=3, negative_ratio=0.5, seed=1)
        n_positive = sum(1 for p in pairs if p.is_positive)
        n_negative = sum(1 for p in pairs if not p.is_positive)
        assert n_negative == round(n_positive * 0.5)

    def test_skips_entities_the_perturbation_does_not_apply_to(self):
        # single-token, no legal suffix, no known transliteration token
        sparse_source = [ofac_entity(1, "Xyzzy")]
        pairs = build_labelled_test_set(sparse_source, NEGATIVE_SOURCE, pairs_per_type=5, seed=1)
        perturbed_types = {p.perturbation_type for p in pairs if p.is_positive and p.perturbation_type != PerturbationType.EXACT}
        # none of the multi-token/suffix/transliteration perturbations could fire
        assert PerturbationType.WORD_ORDER_SWAP not in perturbed_types
        assert PerturbationType.DROPPED_MIDDLE_NAME not in perturbed_types
        assert PerturbationType.LEGAL_SUFFIX_CHANGE not in perturbed_types
        assert PerturbationType.TRANSLITERATION_VARIANT not in perturbed_types

    def test_pair_ids_are_unique(self):
        pairs = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=3, seed=1)
        assert len({p.pair_id for p in pairs}) == len(pairs)

    def test_deterministic_given_seed(self):
        a = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=4, seed=99)
        b = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=4, seed=99)
        assert [p.model_dump() for p in a] == [p.model_dump() for p in b]

    def test_different_seeds_can_differ(self):
        a = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=4, seed=1)
        b = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=4, seed=2)
        assert [p.query_name for p in a] != [p.query_name for p in b]

    def test_covers_every_registered_perturbation_type_given_rich_enough_source(self):
        # a larger, more varied source so every type has applicable candidates
        rich_source = POSITIVE_SOURCE * 5
        pairs = build_labelled_test_set(rich_source, NEGATIVE_SOURCE, pairs_per_type=5, seed=3)
        produced_types = {p.perturbation_type for p in pairs}
        for ptype in PERTURBATION_FUNCS:
            assert ptype in produced_types, f"{ptype} never fired"


class TestReadWriteLabelledSet:
    def test_round_trips(self, tmp_path):
        pairs = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=2, seed=1)
        out_path = write_labelled_set(pairs, tmp_path / "labelled.jsonl")
        read_back = list(read_labelled_set(out_path))
        assert [p.pair_id for p in read_back] == [p.pair_id for p in pairs]
        assert read_back[0].perturbation_type in PerturbationType


class TestPerturbationFuncsDeterminism:
    def test_all_registered_funcs_are_callable_and_seed_stable(self):
        rng_state_probe = random.Random(123)
        for ptype, func in PERTURBATION_FUNCS.items():
            a = func("Mohammed Abdul Karim Trading Ltd", random.Random(5))
            b = func("Mohammed Abdul Karim Trading Ltd", random.Random(5))
            assert a == b, f"{ptype} is not deterministic for a fixed seed"
        # sanity: rng_state_probe untouched by the loop above (each func got its own Random)
        assert rng_state_probe.random() == random.Random(123).random()


class TestNamesAreStillMostlyAlphabetic:
    def test_perturbed_names_do_not_introduce_garbage_control_chars(self):
        pairs = build_labelled_test_set(POSITIVE_SOURCE, NEGATIVE_SOURCE, pairs_per_type=5, seed=1)
        allowed_extra = set(" .,-'áàéèíìóöúüÁÀÉÈÍÌÓÖÚÜñÑ")
        for row in pairs:
            if row.is_positive:
                assert all(c.isalnum() or c in allowed_extra for c in row.query_name), row.query_name
