import random

from sanctions_screening.perturb.perturbations import (
    add_diacritics,
    character_typo,
    doubled_letter,
    dropped_middle_name,
    initials_for_given_name,
    legal_suffix_change,
    remove_diacritics,
    transliteration_variant,
    word_order_swap,
)


class TestTransliterationVariant:
    def test_swaps_known_variant_token(self):
        rng = random.Random(1)
        result = transliteration_variant("MOHAMMED AL-AMIN", rng)
        assert result is not None
        assert result != "MOHAMMED AL-AMIN"
        first_token = result.split()[0]
        assert first_token in {"MUHAMMAD", "MOHAMED", "MOHAMAD", "MUHAMMED"}

    def test_preserves_lowercase_style(self):
        rng = random.Random(1)
        result = transliteration_variant("Mohammed Al-Amin", rng)
        assert result.split()[0][0].isupper()
        assert not result.split()[0].isupper()

    def test_none_when_no_known_token(self):
        rng = random.Random(1)
        assert transliteration_variant("Acme Trading Ltd", rng) is None

    def test_deterministic_given_seed(self):
        assert transliteration_variant("Mohammed Amin", random.Random(7)) == transliteration_variant(
            "Mohammed Amin", random.Random(7)
        )


class TestCharacterTypo:
    def test_changes_exactly_one_character(self):
        rng = random.Random(2)
        original = "Acme Trading Company"
        result = character_typo(original, rng)
        diffs = sum(1 for a, b in zip(original, result, strict=True) if a != b)
        assert diffs == 1
        assert len(result) == len(original)

    def test_none_for_too_short_name(self):
        rng = random.Random(1)
        assert character_typo("Al", rng) is None


class TestDoubledLetter:
    def test_inserts_one_extra_character(self):
        rng = random.Random(3)
        original = "Acme Trading"
        result = doubled_letter(original, rng)
        assert len(result) == len(original) + 1

    def test_none_when_no_letters(self):
        rng = random.Random(1)
        assert doubled_letter("123", rng) is None


class TestWordOrderSwap:
    def test_reorders_tokens(self):
        rng = random.Random(4)
        result = word_order_swap("Alpha Beta Gamma", rng)
        assert sorted(result.split()) == sorted(["Alpha", "Beta", "Gamma"])

    def test_none_for_single_token(self):
        rng = random.Random(1)
        assert word_order_swap("Acme", rng) is None


class TestDroppedMiddleName:
    def test_drops_an_interior_token_keeps_first_and_last(self):
        rng = random.Random(5)
        result = dropped_middle_name("John Michael Quincy Smith", rng)
        tokens = result.split()
        assert tokens[0] == "John"
        assert tokens[-1] == "Smith"
        assert len(tokens) == 3

    def test_none_for_two_tokens(self):
        rng = random.Random(1)
        assert dropped_middle_name("John Smith", rng) is None


class TestInitialsForGivenName:
    def test_replaces_given_names_with_initials(self):
        rng = random.Random(1)
        result = initials_for_given_name("Abboud Abdul Latif Hassan AL-ZOMOR", rng)
        assert result == "A. A. L. H. AL-ZOMOR"

    def test_none_for_single_token(self):
        rng = random.Random(1)
        assert initials_for_given_name("Madonna", rng) is None


class TestLegalSuffixChange:
    def test_drops_or_swaps_known_suffix(self):
        outcomes = set()
        for seed in range(30):
            result = legal_suffix_change("Acme Trading Ltd", random.Random(seed))
            assert result is not None
            outcomes.add(result)
        assert "Acme Trading" in outcomes
        assert any(o not in {"Acme Trading", "Acme Trading Ltd"} for o in outcomes)

    def test_strips_dangling_comma_when_dropping(self):
        for seed in range(20):
            result = legal_suffix_change("Acme Trading, Ltd", random.Random(seed))
            if result == "Acme Trading":
                return
        raise AssertionError("expected at least one seed to drop the suffix and comma")

    def test_none_when_no_legal_suffix(self):
        rng = random.Random(1)
        assert legal_suffix_change("Acme Trading", rng) is None


class TestAddDiacritics:
    def test_adds_an_accent(self):
        rng = random.Random(1)
        result = add_diacritics("Acme Trading", rng)
        assert result != "Acme Trading"
        assert len(result) == len("Acme Trading")

    def test_none_when_no_vowels(self):
        rng = random.Random(1)
        assert add_diacritics("XYZ", rng) is None


class TestRemoveDiacritics:
    def test_strips_accents(self):
        rng = random.Random(1)
        assert remove_diacritics("Müller", rng) == "Muller"

    def test_none_when_already_plain(self):
        rng = random.Random(1)
        assert remove_diacritics("Acme Trading", rng) is None
