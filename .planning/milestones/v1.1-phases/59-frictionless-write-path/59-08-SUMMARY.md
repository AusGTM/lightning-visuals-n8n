---
phase: 59-frictionless-write-path
plan: 08
subsystem: enrichment
tags: [written-records, concurrency, run-id, disclosure, d-59-09, d-59-07, plugin-release]
status: complete

requires:
  - phase: 59-frictionless-write-path (59-07)
    provides: "chunking.ChunkResult.resolvable and the GATE-02..GATE-05 resolvable payload wired through dispatch_plan"
provides:
  - "written_records.written_records_path(run_id) — one artifact filename per run, never shared"
  - "written_records.load() — globs written_records*.json and unions every run's entries, stamped with run_id"
  - "write_grant._consequence discloses the written-records artifact for every grant, one lane or two"
affects: [59-frictionless-write-path, enrichment-lane, scheduled_arm]

actuals:
  tokens: 10123
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Concurrency removed by construction, not discipline: two writers that formerly raced one shared path now resolve to two different paths (one per run_id), so there is nothing left to lock or merge."
    - "A reader-side glob (written_records*.json, not hyphen-anchored) is the cost of a writer-side per-key-file split — every consumer must union rather than open one fixed path, and the glob pattern must still match the pre-change filename so a legacy artifact is never silently dropped."

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/written_records.py
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/tests/test_written_records.py
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/README.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md

key-decisions:
  - "D-59-09 implemented as specified: one written_records-<run_id>.json per run, never a lock, never a merged index — both alternatives were operator-rejected and neither appears in the code (grep-verified: no flock/filelock/msvcrt string anywhere in written_records.py)."
  - "append_chunk's run-id-mismatch replace-not-merge branch is deleted outright, not weakened. Under per-run files it can never fire in production; the explicit path= test escape hatch now simply appends unconditionally to whatever document already exists there, and the one existing test asserting the old replace behavior was rewritten to assert the new append behavior instead."
  - "load()'s glob-vs-explicit-path split: load(path=...) stays byte-identical to its pre-change single-file behavior (no run_id stamp on entries); only the no-argument glob path stamps each entry with its own document's run_id, since that is the only case where two different runs' entries can land in one unioned list and need to stay distinguishable."
  - "write_grant._consequence's artifact disclosure moved out of the len(lane_names) > 1 branch entirely; only the genuinely multi-lane sentence ('this grant covers both lanes at once') stayed inside it. A new single-lane twin test pins the disclosure fires for a one-lane grant, and a negative assertion pins the multi-lane phrasing does NOT leak into a single-lane grant's text."
  - "SKILL.md/README wording uses the literal glob pattern written_records*.json in a few places but the *primary* pinned phrase across the skill-contract test is written_records-<run_id>.json without the asterisk — SKILL.md's own _normalized() test helper strips every '*' character (its bold-marker-removal rule), which would otherwise collapse 'written_records*.json' into the unreadable 'written_recordsjson' and make that specific substring an unusable pin."

open-questions: []
---

# Phase 59 Plan 08: Written-Records Concurrency + Universal Grant Disclosure Summary

One artifact per dispatch run instead of one shared file racing every writer, and the
post-run written-records disclosure now fires for a single-lane write grant exactly as
it already did for a two-lane one.

## What Was Built

**Task 1 — One artifact per `run_id`, and a reader that globs and unions
(`operator-claude-plugin/scripts/written_records.py`, `chunking.py`).**

- `written_records_path(run_id)` now takes the run id and returns
  `written_records-<run_id>.json` in the plugin's durable state directory, resolved
  fresh on every call exactly as before (never a module-level constant).
- `append_chunk`'s old run-id-mismatch "replace, don't merge" branch is deleted. Under
  per-run files, a document already on disk at the target path is always this run's own
  earlier chunks — there is no foreign document left to protect against — so it is
  appended to unconditionally.
- `load()` with no `path` argument now globs `written_records*.json` in the durable
  directory (deliberately NOT hyphen-anchored, so an artifact still sitting under the
  pre-change shared filename is not silently dropped), reads matches in sorted filename
  order, unions their entries, and stamps each returned entry with its own document's
  `run_id`. One unreadable or schema-mismatched file among several does not suppress the
  readable ones — same whole-document degradation the single-file path already had.
  `load(path=...)` is byte-identical to its pre-change behavior.
- An OS-level advisory file lock and a merged cross-run index were both considered and
  rejected, per D-59-09: no contention or stale-lock failure mode on a path that must
  never block a dispatch, and the index is a later addition only if operators ask for
  one combined view. Neither appears in the code — the module docstring states this in
  prose without naming the rejected mechanism by API identifier, per the task's own
  negative-grep gate (`flock|filelock|msvcrt` all return zero matches).
- **Lead test drives the integration path, not `append_chunk` alone**: two real,
  separately-`run_id`'d `chunking.dispatch_plan` calls, interleaved by hand against one
  shared monkeypatched durable directory (run A flushes, run B — a different run —
  flushes, run A flushes again), prove neither run's chunks are lost. A unit test of
  `append_chunk` in isolation would have repeated the exact mistake that let this gap
  ship.
- All three zero-argument `written_records_path` monkeypatches across the test suite
  (two in `test_written_records.py`, one in `test_write_grant.py`'s revoked-run test)
  were updated to accept the new `run_id` parameter.

**Task 2 — Every grant discloses the artifact; every operator-facing reader named the
per-run file (`write_grant.py`, `README.md`, `enrich-before-ingest/SKILL.md`).**

- `write_grant._consequence`'s artifact-disclosure sentence moved out of the
  `len(lane_names) > 1` branch so it fires for every grant, one lane or two. What
  remains inside that branch is only the genuinely multi-lane statement ("this grant
  covers both lanes at once").
- The disclosure now names the per-run artifact shape
  (`written_records-<run_id>.json`, matching `written_records*.json`) rather than the
  retired single fixed filename.
- `plan_grant` — refusal ordering, the empty-record-set refusal, every authorization
  check — is untouched. `git diff` on `write_grant.py` shows exactly two hunks: the new
  `import written_records` line and `_consequence` itself; nothing inside `plan_grant`.
  The structural test asserting no HubSpot search call exists in `write_grant.py` passes
  unmodified.
- A new single-lane disclosure test twins the existing two-lane test, and asserts the
  multi-lane-only phrase does not leak into single-lane text.
- `README.md`'s write-grants section and both `enrich-before-ingest/SKILL.md`
  paragraphs (the step-1 preamble and the step-5 at-the-yes disclosure) reworded to name
  the per-run filename shape, each with its own dated recorded-edit note citing D-59-09.
  The skill-contract test's pinned substring changed from the retired
  `written_records.json` to `written_records-<run_id>.json` (not the asterisked glob
  text — see key-decisions).

**Task 3 — Release 0.27.0 (`plugin.json`, `CHANGELOG.md`).**

- `plugin.json` bumped `0.26.0` -> `0.27.0`.
- A `CHANGELOG.md` entry covers both gap closures, citing D-59-09 and D-59-07 and
  naming the rejected lock/index alternatives so a changelog reader does not
  re-litigate them.
- All three tasks folded into one commit (`744e2ff`), carrying the plugin bump and the
  CHANGELOG entry alongside every code and test change, per the plan's explicit
  fold-into-one-commit instruction for this release.

## Verification

- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py operator-claude-plugin/tests/test_write_grant.py -q` — 138 passed.
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 1690 passed, 5 skipped (baseline 1682/5 + 8 net new tests).
- `.venv/bin/python -m pytest -q` (root suite) — 3297 passed, 154 skipped (baseline 3289/154 + 8).
- `node --test tests/n8n/*.test.mjs` — 776 pass, 0 fail (untouched by this plan, as expected).
- `grep -n 'def written_records_path'`, `grep -c 'written_records\*.json'`,
  `grep -rn 'written_records_path", lambda:'` (zero matches), `grep -c 'D-59-09'`,
  `grep -n 'RUN_ID_FIELD) == run_id'` (zero matches), and
  `grep -riE 'flock|filelock|msvcrt'` (zero matches) all confirmed against
  `written_records.py` per the plan's acceptance criteria.
- `git diff -- operator-claude-plugin/scripts/write_grant.py` shows exactly two hunks
  (the import line, `_consequence`); no hunk inside `plan_grant`.
- `git show --stat HEAD` confirms `plugin.json` and `CHANGELOG.md` landed in the same
  commit as `written_records.py`, `write_grant.py`, and every touched test file.

## Deviations from Plan

None — plan executed exactly as written. The one interpretive call, documented above
under key-decisions, was choosing `written_records-<run_id>.json` (no asterisk) as the
skill-contract test's pinned substring instead of the literal glob text
`written_records*.json`, because that test file's own `_normalized()` helper strips
every `*` character (its bold-marker-removal rule) and would otherwise turn the pin into
an unreadable, unintentional string match on `written_recordsjson`.

## Known Stubs

None.

## Threat Flags

None — this plan closes threats T-59-08-01 through T-59-08-05 named in its own threat
model (concurrent-writer tampering, per-run-file permission inheritance, a too-narrow
glob dropping a legacy artifact, grant persistence, and single-lane disclosure gaps),
introducing no new surface.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/written_records.py` — FOUND
- `operator-claude-plugin/scripts/chunking.py` — FOUND
- `operator-claude-plugin/scripts/write_grant.py` — FOUND
- `operator-claude-plugin/tests/test_written_records.py` — FOUND
- `operator-claude-plugin/tests/test_write_grant.py` — FOUND
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` — FOUND
- `operator-claude-plugin/README.md` — FOUND
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — FOUND
- `operator-claude-plugin/.claude-plugin/plugin.json` — FOUND
- `operator-claude-plugin/CHANGELOG.md` — FOUND
- Commit `744e2ff` — FOUND (`git log --oneline --all | grep 744e2ff`)
