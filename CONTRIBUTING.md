# Contributing to Sentinel-Z

Thank you for considering a contribution. Sentinel-Z is an open research project on explainable APT detection. Contributions of bug fixes, evaluations on new datasets, new detection algorithms, and documentation improvements are all welcome.

## Ways to Contribute

- **Run our pipeline on a new dataset** (DARPA TC E3, CADETS, THEIA, OpTC, or non-DARPA data) and submit a report.
- **Reproduce our results** and report any deviations.
- **Add a new feature** (detection algorithm, narrative template, integration).
- **Improve documentation** — clarity, examples, typos, missing details.
- **Report a bug** with a reproducible test case.
- **Propose an evaluation methodology improvement** — e.g., a new stress test, a new baseline.

## Ground Rules

1. **Honest reporting.** Every metric must come with a 95% CI (we use 30-iteration stratified bootstrap by default). No cherry-picked seeds. If a change doesn't improve metrics, report that honestly in the PR.

2. **Reproducibility.** All experiments must be reproducible from `requirements.txt` + `scripts/`. If you add a script that requires special data, document where to obtain it.

3. **No LLM dependency in core detection or narrative paths.** Sentinel-Z's commitment is to deterministic, auditable narrative generation. LLMs may be used for *meta-tooling* (summarizing reports for humans) but not in the detection or explanation hot path.

4. **Tests.** Any new module under `src/sentinel_z/` requires unit tests with >= 80% coverage. Any new detector or narrative path requires an integration test in `tests/integration/`.

## Development Workflow

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/<your-username>/sentinel-z.git
cd sentinel-z
python -m venv .venv
source .venv/bin/activate           # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pre-commit install

# Make your changes
# Run tests:
pytest tests/

# Run linters:
ruff check src/ scripts/
black --check src/ scripts/

# Run the full validation suite if you changed detection logic:
python scripts/rigorous_validation.py
```

## Pull Request Process

1. Open an issue first for any non-trivial change. Discuss the approach before coding.
2. Branch from `main` with a descriptive name (`feature/cbe-embeddings`, `fix/cdm-v18-parser`).
3. Write a clear PR description: what changed, why, how to test.
4. Ensure CI passes (lint, tests, coverage).
5. Update the relevant documentation (`MODEL_CARD.md` if metrics change; `README.md` if APIs change).
6. A maintainer will review within 7 days.

## Code Style

- **Python:** PEP 8 enforced by `ruff` and `black` (line length 100). Type hints required for public functions.
- **TypeScript (frontend):** ESLint + Prettier (defaults). React functional components only.
- **Rust (production engine):** `rustfmt` + `clippy` (no warnings).
- **Commit messages:** Conventional Commits format. `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `perf:`, `chore:`.

## Research Contributions

If you have a research contribution (a new detector, a new evaluation) and would like to co-author a publication, mention this in the PR. We welcome collaborations and will give appropriate credit.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be respectful, constructive, and patient.

## Questions

Open a GitHub Discussion or email kevin.doshi2@spit.ac.in.
