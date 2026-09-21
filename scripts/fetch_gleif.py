#!/usr/bin/env python3
"""Pull a sample of GLEIF LEI records (the clean population) and write a
versioned snapshot. See ingest/gleif.py's module docstring for why this pages
the public API rather than downloading the full Golden Copy file.

Usage: uv run scripts/fetch_gleif.py [max_records]
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sanctions_screening.ingest.gleif import current_golden_copy_date, iter_lei_records  # noqa: E402
from sanctions_screening.snapshot import write_snapshot  # noqa: E402

SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots"
DEFAULT_MAX_RECORDS = 5000


def main() -> None:
    max_records = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MAX_RECORDS

    list_version = current_golden_copy_date()
    print(f"Fetching {max_records} GLEIF records (Golden Copy {list_version}) ...")
    entities = list(iter_lei_records(max_records=max_records, list_version=list_version))
    print(f"Parsed {len(entities)} entities")

    out_path = write_snapshot(entities, SNAPSHOT_DIR, "GLEIF LEI", list_version)
    print(f"Wrote snapshot: {out_path}")


if __name__ == "__main__":
    main()
