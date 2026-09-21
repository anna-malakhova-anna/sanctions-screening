from sanctions_screening.ingest import gleif
from sanctions_screening.ingest.gleif import (
    _build_url,
    _country_name,
    _parse_aliases,
    entity_from_lei_record,
    iter_lei_records,
)
from sanctions_screening.models import AliasStrength, EntityType


def make_record(
    *,
    lei="984500886653F8100942",
    legal_name="AGYSIALE CONSULTING",
    country="FR",
    other_names=None,
    transliterated_other_names=None,
) -> dict:
    return {
        "type": "lei-records",
        "id": lei,
        "attributes": {
            "entity": {
                "legalName": {"name": legal_name, "language": "fr"},
                "otherNames": other_names or [],
                "transliteratedOtherNames": transliterated_other_names or [],
                "legalAddress": {"country": country},
            }
        },
    }


class TestCountryName:
    def test_known_alpha2_resolves_to_full_name(self):
        assert _country_name("FR") == "France"
        assert _country_name("GB") == "United Kingdom"

    def test_unknown_code_falls_back_to_raw_code(self):
        assert _country_name("XK") == "XK"

    def test_none_input_returns_none(self):
        assert _country_name(None) is None


class TestParseAliases:
    def test_other_names_become_strong_aliases(self):
        attrs = {
            "otherNames": [{"name": "Hop Dragon Kft.", "language": "hu", "type": "TRADING_OR_OPERATING_NAME"}],
            "transliteratedOtherNames": [],
        }
        aliases = _parse_aliases(attrs)
        assert len(aliases) == 1
        assert aliases[0].name == "Hop Dragon Kft."
        assert aliases[0].strength is AliasStrength.STRONG

    def test_dedupes_names_across_both_groups(self):
        attrs = {
            "otherNames": [{"name": "Acme Co", "type": "TRADING_OR_OPERATING_NAME"}],
            "transliteratedOtherNames": [{"name": "Acme Co", "type": "ALTERNATIVE_LANGUAGE_LEGAL_NAME"}],
        }
        aliases = _parse_aliases(attrs)
        assert len(aliases) == 1

    def test_no_names_returns_empty_list(self):
        assert _parse_aliases({"otherNames": [], "transliteratedOtherNames": []}) == []

    def test_missing_keys_handled_gracefully(self):
        assert _parse_aliases({}) == []


class TestEntityFromLeiRecord:
    def test_builds_entity_with_expected_fields(self):
        record = make_record(other_names=[{"name": "Agysiale", "type": "TRADING_OR_OPERATING_NAME"}])
        entity = entity_from_lei_record(record, list_version="2026-09-21")

        assert entity.source_id == "GLEIF-984500886653F8100942"
        assert entity.list_name == "GLEIF LEI"
        assert entity.list_version == "2026-09-21"
        assert entity.canonical_name == "AGYSIALE CONSULTING"
        assert entity.entity_type is EntityType.COMPANY
        assert entity.countries == ["France"]
        assert entity.dob is None
        assert entity.programs == []
        assert entity.aliases[0].name == "Agysiale"

    def test_missing_legal_name_returns_none(self):
        record = make_record(legal_name=None)
        record["attributes"]["entity"]["legalName"] = {}
        assert entity_from_lei_record(record, list_version="2026-09-21") is None

    def test_missing_id_returns_none(self):
        record = make_record()
        del record["id"]
        assert entity_from_lei_record(record, list_version="2026-09-21") is None

    def test_no_country_yields_empty_countries_list(self):
        record = make_record(country=None)
        record["attributes"]["entity"]["legalAddress"] = {}
        entity = entity_from_lei_record(record, list_version="2026-09-21")
        assert entity.countries == []


class TestBuildUrl:
    def test_encodes_page_and_filter_params(self):
        url = _build_url(2, 200, {"entity.status": "ACTIVE"})
        assert "page%5Bnumber%5D=2" in url
        assert "page%5Bsize%5D=200" in url
        assert "filter%5Bentity.status%5D=ACTIVE" in url
        assert url.startswith(gleif.API_BASE)


class TestIterLeiRecords:
    def test_stops_at_max_records_across_pages(self, monkeypatch):
        pages = [
            {"data": [make_record(lei=f"LEI{i}") for i in range(200)]},
            {"data": [make_record(lei=f"LEI{i}") for i in range(200, 400)]},
        ]
        calls = []

        def fake_fetch(page_number, page_size, filters):
            calls.append(page_number)
            return pages[page_number - 1]

        monkeypatch.setattr(gleif, "_fetch_page", fake_fetch)

        entities = list(iter_lei_records(max_records=250, list_version="2026-09-21"))
        assert len(entities) == 250
        assert calls == [1, 2]

    def test_stops_when_a_page_returns_no_data(self, monkeypatch):
        def fake_fetch(page_number, page_size, filters):
            if page_number == 1:
                return {"data": [make_record(lei="ONLY")]}
            return {"data": []}

        monkeypatch.setattr(gleif, "_fetch_page", fake_fetch)

        entities = list(iter_lei_records(max_records=5000, list_version="2026-09-21"))
        assert len(entities) == 1

    def test_uses_explicit_list_version_without_network_call(self, monkeypatch):
        def fake_fetch(page_number, page_size, filters):
            return {"data": [make_record()]}

        called_current_golden_copy = False

        def fake_current_golden_copy_date():
            nonlocal called_current_golden_copy
            called_current_golden_copy = True
            return "2099-01-01"

        monkeypatch.setattr(gleif, "_fetch_page", fake_fetch)
        monkeypatch.setattr(gleif, "current_golden_copy_date", fake_current_golden_copy_date)

        entities = list(iter_lei_records(max_records=1, list_version="2026-09-21"))
        assert entities[0].list_version == "2026-09-21"
        assert called_current_golden_copy is False
