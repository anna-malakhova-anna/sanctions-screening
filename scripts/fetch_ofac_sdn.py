#!/usr/bin/env python3
"""Download the current OFAC SDN.XML, ingest it, and write a versioned snapshot.

Usage: uv run scripts/fetch_ofac_sdn.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sanctions_screening.ingest.ofac import iter_sdn_entities, read_publish_date  # noqa: E402
from sanctions_screening.snapshot import write_snapshot  # noqa: E402

# Documented, current source. The legacy treasury.gov path has mirrored the same
# content as a fallback historically, but is not guaranteed to keep doing so.
SDN_XML_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"

RAW_DIR = REPO_ROOT / "data" / "raw"
SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / "sdn.xml"

    print(f"Downloading {SDN_XML_URL} ...")
    # urllib fails TLS verification in some sandboxed/proxied environments; curl
    # uses the system CA store and has proven reliable here.
    subprocess.run(
        ["curl", "-sS", "-L", "--fail", "--max-time", "60", "-o", str(raw_path), SDN_XML_URL],
        check=True,
    )

    list_version = read_publish_date(raw_path)
    print(f"Ingesting list version {list_version} ...")
    entities = list(iter_sdn_entities(raw_path, list_version=list_version))
    print(f"Parsed {len(entities)} entities")

    out_path = write_snapshot(entities, SNAPSHOT_DIR, "OFAC SDN", list_version)
    print(f"Wrote snapshot: {out_path}")


if __name__ == "__main__":
    main()
