# Sub-project A — Acquire DARPA TC E5 + Reproduce Phase 4

**Date:** 2026-04-14
**Status:** Draft — pending user approval
**Branch:** `restructure` (will continue here unless user wants a sub-branch)
**Author:** Claude (Sentinel-Z restart session)

---

## 1. Goal

End state: a contributor with a fresh `git clone` and Drive access can run **one command** and get to the published Phase 4 results.

```bash
make reproduce   # → ROC-AUC ≈ 0.8628, 6,051 graphs on disk
```

Concretely:
- `data/raw/e5/` populated with DARPA TC E5 (FiveDirections) Avro files (≈ 292 MB)
- `data/auto_processed/graphs/` populated with ≈ 6,051 window JSONs
- `data/auto_processed/labels.csv` populated with ground-truth labels (~85 attack rows)
- `python scripts/verify_phase4.py` exits 0 with `ROC-AUC = 0.86xx ✓`

---

## 2. Context: where the data actually lives

The `darpa-i2o/Transparent-Computing` GitHub repository contains **schema, tooling, ground truth PDFs, and READMEs only — not the dataset bytes.** The actual Avro logs are hosted on a Google Drive folder maintained by Five Directions Inc.:

- **Drive folder URL:** https://drive.google.com/drive/folders/1okt4AYElyBohW4XiOBqmsvjwXsnUjLVf
- **Drive folder name:** `Engagement5`
- **Top-level contents:** `Data/`, `Ground_Truth/`, `Schema/`, `Tools/`, `Engagement-5-Event-Log.md`, `README.md`, `README.pdf`
- **Access:** sign-in required (shared folder, not fully public). The user previously accessed this folder during the Jan 2026 Phase 1 ingest run.

This means we cannot use `wget`, `curl`, `gh release download`, or `git lfs` — we need a Google-Drive-aware tool.

---

## 3. Approach

### 3.1 Considered alternatives

| # | Approach | Verdict |
|---|---|---|
| 1 | Manual browser download | **Fallback only.** Reliable but unreproducible; future contributors can't `make reproduce`. |
| 2 | `gdown` Python library + `gdown.download_folder()` | **Chosen primary.** Single dev dep, scriptable, idempotent. Sometimes flaky on multi-GB folders — that's why we keep #1 as fallback. |
| 3 | `rclone` with Drive remote | Most robust for huge downloads (resumable). Rejected because it requires installing a non-Python tool + interactive OAuth dance — too much friction for a 292 MB one-time grab. |

### 3.2 Chosen plan

`gdown` as the primary path, manual download documented as the fallback. The download script must be **idempotent** (re-runs are no-ops if files already present, hash-checked).

---

## 4. Files to create / modify

| Path | Purpose |
|---|---|
| `scripts/download_e5.py` | Uses `gdown.download_folder()` with the E5 Drive folder ID; targets `data/raw/e5/`. Idempotent (skip if file exists). Prints final byte count + file count. Exits non-zero with a clear message if Drive access fails, pointing to the manual-fallback section of the README. |
| `scripts/ingest_e5.py` | Thin wrapper: `from src.sentinel_z.ingestion.auto_pipeline import AutoPipeline; AutoPipeline(output_dir="data/auto_processed").ingest("data/raw/e5/")`. Logs progress per file. Skips if `data/auto_processed/graphs/` already has ≥ 6,000 JSONs (idempotent). |
| `scripts/verify_phase4.py` | Smoke check: (a) count graph JSONs ≥ 6,000, (b) `labels.csv` exists with attack rows present, (c) run `run_phase4_pipeline()` and parse the resulting `phase4_results.json`, (d) assert `0.84 ≤ roc_auc ≤ 0.88`. Prints a green ✓ on success, red ✗ with diff on failure. |
| `Makefile` | Targets: `download`, `ingest`, `verify`, `reproduce` (= download + ingest + verify), `clean-data` (rm -rf `data/auto_processed/`, prompt before rm-ing `data/raw/`). |
| `pyproject.toml` | Add `gdown>=5.0` to `[project.optional-dependencies].dev`. (Not core — only needed for one-time bootstrap.) |
| `README.md` § 9 (Quick Start) | Add a "First-time setup" subsection: install `[dev]`, `make reproduce`. Also add a "Manual data fallback" subsection with the Drive URL + step-by-step instructions for when `gdown` fails. |
| `tests/test_smoke.py` | Add `test_scripts_parse()` — every file under `scripts/` AST-parses. Keeps the new scripts honest. |

**Total new code estimate:** ~150 LOC across 3 scripts + Makefile + minor README/test edits.

---

## 5. Detailed behavior

### 5.1 `scripts/download_e5.py`

```text
1. Read DRIVE_FOLDER_ID from a constant at top of file (= 1okt4AYElyBohW4XiOBqmsvjwXsnUjLVf).
2. Ensure data/raw/e5/ exists.
3. Try `gdown.download_folder(id=..., output="data/raw/e5", quiet=False, use_cookies=True)`.
4. On success: walk data/raw/e5/, count *.bin.gz / *.avro files, print total size, exit 0.
5. On failure (DriveAccessError / RuntimeError):
   - Print clear message naming the Drive URL + explaining sign-in is required.
   - Point user at the "Manual data fallback" README section.
   - Exit 1.
6. Hash check: maintain a `data/raw/e5/.manifest.txt` with sha256 of each file.
   On re-run, skip files whose hash matches; only refetch missing/changed.
```

### 5.2 `scripts/ingest_e5.py`

```text
1. If data/auto_processed/graphs/ exists with ≥ 6,000 JSONs and labels.csv exists, exit 0 with "already ingested" message.
2. Else import AutoPipeline, instantiate with output_dir="data/auto_processed".
3. Iterate over .bin.gz/.avro files in data/raw/e5/, calling pipeline.ingest(file_path).
4. Per-file progress log: "[3/12] processing ta1-fivedirections-3-e5-official-2.bin.gz... 412k events".
5. Final summary: total events, total subjects, total graphs, total attack windows.
6. Exit 0.
```

### 5.3 `scripts/verify_phase4.py`

```text
ASSERTIONS (all must pass; first failure => exit 1 with diff):

A. data/auto_processed/graphs/ contains ≥ 6,000 *.json files
B. data/auto_processed/labels.csv parses; >= 80 rows with label==1; >= 5,800 with label==0
C. Importable: from src.sentinel_z.detection.semantic_risk_engine import run_phase4_pipeline
D. run_phase4_pipeline() runs without exception
E. data/auto_processed/detection/phase4_results.json exists after the run
F. The "roc_auc" field in phase4_results.json is in [0.84, 0.88]

ON SUCCESS: print Phase 4 results table identical to README §4.1, prefixed "✓ verified".
ON FAILURE: print which assertion failed and what the actual value was.
```

### 5.4 `Makefile`

```make
.PHONY: download ingest verify reproduce clean-data

download:
	python scripts/download_e5.py

ingest:
	python scripts/ingest_e5.py

verify:
	python scripts/verify_phase4.py

reproduce: download ingest verify

clean-data:
	rm -rf data/auto_processed data/model_ready
	@echo "data/raw/ NOT removed (manual: rm -rf data/raw)"
```

---

## 6. Verification gate (definition of done)

A reviewer / future-you / fresh checkout must be able to:

1. ✅ `pip install -e ".[ml,viz,dev]"`
2. ✅ `make reproduce`  → exits 0 in finite time
3. ✅ `cat data/auto_processed/detection/phase4_results.json` shows `roc_auc ≈ 0.86`
4. ✅ `pytest tests/` still passes (smoke tests + new `test_scripts_parse`)
5. ✅ `git status` clean (data/ stays gitignored)

---

## 7. Out of scope (YAGNI)

Explicitly **not doing** in this sub-project:

- Cross-dataset support (E3, CADETS, THEIA, TRACE) — sub-project D
- Re-training the Stage 2 encoder — sub-project C
- Migrating graph storage from JSON to LMDB — Stage 1 optimization, not blocking
- Caching layer for repeat ingests — premature optimization
- Docker packaging — sub-project G
- A `download_e3.py` companion — defer
- Improving `auto_pipeline.py` itself (e.g., parallelism) — same

If `auto_pipeline.py` has bugs that prevent reproduction, fix narrowly to unblock; don't refactor.

---

## 8. Risks & mitigations

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| R1 | Drive access denied (user no longer authorized; or `gdown`'s cookie-based auth broken) | Medium | `download_e5.py` prints clear message + manual fallback URL. README documents the manual path explicitly. |
| R2 | Ingest takes 1–2 h on laptop | High | Per-file progress logs in `ingest_e5.py`; document expected runtime in README; consider a `--max-files N` flag for quick smoke runs (deferred to YAGNI for now). |
| R3 | Reproducibility drift — `auto_pipeline.py` may have changed since Jan 2026, producing slightly different graphs / scores | Medium | `verify_phase4.py` allows ±0.02 ROC-AUC tolerance and surfaces the actual value. If the drift is > 0.02, that's a separate bug to investigate (not this spec). |
| R4 | Phase 4 result schema (`phase4_results.json`) doesn't actually contain a `roc_auc` field | Low | First step of execution: peek at `semantic_risk_engine.py` to confirm field name. If different, rename in `verify_phase4.py`. |
| R5 | `gdown` rate-limit or partial download on large folder | Medium | Idempotent re-runs via the manifest file. If 3 retries fail, surface the manual fallback. |
| R6 | License — DARPA TC data may not be freely redistributable | High (compliance) | Never commit; ensure `data/` stays gitignored; mention in README. |

---

## 9. Open questions for user before execution

1. **Drive access confirmation.** Please visit https://drive.google.com/drive/folders/1okt4AYElyBohW4XiOBqmsvjwXsnUjLVf in your browser right now and confirm you see the contents (`Data/`, `Ground_Truth/`, etc.). If you see "Request access" / sign-in wall, this whole sub-project is blocked until access is granted.
2. **Branch.** Continue on `restructure`, or split off a `feat/data-acquisition` sub-branch? *(Recommendation: continue on `restructure` since this is small and bundled with the broader cleanup arc.)*
3. **Spec location going forward.** OK with `.specs/YYYY-MM-DD-*.md` for working artifacts? *(Stays out of the README narrative; doesn't pollute the project root.)*

---

## 10. After approval

Execute order:
1. Add `gdown` to dev deps; bump `pyproject.toml`
2. Write `scripts/download_e5.py` + run it (verify Drive access + bytes on disk)
3. Write `scripts/ingest_e5.py` + run it (verify graphs + labels on disk)
4. Write `scripts/verify_phase4.py` + run it (verify the ROC-AUC reproduces)
5. Write `Makefile`
6. Update README §9 with first-time setup + manual fallback
7. Update `tests/test_smoke.py` with `test_scripts_parse`
8. Commit per logical step (download script + run; ingest script + run; verify script + run; Makefile; README; test)
9. Push to `origin/restructure`

When done, sub-project A's verification gate (§6) is the success criterion. After that, brainstorm sub-project B (Narrative Engine).
