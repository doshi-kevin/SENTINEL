"""
Ingest the DARPA TC E5 FiveDirections .bin.gz files at ``data/raw/e5/Data/fivedirections/``
through ``AutoPipeline``: parse Avro -> events DataFrames -> build 1-second
graph windows + labels.csv at ``data/auto_processed/``.

Idempotent: skips outright if ``data/auto_processed/graphs/`` already has the
expected graph count and ``labels.csv`` exists.

Usage::

    python scripts/ingest_e5.py
    python scripts/ingest_e5.py --max-files 5     # quick smoke run
    python scripts/ingest_e5.py --force           # re-ingest even if outputs present

Requires the data to already be on disk — run ``python scripts/download_e5.py`` first.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "e5" / "Data" / "fivedirections"
OUT_DIR = REPO_ROOT / "data" / "auto_processed"
GRAPHS_DIR = OUT_DIR / "graphs"
LABELS_CSV = OUT_DIR / "labels.csv"

# Sanity threshold — README says ~6,051; allow some drift across re-runs.
EXPECTED_MIN_GRAPHS = 5_000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-files", type=int, default=None,
                        help="ingest at most N .bin.gz files (smoke testing)")
    parser.add_argument("--force", action="store_true",
                        help="re-ingest even if outputs already present")
    args = parser.parse_args()

    if not RAW_DIR.is_dir():
        print(f"ERROR: raw data dir not found: {RAW_DIR}", file=sys.stderr)
        print("Run: python scripts/download_e5.py", file=sys.stderr)
        return 1

    raw_files = sorted(RAW_DIR.glob("*.bin*.gz"))
    if not raw_files:
        print(f"ERROR: no .bin.gz files in {RAW_DIR}", file=sys.stderr)
        print("Run: python scripts/download_e5.py", file=sys.stderr)
        return 1

    if args.max_files:
        raw_files = raw_files[: args.max_files]
        print(f"--max-files {args.max_files}: ingesting first {len(raw_files)} files only")

    # Idempotency check
    if not args.force and LABELS_CSV.is_file():
        graph_count = sum(1 for _ in GRAPHS_DIR.glob("*.json")) if GRAPHS_DIR.is_dir() else 0
        if graph_count >= EXPECTED_MIN_GRAPHS:
            print(f"Already ingested: {graph_count} graphs at {GRAPHS_DIR}")
            print(f"  labels.csv: {LABELS_CSV}")
            print("  (use --force to re-ingest)")
            return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Imports here so a missing torch/torch-geometric only fails at runtime when needed.
    try:
        from src.sentinel_z.ingestion.auto_pipeline import (
            AutoPipeline,
            DARPA_ATTACK_PERIODS,
        )
    except ImportError as exc:
        print(f"ERROR: cannot import AutoPipeline: {exc}", file=sys.stderr)
        print("Run: pip install -e \".[ml]\"", file=sys.stderr)
        return 1

    pipeline = AutoPipeline(output_dir=str(OUT_DIR))

    print(f"ingesting {len(raw_files)} file(s) from {RAW_DIR}")
    print(f"  output: {OUT_DIR}")
    total_events = 0
    total_subjects = 0
    for i, fp in enumerate(raw_files, 1):
        print(f"\n[{i}/{len(raw_files)}] {fp.name}")
        try:
            counts = pipeline.ingest(str(fp))
        except Exception as exc:
            print(f"  ERROR ingesting {fp.name}: {exc}", file=sys.stderr)
            print("  (continuing with remaining files)", file=sys.stderr)
            continue
        total_events += counts.get("events", 0)
        total_subjects += counts.get("subjects", 0)

    print(f"\nparsing complete: {total_events:,} events, {total_subjects:,} subjects")
    print("building 1-second graph windows + labels...")

    attack_periods = DARPA_ATTACK_PERIODS.get("e5", {}).get("fivedirections", [])
    if not attack_periods:
        print("WARNING: no E5/fivedirections attack periods configured — labels will all be 0",
              file=sys.stderr)
    else:
        print(f"  using {len(attack_periods)} attack period(s) from DARPA_ATTACK_PERIODS")

    try:
        out_path = pipeline.build_dataset(attack_periods=attack_periods, window_seconds=1)
    except Exception as exc:
        print(f"ERROR building dataset: {exc}", file=sys.stderr)
        return 1

    n_graphs = sum(1 for _ in GRAPHS_DIR.glob("*.json")) if GRAPHS_DIR.is_dir() else 0
    print(f"\n[OK] {n_graphs} graphs at {out_path}")
    print(f"     labels: {LABELS_CSV}")
    print("next step: python scripts/verify_phase4.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
