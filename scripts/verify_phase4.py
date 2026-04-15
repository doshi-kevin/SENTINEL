"""
Smoke check: verify the Phase 4 pipeline runs end-to-end on the ingested data.

Per spec amendment 2026-04-15 (option III): we relax the original ROC-AUC
reproduction gate because the configured E5 attack periods in
``DARPA_ATTACK_PERIODS`` cover only a 2-minute window — far less than the
85-attack-window dataset used to produce the published 0.86 ROC-AUC. Until
the full E5 ground truth is extracted from
``data/raw/e5/Ground_Truth/TA51_Final_report_E5.pdf`` and patched into
``DARPA_ATTACK_PERIODS``, ROC-AUC reproduction is a follow-up task, not a
gate for this sub-project.

What this script DOES verify:

  A. data/auto_processed/graphs/ has >= 5,000 JSONs (lower than 6,051 to
     accommodate the incomplete-labels reality)
  B. data/auto_processed/labels.csv parses; 'window_id' and 'label' columns exist
  C. src.sentinel_z.detection.semantic_risk_engine.run_phase4_pipeline imports
  D. run_phase4_pipeline() executes without raising
  E. data/auto_processed/detection/phase4_results.json (or wherever the engine
     writes) is created

Exit 0 = pipeline runs end-to-end on the dataset on disk.
Exit 1 = blocking failure; print which assertion failed.

Once the full ground truth is patched, add the ROC-AUC range assertion back
(roughly: 0.84 <= roc_auc <= 0.88).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAPHS_DIR = REPO_ROOT / "data" / "auto_processed" / "graphs"
LABELS_CSV = REPO_ROOT / "data" / "auto_processed" / "labels.csv"
RESULTS_DIR = REPO_ROOT / "data" / "auto_processed" / "detection"

MIN_GRAPHS = 5_000


def fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def ok(msg: str) -> None:
    print(f"PASS: {msg}")


def main() -> int:
    # A
    if not GRAPHS_DIR.is_dir():
        return fail(f"graphs dir missing: {GRAPHS_DIR}")
    n = sum(1 for _ in GRAPHS_DIR.glob("*.json"))
    if n < MIN_GRAPHS:
        return fail(f"only {n} graph JSONs in {GRAPHS_DIR} (need >= {MIN_GRAPHS})")
    ok(f"A. {n} graph JSONs")

    # B
    if not LABELS_CSV.is_file():
        return fail(f"labels.csv missing: {LABELS_CSV}")
    try:
        import pandas as pd
        labels_df = pd.read_csv(LABELS_CSV)
    except Exception as exc:
        return fail(f"labels.csv unreadable: {exc}")
    if "window_id" not in labels_df.columns or "label" not in labels_df.columns:
        return fail(f"labels.csv missing required columns; has {list(labels_df.columns)}")
    n_attack = int((labels_df["label"] == 1).sum())
    n_benign = int((labels_df["label"] == 0).sum())
    ok(f"B. labels.csv {len(labels_df)} rows ({n_attack} attack, {n_benign} benign)")
    if n_attack == 0:
        print("   NOTE: 0 attack rows — DARPA_ATTACK_PERIODS likely incomplete; ", file=sys.stderr)
        print("   ROC-AUC reproduction gate deferred (option III). See spec.", file=sys.stderr)

    # C
    try:
        from src.sentinel_z.detection.semantic_risk_engine import run_phase4_pipeline
    except Exception as exc:
        return fail(f"cannot import run_phase4_pipeline: {exc}")
    ok("C. run_phase4_pipeline imports")

    # D
    try:
        run_phase4_pipeline()
    except Exception as exc:
        return fail(f"run_phase4_pipeline raised: {exc}")
    ok("D. run_phase4_pipeline executed")

    # E
    if not RESULTS_DIR.is_dir():
        return fail(f"detection results dir missing: {RESULTS_DIR}")
    json_files = list(RESULTS_DIR.glob("*.json"))
    if not json_files:
        return fail(f"no JSON in {RESULTS_DIR}")
    ok(f"E. {len(json_files)} result JSON(s) in {RESULTS_DIR}")

    # Bonus — surface the actual ROC-AUC if present (informational only)
    for jp in json_files:
        try:
            data = json.loads(jp.read_text())
        except Exception:
            continue
        if isinstance(data, dict):
            for key in ("roc_auc", "metrics"):
                if key in data:
                    print(f"   {jp.name}: {key} = {data[key]}")

    print()
    print("verify_phase4: all gates passed (option III: ROC-AUC reproduction deferred)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
