import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATv2Conv, global_mean_pool, global_max_pool

class SentinelGNN(nn.Module):
    def __init__(self, input_dim, hidden_dim=64, embedding_dim=32, num_layers=3, edge_dim=None):
        super(SentinelGNN, self).__init__()
        
        self.convs = nn.ModuleList()
        self.bns = nn.ModuleList()
        
        # Input layer
        # Note: GATv2Conv adds dimensions if heads > 1. We keep concat=False for simplicity or use projection.
        # But usually concat=True is better. Let's use heads=4 for first layers.
        self.conv1 = GATv2Conv(input_dim, hidden_dim, heads=4, concat=False, edge_dim=edge_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        
        # Hidden layers
        for _ in range(num_layers - 2):
            self.convs.append(GATv2Conv(hidden_dim, hidden_dim, heads=4, concat=False, edge_dim=edge_dim))
            self.bns.append(nn.BatchNorm1d(hidden_dim))
            
        # Output conv layer (to embedding)
        self.conv_out = GATv2Conv(hidden_dim, embedding_dim, heads=1, concat=False, edge_dim=edge_dim)
        self.bn_out = nn.BatchNorm1d(embedding_dim)
        
        # Projection Head for Contrastive Learning (SimCLR style)
        # 32 -> 64 -> 32
        self.projection_head = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, embedding_dim)
        )
        
    def forward(self, x, edge_index, edge_attr=None, batch=None):
        # Layer 1
        x = self.conv1(x, edge_index, edge_attr=edge_attr)
        x = self.bn1(x)
        x = F.elu(x)
        x = F.dropout(x, p=0.3, training=self.training)
        
        # Hidden Layers
        for conv, bn in zip(self.convs, self.bns):
            x = conv(x, edge_index, edge_attr=edge_attr)
            x = bn(x)
            x = F.elu(x)
            x = F.dropout(x, p=0.3, training=self.training)
            
        # Output Conv
        x = self.conv_out(x, edge_index, edge_attr=edge_attr)
        x = self.bn_out(x)
        # No activation for the final node embedding usually, but let's keep it raw for pooling?
        # Typically we pool now.
        
        # Pooling (Readout)
        # Combine mean and max pooling for robustness
        x_mean = global_mean_pool(x, batch)
        x_max = global_max_pool(x, batch)
        
        # Representations [Batch, Embedding*2] if we concatenated, but I'll add them or just use mean.
        # Let's use mean for now to match embedding_dim
        h = x_mean
        
        return h

    def project(self, h):
        return self.projection_head(h)

if __name__ == "__main__":
    # Smoke test
    model = SentinelGNN(input_dim=19, edge_dim=12)
    print(model)
    
    # Dummy data
    x = torch.randn(10, 19)
    edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]], dtype=torch.long)
    edge_attr = torch.randn(4, 12)
    batch = torch.zeros(10, dtype=torch.long) # Single graph batch
    
    z = model(x, edge_index, edge_attr, batch)
    print(f"Embedding shape: {z.shape}")
    
    p = model.project(z)
    print(f"Projection shape: {p.shape}")
