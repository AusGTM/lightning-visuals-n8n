---
phase: 44-sj-3-dispatch-gate-drain-cap
plan: 01
subsystem: crm-automation
tags: [n8n, hubspot, write-safety, sj3, dispatch-gate, drain]
status: complete

requires:
  - phase: 43-pipeline-scoring-hygiene-explainability
    provides: the v0.7 pipeline whose SJ-3 poller this plan gates, and the
      write-safety architecture (WRITE_SAFETY_GATE_JS, splice_write_gates,
      NODE_CREDENTIAL_MAP conventions) this plan extends
provides:
  - n8n/code/sj3DispatchGate.js -- pure injected-predicate router (sj3_dispatch /
    sj3_drain, mutually exclusive, fail-closed on non-boolean predicate results)
  - ALLOW_SJ3_DRAIN_WRITES in WRITE_SAFETY_DEFAULTS, defaulting "true" (D-05,
    operator-approved 2026-08-10) -- the first enabled-at-rest write authority, bound
    recorded as code comments in both the defaults dict and the drain gate node
  - the SJ-3 gate/drain cluster in wf_scheduled_maintenance_cloud.json --
    "SJ-3 Dispatch Gate" (embeds WRITE_SAFETY_GATE_JS verbatim per D-02, fans out) ->
    "SJ-3 Build Dispatch Event" (filters sj3_dispatch) -> Execute Workflow, and
    "SJ-3 Drain Gate" (reads only the new constant, exact-string) ->
    "SJ-3 Drain Clear Flag" (baked-literal patch: lv_enrichment_requested="false" +
    lv_enrichment_status="skipped")
  - NODE_CREDENTIAL_MAP entry for "SJ-3 Drain Clear Flag" (same commit as node creation)
  - domain in SJ-3's search properties_csv (BUG 24's class closed for the last lane)
  - _hs_update_set_property extra_properties parameter (existing call sites byte-unchanged)
  - amended write-gate coverage guarantee: DRAIN_EXEMPT_WRITE_NODES + four dedicated
    drain assertions in tests/test_write_gate_coverage.py
  - verify_live_write_safety.py dedicated drain-authority check (opposite polarity,
    both expectations, own report line) without entering any overlay/arm table
affects: [44-02 (cap expansion over the same gate), 44-03 (deploy + bounce + live proof)]

tech-stack:
  added: []
  patterns:
    - "enabled-at-rest write authority: default-true constant excluded from the overlay/arm
      system (third member of the ALLOW_JUDGE_ESCALATION / ALLOW_WEB_RESEARCH shape)"
    - "coverage-guarantee exemption with strictly-stronger replacement assertions
      (sole-feeder + negative-grep + key+value patch allowlist)"

key-files:
  created:
    - n8n/code/sj3DispatchGate.js
    - tests/n8n/sj3DispatchGate.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - scripts/verify_live_write_safety.py
    - n8n/wf_scheduled_maintenance_cloud.json (regenerated)
    - n8n/wf_enrichment_cloud.json (regenerated)
    - n8n/wf_contact_ingest_cloud.json (regenerated)
    - n8n/wf_review_decision_cloud.json (regenerated — see Deviations)
    - tests/n8n/sjPredicates.test.mjs
    - tests/test_write_gate_coverage.py
    - tests/test_verify_live_write_safety.py
    - tests/test_bug10_company_search_transport.py
    - operator-claude-plugin/tests/test_control_flag_parity.py

decisions:
  - "checkpoint:decision resolved APPROVE by operator (2026-08-10, orchestrating
    session): ALLOW_SJ3_DRAIN_WRITES defaults true; bound written into code, not only
    planning docs; approve-with-status-guard option removed pre-execution as vacuous"
  - "drain gate constant literal derives from WRITE_SAFETY_DEFAULTS via
    _write_safety_const, so test_committed_write_safety_constants_are_all_disabled pins
    it like every other write-safety constant"
  - "drain gate documents its D-06 exclusions in words without naming the excluded
    identifiers -- the coverage tests negative-grep the node's entire jsCode and a Code
    node's comments are part of its jsCode"

metrics:
  duration: ~35 min
  completed: 2026-08-10

estimate:
  tokens: 90000
  tasks: 3
actuals:
  tokens: 111191   # chars/4 over the realized diff (inflated by nid() shifts across regenerated JSON)
  tasks: 3
  commits: 3
---

# Phase 44 Plan 01: SJ-3 Dispatch Gate + Drain Summary

SJ-3's poller now filters dispatch through the shared write-safety predicate per record and
drains declined rows via a structurally two-literal HubSpot write under the system's first
enabled-at-rest authority (`ALLOW_SJ3_DRAIN_WRITES`), proven end-to-end offline with both
suites green and nothing deployed.

## Tasks

| Task | Name | Commit | Result |
| ---- | ---- | ------ | ------ |
| — | Checkpoint: approve D-05 default-true drain authority | (no commit) | Resolved **approve** by operator in orchestrating session, 2026-08-10 |
| 1 | Tracer: gate + drain end-to-end, one path each | `8167be7` | Pure module + builder + JSON + credential map + tests; tracer verify re-run green before expansion |
| 2 | Amend write-gate coverage guarantee deliberately | `9b56008` | Exemption by name with the inversion recorded; 4 strictly stronger replacement assertions |
| 3 | Teach live verifier the constant without arming it | `8fb64a4` | Dedicated opposite-polarity check; overlay/arm tables untouched; comment names the third default-true exclusion |

## What was built

- **`n8n/code/sj3DispatchGate.js`** — `sj3Gate(rows, opts)` with injected `opts.allows`;
  annotates every row `sj3_dispatch`/`sj3_drain` (mutually exclusive, input order, payload
  untouched); fails closed on missing predicate or non-`true` predicate results.
- **Builder** — `ALLOW_SJ3_DRAIN_WRITES: "true"` in `WRITE_SAFETY_DEFAULTS` with the D-05
  bound as a comment; `domain` added to SJ-3's search (BUG 24's class); `SJ-3 Dispatch
  Gate` embeds `WRITE_SAFETY_GATE_JS` verbatim (D-02) + the inlined module + an `allows`
  closure delegating to `_writeSafetyAllows("enrich", hs_object_id, domain)`;
  `ENRICH_SJ3_BUILD_DISPATCH_EVENT` filters `sj3_dispatch === true` ahead of its map
  (zero permitted rows → `[]` → Execute Workflow receives zero items, tick costs 1 not
  1+N — Plan 03 verifies that empirically); `SJ-3 Drain Gate` reads only the new constant
  (exact-string, not through `splice_write_gates` — RESEARCH Pitfall 2); `SJ-3 Drain
  Clear Flag` via the extended `_hs_update_set_property` with both keys and both values
  as baked literals.
- **Coverage guarantee** — the generic `_writeSafetyAllows` walk would have passed the
  drain node *for the wrong reason* (the string one hop upstream is evidence of the
  opposite: the drain runs on rows that helper declined). `DRAIN_EXEMPT_WRITE_NODES`
  records the inversion; replacements: sole-feeder is the drain gate; drain gate's jsCode
  has the exact-string comparison and names neither the shared helper nor any allowlist
  constant; the built patch is exactly the two (key, value) pairs (DRAIN-02 as amended
  2026-08-10 — key+value allowlist, deliberately not a key count, because the same write
  stamps the DRAIN-03 provenance); the exemption set itself is pinned to one entry.
- **Verifier** — `ALLOW_SJ3_DRAIN_WRITES` stays out of `_OVERLAY_FLAG_SPEC`,
  `OVERLAY_DISABLED_LITERALS`, and `CHECKED_CONSTANTS`; the deploy-script comment now
  names it as the third default-true exclusion with the same emergency-off path.
  `verify_live_write_safety.py` asserts it is present and reads `"true"` under both
  expectations, on its own `drain authority:` report line; missing/`"false"` fails.

## Deviations from Plan

**1. [Extra artifact] `n8n/wf_review_decision_cloud.json` also regenerated**
- **Found during:** Task 1 rebuild
- **Issue:** the plan's frontmatter lists three JSON artifacts, but `WRITE_SAFETY_GATE_JS`
  is embedded in `wf_review_decision_cloud.json`'s gates too, so the new constant lands
  there on rebuild (the plan's own action text says "regenerate all cloud workflow JSON").
- **Fix:** committed the fourth regenerated file rather than excluding it to match the
  frontmatter. Commit: `8167be7`.

**2. [Knock-on tests] two pinned expectations updated**
- **Found during:** Task 1 full-suite run
- **Issue:** `operator-claude-plugin/tests/test_control_flag_parity.py::test_maintenance_workflow_rewrite_counts`
  pins 4 declaring nodes (now 5 — the dispatch gate embeds the shared blob), and
  `tests/test_bug10_company_search_transport.py` pins SJ-3's exact `properties_csv`
  (now includes `domain`). Neither file is in the plan's `files_modified`.
- **Fix:** updated both expectations with comments citing this plan. Commit: `8167be7`.

**3. [Rule 3 - Blocking] `tests/test_write_gate_coverage.py` could not import the builder standalone**
- **Found during:** Task 2 verify (`pytest tests/test_write_gate_coverage.py -q` alone)
- **Issue:** pre-existing gap — `scripts/build_cloud_workflows.py` does
  `import gen_taxonomy_js` (sibling-script import), which resolves in full-suite runs
  only because an earlier-collected module puts `scripts/` on `sys.path`. The plan's
  verify command runs the file standalone.
- **Fix:** two-line `sys.path.insert` at module top with a comment. Commit: `9b56008`.

**4. [Verifier fixtures] `tests/test_verify_live_write_safety.py` `_node` helper extended**
- **Found during:** Task 3 (anticipated)
- **Issue:** hermetic fixtures declared only the five overlay constants; the new
  missing-means-fail drain check would have failed every fixture.
- **Fix:** `_node` now declares the drain constant at its rest value by default
  (`drain=None` to omit), plus six new drain-check tests. Commit: `8fb64a4`.

## Known accepted states (not defects)

- **Interim live-verifier FAIL window:** until Plan 03 deploys, the live n8n content does
  not declare `ALLOW_SJ3_DRAIN_WRITES`, so a live run of `verify_live_write_safety.py`
  will report the `drain authority` line as FAIL. This is the check working as specified
  (missing = drain inert); the plan accepts the window and Plan 03 closes it.
- **Arm-window residual (documented in the checkpoint context, accepted):** the
  maintenance workflow's baked constants stay disarmed during an armed enrichment window;
  a tick landing after the window closes can drain just-dispatched records whose runs then
  fail. Recovery is re-queue by SJ-1/SJ-2; closing it properly needs a real in-flight
  marker, outside this phase.

## Verification

- `node --test tests/n8n/*.test.mjs` — **648 pass** (636 baseline + 12 new), 0 fail.
- `.venv/bin/python -m pytest -q` — **2437 passed** (2427 baseline + 10 new), 121 skipped.
- `operator-claude-plugin` suite — **1286 passed**.
- `git diff --stat n8n/` at Task 1: regenerated JSON only, no hand edits.
- Nothing deployed; live n8n and HubSpot untouched.

## Threat register outcomes

| Threat | Disposition |
|--------|-------------|
| T-44-01 (EoP, default-true authority) | Mitigated — one reader node, not spliceable, patch pinned by key+value allowlist test |
| T-44-02 (Tampering, patch body) | Mitigated — baked literals; widening fails `test_drain_write_patch_is_exactly_the_two_pair_allowlist` |
| T-44-03 (EoP, authority bleed) | Mitigated — `_writeSafetyAllows` unmodified; no branch reads the new constant; negative-grep pins the reverse |
| T-44-04 (Repudiation) | Mitigated — `skipped` written by nothing else in the pipeline |
| T-44-05 (DoS, silently inert drain) | Mitigated — dedicated verifier line fails loudly on missing/false |
| T-44-06 (Spoofing, unbound credential) | Mitigated — `NODE_CREDENTIAL_MAP` entry in the same commit as the node |

## Commits

- `8167be7` feat(44-01): SJ-3 dispatch gate + drain — one record declined, one dispatched, end to end
- `9b56008` test(44-01): amend the write-gate coverage guarantee for the drain node — deliberately
- `8fb64a4` feat(44-01): teach the live write-safety verifier the drain constant without arming it

## Self-Check: PASSED

All created files present; all three commit hashes found in git log.
