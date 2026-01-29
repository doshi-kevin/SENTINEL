import json
import os

GRAPH_DIR = "data/model_ready/graphs"
EXPLAIN_DIR = "explanations"


def load_graph(seq_id: int):
    """
    Load graph from window_NNNN.json files instead of graph_#.json.
    """
    filename = f"window_{seq_id:04d}.json"
    path = os.path.join(GRAPH_DIR, filename)

    if not os.path.exists(path):
        raise FileNotFoundError(f"Graph {seq_id} not found at {path}")

    with open(path, "r") as f:
        return json.load(f)


def load_explanation(seq_id: int):
    """
    Explanation filenames remain explanation_{seq}.json
    """
    path = os.path.join(EXPLAIN_DIR, f"explanation_{seq_id}.json")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Explanation {seq_id} not found at {path}")

    with open(path, "r") as f:
        return json.load(f)


def safe_float(value):
    if isinstance(value, list):
        return [safe_float(v) for v in value]
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0

def generate_story(graph, explanation):
    """
    Python version of the frontend story generator.
    Produces a readable attack narrative for the /analytics endpoint.
    """

    seq_id = explanation.get("sequence_id", -1)
    pred = explanation.get("prediction", 0)
    temporal_attention = explanation.get("temporal_attention", [0.33, 0.33, 0.33])

    # Determine main window of interest
    if isinstance(temporal_attention, list) and len(temporal_attention) > 0:
        top_window = temporal_attention.index(max(temporal_attention))
    else:
        top_window = 1  # default mid-window

    attack_type = "Benign Activity" if pred == 0 else "Potential Malicious Activity"

    # Count event types in edges
    edges = graph.get("edges", [])
    exec_count = len([e for e in edges if "EXEC" in e.get("event", "")])
    write_count = len([e for e in edges if "WRITE" in e.get("event", "")])
    read_count  = len([e for e in edges if "READ" in e.get("event", "")])
    send_count  = len([e for e in edges if "SEND" in e.get("event", "")])

    story = f"""
    Sequence {seq_id} appears to show: {attack_type}.

    • Most important time window: t-{2 - top_window}
    • EXEC events: {exec_count}
    • WRITE events: {write_count}
    • READ events: {read_count}
    • SEND events: {send_count}

    The model's attention indicates that activity during the highlighted time 
    window contributed the most to its decision. The combination of event 
    patterns may reflect normal behavior or potentially suspicious behavior 
    depending on intensity and interaction types.
    """

    return story.strip()
