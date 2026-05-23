"""Cross-team smoke scoring: run Phase 4 on E5-CADETS graphs, then score
every window with the v2 RF detector (trained on E5-FiveDirections).

This is the cross-team analog of scripts/cross_engagement_eval.py. It does
NOT compute paired-bootstrap CIs because the smoke file (May 7 chunk) has
zero labeled attacks; the meaningful number here is the cross-team flag rate
and score distribution on benign FreeBSD activity.

Usage:
    python scripts/score_cross_team_smoke.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.sentinel_z.detection.semantic_risk_engine import RefinedDetector  # noqa: E402
from src.sentinel_z.pipeline.temporal_features import (  # noqa: E402
    add_temporal_features,
    feature_columns,
)

GRAPHS_DIR = REPO_ROOT / "data" / "model_ready_e5" / "cadets" / "graphs"
LABELS_CSV = REPO_ROOT / "data" / "model_ready_e5" / "cadets" / "labels.csv"
SUBJECTS_DIR = REPO_ROOT / "data" / "auto_processed_e5" / "cadets" / "cadets" / "e5"
OUTPUT_DIR = REPO_ROOT / "data" / "model_ready_e5" / "cadets" / "detection"
MODEL_PATH = REPO_ROOT / "models" / "rf_detector_v2.joblib"


def main() -> int:
    print(f"graphs:   {GRAPHS_DIR}")
    print(f"labels:   {LABELS_CSV}")
    print(f"subjects: {SUBJECTS_DIR}")
    print(f"output:   {OUTPUT_DIR}")
    print()

    # ---- Phase 4: semantic + structural feature extraction ----
    t0 = time.time()
    print("=== Phase 4: extracting features from CADETS graphs ===", flush=True)
    detector = RefinedDetector(
        graphs_dir=str(GRAPHS_DIR),
        labels_csv=str(LABELS_CSV),
        subjects_csv=str(SUBJECTS_DIR),
        phase3_results=None,
    )
    detector.run()
    detector.export_results(str(OUTPUT_DIR))
    print(f"\nPhase 4 done in {time.time()-t0:.1f}s", flush=True)

    # ---- Score with v2 RF ----
    print("\n=== Scoring with v2 RF (trained on E5-FiveDirections) ===", flush=True)
    results_file = OUTPUT_DIR / "phase4_results.json"
    with open(results_file) as f:
        phase4 = json.load(f)
    # Mirror the flattening in scripts/train_detector_v2.py so the v2 model
    # sees identical feature semantics.
    rows = []
    for w in phase4.get("windows", []):
        profile = w.get("behavioral_profile", {}) or {}
        rows.append({
            "window_id":     w["window_id"],
            "label":         w.get("label", 0),
            "fused_score":   w.get("fused_score", 0.0),
            "unknown_ratio": profile.get("_unknown_ratio", 0.0),
            "num_nodes":     profile.get("_num_nodes", 0),
            "num_edges":     profile.get("_num_edges", 0),
            "num_subjects":  profile.get("_num_subjects", 0),
            "density":       profile.get("_density", 0.0),
            "network_ratio": profile.get("_network_ratio", 0.0),
            "structural":    w.get("structural_score", 0.0),
        })
    df = pd.DataFrame(rows).sort_values("window_id").reset_index(drop=True)
    print(f"  {len(df):,} windows; base feature columns flattened")

    df = add_temporal_features(df)
    cols = feature_columns()
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"ERROR: missing feature columns: {missing}", file=sys.stderr)
        return 1

    X = df[cols].fillna(0.0).values

    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"] if isinstance(bundle, dict) and "model" in bundle else bundle
    threshold = (bundle.get("threshold")
                 if isinstance(bundle, dict)
                 else None) or 0.5

    proba = model.predict_proba(X)[:, 1]
    flag = (proba >= threshold).astype(int)

    # ---- Report ----
    print("\n=== CROSS-TEAM RESULT (v2 on E5-CADETS chunk) ===")
    print(f"  windows scored:  {len(df):,}")
    print(f"  labeled attacks: {int((df.get('label', 0) == 1).sum() if 'label' in df.columns else 0)}")
    print(f"  threshold (from training): {threshold:.4f}")
    print(f"  flag rate:       {flag.mean()*100:.2f}%  ({int(flag.sum())} of {len(flag)})")
    print(f"  score mean:      {proba.mean():.4f}")
    print(f"  score p50/p95/p99: {np.percentile(proba, 50):.4f} / {np.percentile(proba, 95):.4f} / {np.percentile(proba, 99):.4f}")
    print(f"  score max:       {proba.max():.4f}")

    # Save scores
    df["v2_score"] = proba
    df["v2_flag"] = flag
    out_csv = OUTPUT_DIR / "v2_cross_team_scores.csv"
    df[["window_id", "v2_score", "v2_flag"] + (["label"] if "label" in df.columns else [])].to_csv(out_csv, index=False)
    print(f"\n  scores written: {out_csv}")

    summary = {
        "team": "cadets",
        "engagement": "e5",
        "model": "rf_detector_v2 (trained on E5-FiveDirections)",
        "threshold": float(threshold),
        "n_windows": int(len(df)),
        "n_labeled_attacks_in_chunk": int((df.get("label", 0) == 1).sum() if "label" in df.columns else 0),
        "flag_rate_pct": float(flag.mean() * 100),
        "n_flagged": int(flag.sum()),
        "score_mean": float(proba.mean()),
        "score_p50": float(np.percentile(proba, 50)),
        "score_p95": float(np.percentile(proba, 95)),
        "score_p99": float(np.percentile(proba, 99)),
        "score_max": float(proba.max()),
        "note": "Smoke chunk covers 2019-05-07; documented attack window is 2019-05-16 14:00-14:30. Zero labeled attacks expected; flag_rate is benign cross-team FPR.",
    }
    out_json = OUTPUT_DIR / "v2_cross_team_summary.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  summary written: {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
