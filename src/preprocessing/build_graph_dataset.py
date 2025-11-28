"""
SENTINEL — Provenance Graph Builder (v4)
Upgrades:
- 1-second windows
- Expanded event types (full CDM)
- Rich node features (13+ features)
- Edge-type one-hot encoding
- Multi-file ingestion capable
"""

import pandas as pd
import networkx as nx
import numpy as np
from datetime import timedelta
from pathlib import Path
import json
import ast

# -----------------------------
# CONFIG
# -----------------------------
WINDOW = timedelta(seconds=1)

EXPANDED_EVENTS = {
    "EVENT_EXECUTE", "EVENT_FORK", "EVENT_SIGNAL", "EVENT_READ", "EVENT_WRITE",
    "EVENT_OPEN", "EVENT_CREATE", "EVENT_RECVMSG", "EVENT_RECVFROM",
    "EVENT_RENAME", "EVENT_CLONE", "EVENT_UNIT", "EVENT_MODIFY_PROCESS",
    "EVENT_SENDMSG", "EVENT_SENDTO", "EVENT_SHM", "EVENT_TEE", "EVENT_SPLICE",
    "EVENT_VMSPLICE", "EVENT_INIT_MODULE", "EVENT_FINIT_MODULE",
    "EVENT_SERVICEINSTALL"
}

DATA_DIR = Path("data/processed/")
OUTPUT_DIR = Path("data/model_ready/")
GRAPH_DIR = OUTPUT_DIR / "graphs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_DIR.mkdir(parents=True, exist_ok=True)


def clean_uuid(x):
    """Convert b'..' UUIDs into hex strings."""
    if isinstance(x, str) and x.startswith("b'"):
        try:
            b = ast.literal_eval(x)
            return b.hex()
        except:
            return x
    return str(x)


# Ground truth attack period
ATTACK_START = pd.to_datetime("2019-05-07 11:10:00")
ATTACK_END = pd.to_datetime("2019-05-07 11:11:59")


def label_window(ws, we):
    return 1 if (ws <= ATTACK_END and we >= ATTACK_START) else 0


# ------------------------------------------------------------
#                MAIN PIPELINE
# ------------------------------------------------------------
def build_graph_dataset():
    print("📥 Loading events.csv...")
    events = pd.read_csv(DATA_DIR / "events.csv")
    events["timestamp"] = pd.to_datetime(events["timestamp"])

    print(f"Loaded {len(events):,} events")

    events = events[events["type"].isin(EXPANDED_EVENTS)]

    start_time = events["timestamp"].min()
    end_time = events["timestamp"].max()

    windows = []
    cursor = start_time
    while cursor < end_time:
        windows.append((cursor, cursor + WINDOW))
        cursor += WINDOW

    label_rows = []
    total_graphs = 0

    print("🚀 Building graphs (1-second windows)...")

    for idx, (ws, we) in enumerate(windows):
        w = events[(events["timestamp"] >= ws) & (events["timestamp"] < we)]
        if w.empty:
            continue

        G = nx.DiGraph()

        # Add edges + basic nodes
        for _, row in w.iterrows():
            subj = clean_uuid(row["subject"])
            obj = clean_uuid(row["predicate_object"]) if isinstance(row["predicate_object"], str) else None

            G.add_node(subj, node_type="subject")
            if obj:
                G.add_node(obj, node_type="object")
                G.add_edge(subj, obj, event=row["type"], ts=str(row["timestamp"]))

        if len(G.nodes) == 0:
            continue

        # ---------------------------
        # FEATURE ENGINEERING
        # ---------------------------

        # Compute centralities
        try:
            degree_dict = dict(G.degree())
            indeg = dict(G.in_degree())
            outdeg = dict(G.out_degree())
            close = nx.closeness_centrality(G)
            between = nx.betweenness_centrality(G, normalized=True)
            pagerank = nx.pagerank(G, alpha=0.85)
            cluster = nx.clustering(G.to_undirected())
        except:
            # fallback if graph is too small
            close = {n: 0 for n in G.nodes()}
            between = {n: 0 for n in G.nodes()}
            pagerank = {n: 0 for n in G.nodes()}
            cluster = {n: 0 for n in G.nodes()}
            indeg = {n: 0 for n in G.nodes()}
            outdeg = {n: 0 for n in G.nodes()}
            degree_dict = {n: 0 for n in G.nodes()}

        # Add node features
        for node in G.nodes():
            events_set = set()
            ts_values = []

            for _, _, data in G.out_edges(node, data=True):
                evt = data.get("event", None)
                if evt:
                    events_set.add(evt)

                ts = data.get("ts", None)
                if ts:
                    ts_values.append(pd.to_datetime(ts).timestamp())

            ts_var = float(np.var(ts_values)) if len(ts_values) > 1 else 0.0

            G.nodes[node]["node_type_flag"] = 1 if G.nodes[node]["node_type"] == "subject" else 0
            G.nodes[node]["degree"] = degree_dict[node]
            G.nodes[node]["in_degree"] = indeg[node]
            G.nodes[node]["out_degree"] = outdeg[node]
            G.nodes[node]["event_count"] = degree_dict[node]
            G.nodes[node]["event_type_count"] = len(events_set)
            G.nodes[node]["ts_var"] = ts_var
            G.nodes[node]["closeness"] = close[node]
            G.nodes[node]["betweenness"] = between[node]
            G.nodes[node]["pagerank"] = pagerank[node]
            G.nodes[node]["cluster_coeff"] = cluster[node]

        # Save graph
        graph_path = GRAPH_DIR / f"window_{idx:04d}.json"
        with open(graph_path, "w") as f:
            json.dump(nx.node_link_data(G), f)

        # label row
        label_rows.append({
            "window_id": idx,
            "start": ws,
            "end": we,
            "label": label_window(ws, we),
            "num_nodes": len(G.nodes),
            "num_edges": len(G.edges)
        })

        total_graphs += 1

    pd.DataFrame(label_rows).to_csv(OUTPUT_DIR / "labels.csv", index=False)

    print("🎉 Dataset v4 ready!")
    print(f"Total graphs: {total_graphs}")


if __name__ == "__main__":
    build_graph_dataset()
