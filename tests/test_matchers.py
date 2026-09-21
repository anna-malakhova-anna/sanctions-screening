from sanctions_screening.match.matchers import exact_score, jaro_winkler_score


class TestExactScore:
    def test_identical_strings_score_one(self):
        assert exact_score("acme trading", "acme trading") == 1.0

    def test_different_strings_score_zero(self):
        assert exact_score("acme trading", "acme trdaing") == 0.0

    def test_empty_strings_are_equal(self):
        assert exact_score("", "") == 1.0


class TestJaroWinklerScore:
    def test_identical_strings_score_one(self):
        assert jaro_winkler_score("acme trading", "acme trading") == 1.0

    def test_close_variant_scores_high(self):
        score = jaro_winkler_score("mohammed al amin", "muhammad al amin")
        assert score > 0.8

    def test_unrelated_strings_score_low(self):
        score = jaro_winkler_score("acme trading", "zzz unrelated corp")
        assert score < 0.6

    def test_shared_prefix_weighted_higher_than_shared_suffix(self):
        # Jaro-Winkler's defining property: matching prefix boosts the score
        # beyond plain Jaro similarity.
        prefix_match = jaro_winkler_score("acme trading", "acme trading co")
        suffix_match = jaro_winkler_score("trading acme", "co trading acme")
        assert prefix_match >= suffix_match

    def test_score_is_symmetric(self):
        a, b = "mohammed al amin", "muhammad al amin"
        assert jaro_winkler_score(a, b) == jaro_winkler_score(b, a)
