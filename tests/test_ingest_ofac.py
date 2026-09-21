from datetime import date
from pathlib import Path

from sanctions_screening.ingest.ofac import iter_sdn_entities, parse_dob, read_publish_date
from sanctions_screening.models import AliasStrength, EntityType

FIXTURE = Path(__file__).parent / "fixtures" / "sdn_sample.xml"


class TestParseDob:
    def test_day_month_year(self):
        dob = parse_dob("19 Apr 1947")
        assert dob.earliest == date(1947, 4, 19)
        assert dob.latest == date(1947, 4, 19)
        assert dob.raw == "19 Apr 1947"

    def test_year_only_spans_the_whole_year(self):
        dob = parse_dob("1938")
        assert dob.earliest == date(1938, 1, 1)
        assert dob.latest == date(1938, 12, 31)

    def test_month_year_spans_the_whole_month(self):
        dob = parse_dob("Jan 1965")
        assert dob.earliest == date(1965, 1, 1)
        assert dob.latest == date(1965, 1, 31)

    def test_month_year_spans_correct_days_for_short_month(self):
        dob = parse_dob("Feb 1943")
        assert dob.latest == date(1943, 2, 28)

    def test_circa_year_keeps_raw_but_parses_as_plain_year(self):
        dob = parse_dob("circa 1957")
        assert dob.earliest == date(1957, 1, 1)
        assert dob.latest == date(1957, 12, 31)
        assert dob.raw == "circa 1957"

    def test_circa_day_month_year(self):
        dob = parse_dob("circa 07 Jul 1966")
        assert dob.earliest == date(1966, 7, 7)
        assert dob.latest == date(1966, 7, 7)

    def test_year_to_year_range(self):
        dob = parse_dob("1955 to 1957")
        assert dob.earliest == date(1955, 1, 1)
        assert dob.latest == date(1957, 12, 31)

    def test_month_year_to_month_year_range(self):
        dob = parse_dob("Mar 1965 to Mar 1966")
        assert dob.earliest == date(1965, 3, 1)
        assert dob.latest == date(1966, 3, 31)

    def test_full_date_range(self):
        dob = parse_dob("01 Jan 1961 to 31 Dec 1962")
        assert dob.earliest == date(1961, 1, 1)
        assert dob.latest == date(1962, 12, 31)

    def test_unrecognized_format_falls_back_to_raw_only(self):
        dob = parse_dob("sometime in the 60s")
        assert dob.earliest is None
        assert dob.latest is None
        assert dob.raw == "sometime in the 60s"
        assert dob.is_known is False


class TestReadPublishDate:
    def test_reads_and_formats_iso(self):
        assert read_publish_date(FIXTURE) == "2026-09-18"


class TestIterSdnEntities:
    def test_yields_one_entity_per_entry(self):
        entities = list(iter_sdn_entities(FIXTURE))
        assert len(entities) == 4

    def test_individual_full_name_and_type(self):
        entities = list(iter_sdn_entities(FIXTURE))
        individual = next(e for e in entities if e.source_id == "OFAC-2677")
        assert individual.canonical_name == "Abboud Abdul Latif Hassan AL-ZOMOR"
        assert individual.entity_type is EntityType.INDIVIDUAL
        assert individual.dob.earliest == date(1947, 4, 19)
        assert individual.countries == ["Egypt"]
        assert individual.programs == ["SDGT"]

    def test_individual_aliases_carry_strength(self):
        entities = list(iter_sdn_entities(FIXTURE))
        individual = next(e for e in entities if e.source_id == "OFAC-2677")
        by_name = {a.name: a.strength for a in individual.aliases}
        assert by_name["Abbud ZUMAR"] is AliasStrength.STRONG
        assert by_name["ZOMOR"] is AliasStrength.WEAK

    def test_entity_type_maps_to_company(self):
        entities = list(iter_sdn_entities(FIXTURE))
        bank = next(e for e in entities if e.source_id == "OFAC-306")
        assert bank.entity_type is EntityType.COMPANY
        assert bank.canonical_name == "BANCO NACIONAL DE CUBA, LTD."
        assert set(bank.countries) == {"Switzerland", "Spain"}

    def test_vessel_type_and_no_firstname(self):
        entities = list(iter_sdn_entities(FIXTURE))
        vessel = next(e for e in entities if e.source_id == "OFAC-4238")
        assert vessel.entity_type is EntityType.VESSEL
        assert vessel.canonical_name == "MAR AZUL"

    def test_aircraft_type_with_approximate_dob(self):
        entities = list(iter_sdn_entities(FIXTURE))
        aircraft = next(e for e in entities if e.source_id == "OFAC-9001")
        assert aircraft.entity_type is EntityType.AIRCRAFT
        assert aircraft.dob.raw == "circa 1965"

    def test_list_version_applied_to_every_entity(self):
        entities = list(iter_sdn_entities(FIXTURE))
        assert all(e.list_version == "2026-09-18" for e in entities)
        assert all(e.list_name == "OFAC SDN" for e in entities)

    def test_explicit_list_version_overrides_header(self):
        entities = list(iter_sdn_entities(FIXTURE, list_version="test-version"))
        assert all(e.list_version == "test-version" for e in entities)
