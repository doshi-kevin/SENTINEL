"""
Stream processor — Phase 6 placeholder.

The pre-pivot implementation imported `build_graph` and `compute_features` as
free functions; both are class methods (`GraphConstructor.build_graph`,
`FeatureEngineer.compute_features`) so the import never resolved. Rewriting
this against the current pipeline is part of Phase 6 (real-time pipeline).
"""
from .event_buffer import EventBuffer


class StreamProcessor:
    def __init__(self):
        self.buffer = EventBuffer()

    def push(self, event):
        self.buffer.add_event(event)
        window = self.buffer.get_window()
        if len(window) == 0:
            return None
        raise NotImplementedError(
            "StreamProcessor.push() is not yet wired to "
            "src.sentinel_z.pipeline.{graph_constructor,feature_engineer} — "
            "see roadmap/06_realtime_pipeline.md"
        )
