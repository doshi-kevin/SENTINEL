"""
Ingest DARPA TC E5 FiveDirections .bin.gz chunks at ``data/raw/e5/Data/fivedirections/``
into 1-second graph windows + labels.csv at ``data/auto_processed/``, then
promote into ``data/model_ready/`` for ``run_phase4_pipeline()``.

Two phases:

  1. **Parse (sequential).** Each raw .bin.gz goes through ``AutoPipeline.ingest``
     which invokes the single-threaded ``CDMParser`` (fast at ~95K records/sec
     but not trivially parallel due to fastavro + in-memory accumulator).

  2. **Build dataset (parallel).** After parsing, events are windowed at
     1s granularity by ``WindowGenerator``. Each window's graph-construction
     + feature-engineering + JSON export runs in a worker process, spread
     across ``os.cpu_count() - 2`` cores to leave CPU headroom for the OS.

Rationale for writing a replacement instead of calling ``AutoPipeline.build_dataset``:
that method has four API mismatches with the actual ``src/sentinel_z/pipeline/``
modules (``.build`` vs ``.build_graph``, ``.add_features`` vs ``.compute_node_features``,
etc.), indicating it was never successfully executed end-to-end. Rather than
risk silent breakage by patching it, we call the pipeline modules directly
with the correct API from this script.

Usage::

    python scripts/ingest_e5.py
    python scripts/ingest_e5.py --max-files 5     # smoke subset of parsed files
    python scripts/ingest_e5.py --force           # re-ingest even if outputs present
    python scripts/ingest_e5.py --workers 8       # cap parallel workers
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RAW_DIR = REPO_ROOT / "data" / "raw" / "e5" / "Data" / "fivedirections"
OUT_DIR = REPO_ROOT / "data" / "auto_processed"
GRAPHS_DIR = OUT_DIR / "graphs"
LABELS_CSV = OUT_DIR / "labels.csv"

MODEL_READY_DIR = REPO_ROOT / "data" / "model_ready"
MODEL_READY_GRAPHS = MODEL_READY_DIR / "graphs"
MODEL_READY_LABELS = MODEL_READY_DIR / "labels.csv"

EXPECTED_MIN_GRAPHS_SMOKE = 50


def promote_to_model_ready() -> None:
    """Bridge auto_processed/ → model_ready/ so run_phase4_pipeline() sees the data."""
    import shutil

    if not LABELS_CSV.is_file() or not GRAPHS_DIR.is_dir():
        return

    MODEL_READY_DIR.mkdir(parents=True, exist_ok=True)

    if MODEL_READY_GRAPHS.exists() or MODEL_READY_GRAPHS.is_symlink():
        if MODEL_READY_GRAPHS.is_symlink() or MODEL_READY_GRAPHS.is_file():
            MODEL_READY_GRAPHS.unlink()
        else:
            shutil.rmtree(MODEL_READY_GRAPHS)

    try:
        MODEL_READY_GRAPHS.symlink_to(GRAPHS_DIR.resolve(), target_is_directory=True)
        print(f"  symlinked {MODEL_READY_GRAPHS} -> {GRAPHS_DIR}", flush=True)
    except OSError:
        shutil.copytree(GRAPHS_DIR, MODEL_READY_GRAPHS)
        print(f"  copied   {GRAPHS_DIR} -> {MODEL_READY_GRAPHS}", flush=True)

    shutil.copy2(LABELS_CSV, MODEL_READY_LABELS)
    print(f"  copied   {LABELS_CSV} -> {MODEL_READY_LABELS}", flush=True)


# Top-level worker for parallel FILE parsing (must be picklable).
def _parse_file_worker(fp_str: str) -> dict:
    """Parse one .bin.gz file in a worker process.

    Returns a dict the main process can assemble into pipeline.all_events.
    Intermediate subjects CSV is written to disk by AutoPipeline itself.
    """
    import sys as _sys
    import pathlib as _pl
    _repo = _pl.Path(__file__).resolve().parent.parent
    if str(_repo) not in _sys.path:
        _sys.path.insert(0, str(_repo))

    from src.sentinel_z.ingestion.auto_pipeline import AutoPipeline

    p = AutoPipeline(output_dir=str(_repo / "data" / "auto_processed"),
                     save_intermediate=False)
    try:
        counts = p.ingest(fp_str)
    except Exception as exc:
        return {"file": fp_str, "error": str(exc), "counts": None,
                "events": None, "subjects": None}

    events = p.all_events[0] if p.all_events else None
    subjects = p.all_subjects[0] if p.all_subjects else None
    return {"file": fp_str, "error": None, "counts": counts,
            "events": events, "subjects": subjects}


# Worker function MUST be top-level (picklable for ProcessPoolExecutor).
def _build_window_worker(args):
    """Build graph + features + save for a single 1-second window.

    Returns a label dict or None when the window should be skipped.
    """
    import sys as _sys
    import pathlib as _pl
    _repo = _pl.Path(__file__).resolve().parent.parent
    if str(_repo) not in _sys.path:
        _sys.path.insert(0, str(_repo))

    import pandas as _pd
    from src.sentinel_z.pipeline.graph_constructor import GraphConstructor
    from src.sentinel_z.pipeline.feature_engineer import FeatureEngineer
    from src.sentinel_z.pipeline.graph_exporter import GraphExporter

    wid, window_events_records, start_iso, end_iso, attack_periods, graphs_dir = args

    if not window_events_records:
        return None

    window_events = _pd.DataFrame(window_events_records)
    window_events["timestamp"] = _pd.to_datetime(window_events["timestamp"], format="ISO8601")
    start = _pd.Timestamp(start_iso)
    end = _pd.Timestamp(end_iso)

    try:
        G = GraphConstructor().build_graph(window_events)
    except Exception:
        return None
    if len(G.nodes) == 0:
        return None

    try:
        FeatureEngineer().compute_node_features(G)
    except Exception:
        # features are nice-to-have; continue without them
        pass

    label = 0
    for attack_start, attack_end in attack_periods:
        a_start = _pd.Timestamp(attack_start)
        a_end = _pd.Timestamp(attack_end)
        if start <= a_end and end >= a_start:
            label = 1
            break

    GraphExporter(str(graphs_dir)).save(G, wid)

    return {
        "window_id": wid,
        "start": start_iso,
        "end": end_iso,
        "label": label,
        "num_nodes": len(G.nodes),
        "num_edges": len(G.edges),
        "event_count": len(window_events),
    }


def _build_dataset_parallel(events_df, attack_periods, graphs_dir: Path, workers: int) -> list[dict]:
    """Parallel replacement for AutoPipeline.build_dataset().

    Uses WindowGenerator to compute 1-second window ranges, then fans each
    window's build_graph / compute_node_features / save into a worker pool.
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from src.sentinel_z.pipeline.window_generator import WindowGenerator

    graphs_dir.mkdir(parents=True, exist_ok=True)

    print("Generating 1-second windows ...", flush=True)
    window_gen = WindowGenerator(window_seconds=1)
    windows_ranges = window_gen.generate_windows(events_df)
    print(f"  {len(windows_ranges)} candidate windows", flush=True)

    # Pre-index events by second-bucket so workers get only their slice
    import pandas as pd
    events_df = events_df.sort_values("timestamp").reset_index(drop=True)
    events_df["_sec"] = events_df["timestamp"].dt.floor("1s")
    bucketed = {ts: rows for ts, rows in events_df.groupby("_sec", sort=False)}

    def _gen_tasks():
        for wid, (start, end) in enumerate(windows_ranges):
            bucket = bucketed.get(start)
            if bucket is None or len(bucket) == 0:
                continue
            # Drop the helper column; keep minimal columns for pickling
            records = bucket.drop(columns=["_sec"]).to_dict(orient="records")
            # timestamps need ISO strings to survive pickling in workers cleanly
            for r in records:
                if hasattr(r.get("timestamp"), "isoformat"):
                    r["timestamp"] = r["timestamp"].isoformat()
            yield (
                wid,
                records,
                start.isoformat(),
                end.isoformat(),
                attack_periods,
                graphs_dir,
            )

    labels: list[dict] = []
    n_tasks = 0
    print(f"building graphs with {workers} workers ...", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for result in ex.map(_build_window_worker, _gen_tasks(), chunksize=16):
            n_tasks += 1
            if result is not None:
                labels.append(result)
            if n_tasks % 200 == 0:
                print(f"  processed {n_tasks} windows, {len(labels)} graphs saved", flush=True)

    print(f"  processed {n_tasks} windows, {len(labels)} graphs saved", flush=True)
    return labels


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-files", type=int, default=None,
                        help="parse at most N .bin.gz files (smoke testing)")
    parser.add_argument("--force", action="store_true",
                        help="re-ingest even if outputs already present")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2),
                        help="parallel workers for build-dataset stage")
    args = parser.parse_args()

    if not RAW_DIR.is_dir():
        print(f"ERROR: raw data dir not found: {RAW_DIR}", file=sys.stderr)
        print("Run: python scripts/download_e5.py", file=sys.stderr)
        return 1

    raw_files = sorted(RAW_DIR.glob("*.bin*.gz"))
    # Exclude unsplit per-host bundles (e.g. ta1-fivedirections-1-e5-official-1.bin.gz)
    import re
    _unsplit = re.compile(r"^ta1-fivedirections-\d+-e5-official-\d+\.bin\.gz$")
    raw_files = [p for p in raw_files if not _unsplit.match(p.name)]

    if not raw_files:
        print(f"ERROR: no .bin.N.gz chunks in {RAW_DIR}", file=sys.stderr)
        return 1

    if args.max_files:
        raw_files = raw_files[: args.max_files]
        print(f"--max-files {args.max_files}: parsing first {len(raw_files)} chunks")

    if not args.force and LABELS_CSV.is_file():
        graph_count = sum(1 for _ in GRAPHS_DIR.glob("*.json")) if GRAPHS_DIR.is_dir() else 0
        if graph_count >= EXPECTED_MIN_GRAPHS_SMOKE:
            print(f"Already ingested: {graph_count} graphs at {GRAPHS_DIR}")
            print("  (use --force to re-ingest)")
            promote_to_model_ready()
            return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from src.sentinel_z.ingestion.auto_pipeline import (
            AutoPipeline,
            DARPA_ATTACK_PERIODS,
        )
    except ImportError as exc:
        print(f"ERROR: cannot import AutoPipeline: {exc}", file=sys.stderr)
        print("Run: pip install -e \".[ml]\" or install pandas/numpy/networkx/fastavro", file=sys.stderr)
        return 1

    # ------- Phase 1: parallel parse -------
    import time as _time
    from concurrent.futures import ProcessPoolExecutor as _PPE, as_completed as _as_completed

    pipeline = AutoPipeline(output_dir=str(OUT_DIR), save_intermediate=True)
    # Each parse worker holds ~1 GB of parsed events in RAM, so cap at 4 to
    # stay under ~4 GB peak. The previous 15-worker run OOM-crashed silently.
    parse_workers = min(len(raw_files), 4)
    print(f"Parsing {len(raw_files)} chunk(s) from {RAW_DIR}", flush=True)
    print(f"  output: {OUT_DIR}", flush=True)
    print(f"  using {parse_workers} parallel parse workers", flush=True)

    total_events = 0
    total_subjects = 0
    done = 0
    t0 = _time.time()
    with _PPE(max_workers=parse_workers) as _ex:
        _futs = {_ex.submit(_parse_file_worker, str(fp)): fp for fp in raw_files}
        for _fut in _as_completed(_futs):
            fp = _futs[_fut]
            done += 1
            try:
                result = _fut.result()
            except Exception as exc:
                print(f"  [{done}/{len(raw_files)}] {fp.name} CRASHED: {exc}",
                      file=sys.stderr, flush=True)
                continue
            if result.get("error"):
                print(f"  [{done}/{len(raw_files)}] {fp.name} ERROR: {result['error']}",
                      file=sys.stderr, flush=True)
                continue

            counts = result["counts"] or {}
            ev, sj = counts.get("events", 0), counts.get("subjects", 0)
            total_events += ev
            total_subjects += sj
            if result["events"] is not None:
                pipeline.all_events.append(result["events"])
            if result["subjects"] is not None:
                pipeline.all_subjects.append(result["subjects"])

            elapsed = _time.time() - t0
            pct = done / len(raw_files) * 100
            eta = (elapsed / done) * (len(raw_files) - done) if done > 0 else 0
            print(f"  [{done}/{len(raw_files)}] ({pct:.0f}%) {fp.name}: "
                  f"{ev:,} events, {sj:,} subjects | elapsed {elapsed:.0f}s, ETA {eta:.0f}s",
                  flush=True)

    # Save the parallel-parsed subjects to the same layout the semantic engine expects.
    if pipeline.all_subjects:
        from src.sentinel_z.ingestion.auto_pipeline import DARPADataset as _DS
        for sj_df, raw_fp in zip(pipeline.all_subjects, raw_files):
            ds = _DS.from_filename(raw_fp)
            subdir = OUT_DIR / ds.team / ds.engagement
            subdir.mkdir(parents=True, exist_ok=True)
            (subdir / f"subjects_{ds.file_num}.csv").write_text(sj_df.to_csv(index=False))

    print(f"\nparse complete: {total_events:,} events, {total_subjects:,} subjects "
          f"in {_time.time()-t0:.1f}s", flush=True)

    if not pipeline.all_events:
        print("ERROR: no events parsed from any file", file=sys.stderr)
        return 1

    # ------- Phase 2: parallel build -------
    import pandas as pd
    events_df = pd.concat(pipeline.all_events, ignore_index=True)
    events_df["timestamp"] = pd.to_datetime(events_df["timestamp"], format="ISO8601")
    events_df = events_df.dropna(subset=["timestamp"])
    print(f"combined events: {len(events_df):,} rows; sorting by timestamp ...", flush=True)

    attack_periods = DARPA_ATTACK_PERIODS.get("e5", {}).get("fivedirections", [])
    if not attack_periods:
        print("WARNING: no E5/fivedirections attack periods configured — labels will all be 0",
              file=sys.stderr)
    else:
        print(f"  using {len(attack_periods)} attack period(s) from DARPA_ATTACK_PERIODS", flush=True)

    labels = _build_dataset_parallel(events_df, attack_periods, GRAPHS_DIR, args.workers)

    if not labels:
        print("ERROR: no graphs built (all windows were empty?)", file=sys.stderr)
        return 1

    labels_df = pd.DataFrame(labels)
    labels_df = labels_df.sort_values("window_id").reset_index(drop=True)
    labels_df.to_csv(LABELS_CSV, index=False)
    print(f"\n[OK] {len(labels_df)} graphs at {GRAPHS_DIR}", flush=True)
    print(f"     labels: {LABELS_CSV}", flush=True)
    n_attack = int((labels_df["label"] == 1).sum())
    n_benign = int((labels_df["label"] == 0).sum())
    print(f"     attack={n_attack}  benign={n_benign}", flush=True)

    promote_to_model_ready()

    print("next step: python scripts/verify_phase4.py", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
