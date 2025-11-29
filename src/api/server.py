from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.pipeline.sequence_extractor import SequenceExtractor
from src.training.explain_tgnn import main as explain_all
from src.api.schemas import RunResponse, ExplanationResponse, StoryResponse
from src.api.utils import load_explanation, generate_story


app = FastAPI(title="Sentinel APT Detection API")

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
def get_graph(seq_id: int):
    """
    Return raw graph json for the center timestep of sequence.
    """
    import json
    path = f"data/model_ready/graphs/window_{seq_id+1:04d}.json"
    with open(path, "r") as f:
        return json.load(f)

