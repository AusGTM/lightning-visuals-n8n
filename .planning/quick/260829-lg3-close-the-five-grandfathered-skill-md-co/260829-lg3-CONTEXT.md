# Quick Task 260829-lg3: close the five grandfathered SKILL.md composition sequences (P2) - Context

**Gathered:** 2026-08-29
**Status:** Ready for planning

<domain>
## Task Boundary

Close all five entries in `GRANDFATHERED_UNCOVERED` in
`operator-claude-plugin/tests/test_skill_sequence_coverage.py` by writing composition tests
that actually drive each entry's named undriven join, then moving each identity from
`GRANDFATHERED_UNCOVERED` to `COVERED` with the covering test's nodeid.

This is P2 of `.planning/HANDOVER-2026-08-29-backlog.md`. The guard is a ratchet, not a clean
bill of health: it passes today only because these five are grandfathered.

**Out of scope:** the P3 stub harness that RUNS each documented sequence (deliberately deferred
in the handover — this task writes targeted composition tests, not a general harness); the
`row_id` carried-alongside-rows refactor; any change to `skills/*/SKILL.md` files.

</domain>

<decisions>
## Implementation Decisions

### Test shape for entries #1 and #4
**One shared test, two COVERED entries.** Entries #1 (`contact-upload`) and #4
(`enrich-before-ingest`) carry an identical call tuple registered under two different skills, so
they are two distinct identities over one shared chain. A single honest test that drives
`authorize_send | authorize_ungranted_send -> armed_window -> dispatch.dispatch` end to end
satisfies both; both `COVERED` entries name that same nodeid.

Accepted risk, recorded rather than papered over: if the two skills' documented blocks later
diverge, one of the two entries could over-claim. The census test's set-equality assertion
catches a tuple change (it orphans the registry key), so the divergence surfaces as a failure
naming the changed skill — it does not go silent.

### Ratchet end state
**`MAX_GRANDFATHERED` decrements to 0.** The file documents the constant as shrink-only —
"MAX_GRANDFATHERED shrinks by one each time". With all five closed, the correct end state is
`0`, not a headroom-preserving `5`. Any future grandfathered entry then requires a deliberate,
visible constant bump with a written reason.

### Claude's Discretion

- **Task grouping.** Three work units, matching the entries' shared shape:
  1. #1 + #4 — the authorize -> `armed_window` -> `dispatch.dispatch` chain (one test, two entries).
  2. #3 + #7 — the waterfall: `resolve_providers` -> `plan_chunks`/`chunk_ceiling` -> authorize
     -> `armed_window` -> `chunking.dispatch_plan`, plus `preingest.merge_enriched` for
     `enrich-before-ingest` only.
  3. #2 — `chunking.chunk_ceiling(cfg, key='max_rows_per_match_request')`'s **real return**
     flowing into `chunking.plan_chunks` in a test that also drives
     `preingest.match_batch -> preingest.classify_matches`.
- **Honesty bar.** Each registry entry's reason names a *specific* undriven join. The covering
  test must drive exactly that join with results flowing between the calls. Asserting SKILL.md
  wording is explicitly non-coverage by the file's own rule (see the #3 entry, which rules
  `test_step_5_flattens_dispatch_plans_responses_before_merging` out for this reason).
  A fixture may stand in for `config_gate.load_config` — the staleness guard
  (`test_every_covered_nodeid_resolves_to_a_real_test_mentioning_the_sequences_sink`) checks the
  sink call's bare function name only, by design.
- **No live calls.** Stub transports throughout. No live n8n execution, no HubSpot write, no
  provider credits. The autouse `no_durable_writes` fixture in `conftest.py` stays untouched and
  unbypassed.
- **`dispatch.dispatch` API.** Use the post-`bug_004` shape (`run_id` parameter, `written_records`
  recording). The recently added run_id-threading tests are the model.
- **Registry bookkeeping per closed entry, in the same commit as its test:** delete from
  `GRANDFATHERED_UNCOVERED`, add to `COVERED` with the nodeid, decrement `MAX_GRANDFATHERED`.
  Registries stay pairwise disjoint at every commit.

</decisions>

<specifics>
## Specific Ideas

Each gap is a join of two patterns that already exist — none requires new machinery:

- `test_write_grant.py::test_authorize_ungranted_send_arms_with_the_same_guardrails_a_standing_grant_gets`
  opens the armed window but its body is `pass` — it stops exactly one call short of
  `dispatch.dispatch`.
- `test_chunking.py::test_enrichment_and_contacts_writes_from_the_same_run_share_one_file`
  drives `plan_chunks -> dispatch_plan` with a stub transport, but with a literal `PROVIDERS`
  list and no authorization layer.
- `test_preingest_merge.py` covers `merge_enriched` from hand-built rows/responses.
- `test_chunking.py::test_chunk_ceiling_reads_the_match_key_and_it_is_larger_than_the_write_ceiling`
  tests the match-request ceiling key in isolation.

**Standing repo rules that bind this task:**
- Any commit touching `operator-claude-plugin/` bumps `.claude-plugin/plugin.json` **and** adds a
  `CHANGELOG.md` entry in the **same** commit (repo is at `0.28.3`).
- Test command: `.venv/bin/python -m pytest operator-claude-plugin/tests -q` (1721 passed /
  5 skipped baseline). Never bare `python -m pytest` — system python lacks the deps.
- Do not edit `skills/*/SKILL.md` in this task. The census is set-equality over live extraction;
  any edit that churns a call tuple orphans a registry key and fails the suite.

</specifics>

<canonical_refs>
## Canonical References

- `.planning/HANDOVER-2026-08-29-backlog.md` § P2 — the five entries and their priority ranking.
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — the guard, its three
  registries, and each entry's verbatim reason (the acceptance bar).
- `.planning/debug/knowledge-base.md`, last entry (`composition-boundary-blind-spot`) — why
  green suites are not evidence a documented sequence executes.
- `.planning/quick/260829-hjm-skill-sequence-composition-guard/` — the task that shipped the guard.

</canonical_refs>
