# src/models/tgnn.py

import torch
import torch.nn as nn
from torch_geometric.nn import SAGEConv, global_mean_pool
from src.explainability.temporal_attention import TemporalAttention

class GraphSAGEEncoder(nn.Module):
    """
    Encodes a single graph into a dense vector.
    Correctly matches node features (18) + edge features (22).
    """
    def __init__(self, in_channels=18, edge_channels=22,
                 hidden_channels=64, out_channels=128):
        super().__init__()

        # Correct: 22 → 18
        self.edge_fc = nn.Linear(edge_channels, in_channels)

        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, hidden_channels)

        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)

        self.project = nn.Linear(hidden_channels, out_channels)

    def forward(self, data):
        x, edge_index, edge_attr, batch = (
            data.x,
            data.edge_index,
            data.edge_attr,
            data.batch,
        )

        # Update edges into 18-d correction vector
        edge_update = self.edge_fc(edge_attr)  # shape: [num_edges, 18]

        # Apply edge updates to nodes
        x = x.clone()
        for i, (src, dst) in enumerate(edge_index.t()):
            x[src] += edge_update[i]  # both tensors now size 18

        x = self.relu(self.conv1(x, edge_index))
        x = self.relu(self.conv2(x, edge_index))

        x = global_mean_pool(x, batch)
        x = self.project(x)

        return x



class TGNN(nn.Module):
    def __init__(self, node_features=18, edge_features=22,
                 gnn_hidden=64, lstm_hidden=128,
                 lstm_layers=1, num_classes=2):
        super().__init__()

        self.encoder = GraphSAGEEncoder(
            in_channels=node_features,
            edge_channels=edge_features,
            hidden_channels=gnn_hidden,
            out_channels=lstm_hidden,
        )

        self.lstm = nn.LSTM(
            input_size=lstm_hidden,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
        )

        self.temp_attn = TemporalAttention(hidden_dim=lstm_hidden)

        self.classifier = nn.Sequential(
            nn.Linear(lstm_hidden, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes),
        )

    def forward(self, graph_sequence):
        # Encode each graph in sequence
        embeddings = []
        for t in range(len(graph_sequence)):
            emb_t = self.encoder(graph_sequence[t])
            embeddings.append(emb_t)

        seq = torch.stack(embeddings, dim=1)   # (batch, seq_len, hidden_dim)

        lstm_out, _ = self.lstm(seq)

        # 🔥 ADD TEMPORAL ATTENTION FOR EXPLAINABILITY
        final_embedding, attn_weights = self.temp_attn(lstm_out)

        logits = self.classifier(final_embedding)

        return logits, attn_weights
