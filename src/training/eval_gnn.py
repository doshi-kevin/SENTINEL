import torch
from torch_geometric.loader import DataLoader
from src.dataset.sentinel_pyg_dataset import SentinelGraphDataset
from src.models.gnn_sage import GraphSAGE

def evaluate():
    dataset = SentinelGraphDataset(
        graphs_dir="data/model_ready/graphs",
        labels_csv="data/model_ready/labels.csv"
    )

    loader = DataLoader(dataset, batch_size=4)

    # MUST MATCH THE TRAINING SCRIPT EXACTLY
    model = GraphSAGE(
        in_channels=11,
        edge_channels=22,
        hidden_channels=64,
        num_classes=2
    )

    # LOAD THE CORRECT CHECKPOINT
    model.load_state_dict(torch.load("sentinel_gnn_v4.pt"))
    model.eval()

    correct = 0
    total = 0

    with torch.no_grad():
        for batch in loader:
            out = model(batch)
            preds = out.argmax(dim=1)
            correct += (preds == batch.y).sum().item()
            total += batch.y.size(0)

    print(f"Accuracy: {correct / total:.3f}")

if __name__ == "__main__":
    evaluate()
