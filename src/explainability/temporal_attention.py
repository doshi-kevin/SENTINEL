# src/explainability/temporal_attention.py

import torch
import torch.nn as nn
import torch.nn.functional as F


class TemporalAttention(nn.Module):
    """
    Learns attention weights over sequence of graph embeddings.
    Input: (batch, seq_len, hidden_dim)
    Output: (batch, hidden_dim), attention_weights
    """

    def __init__(self, hidden_dim=128):
        super().__init__()
        self.attn = nn.Linear(hidden_dim, 1)

    def forward(self, seq_embeddings):
        # seq_embeddings shape: (batch, seq_len, hidden_dim)
        scores = self.attn(seq_embeddings).squeeze(-1)  # (batch, seq_len)
        weights = F.softmax(scores, dim=1)               # attention weights
        weighted_sum = torch.sum(seq_embeddings * weights.unsqueeze(-1), dim=1)
        return weighted_sum, weights
