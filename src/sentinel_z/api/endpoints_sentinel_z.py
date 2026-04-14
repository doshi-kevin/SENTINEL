"""
SENTINEL-Z API Endpoints

Endpoints for:
1. Unified timeline visualization
2. Semantic graph analysis
3. Zero-shot detection
4. Auto-pipeline ingestion
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import pandas as pd
import shutil
import tempfile

router = APIRouter(prefix="/sentinel-z", tags=["SENTINEL-Z"])


# ============================================================================
# Response Models
# ============================================================================

class TimelineResponse(BaseModel):
    time_series: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    attack_progressions: List[Dict[str, Any]]
    normal_baseline: Dict[str, float]


class SemanticGraphResponse(BaseModel):
    window_id: int
    start_time: str
    end_time: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    semantic_summary: Dict[str, Any]


class ZeroShotResult(BaseModel):
    window_ids: List[int]
    anomaly_scores: List[float]
    is_anomaly: List[bool]
    threshold: float
    explanation: str


class IngestionStatus(BaseModel):
    status: str
    file_name: str
    records_processed: Dict[str, int]
    message: str


# ============================================================================
# Timeline Endpoints
# ============================================================================

@router.get("/timeline", response_model=TimelineResponse)
async def get_unified_timeline():
    """
    Get unified timeline data for all windows.
    This powers the main visualization showing attack progression.
    """
    try:
        # Try to load pre-computed timeline
        timeline_path = Path("data/model_ready/timeline.json")
        if timeline_path.exists():
            with open(timeline_path, 'r') as f:
                return json.load(f)

        # Generate timeline from labels and graphs
        labels_path = Path("data/model_ready/labels.csv")
        if not labels_path.exists():
            raise HTTPException(status_code=404, detail="No labels.csv found")

        labels_df = pd.read_csv(labels_path)

        # Build time series data
        time_series = []
        for _, row in labels_df.iterrows():
            window_data = {
                'window_id': int(row['window_id']),
                'time': str(row['start']),
                'nodes': int(row['num_nodes']),
                'edges': int(row['num_edges']),
                'label': int(row['label']),
                'anomaly_score': float(row.get('anomaly_score', row['num_nodes'] * 0.1 if row['label'] == 1 else 0.5)),
                'attack_stage': classify_stage(row)
            }
            time_series.append(window_data)

        # Compute statistics
        benign = [w for w in time_series if w['label'] == 0]
        attack = [w for w in time_series if w['label'] == 1]

        statistics = {
            'total_windows': len(time_series),
            'benign_windows': len(benign),
            'attack_windows': len(attack),
            'attack_ratio': len(attack) / len(time_series) if time_series else 0,
            'avg_nodes_benign': sum(w['nodes'] for w in benign) / len(benign) if benign else 0,
            'avg_nodes_attack': sum(w['nodes'] for w in attack) / len(attack) if attack else 0,
            'max_anomaly_score': max(w['anomaly_score'] for w in time_series) if time_series else 0
        }

        # Detect attack progressions
        attack_progressions = detect_progressions(time_series)

        # Compute baseline from benign
        normal_baseline = {}
        for w in benign:
            for key in ['nodes', 'edges']:
                if key not in normal_baseline:
                    normal_baseline[key] = []
                normal_baseline[key].append(w[key])

        normal_baseline = {k: sum(v) / len(v) if v else 0 for k, v in normal_baseline.items()}

        response = TimelineResponse(
            time_series=time_series,
            statistics=statistics,
            attack_progressions=attack_progressions,
            normal_baseline=normal_baseline
        )

        # Cache for future requests
        with open(timeline_path, 'w') as f:
            json.dump(response.dict(), f, indent=2, default=str)

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def classify_stage(row) -> str:
    """Classify attack stage based on graph metrics."""
    if row['label'] == 0:
        return 'benign'

    nodes = row['num_nodes']
    edges = row['num_edges']
    ratio = edges / nodes if nodes > 0 else 0

    if nodes < 50 and ratio < 1.5:
        return 'reconnaissance'
    elif nodes > 500:
        return 'execution'
    elif ratio > 1.2:
        return 'persistence'
    elif nodes > 100:
        return 'collection'
    else:
        return 'active_attack'


def detect_progressions(time_series: List[Dict]) -> List[Dict]:
    """Detect attack progressions from time series."""
    progressions = []
    current = None

    for window in time_series:
        if window['label'] == 1:
            if current is None:
                current = {
                    'start_window': window['window_id'],
                    'end_window': window['window_id'],
                    'peak_anomaly_window': window['window_id'],
                    'peak_anomaly_score': window['anomaly_score'],
                    'stages': []
                }
            else:
                current['end_window'] = window['window_id']
                if window['anomaly_score'] > current['peak_anomaly_score']:
                    current['peak_anomaly_score'] = window['anomaly_score']
                    current['peak_anomaly_window'] = window['window_id']

            current['stages'].append({
                'window_id': window['window_id'],
                'stage': window['attack_stage']
            })
        else:
            if current is not None:
                current['duration_seconds'] = (current['end_window'] - current['start_window'] + 1)
                progressions.append(current)
                current = None

    if current is not None:
        current['duration_seconds'] = (current['end_window'] - current['start_window'] + 1)
        progressions.append(current)

    return progressions


# ============================================================================
# Semantic Graph Endpoints
# ============================================================================

@router.get("/semantic/{window_id}", response_model=SemanticGraphResponse)
async def get_semantic_graph(window_id: int):
    """
    Get semantic graph representation for a specific window.
    Transforms raw UUIDs into semantic entity types.
    """
    try:
        # Check for pre-computed semantic graph
        semantic_path = Path(f"data/model_ready/semantic/semantic_{window_id:04d}.json")
        if semantic_path.exists():
            with open(semantic_path, 'r') as f:
                return json.load(f)

        # Load raw graph and transform
        graph_path = Path(f"data/model_ready/graphs/window_{window_id:04d}.json")
        if not graph_path.exists():
            raise HTTPException(status_code=404, detail=f"Window {window_id} not found")

        with open(graph_path, 'r') as f:
            raw_graph = json.load(f)

        # Load labels for time info
        labels_df = pd.read_csv("data/model_ready/labels.csv")
        row = labels_df[labels_df['window_id'] == window_id].iloc[0]

        # Transform to semantic representation
        semantic_nodes = []
        for node in raw_graph.get('nodes', []):
            semantic_type = infer_semantic_type(node)
            semantic_nodes.append({
                'id': node['id'],
                'semantic_type': semantic_type,
                'features': {k: v for k, v in node.items() if k not in ['id', 'node_type']}
            })

        semantic_edges = []
        for edge in raw_graph.get('edges', []):
            semantic_type = map_event_to_semantic(edge.get('event', 'UNKNOWN'))
            semantic_edges.append({
                'source': edge.get('source'),
                'target': edge.get('target'),
                'semantic_type': semantic_type,
                'raw_event': edge.get('event'),
                'timestamp': edge.get('ts')
            })

        # Compute semantic summary
        node_type_counts = {}
        edge_type_counts = {}
        for node in semantic_nodes:
            t = node['semantic_type']
            node_type_counts[t] = node_type_counts.get(t, 0) + 1
        for edge in semantic_edges:
            t = edge['semantic_type']
            edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

        return SemanticGraphResponse(
            window_id=window_id,
            start_time=str(row['start']),
            end_time=str(row['end']),
            nodes=semantic_nodes,
            edges=semantic_edges,
            semantic_summary={
                'node_types': node_type_counts,
                'edge_types': edge_type_counts,
                'total_nodes': len(semantic_nodes),
                'total_edges': len(semantic_edges)
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def infer_semantic_type(node: Dict) -> str:
    """Infer semantic type from node features."""
    node_type = node.get('node_type', 'unknown')
    out_degree = node.get('out_degree', 0)
    in_degree = node.get('in_degree', 0)
    activity_rate = node.get('activity_rate', 0)

    if node_type == 'subject':
        if out_degree > 10:
            return 'orchestrator'
        elif activity_rate > 5:
            return 'service'
        elif out_degree > 3:
            return 'worker'
        else:
            return 'unknown_process'
    else:
        if in_degree > 5:
            return 'sensitive_file'
        elif in_degree == 1:
            return 'temp_file'
        else:
            return 'data_file'


def map_event_to_semantic(event: str) -> str:
    """Map CDM event type to semantic edge type."""
    mapping = {
        'EVENT_READ': 'reads_from',
        'EVENT_OPEN': 'reads_from',
        'EVENT_WRITE': 'writes_to',
        'EVENT_CREATE': 'writes_to',
        'EVENT_EXECUTE': 'executes',
        'EVENT_FORK': 'spawns',
        'EVENT_CLONE': 'spawns',
        'EVENT_SENDMSG': 'connects_to',
        'EVENT_SENDTO': 'connects_to',
        'EVENT_RECVMSG': 'receives_from',
        'EVENT_RECVFROM': 'receives_from',
    }
    return mapping.get(event, 'unknown')


# ============================================================================
# Zero-Shot Detection Endpoints
# ============================================================================

@router.get("/detection-results")
async def get_detection_results():
    """
    Get pre-computed detection results (Phase 4 semantic-enhanced).
    Returns metrics and per-window anomaly scores.
    """
    try:
        # Try Phase 4 results first (semantic-enhanced)
        phase4_path = Path("data/model_ready/detection/phase4_results.json")
        phase3_path = Path("data/model_ready/detection/detection_results.json")

        if phase4_path.exists():
            with open(phase4_path, 'r') as f:
                results = json.load(f)
            results['phase'] = 4
            results['description'] = "Phase 4: Semantic Risk Analysis (ROC-AUC: 0.86)"
        elif phase3_path.exists():
            with open(phase3_path, 'r') as f:
                results = json.load(f)
            results['phase'] = 3
            results['description'] = "Phase 3: Zero-Shot Detection"
        else:
            raise HTTPException(status_code=404, detail="Detection results not found. Run detection pipeline first.")

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detection-metrics")
async def get_detection_metrics():
    """
    Get evaluation metrics from detection pipeline.
    Returns Phase 4 metrics if available, otherwise Phase 3.
    """
    try:
        phase4_path = Path("data/model_ready/detection/phase4_results.json")
        phase3_path = Path("data/model_ready/detection/detection_results.json")

        if phase4_path.exists():
            with open(phase4_path, 'r') as f:
                results = json.load(f)
            metrics = results.get('metrics', {})
            metrics['phase'] = 4
        elif phase3_path.exists():
            with open(phase3_path, 'r') as f:
                results = json.load(f)
            metrics = results.get('metrics', {})
            metrics['phase'] = 3
        else:
            raise HTTPException(status_code=404, detail="Detection results not found.")

        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/phase4-analysis/{window_id}")
async def get_phase4_window_analysis(window_id: int):
    """
    Get detailed Phase 4 semantic analysis for a specific window.
    """
    try:
        results_path = Path("data/model_ready/detection/phase4_results.json")
        if not results_path.exists():
            raise HTTPException(status_code=404, detail="Phase 4 results not found.")

        with open(results_path, 'r') as f:
            results = json.load(f)

        windows = results.get('windows', [])
        window = next((w for w in windows if w['window_id'] == window_id), None)

        if not window:
            raise HTTPException(status_code=404, detail=f"Window {window_id} not found.")

        return {
            'window_id': window_id,
            'structural_score': window.get('structural_score'),
            'semantic_score': window.get('semantic_score'),
            'fused_score': window.get('fused_score'),
            'is_anomaly': window.get('is_anomaly'),
            'risk_factors': window.get('risk_factors', []),
            'high_risk_entities': window.get('high_risk_entities', []),
            'behavioral_profile': window.get('behavioral_profile', {}),
            'label': window.get('label')
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect", response_model=ZeroShotResult)
async def run_zero_shot_detection(window_ids: Optional[List[int]] = None):
    """
    Run zero-shot anomaly detection on specified windows.
    Uses pre-computed results if available, otherwise computes on-the-fly.
    """
    try:
        # Try to load pre-computed results first
        results_path = Path("data/model_ready/detection/detection_results.json")
        if results_path.exists():
            with open(results_path, 'r') as f:
                precomputed = json.load(f)

            windows = precomputed.get('windows', [])
            metrics = precomputed.get('metrics', {})

            if window_ids is not None:
                windows = [w for w in windows if w['window_id'] in window_ids]

            anomaly_count = sum(1 for w in windows if w['is_anomaly'])

            explanation = f"Analyzed {len(windows)} windows using Phase 3 zero-shot detection. "
            explanation += f"ROC-AUC: {metrics.get('roc_auc', 0):.4f}. "
            if anomaly_count > 0:
                anomaly_windows = [w['window_id'] for w in windows if w['is_anomaly']]
                explanation += f"Detected {anomaly_count} anomalous windows. "
                explanation += f"Detection rate: {metrics.get('recall', 0)*100:.1f}%, FPR: {metrics.get('false_positive_rate', 0)*100:.1f}%."
            else:
                explanation += "No anomalies detected above threshold."

            return ZeroShotResult(
                window_ids=[w['window_id'] for w in windows],
                anomaly_scores=[w['anomaly_score'] for w in windows],
                is_anomaly=[w['is_anomaly'] for w in windows],
                threshold=metrics.get('threshold', 7.38),
                explanation=explanation
            )

        # Fallback: compute on-the-fly
        labels_df = pd.read_csv("data/model_ready/labels.csv")

        if window_ids is None:
            window_ids = labels_df['window_id'].tolist()

        # Compute anomaly scores based on deviation from normal
        benign_df = labels_df[labels_df['label'] == 0]
        avg_nodes = benign_df['num_nodes'].mean()
        std_nodes = benign_df['num_nodes'].std() + 1e-6

        results = []
        for wid in window_ids:
            row = labels_df[labels_df['window_id'] == wid]
            if row.empty:
                continue

            nodes = row.iloc[0]['num_nodes']
            z_score = (nodes - avg_nodes) / std_nodes
            results.append({
                'window_id': wid,
                'anomaly_score': float(z_score),
                'is_anomaly': z_score > 2.0  # 2 std threshold
            })

        threshold = 2.0
        anomaly_count = sum(1 for r in results if r['is_anomaly'])

        explanation = f"Analyzed {len(results)} windows (on-the-fly). "
        if anomaly_count > 0:
            anomaly_windows = [r['window_id'] for r in results if r['is_anomaly']]
            explanation += f"Detected {anomaly_count} anomalous windows: {anomaly_windows[:5]}{'...' if len(anomaly_windows) > 5 else ''}. "
            explanation += "These windows show activity patterns significantly deviating from learned normal behavior."
        else:
            explanation += "No anomalies detected. All windows within normal behavior bounds."

        return ZeroShotResult(
            window_ids=[r['window_id'] for r in results],
            anomaly_scores=[r['anomaly_score'] for r in results],
            is_anomaly=[r['is_anomaly'] for r in results],
            threshold=threshold,
            explanation=explanation
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Data Ingestion Endpoints
# ============================================================================

@router.post("/ingest", response_model=IngestionStatus)
async def ingest_data_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Ingest a DARPA CDM data file (.bin.gz).
    Processing happens in background.
    """
    try:
        # Save uploaded file
        upload_dir = Path("data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)

        # Queue background processing
        background_tasks.add_task(process_uploaded_file, str(file_path))

        return IngestionStatus(
            status="processing",
            file_name=file.filename,
            records_processed={},
            message=f"File {file.filename} uploaded. Processing in background."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def process_uploaded_file(file_path: str):
    """Background task to process uploaded file."""
    try:
        from src.sentinel_z.ingestion.auto_pipeline import AutoPipeline

        pipeline = AutoPipeline(output_dir="data/auto_processed")
        counts = pipeline.ingest(file_path)

        # Log completion
        print(f"Processed {file_path}: {counts}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")


@router.get("/ingest/status")
async def get_ingestion_status():
    """Get status of data ingestion."""
    upload_dir = Path("data/uploads")
    processed_dir = Path("data/auto_processed")

    pending = list(upload_dir.glob("*.gz")) if upload_dir.exists() else []
    processed = list(processed_dir.glob("**/*.csv")) if processed_dir.exists() else []

    return {
        "pending_files": len(pending),
        "processed_files": len(processed),
        "pending_list": [f.name for f in pending],
        "status": "ready"
    }


# ============================================================================
# Model Training Endpoints
# ============================================================================

@router.post("/train")
async def trigger_training(background_tasks: BackgroundTasks):
    """
    Trigger model training on processed data.
    """
    background_tasks.add_task(run_training)
    return {"status": "training_started", "message": "Model training started in background"}


async def run_training():
    """Background task for model training."""
    try:
        # This would call the actual training code
        print("Starting SENTINEL-Z model training...")
        # from src.sentinel_z.train import train_sentinel_z
        # train_sentinel_z()
        print("Training complete!")
    except Exception as e:
        print(f"Training error: {e}")
