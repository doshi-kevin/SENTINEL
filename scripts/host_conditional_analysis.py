"""
Host-conditional analysis of the trained RF detector.

Cross-host LOHO-CV is degenerate (all known attacks are on host 1), but we can
still ask the more important question: does the trained model produce
GENERALIZABLE predictions, or is it just learning 'host 1 == attack'?

Method:
  1. Load the trained RF model.
  2. Predict on every window in the dataset (already split by host attribution).
  3. Compare score distributions across hosts.
  4. Show top anomalies on host 2 and host 3 (no labeled attacks there) - if the
     model learned generalizable patterns, these should be windows with high
     unknown_ratio / density / etc that look attack-like even though unlabeled.

This tells us whether the 0.989 ROC-AUC reflects real attack semantics or
host-specific signal leakage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from src.sentinel_z.detection.rf_detector import RFDetector


def main() -> int:
    cross_host_path = REPO_ROOT / "data" / "model_ready" / "cross_host_validation.json"
    results_path    = REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json"
    model_path      = REPO_ROOT / "models" / "rf_detector.joblib"

    if not cross_host_path.exists():
        print("Run scripts/cross_host_validation.py first.", file=sys.stderr)
        return 1

    print("Loading trained RF detector ...")
    det = RFDetector.load(model_path)
    threshold = det.threshold
    print(f"  Threshold: {threshold:.4f}")

    print("Loading features + host attribution ...")
    with open(results_path) as f:
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
    df = pd.DataFrame(rows)

    # Add host attribution from cross_host_validation.json
    with open(cross_host_path) as f:
        cross = json.load(f)
    host_counts = cross["host_counts"]
    print(f"  Per-host distribution: {host_counts['n_windows']}")

    # Re-attribute by reusing the same logic - simpler: read it from the json output above
    # But we need per-window host. Build it again from subjects (cached output).
    import glob
    subjects_dir = REPO_ROOT / "data" / "auto_processed" / "fivedirections" / "e5"
    uuid_to_host = {}
    for fp in sorted(glob.glob(str(subjects_dir / "subjects_*.csv"))):
        fname = Path(fp).stem
        host = int(fname.split("_")[1]) // 1000
        if host in (1, 2, 3):
            sub_df = pd.read_csv(fp, usecols=["uuid"])
            for u in sub_df["uuid"].dropna().astype(str):
                uuid_to_host.setdefault(u, host)

    print("\nAttributing windows to hosts ...")
    from collections import Counter
    graphs_dir = REPO_ROOT / "data" / "model_ready" / "graphs"
    window_host = {}
    for wid in df["window_id"]:
        path = graphs_dir / f"window_{wid:04d}.json"
        if not path.exists():
            continue
        with open(path) as f:
            g = json.load(f)
        c = Counter()
        for n in g.get("nodes", []):
            if n.get("node_type") == "subject":
                h = uuid_to_host.get(str(n.get("id", "")))
                if h:
                    c[h] += 1
        if c:
            window_host[wid] = c.most_common(1)[0][0]
    df["host"] = df["window_id"].map(window_host)
    df_attr = df[df["host"].notna()].copy()
    df_attr["host"] = df_attr["host"].astype(int)

    print("Predicting on all attributed windows ...")
    detections = det.predict(df_attr)
    df_attr["score"] = [d.anomaly_score for d in detections]
    df_attr["flagged"] = df_attr["score"] >= threshold

    print("\n" + "=" * 72)
    print("PER-HOST PREDICTION SUMMARY")
    print("=" * 72)
    summary = df_attr.groupby("host").agg(
        n_windows=("window_id", "count"),
        n_attacks=("label", "sum"),
        flag_rate=("flagged", "mean"),
        score_mean=("score", "mean"),
        score_p95=("score", lambda s: np.percentile(s, 95)),
        score_p99=("score", lambda s: np.percentile(s, 99)),
    )
    print(summary.to_string())

    print("\n" + "=" * 72)
    print("INTERPRETATION")
    print("=" * 72)
    h1 = df_attr[df_attr["host"] == 1]
    h2 = df_attr[df_attr["host"] == 2]
    h3 = df_attr[df_attr["host"] == 3]

    if len(h1) > 0 and len(h2) > 0:
        delta_12 = h1["score"].mean() - h2["score"].mean()
        print(f"Host 1 mean score - Host 2 mean score: {delta_12:+.4f}")
    if len(h1) > 0 and len(h3) > 0:
        delta_13 = h1["score"].mean() - h3["score"].mean()
        print(f"Host 1 mean score - Host 3 mean score: {delta_13:+.4f}")

    print("\nHigh-score windows on host 2 (no labeled attacks):")
    top2 = h2.nlargest(5, "score")[["window_id", "score", "unknown_ratio", "num_nodes", "density"]]
    print(top2.to_string(index=False))

    print("\nHigh-score windows on host 3 (no labeled attacks):")
    top3 = h3.nlargest(5, "score")[["window_id", "score", "unknown_ratio", "num_nodes", "density"]]
    print(top3.to_string(index=False))

    print("\nFalse-positive rate by host:")
    fpr_per_host = df_attr.groupby("host").apply(
        lambda d: ((d["flagged"]) & (d["label"] == 0)).sum() / max(1, (d["label"] == 0).sum())
    )
    print(fpr_per_host.to_string())

    out = REPO_ROOT / "data" / "model_ready" / "host_conditional_report.json"
    report = {
        "per_host_summary": summary.to_dict(),
        "interpretation": {
            "host1_minus_host2_mean_score": float(h1["score"].mean() - h2["score"].mean())
                if (len(h1) > 0 and len(h2) > 0) else None,
            "host1_minus_host3_mean_score": float(h1["score"].mean() - h3["score"].mean())
                if (len(h1) > 0 and len(h3) > 0) else None,
            "fpr_by_host": fpr_per_host.to_dict(),
        },
        "top_host2_anomalies": top2.to_dict(orient="records"),
        "top_host3_anomalies": top3.to_dict(orient="records"),
    }
    with open(out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
