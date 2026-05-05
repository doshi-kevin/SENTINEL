"""
Rigorous validation suite for the RF detector.

This script goes beyond the single-split metrics in the model card and
addresses the standard ML credibility questions a reviewer or buyer would ask:

  1. STABILITY: are the metrics stable across random splits, or is 0.989 luck?
     -> 30-iteration stratified bootstrap. Report mean +/- std + 95% CI for
        ROC-AUC, PR-AUC, F1, Recall, Precision.

  2. IMBALANCE: ROC-AUC can be optimistic on extremely imbalanced data
     (86 attacks / 75147 = 0.11%).
     -> Compute Average Precision (PR-AUC), which is more informative under
        imbalance.

  3. SIGNIFICANCE: does RF beat the simpler baselines by a margin we can defend?
     -> Paired bootstrap test for ROC-AUC and PR-AUC differences vs the
        unknown_ratio threshold baseline. Report 95% CI on the delta.

  4. CALIBRATION: do RF probability scores correspond to real attack frequencies?
     -> Brier score + reliability-diagram bin counts. SOC analysts need
        calibrated scores ("0.8 means roughly 80% confidence") to trust the tool.

  5. FEATURE IMPORTANCE ROBUSTNESS: RF's built-in importance is biased toward
     high-cardinality features.
     -> Permutation importance, computed on held-out test data.

  6. K-FOLD CROSS-VALIDATION: with only 86 attacks, single splits are
     statistically thin.
     -> 5-fold StratifiedKFold; report per-fold metrics.

Outputs: data/model_ready/rigorous_validation_report.json + console summary.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, asdict
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
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.inspection import permutation_importance


FEATURES = ["num_nodes", "num_edges", "num_subjects", "density",
            "unknown_ratio", "network_ratio", "structural"]


def load_features(results_path: Path) -> pd.DataFrame:
    """Same flat feature DataFrame the rest of the suite uses."""
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
    return pd.DataFrame(rows)


@dataclass
class FoldMetrics:
    seed: int
    roc_auc: float
    pr_auc: float
    f1_at_youden: float
    precision_at_youden: float
    recall_at_youden: float
    fpr_at_youden: float
    threshold_youden: float
    brier_score: float
    n_train: int
    n_test: int
    n_test_attacks: int


def metrics_at_threshold(scores: np.ndarray, labels: np.ndarray,
                         threshold: float) -> dict:
    preds = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, preds, labels=[0, 1]).ravel()
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {"precision": float(p), "recall": float(r), "f1": float(f1),
            "fpr": float(fpr),
            "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)}


def youden_threshold(scores: np.ndarray, labels: np.ndarray) -> float:
    """Pick threshold maximizing TPR - FPR (Youden's J)."""
    cands = np.unique(scores)
    if len(cands) > 500:
        cands = np.percentile(scores, np.linspace(0, 100, 501))
    best_t, best_j = cands[0], -1.0
    for t in cands:
        m = metrics_at_threshold(scores, labels, t)
        j = m["recall"] - m["fpr"]
        if j > best_j:
            best_j, best_t = j, t
    return float(best_t)


def fit_rf(train_X, train_y, seed=42):
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, class_weight="balanced",
        random_state=seed, n_jobs=-1,
    )
    rf.fit(train_X, train_y)
    return rf


def evaluate_split(df: pd.DataFrame, seed: int,
                   test_size: float = 0.30) -> tuple[FoldMetrics, np.ndarray, np.ndarray]:
    """Single bootstrap iteration: stratified split, fit RF, return metrics + scores."""
    train_df, test_df = train_test_split(
        df, test_size=test_size, stratify=df["label"], random_state=seed,
    )
    rf = fit_rf(train_df[FEATURES].values, train_df["label"].values, seed=seed)
    test_scores = rf.predict_proba(test_df[FEATURES].values)[:, 1]
    test_y = test_df["label"].values

    if test_y.sum() == 0:
        return None, test_scores, test_y

    roc = float(roc_auc_score(test_y, test_scores))
    pr  = float(average_precision_score(test_y, test_scores))
    brier = float(brier_score_loss(test_y, test_scores))
    t = youden_threshold(test_scores, test_y)
    m = metrics_at_threshold(test_scores, test_y, t)

    fm = FoldMetrics(
        seed=seed, roc_auc=roc, pr_auc=pr,
        f1_at_youden=m["f1"], precision_at_youden=m["precision"],
        recall_at_youden=m["recall"], fpr_at_youden=m["fpr"],
        threshold_youden=t, brier_score=brier,
        n_train=len(train_df), n_test=len(test_df),
        n_test_attacks=int(test_y.sum()),
    )
    return fm, test_scores, test_y


def bootstrap_validation(df: pd.DataFrame, n_iter: int = 30) -> list[FoldMetrics]:
    """Run n_iter stratified random splits with different seeds."""
    print(f"\n[1/6] BOOTSTRAP: {n_iter} stratified random splits")
    print("  seeds 0..N, 70/30 stratified, fit RF, eval on test")
    out = []
    for seed in range(n_iter):
        fm, _, _ = evaluate_split(df, seed)
        if fm is not None:
            out.append(fm)
        if (seed + 1) % 10 == 0 or seed == n_iter - 1:
            print(f"  {seed+1}/{n_iter} splits done")
    return out


def report_bootstrap(metrics: list[FoldMetrics]) -> dict:
    arr = lambda key: np.array([getattr(m, key) for m in metrics])
    roc, pr, f1 = arr("roc_auc"), arr("pr_auc"), arr("f1_at_youden")
    rec, prec, fpr = arr("recall_at_youden"), arr("precision_at_youden"), arr("fpr_at_youden")
    brier = arr("brier_score")

    def stat(a):
        return {"mean": float(a.mean()), "std": float(a.std()),
                "ci_low": float(np.percentile(a, 2.5)),
                "ci_high": float(np.percentile(a, 97.5))}

    return {"n_iter": len(metrics),
            "roc_auc": stat(roc), "pr_auc": stat(pr), "f1": stat(f1),
            "recall": stat(rec), "precision": stat(prec), "fpr": stat(fpr),
            "brier_score": stat(brier)}


def paired_bootstrap_test(df: pd.DataFrame, n_iter: int = 30) -> dict:
    """For each split, compute (rf_score - unknown_only_score) on the same test
    set. Report 95% CI on the delta. If CI excludes 0, RF is significantly better.
    """
    print(f"\n[2/6] PAIRED BOOTSTRAP: RF vs unknown_ratio baseline ({n_iter} splits)")
    deltas_roc, deltas_pr = [], []
    for seed in range(n_iter):
        train_df, test_df = train_test_split(
            df, test_size=0.30, stratify=df["label"], random_state=seed,
        )
        if test_df["label"].sum() == 0:
            continue
        rf = fit_rf(train_df[FEATURES].values, train_df["label"].values, seed=seed)
        rf_scores = rf.predict_proba(test_df[FEATURES].values)[:, 1]
        baseline_scores = test_df["unknown_ratio"].values
        ty = test_df["label"].values
        try:
            d_roc = roc_auc_score(ty, rf_scores) - roc_auc_score(ty, baseline_scores)
            d_pr  = average_precision_score(ty, rf_scores) - average_precision_score(ty, baseline_scores)
            deltas_roc.append(d_roc)
            deltas_pr.append(d_pr)
        except ValueError:
            continue
    a = np.array(deltas_roc)
    b = np.array(deltas_pr)
    return {
        "n_pairs": len(a),
        "roc_auc_delta": {"mean": float(a.mean()), "std": float(a.std()),
                           "ci_low": float(np.percentile(a, 2.5)),
                           "ci_high": float(np.percentile(a, 97.5)),
                           "p_lt_zero": float(np.mean(a <= 0))},
        "pr_auc_delta": {"mean": float(b.mean()), "std": float(b.std()),
                          "ci_low": float(np.percentile(b, 2.5)),
                          "ci_high": float(np.percentile(b, 97.5)),
                          "p_lt_zero": float(np.mean(b <= 0))},
    }


def kfold_validation(df: pd.DataFrame, n_splits: int = 5) -> dict:
    """K-fold stratified CV. Different folds, different statistical power."""
    print(f"\n[3/6] {n_splits}-FOLD STRATIFIED CV")
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    folds = []
    for i, (train_idx, test_idx) in enumerate(skf.split(df[FEATURES], df["label"])):
        train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]
        rf = fit_rf(train_df[FEATURES].values, train_df["label"].values)
        scores = rf.predict_proba(test_df[FEATURES].values)[:, 1]
        ty = test_df["label"].values
        if ty.sum() == 0:
            continue
        folds.append({
            "fold": i + 1, "n_test": len(test_df), "n_test_attacks": int(ty.sum()),
            "roc_auc": float(roc_auc_score(ty, scores)),
            "pr_auc": float(average_precision_score(ty, scores)),
            "brier": float(brier_score_loss(ty, scores)),
        })
        print(f"  fold {i+1}: ROC-AUC={folds[-1]['roc_auc']:.4f} "
              f"PR-AUC={folds[-1]['pr_auc']:.4f}")
    aucs = np.array([f["roc_auc"] for f in folds])
    prs = np.array([f["pr_auc"] for f in folds])
    return {
        "folds": folds,
        "roc_auc_mean": float(aucs.mean()), "roc_auc_std": float(aucs.std()),
        "pr_auc_mean": float(prs.mean()), "pr_auc_std": float(prs.std()),
    }


def calibration_analysis(df: pd.DataFrame, n_bins: int = 10) -> dict:
    """Reliability diagram: are RF probabilities calibrated?"""
    print(f"\n[4/6] CALIBRATION (reliability diagram, {n_bins} bins)")
    train_df, test_df = train_test_split(
        df, test_size=0.30, stratify=df["label"], random_state=42,
    )
    rf = fit_rf(train_df[FEATURES].values, train_df["label"].values)
    scores = rf.predict_proba(test_df[FEATURES].values)[:, 1]
    ty = test_df["label"].values
    bins = np.linspace(0, 1, n_bins + 1)
    bin_data = []
    for i in range(n_bins):
        mask = (scores >= bins[i]) & (scores < bins[i+1] if i < n_bins-1 else scores <= bins[i+1])
        if mask.sum() == 0:
            continue
        mean_pred = float(scores[mask].mean())
        actual = float(ty[mask].mean())
        n = int(mask.sum())
        bin_data.append({"bin_low": float(bins[i]), "bin_high": float(bins[i+1]),
                         "n": n, "mean_predicted": mean_pred, "actual_rate": actual})
        print(f"  [{bins[i]:.2f}-{bins[i+1]:.2f}]: n={n:>5}  pred={mean_pred:.3f}  actual={actual:.3f}")
    return {"brier_score": float(brier_score_loss(ty, scores)), "bins": bin_data}


def permutation_importance_analysis(df: pd.DataFrame) -> dict:
    """Unbiased feature importance via permutation."""
    print("\n[5/6] PERMUTATION IMPORTANCE (unbiased vs RF.feature_importances_)")
    train_df, test_df = train_test_split(
        df, test_size=0.30, stratify=df["label"], random_state=42,
    )
    rf = fit_rf(train_df[FEATURES].values, train_df["label"].values)
    if test_df["label"].sum() == 0:
        return {"note": "no test attacks - skipped"}
    result = permutation_importance(
        rf, test_df[FEATURES].values, test_df["label"].values,
        n_repeats=10, random_state=42, scoring="roc_auc", n_jobs=-1,
    )
    out = []
    for i, name in enumerate(FEATURES):
        out.append({
            "feature": name,
            "importance_mean": float(result.importances_mean[i]),
            "importance_std": float(result.importances_std[i]),
            "rf_builtin": float(rf.feature_importances_[i]),
        })
    out.sort(key=lambda r: -r["importance_mean"])
    print(f"  {'feature':<18} {'perm_mean':>10} {'perm_std':>10} {'rf_builtin':>12}")
    for r in out:
        print(f"  {r['feature']:<18} {r['importance_mean']:>10.4f} "
              f"{r['importance_std']:>10.4f} {r['rf_builtin']:>12.4f}")
    return {"permutation_importance": out}


def sanity_check_random(df: pd.DataFrame) -> dict:
    """Train RF on shuffled labels - should get ~0.5 ROC-AUC. If higher, leakage."""
    print("\n[6/6] SANITY: shuffled-label control")
    train_df, test_df = train_test_split(
        df, test_size=0.30, stratify=df["label"], random_state=42,
    )
    shuffled = np.random.RandomState(42).permutation(train_df["label"].values)
    if shuffled.sum() == 0 or test_df["label"].sum() == 0:
        return {"note": "degenerate"}
    rf = fit_rf(train_df[FEATURES].values, shuffled, seed=42)
    scores = rf.predict_proba(test_df[FEATURES].values)[:, 1]
    ty = test_df["label"].values
    auc = float(roc_auc_score(ty, scores))
    print(f"  Shuffled-label ROC-AUC: {auc:.4f} (should be ~0.5; >0.6 = data leakage)")
    return {"shuffled_label_roc_auc": auc, "expected_around": 0.5}


def main() -> int:
    results = REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json"
    out_path = REPO_ROOT / "data" / "model_ready" / "rigorous_validation_report.json"
    df = load_features(results)
    print(f"Loaded {len(df):,} windows ({int(df['label'].sum())} attacks)")

    t0 = time.time()
    bootstrap = bootstrap_validation(df, n_iter=30)
    bs_summary = report_bootstrap(bootstrap)
    paired = paired_bootstrap_test(df, n_iter=30)
    kfold = kfold_validation(df, n_splits=5)
    calib = calibration_analysis(df, n_bins=10)
    perm = permutation_importance_analysis(df)
    sanity = sanity_check_random(df)
    elapsed = time.time() - t0

    print("\n" + "=" * 72)
    print("RIGOROUS VALIDATION SUMMARY")
    print("=" * 72)
    print(f"Bootstrap ({bs_summary['n_iter']} splits):")
    for k in ("roc_auc", "pr_auc", "f1", "recall", "precision", "fpr", "brier_score"):
        s = bs_summary[k]
        print(f"  {k:<14} {s['mean']:.4f} +/- {s['std']:.4f}  "
              f"95% CI [{s['ci_low']:.4f}, {s['ci_high']:.4f}]")

    print(f"\nPaired bootstrap (RF vs unknown_ratio):")
    d = paired["roc_auc_delta"]
    print(f"  ROC-AUC delta: {d['mean']:+.4f} +/- {d['std']:.4f}  "
          f"95% CI [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}]  "
          f"P(<=0)={d['p_lt_zero']:.3f}")
    d = paired["pr_auc_delta"]
    print(f"  PR-AUC delta:  {d['mean']:+.4f} +/- {d['std']:.4f}  "
          f"95% CI [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}]  "
          f"P(<=0)={d['p_lt_zero']:.3f}")

    print(f"\n5-fold CV: ROC-AUC = {kfold['roc_auc_mean']:.4f} +/- {kfold['roc_auc_std']:.4f}")
    print(f"           PR-AUC  = {kfold['pr_auc_mean']:.4f} +/- {kfold['pr_auc_std']:.4f}")
    print(f"\nSanity: shuffled-label ROC-AUC = {sanity.get('shuffled_label_roc_auc', 'NA'):.4f} "
          f"(should be near 0.5)")

    print(f"\nTotal validation time: {elapsed:.0f}s")

    report = {
        "n_windows": len(df),
        "n_attacks": int(df["label"].sum()),
        "bootstrap": bs_summary,
        "bootstrap_folds": [asdict(m) for m in bootstrap],
        "paired_bootstrap_vs_unknown_only": paired,
        "kfold_5": kfold,
        "calibration": calib,
        "permutation_importance": perm,
        "sanity_shuffled_labels": sanity,
        "wall_time_sec": elapsed,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
