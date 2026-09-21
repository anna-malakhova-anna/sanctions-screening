#!/usr/bin/env python3
"""Build the data the app ships with: committed, small, and version-controlled,
unlike data/snapshots and data/eval (regenerable build artifacts, gitignored).

Produces, in data/bundled/:
  - ofac_sdn_<version>.jsonl   -- the watchlist the match engine runs against
  - labelled_test_set.jsonl    -- ground truth for the live precision/recall readout
  - demo_counterparties.csv    -- the ~200-row file that loads on open

Run scripts/fetch_ofac_sdn.py and scripts/fetch_gleif.py first.

Usage: uv run scripts/build_demo_data.py
"""

from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sanctions_screening.perturb.harness import build_labelled_test_set, write_labelled_set  # noqa: E402
from sanctions_screening.snapshot import read_snapshot  # noqa: E402

SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots"
BUNDLED_DIR = REPO_ROOT / "data" / "bundled"

# Lands at ~198 rows against the current OFAC/GLEIF snapshots -- see the
# handover doc's "200-row demo file" requirement. Not exact by design: it's
# whatever a fixed seed and pairs_per_type actually produce, not a padded
# round number.
DEMO_PAIRS_PER_TYPE = 11
DEMO_SEED = 7


def _latest(pattern: str) -> Path:
    matches = sorted(SNAPSHOT_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"no snapshot matching {pattern!r} in {SNAPSHOT_DIR}")
    return matches[-1]


def main() -> None:
    BUNDLED_DIR.mkdir(parents=True, exist_ok=True)

    ofac_path = _latest("ofac_sdn_*.jsonl")
    gleif_path = _latest("gleif_lei_*.jsonl")
    print(f"Watchlist source: {ofac_path.name}")
    print(f"Clean population source: {gleif_path.name}")

    bundled_ofac_path = BUNDLED_DIR / ofac_path.name
    shutil.copyfile(ofac_path, bundled_ofac_path)
    print(f"Bundled: {bundled_ofac_path}")

    ofac = list(read_snapshot(ofac_path))
    gleif = list(read_snapshot(gleif_path))

    pairs = build_labelled_test_set(ofac, gleif, pairs_per_type=DEMO_PAIRS_PER_TYPE, seed=DEMO_SEED)
    labelled_path = write_labelled_set(pairs, BUNDLED_DIR / "labelled_test_set.jsonl")
    print(f"Bundled: {labelled_path} ({len(pairs)} rows)")

    demo_csv_path = BUNDLED_DIR / "demo_counterparties.csv"
    with demo_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name"])
        for pair in pairs:
            writer.writerow([pair.query_name])
    print(f"Bundled: {demo_csv_path} ({len(pairs)} rows)")


if __name__ == "__main__":
    main()
