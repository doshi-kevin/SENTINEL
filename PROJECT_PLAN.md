# SENTINEL-Z Project Plan

**Last Updated:** January 22, 2026
**Goal:** Build a working APT detection tool with human-readable explanations

---

## Project Overview

SENTINEL-Z is an Advanced Persistent Threat (APT) detection system that analyzes system provenance graphs to identify malicious activity and explain attacks in plain English. Unlike pure research prototypes, this is designed as a deployable tool for security operations centers.

---

## Phase Summary

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Foundation & Data Infrastructure | ✅ COMPLETED |
| **Phase 2** | ML-Based Anomaly Detection | 🔄 Next |
| **Phase 3** | Semantic Understanding & Attack Stories | ⏳ Pending |
| **Phase 4** | Real-Time Deployment | ⏳ Pending |
| **Phase 5** | Evaluation & Documentation | ⏳ Pending |

---

## Phase 1: Foundation & Data Infrastructure (COMPLETED)

### What Was Built

#### 1.1 Data Pipeline
- **Input:** DARPA TC Engagement 5 (FiveDirections) binary Avro logs (292MB compressed)
- **Parser:** Built custom Avro parser using `fastavro` library
- **Output:** 9,709,407 system events extracted to CSV
- **Subjects:** 30,380 unique processes/entities tracked

#### 1.2 Graph Construction
- **Windowing:** 1-second tumbling windows over event stream
- **Graph Format:** Directed graphs with nodes (processes, files, network) and edges (events)
- **Output:** 6,018 time-windowed graph snapshots saved as JSON
- **Labels:** 83 attack windows, 5,935 benign windows (based on ground truth timestamps)

#### 1.3 Node Features Computed
- Degree (in/out/total)
- Event count per node
- Node type flag (subject vs object)

#### 1.4 Interactive Visualization Dashboard
- **Framework:** Next.js 16 + Tailwind CSS
- **Graph Rendering:** Canvas-based force-directed layout with physics simulation
- **Features:**
  - Drag nodes to explore graph structure
  - Click to select nodes and see connections highlighted
  - Hover tooltips showing entity details
  - Attack/Normal filtering
  - Timeline overview with clickable bars
  - Stats summary (total windows, attacks, benign)

#### 1.5 Project Structure Cleanup
- Removed legacy code, old models, unused documentation
- Clean folder structure:
  ```
  SENTINEL/
  ├── data/
  │   ├── auto_processed/   # 6,018 graphs + labels
  │   └── raw/              # Original DARPA data
  ├── frontend/             # Next.js dashboard
  ├── src/
  │   ├── api/              # FastAPI backend
  │   ├── pipeline/         # Data processing
  │   ├── realtime/         # Stream ingestion (scaffolding)
  │   └── sentinel_z/       # ML pipeline code
  └── PROJECT_PLAN.md
  ```

### Phase 1 Deliverables
| Deliverable | Location | Status |
|-------------|----------|--------|
| Event extraction pipeline | `src/sentinel_z/auto_pipeline.py` | ✅ |
| Graph dataset builder | `src/sentinel_z/build_large_dataset.py` | ✅ |
| 6,018 graph JSON files | `data/auto_processed/graphs/` | ✅ |
| Labels CSV | `data/auto_processed/labels.csv` | ✅ |
| Visualization dashboard | `frontend/` | ✅ |
| API endpoints | `src/api/` | ✅ |

---

## Phase 2: ML-Based Anomaly Detection (NEXT)

### Objective
Train a model to distinguish attack windows from benign windows using graph structure.

### Approach
1. **Self-Supervised Pre-training**
   - Contrastive learning on graph pairs (augmented views)
   - Learn node and graph-level embeddings without labels

2. **Anomaly Detection**
   - Train on benign windows only (learn "normal" behavior)
   - Use Isolation Forest or One-Class SVM on embeddings
   - Score each window by deviation from normal

3. **Supervised Fine-tuning (Optional)**
   - Use labeled attack windows to calibrate threshold
   - Improve precision/recall trade-off

### Target Metrics
- Detection Rate: >90% of attack windows identified
- False Positive Rate: <5% benign windows flagged
- Inference Time: <100ms per window

### Files to Create/Modify
- `src/sentinel_z/train_encoder.py` (exists, needs completion)
- `src/sentinel_z/anomaly_detector.py` (new)
- `data/auto_processed/model.pt` (trained model)

---

## Phase 3: Semantic Understanding & Attack Stories

### Objective
Classify entity behaviors and generate human-readable attack narratives.

### 3.1 Entity Behavior Classifier
Map entities to semantic behaviors:
- **Scanner:** Port/network scanning patterns
- **Downloader:** Fetching remote files
- **Executor:** Running commands/scripts
- **Exfiltrator:** Sending data outbound
- **C2 Communicator:** Beaconing patterns
- **Normal:** Regular application behavior

### 3.2 Attack Story Generator
Generate plain-English explanations:
```
"At 11:10:42 AM, process chrome.exe (behaving like a downloader)
fetched suspicious file payload.dll from external IP 192.168.1.100.
This file was then executed by svchost.exe, which proceeded to
scan the internal network and establish a connection to 10.0.0.50
(exhibiting C2 beacon behavior)."
```

### Files to Create
- `src/sentinel_z/behavior_classifier.py`
- `src/sentinel_z/story_generator.py`

---

## Phase 4: Real-Time Deployment

### Objective
Process live system logs and generate alerts in real-time.

### Components
1. **Event Buffer:** Streaming ingestion from log sources
2. **Window Generator:** 1-second tumbling windows
3. **Graph Constructor:** Build graph on-the-fly
4. **Model Inference:** Score window for anomalies
5. **Alert Service:** Push notifications + dashboard updates

### Integration Points
- FastAPI endpoint for log ingestion
- WebSocket for real-time dashboard updates
- Export to SIEM (STIX/JSON format)

---

## Phase 5: Evaluation & Documentation

### Objective
Validate system performance and document for users.

### Evaluation
- Test on all DARPA TC engagements (E3, E5)
- Measure: detection rate, time-to-detect, false positives
- Compare against published baselines (FLASH, RAPID)

### Documentation
- User manual for SOC analysts
- Installation guide
- API documentation
- Sample incident response playbooks

---

## Research Paper Analysis

### Papers Reviewed (2024-2025)

#### 1. **FLASH** (IEEE S&P 2024)
- **Technique:** GNN + Word2Vec embeddings with embedding recycling database
- **Key Innovation:** Two-phase pipeline - GNN learns graph structure, Word2Vec captures semantic attributes
- **Performance:** Outperforms Unicorn on stealthy attacks
- **Limitations:** 54-76% missing node attributes, computational overhead
- **Source:** https://dartlab.org/assets/pdf/flash.pdf

#### 2. **RAPID** (arXiv June 2024)
- **Technique:** Bi-LSTM anomaly detector + CBOW embeddings
- **Key Innovation:** Uses anomalies as starting points for attack narrative reconstruction
- **Performance:** Graph-level perfect precision/recall, 3.6×10⁴ logs/second throughput
- **Limitations:** Concept drift, no automated response integration
- **Source:** https://arxiv.org/html/2406.05362v1

#### 3. **APT-MCL** (arXiv January 2025)
- **Technique:** Multi-view collaborative learning with co-training
- **Key Innovation:** Unsupervised detection without labeled attacks
- **Performance:** F1 0.847-0.998 on DARPA TC, drops to 0.242 on unseen attacks
- **Limitations:** Poor cross-domain adaptability, high computational cost
- **Source:** https://arxiv.org/html/2601.08328

#### 4. **TREC** (ACM CCS 2024)
- **Technique:** Few-shot APT tactic/technique recognition with Siamese networks
- **Key Innovation:** First DL approach for MITRE ATT&CK recognition from provenance graphs
- **Performance:** 83.1% tactic recognition, 47.1% technique recognition
- **Limitations:** Low recall, Windows-only, no adversarial testing
- **Source:** https://arxiv.org/html/2402.15147v1

### Key Research Gaps Identified

1. **Cross-Campaign Generalization:** Models fail on unseen attack types
2. **Explainability:** No human-readable attack stories
3. **Semantic Abstraction:** Raw IDs instead of behavioral meanings
4. **Temporal Modeling:** Windows treated independently, missing kill-chain flow

### Our Differentiation
We focus on **practical deployment** rather than academic novelty:
- End-to-end pipeline (raw logs → detection → explanation)
- Designed for SOC analysts, not ML researchers
- Human-readable outputs
- Real-time capable

---

## Technical Stack

### Backend
- Python 3.11
- PyTorch, PyTorch Geometric
- Pandas, NumPy, fastavro
- FastAPI, NetworkX

### Frontend
- Next.js 16, React
- Tailwind CSS
- Canvas-based graph visualization

### Data
- DARPA TC E5 (FiveDirections): 292MB raw → 9.7M events → 6,018 graphs
- Storage: 2.3GB processed

---

## Timeline Estimate

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Foundation | - | ✅ COMPLETED |
| Phase 2: ML Detection | 2-3 weeks | 🔄 Next |
| Phase 3: Semantic + Stories | 2-3 weeks | ⏳ Pending |
| Phase 4: Real-Time | 1-2 weeks | ⏳ Pending |
| Phase 5: Eval & Docs | 1-2 weeks | ⏳ Pending |

---

## Open Questions for Advisor

1. Is building a working tool (vs novel research) acceptable for the project?
2. What metrics matter most for practical systems?
3. Any industry contacts who could validate usefulness?
4. Could this be a "systems paper" or demo paper at a security conference?
5. Access to more diverse datasets beyond DARPA TC?

---

## References

### Papers
- FLASH: https://dartlab.org/assets/pdf/flash.pdf (IEEE S&P 2024)
- RAPID: https://arxiv.org/html/2406.05362v1 (arXiv 2024)
- APT-MCL: https://arxiv.org/html/2601.08328 (arXiv 2025)
- TREC: https://arxiv.org/html/2402.15147v1 (ACM CCS 2024)

### Datasets
- DARPA Transparent Computing: https://github.com/darpa-i2o/Transparent-Computing

### Code
- FLASH-IDS: https://github.com/DART-Laboratory/Flash-IDS

---

## Changelog

- **2026-01-22:** Consolidated all previous work as Phase 1; restructured roadmap
- **2026-01-18:** Initial project plan created after research review
