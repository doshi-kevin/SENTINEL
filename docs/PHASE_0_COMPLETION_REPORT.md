# Phase 0 Completion Report

**Phase:** 0 — Defensive Foundation
**Date:** 2026-05-22
**Plan reference:** Sentinel-Z Strategic Implementation Plan
**Status:** Infrastructure complete; data-dependent runs queued for user execution

---

## Executive summary

Phase 0 set up the entire defensive foundation needed to make Sentinel-Z's
existing v2 metrics defensible at a Tier-2 venue (RAID 2027 / ACSAC 2026)
and ready for public open-source release. Every piece of infrastructure
needed for the headline cross-engagement evaluation and MAGIC comparison
is in place; the only remaining work is data acquisition (which requires
the user's DARPA TC Drive credentials) and running the pipelines end-to-end.

**What is done in code:** all 14 planned items.
**What requires user action:** downloading E3-CADETS data, running MAGIC,
manually reviewing extracted ground-truth candidates.

---

## Deliverables checklist

### 1. Open-source credibility

- [x] `LICENSE` (Apache 2.0 — chosen for permissive commercial-use compatibility)
- [x] `CITATION.cff` (machine-readable, GitHub auto-renders)
- [x] `CONTRIBUTING.md` (workflow, code style, research-contribution path)
- [x] `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1)
- [x] `.github/ISSUE_TEMPLATE/` (bug report + research-reproduction templates)
- [x] `.github/PULL_REQUEST_TEMPLATE.md`
- [x] `.github/dependabot.yml` (monthly dependency updates)

### 2. Reproducibility infrastructure

- [x] `pyproject.toml` — Apache 2.0 license, pinned dependencies, ruff/black/mypy/pytest config, console scripts
- [x] `Dockerfile` (multi-stage runtime image)
- [x] `frontend/Dockerfile` (Node 20 alpine, multi-stage build)
- [x] `docker-compose.yml` (backend + frontend + optional postgres)
- [x] `.github/workflows/ci.yml` (lint, test, smoke, metrics regression, docker build)

### 3. CDM v18 (E3) support

- [x] `src/sentinel_z/ingestion/auto_pipeline.py` — `CDMParser` now supports both
      v18 and v20 schemas; `detected_schema_version` attribute set per file
- [x] `RECORD_TYPES` enumerates both v18 and v20 record types for documentation
- [x] E3-only types (`UnnamedPipeObject`, `MemoryObject`, `SrcSinkObject`)
      silently skipped without breaking the pipeline
- [x] `DARPA_ATTACK_PERIODS` populated with E3 entries (CADETS, THEIA, TRACE,
      FiveDirections) from public DARPA TA5.1 documentation
- [x] `docs/cdm-schema-notes.md` explains differences and known issues
- [x] `data/raw/e3/README.md` instructs users where to download

### 4. Cross-engagement evaluation

- [x] `scripts/ingest_e3.py` — full E3 ingest pipeline (parallel parse + graph build)
      mirroring `ingest_e5.py` for protocol consistency
- [x] `scripts/cross_engagement_eval.py` — the headline framework:
      - Within-E5 baseline (bootstrap)
      - Within-E3 baseline (bootstrap)
      - Cross-engagement E5 → E3 (with full metrics)
      - Reverse cross-engagement E3 → E5
      - Verdict classification (STRONG/MODERATE/WEAK/FAILED TRANSFER)
- [x] Both ingest scripts use the same temporal-feature engineering for
      paired-comparison validity

### 5. MAGIC baseline comparison

- [x] `scripts/compare_magic.py` — paired-bootstrap framework:
      - Loads pre-computed MAGIC scores from CSV (you run MAGIC externally)
      - Aligns by window_id
      - Trains Sentinel-Z v2 on identical seeds (0..29 by default)
      - Reports paired ROC-AUC, PR-AUC, F1, Recall, Precision, FPR deltas
        with 95% CIs and significance verdict
      - Stub mode for plumbing tests without running MAGIC

**User action required:** Clone https://github.com/FDUDSDE/MAGIC, get it running
in Python 3.8 + DGL environment, export per-window scores to CSV, then run
`python scripts/compare_magic.py --magic-scores magic_scores_e5.csv`.

### 6. E5 ground-truth extraction

- [x] `scripts/extract_e5_labels.py` — PDF parser (pdfplumber + pypdf fallback)
- [x] Successfully extracted ~200 candidate attack windows from
      `TA51_Final_report_E5.pdf` (saved to
      `data/raw/e5/Ground_Truth/extracted_attack_windows.csv` and `.py`)
- [x] Heuristic-based: anchors on attack keywords + timestamp patterns + context

**User action required:** Manually review the CSV. The PDF largely documents
CADETS scenarios (not FiveDirections), and some timestamps have OCR artifacts.
Curate the FiveDirections-specific subset before updating `DARPA_ATTACK_PERIODS`.

### 7. Documentation

- [x] `README.md` — rewritten with hero, badges, results table, industry comparison,
      quick-start, architecture diagram, roadmap, citation block (legacy preserved
      as `README.v1.md`)
- [x] `docs/architecture.md` — full component-layer architecture
- [x] `docs/cdm-schema-notes.md` — practical v18/v20 differences
- [x] `docs/paper-drafts/raid-2027-outline.md` — full paper skeleton with
      abstract draft, outline, submission checklist, risk register

### 8. Frontend dashboard refresh

- [x] `frontend/lib/api.ts` — typed API client for backend
- [x] `frontend/components/PageHeader.tsx` — identity + backend status indicator
- [x] `frontend/components/MetricsHeader.tsx` — 4-tile metrics ribbon with
      graceful offline fallback
- [x] `frontend/components/CampaignList.tsx` — clickable campaign list with
      MITRE tactic badges
- [x] `frontend/components/NarrativePanel.tsx` — detail view with collapsible
      signal evidence
- [x] `frontend/components/StressTestPanel.tsx` — at-a-glance stress test verdicts
- [x] `frontend/app/page.tsx` — new dashboard composition
- [x] `frontend/app/layout.tsx` — Sentinel-Z metadata + dark theme
- [x] `frontend/Dockerfile` — production multi-stage build
- [x] `frontend/README.md` — frontend-specific docs

**Deferred to Phase 1:** Provenance graph visualization (Cytoscape custom layout).
The infrastructure is in place; the graph component itself is non-trivial and
requires the graph-format design decisions described in Phase 1 of the strategic plan.

---

## What this enables (immediately usable)

You can now, with no further coding:

1. **Push to GitHub publicly** — the repository is OSS-ready (license, citation,
   contribution guide, CI, issue templates all present).
2. **Run cross-engagement validation** once E3 data is downloaded:
   ```bash
   python scripts/ingest_e3.py --team cadets
   python scripts/verify_phase4.py --results-dir data/model_ready_e3/cadets/detection
   python scripts/cross_engagement_eval.py
   ```
3. **Run MAGIC comparison** once MAGIC scores are exported:
   ```bash
   python scripts/compare_magic.py --magic-scores magic_scores_e5.csv
   ```
4. **Refine E5 ground truth** by reviewing
   `data/raw/e5/Ground_Truth/extracted_attack_windows.csv`, curating the
   FiveDirections subset, and updating `DARPA_ATTACK_PERIODS` in
   `src/sentinel_z/ingestion/auto_pipeline.py`.
5. **Demo the frontend** at `npm run dev` in `frontend/` — works offline with
   sample data, connects to the backend automatically when available.
6. **Stand up the full stack** with `docker-compose up`.

---

## What is intentionally NOT in Phase 0

The following are deferred to Phase 1 per the strategic plan:

- Contrastive Behavioral Embeddings (CBE) — the core algorithmic novelty
- Causal Reasoning Engine (CRE) — Bayesian kill-chain inference
- Conformal Prediction — Mondrian inductive conformal
- Cytoscape provenance graph visualization (frontend)
- Rust streaming engine
- Sysmon / eBPF / OSQuery ingestion adapters

---

## Known weak points (be honest)

1. **Cross-engagement evaluation has NOT actually been run yet.** The
   script exists, the schema support exists, but the E3 data is not
   downloaded. Until this runs, we have ZERO evidence the model generalizes.
   **This is the single most important next action.**

2. **MAGIC comparison has not actually been run.** The harness exists; MAGIC
   itself has not been installed and run. The paired-bootstrap framework
   requires the user to set up MAGIC's Python 3.8 + DGL environment and
   export per-window scores. Until this happens, our paper has no baseline
   comparison.

3. **The extracted ground-truth candidates are LARGELY CADETS, not
   FiveDirections.** The TA5.1 PDF mostly documents CADETS scenarios; the
   FiveDirections subset of the PDF is smaller. User review is required to
   improve the E5 FiveDirections label set.

4. **The frontend lacks a real provenance graph viewer.** Cytoscape custom
   layout is Phase 1 work. The current dashboard is metrics + campaigns +
   narratives only.

5. **CI/CD has not been activated.** `.github/workflows/ci.yml` is in place
   but will only start running once the repo is pushed to GitHub. The user
   must verify the matrix passes on their account.

6. **Pinned dependency versions in `pyproject.toml` are the developer's
   current installed versions** — they should reproduce on Linux/macOS/Windows
   but may need adjustment if Phase 1 work bumps any of them.

---

## Recommended user actions (priority order)

1. **Push the current branch to a public GitHub repository.** The work is
   defensible as-is for the Tier-2 paper plan; sitting on it costs us citations.

2. **Download DARPA TC E3-CADETS** from the Drive folder linked in the official
   GitHub repository (`data/raw/e3/README.md` has instructions). Approximately
   50 GB compressed.

3. **Run the E3 pipeline**:
   ```bash
   python scripts/ingest_e3.py --team cadets --max-files 2   # smoke
   python scripts/ingest_e3.py --team cadets                  # full
   python scripts/cross_engagement_eval.py
   ```

4. **Set up MAGIC** (https://github.com/FDUDSDE/MAGIC) in a separate Python
   3.8 environment, run it on the same E5 windows, export scores, and run
   `python scripts/compare_magic.py --magic-scores <file>`.

5. **Curate the extracted E5 ground truth.** The candidates file is at
   `data/raw/e5/Ground_Truth/extracted_attack_windows.csv`. Filter to the
   FiveDirections-relevant subset and patch into `DARPA_ATTACK_PERIODS`.

6. **Write the RAID 2027 paper** from the outline in
   `docs/paper-drafts/raid-2027-outline.md`. Plug in actual cross-engagement
   and MAGIC-comparison numbers from steps 3 and 4.

---

## File inventory (Phase 0 additions)

```
NEW FILES:
  LICENSE
  CITATION.cff
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  Dockerfile
  docker-compose.yml

  .github/workflows/ci.yml
  .github/dependabot.yml
  .github/ISSUE_TEMPLATE/bug_report.md
  .github/ISSUE_TEMPLATE/research_reproduction.md
  .github/PULL_REQUEST_TEMPLATE.md

  scripts/ingest_e3.py
  scripts/cross_engagement_eval.py
  scripts/compare_magic.py
  scripts/extract_e5_labels.py

  docs/architecture.md
  docs/cdm-schema-notes.md
  docs/PHASE_0_COMPLETION_REPORT.md  ← this file
  docs/paper-drafts/raid-2027-outline.md

  data/raw/e3/README.md
  data/raw/e5/Ground_Truth/extracted_attack_windows.csv  (auto-generated)
  data/raw/e5/Ground_Truth/extracted_attack_windows.py   (auto-generated)

  frontend/lib/api.ts
  frontend/components/PageHeader.tsx
  frontend/components/MetricsHeader.tsx
  frontend/components/CampaignList.tsx
  frontend/components/NarrativePanel.tsx
  frontend/components/StressTestPanel.tsx
  frontend/Dockerfile

MODIFIED FILES:
  README.md                         (rewritten; legacy in README.v1.md)
  pyproject.toml                    (v0.2.0, pinned deps, Apache 2.0)
  src/sentinel_z/ingestion/auto_pipeline.py
                                    (CDM v18 support, DARPA_ATTACK_PERIODS expanded)
  frontend/app/page.tsx             (new dashboard composition)
  frontend/app/layout.tsx           (new metadata + dark theme)
  frontend/README.md                (rewritten)
```

---

## Closing note

Phase 0 was deliberately about INFRASTRUCTURE not RESULTS. Every Phase 0
deliverable enables a follow-on result that the user must produce by running
the pipelines on real data. The work is honest and defensible; the next
step is the user's to take.

When the user reports back with the cross-engagement and MAGIC comparison
numbers, Phase 1 (Contrastive Behavioral Embeddings, Causal Reasoning Engine,
Conformal Prediction) begins.
