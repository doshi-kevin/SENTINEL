# src/training/explain_tgnn.py

import torch
from torch.utils.data import DataLoader

from src.pipeline.sequence_extractor import SequenceExtractor
from src.dataset.temporal_graph_dataset import TemporalGraphDataset, temporal_collate_fn
from src.models.tgnn import TGNN
from src.explainability.importance_extractor import ImportanceExtractor
from src.explainability.explanation_generator import ExplanationGenerator

def main():

    print("🔍 Loading sequences...")
    seq = SequenceExtractor("data/model_ready/graphs", "data/model_ready/labels.csv")
    sequences = seq.build_sequences()

    dataset = TemporalGraphDataset(sequences)
    loader = DataLoader(dataset, batch_size=1, shuffle=False,
                        collate_fn=temporal_collate_fn)

    model = TGNN(node_features=18, edge_features=22)
    state = torch.load("sentinel_tgnn.pt")
    model.load_state_dict(state, strict=False)
    model.eval()

    explainer = ImportanceExtractor(model)
    generator = ExplanationGenerator()

    print("🚀 Generating explanations for ALL sequences...\n")

    for idx, (graph_sequence, label) in enumerate(loader):

        graph_sequence = [g for g in graph_sequence]
        label = label.item()

        # Forward pass
        logits, attn = model(graph_sequence)
        pred = logits.argmax(dim=1).item()

        # Extract importance
        node_scores, edge_scores, temporal_weights = \
            explainer.compute_importance(graph_sequence, pred)

        # Save explanation file
        path = generator.save_explanation(
            seq_id=idx,
            prediction=pred,
            node_scores=node_scores,
            edge_scores=edge_scores,
            temporal_weights=temporal_weights
        )

        print(f"✔ Saved explanation for sequence {idx}: {path}")

    print("\n🎉 Explainability generation complete!")


if __name__ == "__main__":
    main()
