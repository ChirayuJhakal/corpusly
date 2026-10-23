# Progress log

Last updated: 2026-10-20. Current stage: **Stage 3, Postgres integration (raw SQL, psycopg 3)**.

## Done

### Stage 2: FastAPI + in-memory storage
- Endpoints: `POST /workspaces/`, `GET /workspaces/{id}`, and documents `GET` list (limit/offset), `POST`, `GET /{id}`, `PATCH /{id}` under `/workspaces/{workspace_id}/documents`.
- Repository layer (`src/corpusly/repositories/`): store injected via `__init__`; every document method takes `workspace_id`; cross-tenant access returns `None` → 404; copy-on-read with `model_copy()`.
- Composition root (`src/corpusly/dependencies.py`): providers `get_workspace_repository` / `get_document_repository` plus `Annotated` aliases. This file and the repositories are the seam the Postgres port replaces.
- Request-ID middleware, `/health`.
- Review: `docs/week-02-review.md` (3 rounds).

### Test safety net (Phases A–E)
- **A, isolation:** `tests/conftest.py` gives a fresh store per test via `app.dependency_overrides` keyed by the provider function and clears them after. Two broken versions observed (no overrides → 409 leak; string keys → override ignored). Note: `docs/notes/dependency-override-keys.md`.
- **B, tenant test:** `test_cross_tenant_workspace_patch` uses real tenants A/B, 404 both ways, and checks the effect after a cross-tenant PATCH. Items 4–7 skipped (time).
- **C, extra tests:** skipped (optional).
- **D, mutation-tested** the existing tests.
- **E, event-loop experiment:** 3 concurrent requests with a 2s sleep: async + `time.sleep` 6.11s, `def` + `time.sleep` 2.06s, async + `asyncio.sleep` 2.09s. `/health` 5.72s while the loop was blocked. Threadpool cap: 40 concurrent → 2.34s, 41 → 4.08s. Note: `docs/notes/event-loop-blocking.md`.

### Stage 3 so far
- **Step 1, done.** Role `corpusly` (LOGIN; no superuser/createdb/createrole). Databases `corpusly` and `corpusly_test`, both owned by `corpusly`. Local `pg_hba.conf` is `trust`, so passwords are not checked locally.
- **Step 2, done.** `db/schema.sql`: uuid PKs via `gen_random_uuid()`, `text` names, `timestamptz` with `DEFAULT now()`, `UNIQUE(workspace_name)`, FK `documents.workspace_id ... ON DELETE CASCADE` (justified: no business need to keep a deleted workspace's documents; the future `credit_ledger` must NOT cascade), column `document_status` of ENUM `document_status_enum`. Re-runnable (drops tables, then the type). Loaded into `corpusly` and `corpusly_test`, owned by `corpusly`. The API field stays `status`; the repository SQL must alias `document_status AS status` (Step 6).
- **Step 2 gate 3: constraint violations, observed** (SQLSTATE codes are what Step 7 will catch):

  | Violation | Error | SQLSTATE / psycopg class |
  |---|---|---|
  | duplicate `workspace_name` | `duplicate key value violates unique constraint "workspaces_workspace_name_key"` | 23505 `UniqueViolation` |
  | document with non-existent `workspace_id` | `insert or update on table "documents" violates foreign key constraint "documents_workspace_id_fkey"` | 23503 `ForeignKeyViolation` |
  | NULL `document_name` / `workspace_name` | `null value in column "document_name" of relation "documents" violates not-null constraint` | 23502 `NotNullViolation` |
  | status `'banana'` | `invalid input value for enum document_status_enum: "banana"` | 22P02 `InvalidTextRepresentation` |
  | over-length name (old `varchar(225)`) | `value too long for type character varying(225)` | 22001 `StringDataRightTruncation` |

- **Step 3, done.** `Settings` lives in `src/corpusly/config.py` (a leaf module that imports nothing from `corpusly`, so `main.py` and `dependencies.py` can both import it without a cycle) with module-level `settings = Settings()`. `database_url: str` is required; the real value is in `.env`; `.env.example` shows the URL format with a `CHANGE_ME` password. `python-dotenv` and `load_dotenv()` removed (it stays in `uv.lock` as a transitive dependency of pydantic-settings). Observed:
  - `.env` missing → app fails at import: `ValidationError ... database_url Field required`. That fail-fast is intended.
  - Shell `DATABASE_URL` set **and** `.env` present → **the shell value wins**. pydantic-settings precedence: init kwargs > environment variables > `.env` file > defaults. (The prediction was that `.env` wins; it doesn't.)
- **Step 4, done.** `psycopg[binary,pool]` added. `[binary]` = precompiled wheel bundling libpq; `[pool]` = `psycopg_pool`. Smoke test (run on `corpusly_test`):
  - `uuid` columns come back as `uuid.UUID`, not `str` (prediction was `str`). Pydantic v2 `str` fields reject it ("Input should be a valid string"), so the repositories must convert with `str(...)` in Step 6, keeping the models unchanged.
  - `timestamptz` comes back as a timezone-aware `datetime`.
  - `connect()` then `close()` without `commit()` → row discarded (implicit BEGIN; psycopg isn't autocommit).
  - `with psycopg.connect(...)` without `commit()` → row saved (commits on clean exit, rolls back on exception).
- **Concept note:** `docs/notes/connections-pools-transactions.md`: one pool per process, one connection per request, one transaction per request. Covers connection cost, MVCC, locks, the aborted-transaction state, pool mechanics and sizing, and the FastAPI mapping. Includes a two-terminal psql exercise and three check questions (not yet answered).

## Step 5, connection lifetime (5.1–5.2 done; 5.3 merged into Step 6)
| Sub-step | What | Status |
|---|---|---|
| 5.1 | Pool created once per process in `lifespan` (`main.py`): `ConnectionPool(..., min_size=4, max_size=10, open=False)`, `pool.open(wait=True)`, stored as `app.state.db_pool`, `pool.close()` after `yield` | **done** (commit `53c0ebc`) |
| 5.2 | `get_db_connection(request)` in `dependencies.py`: sync `def` generator, `with request.app.state.db_pool.connection() as conn: yield conn` (commit on clean exit, rollback on exception, connection returned to pool). Alias `ConnectionFromPool = Annotated[Connection, Depends(get_db_connection, scope="function")]` | **done** (uncommitted) |
| 5.3 | Repository providers take `conn: ConnectionFromPool` and pass it to the repositories | merged into Step 6 (porting repos one at a time keeps the app working) |
| 5.4 | Prove commit/rollback + same connection for both repos in one request (`use_cache=True`) | folded into Step 6 verification |

**Observed:**
- 5.1: server up → 4 `idle` rows in `pg_stat_activity` (= `min_size`); after Ctrl+C → 0. With the pool built at module level, `pytest` (which never touches the DB) hung 30s and failed with `PoolTimeout: pool initialization incomplete after 30.0 sec` while Postgres was stopped. Moving creation into `lifespan` fixed it: tests pass with no DB, since `TestClient(app)` without `with` never runs lifespan. Also: a closed psycopg pool can't be reopened, so a module-level pool would break a second lifespan run in the same process.
- 5.2 (scratch debug route returning `pg_backend_pid()`): 10 sequential requests → **4 distinct pids**, each repeating 2–3×, identical to the 4 idle backends in `pg_stat_activity`. So connections are reused, not opened per request, and the pool rotates them. `max_size` is never reached by sequential traffic.

**Pool sizing (correct model):** `max_size=10` = at most 10 requests hold a DB connection at once per process. With the 40-thread threadpool, requests 11–40 wait for a connection (up to `timeout`, 30s, then `PoolTimeout`). Pool `num_workers=3` are background maintenance threads, not query runners. Constraint: workers × `max_size` < `max_connections` (100). The old comment ("10 worker threads per connection") was wrong and has been removed; re-add a correct one-line justification.

**Circular import hit and fixed:** the repositories imported `ConnectionFromPool` from `dependencies.py`, which imports the repositories → `ImportError: cannot import name 'ConnectionFromPool' from partially initialized module 'corpusly.dependencies'`. Root cause is layering: `ConnectionFromPool` is FastAPI wiring (`Depends`), and repositories must not know FastAPI exists. Fix: repositories type `__init__(self, conn: psycopg.Connection)`. Direction: routes → dependencies (composition root) → repositories → models/psycopg. This also makes repositories usable from scripts, tests and the future ingestion worker.

## Current: Step 6, port repositories (one at a time)
**State (uncommitted, mid-edit):** both repositories now take `psycopg.Connection`; both providers in `dependencies.py` pass `conn`; the in-memory stores are removed. The app imports cleanly. **The bodies are not working SQL yet.** **Tests currently fail (2 failed):** `tests/conftest.py` overrides still build the repositories with dicts (`WorkspaceRepository(_workspace_store_test)`), and the repositories now call `.execute()` on them → `AttributeError: 'dict' object has no attribute 'execute'`. Expected: the in-memory test fixture no longer fits the SQL repositories. It gets reworked in Step 9 (tests against `corpusly_test`). Until then, verify Step 6 manually with curl + psql.

**6a: `WorkspaceRepository`, do first.** Open issues in the current draft:
1. `conn.execute(...)` returns a cursor; call `.fetchone()` to get the row.
2. `create` returns the raw result; it must build a `Workspace`. `get`/`get_by_name` call `.model_copy()` on a non-Pydantic object. Copy-on-read is no longer needed (every read builds a fresh object).
3. `RETURNING *`: list columns explicitly.
4. Convert `workspace_id` `UUID` → `str` before building the model (or use `row_factory=dict_row` and convert).
5. Remove the leftover `uuid4` / `datetime` imports. Postgres owns ids and timestamps.
6. **Gotcha to decide:** `GET /workspaces/abc`. Comparing a non-UUID string to a `uuid` column raises 22P02 `InvalidTextRepresentation` → 500, and it aborts the request's transaction. In memory it was a 404. Decide where the fix belongs (route, repository or model) and why.

**6a verify:** POST then GET; row visible in psql; **restart server and GET again** (persistence); duplicate name → 409; random valid UUID → 404; `abc` → (your answer).

**6b: `DocumentRepository`, after 6a.** Its draft is also half-changed (`RETURNING *`, cursor not row); finish 6a first. Requirements: `WHERE workspace_id = %s` on every query (tenant scoping), `document_status AS status` alias, `UUID` → `str` for both ids, `updated_at = now()` on UPDATE, `ORDER BY created_at, document_id LIMIT %s OFFSET %s`. A partial PATCH (only name, only status) must not overwrite the other field. Then verify that `POST /workspaces/{id}/documents` (which uses both repos) gets one connection, and that a raised error rolls back.

## Pending: Steps 6–10
6. **Port repositories** (in progress, see above): same signatures. `%s` parameters only (never f-strings), `WHERE workspace_id = %s` on every document query, `RETURNING` for DB-generated ids/timestamps, `updated_at = now()` on UPDATE, `ORDER BY created_at, document_id` for pagination. Alias `document_status AS status`; convert `UUID` → `str`.
7. **Errors:** `UniqueViolation` → domain error → 409; the route's check-then-insert becomes redundant. Bad status → 422, not 500. Remember a failed statement aborts the transaction: map the error and let the request fail.
8. **Seam check:** `git diff --stat`. Only repositories, `dependencies.py`, `main.py` (lifespan) and config should change.
9. **Tests on `corpusly_test`:** truncate tables between tests. Existing tests must pass unchanged.
10. **Gate 3 breaks** (before/after numbers in `docs/notes/`): pool vs connection-per-request latency; sync DB call inside `async def`; SQL injection via f-string on a throwaway branch; duplicate-name race (check-then-insert vs UNIQUE).

Out of scope for this stage: SQLAlchemy/Alembic, extra indexes (week 4), Docker Compose (week 10), async driver.

## Open items
- Repo is public; `CLAUDE.md` and `docs/week-02-review.md` are tracked. Decide on visibility.
- Known leftovers: `POST /workspaces` returns 200 (not 201) and 307s without the trailing slash; `WorkspaceReponse` typo; ruff import-sort warning in `main.py`.
- Commits must use `Chirayu Jhakal <jhakalchirayu@gmail.com>`. Never use the work account.

## Run
```sh
uv run uvicorn corpusly.main:app --reload
uv run pytest -q
```
