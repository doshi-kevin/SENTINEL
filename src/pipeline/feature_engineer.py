# src/pipeline/feature_engineer.py
import numpy as np
import pandas as pd
import networkx as nx
from datetime import datetime

class FeatureEngineer:
    """
    Adds structural, statistical, and temporal features to graph nodes.
    Clean, modular, and future-proof for sequence-based detection.
    """

    NODE_KEYS = [
        # structural / centrality
        "node_type_flag", "degree", "in_degree", "out_degree",
        "event_count", "event_type_count", "ts_var",
        "closeness", "betweenness", "pagerank", "cluster_coeff",

        # --- TEMPORAL FEATURES ---
        "avg_ts_gap", "last_seen_delta", "burst_flag",
        "activity_rate", "temporal_entropy",
        "time_sin", "time_cos"
    ]

    def compute_node_features(self, G):
        """
        Compute centrality, statistical, and temporal features.
        """

        # ------------------------------
        # Structural features
        # ------------------------------
        try:
            degree_dict = dict(G.degree())
            indeg = dict(G.in_degree())
            outdeg = dict(G.out_degree())
            close = nx.closeness_centrality(G)
            between = nx.betweenness_centrality(G, normalized=True)
            pagerank = nx.pagerank(G, alpha=0.85)
            cluster = nx.clustering(G.to_undirected())
        except:
            close = {n: 0 for n in G.nodes()}
            between = {n: 0 for n in G.nodes()}
            pagerank = {n: 0 for n in G.nodes()}
            cluster = {n: 0 for n in G.nodes()}
            indeg = {n: 0 for n in G.nodes()}
            outdeg = {n: 0 for n in G.nodes()}
            degree_dict = {n: 0 for n in G.nodes()}

        # ------------------------------
        # TEMPORAL FEATURES
        # ------------------------------
        for node in G.nodes():

            # collect timestamps of outgoing events
            ts_list = []
            event_types = set()

            for _, _, data in G.out_edges(node, data=True):
                evt = data.get("event", None)
                if evt:
                    event_types.add(evt)

                ts = data.get("ts", None)
                if ts:
                    ts_list.append(pd.to_datetime(ts).timestamp())

            ts_list = sorted(ts_list)

            # --- temporal var ---
            ts_var = float(np.var(ts_list)) if len(ts_list) > 1 else 0.0

            # --- avg time gap ---
            if len(ts_list) > 1:
                gaps = np.diff(ts_list)
                avg_ts_gap = float(np.mean(gaps))
            else:
                avg_ts_gap = 0.0

            # --- last seen delta ---
            if ts_list:
                last_seen_delta = float(ts_list[-1] - ts_list[0])
            else:
                last_seen_delta = 0.0

            # --- burst flag (>5 events in 200 ms) ---
            burst_flag = 0
            if len(ts_list) >= 5:
                for i in range(len(ts_list) - 5):
                    if ts_list[i+5] - ts_list[i] < 0.2:
                        burst_flag = 1
                        break

            # --- activity rate ---
            activity_rate = degree_dict[node]  # events per window (1 sec)

            # --- temporal entropy ---
            if len(ts_list) > 1:
                diffs = np.diff(ts_list)
                diffs = diffs / diffs.sum() if diffs.sum() > 0 else diffs
                temporal_entropy = float(-(diffs * np.log(diffs + 1e-9)).sum())
            else:
                temporal_entropy = 0.0

            # --- time of day encoding ---
            if ts_list:
                dt_obj = datetime.fromtimestamp(ts_list[0])
                tod = dt_obj.hour * 3600 + dt_obj.minute * 60 + dt_obj.second
                time_sin = np.sin(2 * np.pi * tod / 86400)
                time_cos = np.cos(2 * np.pi * tod / 86400)
            else:
                time_sin = 0.0
                time_cos = 0.0

            # -------------------------------------
            # ASSIGN FEATURES
            # -------------------------------------
            G.nodes[node]["node_type_flag"] = 1 if G.nodes[node]["node_type"] == "subject" else 0
            G.nodes[node]["degree"] = degree_dict[node]
            G.nodes[node]["in_degree"] = indeg[node]
            G.nodes[node]["out_degree"] = outdeg[node]
            G.nodes[node]["event_count"] = degree_dict[node]
            G.nodes[node]["event_type_count"] = len(event_types)
            G.nodes[node]["ts_var"] = ts_var
            G.nodes[node]["closeness"] = close[node]
            G.nodes[node]["betweenness"] = between[node]
            G.nodes[node]["pagerank"] = pagerank[node]
            G.nodes[node]["cluster_coeff"] = cluster[node]

            # temporal features
            G.nodes[node]["avg_ts_gap"] = avg_ts_gap
            G.nodes[node]["last_seen_delta"] = last_seen_delta
            G.nodes[node]["burst_flag"] = burst_flag
            G.nodes[node]["activity_rate"] = activity_rate
            G.nodes[node]["temporal_entropy"] = temporal_entropy
            G.nodes[node]["time_sin"] = time_sin
            G.nodes[node]["time_cos"] = time_cos

        return G
