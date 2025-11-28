# src/training/train_tgnn.py

import torch
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split

from src.pipeline.sequence_extractor import SequenceExtractor
from src.dataset.temporal_graph_dataset import TemporalGraphDataset, temporal_collate_fn
from src.models.tgnn import TGNN

def train_tgnn():

    seq = SequenceExtractor("data/model_ready/graphs", "data/model_ready/labels.csv")
    sequences = seq.build_sequences()

    labels = [lab for (_, lab) in sequences]

    train_idx, val_idx = train_test_split(
        list(range(len(sequences))),
        test_size=0.2,
        shuffle=True,
        stratify=labels
    )

    train_seq = [sequences[i] for i in train_idx]
    val_seq = [sequences[i] for i in val_idx]

    train_ds = TemporalGraphDataset(train_seq)
    val_ds = TemporalGraphDataset(val_seq)

    train_loader = DataLoader(train_ds, batch_size=4, shuffle=True, collate_fn=temporal_collate_fn)
    val_loader = DataLoader(val_ds, batch_size=4, shuffle=False, collate_fn=temporal_collate_fn)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TGNN(node_features=18, edge_features=22).to(device)

    criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor([0.3, 0.7]).to(device))
    optim = torch.optim.Adam(model.parameters(), lr=0.002)

    for epoch in range(1, 31):
        model.train()
        loss_sum = 0

        for batch_graphs, batch_labels in train_loader:
            batch_graphs = [g.to(device) for g in batch_graphs]
            batch_labels = batch_labels.to(device)

            optim.zero_grad()
            out = model(batch_graphs)
            loss = criterion(out, batch_labels)
            loss.backward()
            optim.step()

            loss_sum += loss.item()

        # ---- validation ----
        model.eval()
        correct = 0
        total = 0

        with torch.no_grad():
            for batch_graphs, batch_labels in val_loader:
                batch_graphs = [g.to(device) for g in batch_graphs]
                batch_labels = batch_labels.to(device)

                preds = model(batch_graphs).argmax(dim=1)
                correct += (preds == batch_labels).sum().item()
                total += batch_labels.size(0)

        acc = correct / total if total > 0 else 0
        print(f"Epoch {epoch} | Loss {loss_sum:.3f} | Val Acc {acc:.3f}")

    torch.save(model.state_dict(), "sentinel_tgnn.pt")
    print("Model saved as sentinel_tgnn.pt")


if __name__ == "__main__":
    train_tgnn()
