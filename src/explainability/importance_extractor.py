# src/explainability/importance_extractor.py

import torch

class ImportanceExtractor:
    """
    Computes node and edge importance via gradients.
    """

    def __init__(self, model):
        self.model = model

    def compute_importance(self, graph_sequence, label_idx):
        """
        graph_sequence: list of Batch objects
        label_idx: the predicted class
        Returns: node_importance_per_graph, edge_importance_per_graph
        """
        self.model.zero_grad()

        # Enable gradients for node features
        for g in graph_sequence:
            g.x.requires_grad = True

        logits, attn = self.model(graph_sequence)
        logit = logits[:, label_idx]
        logit.backward()

        node_scores = []
        edge_scores = []

        for g in graph_sequence:
            # Node importance: gradient norm per node
            node_imp = g.x.grad.norm(dim=1).cpu().tolist()
            node_scores.append(node_imp)

            # Edge importance: gradient norm per edge attribute
            if g.edge_attr is not None and g.edge_attr.grad is not None:
                edge_imp = g.edge_attr.grad.norm(dim=1).cpu().tolist()
            else:
                edge_imp = []
            edge_scores.append(edge_imp)

        return node_scores, edge_scores, attn.detach().cpu().tolist()
