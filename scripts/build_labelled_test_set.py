#!/usr/bin/env python3
"""Build the labelled test set from the most recent OFAC and GLEIF snapshots.

Usage: uv run scripts/build_labelled_test_set.py [pairs_per_type]

Run scripts/fetch_ofac_sdn.py and scripts/fetch_gleif.py first if data/snapshots/
is empty.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sanctions_screening.perturb.harness import build_labelled_test_set, write_labelled_set  # noqa: E402
from sanctions_screening.snapshot import read_snapshot  # noqa: E402

SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots"
EVAL_DIR = REPO_ROOT / "data" / "eval"
DEFAULT_PAIRS_PER_TYPE = 20


def _latest(pattern: str) -> Path:
    matches = sorted(SNAPSHOT_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"no snapshot matching {pattern!r} in {SNAPSHOT_DIR}")
    return matches[-1]


def main() -> None:
    pairs_per_type = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PAIRS_PER_TYPE

    ofac_path = _latest("ofac_sdn_*.jsonl")
    gleif_path = _latest("gleif_lei_*.jsonl")
    print(f"Positive source: {ofac_path.name}")
    print(f"Negative source: {gleif_path.name}")

    ofac = list(read_snapshot(ofac_path))
    gleif = list(read_snapshot(gleif_path))

    pairs = build_labelled_test_set(ofac, gleif, pairs_per_type=pairs_per_type)
    n_positive = sum(1 for p in pairs if p.is_positive)
    n_negative = len(pairs) - n_positive
    print(f"Built {len(pairs)} rows ({n_positive} positive, {n_negative} negative)")

    out_path = write_labelled_set(pairs, EVAL_DIR / "labelled_test_set.jsonl")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
