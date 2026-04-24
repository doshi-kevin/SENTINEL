"""
Random Forest Detector - primary anomaly detector for Sentinel-Z.

Honest rationale: in rigorous stratified 70/15/15 validation on DARPA TC E5,
a Random Forest on the exact same features as the semantic fusion engine
achieves Test ROC-AUC 0.9577 vs the fusion's 0.7914 (see
scripts/validate_phase4.py output). We use RF as the primary detector and
keep the semantic risk engine for explainability only.

Persistence uses joblib (sklearn standard). NOTE: joblib deserialization is
NOT safe on untrusted input. Only load model files you produced yourself
or obtained from a trusted distribution channel with integrity checks.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, confusion_matrix
from sklearn.model_selection import train_test_split
import joblib


FEATURE_COLUMNS: List[str] = [
    "num_nodes", "num_edges", "num_subjects", "density",
    "unknown_ratio", "network_ratio", "structural",
]


@dataclass
class DetectionResult:
    """Per-window detection output from the RF detector."""
    window_id: int
    anomaly_score: float
    is_anomaly: bool
    threshold: float
    top_features: Dict[str, float]


@dataclass
class ModelCard:
    """Honest metadata about the trained detector."""
    roc_auc_test: float
    precision_test: float
    recall_test: float
    f1_test: float
    fpr_test: float
    threshold: float
    feature_importances: Dict[str, float]
    n_train: int
    n_val: int
    n_test: int
    n_attacks_test: int
    trained_on: str
    limitations: List[str]
    model_version: str = "1.0.0"

    def to_dict(self) -> dict:
        return asdict(self)


class RFDetector:
    """Random Forest detector - the PRIMARY Sentinel-Z detection engine."""

    def __init__(self, n_estimators: int = 200, max_depth: int = 8,
                 class_weight: str = "balanced", random_state: int = 42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.class_weight = class_weight
        self.random_state = random_state
        self.model: Optional[RandomForestClassifier] = None
        self.threshold: float = 0.5
        self.model_card: Optional[ModelCard] = None
        self.feature_names = FEATURE_COLUMNS

    def fit(self, features_df: pd.DataFrame,
            labels: np.ndarray,
            val_size: float = 0.15,
            test_size: float = 0.15,
            threshold_objective: str = "f1") -> ModelCard:
        """Train with stratified train/val/test split; return an honest model card.

        Threshold is chosen on val; metrics reported are from held-out test.
        """
        X = features_df[self.feature_names].values
        y = labels

        trainval_X, test_X, trainval_y, test_y = train_test_split(
            X, y, test_size=test_size, stratify=y, random_state=self.random_state,
        )
        val_rel = val_size / (1.0 - test_size)
        train_X, val_X, train_y, val_y = train_test_split(
            trainval_X, trainval_y, test_size=val_rel, stratify=trainval_y,
            random_state=self.random_state,
        )

        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            class_weight=self.class_weight,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.model.fit(train_X, train_y)

        val_scores = self.model.predict_proba(val_X)[:, 1]
        self.threshold = self._pick_threshold(val_scores, val_y, threshold_objective)

        test_scores = self.model.predict_proba(test_X)[:, 1]
        test_preds = (test_scores >= self.threshold).astype(int)

        try:
            roc_auc_val = float(roc_auc_score(test_y, test_scores))
        except ValueError:
            roc_auc_val = float("nan")

        tn, fp, fn, tp = confusion_matrix(test_y, test_preds, labels=[0, 1]).ravel()
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        importances = dict(zip(self.feature_names,
                               [float(v) for v in self.model.feature_importances_]))

        self.model_card = ModelCard(
            roc_auc_test=roc_auc_val,
            precision_test=float(precision),
            recall_test=float(recall),
            f1_test=float(f1),
            fpr_test=float(fpr),
            threshold=float(self.threshold),
            feature_importances=importances,
            n_train=len(train_y),
            n_val=len(val_y),
            n_test=len(test_y),
            n_attacks_test=int(test_y.sum()),
            trained_on="DARPA TC E5 FiveDirections (smoke subset: files 1-2)",
            limitations=[
                "Trained on a single campaign (E5 FiveDirections) - generalization to other "
                "teams (THEIA, TRACE, CADETS) or engagements (E3, E4) is UNVERIFIED.",
                "All 86 attacks cluster in a 2-minute window; stratified (not temporal) split "
                "means this measures discrimination, not temporal robustness.",
                "Small attack sample size (~86 windows) limits statistical power.",
                "Features derived from 1-second graph windows; multi-step APTs spanning "
                "minutes/hours are not captured by this model alone.",
            ],
        )
        return self.model_card

    def _pick_threshold(self, scores: np.ndarray, labels: np.ndarray,
                        objective: str = "f1") -> float:
        if labels.sum() == 0:
            return float(np.percentile(scores, 95))
        candidates = np.unique(np.concatenate([scores, np.percentile(scores, np.arange(50, 100, 0.5))]))
        best_t, best_score = candidates[0], -1.0
        for t in candidates:
            preds = (scores >= t).astype(int)
            tn, fp, fn, tp = confusion_matrix(labels, preds, labels=[0, 1]).ravel()
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            if objective == "f1":
                s = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
            elif objective == "youden":
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
                s = r - fpr
            else:
                raise ValueError(f"unknown objective: {objective}")
            if s > best_score:
                best_score, best_t = s, t
        return float(best_t)

    def predict(self, features_df: pd.DataFrame) -> List[DetectionResult]:
        if self.model is None:
            raise RuntimeError("Model not fitted. Call fit() or load() first.")

        X = features_df[self.feature_names].values
        scores = self.model.predict_proba(X)[:, 1]
        preds = (scores >= self.threshold).astype(int)
        importances = dict(zip(self.feature_names, self.model.feature_importances_))

        results = []
        window_ids = (features_df["window_id"].values
                      if "window_id" in features_df.columns else np.arange(len(features_df)))
        for i, (wid, score, pred) in enumerate(zip(window_ids, scores, preds)):
            row = features_df.iloc[i]
            top_feats = self._top_contributors(row, importances, n=3)
            results.append(DetectionResult(
                window_id=int(wid),
                anomaly_score=float(score),
                is_anomaly=bool(pred),
                threshold=float(self.threshold),
                top_features=top_feats,
            ))
        return results

    def _top_contributors(self, row: pd.Series,
                          importances: Dict[str, float], n: int = 3) -> Dict[str, float]:
        """Return top-N features by (value * importance). Used by narrative layer."""
        contribs = {}
        for feat, imp in importances.items():
            if feat in row.index:
                val = float(row[feat])
                contribs[feat] = val * imp
        sorted_feats = sorted(contribs.items(), key=lambda kv: abs(kv[1]), reverse=True)
        return dict(sorted_feats[:n])

    def save(self, path: str) -> None:
        """Persist with joblib + integrity checksum. NOT safe on untrusted input."""
        if self.model is None:
            raise RuntimeError("No model to save.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump({
            "model": self.model,
            "threshold": self.threshold,
            "feature_names": self.feature_names,
            "model_card": self.model_card.to_dict() if self.model_card else None,
        }, path)

        h = hashlib.sha256(path.read_bytes()).hexdigest()
        (path.parent / f"{path.name}.sha256").write_text(h)

        if self.model_card:
            (path.parent / "model_card.json").write_text(
                json.dumps(self.model_card.to_dict(), indent=2)
            )

    @classmethod
    def load(cls, path: str, verify_checksum: bool = True) -> "RFDetector":
        """Load a trained detector. If verify_checksum, check sha256 sidecar."""
        path = Path(path)
        if verify_checksum:
            sidecar = path.parent / f"{path.name}.sha256"
            if sidecar.exists():
                expected = sidecar.read_text().strip()
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if expected != actual:
                    raise RuntimeError(f"Checksum mismatch for {path}: refusing to load.")

        payload = joblib.load(path)
        det = cls()
        det.model = payload["model"]
        det.threshold = payload["threshold"]
        det.feature_names = payload["feature_names"]
        card = payload.get("model_card")
        if card:
            det.model_card = ModelCard(**card)
        return det
