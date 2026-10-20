# Connections, pools and transactions

The rule Step 5 implements: **one pool per process, one connection per request, one transaction per request.** This note builds up why, starting simple and getting more technical.

---

## Layer 0: The analogy

Think of the database as an office you can only reach by **phone**.

- **Connection = a phone call.** Dialling takes time: it rings, someone answers, they check who you are. Once you're connected, you talk **one sentence at a time**, in order.
- **Transaction = speaking "in pencil".** Everything you say during the call is provisional. At the end you say either "make it permanent" (**COMMIT**) or "forget all that" (**ROLLBACK**). Until you commit, nobody else in the office sees your changes.
- **Pool = a bank of phones that are already connected.** Instead of dialling each time, a worker picks up a phone that's already on the line, uses it, and puts it back.

Everything below is the technical version of this picture.

---

## Layer 1: The vocabulary

| Term | What it is |
|---|---|
| **Process** | A running program with its **own private memory**. Two processes can't see each other's variables. `uvicorn` is a process, and so is each Postgres server process. |
| **Thread** | A worker *inside* a process. Threads **share** the process's memory. `def` routes run on threads (the threadpool of 40 measured in `event-loop-blocking.md`). |
| **Socket** | The operating system's handle for a network conversation. A connection is, at the bottom, a socket. |
| **TCP handshake** | The three messages that open a reliable network channel before any data flows. |
| **TLS** | Encryption on top of TCP, with its own extra handshake. Used in production, usually skipped on localhost. |
| **Authentication** | Postgres checking who you are. The local config is `trust`, which skips it; in production it's a password exchange (SCRAM). |
| **Backend** | The Postgres process that serves **one** connection. Postgres **forks** (clones) a new one for every connection. |
| **Session** | Everything Postgres remembers about one connection: the open transaction, settings like `timezone`, temporary tables. |
| **Transaction** | A group of statements that succeed or fail as **one unit**. |
| **Autocommit** | A mode where every statement is its own transaction and commits immediately. `psql` uses it by default; **psycopg doesn't**. |
| **Lock** | Postgres marking a row "being changed, wait your turn" so two writers can't clash. |
| **Pool** | A set of open connections kept ready and reused across requests. |

---

## Layer 2: What a connection really is

### What happens on `psycopg.connect(url)`
1. **DNS:** `localhost` is turned into an IP address.
2. **TCP handshake:** three network messages.
3. **TLS handshake:** in production, more round trips plus cryptography.
4. **Startup message:** "I'm role `corpusly`, I want database `corpusly`."
5. **Postgres forks a backend process.** That is a real OS process, using several MB of memory.
6. **Authentication:** a password exchange.
7. **Session setup:** the backend loads settings and reports `ReadyForQuery`.

That's many steps, several network round trips and a new OS process. It takes milliseconds on a laptop and tens of milliseconds to a cloud database. A simple `SELECT` by primary key can take *less* time than that. So if you connect on every request, connecting can become the slowest part of the request. Step 10 measures this.

### Each connection is a process
Postgres caps them with `max_connections`, which defaults to **100**, with 3 reserved for superusers. Every connection uses real memory on the server, which is why you can't just open thousands.

### A connection is sequential and has state
- **Sequential:** send a query, wait, read the result. You can't send two queries in parallel over the same connection.
- **Stateful:** the backend remembers things between statements. The most important is **"am I inside a transaction, and has it failed?"**

Because the transaction belongs to the connection, a statement inherits whatever transaction the connection is currently in. That one fact drives all three rules.

---

## Layer 3: Transactions

### The guarantee (ACID)
- **Atomic:** all statements apply, or none do.
- **Consistent:** constraints (UNIQUE, FK, NOT NULL) hold when you commit.
- **Isolated:** others don't see your uncommitted changes.
- **Durable:** once COMMIT returns, the data survives a crash.

### How Postgres does it: MVCC
MVCC stands for Multi-Version Concurrency Control.
- An `UPDATE` doesn't overwrite a row. It writes a **new version** of it, tagged with the writing transaction's id.
- Other sessions keep seeing the **old** version until the writer commits.
- **COMMIT** marks the transaction as committed, so the new versions become visible to everyone.
- **ROLLBACK** marks it as aborted, so the new versions are simply ignored, and cleaned up later by VACUUM.

So **rollback is cheap**: nothing gets undone, the new versions are just never shown.

### Locks
If two transactions UPDATE the **same row**, the second one **waits** until the first commits or rolls back. Locks are held **until the transaction ends**. That's why long transactions hurt: everyone needing those rows waits behind them.

### Implicit BEGIN in psycopg
psycopg isn't in autocommit mode. The **first statement silently starts a transaction**, and it stays open until a commit or rollback. Smoke test: closing a connection without a commit lost the inserted row; `with psycopg.connect(...)` committed it on a clean exit.

### The "failed transaction" state
If a statement fails inside a transaction (for example, a `UniqueViolation`), the transaction is now **aborted**. Every later statement on that connection fails with:
```
current transaction is aborted, commands ignored until end of transaction block
```
until a `ROLLBACK`. You can't catch the error and carry on querying on the same transaction. (Savepoints are the finer-grained tool; that comes later.)

---

## Layer 4: Why sharing a connection is wrong

`def` routes run on **up to 40 threads at once**. Suppose they all share one global connection:

```
thread A: INSERT doc_a           ┐
thread B: INSERT doc_b           │ same connection → same transaction
thread B: COMMIT                 │ ← commits A's half-finished work too
thread A: (error) ROLLBACK       ┘ ← too late, doc_a is already permanent
```

- A's **partial work gets committed** by B's commit.
- Or B's error **aborts the transaction**, so A's statements fail through no fault of A's.
- psycopg 3 does put a lock around each statement, so the bytes on the wire don't get garbled. But that protects only the **wire protocol**, not **transaction boundaries**. It also means all 40 threads queue behind one connection, so concurrency drops to 1.

**Conclusion:** a request needs a connection that is **its own** for the whole request.

---

## Layer 5: The pool

### What it does
- **At startup:** open `min_size` connections, paying the connection cost up front.
- **On borrow:** hand out an idle connection. If none is idle and there are fewer than `max_size`, open a new one. If the pool is at `max_size`, **wait**. If nothing frees up within `timeout` (default 30s), raise `PoolTimeout`.
- **On return:** check the connection's state:
  - transaction still open → commit it, or roll it back if an error happened
  - connection broken → throw it away and open a fresh one
  - otherwise → mark it idle for the next borrower
- **Housekeeping:** close connections idle past `max_idle`, and replace connections older than `max_lifetime`.

The pool is **thread-safe**: 40 threads can borrow and return at the same time. Each *connection* is used by one thread at a time; the *pool* is shared.

### Why "per process"
- Processes don't share memory. With `uvicorn --workers 4`, each worker process imports the app, runs `lifespan` and **builds its own pool**.
- So the total number of Postgres connections is **workers × max_size**, and that has to fit under `max_connections`.
- Within one process, all threads share **that process's one pool**.

```
uvicorn master
 ├─ worker process 1 ── pool (max 10) ──┐
 ├─ worker process 2 ── pool (max 10) ──┤
 ├─ worker process 3 ── pool (max 10) ──┼──▶ Postgres (max_connections=100)
 └─ worker process 4 ── pool (max 10) ──┘     up to 40 backends in use
```

### Sizing
- **Too small:** requests wait for a connection, so latency climbs and eventually you get `PoolTimeout`. Same shape as request 41 waiting for the threadpool, but waiting on the pool instead.
- **Too big:** wasted Postgres memory, and a risk of hitting `max_connections` once you scale out to more workers.
- More connections isn't faster past a point. Postgres has a limited number of CPU cores; a few hundred busy backends spend their time contending, not working.

---

## Layer 6: Mapping it onto FastAPI

| Concept | FastAPI mechanism | When it runs |
|---|---|---|
| Pool (per process) | **`lifespan`**: a function that runs code at startup, `yield`s while the app serves requests, then runs shutdown code | once at startup, once at shutdown |
| Where the pool lives | **`app.state`**: a place on the app object to keep process-wide things | for the process's lifetime |
| Connection (per request) | **dependency with `yield`**: code before `yield` = setup, `yield` = hand the value to the route, code after `yield` = cleanup. If the route raises an exception, it propagates **into** the dependency at the `yield`. | around each request |
| Transaction (per request) | the `with pool.connection()` block in that dependency: commit on clean exit, rollback on exception | inside the dependency |
| Same connection for both repositories | **`use_cache=True`** (the default): within one request, a dependency is called **once** and its result shared with everything that asks for it | per request |
| Commit before the response | **`scope="function"`**: the cleanup after `yield` runs **before** the response is sent | per request |

### A full request, end to end
```
uvicorn receives HTTP request
 └─ threadpool thread picks it up (because the route is `def`)
     └─ FastAPI resolves dependencies
         └─ get_conn: borrow conn from app.state.pool        (waits if pool exhausted)
             └─ WorkspaceRepo(conn), DocumentRepo(conn)        (same conn, via cache)
                 └─ route runs → repo SQL → implicit BEGIN on first statement
             ┌─ route returned normally → COMMIT
             └─ route raised (HTTPException, bug, UniqueViolation) → ROLLBACK
         └─ connection returned to pool, idle for next request
     └─ response sent (status matches what actually happened in the DB)
```

### Summary

| Scope | Lives for | Created where | Protects against |
|---|---|---|---|
| Pool | the whole process | `lifespan` | paying the connection setup cost per request |
| Connection | one request | `yield` dependency | two requests interleaving statements on one connection |
| Transaction | one request | the `with pool.connection()` block | half-applied writes |

---

## Layer 7: Rules this gives you for later

1. **Never hold a transaction open across slow work.** No HTTP calls, file processing or LLM calls inside the request's transaction. The transaction holds locks and a connection the whole time.
2. **A caught DB error poisons the transaction.** In Step 7, map the error and let the request fail; don't run more queries on the same transaction.
3. **Pool size is a capacity decision,** and the math is workers × `max_size` ≤ `max_connections`.
4. **Async later means an async pool.** A sync pool inside `async def` blocks the event loop, the same failure as the Phase E experiment. That's in Step 10.

---

## Hands-on: see it in psql

Open **two** terminals, each running `psql -U corpusly -d corpusly_test`. Both are in autocommit mode until you type `BEGIN`.

0. **T2:** `INSERT INTO workspaces (workspace_name) VALUES ('lockdemo');` This is committed immediately.
1. **Both:** `SELECT pg_backend_pid();` You get two different numbers: two backend processes.
2. **T1:** `BEGIN; INSERT INTO workspaces (workspace_name) VALUES ('mvcc');`
   **T2:** `SELECT workspace_name FROM workspaces;` `mvcc` is **not visible**. That's isolation.
3. **T1:** `UPDATE workspaces SET workspace_name = 'lock_a' WHERE workspace_name = 'lockdemo';`
   **T2:** `UPDATE workspaces SET workspace_name = 'lock_b' WHERE workspace_name = 'lockdemo';` T2 **hangs**: it's waiting for T1's row lock.
4. **T1:** `INSERT INTO workspaces (workspace_name) VALUES (NULL);` This fails. Then **T1:** `SELECT 1;` This fails with "current transaction is aborted". T2 is still hanging.
5. **T1:** `ROLLBACK;` T2 unblocks immediately. T1's update was discarded, so T2 still finds `lockdemo` and updates it. `mvcc` never existed.
6. **Cleanup (either terminal):** `DELETE FROM workspaces WHERE workspace_name IN ('lockdemo', 'lock_b');`

---

## Check yourself

1. With 4 uvicorn workers and `max_size=30`, how many Postgres connections could you end up with, and what's the default limit?
2. A route creates a document, then raises `HTTPException(404)`. Is the document saved?
3. Why is "one global connection plus a lock around it" safe but still a bad idea?
