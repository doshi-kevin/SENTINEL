# Paper Draft Outline — RAID 2027 Submission

**Target venue:** RAID 2027 (International Symposium on Research in Attacks, Intrusions and Defenses)
**Backup venue:** ACSAC 2026 (Annual Computer Security Applications Conference)
**Status:** Outline. To be written after Phase 0 results land.
**Timeline:** Submit by RAID 2027 deadline (~Feb/Mar 2027)

---

## Working Title

**Sentinel-Z: Explainable Provenance-Based APT Detection with Honest Validation**

Alternative titles to consider:
- *Sentinel-Z: A Reproducibility-First Detector for Cross-Engagement APT Analysis*
- *Detecting What DARPA Missed: Signal-Driven Narratives for Provenance-Based Intrusion Detection*
- *Honest Methodology for Provenance APT Detection: A Cross-Engagement Study*

---

## Abstract (draft, ~250 words)

```
Provenance-based Advanced Persistent Threat (APT) detection systems
routinely report ROC-AUC above 0.99 on DARPA Transparent Computing
benchmarks (MAGIC, KAIROS, FLASH, APT-MCL). At the same time, recent
reproducibility studies (PIDSMaker, USENIX Sec'25; SRI 2025) have
flagged widespread methodological issues including label leakage,
inflated metrics from non-standard splits, and absent cross-dataset
validation. The field's headline numbers have grown faster than its
methodology has matured.

We present Sentinel-Z, a provenance-based APT detector built around
three commitments: (1) every reported metric carries a 95% confidence
interval from paired-bootstrap iterations; (2) the system passes a
shuffled-label leakage control that none of the prior arts published;
and (3) detections come with deterministic, template-driven narratives
that cite their underlying signals — no language model is invoked in
the detection or explanation path.

We evaluate Sentinel-Z on DARPA TC Engagement 5 (FiveDirections),
which the published academic literature consistently avoids despite
being the most challenging scenario in the corpus. Within-engagement
performance (ROC-AUC 0.9996 ± 0.0002; PR-AUC 0.832 ± 0.059; FPR 0.35%)
is comparable to published systems. Cross-engagement performance
against E3-CADETS [drops by X.YY ROC-AUC and Z.WW PR-AUC]. A direct
paired-bootstrap comparison against MAGIC on identical splits yields
[insert verdict]. A separate forensic investigation surfaces 5 host-2
windows that match labeled-attack signatures but appear in no public
ground truth — consistent with the field consensus that DARPA's
labeling is partial.

We release all code, validation scripts, and a hosted demo. We argue
the field's next ROC-AUC point matters less than its first honest
cross-engagement number.
```

---

## Outline

### 1. Introduction (1.5 pages)

- The provenance-APT detection problem.
- The reproducibility crisis: published 0.99 numbers, no cross-dataset, no
  leakage controls, vendor numbers absent entirely.
- Sentinel-Z contributions:
  1. Cross-engagement evaluation protocol (E5 ↔ E3) with paired bootstrap.
  2. Deterministic narrative generation with explicit signal citation.
  3. Six-test stress suite for label leakage detection.
  4. Forensic methodology that surfaced 5 unlabeled-but-attack-signatured
     host-2 windows in E5.
  5. Open-source reproducible release.
- Roadmap of the paper.

### 2. Background and Related Work (2 pages)

- DARPA Transparent Computing campaign overview (E3, E5, dataset structure).
- Provenance graph detection: ThreaTrace, FLASH, MAGIC, KAIROS, RAPID,
  APT-MCL, TFLAG, Slot.
- Explainable AI in intrusion detection: SHAP/LIME limitations on tree models,
  TreeSHAP bias.
- Reproducibility literature: PIDSMaker, SRI provenance-IDS reproducibility study,
  Schloegel et al. on label leakage.
- MITRE ATT&CK as evaluation framework.

### 3. Methodology (3 pages)

#### 3.1 Pipeline overview
- CDM (Common Data Model) ingestion supporting both v18 (E3) and v20 (E5).
- 1-second graph windowing.
- Feature extraction (7 per-window + 13 temporal-context features).
- RandomForest detector with Youden-threshold calibration.
- Deterministic narrative engine.

#### 3.2 The 13 temporal-context features
- Rolling 30-second statistics (mean, max, std, delta, burst ratio) over
  unknown_ratio, num_nodes, density, network_ratio, fused_score, plus an
  anomaly_count_30s indicator.
- Justification: APT activity creates bursts across multiple windows; per-window
  features systematically miss this.

#### 3.3 Deterministic narrative generation
- Stage classification from event-type distribution (no LLM).
- MITRE ATT&CK tactic mapping (rule-based).
- Signal citation: every claim in the narrative references the exact feature
  value that produced it.
- Trade-off vs LLM: lower fluency, perfect auditability, zero hallucination.

#### 3.4 Evaluation protocol
- Stratified 70/15/15 split (within-engagement).
- 30-iteration paired bootstrap for confidence intervals.
- Youden's J threshold selection on validation set.
- Cross-engagement: train one engagement, test on disjoint engagement.
- Mondrian-aware stratification under class imbalance.

### 4. Six-Test Stress Suite (1.5 pages)

This is one of the paper's main methodological contributions. We argue every
provenance-APT system should report results on this suite.

| Test | Question answered |
|---|---|
| 1. Shuffled-label control | Is there label leakage? |
| 2. Rolling-context corruption | Are temporal features leaking from attack-adjacent context? |
| 3. Attack-cluster holdout | Can the model detect from out-of-cluster training? |
| 4. Class-imbalance sweep | How does performance scale across 10:1 → 1000:1 ratios? |
| 5. Feature-noise injection | What's the production-noise tolerance? |
| 6. Window-size sensitivity | Is the rolling-window choice overfit? |

For each, present the protocol, the Sentinel-Z result, and a discussion of
what a failing result would have implied.

### 5. Cross-Engagement Evaluation (2 pages) — THE HEADLINE

The single most important evaluation in the paper.

- Within-engagement (E5): ROC-AUC 0.9996 ± 0.0002, PR-AUC 0.832 ± 0.059.
- Within-engagement (E3-CADETS): [results from Phase 0 Week 1].
- Cross-engagement (E5 → E3-CADETS): [results].
- Reverse cross-engagement (E3-CADETS → E5): [results].

Discussion:
- Which features transferred? (Use permutation-importance comparison.)
- Which features are dataset-specific?
- The "unknown_subject_ratio" feature's behavior under both protocols.

### 6. Comparison Against MAGIC (1.5 pages)

- MAGIC as a strong, current SOTA baseline.
- Paired-bootstrap with IDENTICAL train/test seeds.
- Side-by-side ROC-AUC, PR-AUC, F1, Recall, Precision, FPR with deltas + 95% CIs.

Expected framing (depends on Phase 0 results):
- Either: "Sentinel-Z is statistically equivalent to MAGIC on detection, but
  produces actionable narratives that MAGIC does not."
- Or: "MAGIC narrowly outperforms Sentinel-Z on detection metrics; trade-offs
  in explainability and calibration favor Sentinel-Z for production use."

### 7. Forensic Findings (1.5 pages)

The 5 host-2 windows: persistent UUID, behavioral signatures matching labeled
attacks, no entry in published ground truth.

- Subsection: methodology for finding hidden attacks.
- Subsection: implications for DARPA TC benchmarks (partial ground truth is the norm).
- Subsection: practical implications — Sentinel-Z's narratives helped surface this.

### 8. Limitations and Threats to Validity (0.75 pages)

Honest section. Each limitation gets named explicitly.

- Single-engagement training origin (only E5/E3 evaluated, not THEIA/CADETS/OpTC).
- 86 labeled attack windows in E5 (small statistical sample).
- Feature pipeline noise sensitivity (PR-AUC drops 0.86 → 0.41 at +10% noise).
- No adversarial robustness evaluation (planned Phase 3 work).
- No streaming-latency evaluation (planned Phase 2 work).

### 9. Discussion and Open Problems (0.75 pages)

- Why the field needs to standardize cross-engagement evaluation.
- Why ROC-AUC alone is insufficient under extreme class imbalance.
- The unrealized potential of provenance graph self-supervision.
- The case for deterministic narratives over LLM-generated explanations.

### 10. Conclusion (0.5 pages)

The next ROC-AUC point matters less than the first honest cross-engagement number.

### Acknowledgments

DARPA TC team, MAGIC authors, the reproducibility-study authors who motivated
this work.

### References (estimated 40-60 citations)

---

## Submission Checklist (pre-submit)

- [ ] All metrics in the paper have 95% CIs from at least 30 bootstrap iterations
- [ ] Cross-engagement evaluation is REAL (not handwaved)
- [ ] MAGIC comparison uses IDENTICAL seeds (paired bootstrap)
- [ ] Six stress tests reported with verdict per test
- [ ] No claim of "state of the art" — claim "competitive" or "comparable" only
- [ ] Public GitHub repo with version-tagged release matching paper
- [ ] Hosted demo URL
- [ ] Reproducibility appendix with exact command sequences
- [ ] All authors have signed off
- [ ] Anonymized for double-blind review (if required)
- [ ] LaTeX overleaf project is public after submission

## Risk Register

| Risk | Mitigation |
|---|---|
| Cross-engagement results collapse to near-random | Paper still publishable — frame as "feature-portability ablation"; reframe as a negative result with diagnostic value |
| MAGIC actually beats Sentinel-Z by > 0.05 ROC-AUC | Lead with explainability + calibration + reproducibility; do not claim detection superiority |
| Reviewer demands a third engagement | Have E5-THEIA ingestion ready in code; can re-run within revision deadline |
| Reviewer accuses us of cherry-picking E5-FiveDirections | Cite: "We chose the hardest scenario; existing work avoided it" |

---

## Companion Submissions

After RAID-27, two follow-on papers are queued:

1. **USENIX Security 2027 / NDSS 2028** — *Contrastive Behavioral Embeddings
   with Probabilistic Kill-Chain Hypotheses* (the algorithmic-novelty paper;
   Phase 1 work).

2. **IEEE S&P 2028 / CCS 2027** — *Adversarial Robustness in Provenance-Based
   APT Detection* (the robustness-frontier paper; Phase 3 work).

This is a deliberate three-paper sequence. Each paper builds on the previous.
The RAID-27 paper establishes the framework; the USENIX/S&P papers add depth.
