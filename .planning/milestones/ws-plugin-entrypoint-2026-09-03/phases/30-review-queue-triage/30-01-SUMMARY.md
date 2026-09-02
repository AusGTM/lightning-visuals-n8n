---
phase: 30-review-queue-triage
plan: 01
subsystem: n8n-backend
tags: [n8n, hubspot, write-safety, arming, review-writeback, separation-of-authority]

requires:
  - phase: 28
    plan: 01
    provides: "the arm/dispatch/disarm cycle over ALLOW_HUBSPOT_RECORD_WRITES that this flag must stay outside of (D-01/D-02)"
provides:
  - "ALLOW_HUBSPOT_REVIEW_WRITES — a fifth baked write-safety constant, overlayable and allowlist-guarded, declared in all 8 write-gate/Decide sites that carry ALLOW_HUBSPOT_RECORD_WRITES"
  - "_writeSafetyAllows(action=\"review\", …) — the review branch every future review write gate routes through"
  - "tests/n8n/reviewWriteFlagSeparation.test.mjs — executable proof that dispatch and review arming are independent"
affects: [30-02 (builds the review write gate that passes action \"review\"), 28 (its armed window now read-back-verified against the new flag)]

tech-stack:
  added: []
  patterns:
    - "a second arming authority is a BRANCH inside the shared gate function, never a second gate function — one function keeps every write node covered by construction"
    - "read-back verifiers and their fixtures derive the checked constant set from _OVERLAY_FLAG_SPEC / WRITE_SAFETY_DEFAULTS rather than re-typing names, so a flag added later cannot sit outside the disarmed guarantee"

key-files:
  created:
    - tests/n8n/reviewWriteFlagSeparation.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - scripts/verify_live_write_safety.py
    - tests/test_enabled_build_invariants.py
    - tests/test_write_gate_coverage.py
    - tests/test_verify_live_write_safety.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json

key-decisions:
  - "The review branch is an if/else inside _writeSafetyAllows, not a parallel check: `action === \"review\"` requires ALLOW_HUBSPOT_REVIEW_WRITES and never reads ALLOW_HUBSPOT_RECORD_WRITES; every other action takes the else branch, which is byte-identical to the previous body. Separation holds in BOTH directions with no behaviour change to dispatch."
  - "The shared allowlist requirement was deliberately left outside the branch — it applies to review exactly as to dispatch, so an armed review deploy is still bounded to named TEST_RECORD_* entries, and an EMPTY allowlist still denies everything while the deploy reports success. The new flag inherits that; it is correct and intentional."
  - "No node list was hardcoded anywhere. The constant is emitted by the existing WRITE_SAFETY_GATE_JS join, so it landed in exactly the 8 sites that already declare ALLOW_HUBSPOT_RECORD_WRITES — verified by count, not by enumeration."
  - "scripts/verify_live_write_safety.py's checked booleans were switched from two hardcoded names to a derived BOOLEAN_CONSTANTS set (deviation, Rule 2 — see below). Without it a live artifact with review writeback armed would have reported `disarmed PASS`."
  - "STATE.md, ROADMAP.md and REQUIREMENTS.md were NOT touched, by explicit dispatch instruction (an operator holds STATE.md uncommitted mid-23-06, and a gsd-planner was concurrently rewriting 30-02/04/05/06 and 30-CONTEXT). REVIEW-03 is a six-plan chain and is not complete at 30-01 anyway."

metrics:
  duration: ~35 min
  completed: 2026-07-31
status: complete
---

# Phase 30 Plan 01: Review-Write Arming Separation Summary

Review writeback now has its own baked backend authority, `ALLOW_HUBSPOT_REVIEW_WRITES`, wired
through the one `_writeSafetyAllows` branch every cloud write gate already inlines — so "review is
armed separately from dispatch" is a property of the deployed artifact and a passing test, not a
client-side boolean.

## What was built

**Task 1 — the constant and its gate branch** (`057621d`)

`WRITE_SAFETY_DEFAULTS` gained `"ALLOW_HUBSPOT_REVIEW_WRITES": "false"`, so `_write_safety_const()`
emits `const ALLOW_HUBSPOT_REVIEW_WRITES = "false";` — a JSON **string** literal, matching the
`'"false"'` disabled literal registered in `_OVERLAY_FLAG_SPEC`. `_writeSafetyAllows` became:

```js
if (action === "review") {
  if (String(ALLOW_HUBSPOT_REVIEW_WRITES).toLowerCase() !== "true") return false;
} else {
  if (String(ALLOW_HUBSPOT_RECORD_WRITES).toLowerCase() !== "true") return false;
  if (action === "create" && String(ALLOW_HUBSPOT_CREATE).toLowerCase() !== "true") return false;
}
```

The shared allowlist check below it is untouched and still applies to every action.

Deploy side: `_OVERLAY_FLAG_SPEC` gained `('"false"', '"true"', False)` and `_WRITE_ENABLING_FLAGS`
gained the name, so `_requested_overlay_flags()` refuses `ENABLE_BAKED_FLAGS=ALLOW_HUBSPOT_REVIEW_WRITES`
unless the same invocation supplies a `TEST_RECORD_IDS=` / `TEST_RECORD_DOMAINS=` value.

**Task 2 — the pin moved once, on purpose** (`59b859b`)

`test_overlayable_flags_is_a_strict_subset_of_config_flag_defaults` now asserts five names, with an
8-line comment above it recording why (D-02/D-08e, and why Phase 23 D-16a's reuse trick does not
apply here). The negative "never overlayable" set is unchanged; the per-flag disabled-literal parity
loop picked up the fifth flag automatically because it is a `WRITE_SAFETY_DEFAULTS` member.

**Task 3 — the separation is executable** (`11ebfe0`)

`tests/n8n/reviewWriteFlagSeparation.test.mjs`, 4 cases, all reading jsCode out of the committed
`n8n/wf_contact_ingest_cloud.json` (`HubSpot Create Write Gate`) and arming by the exact literal swap
`enable_baked_flags()` performs, with an assertion that the swap actually matched:

| Case | Result |
|---|---|
| committed/disarmed | create row dropped (0 items out) |
| ONLY `ALLOW_HUBSPOT_REVIEW_WRITES` armed **+ matching allowlist** | still dropped |
| dispatch constants armed + matching allowlist | row passes (1 item, `action: "create"`) |
| dispatch arming applied | `ALLOW_HUBSPOT_REVIEW_WRITES` still reads `"false"` |

Case 2 carries the allowlist deliberately, so its drop cannot be blamed on the allowlist; case 3
proves the harness can pass a row at all.

## Where the constant landed (counted, never enumerated)

| Workflow | `ALLOW_HUBSPOT_RECORD_WRITES` | `ALLOW_HUBSPOT_REVIEW_WRITES` |
|---|---|---|
| `wf_contact_ingest_cloud.json` | 2 | 2 |
| `wf_enrichment_cloud.json` | 2 | 2 |
| `wf_scheduled_maintenance_cloud.json` | 4 | 4 |
| `wf_backend_status_cloud.json` | 0 | 0 (no write nodes) |

8 and 8. `ALLOW_HUBSPOT_CREATE` remains 9 — contact ingest's `Decide Action` bakes that one alone at
the build site (D-16a), which is why the two families are different subsets.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — missing critical functionality] `verify_live_write_safety.py` would have reported a review-armed live artifact as `disarmed PASS`**

- **Found during:** Task 1, via 7 failures in `tests/test_verify_live_write_safety.py` (a file the
  plan did not list).
- **Issue:** two things at once. (a) The test's synthetic `_node()` fixture hardcoded four constants
  while `CHECKED_CONSTANTS` is imported from `_OVERLAY_FLAG_SPEC` — so every node report became
  "missing constant". That was the visible breakage. (b) The real one underneath: `verify()` named
  `ALLOW_HUBSPOT_RECORD_WRITES` and `ALLOW_HUBSPOT_CREATE` explicitly in both expectation branches.
  A live artifact with `ALLOW_HUBSPOT_REVIEW_WRITES = "true"` would have passed the **disarmed**
  check, and a dispatch armed window carrying a stray armed review flag would have passed the
  **armed** check. That is exactly the false-success this read-back exists to prevent (threats
  T-30-01 / T-30-04), and it silently widens an armed window's blast radius.
- **Fix:** derived `BOOLEAN_CONSTANTS = CHECKED_CONSTANTS - ALLOWLIST_CONSTANTS`; disarmed now
  requires every boolean `"false"`, armed requires `ALLOW_HUBSPOT_RECORD_WRITES == "true"` and every
  other boolean `"false"`. `_print_report` prints all checked constants instead of four. Fixture
  builds its jsCode from a dict asserted equal to `CHECKED_CONSTANTS`. Two new tests added:
  `test_disarmed_fails_when_review_writeback_is_still_armed`,
  `test_armed_fails_when_review_writeback_is_also_enabled`.
- **Files modified:** `scripts/verify_live_write_safety.py`, `tests/test_verify_live_write_safety.py`
- **Commit:** `057621d`

**2. [Rule 2 — missing critical functionality] `tests/test_write_gate_coverage.py` hardcoded the four constant names**

- **Found during:** Task 1 pre-check.
- **Issue:** `test_every_cloud_workflow_with_a_write_declares_the_safety_constants` and
  `test_committed_write_safety_constants_are_all_disabled` both looped over a hardcoded 4-tuple.
  They would have kept passing, but the new constant would have sat **outside** the
  "committed artifacts stay disarmed" guarantee — this plan's own truth #3.
- **Fix:** both loops now iterate `WRITE_SAFETY_DEFAULTS`, with the safe literal computed as
  `json.dumps(json.dumps(value))[1:-1]` (the constant as it appears inside the serialized workflow).
  Verified non-vacuous: the regex finds 8 `ALLOW_HUBSPOT_REVIEW_WRITES` declarations across the three
  cloud workflows, all `\"false\"`.
- **Files modified:** `tests/test_write_gate_coverage.py`
- **Commit:** `057621d`

Both deviations touch files outside the plan's `files_modified`. Neither is a scope expansion: both
are the direct, in-scope consequence of adding a fifth constant to a set those files were tracking by
hand.

### Not deviations, but worth recording

- **The plan's cited line numbers, signatures and literals were all correct.** `:861`, `:873`, `:882`
  in the builder; the four-entry `(disabled_literal, default_enabled_literal, takes_value)` spec at
  `deploy_n8n_workflows.py:142-148`; the four-name pin at `test_enabled_build_invariants.py:216-220`
  with its parity loop at `:232-237` auto-covering the fifth. Nothing needed re-derivation.
- **No STATE.md / ROADMAP.md / REQUIREMENTS.md update was performed**, per dispatch instruction.
  The normal GSD state-advance steps were skipped deliberately, not forgotten.

## Verification

No network call of any kind. Nothing armed, deployed, or activated.

| Suite | Before | After |
|---|---|---|
| `.venv/bin/python -m pytest -q` | 1163 passed, 1 skipped | **1165 passed, 1 skipped** (+2: the new verifier tests) |
| `node --test tests/n8n/*.test.mjs` | 404 passed, 0 failed | **408 passed, 0 failed** (+4: the new separation test) |
| plugin `pytest -q` from `operator-claude-plugin/` | 400 passed | **400 passed** (untouched) |

Disarmed grep, run before staging and again after the final commit:

```
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json
n8n/wf_backend_status_cloud.json:0
n8n/wf_contact_ingest_cloud.json:0
n8n/wf_contact_ingest_local.json:0
n8n/wf_enrichment_cloud.json:0
n8n/wf_enrichment_local_live.json:0
n8n/wf_enrichment_local.json:0
n8n/wf_scheduled_maintenance_cloud.json:0
```

**One unreproduced node flake.** A single run reported `pass 407, fail 1` with no failure block in
the output and no identifiable failing test name. Re-run 5 times afterwards (3 standalone, 2 in the
same pytest-then-node compound sequence): 408/408 every time. Recorded here rather than absorbed
silently; if it recurs it is worth chasing, but it did not reproduce.

## What 30-02 needs to know

1. **Pass the literal string `"review"` as the action.** `splice_write_gates(nodes, conns, {"<Write
   Node Name>": "review"})` produces a gate whose `_writeSafetyAllows("review", …)` call hits the new
   branch. Do not add a second gate function; do not read the constant directly in a write node.
2. **Arming syntax:**
   `ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_REVIEW_WRITES,TEST_RECORD_IDS=<id>"`. The bare flag alone is
   **refused** — it is in `_WRITE_ENABLING_FLAGS`, so `_requested_overlay_flags()` raises without an
   allowlist entry in the same invocation. Multi-value allowlists use `|` as the separator (`,`
   already separates entries).
3. **An empty allowlist denies everything while the deploy reports success.** `_writeSafetyAllows`
   returns false when both `TEST_RECORD_IDS` and `TEST_RECORD_DOMAINS` are empty, *before* any
   per-record match. The review flag inherits this unchanged. A review gate armed with no allowlist
   will silently drop every row — that is correct, and 30-02's tests should assert it rather than
   treat it as a bug.
4. **The gate reads identity from the item, in this order:**
   `it.json.hs_object_id || it.json.existingRecord?.hs_object_id || null` for the id, and
   `it.json.identity_keys?.domain || it.json.domain || null` for the domain. A review row that
   carries neither will be dropped even when fully armed. Note the handoff's standing fact that
   **`Set Review` strips every identifying field** — if 30-02's review lane routes rows through that
   node, `hs_object_id` must be re-attached upstream of the gate or the allowlist can never match.
5. **The reverse-direction proof is yours.** `reviewWriteFlagSeparation.test.mjs` proves review
   arming grants nothing on the dispatch path. The mirror — a `review` row permitted with ONLY
   `ALLOW_HUBSPOT_REVIEW_WRITES` armed, and denied when only the dispatch constants are armed —
   needs the review write gate, which does not exist until 30-02. The test file's header says so.
6. **`scripts/verify_live_write_safety.py` now covers the new flag**, but still only inspects
   `LV Enrichment (Cloud template)`'s two `Decide*` nodes (the pre-existing defect the handoff
   records against 23-gaps). If 30-02's review write gate lives in
   `wf_scheduled_maintenance_cloud.json` — `Review Apply Update Write Gate` is already there — this
   verifier will **not** read it back. Plan the armed-window read-back accordingly.

## Self-Check: PASSED

- `tests/n8n/reviewWriteFlagSeparation.test.mjs` — FOUND
- `.planning/workstreams/plugin-entrypoint/phases/30-review-queue-triage/30-01-SUMMARY.md` — FOUND
- commits `057621d`, `59b859b`, `11ebfe0` — all FOUND in `git log`
- no file deletions in any of the three commits (`git diff --diff-filter=D HEAD~3 HEAD` empty)
