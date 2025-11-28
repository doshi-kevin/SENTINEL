import torch
import torch.nn as nn
from torch_geometric.nn import SAGEConv, global_mean_pool

class GraphSAGE(nn.Module):
    def __init__(self, in_channels=11, edge_channels=22, hidden_channels=64, num_classes=2):
        super().__init__()

        # We will combine node and edge features before convolution
        self.fc_edge = nn.Linear(edge_channels, in_channels)

        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, hidden_channels)
        self.conv3 = SAGEConv(hidden_channels, hidden_channels)

        self.relu = nn.ReLU()
        self.drop = nn.Dropout(0.3)
        self.fc = nn.Linear(hidden_channels, num_classes)

    def forward(self, data):
        x, edge_index, edge_attr, batch = (
            data.x,
            data.edge_index,
            data.edge_attr,
            data.batch,
        )

        # convert each edge’s feature into a correction vector
        edge_correction = self.fc_edge(edge_attr)

        # aggregate corrections onto nodes
        # NOTE: simple scatter-add for now
        x = x.clone()
        for i, (src, dst) in enumerate(edge_index.t()):
            x[src] += edge_correction[i]

        x = self.relu(self.conv1(x, edge_index))
        x = self.relu(self.conv2(x, edge_index))
        x = self.relu(self.conv3(x, edge_index))

        x = global_mean_pool(x, batch)
        x = self.drop(x)

        return self.fc(x)
