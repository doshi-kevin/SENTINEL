# Sentinel-Z — Session Handoff Document

> **For the next Claude Code session.** This document is the single source of
> truth for everything that has happened, every decision that was made, and
> every action that is queued. Read this end-to-end before doing anything else.

**Last updated:** 2026-05-22 (Phase 0 complete)
**Current branch:** `restructure`
**Latest commit:** `6c71af5 chore(phase-0): defensive foundation`
**Total commits on branch:** 18 ahead of `origin/restructure`

---

## TL;DR — what to know in 90 seconds

You are picking up a real research + commercial cybersecurity project mid-stream.

- **Owner:** Kevin Doshi, CS student at SPIT. Solo builder. Wants both academic
  publications AND commercial revenue.
- **Project:** Sentinel-Z — provenance-based APT (Advanced Persistent Threat)
  detection with explainable, deterministic, signal-driven narratives. NO LLMs
  in the detection path. Validated on DARPA TC E5 FiveDirections.
- **Where we are:** Phase 0 (defensive foundation) is COMPLETE in code. The user
  must now run the data-dependent pipelines (E3 download, MAGIC comparison,
  ground-truth curation) before Phase 1 begins.
- **What's next (Phase 1):** Contrastive Behavioral Embeddings + Causal
  Reasoning Engine + Mondrian Conformal Prediction. ~3 months of work.
- **Paper plan:** RAID 2027 / ACSAC 2026 (Tier-2, ~9 months out) first;
  USENIX Security 2027 / NDSS 2028 (Tier-1, ~12-18 months out) second.

---

## 1. Project identity and decisions

### Who Kevin is and what he wants

- CS student at Sardar Patel Institute of Technology (SPIT), India
- Solo builder, NOT a team
- Ambitious but realistic — wants both publications AND eventual revenue
- Treats this as a serious research + commercial project, NOT a class project
- Demands brutal honesty — has explicitly rejected sugarcoating multiple times
- Has rejected vibe-coding / LLM-wrapper startup patterns — wants original work

### Strategic decisions made (these are LOCKED, do not revisit without good reason)

| Decision | Choice | Rationale |
|---|---|---|
| Academic vs commercial timing | Academic-first (9-12 mo), commercial second | Builds credibility + citations first |
| Open vs closed source | Open-source core (Apache 2.0) | Citations matter for academic career; commercial moat moves to integrations |
| Domain scope | Narrow — provenance-based APT detection only | Win one niche before broadening (Darktrace took 8 years to broaden) |
| Detection ceiling | RF v2 metrics in published SOTA range — STOP chasing more | Diminishing returns; effort goes to NEW signal types in Phase 1 |
| LLM usage | None in detection or narrative path | The auditability story IS the moat |
| Visual language | Custom (not shadcn/ui boilerplate) | "Screams AI-generated startup" — Kevin's words |
| Frontend chat UI | NOT going to be built | Implies LLM dependency, undermines moat |

### What this project is NOT

- NOT competing head-to-head with CrowdStrike / SentinelOne / Darktrace
- NOT an LLM-wrapper startup
- NOT going to be Fortune-500 enterprise sold
- NOT trying to win on raw detection accuracy (we're competitive, not better)

### What this project IS

- A research-grade detection system with disciplined methodology
- A unique deterministic narrative engine (the actual commercial moat)
- A defensible open-source reference implementation
- A 18-24 month path to first revenue from MSSPs + government + mid-market

---

## 2. Current validated metrics — what we can defensibly claim

All numbers below have 95% CIs from 30-iteration paired-bootstrap evaluation.
Source: `MODEL_CARD.md`, `STRESS_TEST_REPORT.md`.

### Held-out test performance (DARPA TC E5 FiveDirections)

| Metric | v2 (current default) | v1 (deprecated baseline) | Delta |
|---|:---:|:---:|:---:|
| **Test ROC-AUC** | **0.9996 ± 0.0002** | 0.977 ± 0.009 | +0.022 [95% CI: +0.012, +0.042] |
| **Test PR-AUC** | **0.832 ± 0.059** | 0.089 ± 0.033 | **+0.744** [95% CI: +0.615, +0.860] |
| **Test F1** | 0.433 | 0.039 | 11× higher |
| **Test Precision** | 29.3% | 2.0% | 14.7× higher |
| **Test Recall** | 100% | 96.2% | Perfect |
| **Test FPR** | 0.35% | 6.0% | 17× lower |
| **Brier score** | 0.0008 | 0.008 | 10× better calibration |

P(v2 ≤ v1) on each metric = 0.000 across all 30 paired bootstrap splits.

### What makes v2 work — temporal context features

Added in commit `0bb999c feat(v2): temporal correlation features`:

13 rolling 30-second statistics over: `unknown_ratio`, `num_nodes`,
`num_edges`, `density`, `network_ratio`, `fused_score`, plus an
`anomaly_count_30s` indicator.

**Permutation importance** (unbiased, from `rigorous_validation.py`):
- `unknown_ratio_30s_std` (rolling volatility of unknowns) — top feature
- `unknown_ratio_30s_mean` — 2nd
- `num_nodes_30s_max` — 3rd
- `density_30s_max` — 4th
- `network_ratio_30s_max` — 5th
- `anomaly_count_30s` — 6th
- Original per-window features rank lower

**Why it works:** APTs create *bursts* of unknown subjects across multiple
windows. Per-window detection misses this temporal structure. Confirmed by
the host-2 forensic finding (UUID `1e27fa885eae4792` appearing in 3
non-adjacent windows with 209 events each).

### Stress tests — all 6 passed

From `STRESS_TEST_REPORT.md` (commit `773017a`):

| Test | Result | Verdict |
|---|---|:---:|
| Shuffled-label leakage | ROC-AUC = 0.5007 on shuffled labels (expected 0.5) | ✅ PASS — no leakage |
| Rolling-context corruption | PR-AUC stable after attack-window feature replacement | ✅ PASS — signal in features |
| Class imbalance 10:1 → 1000:1 | PR-AUC degrades monotonically 0.98 → 0.87 | ✅ PASS — robust |
| Feature noise +10% std | PR-AUC drops 0.86 → 0.41 | ⚠️ Production risk |
| Window-size sensitivity | PR-AUC monotonic 0.30/0.54/0.86/0.91/0.99 | ✅ PASS — 30s is conservative |
| Cold-start 10% training | ROC-AUC 0.998 with 8 train attacks | ✅ PASS — deployable |
| Cluster holdout (±300s) | Degenerate (all attacks in one cluster) | ⚠️ Dataset limitation, NOT model |

### Industry comparison (from independent web search by Claude subagent)

| System | Venue | Dataset | ROC-AUC | F1 / PR-AUC |
|---|---|---|:---:|:---:|
| **Sentinel-Z (v2)** | (Phase 0) | E5-FiveDirections | **0.9996** | **PR-AUC 0.832** |
| MAGIC | USENIX Sec '24 | E3-THEIA | 0.999 | F1 0.991 |
| KAIROS | IEEE S&P '24 | E5-THEIA | 0.997 | precision 0.67 @ recall 1.0 |
| TFLAG | arXiv '25 | E5-THEIA | 0.997 | precision 0.67 @ recall 1.0 |
| FLASH | IEEE S&P '24 | E3 avg | — | F1 0.945 |
| APT-MCL | arXiv '25 | E3-CADETS | — | F1 0.999 |
| APT-MCL | arXiv '25 | unseen ransomware | — | **F1 0.242 (collapse)** |

**Critical context:** Published systems consistently **avoid E5-FiveDirections**
(the Windows TA1 platform). Choosing it makes our claim *stronger*, not weaker.

---

## 3. The forensic finding (potential paper headline)

Documented in `INVESTIGATION_REPORT.md`. The trained v2 RF flagged **5
host-2 windows** with confidence 0.87-0.88 matching the structural+behavioral
signatures of host-1 labeled attacks but NOT in DARPA's official ground truth.

| Smoking-gun evidence | Detail |
|---|---|
| UUID `1e27fa885eae4792` recurring | Appears in 3 of 5 flagged windows with **exactly 209 events each** |
| 4 additional UUIDs recurring across windows | Lateral-movement signature |
| Read/Open events 60-75% of total | Stealth recon profile |
| Write events 1-2% of total | Not modifying (stealth) |
| Network events present but minimal | Possible C2 heartbeat |
| Unknown-subject ratio 84-87% | Top 0.1% on host 2 |

DARPA's E5 ground truth is widely acknowledged as **incomplete** (KAIROS supp.,
Slot, OCR-APT, SRI 2025). The case for these being undiscovered attacks is
moderate-to-high; full confirmation requires cross-referencing raw event cmdlines.

---

## 4. Phase 0 — what just landed (commit `6c71af5`)

Phase 0 was about INFRASTRUCTURE not RESULTS. Every Phase 0 deliverable
enables a follow-on result that Kevin must produce by running pipelines on
real data.

### Phase 0 deliverable inventory

#### Open-source credibility
- `LICENSE` (Apache 2.0)
- `CITATION.cff` (machine-readable)
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
- `.github/` issue templates + PR template + dependabot + 5-job CI matrix

#### Reproducibility infrastructure
- `pyproject.toml` v0.2.0 with pinned dependencies
- `Dockerfile` (backend, multi-stage)
- `frontend/Dockerfile` (Next.js production)
- `docker-compose.yml` (backend + frontend + optional postgres)
- GitHub Actions: lint, test matrix (3.10/3.11/3.12), smoke, metrics-regression, docker build

#### CDM v18 (E3) support
- `CDMParser` now supports both v18 and v20 schemas
- `detected_schema_version` attribute set per file
- E3-only types silently skipped
- `DARPA_ATTACK_PERIODS` expanded with E3 entries (CADETS, THEIA, TRACE, FiveDirections)
- `docs/cdm-schema-notes.md` explains differences

#### Cross-engagement evaluation
- `scripts/ingest_e3.py` — mirrors `ingest_e5.py` for paired-comparison validity
- `scripts/cross_engagement_eval.py` — within-E5 + within-E3 + cross E5↔E3 with verdict classification

#### MAGIC baseline harness
- `scripts/compare_magic.py` — paired-bootstrap with identical seeds, stub mode for plumbing

#### E5 ground-truth extraction
- `scripts/extract_e5_labels.py` — PDF parser (pdfplumber + pypdf fallback)
- **Already ran successfully** — produced 200 candidate windows at
  `data/raw/e5/Ground_Truth/extracted_attack_windows.csv`
- ⚠️ Most candidates are CADETS-relevant, not FiveDirections. Human curation needed.

#### Documentation
- `README.md` REWRITTEN (legacy at `README.v1.md`, gitignored)
- `docs/architecture.md` — full component-layer architecture
- `docs/cdm-schema-notes.md` — v18 vs v20 differences
- `docs/paper-drafts/raid-2027-outline.md` — complete RAID 2027 paper skeleton
- `docs/PHASE_0_COMPLETION_REPORT.md` — full Phase 0 inventory

#### Frontend refresh
- `lib/api.ts` — typed FastAPI client
- `components/PageHeader.tsx` — identity + backend status indicator
- `components/MetricsHeader.tsx` — 4-tile ribbon with offline fallback
- `components/CampaignList.tsx` — clickable campaigns with MITRE badges
- `components/NarrativePanel.tsx` — detail view with collapsible evidence
- `components/StressTestPanel.tsx` — at-a-glance stress test status
- `app/page.tsx` — new dashboard composition (legacy `dashboard.tsx` orphaned)
- `app/layout.tsx` — Sentinel-Z metadata + dark theme

---

## 5. Pending user actions (Kevin must do these — Claude Code cannot)

In priority order:

### IMMEDIATE (this week)

1. **Push the repo to a public GitHub remote.**
   ```bash
   gh repo create kevin-doshi/sentinel-z --public --source=. --remote=origin
   git push origin restructure:main
   git push origin restructure
   ```
   Then verify the GitHub Actions CI matrix passes.

2. **Download DARPA TC E3-CADETS** (~50 GB compressed)
   - Source: https://github.com/darpa-i2o/Transparent-Computing (Engagement 3 section)
   - Drive folder: requires sign-in
   - Place files under `data/raw/e3/cadets/`
   - See `data/raw/e3/README.md` for full instructions

3. **Run cross-engagement evaluation**
   ```bash
   python scripts/ingest_e3.py --team cadets --max-files 2     # smoke first
   python scripts/ingest_e3.py --team cadets                    # full
   python scripts/verify_phase4.py --results-dir data/model_ready_e3/cadets/detection
   python scripts/cross_engagement_eval.py
   ```
   Report the resulting `cross_engagement_report.json` numbers. This is **the
   single most important data point for the RAID paper.**

### SHORT-TERM (this month)

4. **Set up MAGIC** (https://github.com/FDUDSDE/MAGIC)
   - Separate Python 3.8 environment (their requirement)
   - Run MAGIC on the same E5 windows Sentinel-Z saw
   - Export per-window scores to CSV (columns: `window_id,magic_score`)
   - Then: `python scripts/compare_magic.py --magic-scores <file>.csv`

5. **Curate the extracted E5 ground-truth candidates**
   - Review `data/raw/e5/Ground_Truth/extracted_attack_windows.csv`
   - Filter to FiveDirections-specific entries (most are CADETS)
   - Manually verify against raw events under `data/raw/e5/Data/`
   - Replace `DARPA_ATTACK_PERIODS["e5"]["fivedirections"]` in
     `src/sentinel_z/ingestion/auto_pipeline.py`
   - Re-run `scripts/ingest_e5.py --force` to relabel

### MEDIUM-TERM (next 2 months)

6. **Email MAGIC, KAIROS, FLASH authors** with the project link and a polite
   "we'd love your feedback on our methodology" message. Don't ask for
   collaboration; ask for critique. They'll respect that.

7. **Draft the RAID 2027 paper** from
   `docs/paper-drafts/raid-2027-outline.md`. Plug in real cross-engagement
   and MAGIC-comparison numbers. Target RAID 2027 deadline (~Feb/Mar 2027).

8. **Begin Phase 1 work** (see section 7 below).

---

## 6. The full commit history (what already exists)

```
6c71af5  chore(phase-0): defensive foundation - OSS infra, E3 support, paper, frontend
773017a  test(stress): 7-stress-test suite + STRESS_TEST_REPORT confirms v2 is real
0bb999c  feat(v2): temporal correlation features = transformational improvement
4cb91c3  test: rigorous validation suite + honest CI numbers in model card
c7670ef  feat(investigation): forensic dossier on 5 host-2 unlabeled anomalies
52bc324  feat(validation): cross-host LOHO-CV + host-conditional analysis
c716184  feat: full 15-file pipeline + Youden threshold + updated model card
6090d25  fix(ingest): cap parallel parse workers at 4 (prevent OOM)
9709b9b  feat(scripts): full_pipeline.py orchestrator for post-ingest steps
0a39382  docs(README): replace overfit claims with honest metrics + MODEL_CARD reference
57e4a22  perf(ingest): parallel Phase 1 parse with top-level worker function
e9e2c53  fix: semantic engine loads subjects from all host partitions
0db54c7  fix: pandas 2.x + networkx 3.x API compatibility
169f859  feat(narrative): signal-driven story generation from real Phase 4 data
... (earlier commits build out the original v1 detector, semantic_risk_engine,
       narrative engine, data pipeline, and validation framework)
```

---

## 7. Phase 1 plan — the algorithmic depth (DO NOT START until Phase 0 user actions land)

Phase 1 takes Sentinel-Z from "competitive prototype" to "genuine research
contribution." Estimated 3 months of focused work, parallel-tracked.

### Pillar 1: Contrastive Behavioral Embeddings (CBE) — the algorithmic novelty

**Hypothesis:** Hand-crafted features (`unknown_ratio` etc.) plateau because
they're proxies for a deeper signal — behavioral role. A self-supervised
embedding that captures behavioral role should beat hand-crafted features
AND transfer across engagements.

**Algorithm:**
1. For each subject S in a window, define its behavioral context as a
   multiset of `(event_type, object_class)` pairs.
2. Construct positive pairs (same S at slightly different times) and
   negative pairs (different S in same window).
3. Train an attention-based encoder with InfoNCE loss (temperature τ=0.07).
4. Output: 64-dim L2-normalized embedding per subject.
5. At inference, window anomaly score = max distance of any subject's
   embedding from a benign reference set.

**Implementation files (planned, do not exist yet):**
- `src/sentinel_z/detection/cbe/encoder.py`
- `src/sentinel_z/detection/cbe/training.py`
- `src/sentinel_z/detection/cbe/inference.py`
- `scripts/train_cbe.py`

**Estimated timeline:** 4-6 weeks
**Publication target:** USENIX Security 2027 — companion to Pillar 2

### Pillar 2: Causal Reasoning Engine (CRE) — replaces template stage classification

**Algorithm:**
1. Backward provenance traversal from the highest-anomaly subject (BFS up
   FORK/EXECUTE/LOAD edges, depth 5).
2. Forward impact assessment (files written, network destinations).
3. Bayesian inference over MITRE ATT&CK tactics: `P(tactic | observed_subgraph)`
   computed from per-tactic event-type distributions extracted from
   MITRE STIX 2.1 data.
4. Multi-stage attack chain: HMM with Viterbi decoding over tactics.

**Implementation files (planned):**
- `src/sentinel_z/detection/causal/traversal.py`
- `src/sentinel_z/detection/causal/bayesian.py`
- `src/sentinel_z/detection/causal/mitre_kb.py`

**Estimated timeline:** 4-6 weeks
**Publication target:** USENIX Security 2027 — companion to Pillar 1

### Pillar 3: Mondrian Conformal Prediction — SOC trust calibration

**Algorithm:**
1. Held-out calibration set (10% of training, with original class imbalance).
2. Compute nonconformity scores for calibration set.
3. For new prediction, compute conformal p-value with coverage guarantee.
4. Mondrian variant: separate calibration per class (handles 0.11% positive rate).
5. Abstain option: if p-value is in [α-0.02, α+0.02], output "ABSTAIN".

**Implementation files (planned):**
- `src/sentinel_z/detection/conformal/calibration.py`
- `src/sentinel_z/detection/conformal/mondrian.py`

**Estimated timeline:** 2-3 weeks
**Publication target:** Section of USENIX paper OR short workshop paper

### Pillar 4 (deferred): Cytoscape provenance graph visualization

Custom layout (NOT D3 force-directed — semantically wrong for causal graphs):
- Subjects on left, objects on right
- Time on horizontal axis within each side
- Edge colored by event type
- Anomalous nodes with subtle pulse animation

**Estimated timeline:** 1-2 weeks
**Pre-requirement:** Pillar 2 (CRE) finished so the visualization has
something causally meaningful to render.

---

## 8. Critical conventions Claude Code must follow

### When making changes

- Follow **Conventional Commits** (`feat:`, `fix:`, `docs:`, etc.)
- Every change to detection logic requires re-running
  `scripts/rigorous_validation.py` AND updating `MODEL_CARD.md` numbers
  with new 95% CIs
- Every new module under `src/sentinel_z/` needs unit tests with ≥80% coverage
- No off-the-shelf XAI tools (SHAP/LIME); use project-specific signal-citation
  narrative + counterfactual approach
- No shadcn/ui in the frontend; the visual language is distinctive on purpose

### When investigating issues

- The Windows Python alias (`python3`) can hit Microsoft Store stub problems.
  Use `/c/Users/conve/AppData/Local/Python/pythoncore-3.14-64/python.exe`
  directly if `python3` errors out.
- Long-running pipelines: use `run_in_background: true` and the `Monitor` tool
  for progress. NEVER poll output in a loop.
- The `data/` directory is gitignored; everything in there can be regenerated
  via the scripts.

### When writing reports / docs

- Brutal honesty always. If a result is worse than expected, document it
  honestly. The owner explicitly demands this.
- Every metric in any doc must have a 95% CI.
- Comparisons against other systems must use IDENTICAL seeds (paired
  bootstrap) when possible.

### When in doubt

- **Re-read this file (`SESSION_HANDOFF.md`)** before improvising.
- Read `MODEL_CARD.md` for current claimed metrics.
- Read `docs/paper-drafts/raid-2027-outline.md` for the paper plan.
- Check `git log --oneline -10` for recent context.

---

## 9. Files Claude Code should know how to find

```
# Project state (read first)
SESSION_HANDOFF.md              ← this file
CLAUDE.md                       ← session orientation
MODEL_CARD.md                   ← validated metrics + limitations
STRESS_TEST_REPORT.md           ← 7 stress tests
INVESTIGATION_REPORT.md         ← forensic findings
docs/PHASE_0_COMPLETION_REPORT.md  ← what Phase 0 delivered

# Strategic docs
docs/paper-drafts/raid-2027-outline.md
docs/architecture.md
docs/cdm-schema-notes.md

# Code (read on demand)
src/sentinel_z/                 ← all Python source
scripts/                        ← CLI tools
frontend/                       ← Next.js dashboard

# Data (gitignored; populated by scripts)
data/raw/e5/                    ← E5 raw .bin.gz files (downloaded)
data/raw/e3/                    ← E3 raw files (NOT YET DOWNLOADED)
data/auto_processed/            ← E5 intermediate outputs
data/model_ready/               ← E5 final graphs + features
data/model_ready_e3/            ← E3 outputs (will exist after ingest_e3.py runs)
models/rf_detector_v2.joblib    ← Trained v2 model + checksum + model_card.json
```

---

## 10. Quick reference: high-frequency commands

```bash
# Inspect current state
git log --oneline -10
git status

# Re-run validation suite (after detection-logic changes)
python scripts/rigorous_validation.py
python scripts/stress_test.py

# Smoke-test the full pipeline on 2 files (~5 min)
python scripts/ingest_e5.py --max-files 2 --force
python scripts/verify_phase4.py
python scripts/train_detector_v2.py
python scripts/run_detection.py

# Cross-engagement evaluation (after E3 data is downloaded)
python scripts/ingest_e3.py --team cadets
python scripts/cross_engagement_eval.py

# MAGIC comparison (after MAGIC scores are exported)
python scripts/compare_magic.py --magic-scores magic_scores_e5.csv

# Full demo stack
docker-compose up                # backend on :8000, frontend on :3000
```

---

## Closing note for the new session

Kevin has invested significant effort getting Sentinel-Z to this state.
Treat this work with the same discipline that produced it:

- Honest reporting always
- Every metric gets a CI
- No LLMs in the detection path
- No vibe-coding shortcuts
- No premature scope expansion

The single most important action right now is **the user pushing this to a
public GitHub repo and running the E3 cross-engagement evaluation.**

When that happens, you have everything you need to start Phase 1.

Good luck. Don't break the discipline.
