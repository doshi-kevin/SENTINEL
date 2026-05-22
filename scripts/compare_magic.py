"""
Paired-bootstrap comparison: Sentinel-Z RF v2 vs MAGIC (USENIX Security '24).

MAGIC is the strongest open-source baseline for provenance-based APT detection
on DARPA TC. Without a direct comparison, any paper submitted to a top venue
will be rejected on methodology grounds. This script implements the comparison
under TWO modes:

  1. SCORE-FILE MODE:  You run MAGIC externally (their Python 3.8 env), export
                       per-window scores to a CSV, and point this script at it.
                       MAGIC's GitHub: https://github.com/FDUDSDE/MAGIC

  2. STUB-MODE:        For development / CI: read scores from a stub file that
                       has the same schema. Useful for plumbing tests when
                       MAGIC isn't installed yet.

The comparison protocol is paired bootstrap with the IDENTICAL train/test split
seeds Sentinel-Z used. This is essential for valid statistical comparison; if
MAGIC and Sentinel-Z see different test sets, the comparison is meaningless.

The expected MAGIC scores file format:

    window_id,magic_score,magic_pred
    0,0.0123,0
    1,0.8731,1
    ...

`magic_score` is a continuous anomaly probability in [0, 1].
`magic_pred` is the binary decision at MAGIC's chosen threshold (optional).

Usage:
    python scripts/compare_magic.py --magic-scores magic_scores_e5.csv
    python scripts/compare_magic.py --stub                # use built-in stub
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from src.sentinel_z.pipeline.temporal_features import (
    add_temporal_features, feature_columns,
)


def load_sentinel_features(results_path: Path) -> pd.DataFrame:
    with open(results_path) as f:
        data = json.load(f)
    rows = []
    for w in data.get("windows", []):
        profile = w.get("behavioral_profile", {}) or {}
        rows.append({
            "window_id": w["window_id"],
            "label": w["label"],
            "fused_score": w["fused_score"],
            "unknown_ratio": profile.get("_unknown_ratio", 0.0),
            "num_nodes": profile.get("_num_nodes", 0),
            "num_edges": profile.get("_num_edges", 0),
            "num_subjects": profile.get("_num_subjects", 0),
            "density": profile.get("_density", 0.0),
            "network_ratio": profile.get("_network_ratio", 0.0),
            "structural": w.get("structural_score", 0.0),
        })
    df = pd.DataFrame(rows)
    return add_temporal_features(df)


def load_magic_scores(magic_csv: Path) -> pd.DataFrame:
    """Load MAGIC scores. Expected columns: window_id, magic_score.

    Optional: magic_pred (we don't trust their threshold; we choose our own).
    """
    df = pd.read_csv(magic_csv)
    if "window_id" not in df.columns or "magic_score" not in df.columns:
        raise ValueError(
            f"{magic_csv} must have columns 'window_id' and 'magic_score'. Got: {df.columns.tolist()}"
        )
    return df[["window_id", "magic_score"]].copy()


def generate_stub_magic_scores(sentinel_df: pd.DataFrame, seed: int = 1) -> pd.DataFrame:
    """Synthesize a 'MAGIC' scores series for plumbing tests only.

    The stub returns a noisy version of unknown_ratio + label leakage to roughly
    mimic what a real graph-NN baseline would produce. THIS IS NOT A REAL
    COMPARISON — it exists only so the script's downstream logic can be tested
    without installing MAGIC's heavy DGL/PyTorch dependency stack.
    """
    rng = np.random.default_rng(seed)
    base = sentinel_df["unknown_ratio"].values
    noise = rng.normal(0, 0.15, size=len(base))
    label_signal = sentinel_df["label"].values * 0.3
    magic_score = np.clip(base + noise + label_signal, 0, 1)
    return pd.DataFrame({
        "window_id": sentinel_df["window_id"].values,
        "magic_score": magic_score,
    })


def fit_rf(X, y, seed=42):
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, class_weight="balanced",
        random_state=seed, n_jobs=-1,
    )
    rf.fit(X, y)
    return rf


def youden_threshold(scores, labels):
    cands = np.unique(scores)
    if len(cands) > 200:
        cands = np.percentile(scores, np.linspace(0, 100, 201))
    best_t, best_j = cands[0], -1.0
    for t in cands:
        preds = (scores >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(labels, preds, labels=[0, 1]).ravel()
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        if (r - fpr) > best_j:
            best_j, best_t = (r - fpr), t
    return float(best_t)


def metrics_at(scores, labels, threshold):
    preds = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, preds, labels=[0, 1]).ravel()
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {"precision": float(p), "recall": float(r), "f1": float(f1), "fpr": float(fpr)}


def paired_bootstrap(df: pd.DataFrame, n_iter: int = 30,
                     test_size: float = 0.30) -> dict:
    """For each seed in [0, n_iter):
       - Build the same train/test split
       - Train Sentinel-Z v2 on the training set
       - Score Sentinel-Z's predict_proba on the test set
       - Take MAGIC's pre-computed scores (already aligned by window_id)
       - Compute metrics for both on the SAME test set
       - Report per-iteration deltas + 95% CI on delta
    """
    full_cols = feature_columns()
    rows = []
    for seed in range(n_iter):
        train_df, test_df = train_test_split(
            df, test_size=test_size, stratify=df["label"], random_state=seed,
        )
        if train_df["label"].sum() == 0 or test_df["label"].sum() == 0:
            continue

        # Sentinel-Z v2 retrained per seed
        rf = fit_rf(train_df[full_cols].values, train_df["label"].values, seed=seed)
        sz_scores = rf.predict_proba(test_df[full_cols].values)[:, 1]

        # MAGIC scores were precomputed once; just align by window_id
        magic_scores = test_df["magic_score"].values

        ty = test_df["label"].values
        try:
            sz_roc = roc_auc_score(ty, sz_scores)
            sz_pr = average_precision_score(ty, sz_scores)
            sz_brier = brier_score_loss(ty, sz_scores)
            mg_roc = roc_auc_score(ty, magic_scores)
            mg_pr = average_precision_score(ty, magic_scores)
            mg_brier = brier_score_loss(ty, magic_scores)
        except ValueError:
            continue

        # Pick thresholds independently for each model
        sz_t = youden_threshold(sz_scores, ty); sz_m = metrics_at(sz_scores, ty, sz_t)
        mg_t = youden_threshold(magic_scores, ty); mg_m = metrics_at(magic_scores, ty, mg_t)

        rows.append({
            "seed": seed,
            "sz_roc": sz_roc, "mg_roc": mg_roc, "delta_roc": sz_roc - mg_roc,
            "sz_pr": sz_pr,   "mg_pr": mg_pr,   "delta_pr":  sz_pr - mg_pr,
            "sz_brier": sz_brier, "mg_brier": mg_brier, "delta_brier": sz_brier - mg_brier,
            "sz_f1": sz_m["f1"],   "mg_f1": mg_m["f1"],
            "sz_recall": sz_m["recall"], "mg_recall": mg_m["recall"],
            "sz_precision": sz_m["precision"], "mg_precision": mg_m["precision"],
            "sz_fpr": sz_m["fpr"], "mg_fpr": mg_m["fpr"],
        })
        if (seed + 1) % 10 == 0:
            print(f"  {seed+1}/{n_iter} splits done")

    rdf = pd.DataFrame(rows)

    def stat(col):
        a = rdf[col].values
        return {
            "mean": float(a.mean()), "std": float(a.std()),
            "ci_low": float(np.percentile(a, 2.5)),
            "ci_high": float(np.percentile(a, 97.5)),
            "p_lt_zero": float((a <= 0).mean()),
        }

    return {
        "n_pairs": len(rdf),
        "sz_roc_auc": stat("sz_roc"), "mg_roc_auc": stat("mg_roc"),
        "delta_roc_auc": stat("delta_roc"),
        "sz_pr_auc": stat("sz_pr"),   "mg_pr_auc": stat("mg_pr"),
        "delta_pr_auc": stat("delta_pr"),
        "sz_f1": stat("sz_f1"),       "mg_f1": stat("mg_f1"),
        "sz_recall": stat("sz_recall"), "mg_recall": stat("mg_recall"),
        "sz_precision": stat("sz_precision"), "mg_precision": stat("mg_precision"),
        "sz_fpr": stat("sz_fpr"),     "mg_fpr": stat("mg_fpr"),
        "sz_brier": stat("sz_brier"), "mg_brier": stat("mg_brier"),
        "delta_brier": stat("delta_brier"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sentinel-results", type=Path,
                   default=REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json")
    p.add_argument("--magic-scores", type=Path, default=None,
                   help="CSV of MAGIC scores (window_id, magic_score). Required unless --stub.")
    p.add_argument("--stub", action="store_true",
                   help="Use synthetic stub MAGIC scores (plumbing test only)")
    p.add_argument("--bootstrap", type=int, default=30)
    p.add_argument("--out", type=Path,
                   default=REPO_ROOT / "data" / "model_ready" / "magic_comparison_report.json")
    args = p.parse_args()

    if not args.stub and not args.magic_scores:
        print("ERROR: provide --magic-scores or use --stub", file=sys.stderr)
        return 2

    print("=" * 72)
    print("SENTINEL-Z vs MAGIC (paired-bootstrap)")
    print("=" * 72)

    sz_df = load_sentinel_features(args.sentinel_results)
    print(f"Sentinel-Z features: {len(sz_df):,} windows, {int(sz_df['label'].sum())} attacks")

    if args.stub:
        print("Mode: STUB (synthetic MAGIC scores - plumbing test only, NOT publishable)")
        mg_df = generate_stub_magic_scores(sz_df)
    else:
        print(f"Mode: REAL MAGIC scores from {args.magic_scores}")
        mg_df = load_magic_scores(args.magic_scores)

    # Align by window_id
    merged = sz_df.merge(mg_df, on="window_id", how="inner")
    if len(merged) < len(sz_df):
        print(f"WARNING: only {len(merged):,} of {len(sz_df):,} Sentinel-Z windows have MAGIC scores",
              file=sys.stderr)
    print(f"Aligned: {len(merged):,} windows for paired comparison")

    print(f"\nRunning {args.bootstrap}-iteration paired bootstrap ...")
    t0 = time.time()
    result = paired_bootstrap(merged, n_iter=args.bootstrap)
    elapsed = time.time() - t0

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    print(f"\nROC-AUC (paired, {result['n_pairs']} splits):")
    print(f"  Sentinel-Z: {result['sz_roc_auc']['mean']:.4f} +/- {result['sz_roc_auc']['std']:.4f}")
    print(f"  MAGIC:      {result['mg_roc_auc']['mean']:.4f} +/- {result['mg_roc_auc']['std']:.4f}")
    d = result["delta_roc_auc"]
    print(f"  Delta:      {d['mean']:+.4f} +/- {d['std']:.4f}  "
          f"95% CI [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}]  P(SZ<=MG) = {d['p_lt_zero']:.3f}")

    print(f"\nPR-AUC (paired):")
    print(f"  Sentinel-Z: {result['sz_pr_auc']['mean']:.4f} +/- {result['sz_pr_auc']['std']:.4f}")
    print(f"  MAGIC:      {result['mg_pr_auc']['mean']:.4f} +/- {result['mg_pr_auc']['std']:.4f}")
    d = result["delta_pr_auc"]
    print(f"  Delta:      {d['mean']:+.4f} +/- {d['std']:.4f}  "
          f"95% CI [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}]  P(SZ<=MG) = {d['p_lt_zero']:.3f}")

    print(f"\nF1 at Youden's J:")
    print(f"  Sentinel-Z: {result['sz_f1']['mean']:.4f}")
    print(f"  MAGIC:      {result['mg_f1']['mean']:.4f}")

    print(f"\nFPR at Youden's J:")
    print(f"  Sentinel-Z: {result['sz_fpr']['mean']:.4f}")
    print(f"  MAGIC:      {result['mg_fpr']['mean']:.4f}")

    print(f"\nBrier score (lower = better calibration):")
    print(f"  Sentinel-Z: {result['sz_brier']['mean']:.4f}")
    print(f"  MAGIC:      {result['mg_brier']['mean']:.4f}")

    d_pr = result["delta_pr_auc"]
    if d_pr["p_lt_zero"] <= 0.05:
        verdict = "Sentinel-Z SIGNIFICANTLY BEATS MAGIC on PR-AUC (p <= 0.05)"
    elif d_pr["p_lt_zero"] >= 0.95:
        verdict = "MAGIC SIGNIFICANTLY BEATS Sentinel-Z on PR-AUC (p <= 0.05)"
    elif abs(d_pr["mean"]) < 0.02:
        verdict = "STATISTICALLY EQUIVALENT (delta < 0.02 PR-AUC, CI crosses zero)"
    else:
        verdict = (f"INCONCLUSIVE (delta {d_pr['mean']:+.4f}, "
                   f"95% CI [{d_pr['ci_low']:+.4f}, {d_pr['ci_high']:+.4f}] crosses zero)")
    print(f"\nVERDICT: {verdict}")
    if args.stub:
        print("(stub mode — verdict is meaningless until real MAGIC scores are provided)")

    report = {
        "mode": "stub" if args.stub else "real",
        "n_windows_aligned": len(merged),
        "n_pairs": result["n_pairs"],
        "bootstrap_iterations": args.bootstrap,
        "results": result,
        "verdict": verdict,
        "wall_time_sec": elapsed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report: {args.out}")
    print(f"Wall time: {elapsed:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
