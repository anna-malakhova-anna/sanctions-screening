"""Versioned list snapshots.

A snapshot is a JSONL file of normalized Entities, one list-version per file, so
the match engine always runs against a known, reproducible cut of the source
list rather than whatever happens to be on disk.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from sanctions_screening.models import Entity


def snapshot_path(out_dir: Path | str, list_name: str, list_version: str) -> Path:
    slug = list_name.lower().replace(" ", "_")
    return Path(out_dir) / f"{slug}_{list_version}.jsonl"


def write_snapshot(entities: Iterable[Entity], out_dir: Path | str, list_name: str, list_version: str) -> Path:
    out_path = snapshot_path(out_dir, list_name, list_version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for entity in entities:
            f.write(entity.model_dump_json())
            f.write("\n")
    return out_path


def read_snapshot(path: Path | str) -> Iterator[Entity]:
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield Entity.model_validate_json(line)
