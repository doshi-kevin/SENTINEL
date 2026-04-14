"""
FAST Graph Dataset Builder for Large Event Files

Optimized for speed: vectorized operations, minimal features, batch processing.
"""

import pandas as pd
import numpy as np
import json
import sys
import time
from pathlib import Path
from datetime import timedelta
from typing import Optional


def print_progress(current: int, total: int, prefix: str = "", elapsed: float = 0):
    """Print progress bar."""
    if total == 0:
        return
    percent = current / total
    filled = int(40 * percent)
    bar = '#' * filled + '-' * (40 - filled)

    if elapsed > 0 and percent > 0:
        eta = (elapsed / percent) - elapsed
        eta_str = f"ETA: {eta:.0f}s"
    else:
        eta_str = ""

    print(f'\r{prefix} |{bar}| {percent*100:.1f}% {eta_str}    ', end='', flush=True)


def build_graph_fast(events: pd.DataFrame) -> dict:
    """Build graph data structure quickly using vectorized operations."""
    # Get unique nodes
    subjects = events['subject'].dropna().unique()
    objects = events['predicate_object'].dropna().unique()

    all_nodes = list(set(subjects) | set(objects))
    if len(all_nodes) == 0:
        return None

    node_to_idx = {node: i for i, node in enumerate(all_nodes)}

    # Build nodes list
    nodes = []
    for node in all_nodes:
        is_subject = node in subjects
        nodes.append({
            'id': str(node),
            'node_type': 'subject' if is_subject else 'object'
        })

    # Build edges using groupby for speed
    valid_events = events.dropna(subset=['subject', 'predicate_object'])

    if len(valid_events) == 0:
        # No edges, but we have nodes
        return {
            'directed': True,
            'multigraph': False,
            'nodes': nodes,
            'links': []
        }

    # Aggregate edges
    edge_agg = valid_events.groupby(['subject', 'predicate_object']).agg({
        'type': 'first',
        'timestamp': ['first', 'count']
    }).reset_index()

    edge_agg.columns = ['source', 'target', 'event', 'ts', 'count']

    links = []
    for _, row in edge_agg.iterrows():
        src = str(row['source'])
        tgt = str(row['target'])
        if src in node_to_idx and tgt in node_to_idx:
            links.append({
                'source': node_to_idx[src],
                'target': node_to_idx[tgt],
                'event': str(row['event']),
                'count': int(row['count'])
            })

    return {
        'directed': True,
        'multigraph': False,
        'nodes': nodes,
        'links': links
    }


def add_basic_features(graph_data: dict, events: pd.DataFrame) -> None:
    """Add minimal features to nodes (fast computation only)."""
    if graph_data is None:
        return

    nodes = graph_data['nodes']
    links = graph_data['links']

    # Compute degree from links
    in_degree = {}
    out_degree = {}

    for link in links:
        src = link['source']
        tgt = link['target']
        out_degree[src] = out_degree.get(src, 0) + link['count']
        in_degree[tgt] = in_degree.get(tgt, 0) + link['count']

    # Event counts per node
    subject_counts = events['subject'].value_counts().to_dict()
    object_counts = events['predicate_object'].value_counts().to_dict()

    for i, node in enumerate(nodes):
        node_id = node['id']
        node['in_degree'] = in_degree.get(i, 0)
        node['out_degree'] = out_degree.get(i, 0)
        node['degree'] = node['in_degree'] + node['out_degree']
        node['event_count'] = subject_counts.get(node_id, 0) + object_counts.get(node_id, 0)
        node['node_type_flag'] = 1 if node['node_type'] == 'subject' else 0


def build_dataset(
    events_csv: str,
    output_dir: str,
    window_seconds: int = 1,
    attack_start: str = "2019-05-07 11:10:00",
    attack_end: str = "2019-05-07 11:12:00",
    max_windows: Optional[int] = None,
    save_every: int = 500
):
    """
    Build graph dataset from large event CSV - FAST version.
    """
    output_dir = Path(output_dir)
    graphs_dir = output_dir / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("SENTINEL-Z Graph Dataset Builder (FAST)")
    print("="*60)

    # Parse attack period
    attack_start_dt = pd.to_datetime(attack_start)
    attack_end_dt = pd.to_datetime(attack_end)
    print(f"Attack period: {attack_start} to {attack_end}")

    # Load all events at once (faster than chunked for this size)
    print("\nPhase 1: Loading events...")
    start_time = time.time()

    all_events = pd.read_csv(events_csv)
    load_time = time.time() - start_time
    print(f"  Loaded {len(all_events):,} events in {load_time:.1f}s")

    # Parse timestamps
    print("  Parsing timestamps...")
    all_events['timestamp'] = pd.to_datetime(all_events['timestamp'])

    min_ts = all_events['timestamp'].min()
    max_ts = all_events['timestamp'].max()
    print(f"  Time range: {min_ts} to {max_ts}")
    print(f"  Duration: {max_ts - min_ts}")

    # Create window key
    print("\nPhase 2: Grouping by time windows...")
    all_events['window_key'] = (
        (all_events['timestamp'] - min_ts).dt.total_seconds() // window_seconds
    ).astype(int)

    # Group
    grouped = all_events.groupby('window_key')
    window_keys = sorted(grouped.groups.keys())
    total_windows = len(window_keys)

    if max_windows:
        window_keys = window_keys[:max_windows]
        total_windows = len(window_keys)

    print(f"  Found {total_windows} non-empty windows")

    # Build graphs
    print("\nPhase 3: Building graphs...")
    labels = []
    graph_count = 0
    start_build = time.time()

    for i, window_key in enumerate(window_keys):
        window_events = grouped.get_group(window_key)

        if len(window_events) < 2:  # Skip tiny windows
            continue

        # Get window time
        window_start = min_ts + timedelta(seconds=window_key * window_seconds)
        window_end = window_start + timedelta(seconds=window_seconds)

        # Build graph
        graph_data = build_graph_fast(window_events)

        if graph_data is None or len(graph_data['nodes']) == 0:
            continue

        # Add features
        add_basic_features(graph_data, window_events)

        # Determine label
        label = 1 if (window_start <= attack_end_dt and window_end >= attack_start_dt) else 0

        # Save graph
        graph_path = graphs_dir / f"window_{graph_count:05d}.json"
        with open(graph_path, 'w') as f:
            json.dump(graph_data, f)

        # Record label
        labels.append({
            'window_id': graph_count,
            'start': str(window_start),
            'end': str(window_end),
            'label': label,
            'num_nodes': len(graph_data['nodes']),
            'num_edges': len(graph_data['links']),
            'event_count': len(window_events)
        })

        graph_count += 1

        # Progress
        if graph_count % 100 == 0:
            elapsed = time.time() - start_build
            print_progress(graph_count, total_windows, "Building", elapsed)

    print()  # Newline after progress bar
    build_time = time.time() - start_build
    print(f"  Built {graph_count} graphs in {build_time:.1f}s")

    # Save labels
    labels_df = pd.DataFrame(labels)
    labels_path = output_dir / "labels.csv"
    labels_df.to_csv(labels_path, index=False)

    # Summary
    attack_windows = labels_df[labels_df['label'] == 1].shape[0]
    benign_windows = labels_df[labels_df['label'] == 0].shape[0]

    total_time = time.time() - start_time

    print("\n" + "="*60)
    print("DATASET COMPLETE")
    print("="*60)
    print(f"  Total graphs: {graph_count}")
    print(f"  Attack windows: {attack_windows}")
    print(f"  Benign windows: {benign_windows}")
    print(f"  Avg nodes/graph: {labels_df['num_nodes'].mean():.1f}")
    print(f"  Avg edges/graph: {labels_df['num_edges'].mean():.1f}")
    print(f"  Output: {graphs_dir}")
    print(f"  Labels: {labels_path}")
    print(f"  Total time: {total_time:.1f}s")

    return labels_df


if __name__ == "__main__":
    build_dataset(
        events_csv="data/auto_processed/fivedirections/e5/events_1.csv",
        output_dir="data/auto_processed",
        window_seconds=1,
        attack_start="2019-05-07 11:10:00",
        attack_end="2019-05-07 11:12:00"
    )
