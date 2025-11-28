# src/dataset/temporal_graph_dataset.py

import torch
from torch_geometric.data import Batch, Data

class TemporalGraphDataset(torch.utils.data.Dataset):
    """
    Accepts sequences of PyG Data objects.
    Each item = (list of graphs, sequence_label)
    """

    def __init__(self, sequences):
        self.sequences = sequences

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        seq_graphs, label = self.sequences[idx]

        # Convert list[Data] → list[Batch]
        batched_graphs = []
        for g in seq_graphs:
            # Batch.from_data_list turns Data → Batch
            batched_graphs.append(Batch.from_data_list([g]))

        label = torch.tensor([label], dtype=torch.long)

        return batched_graphs, label


def temporal_collate_fn(batch):
    """
    Custom collate function.
    batch: list of (sequence, label) pairs.
    """

    seq_len = len(batch[0][0])
    batch_size = len(batch)

    # Unpack graphs and labels
    labels = torch.cat([item[1] for item in batch], dim=0)

    # Combine each time-step separately
    timestep_batches = []
    for t in range(seq_len):
        graphs_t = [item[0][t] for item in batch]
        timestep_batches.append(Batch.from_data_list(graphs_t))

    return timestep_batches, labels
