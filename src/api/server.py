"""
Sentinel-Z FastAPI server.

Exposes the live `/sentinel-z/*` router and a small set of utility endpoints
for the Next.js dashboard. The legacy temporal-GNN explanation endpoints
(`/run`, `/explain`, `/story`) were removed in the Phase 4 pivot — see
docs/PHASE_4_TECHNICAL_REPORT.md for context.
"""
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.endpoints_sentinel_z import router as sentinel_z_router

app = FastAPI(title="Sentinel-Z APT Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sentinel_z_router)


@app.get("/status")
def status():
    return {"status": "ok", "message": "Sentinel-Z backend running"}


@app.get("/graph/{seq_id}")
def get_graph(seq_id: int, window: int = 1):
    """
    Return a graph window snapshot. Sequence `s` maps to window file
    `window_{s+window:04d}.json` so the dashboard can step through t-2/t-1/t.
    """
    base = seq_id + window
    filename = f"data/model_ready/graphs/window_{base:04d}.json"

    if not os.path.exists(filename):
        raise HTTPException(
            status_code=404,
            detail=f"Graph window_{base:04d}.json not found",
        )

    try:
        with open(filename, "r") as f:
            g_json = json.load(f)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading graph file: {exc}",
        )

    if "nodes" not in g_json or "edges" not in g_json:
        return {
            "nodes": [],
            "edges": [],
            "warning": "Graph json missing required fields.",
        }

    return g_json
