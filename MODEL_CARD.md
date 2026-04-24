# Sentinel-Z Model Card

**Version:** 1.0.0
**Last updated:** 2026-04-24
**Trained on:** DARPA TC Engagement 5 — FiveDirections (smoke subset, files 1-2)

---

## What this model does

Sentinel-Z detects anomalous 1-second graph windows in system provenance data and generates plain-English attack narratives for SOC analysts.

The system has two layers:

1. **RFDetector** — Random Forest classifier on graph features. Primary detection signal.
2. **StoryBuilder** — Deterministic template-based narrative generator. Uses RF output + semantic context to explain WHY a window was flagged.

## Honest Performance (held-out test set)

Evaluated with **stratified 70/15/15 split** on 12,935 windows (86 attacks, 12,849 benign).

| Metric | Value |
|---|:---:|
| Test ROC-AUC | **0.9647** |
| Test Precision | 23.8% |
| Test Recall | 38.5% |
| Test F1 | 0.294 |
| Test FPR | 0.83% |
| Threshold | 0.583 (selected on validation) |
| Test attacks | 13 (of 1,941 test windows) |

### Baseline comparison (same test split)

| Model | ROC-AUC | F1 | Note |
|---|:---:|:---:|---|
| **RFDetector (this model)** | **0.965** | **0.294** | Primary detector |
| unknown_ratio threshold alone | 0.940 | 0.151 | Simplest baseline |
| Isolation Forest (unsupervised) | 0.818 | 0.057 | No labels needed |
| Original semantic fused_score | 0.791 | 0.000 | **Deprecated — worse than RF** |
| Structural features only | 0.718 | 0.012 | Insufficient |

## Feature importance

```
unknown_ratio       0.4552   ← dominant signal
num_subjects        0.1548
num_nodes           0.0942
structural          0.0931
num_edges           0.0915
network_ratio       0.0581
density             0.0530
```

**Interpretation:** Unknown-subject ratio (processes not in system catalog) carries ~46% of the detection signal. The remaining features contribute moderately when combined.

## What this model does NOT do

1. **Cross-dataset generalization is UNVERIFIED.** Trained on a single campaign. Accuracy on E3, THEIA, TRACE, CADETS, or any real-world deployment is unknown until tested.

2. **Temporal robustness is UNVERIFIED.** All 86 attacks cluster in a 2-minute window, so we use stratified (not temporal) split. This measures discrimination, not generalization over time.

3. **Multi-step APT tracking is NOT implemented.** Each 1-second window is scored independently. Campaigns spanning hours/days require additional temporal correlation.

4. **Real-time / streaming detection is NOT implemented.** Batch-only pipeline. Latency and throughput for streaming are unmeasured.

5. **Zero-shot detection is a RESEARCH CLAIM, not a product feature.** The architecture supports it (behavioral abstraction), but it has not been validated on a truly unseen dataset.

## Known limitations and risks

### Training data
- Single dataset, single campaign (E5 FiveDirections smoke subset: 2 of 15 files)
- 86 attack windows — small statistical sample
- Attack labels cover a 2-minute window of a multi-hour campaign

### Evaluation methodology
- Threshold selected on validation set (correct methodology, but small val set)
- No confidence intervals / statistical tests
- No A/B comparison against commercial SIEM baselines

### Known failure modes
- High-activity benign windows can score near threshold (cmd.exe usage common)
- Attacks that blend into normal activity patterns are missed (recall 38.5%)
- ~1% of benign windows still flagged (at the chosen operating point)

## Responsible deployment guidance

**DO**
- Use in SOC environments with analyst review — this is a triage tool, not autonomous decision
- Verify cross-dataset performance before deployment to any new environment
- Monitor false-positive rate over time for drift
- Recalibrate threshold on environment-specific data before production use
- Retrain on larger, more representative attack samples when available

**DO NOT**
- Deploy as an autonomous blocking system — recall is 38.5%, attacks will be missed
- Use as sole detection layer — combine with other signals (NIDS, EDR)
- Claim detection rates without specifying the dataset and methodology
- Assume generalization beyond DARPA TC E5 without testing

## Reproducibility

```bash
# From the repository root:
python scripts/ingest_e5.py --max-files 2        # Parse data, build graphs
python scripts/verify_phase4.py                  # Extract features
python scripts/train_detector.py                 # Train RF model
python scripts/validate_phase4.py                # Rigorous validation
python scripts/run_detection.py                  # End-to-end inference
```

Model artifact: `models/rf_detector.joblib`
Model card JSON: `models/model_card.json`
Integrity checksum: `models/rf_detector.joblib.sha256`

## Future work needed before v2

1. Evaluate on DARPA TC E3 and other teams for cross-dataset generalization
2. Extract full E5 ground-truth labels (currently only 2-minute window labeled)
3. Add temporal correlation for multi-step APT tracking
4. Stream-process support (sub-second latency)
5. Confidence calibration (probability → trustable SOC confidence)
6. Adversarial robustness testing

---

*This card is updated with every significant model change. Do not use any version of this model without reading the limitations section.*
