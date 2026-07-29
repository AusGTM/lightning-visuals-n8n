---
phase: 18-normalization-copy-loop-fixes
verified: 2026-07-29T11:40:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  gaps_closed:
    - "lv_sponsorship_reliant stops being permanently empty (SC-3) — Claude Web Research request contract now asks for the field"
    - "lv_persona_group stops being permanently empty (SC-4) — a real provider-mapper producer now emits a persona_group candidate"
  gaps_remaining: []
  regressions: []
deferred: []
human_verification: []
---

# Phase 18: Normalization & Copy-Loop Fixes Verification Report

**Phase Goal:** Two known, offline-provable data-quality gaps stop silently degrading enrichment
output — a numeric provider code no longer masquerades as a normalized industry value, and two
ICP/persona properties stop being permanently empty.
**Verified:** 2026-07-29T11:40:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (18-03-PLAN.md / 18-03-SUMMARY.md, executed 2026-07-29)

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | SC-1: A numeric provider industry code (ZoomInfo's `"71"`) never survives normalization unchanged | ✓ VERIFIED (regression check) | `_industryText()` unchanged since prior verification, `n8n/code/normalizeProviders.js:139`, wired at both call sites (Lusha :224, ZoomInfo :343 — line numbers shifted by the new `_personaGroup` helper, logic identical). `node --test tests/n8n/industryNormalization.test.mjs` re-run independently this session: 4/4 pass. |
| 2 | SC-2: That same numeric code never wins the waterfall over provider text by confidence/priority ordering alone | ✓ VERIFIED (regression check) | `CRITERION 2` test re-run independently this session: pass. `scoreEnrichment.js` confirmed git-unchanged this plan (`git diff --quiet` against frozen module list, exit 0). |
| 3 | SC-3: `lv_sponsorship_reliant` is copied from its candidate source into the companies merge call — property stops being permanently empty | ✓ VERIFIED | Both prior-verification blockers independently re-checked and now closed: (1) `grep -c lv_sponsorship_reliant` inside the "Build Research Request" node's compiled `jsCode` in **both** built workflows now returns **3 hits each** (was 0) — independently re-run this session, not taken from SUMMARY. (2) The forced JSON response schema string and `required_fields` array in `scripts/build_cloud_workflows.py:1840-1863` both name the field, confirmed by direct read. (3) `tests/n8n/researchRequestSponsorshipContract.test.mjs` — 5/5 pass, independently re-run — proves the field is requested in both variants AND survives the frozen `Validate Research Output` validator's wholesale `{...raw.data}` spread into `research_candidate.data` untouched (no edit to any frozen module). (4) This feeds the already-proven `sponsorshipReliantCopyLoop.test.mjs` copy step (5/5 pass, independently re-run) — the full prompt→validate→copy→merge chain is now offline-provable end to end. (5) `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` now includes `lv_sponsorship_reliant` (confirmed by direct read, line 3419), closing WR-01's audit-trail gap. **Scope caveat (not a defect):** the field only populates on research-gated rows (`needsResearch`) AND when the pre-existing, deploy-time `ALLOW_WEB_RESEARCH` overlay is armed (disabled by default per Phase 16.5's `enable_baked_flags()` kill switch — an intentional, already-documented operator control, not something Phase 18 was scoped to flip). This is the difference between "structurally impossible in any universe" (the original bug) and "reachable when the existing feature is turned on" (the fixed state). |
| 4 | SC-4: `persona_group`/`lv_persona_group` is copied from its candidate source into the contacts merge call — property stops being permanently empty | ✓ VERIFIED | Prior-verification blocker independently re-checked and now closed: `grep -n "_personaGroup\|persona_group" n8n/code/normalizeProviders.js` now shows a real helper (`_personaGroup`, line 156) plus two live call sites in `lushaCandidates` (line 203-204) and `apolloCandidates` (line 254-255) — read in full, confirmed non-stub (returns the provider's own department string, `null` for an absent or semantically-empty `"Other"` value, never fabricates a taxonomy; guarded by `_push`'s existing null/undefined/empty-string skip). `tests/n8n/personaGroupProducer.test.mjs` — 6/6 pass, independently re-run — drives the RECORDED `apollo_contact.json` fixture through the **compiled** `Normalize + Score` then `Merge Winners` node bodies read out of the committed `n8n/wf_enrichment_cloud.json` (verified by direct read of the test file: `scored.winners.persona_group` and `merge.canonicalPatch.lv_persona_group` are asserted on the node's own OUTPUT row, never hand-written — confirms this is not the shortcut the original gap report warned about). Feeds the already-proven `personaGroupCopyLoop.test.mjs` (4/4 pass, independently re-run). **Flagged residual uncertainty (does not block this verdict, recommended follow-up):** the fixture that proves Apollo's producer fires (`apollo_contact.json`) is this repo's original **offline/mock** MVP fixture (`exampleracing.example` placeholder domain), not a confirmed live Apollo capture. The one genuinely **live-recorded** Apollo response in this repo (`apollo_live_match.json`, Tabcorp/Gillon McLachlan) carries no `departments` field at all — correctly produces zero persona candidates (test (d), by design). Lusha's producer exists in code but has only ever been exercised against the semantically-empty live value `"Other"` (correctly produces no candidate); no live Lusha response with a real department value has been observed. ZoomInfo has no producer — no department field appears in any recorded ZoomInfo shape (deliberate, per D-GAP2-nozoominfo). **Net effect:** the code-level defect this phase was scoped to fix (no producer existed for ANY provider, under ANY circumstances — offline-provably permanent) is genuinely closed. Whether Apollo's live API traffic actually carries a `departments` value for real contacts is an external-data-availability question no offline test can answer — it requires a live Apollo canary, which this codebase's own established pattern defers as a separate, later operational step (matches every other Phase 13-18 producer: proven offline first, canaried live later, per CLAUDE.md §25's rollout plan and explicitly acknowledged in `18-03-SUMMARY.md`'s own "Carry-forward supersession" section). This is a materially different, lesser category of open item than the original gap (external data uncertainty vs. a provable dead code path), so it does not reopen SC-4 — but a live Apollo/Lusha canary is the natural next step to fully retire it. |
| 5 | SC-5: Offline suite green with zero regressions against the 596 pytest / 285 node baseline; workflow builder deterministic | ✓ VERIFIED | Independently re-ran the full suite this session (not trusting the orchestrator's reported counts): `.venv/bin/python -m pytest -q` → **596 passed**, 0 failures. `node --test tests/n8n/*.test.mjs` → **309 passed**, 0 failures (298 prior-verification baseline + 11 new: 5 from `researchRequestSponsorshipContract.test.mjs` + 6 from `personaGroupProducer.test.mjs`). Independently ran `scripts/build_cloud_workflows.py` this session and confirmed `git diff --quiet n8n/` clean after the rebuild (deterministic). Frozen shared modules (`judge.js`, `webResearch.js`, `scoreEnrichment.js`, `mergeCompanies.js`, `mergeContacts.js`, `contactJudge.js`) confirmed git-unchanged via `git diff --quiet`, exit 0. `config/` confirmed unchanged since the plan's start commit (`8e1be31`). `tests/test_companies_factory_frozen.py` — 4/4 pass, confirming the bounded, isolated re-baseline (commit `b9a6394`, separate from the source-edit commits) holds. |

**Score:** 5/5 truths verified (SC-1 through SC-5). Both gaps from the prior verification round
(3/5, `gaps_found`) are now closed at the OUTCOME level the phase's GOAL prose requires, not merely
the wiring level — with one flagged, non-blocking residual item (Apollo/Lusha live department-data
availability, SC-4) recommended for a future live canary.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `n8n/code/normalizeProviders.js` `_industryText` helper | single helper, two call sites | ✓ VERIFIED | Unchanged since prior verification; still wired. |
| `tests/n8n/industryNormalization.test.mjs` | NORM-01 proof | ✓ VERIFIED | 4/4 pass, independently re-run. |
| `tests/n8n/personaGroupCopyLoop.test.mjs` | COPY-02 wiring proof | ✓ VERIFIED | 4/4 pass, independently re-run. |
| `tests/n8n/sponsorshipReliantCopyLoop.test.mjs` | COPY-01 wiring proof | ✓ VERIFIED | 5/5 pass, independently re-run. |
| `tests/n8n/researchRequestSponsorshipContract.test.mjs` (new, 18-03) | COPY-01 producer proof | ✓ VERIFIED | 5/5 pass, independently re-run. Executes the committed "Build Research Request" node body directly. |
| `tests/n8n/personaGroupProducer.test.mjs` (new, 18-03) | COPY-02 producer proof | ✓ VERIFIED | 6/6 pass, independently re-run. Drives a recorded fixture through the compiled Normalize + Score → Merge Winners chain. |
| `scripts/build_cloud_workflows.py` research request `required_fields` / JSON schema | now names lv_sponsorship_reliant | ✓ VERIFIED (was ✗ MISSING) | Confirmed present by direct read (lines 1840, 1845, 1863) and by 3 grep hits in each compiled node body (was 0). |
| `scripts/build_cloud_workflows.py` `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` | now includes lv_sponsorship_reliant | ✓ VERIFIED (was ✗ MISSING) | Confirmed present by direct read (line 3419). |
| `n8n/code/normalizeProviders.js` `_personaGroup()` helper + call sites | provider-mapper producer for persona | ✓ VERIFIED (was ✗ MISSING) | Confirmed present and non-stub by direct read; wired into `lushaCandidates` and `apolloCandidates` contacts branches only (ZoomInfo deliberately excluded, no department field ever observed). |
| `src/web_research.py` `RESEARCH_SYSTEM` schema string | Python-oracle parity for sponsorship field | ✓ VERIFIED | Confirmed by direct read; matches the already-present `REQUIRED_FIELDS` entry. |
| `tests/fixtures/companies_jscode_frozen.json` | re-baselined, isolated commit | ✓ VERIFIED | `tests/test_companies_factory_frozen.py` — 4/4 pass. Re-baseline commit `b9a6394` present in `git log`, isolated from the source-edit commits (`371fe9d`, `bd515e7`). |
| Regenerated `n8n/wf_*.json` artifacts | reflect both fixes | ✓ VERIFIED | Determinism re-confirmed independently this session: rebuild, then `git diff --quiet n8n/` clean. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| ZoomInfo/Lusha companies mappers | `_industryText` helper | direct call | ✓ WIRED | Unchanged, re-confirmed. |
| Claude Web Research request (`Build Research Request`) | `research_candidate.data.lv_sponsorship_reliant` | request schema -> response parse | ✓ WIRED (was ✗ NOT WIRED) | Request schema now asks for the field (independently re-grepped, 3 hits per built workflow); `researchRequestSponsorshipContract.test.mjs` proves survival through the frozen `Validate Research Output` spread. |
| `ENRICH_MERGE_CO` researchData loop | `mergeCompanies()` `canonicalPatch` | array entry -> merge call | ✓ WIRED (end-to-end) | Was previously "wired in isolation only" — now the upstream producer feeding it is also wired, closing the full chain. |
| Provider waterfall (Apollo/Lusha) | `scored.winners.persona_group` | provider mapper -> normalized candidate | ✓ WIRED (was ✗ NOT WIRED) | `_personaGroup()` mapper now produces this key for Apollo/Lusha; independently confirmed via `personaGroupProducer.test.mjs`'s compiled-chain test driving a recorded fixture, not a hand-injected winner. |
| `ENRICH_MERGE` winners loop | `mergeContacts()` `canonicalPatch` | if-block -> merge call | ✓ WIRED (end-to-end) | Was previously "wired in isolation only" — now the upstream producer feeding it is also wired, closing the full chain. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| The exact grep check that failed the prior verification round now passes | `node -e` script grepping "Build Research Request" node's `jsCode` for `lv_sponsorship_reliant` in both `wf_enrichment_cloud.json` and `wf_enrichment_local_live.json` | 3 hits each (was 0/0) | ✓ PASS |
| `_personaGroup` producer exists and is non-stub | direct read of `n8n/code/normalizeProviders.js:156-161` | real implementation, null-rather-than-fabricate, guarded by `_push` | ✓ PASS |
| All 5 targeted 18-01/18-02/18-03 test files pass | `node --test tests/n8n/researchRequestSponsorshipContract.test.mjs tests/n8n/personaGroupProducer.test.mjs tests/n8n/sponsorshipReliantCopyLoop.test.mjs tests/n8n/personaGroupCopyLoop.test.mjs tests/n8n/industryNormalization.test.mjs` | 24/24 pass, 0 fail | ✓ PASS |
| `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` carries the sponsorship field | direct read, line 3419 | `lv_sponsorship_reliant` present | ✓ PASS |
| Full offline suite, independently re-run | `.venv/bin/python -m pytest -q` + `node --test tests/n8n/*.test.mjs` | 596 pytest / 309 node, 0 failures | ✓ PASS |
| Builder determinism | rebuild once this session, `git diff --quiet n8n/` | clean | ✓ PASS |
| Frozen shared JS modules + config/ unchanged | `git diff --quiet` against the module list and `config/` | exit 0 | ✓ PASS |
| Frozen companies fixture guard green | `.venv/bin/python -m pytest tests/test_companies_factory_frozen.py -q` | 4/4 pass | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| NORM-01 | 18-01-PLAN.md | Numeric provider industry code never survives normalization / never wins waterfall on trust alone | ✓ SATISFIED (unchanged) | `_industryText` helper wired at both call sites; both offline criteria re-verified this session. |
| COPY-01 | 18-02-PLAN.md, 18-03-PLAN.md | `lv_sponsorship_reliant` copied from candidate source into companies merge call — outcome, not just wiring | ✓ SATISFIED (was ⚠ WIRING SATISFIED / OUTCOME NOT SATISFIED) | Research request now asks for the field; proven to survive validation into `research_candidate.data`; already-proven copy step consumes it. `REQUIREMENTS.md`'s "Complete" marking is now accurate. |
| COPY-02 | 18-02-PLAN.md, 18-03-PLAN.md | `persona_group`/`lv_persona_group` copied from candidate source into contacts merge call — outcome, not just wiring | ✓ SATISFIED (was ⚠ WIRING SATISFIED / OUTCOME NOT SATISFIED) | Real provider-mapper producer emits the candidate for Apollo/Lusha; proven through the compiled Normalize+Score → Merge Winners chain over a recorded fixture. `REQUIREMENTS.md`'s "Complete" marking is now accurate, subject to the flagged live-data-availability caveat above. |

No orphaned requirements — NORM-01, COPY-01, COPY-02 are the complete set mapped to Phase 18 in
both `18-03-PLAN.md` frontmatter and `REQUIREMENTS.md`.

### Anti-Patterns Found

None in the files modified by 18-03. The two anti-patterns flagged in the prior verification round
(`scripts/build_cloud_workflows.py:1823-1860` under-scoped research schema; no `persona_group`
producer anywhere in `normalizeProviders.js`) are both resolved by this plan's edits. No new
`TBD`/`FIXME`/`XXX` unresolved debt markers found in the phase's modified files (`scripts/build_cloud_workflows.py`,
`src/web_research.py`, `n8n/code/normalizeProviders.js`, the two new test files).

### Human Verification Required

None. Both gap closures are fully determined by static analysis (direct read + grep against
compiled node bodies) and executable offline tests driving recorded fixtures through the compiled
node chains — no runtime/visual/external-service judgment is required to confirm the code-level fix.

The one flagged residual item (whether Apollo's live API traffic genuinely carries a `departments`
value for real contacts, and whether a non-"Other" Lusha department value has ever been observed
live) is a live-canary/operational question, not a human-verification question — it requires an
actual API call, not human judgment of already-visible evidence, and per this codebase's own
established norm (offline-proven now, live-canaried later, per CLAUDE.md §25) it is recorded as a
recommended follow-up rather than a blocking gap or a human-verification item.

### Gaps Summary

Both gaps from the prior verification round are closed. Plan 18-03 added a real, offline-provable
producer upstream of each already-correctly-wired copy step:

- **`lv_sponsorship_reliant` (GAP 1 / COPY-01):** the Claude Web Research request contract
  (`scripts/build_cloud_workflows.py`, shared by both the cloud and local_live variants) now asks
  the model for the field in both the `required_fields` array and the forced JSON response schema.
  A new test (`researchRequestSponsorshipContract.test.mjs`) proves the field is requested AND
  survives the frozen `Validate Research Output` validator's spread into
  `research_candidate.data` untouched — the exact hop the prior verification identified as broken.
  `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` also now carries the field (WR-01), restoring the merge
  audit trail's `current_value` accuracy. The only remaining scope limit is the pre-existing,
  intentional `ALLOW_WEB_RESEARCH` deploy-time kill switch (Phase 16.5, disabled by default) — an
  operator decision entirely outside this phase's fence, not a code defect.

- **`lv_persona_group` (GAP 2 / COPY-02):** a new `_personaGroup()` provider-mapper producer in
  `n8n/code/normalizeProviders.js` reads Apollo's and Lusha's own `departments` field, mirroring the
  `_industryText` null-rather-than-fabricate contract from Plan 18-01. A new test
  (`personaGroupProducer.test.mjs`) drives a recorded fixture through the compiled
  `Normalize + Score` → `Merge Winners` chain and proves `lv_persona_group` reaches
  `canonicalPatch` from the node's own produced output — never a hand-injected winner. The one
  honestly-flagged residual uncertainty is that the fixture proving Apollo's branch fires is this
  repo's original offline/mock fixture, not a confirmed live Apollo capture, while the sole
  genuinely live-recorded Apollo response in this repo carries no department field at all; Lusha's
  branch has only been exercised against the live "Other" non-signal value. This is a live-data-
  availability question external to the code, not a reopened code defect, and is recorded as a
  recommended follow-up (a live Apollo/Lusha canary) rather than a blocker.

Both `SUMMARY.md`'s reported test counts (596 pytest / 309 node, 24/24 targeted tests, deterministic
rebuild, frozen modules unchanged) were independently re-verified this session rather than trusted,
and all matched exactly. Phase 18 goal is achieved: both properties now have a real, offline-provable
path to populate in production, closing the "silently degrading enrichment output" concern the
phase's own GOAL statement named. Ready to proceed.

---

_Verified: 2026-07-29T11:40:00Z_
_Verifier: Claude (gsd-verifier)_
