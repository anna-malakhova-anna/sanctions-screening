#!/usr/bin/env python3
"""Run the labelled test set through the match engine and report recall by
perturbation type plus the negative false-positive rate, at a given score
threshold.

This is a diagnostic for matcher development, not the app's threshold UI --
the point (per the handover doc) is being able to say *which failure mode*
the matcher is weak on, not just report one aggregate number.

Usage: uv run scripts/evaluate_matcher.py [threshold]
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sanctions_screening.match.engine import build_search_index, match_batch  # noqa: E402
from sanctions_screening.perturb.harness import PerturbationType, read_labelled_set  # noqa: E402
from sanctions_screening.snapshot import read_snapshot  # noqa: E402

SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots"
EVAL_DIR = REPO_ROOT / "data" / "eval"
DEFAULT_THRESHOLD = 0.85


def _latest(pattern: str) -> Path:
    matches = sorted(SNAPSHOT_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"no snapshot matching {pattern!r} in {SNAPSHOT_DIR}")
    return matches[-1]


def main() -> None:
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_THRESHOLD

    ofac_path = _latest("ofac_sdn_*.jsonl")
    labelled_path = EVAL_DIR / "labelled_test_set.jsonl"
    print(f"Watchlist: {ofac_path.name}")
    print(f"Labelled set: {labelled_path.name}")
    print(f"Threshold: {threshold}\n")

    ofac = list(read_snapshot(ofac_path))
    index = build_search_index(ofac)
    pairs = list(read_labelled_set(labelled_path))

    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "top1_correct": 0, "flagged": 0})
    false_positives = 0
    n_negative = 0

    t0 = time.time()
    all_results = match_batch([pair.query_name for pair in pairs], index, top_k=1)
    for pair, results in zip(pairs, all_results, strict=True):
        top = results[0] if results else None
        stat = by_type[pair.perturbation_type.value]
        stat["n"] += 1
        if pair.is_positive:
            correct = top is not None and top.source_id == pair.source_id
            if correct:
                stat["top1_correct"] += 1
            if correct and top.score >= threshold:
                stat["flagged"] += 1
        else:
            n_negative += 1
            if top and top.score >= threshold:
                false_positives += 1
    elapsed = time.time() - t0

    print(f"{len(pairs)} queries against {len(index)} indexed names in {elapsed:.1f}s ({elapsed / len(pairs) * 1000:.0f}ms/query)\n")
    print(f"{'perturbation type':28s} {'n':>4s} {'top-1 correct':>14s} {'recall@threshold':>17s}")
    for ptype in PerturbationType:
        if ptype is PerturbationType.NEGATIVE_CONTROL:
            continue
        s = by_type.get(ptype.value)
        if not s or s["n"] == 0:
            print(f"{ptype.value:28s} {'--':>4s} {'(no rows)':>14s}")
            continue
        top1_rate = s["top1_correct"] / s["n"]
        recall = s["flagged"] / s["n"]
        print(f"{ptype.value:28s} {s['n']:4d} {top1_rate:14.0%} {recall:17.0%}")

    print(f"\nFalse positive rate on negatives: {false_positives}/{n_negative} = {false_positives / n_negative:.1%}")


if __name__ == "__main__":
    main()
