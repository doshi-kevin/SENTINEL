"""
Forensic investigation of high-score windows the model flagged but DARPA did
NOT label as attacks. The cross-host analysis surfaced 5 host-2 windows with
RF score >0.87 and feature signatures matching host-1 attack patterns.

This script:
  1. Pulls the top-N high-score host-2/host-3 windows.
  2. Pulls a matched comparison set: top labeled attacks on host 1.
  3. Side-by-side compares features.
  4. Dumps the underlying provenance graph for each candidate (subjects + events)
     so we can manually decide: real undiscovered APT or benign anomaly?
  5. Writes a structured investigation report under data/model_ready/investigation/.

The output is the kind of forensic dossier a SOC analyst would receive —
exactly the explainability product Sentinel-Z is selling.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from src.sentinel_z.detection.rf_detector import RFDetector
from src.sentinel_z.narrative.story_builder import StoryBuilder
from dataclasses import asdict


def build_uuid_to_host(subjects_dir: Path) -> dict:
    mapping = {}
    for fp in sorted(glob.glob(str(subjects_dir / "subjects_*.csv"))):
        host = int(Path(fp).stem.split("_")[1]) // 1000
        if host in (1, 2, 3):
            df = pd.read_csv(fp, usecols=["uuid"])
            for u in df["uuid"].dropna().astype(str):
                mapping.setdefault(u, host)
    return mapping


def load_subjects_full(subjects_dir: Path) -> pd.DataFrame:
    """Concatenate every subjects_*.csv into one DataFrame for cmdline lookup."""
    frames = []
    for fp in sorted(glob.glob(str(subjects_dir / "subjects_*.csv"))):
        host = int(Path(fp).stem.split("_")[1]) // 1000
        try:
            df = pd.read_csv(fp)
        except Exception:
            continue
        df["_host"] = host
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def attribute_window(graph_path: Path, uuid_to_host: dict) -> int | None:
    if not graph_path.exists():
        return None
    with open(graph_path) as f:
        g = json.load(f)
    c = Counter()
    for n in g.get("nodes", []):
        if n.get("node_type") == "subject":
            h = uuid_to_host.get(str(n.get("id", "")))
            if h:
                c[h] += 1
    return c.most_common(1)[0][0] if c else None


def dump_window(window_id: int, graph_path: Path,
                subjects_df: pd.DataFrame) -> dict:
    """Return a forensic summary of one graph window."""
    if not graph_path.exists():
        return {"window_id": window_id, "error": "graph file missing"}
    with open(graph_path) as f:
        g = json.load(f)

    subjects = []
    objects = []
    for n in g.get("nodes", []):
        node_uuid = str(n.get("id", ""))
        node_type = n.get("node_type")
        if node_type == "subject":
            row = subjects_df[subjects_df.get("uuid") == node_uuid] if not subjects_df.empty else None
            cmd = row.iloc[0]["cmd_line"] if (row is not None and len(row) > 0 and "cmd_line" in row.columns) else None
            stype = row.iloc[0].get("type", "UNKNOWN") if (row is not None and len(row) > 0) else "UNKNOWN"
            subjects.append({
                "uuid": node_uuid[:16],
                "type": stype,
                "cmd_line": str(cmd)[:200] if cmd and not pd.isna(cmd) else None,
                "out_degree": n.get("out_degree", 0),
                "in_degree": n.get("in_degree", 0),
                "event_count": n.get("event_count", 0),
            })
        else:
            objects.append({"uuid": node_uuid[:16], "node_type": node_type,
                            "in_degree": n.get("in_degree", 0)})

    edges = g.get("links", g.get("edges", []))
    event_types = Counter(e.get("event", "?") for e in edges)
    timestamps = sorted(set(e.get("ts", "") for e in edges if e.get("ts")))

    return {
        "window_id": window_id,
        "n_nodes": len(g.get("nodes", [])),
        "n_edges": len(edges),
        "n_subjects": len(subjects),
        "n_objects": len(objects),
        "subjects_with_cmdline": sum(1 for s in subjects if s["cmd_line"]),
        "event_type_counts": dict(event_types),
        "time_range": [timestamps[0], timestamps[-1]] if timestamps else None,
        "top_subjects": sorted(subjects, key=lambda s: -s["event_count"])[:10],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-host2", type=int, default=5,
                    help="number of top host-2 high-score windows to investigate")
    ap.add_argument("--n-attack-ref", type=int, default=5,
                    help="number of host-1 labeled attack windows to compare against")
    args = ap.parse_args()

    subjects_dir = REPO_ROOT / "data" / "auto_processed" / "fivedirections" / "e5"
    graphs_dir   = REPO_ROOT / "data" / "model_ready" / "graphs"
    results_path = REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json"
    model_path   = REPO_ROOT / "models" / "rf_detector.joblib"
    out_dir      = REPO_ROOT / "data" / "model_ready" / "investigation"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading model + features ...")
    det = RFDetector.load(model_path)
    with open(results_path) as f:
        data = json.load(f)
    rows = []
    for w in data["windows"]:
        profile = w.get("behavioral_profile", {}) or {}
        rows.append({
            "window_id":     w["window_id"],
            "label":         w["label"],
            "fused_score":   w["fused_score"],
            "num_nodes":     profile.get("_num_nodes", 0),
            "num_edges":     profile.get("_num_edges", 0),
            "num_subjects":  profile.get("_num_subjects", 0),
            "density":       profile.get("_density", 0.0),
            "unknown_ratio": profile.get("_unknown_ratio", 0.0),
            "network_ratio": profile.get("_network_ratio", 0.0),
            "structural":    w.get("structural_score", 0.0),
        })
    df = pd.DataFrame(rows)
    detections = det.predict(df)
    df["rf_score"] = [d.anomaly_score for d in detections]

    print("Building UUID->host map ...")
    uuid_to_host = build_uuid_to_host(subjects_dir)

    print("Attributing windows of interest to hosts ...")
    df["host"] = None
    high_score = df[df["rf_score"] > 0.5].copy()
    print(f"  {len(high_score)} windows with rf_score > 0.5 to attribute")
    for idx, row in high_score.iterrows():
        gp = graphs_dir / f"window_{int(row['window_id']):04d}.json"
        df.at[idx, "host"] = attribute_window(gp, uuid_to_host)

    h2_top = df[(df["host"] == 2) & (df["rf_score"] > 0.5)] \
        .sort_values("rf_score", ascending=False).head(args.n_host2)
    h3_top = df[(df["host"] == 3) & (df["rf_score"] > 0.5)] \
        .sort_values("rf_score", ascending=False).head(args.n_host2)
    h1_attacks = df[(df["label"] == 1)].sort_values("rf_score", ascending=False).head(args.n_attack_ref)

    print(f"\n  Top host-2 anomalies (no labels): {len(h2_top)}")
    print(f"  Top host-3 anomalies (no labels): {len(h3_top)}")
    print(f"  Reference host-1 labeled attacks: {len(h1_attacks)}")

    print("\nLoading subjects metadata for cmdline lookup ...")
    subjects_df = load_subjects_full(subjects_dir)
    print(f"  {len(subjects_df):,} subject records loaded")

    print("\n" + "=" * 80)
    print("FEATURE COMPARISON")
    print("=" * 80)
    cmp_cols = ["window_id", "rf_score", "label", "host",
                "unknown_ratio", "num_nodes", "num_subjects",
                "density", "network_ratio"]
    print("\nReference labeled attacks (host 1):")
    print(h1_attacks[cmp_cols].to_string(index=False))
    print("\nUnlabeled high-score windows (host 2):")
    print(h2_top[cmp_cols].to_string(index=False))
    if len(h3_top) > 0:
        print("\nUnlabeled high-score windows (host 3):")
        print(h3_top[cmp_cols].to_string(index=False))

    print("\n" + "=" * 80)
    print("FORENSIC GRAPH DUMPS")
    print("=" * 80)
    sb = StoryBuilder()

    forensic_payload = {"reference_attacks": [], "host2_candidates": [], "host3_candidates": []}

    def make_record(row):
        wid = int(row["window_id"])
        graph_summary = dump_window(wid, graphs_dir / f"window_{wid:04d}.json", subjects_df)
        wr = next((w for w in data["windows"] if w["window_id"] == wid), {})
        rf_result = {"anomaly_score": float(row["rf_score"]),
                     "threshold": float(det.threshold),
                     "top_features": {}}
        narrative = sb.build_window_narrative(wr, attack_stage=None, rf_result=rf_result)
        return {
            "window_id":   wid,
            "host":        int(row["host"]) if not pd.isna(row["host"]) else None,
            "label":       int(row["label"]),
            "rf_score":    float(row["rf_score"]),
            "narrative":   asdict(narrative),
            "graph_summary": graph_summary,
        }

    for _, row in h1_attacks.iterrows():
        forensic_payload["reference_attacks"].append(make_record(row))
    for _, row in h2_top.iterrows():
        forensic_payload["host2_candidates"].append(make_record(row))
    for _, row in h3_top.iterrows():
        forensic_payload["host3_candidates"].append(make_record(row))

    out_path = out_dir / "anomaly_investigation.json"
    with open(out_path, "w") as f:
        json.dump(forensic_payload, f, indent=2, default=str)
    print(f"\nForensic dossier saved to {out_path}")

    print("\n" + "=" * 80)
    print("VERDICT FACTORS - look at these for each host-2 candidate")
    print("=" * 80)
    for cand in forensic_payload["host2_candidates"]:
        print(f"\n--- Window {cand['window_id']} (host {cand['host']}, score {cand['rf_score']:.3f}) ---")
        print(f"Narrative: {cand['narrative']['summary']}")
        gs = cand["graph_summary"]
        print(f"Graph: {gs.get('n_subjects')} subjects, {gs.get('n_objects')} objects, "
              f"{gs.get('n_edges')} edges")
        print(f"Subjects with cmd_line: {gs.get('subjects_with_cmdline')}/{gs.get('n_subjects')}")
        print(f"Event types: {gs.get('event_type_counts')}")
        if gs.get("top_subjects"):
            print("Top subjects (by event count):")
            for s in gs["top_subjects"][:5]:
                cmd_short = (s["cmd_line"][:80] + "...") if (s["cmd_line"] and len(s["cmd_line"]) > 80) else s["cmd_line"]
                print(f"  - {s['uuid']} | {s['type']:>20} | events={s['event_count']:>4} | cmd={cmd_short}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
