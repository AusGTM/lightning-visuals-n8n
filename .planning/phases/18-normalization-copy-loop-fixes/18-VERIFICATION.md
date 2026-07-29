---
phase: 18-normalization-copy-loop-fixes
verified: 2026-07-29T09:15:00Z
status: gaps_found
score: 3/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "lv_sponsorship_reliant stops being permanently empty (ROADMAP Phase 18 goal prose; SC-3 wiring sub-claim)"
    status: failed
    reason: >
      The ENRICH_MERGE_CO researchData copy loop is correctly wired and proven by
      tests/n8n/sponsorshipReliantCopyLoop.test.mjs (red-before-green against the
      compiled Merge Company node body). But the Claude Web Research request contract
      built in scripts/build_cloud_workflows.py (the system prompt's required_fields
      array and the forced JSON response schema string, shared by build_enrichment_cloud()
      and build_enrichment_local_live() via _enrich_build_research_request_js) never asks
      the model for lv_sponsorship_reliant — only lv_org_type, lv_produces_content,
      lv_content_type, lv_is_hardware_vendor, lv_is_gambling_operator. Confirmed live in
      both built workflows: grep for "lv_sponsorship_reliant" inside the "Build Research
      Request" node's jsCode returns nothing in either wf_enrichment_cloud.json or
      wf_enrichment_local_live.json. Since research_candidate.data.lv_sponsorship_reliant
      is therefore never populated in any live invocation, the now-fixed copy step has
      nothing to copy — the HubSpot property remains permanently empty in production,
      exactly as before this phase, even though the unit test for the copy step alone is
      green. This is CR-01 in 18-REVIEW.md (Critical). A secondary compounding gap (WR-01,
      warning-severity): ENRICH_COMPANY_SEARCH_PROPERTIES_CSV (used by both the company
      search and fetch-by-id HubSpot calls) also omits lv_sponsorship_reliant, so even a
      pre-existing manually-set HubSpot value would never populate existingRecord, and the
      merge decision audit record's current_value for this field is always misreported as
      null.
    artifacts:
      - path: "scripts/build_cloud_workflows.py:1823-1860"
        issue: "research_system_prompt_fn_js required_fields array and forced JSON schema string omit lv_sponsorship_reliant"
      - path: "scripts/build_cloud_workflows.py:3404-3411"
        issue: "ENRICH_COMPANY_SEARCH_PROPERTIES_CSV omits lv_sponsorship_reliant (WR-01, warning)"
    missing:
      - "Add \"lv_sponsorship_reliant\" to the research request required_fields array and to the forced JSON schema string (plus evidence_by_field guidance), rebuild, and add a compiled-node-body test on the Build Research Request node proving the field is actually requested — the same differential technique sponsorshipReliantCopyLoop.test.mjs already applies one node later."
      - "Add lv_sponsorship_reliant to ENRICH_COMPANY_SEARCH_PROPERTIES_CSV and re-baseline the frozen companies fixture (WR-01)."
  - truth: "lv_persona_group stops being permanently empty (ROADMAP Phase 18 goal prose; SC-4 wiring sub-claim)"
    status: failed
    reason: >
      The ENRICH_MERGE dot-property-access if-block is correctly wired and proven by
      tests/n8n/personaGroupCopyLoop.test.mjs (red-before-green against the compiled Merge
      Winners node body). But no provider mapper in n8n/code/normalizeProviders.js emits a
      persona_group candidate for Lusha, Apollo, or ZoomInfo, and no research/classifier
      path produces one either — scored.winners.persona_group is non-null only in a
      hand-constructed test row today (confirmed by 18-02-SUMMARY.md's own "Missing-producer
      carry-forward" section and by grep: no `persona_group` assignment exists anywhere in
      normalizeProviders.js). The copy step has nothing to copy in any live run, so
      lv_persona_group remains permanently empty in production, unchanged from before this
      phase. The code reviewer did not flag this as a defect (18-REVIEW.md notes it mirrors
      the pre-existing linkedin_url forward-wiring pattern already in the same function),
      but that is a code-style/consistency judgment, not a goal-achievement judgment — the
      phase's own GOAL prose ("two ICP/persona properties stop being permanently empty")
      makes an outcome claim this does not satisfy for either field.
    artifacts:
      - path: "n8n/code/normalizeProviders.js"
        issue: "no provider mapper (lushaCandidates/apolloCandidates/zoominfoCandidates) ever emits a persona_group candidate"
    missing:
      - "A live producer for the persona field — a provider-mapper addition or a Claude-web-research/classifier addition that actually sets scored.winners.persona_group from real signal, matching the level of producer support lv_org_type/lv_produces_content already have."
deferred: []
human_verification: []
---

# Phase 18: Normalization & Copy-Loop Fixes Verification Report

**Phase Goal:** Two known, offline-provable data-quality gaps stop silently degrading enrichment
output — a numeric provider code no longer masquerades as a normalized industry value, and two
ICP/persona properties stop being permanently empty.
**Verified:** 2026-07-29T09:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | SC-1: A numeric provider industry code (ZoomInfo's `"71"`) never survives normalization unchanged | ✓ VERIFIED | `_industryText()` in `n8n/code/normalizeProviders.js:139` wired at both call sites (line 202 Lusha, line 319 ZoomInfo). `node --test tests/n8n/industryNormalization.test.mjs` — 4/4 pass, independently re-run this session. Live `zoominfo_live_company.json` (Racing NSW) fixture resolves `naicsCodes[0].name` ("Arts, Entertainment, and Recreation"), never the bare `"71"` code. |
| 2 | SC-2: That same numeric code never wins the waterfall over provider text by confidence/priority ordering alone | ✓ VERIFIED | `CRITERION 2` test in `industryNormalization.test.mjs` scores the real execution-19 ZoomInfo+Apollo conflict together and asserts the winning value's shape is text, not a bare digit string — independently re-run, passes. `scoreEnrichment.js` is git-unchanged (confirmed via `git diff --quiet`), so the fix is upstream of the scorer as designed. |
| 3 | SC-3: `lv_sponsorship_reliant` is copied from its candidate source into the companies merge call — "the property stops being permanently empty" | ✗ FAILED | Wiring sub-claim (test proves the copy step in isolation) is true: `tests/n8n/sponsorshipReliantCopyLoop.test.mjs` — 5/5 pass, independently re-run. But the outcome claim is false in production: the Claude Web Research request contract (`scripts/build_cloud_workflows.py:1823-1860`) never asks for this field — confirmed by grep against both built workflows, zero hits for `lv_sponsorship_reliant` in the "Build Research Request" node body. No live invocation can ever populate `research_candidate.data.lv_sponsorship_reliant`, so the property remains permanently empty. Matches 18-REVIEW.md CR-01 (Critical). |
| 4 | SC-4: `persona_group`/`lv_persona_group` is copied from its candidate source into the contacts merge call — "the property stops being permanently empty" | ✗ FAILED | Wiring sub-claim is true: `tests/n8n/personaGroupCopyLoop.test.mjs` — 4/4 pass, independently re-run. Outcome claim is false: no provider mapper in `n8n/code/normalizeProviders.js` (grep confirms) ever emits a `persona_group` candidate, so `scored.winners.persona_group` is only ever non-null in a hand-constructed test row. The property remains permanently empty in every live run, unchanged from before this phase. |
| 5 | SC-5: Offline suite green with zero regressions against the 596 pytest / 285 node baseline; workflow builder deterministic | ✓ VERIFIED | Independently re-ran the target test files (`node --test tests/n8n/industryNormalization.test.mjs tests/n8n/personaGroupCopyLoop.test.mjs tests/n8n/sponsorshipReliantCopyLoop.test.mjs tests/n8n/enrichment.test.mjs`) — 44/44 pass, 0 fail. Orchestrator-confirmed full suite: 596 pytest / 298 node (baseline 596/285, +13 new tests, 0 regressions). Independently ran `scripts/build_cloud_workflows.py` twice this session — `git diff --quiet n8n/` clean after both runs (deterministic). Frozen modules (`judge.js`, `webResearch.js`, `scoreEnrichment.js`, `mergeCompanies.js`, `mergeContacts.js`) confirmed git-unchanged. |

**Score:** 3/5 truths verified (SC-1, SC-2, SC-5). SC-3 and SC-4 fail on the phase's own GOAL
prose ("stop being permanently empty") even though their literal ROADMAP wording ("a test proves
the property populates from a real candidate") is satisfied by construction.

### Judgment call on SC-3 / SC-4 (explicit, not softened)

The plan authors made an explicit, named, reviewed scope decision (D-COPY-scope) to land the copy
wiring only, and recorded the missing-producer gap prominently in `18-02-SUMMARY.md` and
`STATE.md` Blockers/Concerns / Deferred Items. That transparency is real and is credited above (no
prohibitions were violated, no evidence was hidden, the gap was never claimed to be closed).
However, "the ROADMAP criterion's literal text is satisfied" and "the phase GOAL is achieved" are
different bars, and this agent's mandate is the latter. Read literally, the Phase 18 GOAL states
that the two properties **stop being permanently empty** — a claim about production/live behavior,
not about test-fixture behavior. As of this commit, both properties are still, in fact, permanently
empty in every live run: `lv_sponsorship_reliant` because the research prompt never requests it,
`lv_persona_group` because no provider mapper or research path ever produces it. No later phase in
the current ROADMAP (Phase 19 is "Verification Debt Closure," scoped to re-running deferred
`/gsd-verify-work` checks, not to adding a producer) is scheduled to close this — so per Step 9b
this cannot be treated as a deferred item; it is an open, unscheduled gap. The code reviewer's own
`18-REVIEW.md` independently reached the same conclusion for COPY-01 (CR-01, Critical: "the phase's
stated goal ... is not achieved end-to-end; the gap moves one layer upstream and remains open in
production, even though the unit test for the copy step itself is green").

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `n8n/code/normalizeProviders.js` `_industryText` helper | single helper, two call sites | ✓ VERIFIED | Defined line 139; called line 202 (Lusha) and line 319 (ZoomInfo). |
| `tests/n8n/industryNormalization.test.mjs` | new, NORM-01 proof | ✓ VERIFIED | Exists, 4/4 pass independently re-run. |
| `tests/n8n/personaGroupCopyLoop.test.mjs` | new, COPY-02 proof | ✓ VERIFIED | Exists, 4/4 pass independently re-run. |
| `tests/n8n/sponsorshipReliantCopyLoop.test.mjs` | new, COPY-01 proof | ✓ VERIFIED | Exists, 5/5 pass independently re-run. |
| `scripts/build_cloud_workflows.py` `ENRICH_MERGE_CO` researchData array | sponsorship field appended | ✓ VERIFIED | `lv_sponsorship_reliant` present as 6th entry, line ~2325. |
| `scripts/build_cloud_workflows.py` `ENRICH_MERGE` persona if-block | mirrors linkedin block | ✓ VERIFIED | Dot-property-access if-block present after linkedin block (per SUMMARY, confirmed by passing personaGroupCopyLoop tests). |
| `tests/fixtures/companies_jscode_frozen.json` | re-baselined, isolated commit | ✓ VERIFIED | `tests/test_companies_factory_frozen.py` green; re-baseline commit `57b5eb2` present in `git log`, separate from source-edit commit `5dc5137`. |
| Regenerated `n8n/wf_*.json` artifacts | reflect both fixes | ✓ VERIFIED | Determinism re-confirmed independently: two builder runs, `git diff --quiet n8n/` clean both times. |
| `scripts/build_cloud_workflows.py` research request `required_fields` / JSON schema | should request sponsorship signal for SC-3 to hold end-to-end | ✗ MISSING | `lv_sponsorship_reliant` absent from both the `required_fields` array and the forced JSON schema string at lines 1823-1860 — confirmed by direct read and grep. |
| `scripts/build_cloud_workflows.py` `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` | should include sponsorship for accurate audit `current_value` | ✗ MISSING | `lv_sponsorship_reliant` absent from the CSV at lines 3404-3411 (WR-01, warning-severity, does not affect promote/clobber correctness today but corrupts the audit trail). |
| Persona-field producer (provider mapper / research path) | should exist for SC-4 to hold end-to-end | ✗ MISSING | Grep of `n8n/code/normalizeProviders.js` confirms no mapper emits `persona_group` for Lusha/Apollo/ZoomInfo. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| ZoomInfo/Lusha companies mappers | `_industryText` helper | direct call | ✓ WIRED | Confirmed by grep + passing tests. |
| `scoreEnrichment.js` waterfall | `_industryText` output | candidate value shape | ✓ WIRED | `scoreEnrichment.js` untouched; candidate values are pre-normalized upstream, confirmed by CRITERION 2 test. |
| `ENRICH_MERGE_CO` researchData loop | `mergeCompanies()` `canonicalPatch` | array entry -> merge call | ✓ WIRED (isolated) | Compiled-body test proves the copy step alone. |
| Claude Web Research response | `research_candidate.data.lv_sponsorship_reliant` | request schema -> response parse | ✗ NOT WIRED | Request schema never asks for the field — this is the link that breaks SC-3 end-to-end (see CR-01). |
| `ENRICH_MERGE` winners loop | `mergeContacts()` `canonicalPatch` | if-block -> merge call | ✓ WIRED (isolated) | Compiled-body test proves the copy step alone. |
| Provider waterfall / research | `scored.winners.persona_group` | provider mapper -> normalized candidate | ✗ NOT WIRED | No mapper ever produces this key — this is the link that breaks SC-4 end-to-end. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Target NORM-01/COPY-01/COPY-02 test files pass | `node --test tests/n8n/industryNormalization.test.mjs tests/n8n/personaGroupCopyLoop.test.mjs tests/n8n/sponsorshipReliantCopyLoop.test.mjs tests/n8n/enrichment.test.mjs` | 44 pass, 0 fail | ✓ PASS |
| Research request never asks for sponsorship field (live-shape check) | `grep -c lv_sponsorship_reliant` inside `wf_enrichment_cloud.json`'s "Build Research Request" node jsCode | 0 hits | ✗ FAIL (confirms CR-01) |
| Builder determinism | `.venv/bin/python scripts/build_cloud_workflows.py` (x2) then `git diff --quiet n8n/` | clean both times | ✓ PASS |
| Frozen shared JS modules unchanged | `git diff --quiet n8n/code/scoreEnrichment.js n8n/code/judge.js n8n/code/webResearch.js n8n/code/mergeCompanies.js n8n/code/mergeContacts.js` | exit 0 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| NORM-01 | 18-01-PLAN.md | Numeric provider industry code never survives normalization / never wins waterfall on trust alone | ✓ SATISFIED | `_industryText` helper wired at both call sites; both offline criteria proven; frozen/scorer modules untouched. |
| COPY-01 | 18-02-PLAN.md | `lv_sponsorship_reliant` copied from candidate source into companies merge call | ⚠ WIRING SATISFIED / OUTCOME NOT SATISFIED | Copy step proven by compiled-body test, but the research prompt never produces the candidate it would copy — property stays permanently empty live (CR-01). REQUIREMENTS.md marks this "Complete," which overstates the live-behavior outcome. |
| COPY-02 | 18-02-PLAN.md | `persona_group`/`lv_persona_group` copied from candidate source into contacts merge call | ⚠ WIRING SATISFIED / OUTCOME NOT SATISFIED | Copy step proven by compiled-body test, but no producer ever sets the winner it would copy — property stays permanently empty live. REQUIREMENTS.md marks this "Complete," which overstates the live-behavior outcome. |

No orphaned requirements found — NORM-01, COPY-01, COPY-02 are the complete set mapped to Phase 18
in both the PLAN frontmatter and `REQUIREMENTS.md`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `scripts/build_cloud_workflows.py` | 1823-1860 | Research request schema silently under-scoped relative to `field_policy.yaml`'s `allow_web_research: true` declaration for `lv_sponsorship_reliant` | 🛑 Blocker (for SC-3's outcome claim) | Field can never populate from research in production; matches 18-REVIEW.md CR-01. |
| `scripts/build_cloud_workflows.py` | 3404-3411 | `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` omits `lv_sponsorship_reliant`, unlike every sibling research field | ⚠ Warning | Audit `current_value` misreported as null for this field even when HubSpot already holds one; matches 18-REVIEW.md WR-01. Does not cause clobbering today (field policy is `system_owned`, gate does not branch on `currentValue`), but corrupts the reviewer-facing audit trail. |
| `n8n/code/normalizeProviders.js` | n/a | No producer for `persona_group` anywhere in provider mappers | ⚠ Warning (goal-level, not a code defect) | `lv_persona_group` copy path is unreachable in production; explicitly named in `18-02-SUMMARY.md` and `STATE.md` as a carry-forward, not hidden, but still open. |

No `TBD`/`FIXME`/`XXX` unresolved debt markers found in the phase's modified files.

### Human Verification Required

None. Both gaps are fully determined by static analysis of the compiled node bodies (grep +
direct read) and require no runtime/visual/external-service judgment to confirm.

### Gaps Summary

Phase 18 lands two genuinely solid pieces of work (NORM-01 fully closed end-to-end; the copy-loop
wiring itself for COPY-01/COPY-02, cleanly proven with red-before-green tests against compiled node
bodies) and one honestly-disclosed but still-open gap: the phase's own GOAL text promises that
"two ICP/persona properties stop being permanently empty," and that promise is not kept in
production for either property, because neither has a live producer. `lv_sponsorship_reliant`'s gap
is upstream in the Claude Web Research request contract (never asks for the field — CR-01,
Critical, plus the lower-severity WR-01 search-CSV omission); `lv_persona_group`'s gap is that no
provider mapper or research path anywhere in the codebase ever sets a `persona_group` candidate.
The planners were transparent about this (D-COPY-scope, named carry-forward in `18-02-SUMMARY.md`
and `STATE.md`), and the wiring itself is exactly what was asked for at the literal ROADMAP
criteria-3/4 text level — but "wiring proven by a hand-constructed test row" and "property stops
being permanently empty" are different claims, and the phase's own GOAL statement makes the
stronger one. This phase should not be treated as fully closing the copy-loop problem; a follow-up
phase is needed to add the two missing producers (and, ideally, the WR-01 search-CSV fix) before
COPY-01/COPY-02 can be marked truly complete against the stated goal.

---

_Verified: 2026-07-29T09:15:00Z_
_Verifier: Claude (gsd-verifier)_
