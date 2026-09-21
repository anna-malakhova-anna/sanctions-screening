"""GLEIF ingest: the clean population.

GLEIF's role in this project isn't a watchlist -- it's a source of real legal
entity names to screen so that known negatives in the test set look like
plausible counterparties, not random strings.

Scoping decision, worth stating plainly: the handover doc frames GLEIF as
"open, bulk download," meaning the Golden Copy full-file dump (CSV/XML,
~3.4M records, multi-gigabyte). We don't ingest that file. Instead this
module pages through GLEIF's public search API
(https://api.gleif.org/api/v1/lei-records), which serves the identical
per-record data as the Golden Copy, and pulls a bounded sample. For "enough
real names to build a clean-negative population," a few thousand records is
plenty, and paging the API avoids parsing and storing gigabytes of records
that would never be used. If a larger population is ever needed, swap
`iter_lei_records` for a Golden Copy CSV reader without touching anything
downstream -- both paths yield the same Entity shape.

Schema notes gathered by probing the live API on 2026-09-21 (verify again
before relying on this):

- Pagination is JSON:API style: `page[number]` / `page[size]`, `page[size]`
  capped at 200 by the server.
- `data[].id` is the LEI itself -- a stable, unique identifier, used as our
  source_id.
- `attributes.entity.legalName.name` is the canonical name. GLEIF's LEI-CDF
  covers only legal entities (companies, funds, etc.) -- never individuals,
  vessels, or aircraft -- so entity_type is always COMPANY here.
- `attributes.entity.otherNames` / `transliteratedOtherNames` are alternate
  names (trading names, previous legal names, other-language variants) with
  a `type` tag but no strong/weak quality signal like OFAC's akaList. We
  treat all of them as STRONG: unlike OFAC's low-confidence aliases, these
  are GLEIF-validated name records, not loosely associated guesses.
- `attributes.entity.legalAddress.country` is an ISO 3166-1 alpha-2 code
  (e.g. "FR"), not a country name -- OFAC's feed gives full names, so we
  convert via pycountry to keep the `countries` field comparable across
  sources. A handful of user-assigned or retired codes (e.g. "XK" Kosovo)
  aren't in the ISO standard list; we fall back to the raw code rather than
  dropping the country.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import datetime

import pycountry

from sanctions_screening.models import Alias, AliasStrength, Entity, EntityType

LIST_NAME = "GLEIF LEI"
API_BASE = "https://api.gleif.org/api/v1/lei-records"
MAX_PAGE_SIZE = 200

DEFAULT_FILTERS = {
    "entity.status": "ACTIVE",
    "entity.category": "GENERAL",
}


def _country_name(code: str | None) -> str | None:
    if not code:
        return None
    country = pycountry.countries.get(alpha_2=code)
    return country.name if country else code


def _parse_aliases(entity_attrs: dict) -> list[Alias]:
    aliases: list[Alias] = []
    seen: set[str] = set()
    for group in ("otherNames", "transliteratedOtherNames"):
        for other in entity_attrs.get(group) or []:
            name = (other.get("name") or "").strip()
            if name and name not in seen:
                aliases.append(Alias(name=name, strength=AliasStrength.STRONG))
                seen.add(name)
    return aliases


def entity_from_lei_record(record: dict, *, list_version: str) -> Entity | None:
    """Build one canonical Entity from a single GLEIF API `data[]` record."""
    lei = record.get("id")
    entity_attrs = record.get("attributes", {}).get("entity", {})
    legal_name = (entity_attrs.get("legalName") or {}).get("name")
    if not lei or not legal_name:
        return None

    country = _country_name((entity_attrs.get("legalAddress") or {}).get("country"))

    return Entity(
        source_id=f"GLEIF-{lei}",
        list_name=LIST_NAME,
        list_version=list_version,
        canonical_name=legal_name,
        entity_type=EntityType.COMPANY,
        aliases=_parse_aliases(entity_attrs),
        dob=None,
        countries=[country] if country else [],
        programs=[],
    )


def _build_url(page_number: int, page_size: int, filters: dict[str, str]) -> str:
    params: list[tuple[str, str]] = [
        ("page[number]", str(page_number)),
        ("page[size]", str(page_size)),
    ]
    for key, value in filters.items():
        params.append((f"filter[{key}]", value))
    return f"{API_BASE}?{urllib.parse.urlencode(params)}"


def _fetch_page(page_number: int, page_size: int, filters: dict[str, str]) -> dict:
    url = _build_url(page_number, page_size, filters)
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def current_golden_copy_date() -> str:
    """The GLEIF API stamps every response with the Golden Copy publish date
    it's currently serving -- that's our list_version, one cheap request."""
    payload = _fetch_page(page_number=1, page_size=1, filters=DEFAULT_FILTERS)
    publish_date = payload["meta"]["goldenCopy"]["publishDate"]
    return datetime.fromisoformat(publish_date.replace("Z", "+00:00")).date().isoformat()


def iter_lei_records(
    *,
    max_records: int = 5000,
    page_size: int = MAX_PAGE_SIZE,
    filters: dict[str, str] | None = None,
    list_version: str | None = None,
) -> Iterator[Entity]:
    """Page through the GLEIF API and yield Entities, up to max_records.

    Bounded by default (5000) since this is a sample population, not a
    watchlist that needs to be exhaustive -- see the module docstring.
    """
    active_filters = DEFAULT_FILTERS if filters is None else filters
    version = list_version or current_golden_copy_date()

    fetched = 0
    page_number = 1
    while fetched < max_records:
        page = _fetch_page(page_number, min(page_size, max_records - fetched), active_filters)
        records = page.get("data", [])
        if not records:
            return
        for record in records:
            entity = entity_from_lei_record(record, list_version=version)
            if entity is not None:
                yield entity
                fetched += 1
                if fetched >= max_records:
                    return
        page_number += 1
