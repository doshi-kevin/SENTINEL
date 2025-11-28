# src/pipeline/sequence_extractor.py

import os
import json
import torch
import networkx as nx
import pandas as pd
from torch_geometric.data import Data

from src.dataset.sentinel_pyg_dataset import NODE_FEATURE_KEYS, EVENT_TYPES

class SequenceExtractor:
    """
    Loads G0, G1, G2, ..., G_N as PyG Data objects
    And converts them into sequences of length seq_len.
    """

    def __init__(self, graphs_dir, labels_csv, seq_len=3):
        self.graphs_dir = graphs_dir
        self.labels = pd.read_csv(labels_csv)
        self.seq_len = seq_len

    def load_graph(self, wid):
        """Load one graph JSON and convert to PyG Data."""
        path = os.path.join(self.graphs_dir, f"window_{wid:04d}.json")
        with open(path, "r") as f:
            g_json = json.load(f)

        G = nx.node_link_graph(g_json)

        # =============== NODE FEATURES ===============
        node_idx = {}
        node_features = []
        for i, (node, data) in enumerate(G.nodes(data=True)):
            node_idx[node] = i
            node_features.append([float(data.get(k, 0)) for k in NODE_FEATURE_KEYS])

        x = torch.tensor(node_features, dtype=torch.float)

        # =============== EDGE FEATURES ===============
        edges = []
        edge_features = []
        for src, dst, data in G.edges(data=True):
            edges.append([node_idx[src], node_idx[dst]])

            evt = data.get("event", None)
            onehot = [1.0 if evt == e else 0.0 for e in EVENT_TYPES]
            edge_features.append(onehot)

        if len(edges) == 0:
            edges = torch.zeros((2, 1), dtype=torch.long)
            edge_features = torch.zeros((1, len(EVENT_TYPES)), dtype=torch.float)
        else:
            edges = torch.tensor(edges, dtype=torch.long).t().contiguous()
            edge_features = torch.tensor(edge_features, dtype=torch.float)

        # =============== LABEL ===============
        y_val = int(self.labels[self.labels.window_id == wid]["label"].values[0])
        y = torch.tensor([y_val], dtype=torch.long)

        return Data(x=x, edge_index=edges, edge_attr=edge_features, y=y)

    def build_sequences(self):
        """
        Build overlapping sequences:
        [G0,G1,G2], [G1,G2,G3], ...
        """
        sequences = []
        valid_windows = sorted(self.labels.window_id.tolist())

        for i in range(len(valid_windows) - self.seq_len + 1):
            seq_ids = valid_windows[i : i + self.seq_len]

            # load each graph
            seq_graphs = [self.load_graph(wid) for wid in seq_ids]

            # label = OR of labels inside sequence
            labels = [g.y.item() for g in seq_graphs]
            seq_label = 1 if any(labels) else 0

            sequences.append((seq_graphs, seq_label))

        return sequences
