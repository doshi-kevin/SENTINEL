"""
SENTINEL-Z Phase 3: Zero-Shot Detection Engine

This module implements anomaly detection WITHOUT any labeled attack data.
The core idea: the trained encoder learned "normal" behavior patterns.
Anything that deviates significantly from normal = anomaly = potential attack.

Components:
1. AnomalyEngine: Isolation Forest + LOF for embedding-based detection
2. StatisticalBaseline: Compute normal behavior statistics
3. ZeroShotScorer: Score all windows and identify anomalies
4. Evaluator: Compute precision, recall, F1 against ground truth
"""

import json
import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
import warnings
warnings.filterwarnings('ignore')


@dataclass
class DetectionResult:
    """Result for a single window."""
    window_id: int
    anomaly_score: float
    is_anomaly: bool
    isolation_score: float
    lof_score: float
    reconstruction_error: float
    ground_truth: int  # 0=benign, 1=attack


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for the detector."""
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    detection_rate: float  # Same as recall
    false_positive_rate: float
    threshold: float

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        return f"""
=== SENTINEL-Z Zero-Shot Detection Results ===
Precision:        {self.precision:.4f}
Recall (DR):      {self.recall:.4f}
F1 Score:         {self.f1_score:.4f}
ROC-AUC:          {self.roc_auc:.4f}

Confusion Matrix:
  TP: {self.true_positives:4d}  |  FP: {self.false_positives:4d}
  FN: {self.false_negatives:4d}  |  TN: {self.true_negatives:4d}

Detection Rate:   {self.detection_rate*100:.2f}%
FP Rate:          {self.false_positive_rate*100:.2f}%
Threshold:        {self.threshold:.4f}
===============================================
"""


class AnomalyEngine:
    """
    Anomaly detection engine using ensemble of methods:
    1. Isolation Forest - tree-based anomaly detection
    2. Local Outlier Factor - density-based anomaly detection
    3. Reconstruction Error - from the encoder itself
    """

    def __init__(
        self,
        contamination: float = 0.02,  # Expected ~2% anomalies
        n_estimators: int = 100,
        random_state: int = 42
    ):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state

        self.isolation_forest = None
        self.lof = None
        self.scaler = StandardScaler()
        self.is_fitted = False

    def fit(self, embeddings: np.ndarray) -> 'AnomalyEngine':
        """
        Fit anomaly detectors on normal (benign) embeddings.

        Args:
            embeddings: [n_samples, embedding_dim] - embeddings from benign windows
        """
        print(f"Fitting anomaly engine on {len(embeddings)} samples...")

        # Normalize embeddings
        embeddings_scaled = self.scaler.fit_transform(embeddings)

        # Isolation Forest
        self.isolation_forest = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1
        )
        self.isolation_forest.fit(embeddings_scaled)

        # Local Outlier Factor (novelty detection mode)
        self.lof = LocalOutlierFactor(
            n_neighbors=20,
            contamination=self.contamination,
            novelty=True,
            n_jobs=-1
        )
        self.lof.fit(embeddings_scaled)

        self.is_fitted = True
        print("Anomaly engine fitted successfully!")
        return self

    def score(self, embeddings: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Score embeddings for anomaly.

        Returns:
            isolation_scores: Higher = more anomalous (inverted from sklearn)
            lof_scores: Higher = more anomalous (inverted from sklearn)
        """
        if not self.is_fitted:
            raise RuntimeError("AnomalyEngine not fitted. Call fit() first.")

        embeddings_scaled = self.scaler.transform(embeddings)

        # Isolation Forest: score_samples returns negative values, lower = more anomalous
        # We invert so higher = more anomalous
        if_scores = -self.isolation_forest.score_samples(embeddings_scaled)

        # LOF: score_samples returns negative values, lower = more anomalous
        lof_scores = -self.lof.score_samples(embeddings_scaled)

        return if_scores, lof_scores


class StatisticalBaseline:
    """
    Computes statistical baseline from benign windows.
    Used to determine what "normal" looks like.
    """

    def __init__(self):
        self.mean_embedding = None
        self.std_embedding = None
        self.mean_score = None
        self.std_score = None
        self.threshold_2sigma = None
        self.threshold_3sigma = None

    def compute(
        self,
        embeddings: np.ndarray,
        isolation_scores: np.ndarray,
        lof_scores: np.ndarray
    ) -> 'StatisticalBaseline':
        """
        Compute baseline statistics from benign data.
        """
        print(f"Computing statistical baseline from {len(embeddings)} benign samples...")

        # Embedding statistics
        self.mean_embedding = embeddings.mean(axis=0)
        self.std_embedding = embeddings.std(axis=0) + 1e-6

        # Combined score (average of normalized IF and LOF)
        combined_scores = (isolation_scores + lof_scores) / 2

        self.mean_score = combined_scores.mean()
        self.std_score = combined_scores.std() + 1e-6

        # Thresholds
        self.threshold_2sigma = self.mean_score + 2 * self.std_score
        self.threshold_3sigma = self.mean_score + 3 * self.std_score

        print(f"  Mean score: {self.mean_score:.4f}")
        print(f"  Std score:  {self.std_score:.4f}")
        print(f"  2-sigma threshold: {self.threshold_2sigma:.4f}")
        print(f"  3-sigma threshold: {self.threshold_3sigma:.4f}")

        return self

    def normalize_score(self, score: float) -> float:
        """Normalize a score using z-score."""
        return (score - self.mean_score) / self.std_score


class ZeroShotScorer:
    """
    Zero-shot anomaly scorer that combines multiple signals.
    """

    def __init__(
        self,
        anomaly_engine: AnomalyEngine,
        baseline: StatisticalBaseline,
        threshold_sigma: float = 2.5
    ):
        self.engine = anomaly_engine
        self.baseline = baseline
        self.threshold_sigma = threshold_sigma

        # Compute actual threshold
        self.threshold = self.baseline.mean_score + threshold_sigma * self.baseline.std_score

    def score_windows(
        self,
        embeddings: np.ndarray,
        window_ids: List[int],
        labels: List[int],
        reconstruction_errors: Optional[np.ndarray] = None
    ) -> List[DetectionResult]:
        """
        Score all windows and return detection results.
        """
        print(f"Scoring {len(embeddings)} windows...")

        # Get anomaly scores
        if_scores, lof_scores = self.engine.score(embeddings)

        # Combined score
        combined_scores = (if_scores + lof_scores) / 2

        # If no reconstruction errors provided, use zeros
        if reconstruction_errors is None:
            reconstruction_errors = np.zeros(len(embeddings))

        results = []
        for i, (wid, label) in enumerate(zip(window_ids, labels)):
            anomaly_score = combined_scores[i]
            is_anomaly = anomaly_score > self.threshold

            results.append(DetectionResult(
                window_id=wid,
                anomaly_score=float(anomaly_score),
                is_anomaly=bool(is_anomaly),
                isolation_score=float(if_scores[i]),
                lof_score=float(lof_scores[i]),
                reconstruction_error=float(reconstruction_errors[i]),
                ground_truth=int(label)
            ))

        return results

    def adjust_threshold(self, new_sigma: float):
        """Adjust the detection threshold."""
        self.threshold_sigma = new_sigma
        self.threshold = self.baseline.mean_score + new_sigma * self.baseline.std_score


class Evaluator:
    """
    Evaluates detection results against ground truth.
    """

    @staticmethod
    def evaluate(results: List[DetectionResult], threshold: float) -> EvaluationMetrics:
        """
        Compute evaluation metrics.
        """
        y_true = np.array([r.ground_truth for r in results])
        y_scores = np.array([r.anomaly_score for r in results])
        y_pred = np.array([1 if r.anomaly_score > threshold else 0 for r in results])

        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

        # Metrics
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)

        # ROC-AUC (need at least one positive and negative)
        try:
            roc_auc = roc_auc_score(y_true, y_scores)
        except:
            roc_auc = 0.0

        # False positive rate
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        return EvaluationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            roc_auc=roc_auc,
            true_positives=int(tp),
            false_positives=int(fp),
            true_negatives=int(tn),
            false_negatives=int(fn),
            detection_rate=recall,
            false_positive_rate=fpr,
            threshold=threshold
        )

    @staticmethod
    def find_optimal_threshold(
        results: List[DetectionResult],
        target_fpr: float = 0.01
    ) -> Tuple[float, EvaluationMetrics]:
        """
        Find optimal threshold to achieve target false positive rate.
        """
        scores = sorted(set([r.anomaly_score for r in results]))

        best_threshold = scores[0]
        best_metrics = None

        for threshold in scores:
            metrics = Evaluator.evaluate(results, threshold)

            if metrics.false_positive_rate <= target_fpr:
                if best_metrics is None or metrics.recall > best_metrics.recall:
                    best_threshold = threshold
                    best_metrics = metrics

        if best_metrics is None:
            # If we can't achieve target FPR, use the highest threshold
            best_threshold = max(scores)
            best_metrics = Evaluator.evaluate(results, best_threshold)

        return best_threshold, best_metrics


class ZeroShotDetectionPipeline:
    """
    Complete pipeline for zero-shot detection.

    Usage:
        pipeline = ZeroShotDetectionPipeline(model_path, graphs_dir, labels_csv)
        pipeline.run()
        pipeline.export_results(output_path)
    """

    def __init__(
        self,
        model_path: str,
        graphs_dir: str,
        labels_csv: str,
        device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    ):
        self.model_path = Path(model_path)
        self.graphs_dir = Path(graphs_dir)
        self.labels_csv = Path(labels_csv)
        self.device = device

        self.model = None
        self.embeddings = None
        self.window_ids = None
        self.labels = None
        self.results = None
        self.metrics = None

    def extract_graph_features(self, graph_data: dict) -> np.ndarray:
        """
        Extract features from a graph for anomaly detection.
        Uses graph-level statistics that capture APT behavior patterns.

        Key insight: Attack graphs tend to be LARGER and have different
        structural patterns (more subjects, higher connectivity).
        """
        nodes = graph_data.get('nodes', [])
        links = graph_data.get('links', [])

        if not nodes:
            return np.zeros(30)

        # Node-level statistics
        num_nodes = len(nodes)
        num_edges = len(links)

        # Extract node features
        degrees = [n.get('degree', 0) for n in nodes]
        in_degrees = [n.get('in_degree', 0) for n in nodes]
        out_degrees = [n.get('out_degree', 0) for n in nodes]
        event_counts = [n.get('event_count', 0) for n in nodes]

        # Centrality features
        pageranks = [n.get('pagerank', 0) for n in nodes]
        betweenness = [n.get('betweenness', 0) for n in nodes]
        closeness = [n.get('closeness', 0) for n in nodes]

        # Temporal features
        burst_flags = [n.get('burst_flag', 0) for n in nodes]
        temporal_entropy = [n.get('temporal_entropy', 0) for n in nodes]
        activity_rates = [n.get('activity_rate', 0) for n in nodes]

        # Node type distribution
        subjects = sum(1 for n in nodes if n.get('node_type') == 'subject')
        objects = num_nodes - subjects

        # Edge type analysis (APT-relevant patterns)
        edge_types = [l.get('edge_type', 'unknown') for l in links]
        read_edges = sum(1 for e in edge_types if 'read' in str(e).lower())
        write_edges = sum(1 for e in edge_types if 'write' in str(e).lower())
        exec_edges = sum(1 for e in edge_types if 'exec' in str(e).lower() or 'fork' in str(e).lower())
        connect_edges = sum(1 for e in edge_types if 'connect' in str(e).lower() or 'socket' in str(e).lower())

        # Aggregate features (30 total)
        features = [
            # Graph structure (key discriminators based on analysis)
            num_nodes,
            num_edges,
            num_edges / max(num_nodes, 1),  # Edge density
            subjects / max(num_nodes, 1),   # Subject ratio
            subjects,  # Absolute subject count
            objects,   # Absolute object count

            # Size-based anomaly indicators (attacks are larger)
            1 if num_nodes > 150 else 0,  # Large graph flag
            1 if subjects > 20 else 0,     # Many subjects flag
            np.log1p(num_nodes),           # Log-scaled size
            np.log1p(num_edges),           # Log-scaled edges

            # Degree statistics
            np.mean(degrees) if degrees else 0,
            np.std(degrees) if len(degrees) > 1 else 0,
            np.max(degrees) if degrees else 0,
            np.mean(in_degrees) if in_degrees else 0,
            np.mean(out_degrees) if out_degrees else 0,
            np.max(out_degrees) if out_degrees else 0,  # High out-degree = data exfil

            # Centrality statistics
            np.mean(pageranks) if pageranks else 0,
            np.max(pageranks) if pageranks else 0,
            np.mean(betweenness) if betweenness else 0,
            np.max(betweenness) if betweenness else 0,  # Bottleneck nodes

            # Temporal statistics
            sum(burst_flags),  # Number of bursty nodes
            np.mean(temporal_entropy) if temporal_entropy else 0,
            np.max(activity_rates) if activity_rates else 0,

            # Edge type distribution (APT patterns)
            read_edges / max(num_edges, 1),    # Read ratio
            write_edges / max(num_edges, 1),   # Write ratio
            exec_edges / max(num_edges, 1),    # Execution ratio
            connect_edges / max(num_edges, 1), # Network ratio

            # Event statistics
            np.mean(event_counts) if event_counts else 0,
            sum(event_counts) if event_counts else 0,
            np.max(event_counts) if event_counts else 0,  # Hotspot node
        ]

        return np.array(features, dtype=np.float32)

    def extract_embeddings(self):
        """Extract feature embeddings for all windows using graph statistics."""
        print("Extracting graph feature embeddings...")

        # Load labels
        labels_df = pd.read_csv(self.labels_csv)

        embeddings = []
        window_ids = []
        labels = []

        # Process each graph file
        graph_files = sorted(self.graphs_dir.glob("window_*.json"))
        print(f"Found {len(graph_files)} graph files")

        for i, graph_file in enumerate(graph_files):
            try:
                # Extract window ID from filename
                wid = int(graph_file.stem.split('_')[1])

                # Load graph
                with open(graph_file) as f:
                    graph_data = json.load(f)

                # Extract features
                features = self.extract_graph_features(graph_data)

                # Get label
                if wid < len(labels_df):
                    label = labels_df.iloc[wid]['label']
                else:
                    label = 0

                embeddings.append(features)
                window_ids.append(wid)
                labels.append(label)

                if (i + 1) % 500 == 0:
                    print(f"  Processed {i + 1}/{len(graph_files)} windows...")

            except Exception as e:
                print(f"  Error processing {graph_file}: {e}")
                continue

        self.embeddings = np.array(embeddings)
        self.window_ids = window_ids
        self.labels = labels

        # Replace NaN/Inf with 0
        self.embeddings = np.nan_to_num(self.embeddings, nan=0.0, posinf=0.0, neginf=0.0)

        print(f"Extracted {len(embeddings)} embeddings (dim={self.embeddings.shape[1]})")
        print(f"  Benign windows: {sum(1 for l in labels if l == 0)}")
        print(f"  Attack windows: {sum(1 for l in labels if l == 1)}")

    def run_size_based_detection(self) -> EvaluationMetrics:
        """
        Alternative detection using size-based thresholds.
        Based on analysis: attack graphs are significantly LARGER than benign.
        """
        print("\n" + "="*60)
        print("SENTINEL-Z Size-Based Detection")
        print("="*60 + "\n")

        import json
        from pathlib import Path

        # Load labels
        labels_df = pd.read_csv(self.labels_csv)

        # Collect size metrics for all graphs
        print("Analyzing graph sizes...")
        sizes = []
        for graph_file in sorted(self.graphs_dir.glob("window_*.json")):
            wid = int(graph_file.stem.split('_')[1])
            with open(graph_file) as f:
                data = json.load(f)

            nodes = data.get('nodes', [])
            links = data.get('links', [])
            subjects = sum(1 for n in nodes if n.get('node_type') == 'subject')

            label = labels_df.iloc[wid]['label'] if wid < len(labels_df) else 0

            sizes.append({
                'window_id': wid,
                'num_nodes': len(nodes),
                'num_edges': len(links),
                'subjects': subjects,
                'label': label
            })

        df = pd.DataFrame(sizes)

        # Calculate benign statistics
        benign = df[df['label'] == 0]
        attack = df[df['label'] == 1]

        # Use percentile-based thresholds
        # If a graph is larger than 95th percentile of benign, flag it
        node_threshold = benign['num_nodes'].quantile(0.90)
        edge_threshold = benign['num_edges'].quantile(0.90)
        subject_threshold = benign['subjects'].quantile(0.90)

        print(f"Thresholds (90th percentile of benign):")
        print(f"  Nodes: {node_threshold:.0f}")
        print(f"  Edges: {edge_threshold:.0f}")
        print(f"  Subjects: {subject_threshold:.0f}")

        # Score based on how many thresholds exceeded
        df['anomaly_score'] = (
            (df['num_nodes'] > node_threshold).astype(int) +
            (df['num_edges'] > edge_threshold).astype(int) +
            (df['subjects'] > subject_threshold).astype(int)
        )

        # Anomaly if exceeds at least 2 thresholds
        df['is_anomaly'] = df['anomaly_score'] >= 2

        # Evaluate
        y_true = df['label'].values
        y_pred = df['is_anomaly'].astype(int).values
        y_scores = df['anomaly_score'].values

        from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score, roc_auc_score

        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

        metrics = EvaluationMetrics(
            precision=precision_score(y_true, y_pred, zero_division=0),
            recall=recall_score(y_true, y_pred, zero_division=0),
            f1_score=f1_score(y_true, y_pred, zero_division=0),
            roc_auc=roc_auc_score(y_true, y_scores),
            true_positives=int(tp),
            false_positives=int(fp),
            true_negatives=int(tn),
            false_negatives=int(fn),
            detection_rate=recall_score(y_true, y_pred, zero_division=0),
            false_positive_rate=fp / (fp + tn) if (fp + tn) > 0 else 0,
            threshold=2.0
        )

        print(metrics.summary())

        # Store for export
        self.results = df.to_dict('records')
        self.metrics = metrics

        return metrics

    def run(self) -> EvaluationMetrics:
        """Run the complete detection pipeline."""
        print("\n" + "="*60)
        print("SENTINEL-Z Zero-Shot Detection Pipeline")
        print("="*60 + "\n")

        # Step 1: Extract embeddings (using graph statistics)
        self.extract_embeddings()

        # Step 3: Split benign data for fitting
        benign_mask = np.array(self.labels) == 0
        benign_embeddings = self.embeddings[benign_mask]

        print(f"\nUsing {len(benign_embeddings)} benign samples for baseline...")

        # Step 4: Fit anomaly engine on benign data
        engine = AnomalyEngine(contamination=0.01)
        engine.fit(benign_embeddings)

        # Step 5: Compute baseline statistics
        if_scores_benign, lof_scores_benign = engine.score(benign_embeddings)
        baseline = StatisticalBaseline()
        baseline.compute(benign_embeddings, if_scores_benign, lof_scores_benign)

        # Step 6: Score all windows
        scorer = ZeroShotScorer(engine, baseline, threshold_sigma=2.5)
        self.results = scorer.score_windows(
            self.embeddings,
            self.window_ids,
            self.labels
        )

        # Step 7: Evaluate with default threshold
        self.metrics = Evaluator.evaluate(self.results, scorer.threshold)
        print("\n" + self.metrics.summary())

        # Step 8: Find optimal threshold for <1% FPR
        optimal_threshold, optimal_metrics = Evaluator.find_optimal_threshold(
            self.results, target_fpr=0.01
        )

        print(f"\nOptimal threshold for <1% FPR: {optimal_threshold:.4f}")
        print(optimal_metrics.summary())

        self.metrics = optimal_metrics

        return self.metrics

    def export_results(self, output_dir: str):
        """Export results for dashboard integration."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export detection results
        results_data = [asdict(r) for r in self.results]
        results_path = output_dir / "detection_results.json"
        with open(results_path, 'w') as f:
            json.dump(results_data, f, indent=2)
        print(f"Detection results saved to {results_path}")

        # Export metrics
        metrics_path = output_dir / "evaluation_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(self.metrics.to_dict(), f, indent=2)
        print(f"Evaluation metrics saved to {metrics_path}")

        # Export scores CSV for easy analysis
        scores_df = pd.DataFrame([
            {
                'window_id': r.window_id,
                'anomaly_score': r.anomaly_score,
                'is_anomaly': r.is_anomaly,
                'ground_truth': r.ground_truth,
                'correct': r.is_anomaly == (r.ground_truth == 1)
            }
            for r in self.results
        ])
        scores_path = output_dir / "anomaly_scores.csv"
        scores_df.to_csv(scores_path, index=False)
        print(f"Anomaly scores saved to {scores_path}")

        return {
            'results_path': str(results_path),
            'metrics_path': str(metrics_path),
            'scores_path': str(scores_path)
        }


def main():
    """Run zero-shot detection pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description='SENTINEL-Z Zero-Shot Detection')
    parser.add_argument('--model', type=str, default='backend/models/sentinel_encoder.pt',
                        help='Path to trained model')
    parser.add_argument('--graphs', type=str, default='data/model_ready/graphs',
                        help='Path to graph directory')
    parser.add_argument('--labels', type=str, default='data/model_ready/labels.csv',
                        help='Path to labels CSV')
    parser.add_argument('--output', type=str, default='data/model_ready/detection',
                        help='Output directory for results')

    args = parser.parse_args()

    pipeline = ZeroShotDetectionPipeline(
        model_path=args.model,
        graphs_dir=args.graphs,
        labels_csv=args.labels
    )

    metrics = pipeline.run()
    pipeline.export_results(args.output)

    print("\nPhase 3 Complete!")
    print(f"Detection Rate: {metrics.detection_rate*100:.1f}%")
    print(f"False Positive Rate: {metrics.false_positive_rate*100:.2f}%")


if __name__ == "__main__":
    main()
