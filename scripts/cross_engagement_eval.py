"""
Cross-engagement evaluation: the single most important test in Phase 0.

Trains an RF detector on one DARPA TC engagement (e.g., E5-FiveDirections)
and evaluates it on a held-out engagement (e.g., E3-CADETS). Reports:

  - Within-engagement baseline (train on E5, test on E5 holdout)
  - Cross-engagement transfer  (train on E5, test on E3-CADETS)
  - Reverse cross-engagement   (train on E3-CADETS, test on E5)
  - Per-feature degradation (which features transfer, which don't)

If cross-engagement metrics are within 5-10 points of within-engagement, the
"zero-shot" / "generalizable" claim has real evidence. If they collapse to
random (AUC < 0.6), the model is dataset-specific and the claim is wrong.

This is the test that will be the headline of our Tier-2 paper. Be honest
about the result regardless of which way it goes.

Requirements:
  - Phase 4 results must exist for BOTH engagements:
      data/model_ready/detection/phase4_results.json          (E5)
      data/model_ready_e3/<team>/detection/phase4_results.json (E3)
  - Run scripts/ingest_e5.py and scripts/ingest_e3.py first.

Usage:
    python scripts/cross_engagement_eval.py
    python scripts/cross_engagement_eval.py --e3-team cadets
    python scripts/cross_engagement_eval.py --bootstrap 30
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
    BASE_FEATURES, add_temporal_features, feature_columns,
)


def load_engagement(results_path: Path, engagement_label: str) -> pd.DataFrame:
    """Load phase4_results.json into a per-window DataFrame with temporal features.

    Adds an 'engagement' column for downstream tracking.
    """
    if not results_path.exists():
        raise FileNotFoundError(f"{results_path} does not exist")
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
    if df.empty:
        raise ValueError(f"No windows found in {results_path}")
    df = add_temporal_features(df)
    df["engagement"] = engagement_label
    return df


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
    return {"precision": float(p), "recall": float(r), "f1": float(f1),
            "fpr": float(fpr), "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)}


def evaluate(train_df: pd.DataFrame, test_df: pd.DataFrame,
             feature_cols, label_train: str, label_test: str,
             seed: int = 42) -> dict:
    """Train on train_df, evaluate on test_df. Returns full metrics dict."""
    if train_df["label"].sum() == 0:
        return {"error": "no attacks in training data — cannot fit", "fitted": False}
    if test_df["label"].sum() == 0:
        return {"error": "no attacks in test data — cannot evaluate", "fitted": False}

    rf = fit_rf(train_df[feature_cols].values, train_df["label"].values, seed=seed)
    scores = rf.predict_proba(test_df[feature_cols].values)[:, 1]
    ty = test_df["label"].values

    try:
        roc = float(roc_auc_score(ty, scores))
        pr = float(average_precision_score(ty, scores))
        brier = float(brier_score_loss(ty, scores))
    except ValueError as e:
        return {"error": str(e), "fitted": True}

    threshold = youden_threshold(scores, ty)
    m = metrics_at(scores, ty, threshold)

    return {
        "fitted": True,
        "train_engagement": label_train,
        "test_engagement": label_test,
        "n_train": len(train_df),
        "n_train_attacks": int(train_df["label"].sum()),
        "n_test": len(test_df),
        "n_test_attacks": int(ty.sum()),
        "roc_auc": roc,
        "pr_auc": pr,
        "brier": brier,
        "threshold_youden": threshold,
        **m,
        "feature_importances": dict(zip(feature_cols, [float(v) for v in rf.feature_importances_])),
    }


def bootstrap_eval(train_df: pd.DataFrame, test_df: pd.DataFrame,
                   feature_cols, label_train: str, label_test: str,
                   n_iter: int = 30) -> dict:
    """Run multiple seeds, report mean +/- std + 95% CI for ROC-AUC and PR-AUC."""
    aucs, prs, briers = [], [], []
    for seed in range(n_iter):
        r = evaluate(train_df, test_df, feature_cols, label_train, label_test, seed=seed)
        if not r.get("fitted"):
            continue
        aucs.append(r["roc_auc"])
        prs.append(r["pr_auc"])
        briers.append(r["brier"])

    if not aucs:
        return {"error": "all iterations failed"}

    def stat(arr):
        a = np.array(arr)
        return {"mean": float(a.mean()), "std": float(a.std()),
                "ci_low": float(np.percentile(a, 2.5)),
                "ci_high": float(np.percentile(a, 97.5))}

    return {
        "n_iter": len(aucs),
        "train_engagement": label_train,
        "test_engagement": label_test,
        "roc_auc": stat(aucs),
        "pr_auc": stat(prs),
        "brier": stat(briers),
    }


def within_engagement_split(df: pd.DataFrame, feature_cols,
                            label: str, n_iter: int = 30) -> dict:
    """Within-engagement baseline: 70/30 stratified, bootstrap n_iter times."""
    aucs, prs, briers = [], [], []
    for seed in range(n_iter):
        train, test = train_test_split(
            df, test_size=0.30, stratify=df["label"], random_state=seed,
        )
        if train["label"].sum() == 0 or test["label"].sum() == 0:
            continue
        r = evaluate(train, test, feature_cols, label, label, seed=seed)
        if not r.get("fitted"):
            continue
        aucs.append(r["roc_auc"])
        prs.append(r["pr_auc"])
        briers.append(r["brier"])

    if not aucs:
        return {"error": "all iterations failed"}

    def stat(arr):
        a = np.array(arr)
        return {"mean": float(a.mean()), "std": float(a.std()),
                "ci_low": float(np.percentile(a, 2.5)),
                "ci_high": float(np.percentile(a, 97.5))}

    return {
        "n_iter": len(aucs),
        "train_engagement": label,
        "test_engagement": f"{label}_holdout",
        "roc_auc": stat(aucs),
        "pr_auc": stat(prs),
        "brier": stat(briers),
    }


def print_metrics_row(label: str, metrics: dict) -> None:
    if "error" in metrics:
        print(f"  {label}: ERROR — {metrics['error']}")
        return
    roc = metrics["roc_auc"]
    pr = metrics["pr_auc"]
    print(f"  {label}:")
    print(f"    ROC-AUC: {roc['mean']:.4f} +/- {roc['std']:.4f}  "
          f"95% CI [{roc['ci_low']:.4f}, {roc['ci_high']:.4f}]")
    print(f"    PR-AUC:  {pr['mean']:.4f} +/- {pr['std']:.4f}  "
          f"95% CI [{pr['ci_low']:.4f}, {pr['ci_high']:.4f}]")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--e5-results", type=Path,
                   default=REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json",
                   help="E5 (FiveDirections) phase4 results JSON")
    p.add_argument("--e3-team", choices=["cadets", "theia", "trace", "fivedirections"],
                   default="cadets",
                   help="E3 TA1 team to cross-validate against (default: cadets)")
    p.add_argument("--e3-results", type=Path, default=None,
                   help="E3 phase4 results JSON (default: derived from --e3-team)")
    p.add_argument("--bootstrap", type=int, default=30,
                   help="Number of bootstrap iterations (default: 30)")
    p.add_argument("--out", type=Path,
                   default=REPO_ROOT / "data" / "model_ready" / "cross_engagement_report.json")
    args = p.parse_args()

    e3_results = args.e3_results or (
        REPO_ROOT / "data" / "model_ready_e3" / args.e3_team / "detection" / "phase4_results.json"
    )

    print("=" * 72)
    print("CROSS-ENGAGEMENT EVALUATION")
    print("=" * 72)
    print(f"E5 results: {args.e5_results}")
    print(f"E3 results: {e3_results}")
    print(f"Bootstrap:  {args.bootstrap} iterations")

    try:
        df_e5 = load_engagement(args.e5_results, "e5_fivedirections")
        print(f"\nE5 loaded: {len(df_e5):,} windows ({int(df_e5['label'].sum())} attacks)")
    except FileNotFoundError as exc:
        print(f"\nERROR loading E5: {exc}", file=sys.stderr)
        print("  Run: python scripts/ingest_e5.py && python scripts/verify_phase4.py", file=sys.stderr)
        return 1

    try:
        df_e3 = load_engagement(e3_results, f"e3_{args.e3_team}")
        print(f"E3 loaded: {len(df_e3):,} windows ({int(df_e3['label'].sum())} attacks)")
    except FileNotFoundError as exc:
        print(f"\nERROR loading E3: {exc}", file=sys.stderr)
        print(f"  Run: python scripts/ingest_e3.py --team {args.e3_team}", file=sys.stderr)
        print("       python scripts/verify_phase4.py "
              f"--results-dir data/model_ready_e3/{args.e3_team}/detection", file=sys.stderr)
        return 1

    feature_cols = feature_columns()
    print(f"\nFeature set: {len(feature_cols)} features (base + temporal)")

    t0 = time.time()
    report = {
        "config": {
            "e5_results_path": str(args.e5_results),
            "e3_results_path": str(e3_results),
            "e3_team": args.e3_team,
            "bootstrap_iterations": args.bootstrap,
            "feature_count": len(feature_cols),
            "feature_set": feature_cols,
        },
        "data_summary": {
            "e5": {"n_windows": len(df_e5), "n_attacks": int(df_e5["label"].sum())},
            "e3": {"n_windows": len(df_e3), "n_attacks": int(df_e3["label"].sum())},
        },
    }

    print("\n[1/4] Within-engagement E5 baseline (70/30 stratified, bootstrap)")
    report["within_e5"] = within_engagement_split(df_e5, feature_cols, "e5_fivedirections", args.bootstrap)
    print_metrics_row("within E5 (FiveDirections)", report["within_e5"])

    print(f"\n[2/4] Within-engagement E3-{args.e3_team} baseline (70/30 stratified, bootstrap)")
    report["within_e3"] = within_engagement_split(df_e3, feature_cols, f"e3_{args.e3_team}", args.bootstrap)
    print_metrics_row(f"within E3-{args.e3_team}", report["within_e3"])

    print("\n[3/4] CROSS-ENGAGEMENT: train E5 -> test E3 (the headline test)")
    print("      Note: with this protocol, the train/test split has no overlap by")
    print("      construction — train is ALL of E5, test is ALL of E3.")
    cross_e5_to_e3 = evaluate(df_e5, df_e3, feature_cols,
                              "e5_fivedirections", f"e3_{args.e3_team}", seed=42)
    report["cross_e5_to_e3"] = cross_e5_to_e3
    if cross_e5_to_e3.get("fitted"):
        print(f"  E5 -> E3-{args.e3_team}:")
        print(f"    ROC-AUC: {cross_e5_to_e3['roc_auc']:.4f}")
        print(f"    PR-AUC:  {cross_e5_to_e3['pr_auc']:.4f}")
        print(f"    F1:      {cross_e5_to_e3['f1']:.4f}")
        print(f"    Recall:  {cross_e5_to_e3['recall']:.4f}")
        print(f"    Precision: {cross_e5_to_e3['precision']:.4f}")
        print(f"    FPR:     {cross_e5_to_e3['fpr']:.4f}")
    else:
        print(f"  ERROR: {cross_e5_to_e3.get('error')}")

    print(f"\n[4/4] REVERSE CROSS-ENGAGEMENT: train E3-{args.e3_team} -> test E5")
    cross_e3_to_e5 = evaluate(df_e3, df_e5, feature_cols,
                              f"e3_{args.e3_team}", "e5_fivedirections", seed=42)
    report["cross_e3_to_e5"] = cross_e3_to_e5
    if cross_e3_to_e5.get("fitted"):
        print(f"  E3-{args.e3_team} -> E5:")
        print(f"    ROC-AUC: {cross_e3_to_e5['roc_auc']:.4f}")
        print(f"    PR-AUC:  {cross_e3_to_e5['pr_auc']:.4f}")
        print(f"    F1:      {cross_e3_to_e5['f1']:.4f}")
        print(f"    Recall:  {cross_e3_to_e5['recall']:.4f}")
        print(f"    Precision: {cross_e3_to_e5['precision']:.4f}")
        print(f"    FPR:     {cross_e3_to_e5['fpr']:.4f}")
    else:
        print(f"  ERROR: {cross_e3_to_e5.get('error')}")

    elapsed = time.time() - t0
    report["wall_time_sec"] = elapsed

    # ---- Verdict ----
    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)

    if cross_e5_to_e3.get("fitted") and report["within_e5"].get("roc_auc"):
        within = report["within_e5"]["roc_auc"]["mean"]
        cross = cross_e5_to_e3["roc_auc"]
        drop = within - cross
        print(f"  Within-E5 ROC-AUC: {within:.4f}")
        print(f"  Cross-engagement ROC-AUC (E5 -> E3-{args.e3_team}): {cross:.4f}")
        print(f"  Drop: {drop:.4f}")
        if drop < 0.05:
            verdict = "STRONG TRANSFER: cross-engagement performance within 5 points of within"
        elif drop < 0.15:
            verdict = "MODERATE TRANSFER: cross-engagement drops 5-15 points (typical generalization gap)"
        elif drop < 0.30:
            verdict = "WEAK TRANSFER: significant degradation across engagements"
        else:
            verdict = "FAILED TRANSFER: cross-engagement near-random or worse"
        print(f"  Verdict: {verdict}")
        report["verdict"] = verdict
        report["transfer_drop_roc_auc"] = float(drop)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report: {args.out}")
    print(f"Total time: {elapsed:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
