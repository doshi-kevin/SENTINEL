import os
import json
import torch
import networkx as nx
import pandas as pd
from torch_geometric.data import Data, Dataset

# Node features (11 as before)
NODE_FEATURE_KEYS = [
    # structural features
    "node_type_flag",
    "degree",
    "in_degree",
    "out_degree",
    "event_count",
    "event_type_count",
    "ts_var",
    "closeness",
    "betweenness",
    "pagerank",
    "cluster_coeff",

    # temporal features
    "avg_ts_gap",
    "last_seen_delta",
    "burst_flag",
    "activity_rate",
    "temporal_entropy",
    "time_sin",
    "time_cos"
]

# Event types (edge features)
EVENT_TYPES = [
    "EVENT_EXECUTE", "EVENT_FORK", "EVENT_SIGNAL", "EVENT_READ", "EVENT_WRITE",
    "EVENT_OPEN", "EVENT_CREATE", "EVENT_RECVMSG", "EVENT_RECVFROM",
    "EVENT_RENAME", "EVENT_CLONE", "EVENT_UNIT", "EVENT_MODIFY_PROCESS",
    "EVENT_SENDMSG", "EVENT_SENDTO", "EVENT_SHM", "EVENT_TEE", "EVENT_SPLICE",
    "EVENT_VMSPLICE", "EVENT_INIT_MODULE", "EVENT_FINIT_MODULE",
    "EVENT_SERVICEINSTALL"
]

NUM_NODE_FEATURES = len(NODE_FEATURE_KEYS)
NUM_EDGE_FEATURES = len(EVENT_TYPES)


class SentinelGraphDataset(Dataset):
    def __init__(self, graphs_dir, labels_csv):
        super().__init__()
        self.graphs_dir = graphs_dir
        self.labels = pd.read_csv(labels_csv)

        self.valid = []
        for wid in self.labels["window_id"]:
            if os.path.exists(f"{graphs_dir}/window_{wid:04d}.json"):
                self.valid.append(wid)

    def len(self):
        return len(self.valid)

    def get(self, idx):
        wid = self.valid[idx]
        path = f"{self.graphs_dir}/window_{wid:04d}.json"

        with open(path, "r") as f:
            g_json = json.load(f)
        G = nx.node_link_graph(g_json)

        # -------- Node features --------
        node_idx = {}
        node_features = []

        for i, (node, data) in enumerate(G.nodes(data=True)):
            node_idx[node] = i
            node_features.append(
                [float(data.get(k, 0)) for k in NODE_FEATURE_KEYS]
            )

        x = torch.tensor(node_features, dtype=torch.float)

        # -------- Edge features --------
        edges = []
        edge_features = []

        for src, dst, data in G.edges(data=True):
            edges.append([node_idx[src], node_idx[dst]])

            evt = data.get("event", None)
            onehot = [1.0 if evt == e else 0.0 for e in EVENT_TYPES]

            edge_features.append(onehot)

        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(edge_features, dtype=torch.float)

        # -------- Label --------
        y = torch.tensor(
            [int(self.labels[self.labels.window_id == wid]["label"].values[0])],
            dtype=torch.long
        )

        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y)
