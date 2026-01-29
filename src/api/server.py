from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.pipeline.sequence_extractor import SequenceExtractor
from src.training.explain_tgnn import main as explain_all
from src.api.schemas import RunResponse, ExplanationResponse, StoryResponse
from src.api.utils import load_explanation, generate_story

from src.api.endpoints_analytics import router as analytics_router
from src.api.endpoints_sentinel_z import router as sentinel_z_router

from fastapi import HTTPException
import os
import json

app = FastAPI(title="Sentinel APT Detection API")

app.include_router(analytics_router)
app.include_router(sentinel_z_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/status")
def status():
    return {"status": "ok", "message": "Sentinel backend running"}


@app.post("/run", response_model=RunResponse)
def run_detection():
    expl_count = explain_all()
    return RunResponse(
        total_sequences=expl_count,
        message="Successfully analyzed all sequences."
    )


@app.get("/explain/{seq_id}", response_model=ExplanationResponse)
def get_explanation(seq_id: int):
    expl = load_explanation(seq_id)
    return ExplanationResponse(
        sequence_id=seq_id,
        prediction=expl["prediction"],
        temporal_attention=expl["temporal_attention"][0],
        node_importance=expl["node_importance"],
        edge_importance=expl["edge_importance"],
    )


@app.get("/story/{seq_id}", response_model=StoryResponse)
def story(seq_id: int):
    expl = load_explanation(seq_id)
    story, severity, mitre = generate_story(expl)
    return StoryResponse(
        sequence_id=seq_id,
        story=story,
        severity_score=severity,
        mitre_techniques=mitre,
    )

@app.get("/graph/{seq_id}")
def get_graph(seq_id: int, window: int = 1):
    """
    Return graph window for t-2 (0), t-1 (1), t (2)
    Sequence s → windows [s, s+1, s+2]
    """
    base = seq_id + window  # actual window id

    filename = f"data/model_ready/graphs/window_{base:04d}.json"

    # Check file exists
    if not os.path.exists(filename):
        raise HTTPException(
            status_code=404,
            detail=f"Graph window_{base:04d}.json not found"
        )

    try:
        with open(filename, "r") as f:
            g_json = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading graph file: {str(e)}"
        )

    # Guarantee nodes + edges exist
    if "nodes" not in g_json or "edges" not in g_json:
        return {
            "nodes": [],
            "edges": [],
            "warning": "Graph json missing required fields."
        }

    return g_json


