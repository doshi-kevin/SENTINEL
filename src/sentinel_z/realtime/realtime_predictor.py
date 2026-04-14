"""
Real-time predictor — Phase 6 placeholder.

The pre-pivot implementation depended on a TGNN model (`src.models.tgnn`)
and a `prepare_sequence` helper (`src.train_utils`); both belonged to the
temporal-GNN explanation path that was abandoned during the Phase 4
semantic-fusion pivot. A new predictor needs to consume the live
`SemanticRiskEngine` instead — see roadmap/06_realtime_pipeline.md.
"""


class RealTimePredictor:
    def __init__(self, model_path: str = "models/sentinel_z.pt"):
        self.model_path = model_path
        self.sliding = []

    def push_graph(self, graph_tensor):
        self.sliding.append(graph_tensor)
        if len(self.sliding) < 3:
            return None
        raise NotImplementedError(
            "RealTimePredictor.push_graph() awaits Phase 6 wiring against "
            "src.sentinel_z.detection.semantic_risk_engine"
        )
