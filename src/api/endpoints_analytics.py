from fastapi import APIRouter
from src.api.utils import load_graph, load_explanation
from src.intelligence.sequence_analytics import analyze_sequence

router = APIRouter()

@router.get("/analytics/{seq_id}")
def get_analytics(seq_id: int):
    graph = load_graph(seq_id)
    explanation = load_explanation(seq_id)
    result = analyze_sequence(graph, explanation)
    return result
