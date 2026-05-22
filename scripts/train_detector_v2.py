"""
V2 detector: same RF model class, extended feature set with temporal context.

Reads phase4_results.json, attaches 13 new temporal features (rolling 30-window
context for unknown_ratio, num_nodes, density, network_ratio, fused_score,
plus an anomaly_count_30s indicator), retrains, and saves under
models/rf_detector_v2.joblib.

Then runs the SAME rigorous validation suite (30-bootstrap, paired bootstrap
vs the v1 model trained on identical splits) so we can tell whether the new
features are statistically significant.
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
from sklearn.inspection import permutation_importance

from src.sentinel_z.pipeline.temporal_features import (
    BASE_FEATURES, TEMPORAL_FEATURES, add_temporal_features, feature_columns,
)
from src.sentinel_z.detection.rf_detector import RFDetector


def load_features_with_temporal(results_path: Path) -> pd.DataFrame:
    """Same DataFrame as load_features() but with rolling temporal features added."""
    with open(results_path) as f:
        data = json.load(f)
    rows = []
    for w in data.get("windows", []):
        profile = w.get("behavioral_profile", {}) or {}
        rows.append({
            "window_id":    w["window_id"],
            "label":        w["label"],
            "fused_score":  w["fused_score"],
            "unknown_ratio": profile.get("_unknown_ratio", 0.0),
            "num_nodes":    profile.get("_num_nodes", 0),
            "num_edges":    profile.get("_num_edges", 0),
            "num_subjects": profile.get("_num_subjects", 0),
            "density":      profile.get("_density", 0.0),
            "network_ratio": profile.get("_network_ratio", 0.0),
            "structural":   w.get("structural_score", 0.0),
        })
    df = pd.DataFrame(rows)
    df = add_temporal_features(df)
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
    if len(cands) > 500:
        cands = np.percentile(scores, np.linspace(0, 100, 501))
    best_t, best_j = cands[0], -1.0
    for t in cands:
        preds = (scores >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(labels, preds, labels=[0, 1]).ravel()
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        j = r - fpr
        if j > best_j:
            best_j, best_t = j, t
    return float(best_t)


def metrics_at(scores, labels, threshold):
    preds = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, preds, labels=[0, 1]).ravel()
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1, "fpr": fpr}


def evaluate_paired(df: pd.DataFrame, n_iter: int = 30) -> dict:
    """Run n_iter stratified splits. For each, train v1 (BASE) and v2 (BASE+TEMP)
    on the same split. Report per-iteration deltas + 95% CI.
    """
    base_cols = BASE_FEATURES
    full_cols = feature_columns()

    print(f"Paired bootstrap: {n_iter} stratified splits, comparing v1 vs v2")
    rows = []
    for seed in range(n_iter):
        train_df, test_df = train_test_split(
            df, test_size=0.30, stratify=df["label"], random_state=seed,
        )
        if test_df["label"].sum() == 0:
            continue

        rf_v1 = fit_rf(train_df[base_cols].values, train_df["label"].values, seed=seed)
        s_v1 = rf_v1.predict_proba(test_df[base_cols].values)[:, 1]

        rf_v2 = fit_rf(train_df[full_cols].values, train_df["label"].values, seed=seed)
        s_v2 = rf_v2.predict_proba(test_df[full_cols].values)[:, 1]

        ty = test_df["label"].values
        try:
            roc_v1 = roc_auc_score(ty, s_v1); roc_v2 = roc_auc_score(ty, s_v2)
            pr_v1 = average_precision_score(ty, s_v1); pr_v2 = average_precision_score(ty, s_v2)
            br_v1 = brier_score_loss(ty, s_v1); br_v2 = brier_score_loss(ty, s_v2)
        except ValueError:
            continue

        t_v1 = youden_threshold(s_v1, ty); m_v1 = metrics_at(s_v1, ty, t_v1)
        t_v2 = youden_threshold(s_v2, ty); m_v2 = metrics_at(s_v2, ty, t_v2)

        rows.append({
            "seed": seed,
            "v1_roc": roc_v1, "v2_roc": roc_v2, "delta_roc": roc_v2 - roc_v1,
            "v1_pr":  pr_v1,  "v2_pr":  pr_v2,  "delta_pr":  pr_v2 - pr_v1,
            "v1_brier": br_v1, "v2_brier": br_v2, "delta_brier": br_v2 - br_v1,
            "v1_recall": m_v1["recall"], "v2_recall": m_v2["recall"],
            "v1_precision": m_v1["precision"], "v2_precision": m_v2["precision"],
            "v1_fpr": m_v1["fpr"], "v2_fpr": m_v2["fpr"],
            "v1_f1": m_v1["f1"], "v2_f1": m_v2["f1"],
        })
        if (seed + 1) % 10 == 0:
            print(f"  {seed+1}/{n_iter} done")

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
        "v1_roc_auc": stat("v1_roc"), "v2_roc_auc": stat("v2_roc"),
        "delta_roc_auc": stat("delta_roc"),
        "v1_pr_auc": stat("v1_pr"), "v2_pr_auc": stat("v2_pr"),
        "delta_pr_auc": stat("delta_pr"),
        "v1_recall": stat("v1_recall"), "v2_recall": stat("v2_recall"),
        "v1_precision": stat("v1_precision"), "v2_precision": stat("v2_precision"),
        "v1_f1": stat("v1_f1"), "v2_f1": stat("v2_f1"),
        "v1_fpr": stat("v1_fpr"), "v2_fpr": stat("v2_fpr"),
        "v1_brier": stat("v1_brier"), "v2_brier": stat("v2_brier"),
    }


def permutation_v2(df: pd.DataFrame) -> list[dict]:
    train_df, test_df = train_test_split(
        df, test_size=0.30, stratify=df["label"], random_state=42,
    )
    full_cols = feature_columns()
    rf = fit_rf(train_df[full_cols].values, train_df["label"].values)
    if test_df["label"].sum() == 0:
        return []
    result = permutation_importance(
        rf, test_df[full_cols].values, test_df["label"].values,
        n_repeats=10, random_state=42, scoring="roc_auc", n_jobs=-1,
    )
    out = []
    for i, name in enumerate(full_cols):
        out.append({
            "feature": name,
            "perm_mean": float(result.importances_mean[i]),
            "perm_std": float(result.importances_std[i]),
            "rf_builtin": float(rf.feature_importances_[i]),
        })
    out.sort(key=lambda r: -r["perm_mean"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path,
                    default=REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json")
    ap.add_argument("--out-model", type=Path,
                    default=REPO_ROOT / "models" / "rf_detector_v2.joblib")
    ap.add_argument("--out-report", type=Path,
                    default=REPO_ROOT / "data" / "model_ready" / "v2_validation_report.json")
    ap.add_argument("--n-iter", type=int, default=30)
    args = ap.parse_args()

    print("Loading features and adding temporal context ...")
    df = load_features_with_temporal(args.results)
    print(f"  {len(df):,} windows | {int(df['label'].sum())} attacks "
          f"| {len(BASE_FEATURES)} base + {len(TEMPORAL_FEATURES)} temporal features")

    full_cols = feature_columns()
    print("\n[1/3] Training final v2 model on full data ...")
    detector = RFDetector(n_estimators=200, max_depth=8, class_weight="balanced")
    detector.feature_names = full_cols
    card = detector.fit(df, df["label"].values, threshold_objective="youden")
    print(f"  Trained: ROC-AUC={card.roc_auc_test:.4f} (single split for sizing only)")
    detector.save(args.out_model)
    print(f"  Saved: {args.out_model}")

    print("\n[2/3] Permutation importance on v2 ...")
    perm = permutation_v2(df)
    print(f"  {'feature':<32} {'perm_mean':>10} {'rf_builtin':>12}")
    for p in perm:
        print(f"  {p['feature']:<32} {p['perm_mean']:>10.4f} {p['rf_builtin']:>12.4f}")

    print(f"\n[3/3] Paired bootstrap v1 (base only) vs v2 (base+temporal), {args.n_iter} splits ...")
    t0 = time.time()
    paired = evaluate_paired(df, n_iter=args.n_iter)
    elapsed = time.time() - t0

    print("\n" + "=" * 72)
    print("V2 VALIDATION SUMMARY")
    print("=" * 72)
    print(f"\nv1 (base 7 features) mean ROC-AUC: {paired['v1_roc_auc']['mean']:.4f}")
    print(f"v2 (base + 13 temporal) mean ROC-AUC: {paired['v2_roc_auc']['mean']:.4f}")
    d = paired["delta_roc_auc"]
    print(f"  Delta: {d['mean']:+.4f} +/- {d['std']:.4f}  "
          f"95% CI [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}]  "
          f"P(v2 <= v1) = {d['p_lt_zero']:.3f}")

    print(f"\nv1 mean PR-AUC: {paired['v1_pr_auc']['mean']:.4f}")
    print(f"v2 mean PR-AUC: {paired['v2_pr_auc']['mean']:.4f}")
    d = paired["delta_pr_auc"]
    print(f"  Delta: {d['mean']:+.4f} +/- {d['std']:.4f}  "
          f"95% CI [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}]  "
          f"P(v2 <= v1) = {d['p_lt_zero']:.3f}")

    print(f"\nF1 at Youden:")
    print(f"  v1: {paired['v1_f1']['mean']:.4f} +/- {paired['v1_f1']['std']:.4f}")
    print(f"  v2: {paired['v2_f1']['mean']:.4f} +/- {paired['v2_f1']['std']:.4f}")
    print(f"\nFPR at Youden:")
    print(f"  v1: {paired['v1_fpr']['mean']:.4f} +/- {paired['v1_fpr']['std']:.4f}")
    print(f"  v2: {paired['v2_fpr']['mean']:.4f} +/- {paired['v2_fpr']['std']:.4f}")

    if paired["delta_pr_auc"]["p_lt_zero"] <= 0.05:
        verdict = "v2 SIGNIFICANTLY BEATS v1 on PR-AUC (p<=0.05)"
    elif paired["delta_pr_auc"]["p_lt_zero"] <= 0.20:
        verdict = "v2 likely beats v1 on PR-AUC but not at 95% confidence"
    else:
        verdict = "v2 does NOT significantly improve over v1"
    print(f"\nVERDICT: {verdict}")
    print(f"Total time: {elapsed:.0f}s")

    report = {
        "n_windows": len(df),
        "n_attacks": int(df["label"].sum()),
        "feature_set_v2": full_cols,
        "permutation_importance_v2": perm,
        "paired_bootstrap_v1_vs_v2": paired,
        "verdict": verdict,
    }
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_report, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to {args.out_report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
