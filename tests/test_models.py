from sanctions_screening.models import Alias, AliasStrength, DateRange, Entity, EntityType


class TestDateRange:
    def test_unknown_dob_is_not_known(self):
        assert DateRange().is_known is False

    def test_partial_year_only_is_known(self):
        dob = DateRange(earliest="1965-01-01", latest="1965-12-31", raw="circa 1965")
        assert dob.is_known is True

    def test_single_bound_is_known(self):
        assert DateRange(earliest="1960-01-01").is_known is True


class TestEntity:
    def test_minimal_entity_constructs(self):
        e = Entity(
            source_id="OFAC-1234",
            list_name="OFAC SDN",
            list_version="2026-09-20",
            canonical_name="Acme Trading",
            entity_type=EntityType.COMPANY,
        )
        assert e.aliases == []
        assert e.dob is None

    def test_entity_with_aliases_and_dob(self):
        e = Entity(
            source_id="OFAC-5678",
            list_name="OFAC SDN",
            list_version="2026-09-20",
            canonical_name="John Smith",
            entity_type=EntityType.INDIVIDUAL,
            aliases=[
                Alias(name="Jon Smith", strength=AliasStrength.STRONG),
                Alias(name="J Smith", strength=AliasStrength.WEAK),
            ],
            dob=DateRange(raw="1970 to 1975"),
            countries=["Syria"],
        )
        assert e.aliases[0].strength is AliasStrength.STRONG
        assert e.dob.raw == "1970 to 1975"
