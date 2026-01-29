"""
Semantic Graph Transformer

Transforms raw provenance graphs (UUIDs + events) into semantic graphs
(semantic entity types + semantic relationships).

This abstraction is what enables:
1. Zero-shot transfer across different systems
2. Learning attack "grammar" instead of specific patterns
3. Meaningful explanations ("scanner accessed sensitive file" vs "UUID123 read UUID456")
"""

import json
import networkx as nx
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .semantic_resolver import (
    SemanticResolver,
    SemanticEntityType,
    SemanticEdgeType,
    map_event_to_semantic_edge,
    EntityBehaviorProfile
)


@dataclass
class SemanticNode:
    """A node in the semantic graph."""
    id: str                                    # Original UUID
    semantic_type: SemanticEntityType          # Resolved semantic type
    features: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'semantic_type': self.semantic_type.value,
            'features': self.features
        }


@dataclass
class SemanticEdge:
    """An edge in the semantic graph."""
    source: str                                # Source node ID
    target: str                                # Target node ID
    semantic_type: SemanticEdgeType            # Semantic relationship
    raw_event: str                             # Original event type
    timestamp: Optional[str] = None
    weight: float = 1.0                        # Edge weight (frequency)

    def to_dict(self) -> dict:
        return {
            'source': self.source,
            'target': self.target,
            'semantic_type': self.semantic_type.value,
            'raw_event': self.raw_event,
            'timestamp': self.timestamp,
            'weight': self.weight
        }


class SemanticGraph:
    """
    A semantic provenance graph where:
    - Nodes are semantic entity types (not UUIDs)
    - Edges are semantic relationships (not raw events)
    - Features capture behavioral patterns
    """

    def __init__(self, window_id: int, start_time: str, end_time: str):
        self.window_id = window_id
        self.start_time = start_time
        self.end_time = end_time
        self.nodes: Dict[str, SemanticNode] = {}
        self.edges: List[SemanticEdge] = []
        self._nx_graph: Optional[nx.DiGraph] = None

    def add_node(self, node: SemanticNode) -> None:
        self.nodes[node.id] = node
        self._nx_graph = None

    def add_edge(self, edge: SemanticEdge) -> None:
        self.edges.append(edge)
        self._nx_graph = None

    def to_networkx(self) -> nx.DiGraph:
        """Convert to NetworkX graph for analysis."""
        if self._nx_graph is not None:
            return self._nx_graph

        G = nx.DiGraph()

        for node_id, node in self.nodes.items():
            G.add_node(
                node_id,
                semantic_type=node.semantic_type.value,
                **node.features
            )

        for edge in self.edges:
            if G.has_edge(edge.source, edge.target):
                # Aggregate multiple edges
                G[edge.source][edge.target]['weight'] += edge.weight
            else:
                G.add_edge(
                    edge.source,
                    edge.target,
                    semantic_type=edge.semantic_type.value,
                    raw_event=edge.raw_event,
                    weight=edge.weight
                )

        self._nx_graph = G
        return G

    def get_semantic_summary(self) -> Dict:
        """Get a summary of semantic patterns in this graph."""
        node_type_counts = defaultdict(int)
        edge_type_counts = defaultdict(int)

        for node in self.nodes.values():
            node_type_counts[node.semantic_type.value] += 1

        for edge in self.edges:
            edge_type_counts[edge.semantic_type.value] += 1

        # Compute semantic flow patterns
        flows = []
        for edge in self.edges:
            src_type = self.nodes[edge.source].semantic_type.value if edge.source in self.nodes else "unknown"
            tgt_type = self.nodes[edge.target].semantic_type.value if edge.target in self.nodes else "unknown"
            flows.append(f"{src_type}->{edge.semantic_type.value}->{tgt_type}")

        flow_counts = defaultdict(int)
        for flow in flows:
            flow_counts[flow] += 1

        return {
            'window_id': self.window_id,
            'time_range': f"{self.start_time} to {self.end_time}",
            'num_nodes': len(self.nodes),
            'num_edges': len(self.edges),
            'node_types': dict(node_type_counts),
            'edge_types': dict(edge_type_counts),
            'top_flows': dict(sorted(flow_counts.items(), key=lambda x: -x[1])[:10])
        }

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'window_id': self.window_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'nodes': [n.to_dict() for n in self.nodes.values()],
            'edges': [e.to_dict() for e in self.edges]
        }

    def to_json(self, path: Path) -> None:
        """Save to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> 'SemanticGraph':
        """Load from dictionary."""
        graph = cls(
            window_id=data['window_id'],
            start_time=data['start_time'],
            end_time=data['end_time']
        )

        for node_data in data['nodes']:
            node = SemanticNode(
                id=node_data['id'],
                semantic_type=SemanticEntityType(node_data['semantic_type']),
                features=node_data.get('features', {})
            )
            graph.add_node(node)

        for edge_data in data['edges']:
            edge = SemanticEdge(
                source=edge_data['source'],
                target=edge_data['target'],
                semantic_type=SemanticEdgeType(edge_data['semantic_type']),
                raw_event=edge_data['raw_event'],
                timestamp=edge_data.get('timestamp'),
                weight=edge_data.get('weight', 1.0)
            )
            graph.add_edge(edge)

        return graph


class SemanticGraphTransformer:
    """
    Transforms raw provenance graphs into semantic graphs.

    Pipeline:
    1. Load raw graph (NetworkX from JSON)
    2. Resolve each node to semantic type
    3. Map each edge to semantic relationship
    4. Compute semantic features
    5. Output SemanticGraph
    """

    def __init__(self, resolver: SemanticResolver):
        self.resolver = resolver

    def transform_from_json(
        self,
        json_path: Path,
        window_id: int,
        start_time: str,
        end_time: str
    ) -> SemanticGraph:
        """Transform a raw graph JSON to semantic graph."""
        with open(json_path, 'r') as f:
            raw_data = json.load(f)

        # Create semantic graph
        sem_graph = SemanticGraph(
            window_id=window_id,
            start_time=start_time,
            end_time=end_time
        )

        # Process nodes
        for node_data in raw_data['nodes']:
            node_id = node_data['id']
            semantic_type = self.resolver.resolve_semantic_type(node_id)

            # Extract features from raw graph
            features = {
                'degree': node_data.get('degree', 0),
                'in_degree': node_data.get('in_degree', 0),
                'out_degree': node_data.get('out_degree', 0),
                'pagerank': node_data.get('pagerank', 0),
                'betweenness': node_data.get('betweenness', 0),
                'closeness': node_data.get('closeness', 0),
                'temporal_entropy': node_data.get('temporal_entropy', 0),
                'activity_rate': node_data.get('activity_rate', 0),
                'burst_flag': node_data.get('burst_flag', 0),
            }

            sem_node = SemanticNode(
                id=node_id,
                semantic_type=semantic_type,
                features=features
            )
            sem_graph.add_node(sem_node)

        # Process edges
        for edge_data in raw_data.get('edges', raw_data.get('links', [])):
            source = edge_data.get('source', edge_data.get('from'))
            target = edge_data.get('target', edge_data.get('to'))
            raw_event = edge_data.get('event', 'UNKNOWN')

            semantic_edge_type = map_event_to_semantic_edge(raw_event)

            sem_edge = SemanticEdge(
                source=source,
                target=target,
                semantic_type=semantic_edge_type,
                raw_event=raw_event,
                timestamp=edge_data.get('ts'),
                weight=1.0
            )
            sem_graph.add_edge(sem_edge)

        return sem_graph

    def transform_batch(
        self,
        graphs_dir: Path,
        labels_df: pd.DataFrame,
        output_dir: Optional[Path] = None
    ) -> List[SemanticGraph]:
        """Transform all graphs in a directory."""
        semantic_graphs = []

        for _, row in labels_df.iterrows():
            window_id = row['window_id']
            json_path = graphs_dir / f"window_{window_id:04d}.json"

            if not json_path.exists():
                continue

            sem_graph = self.transform_from_json(
                json_path=json_path,
                window_id=window_id,
                start_time=str(row['start']),
                end_time=str(row['end'])
            )

            semantic_graphs.append(sem_graph)

            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                sem_graph.to_json(output_dir / f"semantic_{window_id:04d}.json")

        return semantic_graphs


def compute_semantic_anomaly_score(
    semantic_graph: SemanticGraph,
    normal_flow_distribution: Dict[str, float]
) -> Tuple[float, List[str]]:
    """
    Compute anomaly score based on deviation from normal semantic flows.

    This is the CORE of zero-shot detection:
    - Normal behavior has predictable semantic flow patterns
    - Attacks create unusual semantic flows
    - We don't need to see the specific attack before

    Args:
        semantic_graph: The graph to analyze
        normal_flow_distribution: Expected distribution of semantic flows

    Returns:
        (anomaly_score, list of anomalous flows)
    """
    summary = semantic_graph.get_semantic_summary()
    observed_flows = summary['top_flows']

    anomalous_flows = []
    anomaly_score = 0.0

    for flow, count in observed_flows.items():
        expected_freq = normal_flow_distribution.get(flow, 0.0)

        if expected_freq < 0.01:  # Rare or unseen flow
            anomaly_score += count * 2.0  # High weight for novel flows
            anomalous_flows.append(f"RARE: {flow} (seen {count}x)")
        elif count > expected_freq * 10:  # Frequency spike
            anomaly_score += count * 0.5
            anomalous_flows.append(f"SPIKE: {flow} (expected {expected_freq:.1f}, saw {count})")

    # Suspicious semantic patterns
    suspicious_patterns = [
        ("scanner", "writes_to", "external_host"),      # Data exfiltration
        ("unknown_process", "executes", "executable"),  # Suspicious execution
        ("network_client", "writes_to", "sensitive_file"),  # Possible C2
        ("worker", "spawns", "orchestrator"),           # Privilege escalation pattern
    ]

    for src, edge, tgt in suspicious_patterns:
        pattern = f"{src}->{edge}->{tgt}"
        if pattern in observed_flows:
            anomaly_score += observed_flows[pattern] * 5.0
            anomalous_flows.append(f"SUSPICIOUS: {pattern}")

    return anomaly_score, anomalous_flows
