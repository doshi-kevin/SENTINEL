"""
SENTINEL-Z Self-Supervised Encoder Training

Trains the semantic graph encoder using:
1. Contrastive learning on graph pairs
2. Masked edge prediction
"""

import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import time


# ============================================================
# Data Loading
# ============================================================

class GraphDataset(Dataset):
    """Dataset for loading graph JSON files."""

    def __init__(self, graphs_dir: str, labels_csv: str, max_nodes: int = 500):
        self.graphs_dir = Path(graphs_dir)
        self.labels = pd.read_csv(labels_csv)
        self.max_nodes = max_nodes

        # Filter to valid graphs
        self.valid_indices = []
        for idx in range(len(self.labels)):
            graph_path = self.graphs_dir / f"window_{idx:05d}.json"
            if graph_path.exists():
                self.valid_indices.append(idx)

        print(f"Found {len(self.valid_indices)} valid graphs")

    def __len__(self):
        return len(self.valid_indices)

    def __getitem__(self, idx: int) -> Dict:
        real_idx = self.valid_indices[idx]
        graph_path = self.graphs_dir / f"window_{real_idx:05d}.json"

        with open(graph_path, 'r') as f:
            graph_data = json.load(f)

        label = self.labels.iloc[real_idx]['label']

        return self.process_graph(graph_data, label)

    def process_graph(self, graph_data: Dict, label: int) -> Dict:
        """Convert graph JSON to tensors."""
        nodes = graph_data['nodes']
        links = graph_data['links']

        num_nodes = min(len(nodes), self.max_nodes)

        # Node features: [node_type_flag, in_degree, out_degree, degree, event_count]
        node_features = torch.zeros(num_nodes, 5)

        for i, node in enumerate(nodes[:num_nodes]):
            node_features[i, 0] = node.get('node_type_flag', 0)
            node_features[i, 1] = min(node.get('in_degree', 0), 100) / 100  # Normalize
            node_features[i, 2] = min(node.get('out_degree', 0), 100) / 100
            node_features[i, 3] = min(node.get('degree', 0), 200) / 200
            node_features[i, 4] = min(node.get('event_count', 0), 1000) / 1000

        # Edge index
        edge_src = []
        edge_dst = []
        edge_weights = []

        for link in links:
            src = link['source']
            dst = link['target']
            if src < num_nodes and dst < num_nodes:
                edge_src.append(src)
                edge_dst.append(dst)
                edge_weights.append(min(link.get('count', 1), 100) / 100)

        if len(edge_src) > 0:
            edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.long)
            edge_weight = torch.tensor(edge_weights, dtype=torch.float)
        else:
            edge_index = torch.zeros(2, 0, dtype=torch.long)
            edge_weight = torch.zeros(0, dtype=torch.float)

        return {
            'x': node_features,
            'edge_index': edge_index,
            'edge_weight': edge_weight,
            'num_nodes': num_nodes,
            'label': torch.tensor(label, dtype=torch.long)
        }


def collate_graphs(batch: List[Dict]) -> Dict:
    """Collate graphs into a batch with padding."""
    max_nodes = max(b['num_nodes'] for b in batch)
    max_edges = max(b['edge_index'].shape[1] for b in batch)

    batch_size = len(batch)

    # Pad node features
    x = torch.zeros(batch_size, max_nodes, 5)
    node_mask = torch.zeros(batch_size, max_nodes, dtype=torch.bool)

    # Pad edges
    edge_indices = torch.zeros(batch_size, 2, max_edges, dtype=torch.long)
    edge_weights = torch.zeros(batch_size, max_edges)
    edge_mask = torch.zeros(batch_size, max_edges, dtype=torch.bool)

    labels = torch.zeros(batch_size, dtype=torch.long)

    for i, b in enumerate(batch):
        n = b['num_nodes']
        e = b['edge_index'].shape[1]

        x[i, :n] = b['x']
        node_mask[i, :n] = True

        if e > 0:
            edge_indices[i, :, :e] = b['edge_index']
            edge_weights[i, :e] = b['edge_weight']
            edge_mask[i, :e] = True

        labels[i] = b['label']

    return {
        'x': x,
        'node_mask': node_mask,
        'edge_index': edge_indices,
        'edge_weight': edge_weights,
        'edge_mask': edge_mask,
        'labels': labels,
        'batch_size': batch_size,
        'max_nodes': max_nodes
    }


# ============================================================
# Model Architecture
# ============================================================

class GraphAttention(nn.Module):
    """Simple graph attention layer."""

    def __init__(self, in_dim: int, out_dim: int, heads: int = 4):
        super().__init__()
        self.heads = heads
        self.head_dim = out_dim // heads

        self.query = nn.Linear(in_dim, out_dim)
        self.key = nn.Linear(in_dim, out_dim)
        self.value = nn.Linear(in_dim, out_dim)
        self.out = nn.Linear(out_dim, out_dim)

    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """
        x: [batch, nodes, in_dim]
        mask: [batch, nodes] boolean mask
        """
        B, N, _ = x.shape

        q = self.query(x).view(B, N, self.heads, self.head_dim).transpose(1, 2)
        k = self.key(x).view(B, N, self.heads, self.head_dim).transpose(1, 2)
        v = self.value(x).view(B, N, self.heads, self.head_dim).transpose(1, 2)

        # Attention scores
        scores = torch.matmul(q, k.transpose(-2, -1)) / (self.head_dim ** 0.5)

        # Mask padding
        mask_expanded = mask.unsqueeze(1).unsqueeze(2)  # [B, 1, 1, N]
        scores = scores.masked_fill(~mask_expanded, float('-inf'))

        attn = F.softmax(scores, dim=-1)
        attn = torch.nan_to_num(attn, 0.0)  # Handle all-masked case

        out = torch.matmul(attn, v)
        out = out.transpose(1, 2).contiguous().view(B, N, -1)

        return self.out(out)


class GraphEncoder(nn.Module):
    """Graph encoder with attention-based message passing."""

    def __init__(self, node_dim: int = 5, hidden_dim: int = 64, output_dim: int = 128, num_layers: int = 3):
        super().__init__()

        self.input_proj = nn.Linear(node_dim, hidden_dim)

        self.layers = nn.ModuleList([
            GraphAttention(hidden_dim, hidden_dim, heads=4)
            for _ in range(num_layers)
        ])

        self.norms = nn.ModuleList([
            nn.LayerNorm(hidden_dim)
            for _ in range(num_layers)
        ])

        self.output_proj = nn.Linear(hidden_dim, output_dim)

    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            node_embeddings: [batch, nodes, output_dim]
            graph_embedding: [batch, output_dim]
        """
        h = self.input_proj(x)

        for layer, norm in zip(self.layers, self.norms):
            h = h + layer(h, mask)
            h = norm(h)

        node_embeddings = self.output_proj(h)

        # Global pooling (mean of valid nodes)
        mask_float = mask.unsqueeze(-1).float()
        graph_embedding = (node_embeddings * mask_float).sum(dim=1) / mask_float.sum(dim=1).clamp(min=1)

        return node_embeddings, graph_embedding


class SentinelZModel(nn.Module):
    """Complete SENTINEL-Z model for self-supervised learning."""

    def __init__(self, node_dim: int = 5, hidden_dim: int = 64, output_dim: int = 128):
        super().__init__()

        self.encoder = GraphEncoder(node_dim, hidden_dim, output_dim)

        # Projection head for contrastive learning
        self.projection = nn.Sequential(
            nn.Linear(output_dim, output_dim),
            nn.ReLU(),
            nn.Linear(output_dim, output_dim)
        )

        # Edge prediction head
        self.edge_predictor = nn.Sequential(
            nn.Linear(output_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

        # Anomaly scoring head
        self.anomaly_head = nn.Sequential(
            nn.Linear(output_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, batch: Dict) -> Dict:
        x = batch['x']
        mask = batch['node_mask']

        node_emb, graph_emb = self.encoder(x, mask)
        proj = self.projection(graph_emb)

        return {
            'node_embeddings': node_emb,
            'graph_embedding': graph_emb,
            'projection': proj
        }

    def compute_anomaly_score(self, batch: Dict) -> torch.Tensor:
        """Compute per-graph anomaly scores."""
        outputs = self.forward(batch)
        scores = self.anomaly_head(outputs['graph_embedding'])
        return torch.sigmoid(scores).squeeze(-1)


# ============================================================
# Training
# ============================================================

def contrastive_loss(proj1: torch.Tensor, proj2: torch.Tensor, temperature: float = 0.5) -> torch.Tensor:
    """NT-Xent contrastive loss."""
    batch_size = proj1.shape[0]

    # Normalize
    proj1 = F.normalize(proj1, dim=-1)
    proj2 = F.normalize(proj2, dim=-1)

    # Similarity matrix
    sim = torch.matmul(proj1, proj2.T) / temperature

    # Labels: positive pairs are diagonal
    labels = torch.arange(batch_size, device=proj1.device)

    # Cross entropy both ways
    loss1 = F.cross_entropy(sim, labels)
    loss2 = F.cross_entropy(sim.T, labels)

    return (loss1 + loss2) / 2


def augment_graph(batch: Dict, drop_rate: float = 0.1) -> Dict:
    """Create augmented view by dropping nodes/edges."""
    x = batch['x'].clone()
    mask = batch['node_mask'].clone()

    # Randomly zero out some node features
    drop_mask = torch.rand_like(x[:, :, 0]) < drop_rate
    x[drop_mask.unsqueeze(-1).expand_as(x)] = 0

    return {
        'x': x,
        'node_mask': mask,
        'edge_index': batch['edge_index'],
        'edge_weight': batch['edge_weight'],
        'edge_mask': batch['edge_mask']
    }


def train_epoch(model: nn.Module, dataloader: DataLoader, optimizer: torch.optim.Optimizer,
                device: torch.device) -> float:
    """Train for one epoch."""
    model.train()
    total_loss = 0

    for batch in dataloader:
        # Move to device
        batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}

        # Create two augmented views
        view1 = augment_graph(batch, drop_rate=0.1)
        view2 = augment_graph(batch, drop_rate=0.15)

        # Forward pass
        out1 = model(view1)
        out2 = model(view2)

        # Contrastive loss
        loss = contrastive_loss(out1['projection'], out2['projection'])

        # Backward
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(dataloader)


def evaluate(model: nn.Module, dataloader: DataLoader, device: torch.device) -> Dict:
    """Evaluate model on dataset."""
    model.eval()

    all_scores = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}

            scores = model.compute_anomaly_score(batch)
            all_scores.extend(scores.cpu().numpy())
            all_labels.extend(batch['labels'].cpu().numpy())

    all_scores = np.array(all_scores)
    all_labels = np.array(all_labels)

    # Compute metrics
    attack_scores = all_scores[all_labels == 1]
    benign_scores = all_scores[all_labels == 0]

    # Simple separation metric
    if len(attack_scores) > 0 and len(benign_scores) > 0:
        separation = attack_scores.mean() - benign_scores.mean()
    else:
        separation = 0.0

    return {
        'attack_mean': float(attack_scores.mean()) if len(attack_scores) > 0 else 0,
        'benign_mean': float(benign_scores.mean()) if len(benign_scores) > 0 else 0,
        'separation': separation
    }


def train_model(
    graphs_dir: str,
    labels_csv: str,
    output_path: str,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    hidden_dim: int = 64,
    output_dim: int = 128
):
    """Main training function."""
    print("="*60)
    print("SENTINEL-Z Self-Supervised Training")
    print("="*60)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")

    # Load dataset
    print("\nLoading dataset...")
    dataset = GraphDataset(graphs_dir, labels_csv)

    # Split into train/val
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_graphs)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_graphs)

    print(f"Train samples: {len(train_dataset)}")
    print(f"Val samples: {len(val_dataset)}")

    # Create model
    model = SentinelZModel(
        node_dim=5,
        hidden_dim=hidden_dim,
        output_dim=output_dim
    ).to(device)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {param_count:,}")

    # Optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)

    # Training loop
    print("\nTraining...")
    best_separation = -float('inf')

    for epoch in range(epochs):
        start = time.time()

        train_loss = train_epoch(model, train_loader, optimizer, device)
        val_metrics = evaluate(model, val_loader, device)

        scheduler.step()

        elapsed = time.time() - start

        print(f"Epoch {epoch+1:3d}/{epochs} | Loss: {train_loss:.4f} | "
              f"Attack: {val_metrics['attack_mean']:.3f} | Benign: {val_metrics['benign_mean']:.3f} | "
              f"Sep: {val_metrics['separation']:.3f} | {elapsed:.1f}s")

        # Save best model
        if val_metrics['separation'] > best_separation:
            best_separation = val_metrics['separation']
            torch.save({
                'model_state_dict': model.state_dict(),
                'epoch': epoch,
                'separation': best_separation
            }, output_path)

    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"Best separation: {best_separation:.4f}")
    print(f"Model saved to: {output_path}")

    return model


if __name__ == "__main__":
    train_model(
        graphs_dir="data/auto_processed/graphs",
        labels_csv="data/auto_processed/labels.csv",
        output_path="data/auto_processed/sentinel_z_model.pt",
        epochs=50,
        batch_size=32,
        learning_rate=1e-3,
        hidden_dim=64,
        output_dim=128
    )
