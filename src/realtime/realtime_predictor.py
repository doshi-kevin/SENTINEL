# src/realtime/realtime_predictor.py

import torch
from src.models.tgnn import TGNN
from src.train_utils import prepare_sequence

class RealTimePredictor:
    def __init__(self, model_path="sentinel_tgnn.pt"):
        self.model = TGNN(input_dim=18, hidden_dim=64)
        self.model.load_state_dict(torch.load(model_path))
        self.model.eval()

        self.sliding = []

    def push_graph(self, graph_tensor):
        self.sliding.append(graph_tensor)
        if len(self.sliding) < 3:
            return None

        seq = self.sliding[-3:]
        out = self.model(seq)
        prediction = torch.argmax(out).item()
        return prediction
