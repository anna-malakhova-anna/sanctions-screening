"""Canonical entity model that every list source (OFAC, and later OFSI/EU) normalizes into.

Keeping this source-agnostic is the point: the match engine and review queue
should never know a name came from OFAC's XML vs. someone else's CSV.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"
    VESSEL = "vessel"
    AIRCRAFT = "aircraft"
    OTHER = "other"


class AliasStrength(str, Enum):
    """OFAC tags each AKA with a quality: 'strong' aliases are reliable alternate
    identities, 'weak' ones are looser (e.g. partial or low-confidence) and should
    contribute less to a match score."""

    STRONG = "strong"
    WEAK = "weak"


class Alias(BaseModel):
    name: str
    strength: AliasStrength


class DateRange(BaseModel):
    """A date-of-birth is rarely a single known date on a sanctions list: it's
    'circa 1965', a year, or a spread of years. Modeling it as a range instead of
    forcing a single date avoids inventing precision the source doesn't have.
    """

    earliest: date | None = None
    latest: date | None = None
    raw: str | None = None

    @property
    def is_known(self) -> bool:
        return self.earliest is not None or self.latest is not None


class Entity(BaseModel):
    """One row on a watchlist, normalized into a common shape."""

    source_id: str = Field(description="Source system's own identifier, e.g. OFAC uid")
    list_name: str = Field(description="e.g. 'OFAC SDN'")
    list_version: str = Field(description="Snapshot version/date this entity came from")

    canonical_name: str
    entity_type: EntityType
    aliases: list[Alias] = Field(default_factory=list)

    dob: DateRange | None = None
    countries: list[str] = Field(default_factory=list)

    programs: list[str] = Field(default_factory=list, description="Sanctions programs, e.g. SDGT, UKRAINE-EO13662")
