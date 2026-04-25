"""
End-to-end automation: detection + training + narratives after ingest.

Runs after scripts/ingest_e5.py populates data/model_ready/. Does:
  1. verify_phase4.py  (populates phase4_results.json with signals)
  2. train_detector.py (trains RF with honest splits, saves model card)
  3. validate_phase4.py (rigorous validation: baselines + ablation)
  4. run_detection.py  (RF + narrative end-to-end output)

Call this single script after ingest and you get the complete product output.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STEPS = [
    ("Phase 4 feature extraction", [sys.executable, str(REPO / "scripts" / "verify_phase4.py")]),
    ("RF detector training",        [sys.executable, str(REPO / "scripts" / "train_detector.py")]),
    ("Rigorous validation",         [sys.executable, str(REPO / "scripts" / "validate_phase4.py")]),
    ("Detection + narratives",      [sys.executable, str(REPO / "scripts" / "run_detection.py")]),
]


def main() -> int:
    for i, (label, cmd) in enumerate(STEPS, 1):
        print(f"\n{'='*72}\n[{i}/{len(STEPS)}] {label}\n{'='*72}", flush=True)
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"\n!! Step {i} ({label}) failed with exit code {rc}", file=sys.stderr)
            return rc
    print("\nAll steps complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
