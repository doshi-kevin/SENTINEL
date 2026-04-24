"""
Run end-to-end Sentinel-Z detection + narrative on ingested data.

Pipeline:
    phase4_results.json (feature source)
         |
         v
    RFDetector (primary)           SemanticRiskEngine (context)
         |                                |
         +------> StoryBuilder <----------+
                       |
                       v
               Per-window narrative + campaign stories

Outputs:
    data/model_ready/detection/detections.json  (RF predictions)
    data/model_ready/detection/narratives.json  (per-window stories)
    data/model_ready/detection/campaigns.json   (grouped attack campaigns)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
from dataclasses import asdict

from src.sentinel_z.detection.rf_detector import RFDetector, FEATURE_COLUMNS
from src.sentinel_z.narrative.story_builder import StoryBuilder


def load_features_and_risks(results_json: Path):
    """Load phase4_results.json - returns features DataFrame and full window dicts."""
    with open(results_json) as f:
        data = json.load(f)

    features_rows = []
    windows_by_id = {}
    for w in data.get("windows", []):
        profile = w.get("behavioral_profile", {}) or {}
        features_rows.append({
            "window_id":     w["window_id"],
            "num_nodes":     profile.get("_num_nodes", 0),
            "num_edges":     profile.get("_num_edges", 0),
            "num_subjects":  profile.get("_num_subjects", 0),
            "density":       profile.get("_density", 0.0),
            "unknown_ratio": profile.get("_unknown_ratio", 0.0),
            "network_ratio": profile.get("_network_ratio", 0.0),
            "structural":    w.get("structural_score", 0.0),
        })
        windows_by_id[w["window_id"]] = w
    return pd.DataFrame(features_rows), windows_by_id


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path,
                    default=REPO_ROOT / "data" / "model_ready" / "detection" / "phase4_results.json")
    ap.add_argument("--model", type=Path,
                    default=REPO_ROOT / "models" / "rf_detector.joblib")
    ap.add_argument("--out-dir", type=Path,
                    default=REPO_ROOT / "data" / "model_ready" / "detection")
    ap.add_argument("--top-k", type=int, default=5,
                    help="show this many top detections on stdout")
    args = ap.parse_args()

    if not args.model.exists():
        print(f"ERROR: {args.model} not found. Run scripts/train_detector.py first.", file=sys.stderr)
        return 1

    print(f"Loading RF detector from {args.model}")
    detector = RFDetector.load(args.model)
    print(f"  Threshold: {detector.threshold:.4f}")
    if detector.model_card:
        card = detector.model_card
        print(f"  Training ROC-AUC: {card.roc_auc_test:.4f}")

    print(f"\nLoading features from {args.results}")
    features_df, windows_by_id = load_features_and_risks(args.results)
    print(f"  {len(features_df)} windows")

    print("\nRunning RF detection...")
    detections = detector.predict(features_df)
    anomalies = [d for d in detections if d.is_anomaly]
    print(f"  {len(anomalies)} anomalies flagged (threshold {detector.threshold:.3f})")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    detections_path = args.out_dir / "detections.json"
    with open(detections_path, "w") as f:
        json.dump([asdict(d) for d in detections], f, indent=2)
    print(f"  Saved: {detections_path}")

    print("\nGenerating narratives for anomalies...")
    story_builder = StoryBuilder()
    narratives = []
    for d in anomalies:
        window_risk = windows_by_id.get(d.window_id, {})
        rf_result = asdict(d)
        narrative = story_builder.build_window_narrative(
            window_risk, attack_stage=None, rf_result=rf_result,
        )
        narratives.append(narrative.to_dict())

    narratives_path = args.out_dir / "narratives.json"
    with open(narratives_path, "w") as f:
        json.dump(narratives, f, indent=2)
    print(f"  {len(narratives)} narratives generated")
    print(f"  Saved: {narratives_path}")

    print("\nGrouping into campaigns...")
    sorted_anomalies = sorted(anomalies, key=lambda d: d.window_id)
    campaigns_raw = []
    current = []
    for d in sorted_anomalies:
        if current and d.window_id - current[-1].window_id > 5:
            campaigns_raw.append(current)
            current = []
        current.append(d)
    if current:
        campaigns_raw.append(current)

    campaigns = []
    for camp in campaigns_raw:
        window_risks = [windows_by_id.get(d.window_id, {}) for d in camp]
        prog = {
            "start_window": camp[0].window_id,
            "end_window": camp[-1].window_id,
            "duration_seconds": float(camp[-1].window_id - camp[0].window_id + 1),
            "start_time": "unknown", "end_time": "unknown",
        }
        story = story_builder.build_campaign_story(prog, window_risks, None, detector.threshold)
        campaigns.append(story.to_dict())

    campaigns_path = args.out_dir / "campaigns.json"
    with open(campaigns_path, "w") as f:
        json.dump(campaigns, f, indent=2)
    print(f"  {len(campaigns)} campaigns identified")
    print(f"  Saved: {campaigns_path}")

    print("\n" + "=" * 72)
    print(f"TOP {args.top_k} DETECTIONS")
    print("=" * 72)
    top = sorted(anomalies, key=lambda d: -d.anomaly_score)[:args.top_k]
    for i, d in enumerate(top, 1):
        nar = next((n for n in narratives if n["window_id"] == d.window_id), None)
        print(f"\n#{i} Window {d.window_id}: RF score {d.anomaly_score:.3f}")
        if nar:
            print(f"   Stage: {nar['stage']}  |  Confidence: {nar['confidence']}")
            print(f"   Summary: {nar['summary']}")
            if nar['mitre_hints']:
                print(f"   MITRE: {', '.join(nar['mitre_hints'])}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
