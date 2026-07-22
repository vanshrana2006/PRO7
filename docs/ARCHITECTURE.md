# Architecture

## System overview

```
                    ┌─────────────────────────────────────────┐
                    │              Next.js Frontend             │
                    │  (dashboard / discover / paper / research)│
                    └───────────────────┬───────────────────────┘
                                         │ REST (JSON)
                    ┌───────────────────▼───────────────────────┐
                    │                FastAPI Backend              │
                    │  ┌─────────────────────────────────────┐  │
                    │  │  Rate limit -> CORS -> Observability   │  │
                    │  │           (middleware chain)           │  │
                    │  └─────────────────────────────────────┘  │
                    │                                             │
                    │   /api/papers    /api/knowledge  /api/research │
                    │   /metrics       /api/health                  │
                    └──────┬──────────────┬─────────────┬─────────┘
                           │              │             │
              ┌────────────▼───┐  ┌───────▼──────┐  ┌───▼─────────────┐
              │  Discovery       │  │ Knowledge     │  │  Agent pipeline  │
              │  (arXiv,         │  │ extraction    │  │  (Discovery ->   │
              │  Semantic        │  │ (heuristic or │  │   Reading ->     │
              │  Scholar)        │  │  LLM)         │  │   Extraction ->  │
              │                  │  │               │  │   Contradiction/ │
              │                  │  │               │  │   Gap/Novelty -> │
              │                  │  │               │  │   Survey)        │
              └──────────────────┘  └───────┬───────┘  └──────────────────┘
                                             │
                                   ┌─────────▼─────────┐
                                   │   SQLite/Postgres    │
                                   │  Papers, Sections,    │
                                   │  References, and a    │
                                   │  generic Entity/       │
                                   │  Relationship graph    │
                                   └────────────────────────┘
```

## Request flow: the autonomous research pipeline

`POST /api/research/run {"query": "..."}` runs, in order:

1. **DiscoveryAgent** -- searches arXiv for the query, returns candidate papers.
2. **ReadingAgent** -- downloads each PDF, runs structural extraction
   (sections, references) via `pdf_extractor.py`.
3. **ExtractionAgent** -- for each ingested paper: extracts methods/
   datasets/metrics/claims (LLM if `ANTHROPIC_API_KEY` is set, heuristic
   otherwise), persists them as graph entities/relationships, and builds
   `cites` edges against the rest of the corpus via `citation_matcher.py`.
4. **ContradictionAgent / GapAgent / NoveltyAgent** -- run heuristic
   analysis over the extracted knowledge (see `research_intelligence.py`).
5. **SurveyAgent** -- synthesizes a literature review (LLM prose if a key
   is set, a fact-grounded template otherwise).

Each agent implements the same `Agent.run(context) -> AgentResult`
interface (`app/agents/base.py`) and never raises past its own boundary
for expected failures -- a failed paper download doesn't stop the others,
and the orchestrator (`app/agents/orchestrator.py`) records every agent's
outcome for the response's `agent_results`/`log` fields.

## The optional-upgrade pattern

Every AI-dependent capability follows the same shape:

```python
if llm_is_available():
    try:
        result = await llm_path(...)
    except LLMError:
        result = None  # fall through
if result is None:
    result = heuristic_path(...)
```

This means: **the platform is fully functional with zero API keys**, and
adding `ANTHROPIC_API_KEY` upgrades extraction/synthesis quality with no
code changes and no risk of a flaky LLM call stalling the pipeline. See
`app/services/graph_service.py` and `app/agents/survey_agent.py` for the
concrete implementations.

## The knowledge graph schema

`kg_entities` / `kg_relationships` (see `app/models/knowledge_graph.py`)
use a generic `entity_type`/`relationship_type` column rather than one
table per entity kind. This is deliberate:

- New entity types (Method, Dataset, Claim, Paper, ...) never require a
  migration -- they're just a new string value.
- It maps directly onto a property graph: `entity_type` -> node label,
  `relationship_type` -> edge label. Migrating to Neo4j later is a data
  migration, not a schema redesign.
- Entity resolution (`_get_or_create_entity` in `graph_service.py`) means
  the same dataset mentioned across ten papers becomes one node with ten
  edges, not ten disconnected islands -- this is what makes cross-paper
  queries ("which papers use Cora?") meaningful.

## Fetch/parse split

Every external API integration (arXiv, Semantic Scholar) is split into
two files:

- `*_parser.py` -- pure functions, stdlib only, zero network/DB
  dependency. Fully unit-testable with fixture data.
- `*_client.py` -- thin httpx wrapper that fetches raw data and hands it to
  the parser.

This isn't just a testing convenience -- it also means a source's response
format changing is isolated to one small, pure function, and adding a new
source (CrossRef, PubMed, OpenAlex -- see `docs/GAP_ANALYSIS.md`) means
writing one more pair of files following the exact same shape.

## Retrieval

- **Sparse (BM25)**: `app/services/retrieval.py` implements standard BM25
  (k1=1.5, b=0.75) over ingested papers' title/abstract/full text, exposed
  via `GET /api/papers/corpus-search`. Rebuilds the index per request,
  which is fine at this platform's realistic scale (hundreds to low
  thousands of papers); a growing corpus is the seam to add caching or an
  incremental index behind, without changing the `search()` signature.
- **Hybrid-ready**: `reciprocal_rank_fusion()` combines any number of
  ranked result lists by rank position (not raw score, which isn't
  comparable across methods with different scales) — it's already there
  and tested, waiting for a second (dense/embedding) ranked list to fuse
  with BM25's. Adding dense retrieval means plugging in an embeddings
  provider behind the same optional-upgrade pattern as the LLM extraction
  path, not rewriting the fusion logic.
- **Dense retrieval is not implemented** — see `docs/GAP_ANALYSIS.md`.

## Security posture

- **Rate limiting** is always on (`app/core/rate_limiter.py`, a token
  bucket, wired via `app/core/middleware.py`) -- per-client-IP, generous
  defaults, tunable via `RATE_LIMIT_CAPACITY`/`RATE_LIMIT_REFILL_PER_SECOND`.
- **Auth is off by default.** Set `REQUIRE_API_AUTH=true` and
  `API_AUTH_SECRET` to require a Bearer token (HMAC-signed, stdlib-only --
  see `app/core/auth.py`) on paper-ingest/knowledge-extract/research-run
  calls. Tokens are issued via `scripts/issue_token.py` (a CLI script, not
  an API endpoint -- an unauthenticated "give me a token" route would be a
  real vulnerability).
- **RBAC** (`app/core/rbac.py`): roles (`viewer`/`researcher`/`admin`) are
  named, reusable sets of scopes layered on the token system above --
  `scripts/issue_token.py --role researcher` expands to the concrete scope
  list instead of an operator needing to type every scope by hand. Each
  mutating endpoint requires a specific permission
  (`Depends(require_permission("papers:ingest"))`, etc.) rather than "any
  valid token" -- real 401/403 semantics, not just yes/no auth.
- **CSRF**: not implemented, deliberately -- this is a stateless JSON API
  authenticated via `Authorization: Bearer` headers, not cookies. Classic
  CSRF exploits a browser automatically attaching session cookies to
  cross-site requests; a bearer token in a custom header isn't
  auto-attached by the browser, so the attack this protection exists for
  doesn't apply to this auth model. Adding CSRF tokens here would be
  unnecessary complexity for a threat that isn't present -- if a
  cookie-based session auth is added later, CSRF protection becomes
  necessary at that point, not before.
- **XSS**: verified, not just assumed -- grepped the entire frontend for
  `dangerouslySetInnerHTML`/`eval`/`new Function`; none exist. React's
  default JSX escaping is never bypassed.
- **SQL injection**: verified -- grepped the entire backend for raw SQL
  string interpolation (`f"SELECT`, `.format()` into queries, etc.); none
  exists. Every query goes through SQLAlchemy's parameterized ORM/Core
  API.
- **CORS** is restricted to `CORS_ORIGINS` (defaults to localhost:3000).
- **No secrets are logged.** `ANTHROPIC_API_KEY`/`API_AUTH_SECRET` are
  read from environment only, never included in error messages.
- **OAuth (Google/GitHub login etc.) is not implemented.** It needs real
  provider credentials and a callback round-trip that can't be verified in
  this environment -- the HMAC token system above is the working auth
  layer until that's added. See `docs/GAP_ANALYSIS.md`.

## Observability

- `/metrics` -- Prometheus text-format exposition (`app/core/metrics_registry.py`,
  wired via `app/core/observability.py`). Tracks request counts by
  method/path/status and latency sum/count/max per route. A working
  Grafana dashboard (`observability/grafana/dashboard.json`) and
  Prometheus scrape config (`observability/prometheus.yml`) are included
  -- see `observability/README.md` to wire them up.
- **Distributed tracing** (`app/core/tracing.py`): OpenTelemetry, off by
  default (zero overhead) until `OTEL_EXPORTER_OTLP_ENDPOINT` is set, at
  which point every HTTP request is auto-instrumented and explicit spans
  around PDF download/extraction become active. The no-op behavior when
  disabled is real and tested (`backend/tests/test_tracing.py`); the
  actual OTLP export path needs a running collector to verify, same
  honesty pattern as the rest of this list.
- Structured application logging uses Python's standard `logging` module
  throughout (`ingest_service.py`, etc.) -- configure a handler/formatter
  appropriate to your log aggregator (JSON for most cloud logging systems)
  at the deployment layer.

## Neo4j (optional graph-native view)

The relational `kg_entities`/`kg_relationships` schema is the tested,
working graph store this platform runs on. `backend/scripts/sync_to_neo4j.py`
(needs `pip install -r requirements-neo4j.txt` -- kept out of the core
`requirements.txt` so an optional extra can never break the core
install/CI) exports it into a real Neo4j instance (`docker compose
--profile full up` brings one up) for Cypher queries and tools like Neo4j
Bloom -- idempotent (safe to re-run/cron), using standard `MERGE` Cypher.
Written to production standard; verify against a live instance per the
script's docstring before relying on it, same as every other piece in
this list that needs infrastructure this environment doesn't have.

## What's deliberately not built, and the real next step for each

See `docs/GAP_ANALYSIS.md` for the full, honest list (Neo4j/Qdrant
integrations, OAuth, vector/GraphRAG hybrid search, 3D graph
visualization, additional discovery sources). Each has a concrete,
architecturally-prepared next step rather than a stub pretending to be
done.
