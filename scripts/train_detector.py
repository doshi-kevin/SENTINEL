"""
Train the RF detector on graph features + labels.

Produces models/rf_detector.joblib plus a model_card.json next to it.

Usage:
    python scripts/train_detector.py
    python scripts/train_detector.py --results data/model_ready/detection/phase4_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from src.sentinel_z.detection.rf_detector import RFDetector, FEATURE_COLUMNS


def load_features(results_json: Path) -> pd.DataFrame:
    """Extract feature rows from phase4_results.json's window objects."""
    with open(results_json) as f:
        data = json.load(f)

    rows = []
    for w in data.get("windows", []):
        profile = w.get("behavioral_profile", {}) or {}
        rows.append({
            "window_id":     w["window_id"],
            "label":         w["label"],
            "num_nodes":     profile.get("_num_nodes", 0),
            "num_edges":     profile.get("_num_edges", 0),
            "num_subjects":  profile.get("_num_subjects", 0),
            "density":       profile.get("_density", 0.0),
            "unknown_ratio": profile.get("_unknown_ratio", 0.0),
            "network_ratio": profile.get("_network_ratio", 0.0),
            "structural":    w.get("structural_score", 0.0),
        })
    return pd.DataFrame(rows).sort_values("window_id").reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path,
                    default=REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json")
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "models" / "rf_detector.joblib")
    ap.add_argument("--objective", choices=["f1", "youden"], default="f1",
                    help="threshold objective: f1 or youden (TPR-FPR)")
    args = ap.parse_args()

    if not args.results.exists():
        print(f"ERROR: {args.results} not found. Run scripts/verify_phase4.py first.", file=sys.stderr)
        return 1

    print(f"Loading features from {args.results}")
    df = load_features(args.results)
    print(f"  Total windows: {len(df)}")
    print(f"  Attacks:       {int(df['label'].sum())}")
    print(f"  Benign:        {int((df['label'] == 0).sum())}")
    print(f"  Features:      {FEATURE_COLUMNS}")

    detector = RFDetector(n_estimators=200, max_depth=8, class_weight="balanced")
    card = detector.fit(df, df["label"].values, threshold_objective=args.objective)

    print("\n" + "=" * 72)
    print("TRAINED MODEL CARD")
    print("=" * 72)
    print(f"  Test ROC-AUC:  {card.roc_auc_test:.4f}")
    print(f"  Test Precision:{card.precision_test:.4f}")
    print(f"  Test Recall:   {card.recall_test:.4f}")
    print(f"  Test F1:       {card.f1_test:.4f}")
    print(f"  Test FPR:      {card.fpr_test:.4f}")
    print(f"  Threshold:     {card.threshold:.4f}")
    print(f"  Split:         {card.n_train}/{card.n_val}/{card.n_test}")
    print(f"  Test attacks:  {card.n_attacks_test}")
    print(f"  Trained on:    {card.trained_on}")
    print()
    print("Feature importances:")
    for feat, imp in sorted(card.feature_importances.items(), key=lambda x: -x[1]):
        print(f"    {feat:<18} {imp:.4f}")
    print()
    print("Known limitations:")
    for lim in card.limitations:
        print(f"  - {lim}")
    print("=" * 72)

    detector.save(args.out)
    print(f"\nSaved model to {args.out}")
    print(f"Model card:    {args.out.parent / 'model_card.json'}")
    print(f"Checksum:      {args.out}.sha256")
    return 0


if __name__ == "__main__":
    sys.exit(main())
