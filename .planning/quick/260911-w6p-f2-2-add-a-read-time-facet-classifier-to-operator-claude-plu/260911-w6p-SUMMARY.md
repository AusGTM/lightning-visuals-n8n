---
phase: quick-260911-w6p
plan: 01
subsystem: operator-plugin
tags: [held-queue, confidence, no_match, facets, F2-2]

requires: ["260911-w6o"]
provides:
  - "held_queue.classify_facet(entry, known_company_domains=frozenset()) -- pure read-time facet over a no_match hold, returns new_person/needs_company/nothing_found/None"
  - "held_queue.record_verb(row_id, verb, run_id, path=None) / entry_verb / is_settled / open_entries -- durable create/skip/retry/drop verbs on a held entry"
  - "run_manifest.rows_to_resume's CONFIDENCE_HELD branch short-circuits on a settled/retry verb before the fingerprint comparison"
affects: [260911-w6q, 260911-w6r]

actuals:
  tokens: 8600
  tasks: 3
  commits: 3
  plan_head_before: 3dfbbb44

tech-stack:
  added: []
  patterns:
    - "Read-time facet over an existing durable-store entry, never persisted, never a new closed-vocabulary code -- classify_facet mirrors confidence.assess's total decision-table shape"
    - "Optional, closed-vocabulary status sub-object validated identically on save() and _validated_entries(), same pattern hold_code already used"

key-files:
  created:
    - operator-claude-plugin/tests/test_held_queue_facets.py
    - .planning/todos/pending/2026-09-11-held-queue-row-id-is-positional-not-a-stable-identity.md
  modified:
    - operator-claude-plugin/scripts/held_queue.py
    - operator-claude-plugin/scripts/run_manifest.py

key-decisions:
  - "classify_facet never consults the row's own company NAME -- known_company_domains (a caller-resolved set) is the only signal that a company already exists in HubSpot"
  - "known_company_domains defaults to an empty frozenset, so the default answer for any usable-email entry is needs_company (safe, review-first), never new_person by default"
  - "Freemail/ISP addresses (enrichment.FREEMAIL_DOMAINS) land in nothing_found, not a fourth facet -- conservative, not a claim the person can never be created"
  - "record_verb's run_id is the one passed in (not the queue's original run_id) -- documented as safe today because classify_read() has exactly one caller and passes no expected_run_id"
  - "rows_to_resume checks the verb BEFORE reading current_outcomes at all -- a settled row is done regardless of what a free match pass would now show"

requirements-completed: []

coverage:
  - id: T1
    description: "classify_facet reads new_person/needs_company/nothing_found/None from an entry plus resolved company domains, pinned against the four recorded a254d1e entries"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue_facets.py (13 tests, Task 1 section)"
        status: pass
    human_judgment: false
  - id: T2
    description: "record_verb/entry_verb/is_settled/open_entries -- durable status field, validated on both save() and load()"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue_facets.py (8 tests, Task 2 section)"
        status: pass
    human_judgment: false
  - id: T3
    description: "rows_to_resume excludes a settled row regardless of fingerprint, re-includes a retry row regardless of fingerprint, leaves the no-status path unchanged"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue_facets.py (5 tests, Task 3 section)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-09-11
status: complete
---

# Quick 260911-w6p: Read-time facet classifier + durable verbs on the held queue (F2-2) Summary

**Added `held_queue.classify_facet` (a pure read that splits a `no_match` hold into
`new_person`/`needs_company`/`nothing_found` from the entry plus caller-resolved
company domains) and durable `create`/`skip`/`retry`/`drop` verbs, then taught
`run_manifest.rows_to_resume` to honour a settled/retry verb before it ever compares
fingerprints -- so an operator's answer to a held row is never silently reopened by a
later resume.**

## Performance

- **Tasks:** 3/3 completed
- **Files modified:** 4 (2 created, 2 modified)
- **Commits:** 3 (`15349f77`, `af653e46`, `66de79b8`)

## Public signatures shipped (for 260911-w6q / 260911-w6r to reconcile against)

```python
# operator-claude-plugin/scripts/held_queue.py

FACET_NEW_PERSON = "new_person"
FACET_NEEDS_COMPANY = "needs_company"
FACET_NOTHING_FOUND = "nothing_found"
ALL_FACETS = frozenset({FACET_NEW_PERSON, FACET_NEEDS_COMPANY, FACET_NOTHING_FOUND})

def classify_facet(entry, known_company_domains=frozenset()):
    """Returns one of ALL_FACETS, or None when entry['hold_code'] is not
    confidence.HOLD_NO_MATCH. Pure -- no I/O, no clock. known_company_domains is
    an ARGUMENT the caller resolves (e.g. a HubSpot read); with the default empty
    set, every usable-email entry reads needs_company (the safe default) -- never
    new_person unless the caller actually supplies a matching domain."""

VERB_CREATE = "create"
VERB_SKIP = "skip"
VERB_RETRY = "retry"
VERB_DROP = "drop"
ALL_VERBS = frozenset({VERB_CREATE, VERB_SKIP, VERB_RETRY, VERB_DROP})
SETTLED_VERBS = frozenset({VERB_CREATE, VERB_SKIP, VERB_DROP})  # retry is NOT settled
STATUS_FIELD = "status"

def entry_verb(entry) -> str | None: ...          # tolerant of non-dict entry/status
def is_settled(entry) -> bool: ...                 # entry_verb(entry) in SETTLED_VERBS
def open_entries(entries: dict) -> dict: ...        # {row_id: entry} with settled ones dropped

def record_verb(row_id, verb, run_id, path=None) -> dict:
    """Loads, stamps entries[row_id]['status'] = {'verb', 'at' (UTC ISO), 'run_id'},
    saves, returns the updated {row_id: entry} map. Raises HeldQueueError (writing
    nothing) for: verb not in ALL_VERBS, row_id not in the loaded queue, or a
    run_id that trips the store's existing grant/secret-shaped-name refusal."""
```

**Status field shape on disk** (optional 5th key on an entry, alongside `hold_code`/
`reason`/`observed_signals`/`resume_fingerprint`/`row`):
```json
{"verb": "create", "at": "2026-09-11T04:12:00.123456+00:00", "run_id": "run-2"}
```
Absent means undecided (every entry saved before this plan, and every entry a caller
builds via `build_entry` today, has no `status` key at all). A present `status` whose
`verb` is outside `ALL_VERBS`, or that is not itself a dict, degrades the WHOLE queue
to `{}` on `load()` and to `held_queue.ANOMALOUS` on `classify_read()` -- the same
whole-queue-degrades-not-partial-trust rule `hold_code` already enforces.

`run_manifest.rows_to_resume`'s `CONFIDENCE_HELD` branch now reads
`held_queue.is_settled(entry)` and `held_queue.entry_verb(entry) ==
held_queue.VERB_RETRY` immediately after `entry = held_entries.get(row_id)`, before
`current_outcomes` is even consulted. A settled row appends `{"row_id", "verdict"}` to
`skipped` (the same two-key shape the `matched`/`enriched` branch already uses); a
retry row appends to `to_resume`. Neither reads the fingerprint. An entry with no
`status` falls through unchanged to the pre-existing fingerprint comparison.

## Task Commits

1. **Task 1: `classify_facet` -- one read-time facet for a `no_match` hold, pinned
   to the recorded entries** - `15349f77` (feat)
2. **Task 2: durable create/skip/retry/drop verbs on a held entry** - `af653e46` (feat)
3. **Task 3: a settled entry never comes back through a resume** - `66de79b8` (fix)

No separate plan-metadata commit -- per the orchestrator constraints for this
quick-batch leaf, STATE.md/ROADMAP.md updates and this SUMMARY's own commit belong to
the orchestrator, not this execution.

## TDD Gate Compliance

All three tasks carried `tdd="true"`. RED was observed for the whole test file against
the pre-plan source: with `held_queue.py` and `run_manifest.py` stashed back to their
`3dfbbb44` (pre-w6p) state, collecting `test_held_queue_facets.py` failed at import
time (`AttributeError: module 'held_queue' has no attribute 'VERB_CREATE'`, from the
Task 3 test block referencing verb constants that did not yet exist) -- confirming the
whole file fails against the unmodified module before any of these commits, then
passes after restoring the edits.

Each task was then built and verified incrementally against a progressively-smaller
slice of the final test file (Task-1-only content when committing Task 1, +Task-2
content when committing Task 2), with the intermediate `held_queue.py`/
`run_manifest.py` states re-run against `test_held_queue.py` (pre-existing suite) and
the in-progress `test_held_queue_facets.py` slice before each commit -- so each commit
is independently green, not just the final state. Final full-suite run after all three
commits: `operator-claude-plugin/tests/` 2986 passed, 5 skipped; root suite 4847
passed, 154 skipped; `node --test tests/n8n/*.test.mjs` 1101 passed, 0 failed (n8n/
diff empty throughout, as expected -- no n8n change in this plan).

## Deviations from Plan

None -- plan executed exactly as written. No architectural changes, no scope
expansion beyond the plan's stated three files (`held_queue.py`, `run_manifest.py`,
`test_held_queue_facets.py`) plus the one todo file.

## Known Stubs

None.

## Residuals (recorded per plan, not filed as a todo)

`run_report.py`'s backlog line (~line 997, `held_map = held_queue.load()` ->
"N backlog row(s) exist globally") is unchanged by this plan: a settled entry
(`create`/`skip`/`drop`) still counts into that N. `held_queue.open_entries()` is the
filter a fix would call, but changing the report needs a ruling nobody has given yet,
and CLAUDE.md §31 rule 1 says a residual with no test and no recorded hit is a
sentence, not a todo -- so this is that sentence, per the plan's own "Explicitly NOT
in this plan" instruction.

## Threat Flags

None -- the plan's own `<threat_model>` (T-w6p-01 through T-w6p-04, T-w6p-SC) already
covers this execution's surface: a closed four-word verb vocabulary validated on both
read and write sides, a `run_id` name-checked the same way an arming grant already is,
`classify_facet` reading only already-persisted allowlisted data with no new field
written to disk, and the positional-`row_id` collision filed as a design todo rather
than silently mitigated. No package install occurred.

## Pointers for the sibling quick items

- **For 260911-w6q (review-triage):** call `held_queue.classify_facet(entry,
  known_company_domains)` per `no_match` entry, resolving `known_company_domains`
  itself (a HubSpot read) -- passing no domains silently reads every usable-email
  entry as `needs_company`. Use `held_queue.open_entries()` to drop already-settled
  rows from the table, and `held_queue.record_verb()` to persist the operator's
  decision after a create/skip/retry/drop.
- **For 260911-w6r (the batch's ready answer):** the same `classify_facet` call
  applies; the run's own knowledge of which companies it already resolved this run is
  a valid source for `known_company_domains` (no live call needed if that knowledge is
  already in hand).
- **Both:** the positional-`row_id` collision (Barry Milton's `row-1`/`row-4` in the
  recorded run) means a verb recorded against one spreadsheet's `row-2` could read
  back against a different person's `row-2` in a later run's queue. Filed as
  `.planning/todos/pending/2026-09-11-held-queue-row-id-is-positional-not-a-stable-identity.md`
  (`kind: design`), not fixed here -- a ruling on the stable identity (email? email+
  company? a minted id?) and the disk-migration story is needed first.

## Self-Check: PASSED

- `git log --oneline --all | grep -q 15349f77` -> FOUND
- `git log --oneline --all | grep -q af653e46` -> FOUND
- `git log --oneline --all | grep -q 66de79b8` -> FOUND
- `operator-claude-plugin/scripts/held_queue.py` -> FOUND
- `operator-claude-plugin/scripts/run_manifest.py` -> FOUND
- `operator-claude-plugin/tests/test_held_queue_facets.py` -> FOUND
- `.planning/todos/pending/2026-09-11-held-queue-row-id-is-positional-not-a-stable-identity.md` -> FOUND
