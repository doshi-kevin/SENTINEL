# src/explainability/explanation_generator.py

import json
import os

class ExplanationGenerator:

    def __init__(self, out_dir="explanations"):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)

    def save_explanation(self, seq_id, prediction, node_scores,
                         edge_scores, temporal_weights):

        out = {
            "sequence_id": seq_id,
            "prediction": int(prediction),
            "temporal_attention": temporal_weights,
            "node_importance": node_scores,
            "edge_importance": edge_scores
        }

        path = os.path.join(self.out_dir, f"explanation_{seq_id}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=4)

        return path
