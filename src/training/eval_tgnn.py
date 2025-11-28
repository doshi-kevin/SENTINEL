# src/training/eval_tgnn.py

import torch
from torch.utils.data import DataLoader

from src.pipeline.sequence_extractor import SequenceExtractor
from src.dataset.temporal_graph_dataset import TemporalGraphDataset, temporal_collate_fn
from src.models.tgnn import TGNN


def evaluate():
    print("🔍 Loading sequences...")
    seq = SequenceExtractor("data/model_ready/graphs", "data/model_ready/labels.csv")
    sequences = seq.build_sequences()

    print(f"Total sequences: {len(sequences)}")

    dataset = TemporalGraphDataset(sequences)
    loader = DataLoader(dataset, batch_size=4, shuffle=False,
                        collate_fn=temporal_collate_fn)

    # LOAD MODEL
    model = TGNN(node_features=18, edge_features=22)
    model.load_state_dict(torch.load("sentinel_tgnn.pt"))
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    correct = 0
    total = 0

    print("🔍 Running evaluation...")

    with torch.no_grad():
        for batch_graphs, batch_labels in loader:
            batch_graphs = [g.to(device) for g in batch_graphs]
            batch_labels = batch_labels.to(device)

            preds = model(batch_graphs).argmax(dim=1)

            correct += (preds == batch_labels).sum().item()
            total += batch_labels.size(0)

    acc = correct / total if total > 0 else 0
    print(f"\n🎯 TGNN Accuracy: {acc:.3f}")


if __name__ == "__main__":
    evaluate()
