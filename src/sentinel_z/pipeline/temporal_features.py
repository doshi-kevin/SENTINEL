"""
Temporal feature engineering for the Sentinel-Z detector.

Rigorous validation showed our 7 per-window features are redundant - one
signal (unknown_ratio) carries 95%+ of detection. To improve genuinely,
we have to introduce a DIFFERENT KIND of signal.

This module adds rolling-window temporal context. APTs span seconds to
minutes; treating every 1-second window independently throws away most
of the temporal structure. The new features capture:

  - Trend / drift  (current value vs prior 30-window mean)
  - Burst detection (ratio of current to baseline)
  - Persistence (max of any signal sustained over the window)
  - Volatility (rolling std of the signal)

Usage:
    from src.sentinel_z.pipeline.temporal_features import add_temporal_features
    df_extended = add_temporal_features(df_per_window, window_seconds=30)
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


BASE_FEATURES = [
    "unknown_ratio", "num_nodes", "num_edges", "num_subjects",
    "density", "network_ratio", "structural",
]

TEMPORAL_FEATURES = [
    "unknown_ratio_30s_mean",  "unknown_ratio_30s_max",  "unknown_ratio_30s_std",
    "unknown_ratio_30s_delta", "unknown_ratio_30s_burst",
    "num_nodes_30s_mean",      "num_nodes_30s_max",
    "density_30s_mean",        "density_30s_max",
    "network_ratio_30s_max",
    "fused_score_30s_mean",    "fused_score_30s_burst",
    "anomaly_count_30s",
]


def add_temporal_features(df: pd.DataFrame, window_seconds: int = 30,
                          fused_score_col: str = "fused_score",
                          anomaly_threshold: float = 23.0) -> pd.DataFrame:
    """Append rolling temporal-context features to a per-window dataframe.

    The dataframe must contain `window_id` plus the BASE_FEATURES columns and a
    `fused_score` column. Rows are sorted by window_id (1 row == 1 second).
    """
    df = df.sort_values("window_id").reset_index(drop=True).copy()

    rolling = df.rolling(window_seconds, min_periods=1, closed="left")

    df["unknown_ratio_30s_mean"]  = rolling["unknown_ratio"].mean().fillna(0)
    df["unknown_ratio_30s_max"]   = rolling["unknown_ratio"].max().fillna(0)
    df["unknown_ratio_30s_std"]   = rolling["unknown_ratio"].std().fillna(0)
    df["unknown_ratio_30s_delta"] = (df["unknown_ratio"] - df["unknown_ratio_30s_mean"]).fillna(0)
    eps = 1e-6
    df["unknown_ratio_30s_burst"] = (df["unknown_ratio"] / (df["unknown_ratio_30s_mean"] + eps)).clip(0, 100).fillna(1)

    df["num_nodes_30s_mean"] = rolling["num_nodes"].mean().fillna(0)
    df["num_nodes_30s_max"]  = rolling["num_nodes"].max().fillna(0)

    df["density_30s_mean"] = rolling["density"].mean().fillna(0)
    df["density_30s_max"]  = rolling["density"].max().fillna(0)

    df["network_ratio_30s_max"] = rolling["network_ratio"].max().fillna(0)

    if fused_score_col in df.columns:
        df["fused_score_30s_mean"]  = rolling[fused_score_col].mean().fillna(0)
        df["fused_score_30s_burst"] = (df[fused_score_col] /
                                       (df["fused_score_30s_mean"] + eps)).clip(0, 100).fillna(1)
        is_anom = (df[fused_score_col] >= anomaly_threshold).astype(int)
        df["_is_anom_temp"] = is_anom
        df["anomaly_count_30s"] = (
            df["_is_anom_temp"].rolling(window_seconds, min_periods=1, closed="left")
            .sum().fillna(0)
        )
        df = df.drop(columns=["_is_anom_temp"])
    else:
        df["fused_score_30s_mean"]  = 0.0
        df["fused_score_30s_burst"] = 1.0
        df["anomaly_count_30s"]     = 0.0

    return df


def feature_columns() -> list[str]:
    """The full extended feature set (base + temporal) used by the v2 detector."""
    return BASE_FEATURES + TEMPORAL_FEATURES
