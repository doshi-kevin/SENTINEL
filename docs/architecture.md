# Sentinel-Z Architecture

This document describes the system architecture in detail. For a quick overview,
see the README. For per-component performance, see [MODEL_CARD.md](../MODEL_CARD.md).

## Component layers

```
┌──────────────────────────────────────────────────────────────────┐
│  Ingestion Layer (Python)                                        │
│  src/sentinel_z/ingestion/                                       │
│    - CDMParser (Avro v18 + v20 compatible)                       │
│    - AutoPipeline (orchestration, parallel file parsing)         │
│    - Schema detection (cdm18 vs cdm20 auto-detected per file)    │
├──────────────────────────────────────────────────────────────────┤
│  Pipeline Layer (Python)                                         │
│  src/sentinel_z/pipeline/                                        │
│    - WindowGenerator (1-second floor-buckets, deduped)           │
│    - GraphConstructor (NetworkX DiGraph per window)              │
│    - FeatureEngineer (node features: degree, centrality, etc.)   │
│    - GraphExporter (JSON serialization for downstream)           │
│    - temporal_features (rolling 30s context, the v2 feature set) │
├──────────────────────────────────────────────────────────────────┤
│  Detection Layer (Python)                                        │
│  src/sentinel_z/detection/                                       │
│    - rf_detector.py (RandomForest + ModelCard + joblib persistence)│
│    - semantic_risk_engine.py (legacy v1 contextual scorer; kept  │
│      for explanation context only)                               │
│    - semantic_resolver.py (UUID -> behavioral entity type)       │
├──────────────────────────────────────────────────────────────────┤
│  Narrative Layer (Python, deterministic - NO LLM)                │
│  src/sentinel_z/narrative/                                       │
│    - story_builder.py                                            │
│       Stage inference from event-type distribution               │
│       MITRE ATT&CK tactic mapping (rule-based)                   │
│       Signal citation in every sentence                          │
├──────────────────────────────────────────────────────────────────┤
│  API Layer (Python)                                              │
│  src/sentinel_z/api/                                             │
│    - FastAPI server                                              │
│    - REST + WebSocket endpoints                                  │
│    - /sentinel-z/timeline, /graph, /story/window/:id, etc.       │
├──────────────────────────────────────────────────────────────────┤
│  Frontend Layer (TypeScript, Next.js)                            │
│  frontend/                                                       │
│    - Provenance graph visualization (Cytoscape, custom layout)   │
│    - Narrative panel with collapsible evidence                   │
│    - Campaign timeline                                           │
└──────────────────────────────────────────────────────────────────┘
```

## Data flow (batch)

```
.bin.gz / .json.gz   →  CDMParser  →  events DataFrame
                                       (in-memory per file)
                              ↓
                    WindowGenerator  →  1-second window list
                              ↓
              ProcessPoolExecutor (18 workers)
                              ↓
         GraphConstructor + FeatureEngineer (per worker)
                              ↓
            GraphExporter  →  window_XXXX.json files
                              ↓
                  labels.csv  +  graph JSONs
                              ↓
            verify_phase4.py  →  feature extraction
                              ↓
           phase4_results.json (one row per window)
                              ↓
         ┌──────────────────────┴──────────────────────┐
         ↓                                             ↓
   train_detector_v2.py                       run_detection.py
         ↓                                             ↓
   models/rf_detector_v2.joblib              detections.json
                                              + narratives.json
                                              + campaigns.json
```

## Data flow (streaming - future Phase 2)

```
Sysmon / eBPF / OSQuery events  →  custom binary wire protocol over TLS
                                              ↓
                       Lock-free SPMC ring buffer (Rust)
                                              ↓
                       Incremental graph construction (Rust)
                                              ↓
                       ONNX-exported RF inference (Rust)
                                              ↓
                       gRPC stream → API layer → frontend
```

## Engagement-aware ingestion

CDM has evolved across DARPA engagements:

| Engagement | Year | CDM version | Marker string |
|---|---|---|---|
| E3 | 2018 | v18 | `com.bbn.tc.schema.avro.cdm18.*` |
| E5 | 2019 | v20 | `com.bbn.tc.schema.avro.cdm20.*` |

`CDMParser._route_record` detects the version per record on the fly by
substring-matching the schema name. Both versions share the same record-routing
logic since the major record types (Event, Subject, FileObject, NetFlowObject,
Principal) have compatible field names. E3-specific types (UnnamedPipeObject,
MemoryObject, SrcSinkObject) are silently skipped — they don't carry signals
that affect detection at the window level.

After parsing, `CDMParser.detected_schema_version` is one of `cdm18`, `cdm20`,
or `None`. Use this to look up the correct `DARPA_ATTACK_PERIODS` entry.

## Detector versions

| Version | Features | Status | When to use |
|---|---|---|---|
| v1 | 7 per-window features | Deprecated as primary; kept as baseline | Statistical comparison only |
| v2 | 7 per-window + 13 temporal (current) | Production default | All production detection |
| v3 (planned) | + Contrastive Behavioral Embeddings | Phase 1 R&D | Cross-engagement transfer |

## Reproducibility guarantees

Every metric in `MODEL_CARD.md` should reproduce within bootstrap noise on:
- Python 3.10, 3.11, 3.12, 3.13
- numpy 2.1, pandas 2.2, scikit-learn 1.5
- Linux (Ubuntu 22.04, 24.04), macOS 14+, Windows 11+
- CPU-only path (GPU not required)

If you observe a metric outside the 95% CI in `MODEL_CARD.md`, open an issue
with full reproduction details.

## Why no LLMs in the core path

A SOC analyst evaluating an alert from Sentinel-Z needs to be able to verify
the narrative against the underlying graph. An LLM-generated narrative is
inherently non-verifiable: the text might say "PowerShell spawned by an
unknown parent process" but you cannot trust the model didn't invent any of
those terms.

Deterministic templates with explicit signal citation give us:
- Reproducibility (the same input always produces the same output)
- Auditability (every claim points to a feature value)
- No external dependencies (no API keys, no usage fees, no rate limits)
- No PII risk (no data leaves the deployment)
- Faster (template substitution is microseconds vs. seconds for LLM calls)

The trade-off is lower fluency. We believe this is the right trade-off for a
security tool. See `src/sentinel_z/narrative/story_builder.py` for the templates.

## Performance characteristics (measured)

| Stage | Throughput | Latency |
|---|---|---|
| CDM parse (single file, fastavro) | ~95K records/sec | sequential |
| CDM parse (parallel, 4 workers) | ~340K records/sec | sequential per file |
| Graph construction (per window) | ~50ms (avg), ~250ms (large) | per window |
| Feature extraction (per window) | ~20ms | per window |
| RF v2 inference (per window) | ~0.3ms | per window |
| Narrative generation | ~5ms | per window |

End-to-end batch on 75K windows: ~30 minutes on a single machine (16 cores, 32GB RAM).

## Production deployment (future Phase 2)

Target latency for streaming: < 200ms P99 from event ingestion to narrative output.
Achieving this requires the Rust streaming engine (`crates/sentinel-stream`).

## Open architectural questions

These are deliberate non-decisions that we will resolve through experimentation:

1. **Storage layer.** For deployed production, do we keep graphs as JSON in
   blob storage, or switch to a column-store (DuckDB, Parquet) for analytics?
2. **Multi-tenant isolation.** Process-level, container-level, or VM-level
   isolation for managed-service deployments?
3. **Concept drift.** Do we retrain on a schedule, retrain on drift detection,
   or use online learning?

These are tracked as GitHub issues for community input.
