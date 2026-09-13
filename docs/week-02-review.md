# Week 2 review — six endpoints, in-memory

*Round 2. Everything below was verified against a running server, not read off the page.*

---

## Round 3 — repository layer landed

Closed: **A** (repositories are classes with domain signatures), **B** (`Document.workspace_id`),
**C** (verified: cross-tenant read *and* write now 404), **G** (`Depends` + `Annotated` aliases),
**N1** (timestamps minted once in `create`; same doc read 2s apart returns the same `created_at`),
**N6** (document routes grouped under one resource-shaped router). `workspaces_and_documents` is
gone. Pagination and partial PATCH both work. `grep` finds no storage access outside
`repositories/`.

**The URL changed**, forced by the repository signature: `/documents/{id}` →
`/workspaces/{workspace_id}/documents/{id}`. At week 6 that path segment stops being trusted input
and becomes a claim verified against the token.

Still open, unchanged: **D** (status is a free string, `model_copy(update=...)` skips validation —
matters when it becomes an enum), **E** (should clients write `status` at all?), **H**, 200-not-201,
the globally-unique workspace name, the two error shapes, `WorkspaceReponse`/`doesnt` typos, and
`main.py` (dead `settings`, no `.env.example`, unsorted imports — ruff flags it).

---

## Scorecard

**The app boots and serves.** All six endpoints are registered and respond. That was the whole
blocker last round and it's gone.

| Layer | Movement |
|---|---|
| Wiring / mechanics | **Fixed.** ~15 items, clean. |
| Idiom | Partial. |
| **Architecture** | **Zero.** The finding that mattered most got no work. |

You fixed everything that stopped the server from starting and nothing that determines whether week 3
is a port or a rewrite. That's a real pattern to notice: the mechanical bugs announce themselves, the
structural ones don't, so structural work only happens if you schedule it deliberately.

---

## Fixed since last round

- App boots. `uvicorn` added, dead `uuid` package removed.
- One `app` + `APIRouter` per module + `main.py` — **finding F closed.**
- `WorkspaceReponse` is a real `BaseModel`.
- `.push()` → `.append()`; `model['field']` → attribute access; `int` path params → `str`.
- `post_workspace` returns the workspace it actually created.
- `WorkspaceRequest` / `DocumentRequest` — clients no longer send ids they don't own. **Half of §3.1.**
- `/health`, route prefixes, route tags.
- Request-ID middleware, and it correctly honours an inbound `X-Request-ID` instead of always
  minting one. That detail is right and most people get it wrong.

---

## New problems you introduced

### N1. The timestamps are fiction

`created_at` / `updated_at` have `default_factory` on the model, but the repository stores a bare dict
with neither field. So Pydantic invents them **at serialization time**, on every read:

```
GET /workspaces/{id}  →  created_at: 2026-09-12T14:42:52.556503Z
GET /workspaces/{id}  →  created_at: 2026-09-12T14:42:54.643822Z   # same workspace, 2s later
```

The creation time moves forward with the clock. Worse: `POST /workspaces/` has no `response_model`,
so it returns **no** timestamps, while `GET` of that same resource returns two. One resource, two
shapes, neither true.

This is the "models declared, dicts stored" note from last round graduating from style issue to data
corruption. The fields you added are actively lying. `default_factory` belongs at the point of
creation, not on the type that describes the response.

### N2. A fresh clone cannot start

`Settings.debug` has no default, `.env` is empty and gitignored, and there's no `.env.example`. So
`Settings()` raises `ValidationError` at import. I had to set `DEBUG=true` to get the server up.

Fail-fast on missing config is the right instinct. But required-with-no-default and no committed
template means the only person who can run this repo is the one with the untracked file.

### N3. `settings` is dead, and config is loaded twice

`settings` is assigned and never read. And `load_dotenv()` plus `SettingsConfigDict(env_file='.env')`
do the same job — pydantic-settings reads the file itself. `python-dotenv` is a redundant direct
dependency. Also: `Settings` lives in `main.py`; config belongs in its own module, because at week 3
the DB layer needs it and importing `main` to get it is a cycle.

### N4. `POST /workspaces` 307-redirects

`@router.post('/')` under prefix `/workspaces` produces the path `/workspaces/`, so `POST /workspaces`
returns a 307. Use `''` for the collection path. Harmless today; some HTTP clients drop the body on
redirect.

### N5. The request ID is echoed, not propagated

It's set on the response header and nowhere else — never on `request.state`, so no handler and no log
line can reference it. And there's no logging configured at all, so there's nothing to correlate it
*with*. Your README promises a request id that flows API → DB → cache → worker. Right now it's a
round-trip decoration.

### N6. Document routes split across two modules by URL prefix

`POST /workspaces/{id}/documents` lives in `routes/workspace.py`; `GET /documents/{id}` lives in
`routes/documents.py`. Organise by **resource**, not by URL prefix. The cost is already visible:
`routes/workspace.py` now imports and writes the `documents` store directly, which is tighter
coupling than you had before the refactor.

---

## Still open

### Architecture — none of this moved

| # | Problem | Breaks at |
|---|---|---|
| **A** | **There is still no repository layer.** `repositories/workspaces.py` is still one line: `workspaces = {}`. Zero functions. Routes still index, iterate and mutate storage directly. | wk 3–4 |
| **B** | `Document` still has no `workspace_id`. Ownership lives only in the adjacency dict. | wk 3, wk 6 |
| **C** | `/documents/{id}` still unscoped. **Verified live:** read *and* wrote another tenant's document with nothing but its UUID. | live now |
| **D** | `status` still a free string. **Verified live:** `PATCH {"status":"banana"}` → 200. Still writes `'recieved'`, still not a state in your machine. | wk 3, wk 8 |
| **E** | PATCH still requires every field and still lets a client set `status`. | wk 8 |
| **G** | Still no dependency injection. Repos are module globals. A DB session must be per-request; a module global cannot be. | wk 3 |
| **H** | Module-level dicts, no test isolation. | wk 9 |

**A and G are the same fix and they are the whole game.** Everything else on this page is an
afternoon. Until the repository is functions with domain signatures, week 3 means rewriting all six
handlers instead of swapping two modules.

### Wrong now

- POST still returns **200**. Creation is 201 + `Location`.
- Duplicate-name check is still O(n) *and* still makes workspace names globally unique across all
  tenants — tenant A can probe whether tenant B exists. Still an unintended product decision.
- `documents.get(doc)` can still put `None` in the list → 500 via `response_model`.
- **Two error shapes, verified:** `{"detail": "Document doesnt exists"}` vs
  `{"detail": [{"type":"missing","loc":[...],...}]}`. Your README promises one envelope.

### Idiom

- `else :` and `else`-after-`raise` — both still there.
- `.items()` with a discarded key → `.values()`.
- `WorkspaceReponse` still misspelled. So are `doesnt` and `recieved`.
- Stuttering names: `Workspace.workspace_id` → `Workspace.id`.
- Still `response_model=` rather than a `-> WorkspaceResponse` return annotation.
- **Still no ruff, still no pytest.** Neither is installed. Ruff finds the dead `settings`, the
  unused import and `else :` in under a second — and it's the reason this section keeps repeating.

---

## The four decisions — where they stand

**1. Models per entity — improved, not done.** Request models exist now. Missing: the response model
is still the same class as the stored entity (which is what causes N1), and `DocumentPatch` still has
no optional fields. Target is Create / Patch(all optional) / Response(allowlist) / internal.

**2. `workspace_id` source — unchanged.** Path is right. Two endpoints scoped, two not, so the tenant
boundary is still optional in your URL design. Finding C is the symptom.

**3. Status transitions — unchanged.** Still validated nowhere, still client-writable, still a free
string. It's a domain rule with two callers (HTTP + worker), so it lives where both pass through —
not the route, not a field validator, not the repo.

**4. Error envelope — unchanged, now measured.** Two shapes confirmed by request. The trap: a
human-readable message with no machine code *becomes* your contract, because clients parse it.

---

## Do next, in order

1. **Repository = functions.** `create_workspace(name)`, `get_document(workspace_id, document_id)`,
   `list_documents(workspace_id, limit, offset)`. Domain args in, model instances out. Routes never
   see a dict, never see a `KeyError`. Put `workspace_id` in every document signature **even where
   today you don't need it** — then an unscoped read isn't something a handler can express. That
   kills A, B, C and N1 together, and is most of G.
2. `uv add --dev ruff pytest httpx`. Run ruff before reading the rest of this list.
3. `.env.example` committed, or a default on `debug` — pick one.
4. Fix or delete the timestamps. A field that lies is worse than a missing field.
5. 201 + `Location` on both creates.
6. Make `status` an enum, and decide whether clients may write it at all.

**Target by end of week:** delete both repository modules, write SQL-backed ones with identical
signatures, change nothing under `routes/`.

---

## Answer these

1. `POST /workspaces/{id}/documents` writes to two dicts. Process dies between them — describe the
   state, name the violated property, name the Postgres mechanism. Which layer should hold that
   boundary?
2. You have a document UUID from workspace A. `GET /documents/{id}` returns it. What's the smallest
   change to the **repository signature** — not the handler — that makes the insecure version
   impossible to write, and why is a signature stronger than an `if`?
3. `created_at` changes every time the row is read. Explain the exact mechanism — where the value is
   produced and why the repository never sees it. What does that tell you about the difference
   between a Pydantic model and a stored row?
4. Two identical workspace-name POSTs arrive simultaneously. Walk the interleaving where both
   succeed. With a unique index instead: what happens, what error does your code see, and why keep
   the application-level check anyway?
5. Your middleware sets `X-Request-ID` on the response. A handler five frames deep wants to log with
   it. Can it reach it today? What's the mechanism that would let it — and what changes at week 8
   when the "handler" is a worker in a different process?
