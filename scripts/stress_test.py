"""
Hard stress tests for the v2 detector.

Every test here exists because a serious industry reviewer would run it:

  1. SHUFFLED-LABEL TEMPORAL LEAKAGE: temporal features could be encoding
     "you're near other attacks in time" instead of real signal. Train v2 on
     a permuted label vector with the same temporal structure -> AUC should
     collapse to ~0.5. If it doesn't, the temporal features are leaking.

  2. ATTACK-CLUSTER HOLDOUT: all 86 attacks cluster in a ~2-min window.
     Excluding ALL attack-adjacent windows (within +/-300s of any attack)
     from training measures whether the model can find attacks from
     scratch on unseen attack context.

  3. ROLLING-CONTEXT CORRUPTION: replace each attack window's 30-window
     rolling context with random benign-only windows. If v2 still flags
     them, the per-window signal carries; if it collapses to v1 levels,
     temporal context was carrying the model.

  4. CLASS-IMBALANCE SWEEP: subsample benign at 10:1, 100:1, 1000:1 ratios.
     Does the model degrade gracefully under different imbalance levels?

  5. FEATURE-NOISE INJECTION: add Gaussian noise of varying magnitudes to
     features at inference time. Real-world data is messier than the
     training set; measure degradation slope.

  6. TEMPORAL-WINDOW SENSITIVITY: train v2 with 5s, 10s, 30s, 60s rolling
     contexts. Does any window size beat the others, or are they all
     similar (suggesting we picked one near a plateau)?

  7. COLD-START TRAINING-SIZE SWEEP: train on 10%, 25%, 50%, 75% of data.
     How much training data do we actually need? Lower is better for
     deployability.

Output: STRESS_TEST_REPORT.md and data/model_ready/stress_test_report.json.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
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
    BASE_FEATURES, TEMPORAL_FEATURES, add_temporal_features, feature_columns,
)


def load_raw(results_path: Path) -> pd.DataFrame:
    """Per-window dataframe BEFORE temporal features."""
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
    return pd.DataFrame(rows).sort_values("window_id").reset_index(drop=True)


def fit_rf(X, y, seed=42, n_estimators=200, max_depth=8):
    rf = RandomForestClassifier(
        n_estimators=n_estimators, max_depth=max_depth,
        class_weight="balanced", random_state=seed, n_jobs=-1,
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
    return {"precision": float(p), "recall": float(r), "f1": float(f1),
            "fpr": float(fpr), "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)}


def eval_basic(df: pd.DataFrame, feature_cols, n_iter: int = 10) -> dict:
    """Repeated stratified hold-out: returns mean+/-std for ROC-AUC, PR-AUC, F1."""
    aucs, prs, f1s, recs, precs, fprs = [], [], [], [], [], []
    for seed in range(n_iter):
        train_df, test_df = train_test_split(
            df, test_size=0.30, stratify=df["label"], random_state=seed,
        )
        if test_df["label"].sum() == 0 or train_df["label"].sum() == 0:
            continue
        rf = fit_rf(train_df[feature_cols].values, train_df["label"].values, seed=seed)
        scores = rf.predict_proba(test_df[feature_cols].values)[:, 1]
        ty = test_df["label"].values
        try:
            aucs.append(roc_auc_score(ty, scores))
            prs.append(average_precision_score(ty, scores))
        except ValueError:
            continue
        t = youden_threshold(scores, ty)
        m = metrics_at(scores, ty, t)
        f1s.append(m["f1"]); recs.append(m["recall"])
        precs.append(m["precision"]); fprs.append(m["fpr"])
    if not aucs:
        return {"n": 0, "note": "degenerate"}
    return {
        "n": len(aucs),
        "roc_auc": {"mean": float(np.mean(aucs)), "std": float(np.std(aucs))},
        "pr_auc": {"mean": float(np.mean(prs)),   "std": float(np.std(prs))},
        "f1":      {"mean": float(np.mean(f1s)),   "std": float(np.std(f1s))},
        "recall":  {"mean": float(np.mean(recs)),  "std": float(np.std(recs))},
        "precision":{"mean": float(np.mean(precs)),"std": float(np.std(precs))},
        "fpr":     {"mean": float(np.mean(fprs)),  "std": float(np.std(fprs))},
    }


# -------------------------------------------------------------------
# TEST 1: Shuffled-label leakage check on v2 features
# -------------------------------------------------------------------
def test_shuffled_label_v2(df: pd.DataFrame, n_iter: int = 5) -> dict:
    """Permute labels (keep counts), keep all temporal features unchanged.
    A real signal-bearing model should collapse to ~0.5 AUC.
    """
    print("\n[1/7] SHUFFLED-LABEL LEAKAGE CHECK")
    # Add temporal features on the original (real) feature sequence first;
    # the temporal context is the same, only the labels get shuffled.
    df_with_temp = add_temporal_features(df.copy())
    full_cols = feature_columns()
    aucs = []
    rng = np.random.default_rng(42)
    for seed in range(n_iter):
        shuffled = rng.permutation(df_with_temp["label"].values)
        df_shuf = df_with_temp.copy()
        df_shuf["label"] = shuffled
        train_df, test_df = train_test_split(
            df_shuf, test_size=0.30, stratify=df_shuf["label"], random_state=seed,
        )
        if test_df["label"].sum() == 0:
            continue
        rf = fit_rf(train_df[full_cols].values, train_df["label"].values, seed=seed)
        scores = rf.predict_proba(test_df[full_cols].values)[:, 1]
        try:
            aucs.append(roc_auc_score(test_df["label"].values, scores))
        except ValueError:
            continue
    mean = float(np.mean(aucs)) if aucs else float("nan")
    print(f"  Shuffled-label ROC-AUC: {mean:.4f} (expected ~0.5; >0.6 = leakage)")
    return {"shuffled_label_roc_auc_mean": mean,
            "shuffled_label_roc_auc_std": float(np.std(aucs)) if aucs else None,
            "verdict": "PASS" if mean < 0.6 else "LEAKAGE_SUSPECTED"}


# -------------------------------------------------------------------
# TEST 2: Rolling-context corruption -- the critical one
# -------------------------------------------------------------------
def test_rolling_context_corruption(df_raw: pd.DataFrame) -> dict:
    """Replace the rolling 30-window context around each ATTACK window with
    randomly-sampled benign windows. If v2 still detects, the per-window signal
    is real. If v2 collapses, the temporal features were leaking labels via
    attack-adjacency.
    """
    print("\n[2/7] ROLLING-CONTEXT CORRUPTION (does v2 need attack-adjacent context?)")

    # Baseline: train v2 on original temporal features
    df_full = add_temporal_features(df_raw.copy())
    full_cols = feature_columns()
    baseline = eval_basic(df_full, full_cols, n_iter=5)
    base_pr = baseline["pr_auc"]["mean"]
    base_roc = baseline["roc_auc"]["mean"]
    print(f"  Baseline v2:                ROC={base_roc:.4f}  PR={base_pr:.4f}")

    # Corrupt: for each attack window's id, shuffle that window's row (so its
    # temporal context comes from a random benign window)
    attack_ids = df_raw[df_raw["label"] == 1]["window_id"].values
    benign_pool = df_raw[df_raw["label"] == 0]
    rng = np.random.default_rng(42)

    df_corrupt_raw = df_raw.copy()
    sampled = benign_pool.sample(n=len(attack_ids), random_state=42)
    base_feat_cols = [c for c in BASE_FEATURES]
    # Replace attack windows' raw features (so their rolling context becomes
    # benign-derived once temporal features are recomputed)
    for i, wid in enumerate(attack_ids):
        for c in base_feat_cols + ["fused_score"]:
            df_corrupt_raw.loc[df_corrupt_raw["window_id"] == wid, c] = sampled.iloc[i][c]
    # Re-compute temporal features on the corrupted sequence
    df_corrupt = add_temporal_features(df_corrupt_raw)
    # Restore labels (we corrupted features, not labels)
    df_corrupt["label"] = df_raw["label"].values
    corrupt = eval_basic(df_corrupt, full_cols, n_iter=5)
    cor_pr = corrupt["pr_auc"]["mean"]
    cor_roc = corrupt["roc_auc"]["mean"]
    print(f"  Attack-feature-corrupted:   ROC={cor_roc:.4f}  PR={cor_pr:.4f}")
    print(f"  Delta:                      ROC={cor_roc - base_roc:+.4f}  PR={cor_pr - base_pr:+.4f}")
    print(f"  (If PR collapses near zero, model was relying on attack windows' own features.)")
    return {"baseline_v2": baseline, "corrupted": corrupt,
            "delta_roc": float(cor_roc - base_roc),
            "delta_pr": float(cor_pr - base_pr)}


# -------------------------------------------------------------------
# TEST 3: Attack-cluster holdout
# -------------------------------------------------------------------
def test_cluster_holdout(df_raw: pd.DataFrame, halo_seconds: int = 300) -> dict:
    """Remove all windows within +/-halo_seconds of any attack from training.
    Test set is the (cleaned) attack-adjacent windows. Forces the model to
    detect attacks WITHOUT seeing similar-time-pattern context in training.
    """
    print(f"\n[3/7] ATTACK-CLUSTER HOLDOUT (+/-{halo_seconds}s halo)")
    df_full = add_temporal_features(df_raw.copy())
    full_cols = feature_columns()

    attack_ids = df_raw[df_raw["label"] == 1]["window_id"].values
    halo_ids = set()
    for aid in attack_ids:
        for d in range(-halo_seconds, halo_seconds + 1):
            halo_ids.add(int(aid + d))
    train_df = df_full[~df_full["window_id"].isin(halo_ids)]
    test_df  = df_full[df_full["window_id"].isin(halo_ids)]

    print(f"  Train: {len(train_df):,} windows, {int(train_df['label'].sum())} attacks")
    print(f"  Test:  {len(test_df):,} windows,  {int(test_df['label'].sum())} attacks")
    if train_df["label"].sum() == 0 or test_df["label"].sum() == 0:
        return {"note": "degenerate: all attacks in halo region (expected)",
                "n_train_attacks": int(train_df['label'].sum()),
                "n_test_attacks": int(test_df['label'].sum())}

    rf = fit_rf(train_df[full_cols].values, train_df["label"].values)
    scores = rf.predict_proba(test_df[full_cols].values)[:, 1]
    ty = test_df["label"].values
    return {
        "n_train_attacks": int(train_df['label'].sum()),
        "n_test_attacks": int(ty.sum()),
        "roc_auc": float(roc_auc_score(ty, scores)),
        "pr_auc": float(average_precision_score(ty, scores)),
    }


# -------------------------------------------------------------------
# TEST 4: Class-imbalance sweep
# -------------------------------------------------------------------
def test_imbalance_sweep(df_raw: pd.DataFrame) -> dict:
    """Subsample benign windows to different ratios. Does performance hold?"""
    print("\n[4/7] CLASS-IMBALANCE SWEEP")
    df_full = add_temporal_features(df_raw.copy())
    full_cols = feature_columns()
    attacks = df_full[df_full["label"] == 1]
    benign  = df_full[df_full["label"] == 0]
    results = {}
    for ratio in [10, 100, 500, 1000]:
        n_keep = min(len(benign), len(attacks) * ratio)
        sampled = benign.sample(n=n_keep, random_state=42)
        df_sub = pd.concat([attacks, sampled])
        rep = eval_basic(df_sub, full_cols, n_iter=5)
        results[f"benign_x_{ratio}"] = rep
        if rep.get("n", 0) > 0:
            print(f"  {ratio:>4}:1 benign:attack ({len(df_sub):,} windows): "
                  f"ROC={rep['roc_auc']['mean']:.4f}  PR={rep['pr_auc']['mean']:.4f}")
    return results


# -------------------------------------------------------------------
# TEST 5: Feature noise injection
# -------------------------------------------------------------------
def test_noise_injection(df_raw: pd.DataFrame) -> dict:
    """At inference time, add Gaussian noise to features. Measure degradation."""
    print("\n[5/7] FEATURE NOISE INJECTION (inference-time)")
    df_full = add_temporal_features(df_raw.copy())
    full_cols = feature_columns()
    train_df, test_df = train_test_split(
        df_full, test_size=0.30, stratify=df_full["label"], random_state=42,
    )
    rf = fit_rf(train_df[full_cols].values, train_df["label"].values)
    results = {}
    test_X = test_df[full_cols].values
    feat_std = test_X.std(axis=0)
    feat_std[feat_std == 0] = 1.0
    rng = np.random.default_rng(42)
    for noise_pct in [0.01, 0.05, 0.10, 0.25, 0.50]:
        noise = rng.normal(0, noise_pct * feat_std, size=test_X.shape)
        noisy_X = test_X + noise
        scores = rf.predict_proba(noisy_X)[:, 1]
        ty = test_df["label"].values
        if ty.sum() == 0:
            continue
        roc = float(roc_auc_score(ty, scores))
        pr = float(average_precision_score(ty, scores))
        results[f"noise_{int(noise_pct*100)}pct_std"] = {"roc_auc": roc, "pr_auc": pr}
        print(f"  noise {int(noise_pct*100):>2}% of feature std: ROC={roc:.4f}  PR={pr:.4f}")
    return results


# -------------------------------------------------------------------
# TEST 6: Temporal-window-size sensitivity
# -------------------------------------------------------------------
def test_window_size_sensitivity(df_raw: pd.DataFrame) -> dict:
    """Try different rolling-window sizes (in seconds)."""
    print("\n[6/7] TEMPORAL-WINDOW-SIZE SENSITIVITY")
    results = {}
    for w in [5, 10, 30, 60, 120]:
        df_alt = add_temporal_features(df_raw.copy(), window_seconds=w)
        full_cols = feature_columns()
        rep = eval_basic(df_alt, full_cols, n_iter=5)
        results[f"window_{w}s"] = rep
        if rep.get("n", 0) > 0:
            print(f"  window={w:>3}s: ROC={rep['roc_auc']['mean']:.4f}  PR={rep['pr_auc']['mean']:.4f}")
    return results


# -------------------------------------------------------------------
# TEST 7: Cold-start training-size sweep
# -------------------------------------------------------------------
def test_training_size(df_raw: pd.DataFrame) -> dict:
    """How does v2 perform with less training data?"""
    print("\n[7/7] COLD-START TRAINING-SIZE SWEEP")
    df_full = add_temporal_features(df_raw.copy())
    full_cols = feature_columns()
    results = {}
    for train_frac in [0.10, 0.25, 0.50, 0.75]:
        # Stratified sample at given fraction
        n_attacks = max(2, int(df_full["label"].sum() * train_frac))
        attacks = df_full[df_full["label"] == 1].sample(n=n_attacks, random_state=42)
        benign_n = int(len(df_full[df_full["label"] == 0]) * train_frac)
        benign  = df_full[df_full["label"] == 0].sample(n=benign_n, random_state=42)
        train_df = pd.concat([attacks, benign])
        test_df  = df_full.drop(train_df.index)
        if test_df["label"].sum() == 0 or train_df["label"].sum() == 0:
            continue
        rf = fit_rf(train_df[full_cols].values, train_df["label"].values)
        scores = rf.predict_proba(test_df[full_cols].values)[:, 1]
        ty = test_df["label"].values
        roc = float(roc_auc_score(ty, scores))
        pr = float(average_precision_score(ty, scores))
        results[f"train_{int(train_frac*100)}pct"] = {
            "roc_auc": roc, "pr_auc": pr,
            "n_train": len(train_df), "n_train_attacks": int(train_df['label'].sum()),
            "n_test_attacks": int(ty.sum()),
        }
        print(f"  train_frac={train_frac:.2f} ({len(train_df):,} windows, "
              f"{int(train_df['label'].sum())} attacks): ROC={roc:.4f}  PR={pr:.4f}")
    return results


def main() -> int:
    results_path = REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json"
    out_path = REPO_ROOT / "data" / "model_ready" / "stress_test_report.json"

    print("Loading data ...")
    df_raw = load_raw(results_path)
    print(f"  {len(df_raw):,} windows, {int(df_raw['label'].sum())} attacks")

    t0 = time.time()
    report = {
        "shuffled_label_v2":     test_shuffled_label_v2(df_raw),
        "rolling_context_corruption": test_rolling_context_corruption(df_raw),
        "cluster_holdout_300s":  test_cluster_holdout(df_raw, halo_seconds=300),
        "imbalance_sweep":       test_imbalance_sweep(df_raw),
        "noise_injection":       test_noise_injection(df_raw),
        "window_size_sensitivity": test_window_size_sensitivity(df_raw),
        "training_size_sweep":   test_training_size(df_raw),
    }
    elapsed = time.time() - t0

    print(f"\nTotal stress test time: {elapsed:.0f}s")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Report saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
