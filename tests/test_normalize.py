from sanctions_screening.normalize import (
    collapse_whitespace,
    fold_case,
    normalize_name,
    strip_diacritics,
    strip_legal_suffixes,
    strip_punctuation,
)


class TestStripDiacritics:
    def test_removes_accents(self):
        assert strip_diacritics("Muḥammad") == "Muhammad"

    def test_removes_umlaut(self):
        assert strip_diacritics("Müller") == "Muller"

    def test_leaves_plain_ascii_unchanged(self):
        assert strip_diacritics("Smith") == "Smith"

    def test_cyrillic_transliterates(self):
        # not a perfect transliteration standard, but stable and deterministic
        assert strip_diacritics("Пу́тин") != "Пу́тин"


class TestFoldCase:
    def test_lowercases(self):
        assert fold_case("ACME Trading") == "acme trading"

    def test_idempotent(self):
        assert fold_case(fold_case("Mixed CASE")) == fold_case("Mixed CASE")


class TestStripPunctuation:
    def test_hyphen_becomes_space_not_removed(self):
        assert strip_punctuation("Smith-Jones") == "Smith Jones"

    def test_period_and_comma(self):
        assert strip_punctuation("Acme, Ltd.") == "Acme  Ltd "

    def test_apostrophe(self):
        assert strip_punctuation("O'Brien") == "O Brien"

    def test_no_punctuation_unchanged(self):
        assert strip_punctuation("Acme Trading") == "Acme Trading"


class TestCollapseWhitespace:
    def test_multiple_spaces(self):
        assert collapse_whitespace("Acme    Trading") == "Acme Trading"

    def test_leading_trailing(self):
        assert collapse_whitespace("  Acme Trading  ") == "Acme Trading"

    def test_tabs_and_newlines(self):
        assert collapse_whitespace("Acme\tTrading\n") == "Acme Trading"


class TestStripLegalSuffixes:
    def test_single_suffix(self):
        assert strip_legal_suffixes("acme trading ltd") == "acme trading"

    def test_multiple_stacked_suffixes(self):
        assert strip_legal_suffixes("acme trading co ltd") == "acme trading"

    def test_no_suffix_unchanged(self):
        assert strip_legal_suffixes("acme trading") == "acme trading"

    def test_suffix_only_stripped_at_end(self):
        # "co" appearing mid-name (e.g. a name like "Co Op Bank") must survive
        assert strip_legal_suffixes("co op bank") == "co op bank"

    def test_llc(self):
        assert strip_legal_suffixes("stark industries llc") == "stark industries"


class TestNormalizeNamePipeline:
    def test_full_pipeline_equates_variants(self):
        assert normalize_name("Acme, Ltd.") == normalize_name("Acme Limited")

    def test_diacritics_and_case_and_suffix_together(self):
        assert normalize_name("Müller Trading GmbH") == "muller trading"

    def test_diacritic_variant_matches_plain_ascii(self):
        assert normalize_name("Muḥammad Al-Amin") == normalize_name("Muhammad Al Amin")

    def test_stable_on_already_clean_input(self):
        assert normalize_name("acme trading") == "acme trading"
