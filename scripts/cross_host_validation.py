"""
Leave-One-Host-Out Cross-Validation for Sentinel-Z.

The closest test of cross-system generalization possible with the data on disk:
DARPA TC E5 FiveDirections has 3 distinct host machines (host 1, 2, 3) running
simultaneously. We:

  1. Build a UUID -> host map from the per-host subjects_*.csv partitions.
  2. Attribute each 1-second graph window to its DOMINANT host (the host that
     contributed the most subject nodes in that window).
  3. Run 3-fold cross-validation rotating which host is held out:
       Fold 1: train on hosts {2,3}, test on host 1
       Fold 2: train on hosts {1,3}, test on host 2
       Fold 3: train on hosts {1,2}, test on host 3
  4. Report per-fold ROC-AUC + held-out recall to measure cross-host robustness.

This is NOT full cross-dataset (different DARPA engagement), but it IS a real
out-of-distribution test: each host has different baseline activity, different
process trees, different network behavior. If a model trained on hosts {1,2}
ranks attacks correctly on host 3 it never saw, the zero-shot architecture
claim has real evidence.

Usage:
    python scripts/cross_host_validation.py
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, confusion_matrix


def build_uuid_to_host(subjects_dir: Path) -> dict:
    """uuid -> host_id (1, 2, or 3) from subjects_NNNN.csv partitions.

    file_num NNNN is encoded host*1000 + chunk by AutoPipeline.
    """
    mapping = {}
    files = sorted(glob.glob(str(subjects_dir / "subjects_*.csv")))
    if not files:
        raise FileNotFoundError(f"No subjects_*.csv under {subjects_dir}")
    for fp in files:
        fname = Path(fp).stem
        try:
            file_num = int(fname.split("_")[1])
        except (IndexError, ValueError):
            continue
        host = file_num // 1000
        if host not in (1, 2, 3):
            continue
        df = pd.read_csv(fp, usecols=["uuid"])
        for u in df["uuid"].dropna().astype(str):
            mapping.setdefault(u, host)
    print(f"  Loaded {len(mapping):,} UUID->host mappings from {len(files)} partitions")
    return mapping


def attribute_windows_to_hosts(graphs_dir: Path, uuid_to_host: dict) -> dict:
    """For each window_NNNN.json, return the dominant host based on subject nodes."""
    window_to_host = {}
    files = sorted(glob.glob(str(graphs_dir / "window_*.json")))
    n = len(files)
    print(f"  Attributing {n:,} windows ...")
    t0 = time.time()
    for i, fp in enumerate(files):
        wid = int(Path(fp).stem.split("_")[1])
        with open(fp) as f:
            g = json.load(f)
        counts = Counter()
        for node in g.get("nodes", []):
            if node.get("node_type") == "subject":
                h = uuid_to_host.get(str(node.get("id", "")))
                if h:
                    counts[h] += 1
        if counts:
            window_to_host[wid] = counts.most_common(1)[0][0]
        if (i + 1) % 10000 == 0:
            elapsed = time.time() - t0
            eta = (elapsed / (i + 1)) * (n - i - 1)
            print(f"    {i+1:,}/{n:,} ({100*(i+1)/n:.0f}%) - elapsed {elapsed:.0f}s, ETA {eta:.0f}s")
    print(f"  Attributed {len(window_to_host):,}/{n:,} windows in {time.time()-t0:.0f}s")
    return window_to_host


def load_features(results_path: Path) -> pd.DataFrame:
    """Same flat feature DataFrame used by train_detector.py."""
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
    return pd.DataFrame(rows).sort_values("window_id").reset_index(drop=True)


FEATURES = ["num_nodes", "num_edges", "num_subjects", "density",
            "unknown_ratio", "network_ratio", "structural"]


def evaluate_fold(train_df: pd.DataFrame, test_df: pd.DataFrame,
                  test_host: int) -> dict:
    """Train RF on train_df, evaluate on test_df."""
    if train_df["label"].sum() == 0:
        return {"test_host": test_host, "roc_auc": float("nan"),
                "n_train": len(train_df), "n_test": len(test_df),
                "n_train_attacks": 0,
                "n_test_attacks": int(test_df["label"].sum()),
                "note": "no attacks in training fold - skip"}

    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, class_weight="balanced",
        random_state=42, n_jobs=-1,
    )
    rf.fit(train_df[FEATURES].values, train_df["label"].values)
    test_scores = rf.predict_proba(test_df[FEATURES].values)[:, 1]

    n_test_attacks = int(test_df["label"].sum())
    if n_test_attacks == 0:
        return {"test_host": test_host, "roc_auc": float("nan"),
                "n_train": len(train_df), "n_test": len(test_df),
                "n_train_attacks": int(train_df["label"].sum()),
                "n_test_attacks": 0,
                "note": "no attacks in test fold - cannot measure recall"}

    try:
        roc_auc = float(roc_auc_score(test_df["label"].values, test_scores))
    except ValueError:
        roc_auc = float("nan")

    # At various thresholds, what fraction of test attacks do we catch?
    threshold_perf = []
    for t in [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]:
        preds = (test_scores >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(
            test_df["label"].values, preds, labels=[0, 1]
        ).ravel()
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        threshold_perf.append({
            "threshold": t, "tp": int(tp), "fp": int(fp), "fn": int(fn),
            "recall": round(recall, 4), "precision": round(precision, 4),
            "fpr": round(fpr, 4),
        })

    return {
        "test_host": test_host,
        "roc_auc": roc_auc,
        "n_train": len(train_df),
        "n_test": len(test_df),
        "n_train_attacks": int(train_df["label"].sum()),
        "n_test_attacks": n_test_attacks,
        "threshold_perf": threshold_perf,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graphs", type=Path,
                    default=REPO_ROOT / "data" / "model_ready" / "graphs")
    ap.add_argument("--subjects", type=Path,
                    default=REPO_ROOT / "data" / "auto_processed" / "fivedirections" / "e5")
    ap.add_argument("--results", type=Path,
                    default=REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json")
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "data" / "model_ready" / "cross_host_validation.json")
    args = ap.parse_args()

    print("=" * 72)
    print("LEAVE-ONE-HOST-OUT CROSS-VALIDATION")
    print("=" * 72)
    print(f"Subjects dir: {args.subjects}")
    print(f"Graphs dir:   {args.graphs}")
    print(f"Features:     {args.results}")

    print("\n[1/4] Building UUID -> host map ...")
    uuid_to_host = build_uuid_to_host(args.subjects)

    print("\n[2/4] Attributing windows to hosts ...")
    window_to_host = attribute_windows_to_hosts(args.graphs, uuid_to_host)

    print("\n[3/4] Loading features ...")
    df = load_features(args.results)
    df["host"] = df["window_id"].map(window_to_host)
    n_attributed = df["host"].notna().sum()
    print(f"  {n_attributed:,}/{len(df):,} windows have host attribution")

    host_counts = df.groupby("host", dropna=True).agg(
        n_windows=("window_id", "count"),
        n_attacks=("label", "sum"),
    )
    print("\n  Per-host distribution:")
    print(host_counts.to_string())

    df_attr = df[df["host"].notna()].copy()
    df_attr["host"] = df_attr["host"].astype(int)

    print("\n[4/4] Running 3-fold leave-one-host-out CV ...")
    fold_results = []
    for held_out in [1, 2, 3]:
        train_df = df_attr[df_attr["host"] != held_out]
        test_df  = df_attr[df_attr["host"] == held_out]
        print(f"\n  Fold: held out host {held_out}")
        print(f"    Train: {len(train_df):,} windows, {int(train_df['label'].sum())} attacks")
        print(f"    Test:  {len(test_df):,} windows, {int(test_df['label'].sum())} attacks")
        res = evaluate_fold(train_df, test_df, held_out)
        fold_results.append(res)
        if "roc_auc" in res and not np.isnan(res["roc_auc"]):
            print(f"    Test ROC-AUC: {res['roc_auc']:.4f}")
            print(f"    Threshold sweep:")
            for t in res["threshold_perf"]:
                print(f"      t={t['threshold']:.2f}  R={t['recall']:.3f}  P={t['precision']:.4f}  FPR={t['fpr']:.4f}")
        else:
            print(f"    NOTE: {res.get('note', 'unknown')}")

    valid_aucs = [r["roc_auc"] for r in fold_results if not np.isnan(r.get("roc_auc", float("nan")))]
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    if valid_aucs:
        mean_auc = float(np.mean(valid_aucs))
        std_auc = float(np.std(valid_aucs))
        print(f"Cross-host ROC-AUC: {mean_auc:.4f} +/- {std_auc:.4f} (n={len(valid_aucs)} valid folds)")
        within_host_auc = 0.989
        print(f"Within-host ROC-AUC (stratified split, for comparison): {within_host_auc}")
        delta = mean_auc - within_host_auc
        print(f"Cross-host - within-host delta: {delta:+.4f}")
        if abs(delta) < 0.05:
            verdict = "PASS: cross-host generalization within 5 points of within-host"
        elif delta < 0:
            verdict = f"DROP: cross-host loses {abs(delta):.3f} ROC-AUC vs within-host - generalization is limited"
        else:
            verdict = "PASS+: cross-host actually outperforms within-host (likely fewer overfit signals)"
        print(f"VERDICT: {verdict}")
    else:
        print("All folds had no test attacks - cannot evaluate cross-host generalization.")
        print("This means all 86 attacks cluster on a single host, so LOHO-CV is degenerate.")
        verdict = "DEGENERATE: attacks all on one host"

    report = {
        "folds": fold_results,
        "mean_roc_auc": float(np.mean(valid_aucs)) if valid_aucs else None,
        "std_roc_auc": float(np.std(valid_aucs)) if valid_aucs else None,
        "verdict": verdict if valid_aucs else "DEGENERATE: attacks all on one host",
        "host_counts": host_counts.to_dict(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
