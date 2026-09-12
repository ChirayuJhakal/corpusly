# Corpusly
 
**Multi-tenant document intelligence for teams.** Upload a corpus, ask questions against it, pay for what you use.
 
---
 
## What it does
 
Corpusly gives a team a private workspace, ingests their documents asynchronously, and lets them query that corpus in natural language. Every query draws credits from a workspace balance held in an append-only ledger, so usage is metered, auditable and enforceable.
 
Three things define the system:
 
**Workspaces are hard boundaries.** Every row in every table is scoped to a workspace, and scoping is enforced at the repository layer rather than the route handler. A document belonging to another tenant returns `404`, not `403` — the difference matters, because a `403` confirms the resource exists.
 
**Ingestion is asynchronous by necessity.** Parsing and chunking a large document cannot happen inside a request. Uploads return `202` immediately and a worker takes over, driving the document through `pending → processing → ready | failed`. The worker is safe to kill mid-job: idempotency keys and a resumable checkpoint mean a retry produces zero duplicate chunks.
 
**Balance is derived, never stored.** The credit ledger is append-only. A workspace balance is the sum of its entries, and the invariant that it can never go negative holds under concurrent load — enforced with row-level locking rather than an optimistic read-then-write that loses under contention.
 
---
 
## Data model
 
| Entity | Role |
|---|---|
| `workspace` | The tenant boundary. Everything is scoped to it. |
| `member` | A user within a workspace, with a role: `owner`, `editor`, `viewer`. |
| `document` | An uploaded file and its processing state. |
| `chunk` | A retrievable segment derived from a document. |
| `query` | A question asked against a workspace, with its answer, latency and cost. |
| `credit_ledger` | Append-only debits and credits. The source of truth for balance. |
 
---
 
## Architecture
 
```
Client
  ↓
FastAPI  ──  auth, tenant scoping, rate limiting
  ↓
PostgreSQL  +  Redis (cache-aside, rate limits)
  ↓
Queue  →  ingestion worker  →  parse → chunk → embed
  ↓
Retrieval (hybrid search + rerank)  →  LLM  →  evaluated answer
```
 
Every request carries a request ID that propagates through the API, the database layer, the cache and into the worker, so a single upload is traceable end to end.
 
---
 
## Stack
 
Python · FastAPI · PostgreSQL · SQLAlchemy · Alembic · Redis · Celery · pytest · Docker Compose · GitHub Actions · OpenTelemetry · k6
 
---
 
## Status
 
Built in the open, one capability at a time.
 
**Foundation**
- [ ] REST API with validation, dependency injection and a consistent error envelope
- [ ] PostgreSQL schema with migrations
- [ ] Query performance: N+1 eliminated, composite indexes with recorded query plans
- [ ] Credit ledger with concurrency safety under load
- [ ] Auth, RBAC and tenant isolation with a test suite proving it
**Operations**
- [ ] Redis caching with invalidation across all write paths
- [ ] Async ingestion with retries, backoff and idempotency
- [ ] Integration test suite against a real database
- [ ] Containerised, CI on every push
- [ ] Structured logging, distributed tracing, health checks
- [ ] Deployed with a public URL
- [ ] Load tested, bottleneck identified and fixed, p50/p95/p99 documented
**Intelligence**
- [ ] Embeddings and vector search over chunks
- [ ] Hybrid search with reranking
- [ ] Eval harness: golden dataset, retrieval precision/recall, answer faithfulness
- [ ] Token cost accounting through the existing ledger
- [ ] Guardrails and prompt versioning
---
 
## Engineering notes
 
Failures in this system are documented rather than hidden. Each of the following has a write-up covering what broke, how it was diagnosed and the measured before/after:
 
- Blocking the event loop inside an async endpoint
- N+1 on the document list endpoint
- Lost updates driving a credit balance negative
- Stale reads after a write with no cache invalidation
- Duplicate chunks after a worker crash mid-ingestion
- The first real bottleneck under sustained load
---
 
## Running locally
 
```bash
docker compose up
```
 
Brings up the API, worker, PostgreSQL and Redis. Migrations run on start.