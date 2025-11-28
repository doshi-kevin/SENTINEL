import torch
from torch_geometric.loader import DataLoader
from sklearn.model_selection import train_test_split

from src.dataset.sentinel_pyg_dataset import SentinelGraphDataset
from src.models.gnn_sage import GraphSAGE

def train():
    dataset = SentinelGraphDataset(
        graphs_dir="data/model_ready/graphs",
        labels_csv="data/model_ready/labels.csv"
    )

    labels = [dataset[i].y.item() for i in range(len(dataset))]

    train_idx, val_idx = train_test_split(
        list(range(len(dataset))),
        test_size=0.2,
        shuffle=True,
        stratify=labels
    )

    train_data = [dataset[i] for i in train_idx]
    val_data = [dataset[i] for i in val_idx]

    train_loader = DataLoader(train_data, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=8)

    model = GraphSAGE(
    in_channels=11,
    edge_channels=22)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor([0.3, 0.7]).to(device))
    optim = torch.optim.Adam(model.parameters(), lr=0.002)

    for epoch in range(1, 41):
        model.train()
        loss_acc = 0

        for batch in train_loader:
            batch = batch.to(device)
            optim.zero_grad()

            out = model(batch)
            loss = criterion(out, batch.y)
            loss.backward()
            optim.step()

            loss_acc += loss.item()

        # validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = batch.to(device)
                preds = model(batch).argmax(dim=1)
                correct += (preds == batch.y).sum().item()
                total += batch.y.size(0)

        acc = correct / total if total > 0 else 0
        print(f"Epoch {epoch} | Loss {loss_acc:.3f} | Val Acc {acc:.3f}")

    torch.save(model.state_dict(), "sentinel_gnn_v4.pt")
    print("Model saved as sentinel_gnn_v4.pt")


if __name__ == "__main__":
    train()
