from pydantic import BaseModel
from typing import List, Dict, Any


class RunResponse(BaseModel):
    total_sequences: int
    message: str


class ExplanationResponse(BaseModel):
    sequence_id: int
    prediction: int
    temporal_attention: List[float]
    node_importance: List[List[float]]
    edge_importance: List[List[float]]


class StoryResponse(BaseModel):
    sequence_id: int
    story: str
    severity_score: float
    mitre_techniques: List[str]
