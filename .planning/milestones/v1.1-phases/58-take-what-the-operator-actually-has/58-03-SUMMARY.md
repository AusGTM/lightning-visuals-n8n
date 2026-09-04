---
phase: 58-take-what-the-operator-actually-has
plan: 03
subsystem: operator-claude-plugin
tags: [company-lane, domain-confirm, consent-binding, vocab-05, non-clobber]

requires:
  - phase: 58-01-company-extraction-machinery
    provides: "_clean_domain, NOT_A_COMPANY_DOMAIN choke point in enrichment.py; the companies-form envelope shape"
  - phase: 58-02-propose-mode-observation-spike
    provides: "live-confirmed mode=propose survives to Decide Company Action and forces a non-writing proposed action"
provides:
  - "company_domain.py — a pure decision module (apply_domain_decisions, to_envelope_spec, DECLINE_DOMAIN, DomainDecisionError) that turns a batch of proposed domains into a decided set atomically, refusing to emit any row that was never decided"
  - "enrichment.py's companies form carries a per-event mode key for a propose intent, and three new named refusal paths for empty-handed company shapes"
  - "the confirm-table step, worded in the operator's register, in both enrich-records and enrich-before-ingest SKILL.md"
  - "live operator walk evidence: APPROVED, 2026-08-26, with one out-of-scope finding dispositioned by operator ruling"
affects: [58-04, 58-05]

actuals:
  tokens: 6815
  tasks: 4
  commits: 3

tech-stack:
  added: []
  patterns:
    - "validate-then-apply-atomically two-pass discipline (mirrors preingest.py's apply_match_decisions) reused for a second decision surface"
    - "one shared host-guard choke point (_clean_domain) imported, never re-implemented, enforced by a test that inspects module attributes rather than greps text"

key-files:
  created:
    - operator-claude-plugin/scripts/company_domain.py
    - operator-claude-plugin/tests/test_company_domain_confirm.py
  modified:
    - operator-claude-plugin/scripts/enrichment.py
    - operator-claude-plugin/tests/test_enrichment_envelope.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_enrich_skill_contract.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/tests/test_preingest_preview.py

key-decisions:
  - "Task 4 walk verdict (operator, 2026-08-26): APPROVED. Walked live via the released plugin 0.19.0 (marketplace commit 16b8641), dispatch disarmed throughout. No wording flagged — the operator reported understanding the table and the consequence of silence without being coached."
  - "Walk coverage gap disclosed honestly: the LinkedIn-company-URL input row and the reject-a-row move were not exercised in the live walk (the walk used two bare-name rows). Both moves carry automated test coverage from Tasks 1-3, not live-walk evidence — this is a residual, not a failure."
  - "Operator ruling on the walk's one out-of-scope finding (2026-08-26), two parts: (a) native-field promotion gap (industry/country/city/numberofemployees staying blank on companies this lane creates, live example Series Futsal Victoria 283816805830) folds into Phase 58 as a gap-closure plan, orchestrator-planned separately as 58-05 — NOT created by this plan; (b) CLAUDE.md §29's numberofemployees never-write ban is LIFTED for this lane specifically, scoped to fill_blank_only, provider-sourced values only."

patterns-established:
  - "A confirm-table checkpoint's acceptance bar is the operator's own account of understanding, recorded verbatim rather than paraphrased — the milestone's stated test is whether they had to be told what to type."

requirements-completed: [INPUT-03, INPUT-04]

coverage:
  - id: D1
    description: "A domain that was proposed but not decided on cannot reach a companies envelope event"
    requirement: "INPUT-03"
    verification:
      - kind: automated_test
        ref: "operator-claude-plugin/tests/test_company_domain_confirm.py::test_to_envelope_spec_raises_on_undecided_row (and sibling atomicity/guard tests)"
        status: pass
  - id: D2
    description: "A denied proposal leaves the row in the run with a blank domain, resolved by name, disclosed as such"
    requirement: "INPUT-04"
    verification:
      - kind: automated_test
        ref: "operator-claude-plugin/tests/test_company_domain_confirm.py (decline-survives-to-spec test)"
        status: pass
  - id: D3
    description: "The operator can answer the confirm table without being taught the system's vocabulary, and understands that silence means nothing is sent"
    requirement: "INPUT-03, INPUT-04"
    verification:
      - kind: manual_procedural
        ref: "Live walk, operator, 2026-08-26, plugin 0.19.0 (marketplace commit 16b8641), verdict APPROVED — verbatim evidence recorded in this SUMMARY's Task 4 section"
        status: pass
    human_judgment: true
    rationale: "A checkpoint:human-verify task whose acceptance bar is the operator's own comprehension cannot be automated — the milestone's own test is whether the operator had to be told what to type."
duration: ~15min (this session, resumed from Task 4 checkpoint)
completed: 2026-08-26
status: complete
---

# Phase 58 Plan 03: Confirm the Proposed Domain Summary

**A pure decision module turns a batch of proposed company domains into a decided set atomically — one shared host guard, no silent default, no dropped row — and the operator's live walk of the resulting confirm table came back APPROVED with no wording flagged.**

## Performance

- **Duration:** ~15min this session (Tasks 1-3 completed and committed in a prior session; this session closed Task 4 from the operator's returned walk evidence)
- **Tasks:** 4 (3 code tasks + 1 human-verify checkpoint)
- **Files modified:** 9 (2 created, 7 modified) across Tasks 1-3; this session added only this SUMMARY and state/roadmap updates

## Accomplishments

- Built `company_domain.py`: a pure module (no I/O, no network, no HubSpot call) that validates
  an entire batch of domain decisions before applying any of them, mirroring `preingest.py`'s
  two-pass discipline. A confirm, a correction, and a decline all route through the same
  `_clean_domain` choke point imported from `enrichment.py` — never a second copy of the
  profile-host/freemail guard.
- Extended `enrichment.py`'s companies form to carry a per-event `mode` key for a propose intent
  (placement grounded in 58-02's live-confirmed observation, not an assumption), and added three
  named refusal paths for company shapes that arrive with nothing to look up.
- Wrote the confirm-table step into both company-lane skills in the operator's register: three
  columns (company, proposed website, source + one-line reason), three per-row moves (accept,
  correct, decline), the profile-page rule stated once in plain terms, and the consent-binding
  rule that an unanswered table sends nothing.
- Closed the loop with a live operator walk of the released plugin (0.19.0) — verdict APPROVED,
  no wording flagged, and one out-of-scope finding dispositioned by explicit operator ruling
  rather than left hanging.

## Task Commits

Each task was committed atomically:

1. **Task 1: company_domain.py — propose, confirm, decline, correct** - `4340ae1`
2. **Task 2: The envelope consumes decided rows only** - `b01766d`
3. **Task 3: The confirm table, in the operator's words** - `e69f2ec`
4. **Task 4: Operator walks the confirm table** - no code commit (human-verify checkpoint; evidence recorded in this SUMMARY and closed by this plan's metadata commit)

## Task 4: Operator Walk Evidence (verbatim, per plan acceptance criteria)

**Verdict: APPROVED, operator, 2026-08-26.**

- Walked via the released plugin 0.19.0 (installed from marketplace commit `16b8641`) in a fresh
  conversation, `/operator-claude-plugin:enrich-records`, dispatch disarmed throughout.
- Row 1 — "Futsal Australia" (bare name): web search found no official site, only social pages.
  The table proposed `futsalaustralia.com.au` labeled "Guessed from the name — unverified... Low
  confidence", offered accept / type the right website / say it's wrong, and stated a rejected
  row still goes through looked up by name, never dropped. Social-page addresses were correctly
  refused as websites, with the consequence explained in operator terms.
- Row 2 — "Federation of Australian Futsal" (bare name): research found the org's own site with
  evidence ("Welcome to FAF" page lives on `futsalaustralia.org.au`); the table proposed it
  labeled "Researched — confident", explicitly noted LinkedIn/Facebook/X are social profiles
  never recorded as the website, and explained the domain-first dedupe consequence ("if a company
  at that domain exists it's enriched in place, never duplicated") before asking.
- Operator verdict on wording: APPROVED — no wording flagged; it was clear nothing sends until
  the table is answered.
- Walk coverage note (recorded honestly, not smoothed over): the LinkedIn-company-URL input row
  and the reject-a-row move were **not** exercised in this walk. Those two guards have automated
  test coverage from Tasks 1-3, but live-walk evidence for those two moves specifically is from
  the test suite, not this walk.

## Decisions Made

- **Walk verdict: APPROVED** (operator, 2026-08-26) — see Task 4 section above for the full
  verbatim record.
- **Coverage gap disclosed, not hidden**: the walk exercised two bare-name rows, not the
  LinkedIn-URL-input or reject-a-row moves. Those two moves are proven by Tasks 1-3's automated
  tests, not by this live walk. Recorded here rather than implied as fully walked.
- **Operator ruling on the out-of-scope finding raised during the walk** (2026-08-26), two parts:
  1. A company landing in HubSpot through this lane is enriched in `lv_*` signals but the native
     record-page fields (industry, country, city, employee count) stay blank — live example
     Series Futsal Victoria `283816805830` (industry found at confidence 85 but
     `validation_status: "rejected"` because native `industry` is an enumeration and the
     free-text research value has no picklist mapping; `country`/`city`/`numberofemployees`
     never promoted). **Ruling:** fold the fix into Phase 58 as a gap-closure plan (native
     industry picklist-mapped, native country/city written from derived signals, same machinery
     as quick `260826-20w`'s contact location fields, one deploy). The gap-closure plan (58-05)
     is being planned separately by the orchestrator — **not created by this plan.**
  2. CLAUDE.md §29's `numberofemployees` never-write ban is **LIFTED for this lane specifically**,
     scoped to `fill_blank_only`, provider-sourced values only. This is a deliberate, recorded
     exception to the milestone document's MVP scope cut, not a silent contradiction of it.

## Deviations from Plan

None on Tasks 1-3 — both executed exactly as planned and are already committed. Task 4's
resolution required no code change; the checkpoint's own acceptance criteria (operator
comprehension, recorded verbatim) were satisfied by the returned walk evidence.

## Issues Encountered

None. Both automated test suites green at close: `.venv/bin/python -m pytest
operator-claude-plugin/tests/ -q` — 1585 passed, 5 skipped; `node --test tests/n8n/*.test.mjs` —
727 passed, 0 failed.

## Known Stubs

None introduced by this plan. The native-field promotion gap surfaced during the walk (industry
picklist mapping, country/city/employee-count non-promotion) is pre-existing behavior of the
company lane built in 58-01/58-02, not a stub introduced here — it is dispositioned above and
carried forward as the 58-05 gap-closure plan, not silently left as debt.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`58-04` and the orchestrator-planned `58-05` gap-closure plan can proceed. `58-05` should read
this SUMMARY's operator-ruling section directly: the native industry/country/city/employee-count
promotion gap and the scoped numberofemployees exception are both recorded here as the ruling
that authorizes that plan's scope.

---
*Phase: 58-take-what-the-operator-actually-has*
*Completed: 2026-08-26*
