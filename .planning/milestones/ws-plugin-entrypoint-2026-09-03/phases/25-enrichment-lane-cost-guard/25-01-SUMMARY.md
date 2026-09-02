---
phase: 25-enrichment-lane-cost-guard
plan: 01
subsystem: admin-tooling
tags: [hubspot, lists-api, scope-probe, read-only, operator-gate, RB-1]

status: awaiting-operator
tasks_complete: 1
tasks_total: 3

requires:
  - phase: 16.1
    provides: "scripts/check_provider_credits.py — the live-only-admin-script convention this probe mirrors exactly (lives in scripts/, no test_ prefix, env-gated, never prints a secret, never raises on a refusal, unit-tested offline with mocked requests)"
provides:
  - "scripts/check_hubspot_list_scope.py — read-only HubSpot Lists scope probe (RB-1 Probe A's instrument)"
  - "tests/test_check_hubspot_list_scope.py — 29 offline tests, zero network"
affects:
  - "25-03 (backend list resolution) and 25-04 (client) — both blocked until the operator runs Probe A and settles Task 3"
  - "25-06, 25-07 — chained behind 25-03/04"

tech-stack:
  added: []
  patterns:
    - "status-only scope classification: a 404 and a 403 are DIFFERENT answers to the same question, each a separate named branch with its own test"
    - "a live script never calls load_dotenv() itself — the documented wrapper owns that, asserted against the AST so the wrapper command quoted in the docstring does not read as a call"

key-files:
  created:
    - scripts/check_hubspot_list_scope.py
    - tests/test_check_hubspot_list_scope.py
  modified: []

key-decisions:
  - "404 means GRANTED, not 'not found'. The request was authorized; only the name missed. This makes a deliberately nonsense list name a fully valid input, which is what lets the operator run Probe A without first hunting for a real company list."
  - "Exit code separates 'answered' from 'undetermined', not 'good' from 'bad': granted and denied both exit 0 because both settle the question; 401 / 5xx / timeout exit 2 because they do not."
  - "No portal pin. The plan's Task 1 does not call for one and the token itself determines the portal, so HUBSPOT_EXPECTED_PORTAL_ID was deliberately not wired in — it would add a second required env var to a one-shot read-only probe for no added signal. Noted rather than silently skipped."
  - "25-BLOCKERS.md was deliberately NOT stubbed. Its three sections are Task 2/3 deliverables carrying live-probed values; an empty file with the right headers is exactly the shape that reads as a recorded answer when none exists (the D-20/D-23 failure mode)."

metrics:
  duration: ~25 min
  completed: 2026-07-31
  tests_added: 29
---

# Phase 25 Plan 01: Enrichment Lane Lists-Scope Probe — Summary (PARTIAL)

Task 1 built and committed: a read-only HubSpot Lists scope probe that settles, in one call,
whether this portal's private-app token carries `crm.lists.read`. **Tasks 2 and 3 are operator
checkpoints and were not attempted** — this plan is not complete.

## Status

| Task | Type | State |
|------|------|-------|
| 1 — lists-scope probe | `tracer` / `tdd` | ✅ **Done**, committed `e05346d` (RED) + `103b4ae` (GREEN) |
| 2 — run both live probes | `checkpoint:human-verify` (`gate="blocking"`) | ⏸ **Awaiting operator** — RB-1. Not run; no live HubSpot or n8n call was made by this executor |
| 3 — decide view handling | `checkpoint:decision` (`gate="blocking"`) | ⏸ **Awaiting operator** — a scoping decision only the operator can make |

**This plan still blocks 25-03, 25-04, 25-06 and 25-07.** Task 1 removes the only thing standing
between the operator and RB-1; it does not release the gate.

## What was built

`scripts/check_hubspot_list_scope.py` — a read-only CLI taking a list name and an optional object
type id (default `0-2` = companies).

**The core subtlety, made explicit and tested:** the probe reads the *status code*, not the body.

| Status | Verdict | Why |
|--------|---------|-----|
| 200 | `granted` (+ list id) | The list resolved |
| **404** | **`granted`** (no list id) | The request was **authorized**; only the name failed to match |
| **403** | **`denied`** | HubSpot refused the request itself — the scope is missing |
| 401 | `unauthenticated` | Distinct from both. A bad token is not evidence about scope either way |
| other / timeout / transport failure | `inconclusive` | Never raises |

Because a 404 answers the question just as well as a 200, **a deliberately nonsense list name is a
valid input** — the operator does not need to find a real company list first. The CLI's `--help`
epilog says so.

When the verdict is granted *and* a list id came back, one follow-up GET reports **only** the
member count and a paging-cursor boolean (T-25-06) — no record id, no property, no raw body.

Exit codes separate *answered* from *undetermined*: `0` for granted/denied (and for the
no-credentials skip), `2` for 401/5xx/timeout.

**Missing-token behaviour:** prints `skipped (no credentials)` plus an explicit second line stating
this is **not** a scope verdict and the question is still unanswered, then exits 0 with zero HTTP
calls. A test asserts the word `denied` never appears in that output, so a skip can never be
misread as a refusal.

**Scope honesty:** every run prints that this settles the **Lists API only** — HubSpot saved views
are a different concept with no public API, and nothing here says a view can be resolved. A test
asserts the phrase is present.

## The command the operator should run (paste into the runbook)

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/check_hubspot_list_scope.py', run_name='__main__')" "<the name of a real company list in the portal>"
```

If there is no company list to hand, run it against a nonsense name — the answer is just as good:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/check_hubspot_list_scope.py', run_name='__main__')" "no-such-list-20260731"
```

Contacts instead of companies: append `0-1` as a second argument.

**Record for 25-BLOCKERS.md `## Lists API scope`:** the printed `verdict=`, the printed `status=`,
the date probed, and — if granted with a list id — `member_count` and `has_paging_cursor`.

Reads `HUBSPOT_PRIVATE_APP_TOKEN` from the environment. The script does **not** call `load_dotenv()`
itself (AST-asserted), which is why the wrapper is mandatory — a bare `python scripts/...` from a
fresh shell prints the skip banner and answers nothing.

## Safety

- **Read-only throughout.** At most two GETs. No write, no arming, no deploy, no activation.
- **No live network call in verification.** All 29 tests replace `requests.get`/`post` with a raiser
  in an autouse fixture, so a test that forgets to mock fails loudly rather than reaching HubSpot.
- **Token containment (T-25-11):** read in exactly one place (`_auth_headers`), placed in a header
  and nowhere else. Tests assert it appears in no verdict value, no stdout, and not in the probed
  URL; a source scan asserts it is never interpolated into a `print()`; exception *text* is never
  printed, only the exception's type name.
- **`n8n/` untouched.** All 8 workflow JSONs verified still at **0** armed literals
  (`ALLOW_HUBSPOT_[A-Z_]* = "true"`), each file individually.
- `git diff` for this plan touches nothing under `n8n/` or `operator-claude-plugin/`.

## Verification

`.venv/bin/python -m pytest tests/test_check_hubspot_list_scope.py -q` → **29 passed**.

Acceptance criteria, all checked directly:

| Criterion | Result |
|-----------|--------|
| Task test file exits 0 | ✅ 29 passed |
| Non-comment `HUBSPOT_PRIVATE_APP_TOKEN` references ≥ 1 | ✅ 4 |
| `pytest --collect-only` collects nothing under `scripts/` | ✅ 0 |
| A test asserts 404 and 403 differ | ✅ `test_404_and_403_produce_different_verdicts` |
| A test asserts no verdict value equals the fake token | ✅ `test_no_verdict_value_equals_the_token_it_was_given` |

Cold run with the token unset was executed once and printed the skip banner, exit 0, zero requests.

## Test counts, with attribution

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| pytest | 1290 passed, 1 skipped | **1319 passed, 1 skipped** | **+29, all mine** |
| node (`--test` file form) | 474 pass, 0 fail | **474 pass, 0 fail** | unchanged — no JS touched |
| plugin | 490 passed | 490 passed | unchanged by me |

Baselines were measured in this session before any edit, and matched the handoff exactly. The known
1 ms `mergeContacts.test.mjs` timestamp flake did not fire this run; it remains unfixed and is not
mine.

**Concurrency note:** a sibling executor committed `7b3fdee test(28-02): ...` on top of my two
commits while I was verifying. It touches only `operator-claude-plugin/tests/test_control_probe.py`
(+399 lines) and will move the **plugin** suite count — that movement is theirs, not a regression.
My 490 plugin reading was taken before their commit landed.

## Deviations from Plan

**1. [Rule 1 — Bug] The `load_dotenv` assertion was written as a raw-text check and self-failed**

- **Found during:** Task 1 GREEN
- **Issue:** The test asserted the string `load_dotenv` appears nowhere in the script. But the
  module docstring must quote the wrapper command — which contains `load_dotenv()` — so the test
  failed against a correct script. A raw-text check cannot tell a documented command from a call.
- **Fix:** Rewrote it as an AST walk asserting no `Call` to `load_dotenv` and no `ImportFrom`
  importing it. Docstrings are not code, so the quoted wrapper is correctly ignored. The repo
  already uses this idiom in `operator-claude-plugin/tests/test_no_backend_imports.py`.
- **Files modified:** `tests/test_check_hubspot_list_scope.py`
- **Commit:** `103b4ae`

No other deviations. No package installs. Nothing auto-added beyond the plan.

## Not built, deliberately

- **`.planning/.../25-BLOCKERS.md`** — listed in the plan's `files_modified`, but all three of its
  sections (`## Lists API scope`, `## Chunk timing`, `## View resolution`) carry values that only
  Tasks 2 and 3 can produce. Creating it with empty headers would put a file on disk whose shape
  reads as a recorded answer while recording nothing — the precise failure D-20/D-23 exist to
  prevent. **The operator creates it as part of RB-1.**
- **A portal pin.** `HUBSPOT_EXPECTED_PORTAL_ID` is a repo convention, but Task 1 does not call for
  it and the token itself selects the portal. Wiring it would require the operator to export a
  second variable for a one-shot read-only probe with no added signal. Add it if this probe ever
  grows a write.
- **STATE.md, ROADMAP.md, REQUIREMENTS.md** were not touched. STATE.md is held uncommitted by an
  operator mid-23-06 and was explicitly out of bounds; INGEST-04 and PREVIEW-03 are **not** met by
  Task 1 alone, so marking them complete would be false.

## What the operator does next

1. Run the command above → record `## Lists API scope` in `25-BLOCKERS.md`.
2. Run Probe B's four timed POSTs (Task 2) → record `## Chunk timing`, including whether the
   full-waterfall fire was run.
3. Decide Task 3 (`refuse-and-redirect` / `discovery-spike` / `treat-view-as-list`) → record
   `## View resolution` naming 25-03 (backend) and 25-04 (client) as the implementing plans.

That releases 25-03, 25-04, and through them 25-06 and 25-07.

## Self-Check: PASSED

- `scripts/check_hubspot_list_scope.py` — FOUND
- `tests/test_check_hubspot_list_scope.py` — FOUND
- Commit `e05346d` — FOUND
- Commit `103b4ae` — FOUND
