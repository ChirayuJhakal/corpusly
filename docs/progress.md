# Progress log

Last updated: 2026-10-12. Current stage: **Stage 3, Postgres integration (raw SQL, psycopg 3)**.

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
- **Step 2, in progress.** `db/schema.sql` written: uuid PKs via `gen_random_uuid()`, `timestamptz` with `DEFAULT now()`, `UNIQUE(workspace_name)`, FK `documents.workspace_id` with `ON DELETE CASCADE`, `document_status` ENUM.

## Next: finish Step 2
1. Add `DROP TYPE IF EXISTS document_status;` after the table drops. Re-running currently fails with `type "document_status" already exists`.
2. Column rename `status` → `document_status` leaked into the API. The uncommitted changes in `models/documents.py`, `repositories/documents.py` and `routes/documents.py` change the PATCH body key, so clients sending `status` are silently ignored. Either name the column `status` or alias it in repo SQL, then revert those three files (`git restore`).
3. Add a one-line SQL comment justifying `ON DELETE CASCADE` (consider: the ledger is append-only).
4. Be ready to defend ENUM vs `text + CHECK` (enum values are hard to remove/rename).
5. Load into both DBs: `psql -U corpusly -d corpusly -f db/schema.sql`, same for `corpusly_test`. Neither has tables yet.
6. Gate 3: by hand, insert a bad FK and a NULL name and record the errors. Already observed:
   - duplicate name → `duplicate key value violates unique constraint "workspaces_workspace_name_key"`
   - bad status → `invalid input value for enum document_status: "banana"`
   - over-length (old varchar) → `value too long for type character varying(225)`

## Pending: Steps 3–10
3. **Config:** add `DATABASE_URL` to `Settings`; real value in `.env` (gitignored); commit `.env.example`. Un-comment `settings = Settings()`. Remove `python-dotenv` and `load_dotenv()` (pydantic-settings reads `.env`).
4. **Driver:** `uv add "psycopg[binary]"`. No ORM.
5. **Connection lifetime:** pool created/closed in FastAPI `lifespan`. Providers become `yield` dependencies: borrow a connection per request, commit on success, roll back on error, return it to the pool.
6. **Port repositories:** same signatures. `%s` parameters only (never f-strings), `WHERE workspace_id = %s` on every document query, `RETURNING` for DB-generated ids/timestamps, `updated_at = now()` on UPDATE, `ORDER BY created_at, document_id` for pagination.
7. **Errors:** `UniqueViolation` → domain error → 409; the route's check-then-insert becomes redundant. Bad status → 422, not 500.
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
