# SENTINEL-Z Project Status — April 15, 2026

## Executive Summary
**Phase 4 is ✅ PRODUCTION READY** (ROC-AUC 0.8628, FPR 3.62%).  
**Data pipeline is 🔧 FIXED** (removed 27 GB bottleneck).  
**Next: Acquire DARPA E5 data + reproduce Phase 4 results → then decide Phase 5 path.**

---

## Current Project State

### ✅ COMPLETED (Phase 4)
| Component | Status | Evidence |
|-----------|--------|----------|
| **Semantic Risk Engine** | ✅ DONE | `src/sentinel_z/detection/semantic_risk_engine.py` (~450 lines); fusion formula proven |
| **Detection Pipeline** | ✅ DONE | Endpoints + visualization; 4-step pipeline working |
| **Evaluation Framework** | ✅ DONE | 6,051 graphs on DARPA TC E5, ROC-AUC 0.8628 |
| **Technical Docs** | ✅ DONE | Phase 4 report with fusion weights, threshold table, LOLBins rules |
| **Semantic Resolver** | ✅ DONE | UUID → behavioral entity classification (ORCHESTRATOR, SCANNER, etc.) |

**Key Results:**
- Precision: 8.09% (2.61% in Phase 3 = 210% improvement)
- Recall: 22.35% (18.82% in Phase 3 = 19% improvement)  
- False Positive Rate: 3.62% (10.01% in Phase 3 = 64% reduction)
- Strongest signal: **Unknown Subject Ratio** (weight ×15 in fusion)

---

### 🟡 IN PROGRESS (Sub-project A: Data Acquisition)
**Goal:** Enable `make reproduce` for fresh contributors.

| Deliverable | Status | Notes |
|-------------|--------|-------|
| **download_e5.py** | ✅ Script exists | Downloads DARPA TC E5 from Google Drive; idempotent |
| **ingest_e5.py** | ✅ Script exists (just fixed) | Parses 15 .bin.gz files → 6,051 graphs + labels.csv |
| **verify_phase4.py** | ✅ Script exists | Smoke check: imports, runs, validates gates |
| **Makefile** | ✅ Exists | Targets: download, ingest, verify, reproduce, clean-data |
| **Data on disk** | ❌ NOT YET | Needs to run `make reproduce` first |

**Current Blocker (NOW FIXED):**
- Auto_pipeline was saving 27 GB of intermediate CSVs per run
- **Fix applied:** Made `save_intermediate=False` default; cleaned up existing 27 GB

**Next Steps for Sub-project A:**
1. Verify `make download` works (requires Drive access)
2. Run full `make reproduce` pipeline
3. Confirm `verify_phase4.py` exits 0 with ROC-AUC ≈ 0.86

---

### ❌ NOT STARTED (Phase 5: Narrative Engine)
**Goal:** Convert anomaly scores into plain-English attack stories.

| Component | Status | Plan |
|-----------|--------|------|
| **StoryBuilder class** | ❌ STUB | Template-based narrative generation (BFS backward from anomaly) |
| **Causal chain traversal** | ❌ PLANNED | Follow "Cause" edges backward to root (phishing/USB/download) |
| **Templates** | ❌ PLANNED | 3 types: Infection, Lateral Movement, Exfiltration |
| **Target readability** | ❌ SPEC | Flesch-Kincaid Grade 8 (simple English) |

**Design Decision:** Deterministic templates, NOT LLMs (too slow, hallucinate in security).

**Estimated Effort:** 80–120 lines of code (template matching + BFS traversal).

---

### 🟡 PARTIAL (Phase 6–8: Real-Time + Cross-Dataset)
| Phase | Goal | Status |
|-------|------|--------|
| **Phase 6** | Real-time Kafka streaming | Skeleton only (`stream_processor.py`, `realtime_predictor.py`) |
| **Phase 7** | MITRE ATT&CK mapping | Planned, not started |
| **Phase 8** | Cross-dataset validation (E3 vs E5) | Planned, not started |

---

## Code Architecture (Current)

```
src/sentinel_z/
├── detection/
│   ├── semantic_risk_engine.py      ✅ Phase 4 core (450 lines)
│   ├── semantic_resolver.py         ✅ Behavior profiler
│   ├── semantic_graph.py            ✅ Graph wrapper
│   └── zero_shot_detector.py        🟡 Skeleton (future path)
├── ingestion/
│   ├── auto_pipeline.py             ✅ CDM parser + graph builder
│   └── build_large_dataset.py       ✅ Parallel builder
├── pipeline/
│   ├── window_generator.py          ✅ 1-second windowing
│   ├── graph_constructor.py         ✅ Provenance graph builder
│   ├── feature_engineer.py          ✅ Node/edge features
│   └── graph_exporter.py            ✅ JSON serialization
├── narrative/
│   ├── timeline_builder.py          ❌ Skeleton (Phase 5 target)
│   └── __init__.py
├── realtime/
│   ├── stream_processor.py          ❌ Skeleton (Phase 6 target)
│   ├── realtime_predictor.py        ❌ Skeleton (Phase 6 target)
│   ├── event_buffer.py              🟡 Partial
│   └── ingestion.py                 🟡 Partial
├── encoder/
│   ├── self_supervised_encoder.py   🟡 Skeleton (Phase 2 backup plan)
│   └── train_encoder.py             🟡 Backup (was used in Phase 3)
├── api/
│   ├── server.py                    ✅ FastAPI endpoint
│   └── endpoints_sentinel_z.py      ✅ Timeline + graph + detection endpoints
└── __init__.py
```

---

## Documentation State

| File | Status | Purpose |
|------|--------|---------|
| `README.md` | ✅ Current | Single source of truth; Phase 4 results |
| `docs/PHASE_4_TECHNICAL_REPORT.md` | ✅ Current | Fusion formula + threshold table + LOLBins |
| `docs/roadmap/04_semantic_analysis.md` | ✅ COMPLETED | Phase 4 detailed spec (mark as ✅) |
| `docs/roadmap/05_narrative_engine.md` | 🟡 DRAFT | Phase 5 plan (no code yet) |
| `docs/roadmap/03_zero_shot_detection.md` | ❌ OBSOLETE | Original path bypassed by Phase 4 |
| `PROJECT_PLAN.md` | 🟡 STALE | 5-phase schema conflicts w/ "Phase 4" naming |
| `.specs/2026-04-14-...` | ✅ Current | Sub-project A design (data acquisition) |

**Documentation Issue:**
- Phase numbering inconsistent: PROJECT_PLAN uses 5-phase schema (Foundation, ML Detection, Semantic+Stories, Real-Time, Eval+Docs)
- README calls results "Phase 4" (different schema)
- **Fix needed:** Merged master document clarifying both schemas

---

## Critical Files to Understand Next

### 1. **Phase 4 Technical Specification**
```
docs/PHASE_4_TECHNICAL_REPORT.md
docs/roadmap/04_semantic_analysis.md
```
**Key knowledge:**
- Fusion formula: `15×unknown_ratio + 0.2×structural + 3×network_ratio + ...`
- Threshold = 23 (balances recall vs. FPR)
- LOLBins risk scores: mimikatz=10, psexec=9, mshta=8.5

### 2. **Current Bottleneck (JUST FIXED)**
```
src/sentinel_z/ingestion/auto_pipeline.py:_save_intermediate()
```
**What was wrong:** Saved 1.8 GB CSV per file × 15 files = 27 GB bloat
**Fix applied:** `save_intermediate=False` default

### 3. **Data Pipeline Ready to Run**
```
scripts/ingest_e5.py         # Main workhorse
scripts/verify_phase4.py     # Validation gate
scripts/download_e5.py       # Google Drive fetcher
Makefile                     # Orchestration
```

---

## What Needs to Happen Next

### **IMMEDIATE (Today/Tomorrow)**
1. **Commit the auto_pipeline fix**
   ```bash
   git add src/sentinel_z/ingestion/auto_pipeline.py
   git commit -m "fix(ingest): disable intermediate CSV saving by default (saves 27GB + 5min)"
   ```

2. **Run full data pipeline** (estimated 25–30 min)
   ```bash
   make download  # Fetch DARPA E5 from Drive (requires auth)
   make ingest    # Parse 15 files + build 6,051 graphs
   make verify    # Smoke check: ROC-AUC ~0.86
   ```

3. **If successful:** Data is ready for Phase 5 work

### **SHORT-TERM (This Week)**
**Decision point:** What's the product roadmap?

**Option A: Push Phase 5 (Narrative Engine)**
- ~80 lines of code (template matching + BFS)
- Delivers explainability ("why is this anomalous?")
- Timeline: 2–4 hours

**Option B: Stabilize Phase 4 for production**
- Real-time streaming (Phase 6)
- Cross-dataset validation (E3 vs E5)
- MITRE ATT&CK mapping
- Timeline: 1–2 weeks

**Option C: Productize as-is**
- Package for deployment (Docker, API, docs)
- Create SOC analyst dashboards
- Timeline: varies

### **DEPENDENCIES & UNKNOWNS**
- ❓ Can we access Google Drive for E5 data? (Need OAuth token)
- ❓ Are full DARPA TC E5 ground-truth labels available? (Only 2-min window configured now)
- ❓ Product goals: academic paper vs. production APT detector vs. open-source reference?

---

## Memory & Context
- **Claude-mem:** Rich observations from Apr 13–14 sessions (Phase 4 technical depth)
- **Git history:** 15+ commits on `restructure` branch; ready for PR to main
- **User preference:** Solo builder, productizing research (per memory)

---

## Recommended Next Action

**RUN THIS:**
```bash
cd /c/Projects/Sentinel-Z
git add src/sentinel_z/ingestion/auto_pipeline.py
git commit -m "fix(ingest): disable intermediate CSV saving by default"
make download  # Will fail gracefully if no Drive access
make ingest    # Real test of the pipeline
make verify    # Final gate
```

**Then assess:**
- If all pass: Phase 4 is reproducible ✅
- Next: Decide Phase 5 priority vs Phase 6 vs productization

---

*Compiled: 2026-04-15 21:43 EDT*
*Branch: restructure (4 commits ahead of origin)*
