"""
Ingest DARPA TC Engagement-3 (CADETS) .bin.gz chunks into 1-second graph
windows, mirroring scripts/ingest_e5.py but adapted to:

  - The CDM v18 schema (E3) vs v20 (E5)
  - The CADETS attack ground-truth periods from DARPA TC TA5.1 documentation
  - Different file naming and directory layout

The pipeline is otherwise IDENTICAL to E5 ingestion. This is deliberate: the
cross-engagement evaluation in scripts/cross_engagement_eval.py compares
models trained on one engagement against held-out test data from another,
and any pipeline asymmetry would invalidate the comparison.

Usage:
    python scripts/ingest_e3.py                       # full E3-CADETS run
    python scripts/ingest_e3.py --max-files 2 --force # 2-file smoke test
    python scripts/ingest_e3.py --team theia          # E3-THEIA instead

Raw data:
    Place E3 .bin.gz chunks under data/raw/e3/<team>/ where <team> is one of
    'cadets', 'theia', 'trace', 'fivedirections'.

    Download instructions: see data/raw/e3/README.md
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _parse_file_worker(args: tuple) -> dict:
    """Parse one E3 .bin.gz file (top-level so ProcessPoolExecutor can pickle)."""
    fp_str, team_name = args
    import sys as _sys
    import pathlib as _pl
    _repo = _pl.Path(__file__).resolve().parent.parent
    if str(_repo) not in _sys.path:
        _sys.path.insert(0, str(_repo))

    from src.sentinel_z.ingestion.auto_pipeline import AutoPipeline

    p = AutoPipeline(output_dir=str(_repo / "data" / "auto_processed_e3"),
                     save_intermediate=True)
    try:
        counts = p.ingest(fp_str)
    except Exception as exc:
        return {"file": fp_str, "error": str(exc), "counts": None,
                "events": None, "subjects": None,
                "schema_version": None}

    return {
        "file": fp_str,
        "error": None,
        "counts": counts,
        "events": p.all_events[0] if p.all_events else None,
        "subjects": p.all_subjects[0] if p.all_subjects else None,
        "schema_version": p.parser.detected_schema_version,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--team", choices=["cadets", "theia", "trace", "fivedirections"],
                        default="cadets", help="E3 TA1 team (default: cadets)")
    parser.add_argument("--max-files", type=int, default=None,
                        help="Parse at most N .bin.gz files (smoke testing)")
    parser.add_argument("--force", action="store_true",
                        help="Re-ingest even if outputs already present")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2),
                        help="Parallel workers for graph-build stage")
    parser.add_argument("--parse-workers", type=int, default=4,
                        help="Parallel workers for parse stage (cap memory; default 4)")
    args = parser.parse_args()

    raw_dir = REPO_ROOT / "data" / "raw" / "e3" / args.team
    out_dir = REPO_ROOT / "data" / "auto_processed_e3" / args.team
    graphs_dir = out_dir / "graphs"
    labels_csv = out_dir / "labels.csv"
    model_ready_dir = REPO_ROOT / "data" / "model_ready_e3" / args.team
    model_ready_graphs = model_ready_dir / "graphs"
    model_ready_labels = model_ready_dir / "labels.csv"

    if not raw_dir.is_dir():
        print(f"ERROR: raw data dir not found: {raw_dir}", file=sys.stderr)
        print(f"  Download DARPA TC E3-{args.team.upper()} from:", file=sys.stderr)
        print(f"  https://github.com/darpa-i2o/Transparent-Computing#engagement-3", file=sys.stderr)
        print(f"  Place .bin.gz chunks under {raw_dir}", file=sys.stderr)
        return 1

    raw_files = sorted(raw_dir.glob("*.bin*.gz")) + sorted(raw_dir.glob("*.json.gz"))
    if not raw_files:
        print(f"ERROR: no .bin.gz or .json.gz files in {raw_dir}", file=sys.stderr)
        return 1

    if args.max_files:
        raw_files = raw_files[:args.max_files]
        print(f"--max-files {args.max_files}: parsing first {len(raw_files)} files")

    if not args.force and labels_csv.is_file():
        graph_count = sum(1 for _ in graphs_dir.glob("*.json")) if graphs_dir.is_dir() else 0
        if graph_count >= 1000:
            print(f"Already ingested: {graph_count} graphs at {graphs_dir}")
            print("  (use --force to re-ingest)")
            return 0

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from src.sentinel_z.ingestion.auto_pipeline import AutoPipeline, DARPA_ATTACK_PERIODS
    except ImportError as exc:
        print(f"ERROR: cannot import AutoPipeline: {exc}", file=sys.stderr)
        print("Install: pip install -e \".[ml]\"", file=sys.stderr)
        return 1

    # ---- Phase 1: parallel parse ----
    from concurrent.futures import ProcessPoolExecutor, as_completed

    pipeline = AutoPipeline(output_dir=str(out_dir), save_intermediate=True)
    parse_workers = min(len(raw_files), args.parse_workers)
    print(f"Parsing {len(raw_files)} file(s) from {raw_dir}", flush=True)
    print(f"  team:    e3/{args.team}", flush=True)
    print(f"  output:  {out_dir}", flush=True)
    print(f"  parse workers: {parse_workers}", flush=True)

    total_events = 0
    total_subjects = 0
    schema_versions_seen = set()
    done = 0
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=parse_workers) as ex:
        worker_args = [(str(fp), args.team) for fp in raw_files]
        futures = {ex.submit(_parse_file_worker, wa): wa[0] for wa in worker_args}
        for fut in as_completed(futures):
            fp = futures[fut]
            done += 1
            try:
                result = fut.result()
            except Exception as exc:
                print(f"  [{done}/{len(raw_files)}] {Path(fp).name} CRASHED: {exc}",
                      file=sys.stderr, flush=True)
                continue
            if result.get("error"):
                print(f"  [{done}/{len(raw_files)}] {Path(fp).name} ERROR: {result['error']}",
                      file=sys.stderr, flush=True)
                continue

            counts = result["counts"] or {}
            ev = counts.get("events", 0)
            sj = counts.get("subjects", 0)
            total_events += ev
            total_subjects += sj
            if result["events"] is not None:
                pipeline.all_events.append(result["events"])
            if result["subjects"] is not None:
                pipeline.all_subjects.append(result["subjects"])
            if result.get("schema_version"):
                schema_versions_seen.add(result["schema_version"])

            elapsed = time.time() - t0
            pct = done / len(raw_files) * 100
            eta = (elapsed / done) * (len(raw_files) - done) if done > 0 else 0
            print(f"  [{done}/{len(raw_files)}] ({pct:.0f}%) {Path(fp).name}: "
                  f"{ev:,} events, {sj:,} subjects | elapsed {elapsed:.0f}s, ETA {eta:.0f}s",
                  flush=True)

    # Persist subjects partitions
    if pipeline.all_subjects:
        from src.sentinel_z.ingestion.auto_pipeline import DARPADataset as _DS
        for sj_df, raw_fp in zip(pipeline.all_subjects, raw_files):
            ds = _DS.from_filename(raw_fp)
            subdir = out_dir / ds.team / ds.engagement
            subdir.mkdir(parents=True, exist_ok=True)
            (subdir / f"subjects_{ds.file_num}.csv").write_text(sj_df.to_csv(index=False))

    print(f"\nparse complete: {total_events:,} events, {total_subjects:,} subjects "
          f"in {time.time()-t0:.1f}s", flush=True)
    if schema_versions_seen:
        print(f"  schema(s) detected: {', '.join(sorted(schema_versions_seen))}", flush=True)
        if "cdm20" in schema_versions_seen:
            print("  WARNING: cdm20 (E5) records found in an E3 ingest. Verify dataset.",
                  file=sys.stderr)

    if not pipeline.all_events:
        print("ERROR: no events parsed", file=sys.stderr)
        return 1

    # ---- Phase 2: build graphs (re-uses the E5 worker) ----
    import pandas as pd
    events_df = pd.concat(pipeline.all_events, ignore_index=True)
    events_df["timestamp"] = pd.to_datetime(events_df["timestamp"], format="ISO8601")
    events_df = events_df.dropna(subset=["timestamp"])
    print(f"combined events: {len(events_df):,} rows", flush=True)

    attack_periods = DARPA_ATTACK_PERIODS.get("e3", {}).get(args.team, [])
    if not attack_periods:
        print(f"WARNING: no E3/{args.team} attack periods configured -- all labels will be 0",
              file=sys.stderr)
    else:
        print(f"  using {len(attack_periods)} attack period(s) for e3/{args.team}", flush=True)

    # Reuse the E5 graph-build helper (it's engagement-agnostic)
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from ingest_e5 import _build_dataset_parallel  # noqa: E402

    graphs_dir.mkdir(parents=True, exist_ok=True)
    labels = _build_dataset_parallel(events_df, attack_periods, graphs_dir, args.workers)

    if not labels:
        print("ERROR: no graphs built", file=sys.stderr)
        return 1

    labels_df = pd.DataFrame(labels).sort_values("window_id").reset_index(drop=True)
    labels_df.to_csv(labels_csv, index=False)
    n_attack = int((labels_df["label"] == 1).sum())
    n_benign = int((labels_df["label"] == 0).sum())
    print(f"\n[OK] {len(labels_df)} graphs at {graphs_dir}", flush=True)
    print(f"     labels: {labels_csv}", flush=True)
    print(f"     attack={n_attack}  benign={n_benign}", flush=True)

    # ---- Promote to model_ready_e3/<team>/ ----
    import shutil
    model_ready_dir.mkdir(parents=True, exist_ok=True)
    if model_ready_graphs.exists() or model_ready_graphs.is_symlink():
        if model_ready_graphs.is_symlink() or model_ready_graphs.is_file():
            model_ready_graphs.unlink()
        else:
            shutil.rmtree(model_ready_graphs)
    try:
        model_ready_graphs.symlink_to(graphs_dir.resolve(), target_is_directory=True)
        print(f"  symlinked {model_ready_graphs} -> {graphs_dir}", flush=True)
    except OSError:
        shutil.copytree(graphs_dir, model_ready_graphs)
        print(f"  copied {graphs_dir} -> {model_ready_graphs}", flush=True)
    shutil.copy2(labels_csv, model_ready_labels)
    print(f"  copied {labels_csv} -> {model_ready_labels}", flush=True)

    print("\nnext steps:", flush=True)
    print(f"  python scripts/verify_phase4.py --results-dir data/model_ready_e3/{args.team}/detection", flush=True)
    print(f"  python scripts/cross_engagement_eval.py", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
