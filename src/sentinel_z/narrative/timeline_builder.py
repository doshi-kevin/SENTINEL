"""
Unified Timeline Builder

Creates a comprehensive timeline view of ALL windows for attack visualization.
This addresses your requirement: "map all windows at once for better visualization
of how the attack is happening through the data."

Key Features:
1. Aggregate statistics across all windows
2. Attack progression visualization data
3. Semantic flow evolution over time
4. Anomaly score timeline
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from ..detection.semantic_graph import SemanticGraph, SemanticGraphTransformer
from ..detection.semantic_resolver import SemanticResolver, SemanticEntityType, SemanticEdgeType


@dataclass
class TimelineWindow:
    """A single window in the timeline."""
    window_id: int
    start_time: str
    end_time: str
    label: int  # 0=benign, 1=attack

    # Graph metrics
    num_nodes: int = 0
    num_edges: int = 0

    # Semantic distribution
    semantic_node_types: Dict[str, int] = field(default_factory=dict)
    semantic_edge_types: Dict[str, int] = field(default_factory=dict)

    # Anomaly metrics
    anomaly_score: float = 0.0
    anomalous_flows: List[str] = field(default_factory=list)

    # Attack stage (if detected)
    attack_stage: str = "benign"

    def to_dict(self) -> dict:
        return {
            'window_id': self.window_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'label': self.label,
            'num_nodes': self.num_nodes,
            'num_edges': self.num_edges,
            'semantic_node_types': self.semantic_node_types,
            'semantic_edge_types': self.semantic_edge_types,
            'anomaly_score': self.anomaly_score,
            'anomalous_flows': self.anomalous_flows,
            'attack_stage': self.attack_stage
        }


@dataclass
class AttackProgression:
    """Represents the progression of an attack across multiple windows."""
    start_window: int
    end_window: int
    duration_seconds: float
    stages: List[Dict]  # List of {window_id, stage, evidence}
    peak_anomaly_window: int
    peak_anomaly_score: float
    total_affected_nodes: int
    total_events: int

    def to_dict(self) -> dict:
        return {
            'start_window': self.start_window,
            'end_window': self.end_window,
            'duration_seconds': self.duration_seconds,
            'stages': self.stages,
            'peak_anomaly_window': self.peak_anomaly_window,
            'peak_anomaly_score': self.peak_anomaly_score,
            'total_affected_nodes': self.total_affected_nodes,
            'total_events': self.total_events
        }


class UnifiedTimeline:
    """
    Unified view of all windows with attack progression analysis.
    """

    def __init__(self):
        self.windows: List[TimelineWindow] = []
        self.attack_progressions: List[AttackProgression] = []
        self.normal_flow_baseline: Dict[str, float] = {}

    def add_window(self, window: TimelineWindow) -> None:
        self.windows.append(window)

    def build_normal_baseline(self) -> Dict[str, float]:
        """
        Build baseline of normal semantic flows from benign windows.
        This is used for zero-shot anomaly detection.
        """
        flow_counts = defaultdict(int)
        total_benign = 0

        for window in self.windows:
            if window.label == 0:  # Benign
                total_benign += 1
                # We'll need semantic graphs to compute flows
                # For now, use semantic edge type distribution
                for edge_type, count in window.semantic_edge_types.items():
                    flow_counts[edge_type] += count

        if total_benign > 0:
            self.normal_flow_baseline = {
                k: v / total_benign for k, v in flow_counts.items()
            }

        return self.normal_flow_baseline

    def detect_attack_progressions(self) -> List[AttackProgression]:
        """
        Detect and characterize attack progressions in the timeline.
        Groups consecutive attack windows and identifies stages.
        """
        self.attack_progressions = []
        current_attack = None

        for window in sorted(self.windows, key=lambda w: w.window_id):
            if window.label == 1:  # Attack window
                if current_attack is None:
                    current_attack = {
                        'start': window.window_id,
                        'end': window.window_id,
                        'windows': [window],
                        'peak_score': window.anomaly_score,
                        'peak_window': window.window_id
                    }
                else:
                    current_attack['end'] = window.window_id
                    current_attack['windows'].append(window)
                    if window.anomaly_score > current_attack['peak_score']:
                        current_attack['peak_score'] = window.anomaly_score
                        current_attack['peak_window'] = window.window_id
            else:
                if current_attack is not None:
                    # Finalize attack progression
                    progression = self._create_progression(current_attack)
                    self.attack_progressions.append(progression)
                    current_attack = None

        # Handle attack at end of timeline
        if current_attack is not None:
            progression = self._create_progression(current_attack)
            self.attack_progressions.append(progression)

        return self.attack_progressions

    def _create_progression(self, attack_data: Dict) -> AttackProgression:
        """Create AttackProgression from collected attack data."""
        windows = attack_data['windows']

        # Calculate duration
        start_time = pd.to_datetime(windows[0].start_time)
        end_time = pd.to_datetime(windows[-1].end_time)
        duration = (end_time - start_time).total_seconds()

        # Identify stages based on semantic patterns
        stages = []
        for window in windows:
            stage = self._classify_attack_stage(window)
            stages.append({
                'window_id': window.window_id,
                'stage': stage,
                'evidence': window.anomalous_flows[:3]  # Top 3 anomalies
            })

        # Aggregate metrics
        total_nodes = sum(w.num_nodes for w in windows)
        total_events = sum(w.num_edges for w in windows)

        return AttackProgression(
            start_window=attack_data['start'],
            end_window=attack_data['end'],
            duration_seconds=duration,
            stages=stages,
            peak_anomaly_window=attack_data['peak_window'],
            peak_anomaly_score=attack_data['peak_score'],
            total_affected_nodes=total_nodes,
            total_events=total_events
        )

    def _classify_attack_stage(self, window: TimelineWindow) -> str:
        """
        Classify the attack stage based on semantic patterns.

        Attack Kill Chain Stages:
        1. Reconnaissance - scanning, discovery
        2. Initial Access - first execution
        3. Execution - running malicious code
        4. Persistence - establishing foothold
        5. Privilege Escalation - gaining higher access
        6. Defense Evasion - hiding activity
        7. Credential Access - stealing credentials
        8. Discovery - internal reconnaissance
        9. Lateral Movement - spreading
        10. Collection - gathering data
        11. Exfiltration - sending data out
        12. Impact - damage/disruption
        """
        node_types = window.semantic_node_types
        edge_types = window.semantic_edge_types

        # Simple heuristic classification
        reads = edge_types.get('reads_from', 0)
        writes = edge_types.get('writes_to', 0)
        executes = edge_types.get('executes', 0)
        spawns = edge_types.get('spawns', 0)
        connects = edge_types.get('connects_to', 0)

        total = reads + writes + executes + spawns + connects + 1

        # Stage classification logic
        if reads / total > 0.6 and executes == 0:
            return "reconnaissance"

        if executes > 0 and spawns > 3:
            return "execution"

        if writes / total > 0.4 and executes > 0:
            return "persistence"

        if connects > 0 and reads > writes:
            return "collection"

        if connects > 0 and writes > reads:
            return "exfiltration"

        if spawns > 5:
            return "lateral_movement"

        return "active_attack"

    def get_timeline_data(self) -> Dict:
        """
        Get complete timeline data for visualization.
        This is what gets sent to the frontend.
        """
        # Ensure attack progressions are detected
        if not self.attack_progressions:
            self.detect_attack_progressions()

        # Build time series data
        time_series = []
        for window in sorted(self.windows, key=lambda w: w.window_id):
            time_series.append({
                'window_id': window.window_id,
                'time': window.start_time,
                'nodes': window.num_nodes,
                'edges': window.num_edges,
                'anomaly_score': window.anomaly_score,
                'label': window.label,
                'attack_stage': window.attack_stage
            })

        # Aggregate statistics
        benign_windows = [w for w in self.windows if w.label == 0]
        attack_windows = [w for w in self.windows if w.label == 1]

        stats = {
            'total_windows': len(self.windows),
            'benign_windows': len(benign_windows),
            'attack_windows': len(attack_windows),
            'attack_ratio': len(attack_windows) / len(self.windows) if self.windows else 0,
            'avg_nodes_benign': np.mean([w.num_nodes for w in benign_windows]) if benign_windows else 0,
            'avg_nodes_attack': np.mean([w.num_nodes for w in attack_windows]) if attack_windows else 0,
            'max_anomaly_score': max(w.anomaly_score for w in self.windows) if self.windows else 0,
        }

        return {
            'time_series': time_series,
            'statistics': stats,
            'attack_progressions': [p.to_dict() for p in self.attack_progressions],
            'normal_baseline': self.normal_flow_baseline
        }

    def to_json(self, path: Path) -> None:
        """Save timeline to JSON."""
        with open(path, 'w') as f:
            json.dump(self.get_timeline_data(), f, indent=2, default=str)


class TimelineBuilder:
    """
    Builds unified timeline from semantic graphs.
    """

    def __init__(self, resolver: SemanticResolver):
        self.resolver = resolver
        self.transformer = SemanticGraphTransformer(resolver)

    def build_from_graphs(
        self,
        graphs_dir: Path,
        labels_csv: Path,
        output_path: Optional[Path] = None
    ) -> UnifiedTimeline:
        """
        Build complete timeline from graph directory and labels.
        """
        labels_df = pd.read_csv(labels_csv)
        timeline = UnifiedTimeline()

        print(f"Building unified timeline from {len(labels_df)} windows...")

        for _, row in labels_df.iterrows():
            window_id = row['window_id']
            json_path = graphs_dir / f"window_{window_id:04d}.json"

            if not json_path.exists():
                continue

            # Transform to semantic graph
            sem_graph = self.transformer.transform_from_json(
                json_path=json_path,
                window_id=window_id,
                start_time=str(row['start']),
                end_time=str(row['end'])
            )

            # Get semantic summary
            summary = sem_graph.get_semantic_summary()

            # Create timeline window
            tw = TimelineWindow(
                window_id=window_id,
                start_time=str(row['start']),
                end_time=str(row['end']),
                label=int(row['label']),
                num_nodes=row['num_nodes'],
                num_edges=row['num_edges'],
                semantic_node_types=summary['node_types'],
                semantic_edge_types=summary['edge_types']
            )

            timeline.add_window(tw)

        # Build baseline from benign windows
        timeline.build_normal_baseline()

        # Detect attack progressions
        timeline.detect_attack_progressions()

        # Compute anomaly scores
        self._compute_anomaly_scores(timeline)

        if output_path:
            timeline.to_json(output_path)
            print(f"Timeline saved to {output_path}")

        return timeline

    def _compute_anomaly_scores(self, timeline: UnifiedTimeline) -> None:
        """Compute anomaly scores for all windows based on baseline."""
        baseline = timeline.normal_flow_baseline

        for window in timeline.windows:
            score = 0.0
            anomalies = []

            # Compare edge type distribution to baseline
            for edge_type, count in window.semantic_edge_types.items():
                expected = baseline.get(edge_type, 0)
                if expected == 0 and count > 0:
                    score += count * 2.0
                    anomalies.append(f"Novel edge type: {edge_type}")
                elif count > expected * 3:
                    score += (count - expected) * 0.5
                    anomalies.append(f"Spike in {edge_type}: {count} vs expected {expected:.1f}")

            # Check for attack indicators
            if window.label == 1:
                # Boost score for known attack windows (for visualization)
                score += 10.0

            window.anomaly_score = score
            window.anomalous_flows = anomalies
            window.attack_stage = timeline._classify_attack_stage(window)
