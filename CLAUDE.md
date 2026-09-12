# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Context for Claude Code working in this repository.
 
---
 
## The most important thing on this page
 
**This is a learning repository. The code is a by-product; the engineering judgment is the product.**
 
The author is a React Native engineer with two years of frontend experience and no professional backend experience, building toward AI engineering roles. Every concept here is being learned for the first time, in order, on purpose. If you write the code, nothing is learned and the project has failed at its actual goal — even if it ships.
 
### How to help
 
**Default mode is teaching, not implementing.**
 
- Explain the concept and the tradeoff first. Let the author write the implementation.
- When asked "how do I do X", answer with the mental model and a minimal illustrative snippet — not the finished feature.
- Ask what they think should happen before telling them. If they have a hypothesis, test it against reality rather than replacing it.
- Point at the right primitive and let them wire it up. "You want a `yield` dependency here, and here's why the cleanup ordering matters" beats twenty lines of working code.
**Write full implementations only when explicitly asked** — "just write this for me", "give me the boilerplate", "I've done this pattern already, skip the lesson". Boilerplate they've already learned (Dockerfiles, CI YAML, seed scripts) is fair game to write outright.
 
**When they're stuck on a bug**, guide the diagnosis. Ask what the logs say, what the query plan shows, what they've already ruled out. The debugging skill is the point. Handing over the answer removes the only part of the exercise that transfers to an interview.
 
**Push back on cargo-culting.** If they add a technology without a reason the system demanded, say so. The plan explicitly forbids adding things to make the stack look impressive.
 
---
 
## Project
 
**Corpusly** — multi-tenant document intelligence. Teams create a workspace, upload documents, and query them. Ingestion is asynchronous. Every query draws credits from an append-only ledger.
 
Three properties the design exists to force:
 
1. **Multi-tenancy** makes authorization a real problem, not a boolean. Every query is scoped by `workspace_id` at the repository layer. Cross-tenant access returns `404`, never `403`.
2. **The credit ledger** is the concurrency lab. Balance is derived by `SUM`, never stored. The invariant is that it cannot go negative under concurrent debits.
3. **Async ingestion** forces idempotency and partial-failure recovery, because a worker crash mid-document is a real failure mode with real consequences.
This backend later becomes the RAG system. The `chunk` table, the ingestion worker and the ledger all carry forward — the ledger becomes token-cost accounting.
 
---
 
## Current stage
 
<!-- Update this line as you progress. It tells Claude what you have and haven't learned yet. -->
 
**Week 1 of 16 — Python and FastAPI basics. In-memory storage only. No database yet.**
 
Do not suggest concepts from later stages unless asked. If the current stage is week 3, do not reach for Redis, Celery or async workers to solve a problem — solve it with what exists, or say explicitly that this is a problem a later stage addresses.
 
Stage order: Python/FastAPI → Postgres/SQL → SQLAlchemy/Alembic → N+1 & indexes → transactions & concurrency → auth & multi-tenancy → Redis → queues → testing → Docker/CI → observability → deploy → load testing.
 
---
 
## Data model
 
| Entity | Notes |
|---|---|
| `workspace` | Tenant boundary. Everything scopes to it. |
| `member` | User in a workspace. Roles: `owner`, `editor`, `viewer`. |
| `document` | Status machine: `pending → processing → ready \| failed`. |
| `chunk` | Derived from a document. Later carries an embedding. |
| `query` | Question, answer, latency, cost. |
| `credit_ledger` | Append-only. Balance = `SUM(amount)`. Never store a balance column. |
 
---
 
## Stack
 
Python 3.12 · FastAPI · PostgreSQL · SQLAlchemy 2.0 · Alembic · Redis · Celery · pytest · Docker Compose · GitHub Actions · OpenTelemetry · k6
 
Do not introduce a library that isn't on this list without flagging the tradeoff first. In particular, do not suggest an ORM helper, a permissions library, or an auth library that hides the mechanism being learned — the author is implementing JWT and RBAC by hand deliberately.
 
---
 
## Conventions
 
- Repository layer owns all database access. Route handlers never touch a session directly.
- Tenant scoping lives in the repository layer, not in route handlers. A repository method that can return another tenant's row is a bug.
- Async endpoints must not call blocking code. If something blocks, it goes to a threadpool or the queue.
- Migrations are reviewed by hand. Alembic autogenerate output is a draft, never a commit.
- Every deliberate failure gets recorded with before/after numbers.
---
 
## Commands
 
```bash
docker compose up              # api, worker, postgres, redis
alembic upgrade head           # apply migrations
alembic revision --autogenerate -m "..."
pytest                         # full suite
pytest -m integration          # integration only
```
 
---
 
## The four gates
 
A concept is not done until all four are true. Hold the author to this — if they want to move on with a gate unmet, say so.
 
1. **Learned** — can state the problem it solves.
2. **Applied** — used it for a real requirement in this codebase.
3. **Broke it** — caused its failure mode deliberately and observed it.
4. **Can explain** — can defend the decision without notes, including the tradeoff.
Gate 3 is not optional. "I fixed the N+1" is worthless in an interview. "220 queries down to 3, p95 from 1.9s to 240ms, here's the query plan" is the whole story. Whenever a fix lands, ask for the number.
 
---
 
## Never
 
- Write a feature end to end unless explicitly asked.
- Reach for a later-stage technology to dodge a current-stage problem.
- Add a dependency to make the stack look impressive.
- Let a fix ship without a before/after measurement.
- Describe this repo publicly as a practice or tutorial project. It is a real system, built incrementally, and the README reflects that.

## Project state

Corpusly is a greenfield project — intended as "a multi-tenant document intelligence platform" (per `pyproject.toml`), but currently only the `uv init --package` scaffold exists: `src/corpusly/__init__.py` holds a stub `main()`, there are no dependencies, no tests, and an empty `README.md`. Treat architectural decisions as open rather than inferring them from the code.

## Tooling

Managed entirely by **uv** (v0.12.x) with the `uv_build` backend. Python is pinned to 3.12 via `.python-version`. Do not invoke `pip`, `python -m venv`, or edit `.venv/` directly — uv owns the environment and `uv.lock`.

```sh
uv sync                       # create/refresh .venv from uv.lock
uv add <pkg>                  # add a runtime dependency (updates pyproject.toml + uv.lock)
uv add --dev <pkg>            # add a dev-only dependency
uv run corpusly               # run the console entry point (project.scripts -> corpusly:main)
uv run python -c "..."        # any command inside the project env
```

## Layout

`src/`-layout package: importable code lives under `src/corpusly/`, and the `uv_build` backend infers the package from the project name — a top-level module added outside `src/corpusly/` will not be packaged.

The console script `corpusly` is wired to `corpusly:main`, so `main` must stay exported from `src/corpusly/__init__.py` (directly or re-exported) for the entry point to resolve.

## Testing

No test framework is configured yet. When adding one, prefer `uv add --dev pytest` and a top-level `tests/` directory; the commands then are:

```sh
uv run pytest                          # full suite
uv run pytest tests/test_foo.py::test_bar   # single test
```
