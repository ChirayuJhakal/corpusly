# Test isolation: dependency overrides keyed by the wrong thing

**Stage:** week 3, step 0 (test safety net before the Postgres port)
**Concept:** FastAPI `app.dependency_overrides`

## What broke

Tests shared one in-memory store, so data from one test was visible in the next. It took two attempts
to fix.

**Attempt 1:** the fixture returned a new `TestClient(app)` for each test. That doesn't isolate
anything. Every client wraps the same `app`, and the stores are module-level dicts in
`dependencies.py` created once at import time. A new client is a new caller talking to the same data.

**Attempt 2:** overrides keyed by **strings**:

    app.dependency_overrides = {
        'get_workspace_repository': lambda: ...,
        'get_document_repository': lambda: ...,
    }

## What happened

No error and no warning. The suite stayed green while state was still leaking between tests.

Two tests in a row creating a workspace with the same name:

| | Override key matches provider? | Second create |
|---|---|---|
| Before (string keys) | `False` | **409**: saw the first test's workspace |
| After (function keys) | `True` | 200, in both test orders |

The real suite hadn't caught it, because its two tests happened to use different workspace names
(`test_workpace` vs `test_workspace`, a typo), so the duplicate-name check never fired.

## Why

FastAPI looks up `dependency_overrides` by the **function object** passed to `Depends(...)`. A string
that happens to spell the function's name is never equal to the function. When there's no match,
FastAPI **silently falls back to the real provider**. So a wrong key fails without telling you: the
only symptom is the leak.

## Fix

Import the provider functions from `corpusly.dependencies` and use them as the keys. Create the stores
inside the fixture, before the `yield`: one store per test, shared by every request within that test.
Clear the overrides after the `yield`.

## Takeaways

- A new test client is not a new database. Isolation means swapping the **storage**, not the caller.
- Silent fallback is the dangerous failure mode. A test suite can only show isolation is working if it
  contains a test that would *fail* without it. Here that's the same-name pair.
- No prediction was written down before this ran. It was found by accident, not as a planned
  experiment.
