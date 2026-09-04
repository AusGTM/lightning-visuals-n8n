---
phase: 59-frictionless-write-path
plan: 06
subsystem: operator-claude-plugin (enrichment + grant lanes) + planning artifacts
tags: [D-59-08, enrichment, write-grant, resolve-and-propose, gate-inventory]
dependency-graph:
  requires:
    - "59-05 (extraction.RESOLUTION_SOURCES, the closed vocabulary; 59-GATE-INVENTORY.md)"
  provides:
    - "resolution_sources.RESOLUTION_SOURCES (the closed vocabulary, now the single source both extraction.py and enrichment.py import)"
    - "enrichment.RecordSpecError.resolvable"
    - "write_grant.py's empty-record-set refusal naming a resolution path"
    - "enrich-records/SKILL.md's resolve-then-propose step"
    - "the closed-out 59-GATE-INVENTORY.md (GATE-02..GATE-06)"
  affects:
    - "Phase 60 (review lane) — out of scope for this plan, not touched"
tech-stack:
  added: []
  patterns:
    - "resolve-then-propose, never resolve-then-silently-fill — extended from enrichment.py's identity refusals to write_grant.py's empty-record-set refusal, still entirely in front of the authorization control"
    - "closed-vocabulary provenance validated at construction, shared via a small dependency-free module rather than duplicated (T-59-20/T-59-28 anti-laundering)"
key-files:
  created:
    - operator-claude-plugin/scripts/resolution_sources.py
  modified:
    - operator-claude-plugin/scripts/enrichment.py
    - operator-claude-plugin/scripts/extraction.py
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/tests/test_enrichment_envelope.py
    - operator-claude-plugin/tests/test_write_grant.py
    - .planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
decisions:
  - "RESOLUTION_SOURCES moved out of extraction.py into a new, dependency-free resolution_sources.py module rather than imported directly from extraction.py into enrichment.py — a live import test proved the direct import is a real circular import (enrichment -> extraction -> preview -> preview_enrichment -> chunking -> enrichment), exactly the fallback the plan anticipated. extraction.RESOLUTION_SOURCES is unchanged from every existing reader's perspective (same frozenset object, re-exported)."
  - "authorize_ungranted_send's empty-record-set refusal needed no separate edit — it already relays plan_grant's own refusal verbatim, so the resolution-naming sentence propagates to both paths automatically. Verified by a new test asserting both refusals share the same 'read-only' wording."
  - "The resolve-then-propose step was inserted as a new step 7 in enrich-records/SKILL.md, immediately before the existing dispatch step (renumbered 7->8, 8->9), rather than appended at the end, per the plan's instruction to place it where the flow actually reaches the grant."
metrics:
  duration: ~40min
  completed: 2026-08-29
status: complete
actuals:
  tokens: 9656
  tasks: 3
  commits: 3
---

# Phase 59 Plan 06: Frictionless write path — enrichment identity refusals + grant resolve-then-propose, gate inventory closed Summary

Converted the remaining D-59-08 CONVERT gates the inventory named for this plan
(GATE-02..GATE-06): the enrichment lane's people/companies identity refusals now carry a
machine-readable resolution payload, and the grant lane's empty-record-set dead end
(FINDING 1 of the Phase 53 walk) is resolvable through a proposed, operator-confirmed
read-only lookup performed entirely in the skill — `plan_grant` itself, and
`_writeSafetyAllows()`, are byte-for-byte unchanged. The gate inventory is now closed:
every `CONVERT` row across both 59-05 and 59-06 names its converting plan and task.

## What Was Built

**Task 1 — the enrichment lane's identity refusals name what would resolve them.**
- `enrichment.RecordSpecError` gains an optional keyword-only `resolvable` parameter
  (default `()`), mirroring `extraction.ExtractionError`'s `code`-alongside-`message`
  precedent: a tuple of `{"field", "sources", "detail"}` dicts, validated against the
  closed resolution vocabulary **at construction** — an unrecognised `sources` entry
  raises `ValueError` rather than being carried. Positional construction from a bare
  message keeps working; `ViewNotSupportedError`'s existing `super().__init__(VIEW_REFUSAL)`
  call is untouched.
- Populated at four sites: the people-branch identity gate (GATE-02, names `company`,
  `email`, `linkedin_url` each with their legitimate sources) and the three
  companies-branch no-name refusals (GATE-03/04/05). GATE-03 (a profile-page URL with no
  name) is the one site where `same_row_derivation` is offered — the page's own slug is
  a *proposable* name, never auto-filled — while GATE-04/05 (no website at all) name
  only `operator_statement`, since there is nothing on the row to derive from. Every
  existing refusal MESSAGE string is byte-for-byte unchanged, including the
  verbatim-pinned profile-page sentence (`enrichment.py:368-373`).
- **Deviation from the plan's literal wording, following its own fallback clause:**
  `RESOLUTION_SOURCES` was moved out of `extraction.py` into a new, dependency-free
  `resolution_sources.py` module rather than imported directly from `extraction.py` into
  `enrichment.py`. A live test proved the direct import is a real circular import —
  `enrichment -> extraction -> preview -> preview_enrichment -> chunking -> enrichment`
  (`chunking.py` imports `enrichment`, and `extraction.py` imports `preview`, which
  imports `preview_enrichment`, which imports `chunking`). `extraction.RESOLUTION_SOURCES`
  is unchanged from every existing reader's perspective — it is the same frozenset
  object, re-exported. This is exactly the fallback Planner Decision 3 in the plan
  specified for this case.
- 7 new tests in `test_enrichment_envelope.py`: the positional-construction/empty-tuple
  regression, an out-of-vocabulary source raising, the three resolvable payloads at each
  converted site, and a pin re-asserting every touched refusal's exact message string.

**Task 2 — the grant lane's empty record set stops being a dead end, control untouched.**
- `write_grant.plan_grant`'s empty-record-set refusal keeps its original explanation
  verbatim and adds a second sentence naming what would resolve it: a read-only HubSpot
  lookup for the record's own id, or for its company's domain — exactly how the walk
  resolved it by hand. A dated `D-59-08, 2026-08-28` comment states the refusal itself is
  deliberately unchanged and the resolution happens in the skill, before the call.
- `authorize_ungranted_send` needed **no separate edit** — it already relays
  `plan_grant`'s own refusal verbatim (confirmed by reading its source before editing),
  so the resolution-naming sentence reaches both paths automatically. A new test asserts
  both refusals carry `"read-only"`.
- `write_grant.py` gained no lookup, transport call, or resolution logic of any kind — a
  new structural test greps the module's live source (via `inspect.getsource`, not
  bytecode) for HubSpot-search markers (`hubapi.com`, `crm/v3/objects`, `/search`,
  `hubspot_search`, `HubSpot Company Search`, `hubspot_lookup(`) and fails if any future
  edit adds one.
- `enrich-records/SKILL.md` gains a new step 7 (existing steps 7/8 renumbered to 8/9,
  and the two internal "step 7" cross-references updated), placed immediately before the
  dispatch step where the flow actually reaches the grant: attempt resolution from the
  closed vocabulary only, name what remains forbidden (Claude's own recall, an inferred
  domain, a plausible email pattern), PROPOSE the resolved handle naming its source using
  the SAME confirm/correct/decline vocabulary the companies-domain table already
  established, and require operator confirmation before `plan_grant` is called — a
  declined proposal leaves the original refusal standing.

**Task 3 — inventory closed, plugin released.**
- `59-GATE-INVENTORY.md`'s owner column names the converting plan and task for GATE-02
  through GATE-06 (all `CONVERTED`, none reclassified to close the table), and the
  `Unplanned items` section now states the inventory is fully closed across both 59-05
  and 59-06. Difficulty-dismissal grep stays at 0.
- `plugin.json` `0.24.0` -> `0.25.0`; `CHANGELOG.md` entry names D-59-08's second half,
  states plainly (for the security reviewer) that `plan_grant` still hard-refuses an
  empty record set and `_writeSafetyAllows()` is untouched, and names the single shared
  resolution vocabulary this release extended rather than duplicated.

## Deviations from Plan

**1. [Planner Decision 3's own fallback, exercised] `RESOLUTION_SOURCES` moved to a new
`resolution_sources.py` module instead of being imported directly from `extraction.py`.**
- **Found during:** Task 1, before writing any enrichment.py code — checked for the
  cycle the plan flagged as a possibility, by temporarily patching a
  `from extraction import RESOLUTION_SOURCES` line into a copy of `enrichment.py` and
  running `python -c "import extraction; import enrichment"`.
- **Issue:** `ImportError: cannot import name 'RESOLUTION_SOURCES' from 'extraction'` —
  a real circular import, reproduced live, not merely theorized.
- **Fix:** Created `operator-claude-plugin/scripts/resolution_sources.py` holding the
  frozenset with no imports of its own; `extraction.py` now does
  `from resolution_sources import RESOLUTION_SOURCES` (re-export — `extraction.RESOLUTION_SOURCES`
  is the identical object every existing test and reader already depends on) and
  `enrichment.py` imports the same name from the same module.
- **Files modified:** `operator-claude-plugin/scripts/resolution_sources.py` (new),
  `operator-claude-plugin/scripts/extraction.py`, `operator-claude-plugin/scripts/enrichment.py`.
- **Commit:** `c8a43a3`.

No other deviations — the plan's own text anticipated this exact case and named the
fallback verbatim ("If importing `extraction` from `enrichment` creates a cycle, move the
constant into a small shared module and update both importers in this same commit — never
duplicate the literal"), so this is a plan-anticipated branch taken, not an unplanned
discovery.

## Known Stubs

None.

## Threat Flags

None beyond the plan's own `<threat_model>` register (T-59-26 through T-59-30, all
mitigated as designed):
- T-59-26 (a resolution widening a grant) — mitigated: `write_grant.py` gained no
  lookup or transport call, pinned by the new structural test.
- T-59-27 (a plausible-but-wrong domain resolving to the wrong company) — mitigated:
  legitimate sources are the closed vocabulary only; the skill states the illegitimate
  list explicitly and requires operator confirmation.
- T-59-28 (a Claude-resolved handle presented as operator-supplied) — mitigated: every
  `sources` value is validated against `RESOLUTION_SOURCES` at construction, an
  unrecognised source raises.
- T-59-29 (a pinned refusal message reworded) — mitigated: `RecordSpecError`'s
  verbatim-pinned message survives unchanged (grep-verified), `write_grant.py`'s
  original explanation sentence survives as a pinned prefix (new test).
- T-59-30 (inventory closed by reclassification) — mitigated: no `CONVERT` row was
  moved to `NOT-APPLICABLE`; difficulty-dismissal grep is 0.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/resolution_sources.py` — FOUND
- `.planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md` — FOUND, closed
- Commit `c8a43a3` (enrichment.py identity refusals) — FOUND in `git log --oneline`
- Commit `73d6484` (write_grant.py + SKILL.md resolve-then-propose) — FOUND in `git log --oneline`
- Commit `f27d2b2` (inventory closed, plugin 0.25.0) — FOUND in `git log --oneline`
- `operator-claude-plugin/tests -q`: 1678 passed, 5 skipped (was 1669/5 before this plan;
  +9 new tests across the two touched files)
- Root suite `-q`: 3285 passed, 154 skipped (was 3276/154 before this plan)
- `grep -cE "too (hard|difficult|complex)|not worth|low value" 59-GATE-INVENTORY.md`: 0
- `grep '"version"' plugin.json`: contains `0.25.0`
