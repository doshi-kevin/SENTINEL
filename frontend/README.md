# Sentinel-Z Frontend

Next.js dashboard for the Sentinel-Z APT detection engine. Provides:

- **Live metrics header** — pulls the model card from the backend at mount
- **Campaign list + narrative detail** — clickable campaigns with per-window
  chapters and auditable signal evidence
- **Stress test status board** — at-a-glance summary of the six validation tests
- **Provenance graph visualization** (Phase 1 — Cytoscape custom layout)

## Quick start (dev)

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000.

The frontend will gracefully fall back to sample data when the backend
(http://localhost:8000) is offline. To run the full stack:

```bash
# From repo root
docker-compose up
```

## Tech stack

- Next.js 16 (App Router) + React 19
- TypeScript (strict mode)
- Tailwind CSS 4 (no shadcn/ui boilerplate — distinctive visual language)
- Geist + Geist Mono fonts

## Why no chat UI / no LLM panel

Sentinel-Z's commitment is to deterministic, auditable explanations. The
narratives shown in the dashboard come from `src/sentinel_z/narrative/story_builder.py`
which uses templates and explicit signal citation — no LLM calls anywhere
in the detection or explanation hot path.

Adding a chat UI would imply LLM dependency and undermine the auditability story.
Don't do it.

## Configuration

| Env var | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API origin |

## Production build

```bash
npm run build
npm start
```

Or via Docker:

```bash
docker build -t sentinel-z-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=https://api.example.com sentinel-z-frontend
```

## Roadmap

- [x] Metrics header + campaign list + stress tests (Phase 0)
- [ ] Provenance graph visualization with custom layout (Phase 1)
- [ ] Live WebSocket updates for streaming inference (Phase 2)
- [ ] Threshold-slider UI for SOC operator (Phase 2)
- [ ] Counterfactual explanation panel (Phase 1 — CRE companion)
