<div align="center">

# 🛡️ Sentinel-Z

### Explainable Provenance-Based APT Detection
### with Honest Validation Methodology

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![PR-AUC](https://img.shields.io/badge/PR--AUC-0.83-success.svg)](MODEL_CARD.md)
[![ROC-AUC](https://img.shields.io/badge/ROC--AUC-0.999-success.svg)](MODEL_CARD.md)
[![Validation](https://img.shields.io/badge/Validation-30--bootstrap%20+%207%20stress%20tests-success.svg)](STRESS_TEST_REPORT.md)
[![Dataset](https://img.shields.io/badge/Dataset-DARPA%20TC%20E5%20FiveDirections-orange.svg)](data/raw/e5/README.md)

**Detects APT activity in 1-second provenance graph windows  
and generates SOC-actionable narratives that cite their own evidence.**

[Quick Start](#-quick-start) · [Results](#-results) · [Architecture](#-architecture) · [Roadmap](#-roadmap) · [Cite](#-citation)

</div>

---

## What this is

Sentinel-Z is a **research-grade APT detection system** that pairs:

1. **A calibrated Random Forest detector** on graph-behavioral features extracted from system provenance data (DARPA Transparent Computing CDM format), and
2. **A deterministic narrative engine** that converts detections into plain-English attack stories citing the underlying signals — **without any dependency on large language models**.

It is evaluated with 30-iteration stratified bootstrap statistics, paired-significance testing against baselines, an ablation study, six independent stress tests, and a cross-host generalization analysis. Every claim in the [Model Card](MODEL_CARD.md) has a 95% confidence interval.

## Why it exists

Published academic APT detectors report 99%+ AUC on DARPA datasets and stop there. Commercial detectors don't publish numbers at all. Neither produces explanations that a SOC analyst can actually verify against the underlying evidence.

Sentinel-Z makes three commitments:

- **Honest validation.** Every metric has a 95% CI from paired-bootstrap iterations. No cherry-picked seeds. Stress tests against the field's known failure modes (label leakage, attack-cluster artifacts, feature noise) are part of the public model card.
- **Deterministic explanations.** Narratives are template-driven and cite the exact signals (unknown-subject ratio, graph density, event-type distribution) that drove the detection. They are reproducible byte-for-byte and contain no hallucinated content.
- **Open, reproducible research.** All code, validation scripts, and reports are public. Anyone can re-run the full pipeline on the same data and reproduce the numbers in the model card.

---

## 📊 Results

All numbers are mean ± std across 30 stratified bootstrap iterations on DARPA TC E5 FiveDirections (75,147 1-second windows, 86 labeled attack windows, 0.11% positive class).

| Metric | v2 (Sentinel-Z) | v1 baseline | Improvement |
|---|:---:|:---:|:---:|
| Test ROC-AUC | **0.9996 ± 0.0002** | 0.977 ± 0.009 | +0.022 (CI: [+0.012, +0.042]) |
| Test PR-AUC | **0.832 ± 0.059** | 0.089 ± 0.033 | **+0.744** (CI: [+0.615, +0.860]) |
| Test F1 | 0.433 | 0.039 | 11× higher |
| Test Precision | 29.3% | 2.0% | 14.7× higher |
| Test Recall | 100% | 96.2% | Perfect |
| Test FPR | 0.35% | 6.0% | 17× lower |
| Brier Score | 0.0008 | 0.008 | 10× better calibration |

**Comparison vs published systems** (numbers reported by respective authors on DARPA TC):

| System | Venue | Dataset | ROC-AUC | F1 / PR-AUC |
|---|---|---|:---:|:---:|
| **Sentinel-Z** | this work | E5-FiveDirections | **0.9996** | **PR-AUC 0.832** |
| MAGIC | USENIX Sec '24 | E3-THEIA | 0.999 | F1 0.991 |
| KAIROS | IEEE S&P '24 | E5-THEIA | 0.997 | precision 0.67 @ recall 1.0 |
| FLASH | IEEE S&P '24 | E3 avg | — | F1 0.945 |
| APT-MCL | arXiv 2025 | E3-CADETS | — | F1 0.999 |
| APT-MCL | arXiv 2025 | unseen ransomware | — | **F1 0.242** (collapse) |

Note: Published systems consistently **avoid E5-FiveDirections** (the Windows TA1 platform); Sentinel-Z uses it deliberately as the harder scenario.

📄 **Full results, methodology, and limitations:** [MODEL_CARD.md](MODEL_CARD.md)
🔬 **Stress test details:** [STRESS_TEST_REPORT.md](STRESS_TEST_REPORT.md)
🔎 **Forensic investigation of unlabeled anomalies:** [INVESTIGATION_REPORT.md](INVESTIGATION_REPORT.md)

---

## 🚀 Quick Start

### Requirements

- Python 3.10+
- 16 GB RAM minimum (32 GB recommended for full E5 ingest)
- NVIDIA GPU optional (CPU is the supported path)

### Install

```bash
git clone https://github.com/kevin-doshi/sentinel-z.git
cd sentinel-z
pip install -e ".[ml]"
```

### Run on sample data (2 minutes)

```bash
# Tiny demo (10 graph windows + 2 labeled attacks; no DARPA data needed)
python scripts/run_detection.py --sample
```

You'll see:

```
Top detection: Window 84 (RF score 0.96)
  Stage: lateral_movement | Confidence: high
  Summary: Lateral-movement indicator: 100% novel subjects interacting
           in a dense graph (density 0.93). Affected: a2a93850 +2 more.
           Primary signals: num_nodes=7.91, num_edges=7.13, num_subjects=3.87.
  MITRE: TA0008
```

### Full DARPA TC E5 pipeline (30 minutes)

```bash
# 1. Download DARPA TC E5 FiveDirections from Google Drive (manual; see
#    data/raw/e5/README.md for instructions and Drive folder URL)
#
# 2. Parse, build graphs, train, evaluate
python scripts/ingest_e5.py         # 10 min - parse 15 .bin.gz files
python scripts/verify_phase4.py     # 5  min - extract features per window
python scripts/train_detector.py    # 1  min - train RF v1 baseline
python scripts/train_detector_v2.py # 2  min - train RF v2 (with temporal)
python scripts/rigorous_validation.py # 1 min - bootstrap + significance
python scripts/stress_test.py       # 1  min - 7 stress tests
python scripts/run_detection.py     # 1  min - generate narratives
```

Or run the whole thing:

```bash
make reproduce        # Full pipeline
make smoke            # 2-file subset (faster)
```

### Run with Docker

```bash
docker-compose up
# Frontend available at http://localhost:3000
# API available at http://localhost:8000/docs
```

---

## 🏗️ Architecture

```
                         ┌────────────────────────────────┐
                         │ DARPA TC CDM .bin.gz events    │
                         └────────────────┬───────────────┘
                                          │
                          ┌───────────────▼───────────────┐
                          │ Parallel CDM Parser (4 worker)│
                          │ src/sentinel_z/ingestion/     │
                          └───────────────┬───────────────┘
                                          │
                          ┌───────────────▼───────────────┐
                          │ 1-Second Window Generator     │
                          │ Graph Construction (NetworkX) │
                          │ src/sentinel_z/pipeline/      │
                          └───────────────┬───────────────┘
                                          │
       ┌──────────────────────────────────┼──────────────────────────────────┐
       │                                  │                                  │
┌──────▼──────────┐         ┌─────────────▼──────────┐         ┌─────────────▼──────────┐
│ Feature         │         │ Semantic Risk Engine   │         │ Subjects Catalog       │
│ Extraction      │         │ (Phase 4, contextual)  │         │ (cmd_line lookup)      │
│ 7 base + 13     │         │ src/sentinel_z/        │         │ subjects_*.csv         │
│ temporal feats  │         │   detection/semantic_  │         │                        │
│                 │         │   risk_engine.py       │         │                        │
└──────┬──────────┘         └─────────────┬──────────┘         └────────────────────────┘
       │                                  │
       └─────────────┬────────────────────┘
                     │
       ┌─────────────▼──────────────────────────────────┐
       │ RFDetector v2 (PRIMARY)                        │
       │   200 trees, max_depth=8, class_weight=balanced│
       │   Threshold via Youden's J on calibration set  │
       │   src/sentinel_z/detection/rf_detector.py      │
       └─────────────┬──────────────────────────────────┘
                     │ score ∈ [0, 1], anomaly: bool
       ┌─────────────▼──────────────────────────────────┐
       │ StoryBuilder — deterministic narrative engine  │
       │   - Stage inference from event distribution    │
       │   - MITRE ATT&CK tactic mapping                │
       │   - Signal citation (no LLM)                   │
       │   src/sentinel_z/narrative/story_builder.py    │
       └─────────────┬──────────────────────────────────┘
                     │
       ┌─────────────▼──────────────────────────────────┐
       │ Output: per-window narrative + campaign story  │
       │   JSON + REST API + WebSocket for frontend     │
       └────────────────────────────────────────────────┘
```

### Example narrative output

```
[RF score 0.963 >= 0.108] Lateral-movement indicator: 100% novel
subjects interacting in a dense graph (density 0.93). Affected:
a2a93850 +2 more. Primary signals: num_nodes=7.91, num_edges=7.13,
num_subjects=3.87.
MITRE: TA0008
Confidence: high
```

Every number in the narrative is a signal extractable from the underlying graph. There is no generative model, no LLM, no hallucination.

---

## 📁 Repository Structure

```
sentinel-z/
├── README.md                 ← you are here
├── MODEL_CARD.md             ← honest performance + limitations
├── STRESS_TEST_REPORT.md     ← 7 stress tests with industry context
├── INVESTIGATION_REPORT.md   ← forensic analysis of unlabeled anomalies
├── CITATION.cff              ← machine-readable citation
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── LICENSE                   ← Apache 2.0
├── pyproject.toml            ← Python project metadata
├── docker-compose.yml        ← One-command demo
├── Makefile                  ← make reproduce / make smoke
│
├── src/sentinel_z/           ← All Python code lives here
│   ├── ingestion/            ← CDM parsers (v18 + v20)
│   ├── pipeline/             ← Graph build, feature extract, temporal feats
│   ├── detection/            ← RF detectors v1/v2, semantic risk engine
│   ├── narrative/            ← Story builder, templates
│   └── api/                  ← FastAPI server
│
├── scripts/                  ← Executable CLI tools
│   ├── ingest_e5.py          ← E5 parse + graph build
│   ├── ingest_e3.py          ← E3 parse + graph build (Phase 0)
│   ├── verify_phase4.py      ← Feature extraction
│   ├── train_detector.py     ← RF v1 training
│   ├── train_detector_v2.py  ← RF v2 with temporal features
│   ├── rigorous_validation.py ← 30-bootstrap + significance + calibration
│   ├── stress_test.py        ← 7 stress tests
│   ├── cross_engagement_eval.py ← E5 ⇆ E3 cross-validation (Phase 0)
│   ├── compare_magic.py      ← Paired-bootstrap vs MAGIC baseline
│   ├── extract_e5_labels.py  ← Parse DARPA PDF for full ground truth
│   ├── cross_host_validation.py
│   ├── host_conditional_analysis.py
│   ├── investigate_anomalies.py
│   └── run_detection.py
│
├── tests/                    ← Unit + integration tests
│
├── docs/                     ← Architecture, paper drafts, schema notes
│   └── paper-drafts/
│
├── frontend/                 ← Next.js dashboard with provenance graph viz
│
└── data/                     ← Gitignored; populated by ingest scripts
```

---

## 🗺️ Roadmap

We are executing a deliberate 12-month research-then-commercial trajectory.

### ✅ Phase 0 (Apr 2026, complete)

- Honest validation suite (30-bootstrap, paired-significance, calibration)
- 7 independent stress tests (shuffled-label, context corruption, imbalance sweep, noise injection, window-size, cold-start, cluster holdout)
- Cross-host generalization analysis (LOHO-CV + host-conditional)
- Forensic investigation of unlabeled anomalies (5 host-2 windows with attack signatures)
- Industry comparison context (MAGIC, KAIROS, FLASH, APT-MCL benchmarks)
- Open-source release with full reproducibility
- **Tier-2 paper submission target:** RAID 2027 or ACSAC 2026

### 🔬 Phase 1 (May-Jul 2026, in planning)

Three algorithmic pillars to elevate from competitive-prototype to genuine-research-contribution:

- **Contrastive Behavioral Embeddings (CBE).** Self-supervised representations of subject behavioral roles via InfoNCE contrastive learning on (event_type, object_class) context.
- **Causal Reasoning Engine (CRE).** Backward provenance traversal + Bayesian inference over MITRE ATT&CK tactics + HMM for multi-stage attack sequence hypothesis.
- **Conformal Prediction.** Mondrian inductive conformal prediction for statistically calibrated SOC confidence with abstain option.

**Tier-1 paper submission target:** USENIX Security 2027 or NDSS 2028.

### 🚀 Phase 2 (Q3-Q4 2026)

- Rust streaming inference engine (< 200 ms P99 latency)
- Sysmon / eBPF / OSQuery ingestion adapters (real-world data, not DARPA-only)
- SIEM connectors (Splunk HEC, Elastic, Microsoft Sentinel)
- Production frontend with multi-tenant deployment

### 🛡️ Phase 3 (Q1-Q2 2027)

- Adversarial robustness framework (evasion attacks, certified defenses)
- **Tier-1 paper submission:** IEEE S&P 2028 or CCS 2027

### 💰 Phase 4 (Q3-Q4 2027)

- Pilot deployments with mid-market MSSPs and government contractors
- SBIR Phase I grant application
- First revenue (target: 18-24 months from project start)

---

## 📚 Citation

If you use Sentinel-Z in your research, please cite:

```bibtex
@software{doshi2026sentinelz,
  title  = {Sentinel-Z: Explainable Provenance-Based APT Detection},
  author = {Doshi, Kevin},
  year   = 2026,
  url    = {https://github.com/kevin-doshi/sentinel-z}
}
```

Or use the [CITATION.cff](CITATION.cff) file (GitHub auto-renders this).

---

## 🤝 Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). We particularly value:

- Independent reproduction of our results
- Evaluations on new datasets (E3, CADETS, THEIA, OpTC, non-DARPA real data)
- New stress tests against the field's known failure modes
- Documentation improvements

## 📬 Contact

- Email: kevin.doshi2@spit.ac.in
- Issues: https://github.com/kevin-doshi/sentinel-z/issues
- Discussions: https://github.com/kevin-doshi/sentinel-z/discussions

## License

Apache 2.0 — see [LICENSE](LICENSE). Free for commercial and academic use.

---

<div align="center">

*Built with disciplined methodology, not hype.*  
*Every metric has a confidence interval. Every claim has a test that could falsify it.*

</div>
