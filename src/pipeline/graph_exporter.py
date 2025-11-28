# src/pipeline/graph_exporter.py
import json
from pathlib import Path
import networkx as nx

class GraphExporter:
    """
    Saves graphs to JSON (node-link format) and tracks metadata.
    Clean, safe, reusable.
    """

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, G, window_id):
        path = self.output_dir / f"window_{window_id:04d}.json"
        with open(path, "w") as f:
            json.dump(nx.node_link_data(G), f)
