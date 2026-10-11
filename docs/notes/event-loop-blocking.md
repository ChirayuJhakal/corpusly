# Blocking the event loop: `async def` vs `def`

**Stage:** week 2 gate 3, run before the Postgres port (week 3)
**Concept:** where FastAPI runs a handler, and what a blocking call does there

## Setup

Three temporary endpoints, each waiting 2 seconds a different way. They were added to the real app,
including its request-ID middleware, from a scratch file outside the repo. Uvicorn ran as a single
process with no `--reload`. Requests were fired concurrently with
`seq N | xargs -P N curl ...` and timed as total wall-clock. Two runs each, and the runs agreed to
within 0.03s.

| Endpoint | Handler | Wait |
|---|---|---|
| async-blocking | `async def` | `time.sleep(2)` |
| sync-blocking | `def` | `time.sleep(2)` |
| async-nonblocking | `async def` | `await asyncio.sleep(2)` |

## Predictions vs results: 3 concurrent requests

| Endpoint | Predicted | Measured |
|---|---|---|
| async-blocking | 6s | **6.11s** |
| sync-blocking | 6s | **2.06s** (wrong prediction) |
| async-nonblocking | 3s | **2.09s** (wrong prediction) |
| baseline: 3 requests sent one after another | | 6.10s |

Predictions were written down before the run.

## Side effect: `/health` latency while 3 slow requests were running

| Running at the time | `/health` took |
|---|---|
| async-blocking | **5.72s** |
| sync-blocking | **0.002s** |

## Extension: sync-blocking at higher concurrency

| Concurrent requests | Measured |
|---|---|
| 40 | 2.34s |
| 41 | **4.08s** |
| 50 | 4.12s |

## Why

- **`async def` handlers all run on one thread, the event loop.** `time.sleep` doesn't hand that
  thread back, so the three requests ran one at a time (3 × 2s), and **every other endpoint froze
  too**. `/health`, which does no work, took 5.7s. The problem isn't one slow endpoint; it's that
  the whole server stalls.
- **`def` handlers run in a thread pool,** one thread per request. `time.sleep` blocks only that
  thread, so all three slept in parallel and the event loop stayed free (`/health` in 2ms). This was
  the wrong prediction: plain `def` is not "blocking the server".
- **`await asyncio.sleep` gives control back to the loop while it waits,** so all three overlapped on
  a single thread. This works only if every wait is an `await`.
- **The thread pool holds 40.** Request 41 waited for a free thread, which forced a second 2-second
  batch. `def` gives concurrency, but it's capped at 40 blocking requests at a time per process.

## Consequences for the Postgres port

- A synchronous driver (psycopg) waits on the network the same way `time.sleep` does.
- **Sync driver + `def` handler:** fine. That's the 2.06s row, and the handlers are already `def`.
- **Sync driver inside `async def`:** that's the 6.11s row. One slow query stalls the entire API.
- Connection pool size and the 40-thread limit need to be considered together.
