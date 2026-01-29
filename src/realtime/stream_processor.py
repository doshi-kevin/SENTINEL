# src/realtime/stream_processor.py

from src.realtime.event_buffer import EventBuffer
from src.pipeline.graph_constructor import build_graph
from src.pipeline.feature_engineer import compute_features

class StreamProcessor:
    def __init__(self):
        self.buffer = EventBuffer()

    def push(self, event):
        self.buffer.add_event(event)
        window = self.buffer.get_window()

        if len(window) == 0:
            return None

        G = build_graph(window)
        G = compute_features(G)

        return G
