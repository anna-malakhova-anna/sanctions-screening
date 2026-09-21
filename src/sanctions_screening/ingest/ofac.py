"""OFAC SDN ingest: parse the published SDN.XML feed into the canonical Entity model.

Source: https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML
(the legacy https://www.treasury.gov/ofac/downloads/sdn.xml URL currently mirrors the
same content, but the Sanctions List Service is the documented, current host).

Schema notes gathered by inspecting the live feed on 2026-09-21 (verify again before
relying on this — OFAC has changed formats before):

- Root element is namespaced (`xmlns="https://.../exports/XML"`); every child tag
  inherits that namespace, so lookups strip it rather than hardcode it twice.
- `sdnType` is one of: Individual, Entity, Vessel, Aircraft. No "Company" — OFAC's
  "Entity" is our EntityType.COMPANY.
- Name is `lastName` (+ optional `firstName` for individuals and their akas). Vessels
  and aircraft only ever populate `lastName`.
- `akaList/aka/category` is exactly "strong" or "weak" — maps directly onto
  AliasStrength.
- `dateOfBirthList/dateOfBirthItem/dateOfBirth` is free text in one of 8 observed
  shapes: "DD Mon YYYY", "Mon YYYY", "YYYY", each optionally prefixed "circa ", and
  each optionally forming a "<start> to <end>" range. There is no dedicated
  "approximate" flag beyond the "circa " prefix, and OFAC does not widen the range
  for a circa date — we don't invent one either; we just keep "circa" in `raw` so
  downstream consumers know the precision is lower than it looks.
- Countries come from `addressList/address/country` and `nationalityList/nationality/country`.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from sanctions_screening.models import Alias, AliasStrength, DateRange, Entity, EntityType

LIST_NAME = "OFAC SDN"

_ENTITY_TYPE_MAP: dict[str, EntityType] = {
    "individual": EntityType.INDIVIDUAL,
    "entity": EntityType.COMPANY,
    "vessel": EntityType.VESSEL,
    "aircraft": EntityType.AIRCRAFT,
}

_DAY_MONTH_YEAR_RE = re.compile(r"^\d{1,2} [A-Za-z]{3} \d{4}$")
_MONTH_YEAR_RE = re.compile(r"^[A-Za-z]{3} \d{4}$")
_YEAR_RE = re.compile(r"^\d{4}$")


def _local_tag(elem: ET.Element) -> str:
    """Strip the namespace prefix from an element's tag, e.g. '{ns}uid' -> 'uid'."""
    tag = elem.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_text(elem: ET.Element, local_name: str) -> str | None:
    for child in elem:
        if _local_tag(child) == local_name and child.text:
            return child.text.strip()
    return None


def _find_all(elem: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in elem if _local_tag(child) == local_name]


def _full_name(first_name: str | None, last_name: str | None) -> str:
    parts = [p for p in (first_name, last_name) if p]
    return " ".join(parts)


def _parse_date_bound(text: str, *, end: bool) -> date:
    """Parse one side of a DOB (or a standalone DOB) into a concrete date.

    A bare year or month becomes the earliest possible day for a range start, or
    the latest possible day for a range end -- that's what makes a DateRange a
    genuine bound rather than an arbitrary guess (e.g. "1965" as `earliest` means
    Jan 1 1965, as `latest` means Dec 31 1965).
    """
    text = text.strip()
    if _DAY_MONTH_YEAR_RE.match(text):
        return datetime.strptime(text, "%d %b %Y").date()
    if _MONTH_YEAR_RE.match(text):
        parsed = datetime.strptime(text, "%b %Y").date()
        if end:
            last_day = calendar.monthrange(parsed.year, parsed.month)[1]
            return parsed.replace(day=last_day)
        return parsed.replace(day=1)
    if _YEAR_RE.match(text):
        year = int(text)
        return date(year, 12, 31) if end else date(year, 1, 1)
    raise ValueError(f"unrecognized date-of-birth bound: {text!r}")


def parse_dob(raw: str) -> DateRange:
    """Parse an OFAC dateOfBirth string into a DateRange.

    Handles all 8 shapes observed in the live feed: plain / "circa "-prefixed,
    each as either a single date (day-month-year, month-year, or year alone) or
    a "<start> to <end>" range. Falls back to an unparsed DateRange (raw kept,
    bounds left None) for anything else, rather than raising -- a malformed date
    from the source shouldn't stop the whole entry from ingesting.
    """
    raw = raw.strip()
    text = raw[6:] if raw.lower().startswith("circa ") else raw

    try:
        if " to " in text:
            start_text, end_text = text.split(" to ", 1)
            earliest = _parse_date_bound(start_text, end=False)
            latest = _parse_date_bound(end_text, end=True)
        else:
            earliest = _parse_date_bound(text, end=False)
            latest = _parse_date_bound(text, end=True)
    except ValueError:
        return DateRange(raw=raw)

    return DateRange(earliest=earliest, latest=latest, raw=raw)


def _parse_aliases(entry: ET.Element) -> list[Alias]:
    aliases: list[Alias] = []
    for aka_list in _find_all(entry, "akaList"):
        for aka in _find_all(aka_list, "aka"):
            name = _full_name(_find_text(aka, "firstName"), _find_text(aka, "lastName"))
            if not name:
                continue
            category = (_find_text(aka, "category") or "weak").lower()
            strength = AliasStrength.STRONG if category == "strong" else AliasStrength.WEAK
            aliases.append(Alias(name=name, strength=strength))
    return aliases


def _parse_dob_range(entry: ET.Element) -> DateRange | None:
    for dob_list in _find_all(entry, "dateOfBirthList"):
        for item in _find_all(dob_list, "dateOfBirthItem"):
            raw = _find_text(item, "dateOfBirth")
            if raw:
                return parse_dob(raw)
    return None


def _parse_countries(entry: ET.Element) -> list[str]:
    countries: list[str] = []
    for list_name, item_name in (("addressList", "address"), ("nationalityList", "nationality")):
        for group in _find_all(entry, list_name):
            for item in _find_all(group, item_name):
                country = _find_text(item, "country")
                if country and country not in countries:
                    countries.append(country)
    return countries


def _parse_programs(entry: ET.Element) -> list[str]:
    programs: list[str] = []
    for program_list in _find_all(entry, "programList"):
        for program in _find_all(program_list, "program"):
            if program.text:
                programs.append(program.text.strip())
    return programs


def entity_from_sdn_entry(entry: ET.Element, *, list_version: str) -> Entity | None:
    """Build one canonical Entity from a single <sdnEntry> element, or None if it
    has no usable name (a handful of malformed source rows do occur)."""
    uid = _find_text(entry, "uid")
    canonical_name = _full_name(_find_text(entry, "firstName"), _find_text(entry, "lastName"))
    if not uid or not canonical_name:
        return None

    sdn_type = (_find_text(entry, "sdnType") or "").lower()
    entity_type = _ENTITY_TYPE_MAP.get(sdn_type, EntityType.OTHER)

    return Entity(
        source_id=f"OFAC-{uid}",
        list_name=LIST_NAME,
        list_version=list_version,
        canonical_name=canonical_name,
        entity_type=entity_type,
        aliases=_parse_aliases(entry),
        dob=_parse_dob_range(entry),
        countries=_parse_countries(entry),
        programs=_parse_programs(entry),
    )


def read_publish_date(xml_path: Path | str) -> str:
    """Read just the <Publish_Date> header, formatted as an ISO date, without
    parsing the full (multi-MB) entry list. Used as the list_version."""
    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if _local_tag(elem) == "Publish_Date" and elem.text:
            parsed = datetime.strptime(elem.text.strip(), "%m/%d/%Y").date()
            return parsed.isoformat()
        if _local_tag(elem) == "publshInformation":
            break
    raise ValueError(f"no <Publish_Date> found in {xml_path}")


def iter_sdn_entities(xml_path: Path | str, *, list_version: str | None = None) -> Iterator[Entity]:
    """Stream Entities out of an SDN.XML file one <sdnEntry> at a time.

    Uses iterparse + element.clear() rather than a full parse: the live file is
    ~30MB and only growing, and there's no reason to hold the whole tree in
    memory to walk it once.
    """
    version = list_version or read_publish_date(xml_path)

    context = ET.iterparse(xml_path, events=("end",))
    for _, elem in context:
        if _local_tag(elem) == "sdnEntry":
            entity = entity_from_sdn_entry(elem, list_version=version)
            if entity is not None:
                yield entity
            elem.clear()
