import json
import os

MITRE_MAP = {
    "EXECUTE": ["T1059 Command Execution"],
    "WRITE": ["T1105 Exfiltration"],
    "READ": ["T1087 Discovery"],
    "SENDTO": ["T1041 Exfiltration Over Network"],
}


def load_explanation(seq_id):
    path = f"explanations/explanation_{seq_id}.json"
    with open(path, "r") as f:
        return json.load(f)


def generate_story(expl):
    pred = expl["prediction"]
    temporal = expl["temporal_attention"]

    # severity = soft weighting
    severity = round(temporal[-1] * (1.0 if pred == 1 else 0.3), 2)

    mitre = []
    for timestep, node_list in enumerate(expl["node_importance"]):
        if len(node_list) > 0:
            # heuristics: large changes indicate critical events
            if max(node_list) > 0.05:
                mitre.append("T1059 Command Execution")

    story = (
        f"Sequence {expl['sequence_id']} is classified as "
        f"{'MALICIOUS' if pred == 1 else 'BENIGN'}.\n"
        f"Highest importance occurred at timestep with weight {max(temporal):.3f}.\n"
        f"Severity Score: {severity}.\n"
        f"Possible MITRE Techniques: {', '.join(mitre) if mitre else 'None detected'}."
    )

    return story, severity, mitre
