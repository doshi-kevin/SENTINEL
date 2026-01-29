"""
Self-Supervised Semantic Encoder

THE CORE ML INNOVATION for zero-shot APT detection.

Key Insight: Instead of supervised learning (needs labeled attacks),
we use self-supervised learning to model "normal behavior":

1. Contrastive Learning: Learn that temporally close windows are similar
2. Masked Prediction: Predict masked semantic flows from context
3. Causal Flow Modeling: Learn which semantic flows "should" follow others

The model learns what NORMAL looks like without any attack labels.
At inference, anything deviating from "normal" is flagged as anomaly.

This enables ZERO-SHOT detection: we can identify attack patterns
the model has NEVER seen before.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, global_mean_pool, global_max_pool
from torch_geometric.data import Data, Batch
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass


class SemanticNodeEncoder(nn.Module):
    """
    Encodes semantic node types into learnable embeddings.
    This is what enables semantic abstraction.
    """

    def __init__(
        self,
        num_semantic_types: int = 20,
        embedding_dim: int = 32,
        feature_dim: int = 18
    ):
        super().__init__()

        # Learnable embeddings for semantic types
        self.type_embedding = nn.Embedding(num_semantic_types, embedding_dim)

        # Feature projection
        self.feature_proj = nn.Sequential(
            nn.Linear(feature_dim, embedding_dim),
            nn.ReLU(),
            nn.LayerNorm(embedding_dim)
        )

        # Combine type + features
        self.combine = nn.Sequential(
            nn.Linear(embedding_dim * 2, embedding_dim),
            nn.ReLU(),
            nn.LayerNorm(embedding_dim)
        )

    def forward(self, semantic_type_ids: torch.Tensor, features: torch.Tensor) -> torch.Tensor:
        """
        Args:
            semantic_type_ids: [num_nodes] - semantic type index for each node
            features: [num_nodes, feature_dim] - node features

        Returns:
            [num_nodes, embedding_dim] - node embeddings
        """
        type_emb = self.type_embedding(semantic_type_ids)  # [N, emb_dim]
        feat_emb = self.feature_proj(features)  # [N, emb_dim]

        combined = torch.cat([type_emb, feat_emb], dim=-1)  # [N, 2*emb_dim]
        return self.combine(combined)  # [N, emb_dim]


class SemanticGraphEncoder(nn.Module):
    """
    Encodes a semantic graph into a fixed-size representation.
    Uses GraphSAGE with semantic-aware aggregation.
    """

    def __init__(
        self,
        node_dim: int = 32,
        hidden_dim: int = 64,
        output_dim: int = 128,
        num_layers: int = 3,
        dropout: float = 0.1
    ):
        super().__init__()

        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()

        # First layer
        self.convs.append(SAGEConv(node_dim, hidden_dim))
        self.norms.append(nn.LayerNorm(hidden_dim))

        # Middle layers
        for _ in range(num_layers - 2):
            self.convs.append(SAGEConv(hidden_dim, hidden_dim))
            self.norms.append(nn.LayerNorm(hidden_dim))

        # Last layer
        self.convs.append(SAGEConv(hidden_dim, output_dim))
        self.norms.append(nn.LayerNorm(output_dim))

        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor, batch: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            x: [num_nodes, node_dim] - node embeddings
            edge_index: [2, num_edges] - edge connectivity
            batch: [num_nodes] - batch assignment for each node

        Returns:
            [batch_size, output_dim] - graph-level embeddings
        """
        for conv, norm in zip(self.convs[:-1], self.norms[:-1]):
            x = conv(x, edge_index)
            x = norm(x)
            x = F.relu(x)
            x = self.dropout(x)

        x = self.convs[-1](x, edge_index)
        x = self.norms[-1](x)

        # Global pooling (mean + max)
        if batch is not None:
            x_mean = global_mean_pool(x, batch)
            x_max = global_max_pool(x, batch)
        else:
            x_mean = x.mean(dim=0, keepdim=True)
            x_max = x.max(dim=0, keepdim=True)[0]

        return torch.cat([x_mean, x_max], dim=-1)  # [batch, 2*output_dim]


class TemporalContextEncoder(nn.Module):
    """
    Encodes temporal context from sequence of graph embeddings.
    Uses Transformer-style attention for variable-length sequences.
    """

    def __init__(
        self,
        input_dim: int = 256,
        hidden_dim: int = 128,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1
    ):
        super().__init__()

        self.input_proj = nn.Linear(input_dim, hidden_dim)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)

        # Positional encoding for temporal order
        self.pos_encoding = nn.Parameter(torch.randn(1, 100, hidden_dim) * 0.02)

    def forward(self, graph_embeddings: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            graph_embeddings: [batch, seq_len, input_dim] - sequence of graph embeddings
            mask: [batch, seq_len] - mask for padding (True = masked)

        Returns:
            [batch, hidden_dim] - temporal context embedding
        """
        batch_size, seq_len, _ = graph_embeddings.shape

        x = self.input_proj(graph_embeddings)  # [B, S, hidden]
        x = x + self.pos_encoding[:, :seq_len, :]  # Add positional encoding

        x = self.transformer(x, src_key_padding_mask=mask)  # [B, S, hidden]

        # Use CLS-style aggregation (mean of non-masked positions)
        if mask is not None:
            mask_expanded = (~mask).unsqueeze(-1).float()
            x = (x * mask_expanded).sum(dim=1) / mask_expanded.sum(dim=1).clamp(min=1)
        else:
            x = x.mean(dim=1)

        return x


class ContrastiveLoss(nn.Module):
    """
    NT-Xent contrastive loss for self-supervised learning.

    Positive pairs: temporally adjacent windows
    Negative pairs: windows from different time periods
    """

    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(self, z_i: torch.Tensor, z_j: torch.Tensor) -> torch.Tensor:
        """
        Args:
            z_i: [batch, dim] - embeddings of anchor samples
            z_j: [batch, dim] - embeddings of positive samples

        Returns:
            Contrastive loss
        """
        batch_size = z_i.shape[0]

        # Normalize
        z_i = F.normalize(z_i, dim=1)
        z_j = F.normalize(z_j, dim=1)

        # Compute similarity matrix
        z = torch.cat([z_i, z_j], dim=0)  # [2B, dim]
        sim = torch.mm(z, z.t()) / self.temperature  # [2B, 2B]

        # Mask out self-similarity
        mask = torch.eye(2 * batch_size, device=z.device).bool()
        sim = sim.masked_fill(mask, float('-inf'))

        # Positive pairs: (i, i+B) and (i+B, i)
        labels = torch.cat([
            torch.arange(batch_size, 2 * batch_size),
            torch.arange(batch_size)
        ]).to(z.device)

        loss = F.cross_entropy(sim, labels)
        return loss


class MaskedFlowPrediction(nn.Module):
    """
    Masked prediction head for self-supervised learning.
    Predicts masked semantic flows from context.

    This teaches the model what flows "should" appear given the context.
    """

    def __init__(
        self,
        context_dim: int = 128,
        num_edge_types: int = 12,
        num_node_types: int = 20
    ):
        super().__init__()

        # Predict edge type distribution
        self.edge_predictor = nn.Sequential(
            nn.Linear(context_dim, context_dim),
            nn.ReLU(),
            nn.Linear(context_dim, num_edge_types)
        )

        # Predict node type distribution
        self.node_predictor = nn.Sequential(
            nn.Linear(context_dim, context_dim),
            nn.ReLU(),
            nn.Linear(context_dim, num_node_types)
        )

    def forward(self, context: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            context: [batch, context_dim] - temporal context embedding

        Returns:
            edge_logits: [batch, num_edge_types] - predicted edge type distribution
            node_logits: [batch, num_node_types] - predicted node type distribution
        """
        edge_logits = self.edge_predictor(context)
        node_logits = self.node_predictor(context)
        return edge_logits, node_logits


class SentinelZEncoder(nn.Module):
    """
    Complete SENTINEL-Z Self-Supervised Encoder.

    Combines:
    1. Semantic node encoding
    2. Graph-level encoding (GraphSAGE)
    3. Temporal context encoding (Transformer)
    4. Contrastive learning objective
    5. Masked prediction objective

    The model learns what "normal" behavior looks like without attack labels.
    """

    def __init__(
        self,
        num_semantic_types: int = 20,
        num_edge_types: int = 12,
        node_feature_dim: int = 18,
        node_embed_dim: int = 32,
        graph_hidden_dim: int = 64,
        graph_output_dim: int = 128,
        temporal_hidden_dim: int = 128,
        num_gnn_layers: int = 3,
        num_transformer_layers: int = 2,
        dropout: float = 0.1
    ):
        super().__init__()

        self.num_semantic_types = num_semantic_types
        self.num_edge_types = num_edge_types

        # Node encoder
        self.node_encoder = SemanticNodeEncoder(
            num_semantic_types=num_semantic_types,
            embedding_dim=node_embed_dim,
            feature_dim=node_feature_dim
        )

        # Graph encoder
        self.graph_encoder = SemanticGraphEncoder(
            node_dim=node_embed_dim,
            hidden_dim=graph_hidden_dim,
            output_dim=graph_output_dim,
            num_layers=num_gnn_layers,
            dropout=dropout
        )

        # Graph output is 2*output_dim due to mean+max pooling
        graph_repr_dim = graph_output_dim * 2

        # Temporal encoder
        self.temporal_encoder = TemporalContextEncoder(
            input_dim=graph_repr_dim,
            hidden_dim=temporal_hidden_dim,
            num_layers=num_transformer_layers,
            dropout=dropout
        )

        # Self-supervised heads
        self.contrastive_proj = nn.Sequential(
            nn.Linear(temporal_hidden_dim, temporal_hidden_dim),
            nn.ReLU(),
            nn.Linear(temporal_hidden_dim, 64)
        )

        self.masked_predictor = MaskedFlowPrediction(
            context_dim=temporal_hidden_dim,
            num_edge_types=num_edge_types,
            num_node_types=num_semantic_types
        )

        # Anomaly scoring head
        self.anomaly_scorer = nn.Sequential(
            nn.Linear(temporal_hidden_dim, temporal_hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(temporal_hidden_dim // 2, 1)
        )

        # Loss functions
        self.contrastive_loss = ContrastiveLoss()

    def encode_graph(
        self,
        semantic_types: torch.Tensor,
        features: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """Encode a single graph or batch of graphs."""
        node_emb = self.node_encoder(semantic_types, features)
        graph_emb = self.graph_encoder(node_emb, edge_index, batch)
        return graph_emb

    def encode_sequence(
        self,
        graph_embeddings: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """Encode a sequence of graph embeddings."""
        return self.temporal_encoder(graph_embeddings, mask)

    def forward(
        self,
        semantic_types: torch.Tensor,
        features: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
        sequence_ids: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Full forward pass.

        Returns dict with:
            - graph_embedding: Graph-level representation
            - context_embedding: Temporal context representation
            - anomaly_score: Predicted anomaly score
            - contrastive_features: Features for contrastive learning
        """
        graph_emb = self.encode_graph(semantic_types, features, edge_index, batch)

        # If we have sequence information, encode temporal context
        if sequence_ids is not None:
            # Group by sequence and encode
            # (simplified - in practice need proper batching)
            context_emb = self.temporal_encoder(graph_emb.unsqueeze(0))
        else:
            # Single graph - use graph embedding directly
            context_emb = graph_emb[:, :self.temporal_encoder.input_proj.out_features]

        # Compute outputs
        anomaly_score = self.anomaly_scorer(context_emb).squeeze(-1)
        contrastive_features = self.contrastive_proj(context_emb)

        return {
            'graph_embedding': graph_emb,
            'context_embedding': context_emb,
            'anomaly_score': anomaly_score,
            'contrastive_features': contrastive_features
        }

    def compute_self_supervised_loss(
        self,
        anchor_output: Dict[str, torch.Tensor],
        positive_output: Dict[str, torch.Tensor],
        target_edge_dist: torch.Tensor,
        target_node_dist: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """
        Compute self-supervised training losses.

        Args:
            anchor_output: Output from anchor samples
            positive_output: Output from positive (adjacent) samples
            target_edge_dist: Ground truth edge type distribution
            target_node_dist: Ground truth node type distribution

        Returns:
            Dict with individual losses and total loss
        """
        # Contrastive loss
        contrastive = self.contrastive_loss(
            anchor_output['contrastive_features'],
            positive_output['contrastive_features']
        )

        # Masked prediction loss
        edge_logits, node_logits = self.masked_predictor(anchor_output['context_embedding'])
        edge_loss = F.cross_entropy(edge_logits, target_edge_dist)
        node_loss = F.cross_entropy(node_logits, target_node_dist)

        total = contrastive + edge_loss + node_loss

        return {
            'contrastive': contrastive,
            'edge_prediction': edge_loss,
            'node_prediction': node_loss,
            'total': total
        }


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection on a graph sequence."""
    window_ids: List[int]
    anomaly_scores: List[float]
    is_anomaly: List[bool]
    threshold: float
    explanation: str

    def to_dict(self) -> dict:
        return {
            'window_ids': self.window_ids,
            'anomaly_scores': self.anomaly_scores,
            'is_anomaly': self.is_anomaly,
            'threshold': self.threshold,
            'explanation': self.explanation
        }


class ZeroShotDetector:
    """
    Zero-shot anomaly detector using trained SENTINEL-Z encoder.

    No attack labels needed - detects anomalies based on deviation
    from learned normal behavior.
    """

    def __init__(self, encoder: SentinelZEncoder, threshold: float = 0.5):
        self.encoder = encoder
        self.threshold = threshold
        self.encoder.eval()

        # Statistics from normal data (computed during calibration)
        self.normal_mean = 0.0
        self.normal_std = 1.0

    def calibrate(self, normal_graphs: List[Data]) -> None:
        """
        Calibrate threshold using known-normal data.
        This is the only "supervision" - knowing what's normal.
        """
        scores = []

        with torch.no_grad():
            for graph in normal_graphs:
                output = self.encoder(
                    semantic_types=graph.semantic_types,
                    features=graph.x,
                    edge_index=graph.edge_index
                )
                scores.append(output['anomaly_score'].item())

        self.normal_mean = np.mean(scores)
        self.normal_std = np.std(scores) + 1e-6

        # Set threshold at 2 standard deviations
        self.threshold = self.normal_mean + 2 * self.normal_std

    def detect(self, graphs: List[Data], window_ids: List[int]) -> AnomalyDetectionResult:
        """
        Detect anomalies in a sequence of graphs.

        Args:
            graphs: List of PyG Data objects with semantic types
            window_ids: Corresponding window IDs

        Returns:
            AnomalyDetectionResult with scores and predictions
        """
        scores = []
        is_anomaly = []

        with torch.no_grad():
            for graph in graphs:
                output = self.encoder(
                    semantic_types=graph.semantic_types,
                    features=graph.x,
                    edge_index=graph.edge_index
                )
                score = output['anomaly_score'].item()
                normalized_score = (score - self.normal_mean) / self.normal_std

                scores.append(normalized_score)
                is_anomaly.append(normalized_score > self.threshold)

        # Generate explanation
        num_anomalies = sum(is_anomaly)
        if num_anomalies == 0:
            explanation = "No anomalies detected. All windows within normal behavior bounds."
        else:
            anomaly_windows = [wid for wid, anom in zip(window_ids, is_anomaly) if anom]
            max_score = max(scores)
            explanation = (
                f"Detected {num_anomalies} anomalous windows: {anomaly_windows}. "
                f"Peak anomaly score: {max_score:.2f} (threshold: {self.threshold:.2f}). "
                f"This indicates behavior significantly deviating from learned normal patterns."
            )

        return AnomalyDetectionResult(
            window_ids=window_ids,
            anomaly_scores=scores,
            is_anomaly=is_anomaly,
            threshold=self.threshold,
            explanation=explanation
        )
