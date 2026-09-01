---
phase: 60-review-lane-authority
reviewed: 2026-09-01T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/scripts/n8n_arming.py
  - operator-claude-plugin/scripts/review_decision.py
  - operator-claude-plugin/scripts/written_records.py
  - n8n/code/reviewDecision.js
  - operator-claude-plugin/tests/test_write_grant.py
  - operator-claude-plugin/tests/test_write_grant_guardrails.py
  - operator-claude-plugin/tests/test_write_grant_surface.py
  - operator-claude-plugin/tests/test_review_decision.py
  - operator-claude-plugin/tests/test_written_records.py
  - operator-claude-plugin/tests/test_control_arming.py
  - operator-claude-plugin/tests/test_chunking.py
  - operator-claude-plugin/tests/test_unattended_pair_composition.py
  - operator-claude-plugin/skills/review-triage/SKILL.md
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/README.md
  - operator-claude-plugin/USAGE.md
  - operator-claude-plugin/CHANGELOG.md
  - operator-claude-plugin/.claude-plugin/plugin.json
  - n8n/wf_review_decision_cloud.json
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 60: Code Review Report

**Reviewed:** 2026-09-01
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Phase 60 makes `"review"` a third grantable write lane alongside `enrichment`/`contacts`,
retires the `ALLOW_REVIEW_SUBMIT` environment gate in favour of grant-authorization, widens
Guardrail A to see a stuck-open review authorization, and gives a review-triage sitting a
single batch-scoped armed window. This is genuinely an authorization surface, and it is
treated like one: every fail path I traced (missing grant, closed grant, wrong lane, wrong
record, unreadable backend state, a raised exception mid-window, a failed disarm) refuses
rather than defaults open, the per-send scope check (`covers()`) is the single implementation
both `arm_for_dispatch`'s grant branch and every lane skill route through, and the two-engine
parity between `n8n/code/reviewDecision.js` and the committed `n8n/wf_review_decision_cloud.json`
holds — verified by running `test_review_outcome_parity.py` (7/7 passed) and the full node
suite (`node --test tests/n8n/*.test.mjs`, 848/848 passed), not just by inspection. The
`available`-gating in `written_records.append_chunk`'s call site inside `submit_decision` is
correct: a bookkeeping failure is caught and reported on a separate key, never allowed to
mask or block the write's own outcome (`test_append_chunk_raising_oserror_still_returns_the_writes_own_outcome`,
`test_append_chunk_raising_writtenrecordserror_also_returns_the_writes_own_outcome`).

One genuine correctness defect was found and reproduced live: `write_grant.envelope()` reuses
the local name `ceiling` for two different values, so the operator-facing GRANT-02 cost
disclosure — the text an operator reads immediately before authorizing live HubSpot writes —
renders a raw Python dict where a chunk-size number belongs. No test pins the rendered text,
so the suite stays green with the bug present. Three further findings cover a misleading
operator-facing sentence on a review-inclusive multi-lane grant, a stale README claim that
contradicts already-shipped Phase 57 behavior, and two stale/vacuous test assertions that no
longer verify what their names claim.

## Critical Issues

### CR-01: `write_grant.envelope()`'s chunk-size disclosure renders a dict, not a number

**File:** `operator-claude-plugin/scripts/write_grant.py:457-481, 568-573`
**Issue:** Inside `envelope()`, the local name `ceiling` is used for two unrelated values in
sequence:

```python
ceiling = None
...
ceiling = chunking.chunk_ceiling(config)          # line 462 — an int, the per-chunk record cap
chunk_count = chunking.plan_chunks(..., ceiling).chunk_count
executions = chunk_count + record_count
...
ceiling = ceiling_verdict({"projected_executions": executions}, headroom)   # line 481 — a dict
...
figures["chunk_ceiling"] = ceiling                # line 494 — now the VERDICT DICT, not the int
```

`_envelope_block` then renders `figures['chunk_ceiling']` directly into the operator-facing
GRANT-02 disclosure (`write_grant.py:568-573`):

```python
lines.append(
    f"n8n executions: **{executions} (projected, not measured)** — "
    f"{figures['executions_projection_basis']}, at {figures['chunk_count']} "
    f"chunk(s) of at most {figures['chunk_ceiling']} record(s).")
```

Reproduced live against the shipped code:

```
n8n executions: **5 (projected, not measured)** — 1 webhook execution per chunk + 1
sub-execution per record ..., at 2 chunk(s) of at most {'verdict': 'unknown',
'projected_executions': 5, 'allowance': None, 'spent_sampled': None, 'remaining_sampled':
None, 'shortfall': None, 'basis': '...', 'reason': 'x'} record(s).
```

Per this file's own docstrings, GRANT-02 is explicitly "the arithmetic an operator reads
BEFORE the yes" for a call that authorizes live HubSpot writes. This block is read verbatim
by `plan_grant`'s proposal and by every skill that walks the operator through opening a
grant (`enrich-records/SKILL.md`, `enrich-before-ingest/SKILL.md`, `review-triage/SKILL.md`).
No test in `test_write_grant.py`/`test_write_grant_guardrails.py`/`test_write_grant_surface.py`
asserts on the rendered "chunk(s) of at most N record(s)" text or reads
`figures["chunk_ceiling"]` as a number, so the full suite (485 tests) passes with the bug
present.

**Fix:** Rename one of the two bindings so `chunk_ceiling` in `figures` keeps carrying the
per-chunk record cap (an int) and the sampled-allowance verdict gets its own name, e.g.:

```python
try:
    chunk_record_ceiling = chunking.chunk_ceiling(config)
    chunk_count = chunking.plan_chunks(
        {"record_ids": ids + domains, "object_type": object_type},
        chunk_record_ceiling).chunk_count
    executions = chunk_count + record_count
except chunking.ChunkPlanError:
    executions_basis = UNCONFIGURED

...
execution_ceiling = ceiling_verdict({"projected_executions": executions}, headroom)

figures = {
    ...
    "chunk_ceiling": chunk_record_ceiling,   # unchanged meaning: the per-chunk record cap
    ...
    "ceiling": execution_ceiling,            # unchanged meaning: the sampled monthly verdict
    ...
}
```

Add a regression test asserting `_envelope_block(...)` renders the numeric per-chunk ceiling
(e.g. `"of at most 2 record(s)"`), not a dict repr, so this cannot silently regress again.

## Warnings

### WR-01: Multi-lane grant summary sentence names "enrichment" even when the grant does not include it

**File:** `operator-claude-plugin/scripts/write_grant.py:625-652` (`_consequence`)
**Issue:** For any grant spanning more than one lane, `_consequence()` appends a fixed
sentence regardless of which lanes were actually named:

```python
if len(lane_names) > 1:
    ...
    sentence += (
        f" This grant covers all {len(lane_names)} lanes at once: it enables "
        f"enrichment and writes to HubSpot.")
```

`LANES` now has three entries (`enrichment`, `contacts`, `review` — Phase 60, D-60-02), and a
grant can legally be opened over any combination, e.g. `lanes=["review", "contacts"]` or
`lanes=["review", "enrichment"]`. For either of those, the summary sentence claims the grant
"enables enrichment," which is false when the enrichment lane was never named, and is
misleading for a review-only-inclusive grant (a review decision adjudicates a held
candidate; it does not "enrich"). The per-lane sentences immediately above (`per_lane`) are
accurate and correctly individualized — this is the secondary summary clause, but it is still
operator-facing text on a live-write authorization surface, and no test exercises a
lane combination that excludes `"enrichment"` (`test_a_two_lane_grant_names_both_lanes_...`
only drives `lanes=("enrichment", "contacts")`).

**Fix:** Derive the verb phrase from `lane_names` instead of hardcoding it, e.g.:

```python
verbs = []
if "enrichment" in lane_names or "contacts" in lane_names:
    verbs.append("enrichment")
if "review" in lane_names:
    verbs.append("review decisions")
sentence += (
    f" This grant covers all {len(lane_names)} lanes at once: it enables "
    f"{' and '.join(verbs)} and writes to HubSpot.")
```
Add a test driving `lanes=("review", "contacts")` (no `"enrichment"`) asserting the word
`"enrichment"` does not appear in the consequence text, or that the sentence otherwise
correctly names only the granted lanes.

### WR-02: README.md's "Write grants" section contradicts the shipped Phase 57 ceiling refusal

**File:** `operator-claude-plugin/README.md:392-396`
**Issue:**

```
- **The cost figure discloses; it does not prevent.** It is computed from the batch you
  named, so it cannot refuse anything that batch already implies, and the remaining
  monthly execution allowance is not yet checked before a run starts.
```

This describes the pre-Phase-57 behavior (`D-53-02`). Phase 57 (`D-57-01`, `RUN-05`) shipped
exactly the opposite for the execution-allowance figure: `write_grant.plan_grant` samples the
month-to-date remainder via `allowance_headroom`, computes `ceiling_verdict`, and — when the
verdict is `CEILING_OVER` and the operator has not explicitly overridden — refuses to open the
grant before anything is armed (`write_grant.py:1015-1058`, `_CEILING_CONSTRAINT`'s own text:
"a batch that would exceed it is refused, not merely disclosed"). This bullet is in the
required-reading scope and is read by an operator deciding whether to trust the disclosure;
telling them a shipped safety check does not exist understates what the system does and could
lead an operator to distrust or second-guess a refusal that fires correctly.
**Fix:** Update the bullet to describe the current behavior, e.g.: "The cost figure mostly
discloses, but the projected n8n-execution count is checked against the sampled remaining
monthly allowance before a grant opens — a batch that would exceed it is refused unless you
explicitly override with a reason. Every other figure (provider credits, Anthropic spend)
discloses only; it does not gate the open."

## Info

### IN-01: Stale test name asserts a fact that no longer describes the module's actual (intentionally changed) behavior

**File:** `operator-claude-plugin/tests/test_control_arming.py:394-398`
**Issue:** `test_review_writes_is_not_touched_by_a_dispatch_disarm` only asserts a static
constant fact:

```python
def test_review_writes_is_not_touched_by_a_dispatch_disarm():
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" not in n8n_arming.DISPATCH_FLAGS
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" in n8n_arming.OVERLAYABLE_FLAGS
```

But `n8n_arming.disarm()`'s own docstring (Phase 60, cross-AI review MEDIUM-2/LOW-5) now says
the opposite of what this test's name implies about an actual disarm call: "TARGETS AND
ALLOWLIST ARE BOTH DERIVED FROM WHAT THE FETCHED WORKFLOW ACTUALLY DECLARES... a workflow
whose gate also declares `ALLOW_HUBSPOT_REVIEW_WRITES` disarms that too... a deliberate
fail-safe, not an accident." So a real `disarm()` call against the enrichment/contacts
workflow today DOES clear a co-declared review flag if one is present — which is the
documented, intentional Phase 60 design. The test's assertions are still true and the design
choice is legitimate and tested elsewhere (`test_disarm_rewrites_a_node_declaring_only_the_review_constant`),
but this test's name promises a property about `disarm()`'s runtime behavior that the module
no longer has, which will mislead a future reader who trusts the name over the body.
**Fix:** Rename to something like `test_dispatch_flags_tuple_never_includes_the_review_constant`,
or add a comment pointing at the `disarm()` docstring so the apparent contradiction with the
name is not left for a future reader to puzzle out.

### IN-02: A now-vacuous negative assertion in `test_write_grant.py`

**File:** `operator-claude-plugin/tests/test_write_grant.py:2139-2151`
**Issue:** `test_a_single_lane_grant_also_discloses_the_written_records_artifact` includes:

```python
# The genuinely multi-lane phrasing must NOT leak into a single-lane grant's text.
assert "covers both lanes at once" not in consequence
```

Per `_consequence`'s current wording (`write_grant.py:648-651`), the multi-lane phrase is now
`"covers all {N} lanes at once"` — the literal substring `"covers both lanes at once"` has not
been producible since the D-60-02 wording change (it used to read "covers both lanes"). This
assertion can never fail regardless of whether the multi-lane phrasing correctly stays out of
a single-lane grant's text, so it no longer verifies the property its comment claims to check.
**Fix:** Update the negative assertion to match the current wording, e.g.
`assert "covers all" not in consequence` and/or `assert "lanes at once" not in consequence`.

### IN-03: Same constant name (`WRITE_ENABLING_FLAGS`) reused across two modules for different purposes

**File:** `operator-claude-plugin/scripts/n8n_arming.py:54-56`,
`operator-claude-plugin/scripts/write_grant.py:1647-1648`
**Issue:** Two independent module-level constants share the exact name `WRITE_ENABLING_FLAGS`:
`n8n_arming.WRITE_ENABLING_FLAGS` (a `frozenset` of the three write-enabling flags, used by
`test_control_flag_parity.py` to check parity against the deploy script) and
`write_grant.WRITE_ENABLING_FLAGS` (a `tuple`, whose *order* is explicitly load-bearing per
its own comment: "Order here is load-bearing" for `_live_write_faults`'s presentation order).
Both are correct in their own module and are each independently tested, so this is not a
functional bug today, but a reader editing one in isolation (e.g. adding a fourth flag to
`n8n_arming`'s frozenset) could reasonably assume it also updates `write_grant`'s ordered
tuple, since nothing marks the two as unrelated beyond the type difference.
**Fix:** Rename one of the two — e.g. `write_grant.WRITE_ENABLING_FLAGS` to
`GUARDRAIL_A_LIVE_FLAGS` — or add a one-line comment at each definition site cross-referencing
the other and stating explicitly that they are unrelated constants that happen to share a name.

---

_Reviewed: 2026-09-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
