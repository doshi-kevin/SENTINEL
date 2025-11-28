# test_temporal_dataset.py
"""
Test script for Module 4.3.2:
Validates SequenceExtractor + TemporalGraphDataset + DataLoader.
Run: python test_temporal_dataset.py
"""

from src.pipeline.sequence_extractor import SequenceExtractor
from src.dataset.temporal_graph_dataset import TemporalGraphDataset, temporal_collate_fn
from torch.utils.data import DataLoader

def main():
    print("🔍 Loading sequences...")
    seq = SequenceExtractor("data/model_ready/graphs", "data/model_ready/labels.csv")
    sequences = seq.build_sequences()

    print(f"Total sequences found: {len(sequences)}")

    print("🔍 Building Temporal Dataset...")
    dataset = TemporalGraphDataset(sequences)

    print("🔍 Creating DataLoader...")
    loader = DataLoader(dataset, batch_size=4, collate_fn=temporal_collate_fn)

    print("🔍 Fetching one batch...")
    batch_graphs, batch_labels = next(iter(loader))

    print("\n=== TEST OUTPUT ===")
    print("Sequence length (should be 3):", len(batch_graphs))
    print("Batch size:", batch_graphs[0].num_graphs)
    print("Labels:", batch_labels)
    print("===================")

    print("\n✅ Temporal Dataset + Collate Function working correctly.")

if __name__ == "__main__":
    main()
