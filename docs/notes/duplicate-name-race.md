# Duplicate workspace name: check-then-insert race

## The bug
`POST /workspaces/` checked for the name, then inserted, as two separate statements:

```
A: SELECT ... WHERE workspace_name = 'acme'  → none     B: SELECT ... → none
A: INSERT 'acme'                                         B: INSERT 'acme' → waits on A's uncommitted key
A: COMMIT → 200                                          B: UniqueViolation (23505), unhandled → 500
```

Both checks ran before either insert committed, so both saw the name as free. The UNIQUE constraint still blocked the duplicate (data stayed correct), but the loser got a **500** for what is really a **409**.

Prediction before running: 1 × 200 and the rest 409. That holds only when the requests happen to serialise.

## Setup
- 20 concurrent `POST /workspaces/` with the same name (`xargs -P 20` + curl), fresh name per run, 10–20 runs.
- "Widened": a scratch wrapper sleeps 200 ms at the start of `WorkspaceRepository.create`. On the old code that sleep sits between the check and the INSERT, which makes the race reproducible. On the fixed code it only delays the INSERT. Project files weren't modified for this; the "before" runs used a copy of commit `3d68515`.

## Results

| Code | Window | Runs × concurrency | 200 | 409 | 500 | Runs with a 500 |
|---|---|---|---|---|---|---|
| Before (check, then insert) | natural | 5 × 20 (first run on a cold pool) | 5 | 92 | **3** | 1/5 |
| Before | natural | 20 × 20 (warm) | 20 | 379 | **1** | 1/20 |
| Before | widened 200 ms | 10 × 20 | 10 | 100 | **90** | **10/10** |
| After (constraint only) | widened 200 ms | 10 × 20 | 10 | 190 | **0** | 0/10 |
| After | natural | 10 × 20 | 10 | 190 | **0** | 0/10 |

In every case, the database never held more than one row per name.

## Why
- **The race is rare in normal timing**: 1 in 400 requests warm. That's why it survives manual testing and unit tests. Widening the window proves it exists; a production server under load hits it eventually.
- **The UNIQUE index is what actually serialises the inserts.** A second INSERT of the same key **waits** for the first transaction. If that commits, the waiter fails with 23505; if it rolls back, the waiter succeeds. No application-level check can do this, because the check and the insert aren't atomic.

## Fix
- `WorkspaceRepository.create` catches `psycopg.errors.UniqueViolation` and raises the domain error `WorkspaceNameTaken` (`corpusly/errors.py`). Routes never import psycopg.
- After the violation, the transaction is aborted, so nothing else runs; raising lets `get_db_connection` roll back.
- `POST /workspaces/` catches `WorkspaceNameTaken` and raises 409. The `get_by_name` pre-check is deleted: one code path, and the constraint decides.

## Takeaway
Uniqueness under concurrency is enforced by the database, never by "SELECT first". An application check is at best an optimisation, and here it was a source of 500s.
