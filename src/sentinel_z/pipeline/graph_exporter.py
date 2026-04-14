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

        # Get node-link data and ensure links use numeric indices
        data = nx.node_link_data(G)

        # Create a mapping from node ID to index
        node_id_to_index = {node['id']: i for i, node in enumerate(data['nodes'])}

        # Convert links to use numeric indices
        for link in data['links']:
            link['source'] = node_id_to_index[link['source']]
            link['target'] = node_id_to_index[link['target']]

        with open(path, "w") as f:
            json.dump(data, f)
