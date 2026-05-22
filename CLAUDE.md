# Sentinel-Z — Claude Code Project Instructions

> **READ ME FIRST.** This file orients a fresh Claude Code session in 60 seconds.
> Full project state is in [`SESSION_HANDOFF.md`](SESSION_HANDOFF.md).
> Validated metrics with 95% CIs are in [`MODEL_CARD.md`](MODEL_CARD.md).

## What this project is

**Sentinel-Z** is a research-grade APT (Advanced Persistent Threat) detection
system for DARPA Transparent Computing data. It pairs a Random-Forest detector
on graph-behavioral features with a deterministic narrative engine that
converts detections into SOC-actionable explanations — without any LLM
dependency.

It is **explicitly an academic-first then commercial project**. The owner
(Kevin Doshi, CS student at SPIT) is targeting:

1. RAID 2027 / ACSAC 2026 paper (Tier-2, ~9 months out)
2. USENIX Security 2027 / NDSS 2028 paper (Tier-1, ~12-18 months out)
3. First commercial revenue at 18-24 months (MSSPs, government contractors,
   mid-market — NOT competing with Darktrace / CrowdStrike directly)

## Iron rules — these are non-negotiable

1. **No LLMs in the detection or narrative path.** The narrative engine is
   template-based with explicit signal citation. This is the product moat;
   adding LLM calls would betray the auditability story and is forbidden.
   LLM tools may only be used for meta-tasks (summarizing reports for humans).

2. **Every reported metric must carry a 95% CI** from at least 30-iteration
   stratified-bootstrap evaluation. No single-seed metrics in `MODEL_CARD.md`.
   No cherry-picked seeds. If you change detection logic, you re-run
   `scripts/rigorous_validation.py` and `scripts/stress_test.py` before claiming
   anything in docs.

3. **Honest reporting always.** If a change makes things worse, document it
   honestly. The differentiator vs. commercial products is exactly this
   discipline; betraying it eliminates the moat.

4. **No off-the-shelf tooling that defeats the moat.** Avoid:
   - SHAP/LIME for explanations (use the project's custom signal-citation
     narrative + counterfactual engine — see Phase 1 plan)
   - shadcn/ui (screams AI-generated startup; we have a distinctive visual
     language already)
   - LangChain / OpenAI SDK / Anthropic SDK (no LLMs, period)
   - Generic anomaly libraries (PyOD etc.) instead of project-specific algorithms

5. **Conventional Commits.** Format: `feat:`, `fix:`, `docs:`, `test:`,
   `refactor:`, `perf:`, `chore:`. The git log is part of the academic story.

## What to do in a new session

If you are picking up this project for the first time:

1. **Read `SESSION_HANDOFF.md` first** — it has the full state.
2. **Read `MODEL_CARD.md`** for current validated metrics.
3. **Read `docs/paper-drafts/raid-2027-outline.md`** for paper plan.
4. **Check `git log --oneline -20`** to see recent commits.
5. **Check `docs/PHASE_0_COMPLETION_REPORT.md`** for what just landed.
6. Ask the user what session goal is, then go.

## Current state at a glance

| Item | Value |
|---|---|
| Latest commit | `6c71af5 chore(phase-0): defensive foundation` |
| Active branch | `restructure` (4+ commits ahead of `origin/restructure`) |
| Detector version | v2 (7 base + 13 temporal features, RF + Youden threshold) |
| Validated metrics | ROC-AUC 0.9996 ± 0.0002; PR-AUC 0.832 ± 0.059; Recall 100%; FPR 0.35% |
| Validation rigor | 30-iter paired bootstrap + 7 stress tests + cross-host analysis |
| Dataset | DARPA TC E5 FiveDirections — 75,147 windows / 86 attacks |
| Phase status | Phase 0 (infrastructure) complete; Phase 1 (algorithmic depth) next |
| Open-source status | Repo is OSS-ready but NOT YET PUSHED to public GitHub |

## Where things live

```
src/sentinel_z/
├── ingestion/auto_pipeline.py   # CDM v18 + v20 parser, DARPA_ATTACK_PERIODS
├── pipeline/temporal_features.py # v2 rolling features (the 0.83 PR-AUC win)
├── detection/rf_detector.py     # PRIMARY detector + ModelCard + joblib persistence
├── narrative/story_builder.py   # Signal-driven narratives (NO LLM)
└── api/server.py                # FastAPI backend

scripts/
├── ingest_e5.py                 # E5 ingest (full pipeline, parallel parse)
├── ingest_e3.py                 # E3 ingest (Phase 0 addition, awaiting data)
├── verify_phase4.py             # Feature extraction → phase4_results.json
├── train_detector.py            # v1 RF training
├── train_detector_v2.py         # v2 RF training (current default)
├── rigorous_validation.py       # 30-bootstrap + significance + calibration
├── stress_test.py               # 7 stress tests
├── cross_engagement_eval.py     # Cross-engagement framework (Phase 0)
├── compare_magic.py             # MAGIC paired-bootstrap (awaiting MAGIC scores)
├── extract_e5_labels.py         # PDF ground-truth extractor (ran once)
└── run_detection.py             # End-to-end inference + narratives + campaigns

frontend/
├── app/page.tsx                 # Current dashboard composition
├── components/                  # PageHeader, MetricsHeader, CampaignList,
│                                # NarrativePanel, StressTestPanel
└── lib/api.ts                   # Typed FastAPI client

docs/
├── architecture.md
├── cdm-schema-notes.md
├── paper-drafts/raid-2027-outline.md
└── PHASE_0_COMPLETION_REPORT.md

# Validated artifacts
MODEL_CARD.md                    # Current metrics + limitations + stress tests
STRESS_TEST_REPORT.md            # 7 stress tests with industry comparison
INVESTIGATION_REPORT.md          # Forensic analysis of 5 unlabeled host-2 anomalies
SESSION_HANDOFF.md               # ← THE PRIMARY HANDOFF DOC
```

## The user's pending actions (do NOT do these for them)

These require credentials, accounts, or external systems Claude Code can't access:

1. Push the repo to a public GitHub remote (Kevin's GitHub account)
2. Download DARPA TC E3-CADETS (~50 GB, requires DARPA Drive access)
3. Set up MAGIC (https://github.com/FDUDSDE/MAGIC) and export per-window scores
4. Curate the 200 extracted E5 ground-truth candidates manually
5. Submit the RAID 2027 paper

If the user mentions any of these are done, the relevant downstream scripts
are already in place to consume the results.

## Conventions for this session

- **Working directory:** `c:\Projects\Sentinel-Z` (don't `cd` away unnecessarily)
- **Python:** use `/c/Users/conve/AppData/Local/Python/pythoncore-3.14-64/python.exe`
  when running scripts directly (the `python3` alias can hit Windows Store stub issues)
- **Git:** branch is `restructure`; main branch reference is `main`; tooling
  on Windows produces LF/CRLF warnings — those are benign
- **Long-running tasks:** use `run_in_background: true` and `Monitor` tool;
  do NOT poll output in a loop. The user has explicitly asked for progress
  visibility — give frequent, brief progress updates.

## Phase 1 (next phase) at a glance

When the user is ready to begin Phase 1, the three algorithmic pillars are:

1. **Contrastive Behavioral Embeddings (CBE)** — InfoNCE-trained 64-dim
   embeddings of subject behavioral context. Replaces hand-crafted features.
   The publishable algorithmic novelty.

2. **Causal Reasoning Engine (CRE)** — Backward provenance traversal +
   Bayesian inference over MITRE ATT&CK tactics + HMM for multi-stage
   attack sequence hypothesis. Replaces template-based stage classification.

3. **Mondrian Conformal Prediction** — Statistically calibrated SOC
   confidence with formal coverage guarantees and an abstain option.

Full Phase 1 plan in `SESSION_HANDOFF.md`. Do not start Phase 1 until the user
has run the Phase 0 cross-engagement and MAGIC comparison pipelines.
