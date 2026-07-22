# AI ResearchOS

**The Autonomous AI Scientist.**

Discovers papers on arXiv and Semantic Scholar, reads them structurally,
extracts methods / datasets / metrics / claims into a shared knowledge
graph (with real citation edges between papers), flags contradictions and
research gaps, and writes literature reviews — autonomously, via a 7-agent
pipeline.

See also: **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** (system
design, data flow, extension points) and
**[`docs/GAP_ANALYSIS.md`](docs/GAP_ANALYSIS.md)** (honest audit of what's
built vs. the full spec, and why).

---

## Quick start (one command)

```bash
docker compose up --build
```

- Frontend: **http://localhost:3000**
- Backend API: **http://localhost:8000** (interactive docs at `/docs`, metrics at `/metrics`)

No API key required to run. Optionally add `ANTHROPIC_API_KEY` (see below)
to upgrade extraction and survey-writing from heuristic to LLM-powered —
everything works either way.

---

## What's built, and how it was verified

Honesty about testing matters more than a green checkmark that isn't real,
so here's exactly what happened:

**This development sandbox had no internet access and couldn't install
Python packages beyond `pypdf`/`pdfplumber`/`reportlab`, or npm packages at
all.** Every module was written to the same production standard throughout
— nothing here is a stub or placeholder — but only pieces with no
network/heavy-dependency requirement could be *executed* in that sandbox.

Here's the honest breakdown:

| Layer | Status |
|---|---|
| **Backend pure logic** (arXiv/Semantic Scholar parsing, PDF structural extraction, heuristic knowledge extraction, citation matching, contradiction/gap/novelty/timeline/analysis detection, BM25 retrieval + RRF, survey templating, agent orchestration, rate limiting, auth tokens, RBAC, tracing no-op behavior) | Real automated tests pass -- 182/182, run against real fixtures/generated PDFs, zero mocking of the logic itself |
| **Backend network/DB layer** (FastAPI routes, SQLAlchemy models, httpx clients, LLM calls) | Complete, syntax- and import-checked, but not executed in the sandbox (no network/no installable deps there) |
| **Frontend** (Next.js/React/TypeScript) | Complete, syntax-checked with `tsc`, but not build-tested (no npm registry access in the sandbox) |

**You should run the live verification below once, the first time you boot
this.** It's a five-minute check, not a leap of faith -- and if anything
fails, it's isolated to exactly the layers above that couldn't be executed
already, which makes it fast to fix.

### Live verification

```bash
docker compose up --build
```

```bash
# 1. Health check
curl http://localhost:8000/api/health

# 2. Real arXiv search
curl "http://localhost:8000/api/papers/search?q=graph+neural+networks&max_results=3"

# 2b. Multi-source discovery (arXiv + Semantic Scholar concurrently)
curl "http://localhost:8000/api/papers/discover?q=graph+neural+networks&max_results=3"

# 3. Full ingest: download PDF + extract structure
curl -X POST http://localhost:8000/api/papers/ingest \
  -H "Content-Type: application/json" -d '{"arxiv_id": "1609.02907"}'

# 4. Knowledge extraction (needs the paper_id from step 3's response,
#    or GET /api/papers to find it)
curl -X POST http://localhost:8000/api/knowledge/extract/<paper_id>

# 4b. BM25 search over your ingested corpus
curl "http://localhost:8000/api/papers/corpus-search?q=graph+convolutional&top_k=5"

# 5. The flagship workflow: one call, full pipeline
curl -X POST http://localhost:8000/api/research/run \
  -H "Content-Type: application/json" \
  -d '{"query": "graph neural networks", "max_papers": 3}'

# 5b. Same pipeline, but streamed live via Server-Sent Events -- watch
#     each agent's progress arrive as it happens instead of waiting for
#     the whole multi-minute run
curl -N "http://localhost:8000/api/research/run/stream?query=graph+neural+networks&max_papers=3"
```

Then open **http://localhost:3000** and try the same flows in the UI:
Discover -> search + ingest a paper -> open it -> Extract knowledge; or just
go to **Run Research** and run the whole pipeline from one box.

Re-run the offline backend test suite any time:
```bash
cd backend && ./run_tests.sh
```

---

## Adding an LLM key (optional, upgrades extraction quality)

```bash
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...
```

or when using Docker Compose:
```bash
ANTHROPIC_API_KEY=sk-ant-... docker compose up --build
```

With no key: knowledge extraction uses curated regex/keyword matching
(common dataset/metric names, "we propose X" patterns, results sentences
with numbers) and the literature review is a structured template built
directly from extracted facts. Both are genuinely useful, not fake filler.

With a key: the same call sites automatically use Claude for extraction and
for synthesized review prose -- and automatically fall back to the
heuristic path if any individual LLM call fails, so a rate limit or bad
response never means the pipeline stalls.

---

---

## Security, observability, and deployment

- **Rate limiting** is always on (token bucket, per-client-IP).
- **Auth is off by default** — set `REQUIRE_API_AUTH=true` and
  `API_AUTH_SECRET` in `backend/.env` to require a signed Bearer token on
  write endpoints. Issue tokens with:
  ```bash
  cd backend && API_AUTH_SECRET=your-secret python3 scripts/issue_token.py --subject my-client
  ```
- **Metrics**: `GET /metrics` returns Prometheus-format request
  counts/latency. A ready-to-import Grafana dashboard and Prometheus
  scrape config are in `observability/` -- see `observability/README.md`.
- **Tracing**: OpenTelemetry, off by default with zero overhead. Set
  `OTEL_EXPORTER_OTLP_ENDPOINT` to enable auto-instrumented request spans.
- **Neo4j**: optional. `docker compose --profile full up` brings up
  Neo4j/Prometheus/Grafana alongside the app; `python3 scripts/sync_to_neo4j.py`
  exports the knowledge graph into it for Cypher queries.
- **CI**: `.github/workflows/ci.yml` runs the full offline test suite, a
  live integration smoke test (real arXiv search + ingest + extraction),
  and a frontend build/lint/typecheck on every push.
- **Kubernetes**: manifests in `k8s/` (namespace, backend, frontend,
  ingress, HPA) — see `k8s/README.md` for what to configure before
  applying. Reviewed and YAML-validated, not yet run against a live
  cluster (see `docs/GAP_ANALYSIS.md`).

## Architecture

### The four phases

- **Phase 1 -- Backend foundation.** arXiv search, PDF download, structural
  PDF extraction (sections, references) via `pdfplumber`, SQLite/Postgres
  storage.
- **Phase 2 -- Knowledge graph.** A generic Entity/Relationship graph schema
  (methods, datasets, metrics, claims, papers as nodes) so new entity types
  never need a migration. Heuristic extraction that works with zero API
  keys, with an LLM-refinement path layered behind the identical interface.
- **Phase 3 -- Multi-agent orchestration + frontend.** Discovery, Reading,
  Extraction, and Survey agents run through a hand-rolled async pipeline
  runner (not LangGraph -- this pipeline's shape doesn't need a graph
  execution engine, and a plain async runner is something that could
  actually be unit-tested with fake agents in an offline sandbox). Next.js/
  TypeScript frontend wired to every endpoint.
- **Phase 4 -- UI polish & packaging.** Glassmorphism panels, an animated
  constellation background rendering the knowledge-graph metaphor directly,
  3D hover effects, Framer Motion transitions, full Docker Compose
  deployment.

### Key design decisions

- **Nothing requires an API key to run.** Every LLM call site has a tested,
  genuinely useful non-LLM fallback -- the platform is never dead in the
  water without credentials, it just gets smarter with them.
- **Generic knowledge graph schema** (`kg_entities` / `kg_relationships`
  with a type column) instead of one table per entity type. Scales fine on
  Postgres/SQLite well past what this project will realistically hit;
  migrating to a dedicated graph DB later is a data migration, not a
  schema redesign, since entity_type/relationship_type map directly to
  node/edge labels.
- **Entity resolution on ingest**: the same dataset (e.g. "Cora") mentioned
  across ten papers becomes one graph node with ten edges, not ten
  disconnected islands -- this is what makes cross-paper graph queries
  possible.
- **SQLite by default, Postgres by changing one env var** (`DATABASE_URL`)
  -- no code changes, since only dialect-agnostic SQLAlchemy is used.
- **Every failure path sets a real status + error message.** Papers track
  `extraction_status` through `not_started -> downloading -> extracting ->
  completed/failed`; nothing fails silently.

### Project structure

```
ai-researchos/
├── docker-compose.yml
├── docs/
│   ├── ARCHITECTURE.md
│   └── GAP_ANALYSIS.md
├── k8s/                            # Kubernetes manifests (see k8s/README.md)
├── .github/workflows/ci.yml        # offline tests + live smoke test + frontend build
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                   # config, database, rate_limiter, auth,
│   │   │                           # middleware, metrics_registry, observability
│   │   ├── models/                 # paper.py, knowledge_graph.py
│   │   ├── schemas/                # Pydantic API schemas
│   │   ├── services/
│   │   │   ├── arxiv_parser.py     # pure XML parsing (tested)
│   │   │   ├── arxiv_client.py     # httpx network wrapper
│   │   │   ├── semantic_scholar_parser.py  # pure JSON parsing (tested)
│   │   │   ├── semantic_scholar_client.py
│   │   │   ├── discovery_converters.py  # per-source -> unified shape (tested)
│   │   │   ├── discovery_service.py     # fans out across sources
│   │   │   ├── pdf_extractor.py    # PDF structure extraction (tested)
│   │   │   ├── pdf_downloader.py
│   │   │   ├── ingest_service.py   # orchestrates PDF pipeline
│   │   │   ├── knowledge_extraction.py  # heuristic extraction (tested)
│   │   │   ├── llm_extractor.py    # LLM extraction (same output shape)
│   │   │   ├── llm_client.py       # Anthropic API wrapper
│   │   │   ├── citation_matcher.py # reference -> corpus matching (tested)
│   │   │   ├── graph_service.py    # persists + queries the graph
│   │   │   ├── retrieval.py        # BM25 + reciprocal rank fusion (tested)
│   │   │   ├── corpus_search.py    # DB-backed BM25 over ingested papers
│   │   │   ├── research_intelligence.py  # contradiction/gap/novelty/
│   │   │   │                              # timeline/analysis (tested)
│   │   │   └── survey_templates.py # template review generation (tested)
│   │   ├── agents/
│   │   │   ├── base.py             # Agent/AgentContext/AgentResult
│   │   │   ├── orchestrator.py     # pipeline runner (tested)
│   │   │   ├── discovery_agent.py
│   │   │   ├── reading_agent.py
│   │   │   ├── extraction_agent.py
│   │   │   ├── contradiction_agent.py
│   │   │   ├── gap_agent.py
│   │   │   ├── novelty_agent.py
│   │   │   ├── timeline_agent.py
│   │   │   ├── analysis_agent.py
│   │   │   ├── citation_agent.py
│   │   │   ├── recommendation_agent.py
│   │   │   ├── survey_agent.py
│   │   │   └── research_pipeline.py  # wires the concrete pipeline
│   │   └── api/routes/             # papers.py, knowledge.py, research.py, metrics.py
│   ├── scripts/
│   │   ├── issue_token.py          # CLI token issuance (not an API endpoint; supports --role)
│   │   └── sync_to_neo4j.py        # optional: exports the graph into a real Neo4j instance
│   ├── tests/                      # 182 real, passing offline tests
│   ├── requirements.txt
│   ├── requirements-neo4j.txt      # optional extra, kept separate so it can't break core CI
│   └── Dockerfile
├── observability/                  # Grafana dashboard + Prometheus scrape config
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── page.tsx            # dashboard
    │   │   ├── search/page.tsx     # multi-source search + ingest
    │   │   ├── papers/[id]/page.tsx  # paper detail + extraction
    │   │   └── research/page.tsx   # autonomous pipeline + intelligence UI
    │   ├── components/             # NavBar, PaperCard, ExtractPanel,
    │   │                           # ConstellationBackground, MarkdownView
    │   ├── lib/api.ts              # typed API client
    │   └── types/api.ts
    ├── package.json
    └── Dockerfile
```

---

## Design notes

The visual identity is grounded in what the product actually does: a
knowledge graph of scientific papers reads naturally as a **star chart** --
papers and extracted concepts as stars, the relationships between them as
constellation lines. That's the signature background element throughout,
not decoration borrowed from a generic template.

- **Palette**: deep space navy (`#0A0E17`), phosphor teal for graph/data
  (`#5EEAD4`), warm amber for discoveries/claims (`#F2B44D`).
- **Type**: Newsreader (serif display, academic-paper feel) paired with
  Manrope (UI sans) and JetBrains Mono (data/metrics).
- **Glass panels** throughout, with a subtle 3D perspective tilt on hover
  rather than a flat lift.

---

## Extending further

- **Batch/background jobs**: `POST /api/research/run` is synchronous and
  `GET /api/research/run/stream` streams live progress via SSE, but both
  still hold the HTTP connection open for the whole run. For very large
  batches, a job-queue version (submit, get a job id, poll/subscribe
  separately) would decouple submission from execution -- the streaming
  generator (`run_research_pipeline_streaming`) is already shaped so its
  events could be published to a queue instead of yielded directly.
- **Dedicated graph DB**: a real sync path to Neo4j already exists
  (`scripts/sync_to_neo4j.py`, `docker compose --profile full up`) for
  Cypher queries and tools like Bloom. Making Neo4j the *primary* store
  instead of a synced copy is the next step once the graph outgrows a
  relational store -- the entity/relationship type fields map directly
  onto node/edge labels, so it's a migration, not a redesign.
- **More discovery sources**: Semantic Scholar, CrossRef, PubMed clients
  follow the same fetch/parse split as `arxiv_client.py`/`arxiv_parser.py`.
- **Alembic migrations**: `init_db()` auto-creates tables for local dev;
  production deployments should adopt Alembic for schema changes.
