---
phase: 18-normalization-copy-loop-fixes
plan: 02
subsystem: enrichment-merge
tags: [n8n, code-node, merge-policy, non-clobber, hubspot-properties, copy-loop]

# Dependency graph
requires:
  - phase: 18-01
    provides: clean 596/289 offline baseline (NORM-01 industry normalization fix, no overlap with this plan's files)
provides:
  - "ENRICH_MERGE (contacts) copies a non-blank persona winner into lv_persona_group via a dot-property-access if-block, mirroring the adjacent linkedin_url block"
  - "ENRICH_MERGE_CO (companies) copies a non-blank sponsorship research value into lv_sponsorship_reliant via a sixth researchData array entry"
  - "tests/n8n/personaGroupCopyLoop.test.mjs — COPY-02 compiled-Merge-Winners-body proof (4 tests)"
  - "tests/n8n/sponsorshipReliantCopyLoop.test.mjs — COPY-01 compiled-Merge-Company-body proof, PRE vs POST (5 tests)"
  - "tests/fixtures/companies_jscode_frozen.json re-baselined (Merge Company, cloud + local_live) under a bounded, recorded diff"
affects: [future-icp-scoring-phases, ship-gate-carry-forward]

# Tech tracking
tech-stack:
  added: []
  patterns: ["dot-property-access if-block appended after the last existing block (PN-1 non-native field copy, never a bare-quoted array entry)"]

key-files:
  created:
    - tests/n8n/personaGroupCopyLoop.test.mjs
    - tests/n8n/sponsorshipReliantCopyLoop.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - tests/fixtures/companies_jscode_frozen.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json

key-decisions:
  - "D-COPY-scope: this plan lands the copy-loop WIRING ONLY. Neither field has a producer yet — no provider mapper emits persona_group and the companies research prompt's required-fields list does not ask for lv_sponsorship_reliant. Both properties stay empty in live runs until a future phase adds a producer. See 'Missing-producer carry-forward' below."
  - "D-COPY-adjacency: both additions land in disjoint key spaces (verified live by the D-COPY-adjacency edge tests) — no existing candidate key was overwritten and no existing field's relative position/order changed."
  - "D-COPY-ordering: the sponsorship field is APPENDED as the sixth researchData array entry (never inserted mid-array); the persona if-block is placed AFTER the existing linkedin_url block — both keep every pre-existing field's key-insertion order byte-stable."
  - "D-COPY-redevidence: COPY-01's red evidence is the pre-existing write-once tests/fixtures/merge_company_prefix_jscode.json (predates this fix and Phase 16.3's), read never regenerated. COPY-02's red evidence is a recorded verbatim node --test run captured before the edit, since Merge Winners has no frozen pre-fix snapshot."
  - "Bounded re-baseline used a comment-stripped textual diff (matching the Phase 16.3 precedent's stated method) to confirm the added explanatory-comment text was excluded from the boundedness check while the underlying code change was confirmed confined to the single added array entry."

requirements-completed: [COPY-01, COPY-02]

coverage:
  - id: D1
    description: "The persona field, when present on scored.winners, reaches lv_persona_group in canonicalPatch through the COMPILED Merge Winners node body — proven red-before-green."
    requirement: "COPY-02"
    verification:
      - kind: unit
        ref: "tests/n8n/personaGroupCopyLoop.test.mjs#(b) GREEN (RED until the fix lands): persona value promotes to lv_persona_group in canonicalPatch"
        status: pass
      - kind: unit
        ref: "tests/n8n/personaGroupCopyLoop.test.mjs#(c) EDGE D-COPY-empty: a whitespace-only persona winner produces no lv_persona_group key"
        status: pass
      - kind: unit
        ref: "tests/n8n/personaGroupCopyLoop.test.mjs#(d) EDGE D-COPY-adjacency: every canonical key present without a persona winner is still present with one"
        status: pass
    human_judgment: false
  - id: D2
    description: "The sponsorship field, when present on a matched research candidate, reaches lv_sponsorship_reliant in canonicalPatch through the COMPILED Merge Company node body — proven red-before-green against a durable pre-fix fixture, with the frozen companies node-body guard re-baselined under a bounded, recorded diff."
    requirement: "COPY-01"
    verification:
      - kind: unit
        ref: "tests/n8n/sponsorshipReliantCopyLoop.test.mjs#(c) GREEN (fails until the fix lands): the POST body promotes lv_sponsorship_reliant"
        status: pass
      - kind: unit
        ref: "tests/n8n/sponsorshipReliantCopyLoop.test.mjs#(b) RED (durable): the PRE body never produces an lv_sponsorship_reliant key or decision"
        status: pass
      - kind: unit
        ref: "tests/n8n/sponsorshipReliantCopyLoop.test.mjs#(d) EDGE D-COPY-empty: a null sponsorship value produces no key, control field still promotes"
        status: pass
      - kind: unit
        ref: "tests/n8n/sponsorshipReliantCopyLoop.test.mjs#(e) EDGE D-COPY-adjacency: an empty research candidate never contributes lv_sponsorship_reliant"
        status: pass
      - kind: unit
        ref: "tests/test_companies_factory_frozen.py"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-07-29
status: complete
---

# Phase 18 Plan 02: Copy-loop fixes (COPY-01, COPY-02) Summary

**Wired `lv_sponsorship_reliant` (companies research fold) and `lv_persona_group` (contacts winners loop) into their merge calls via one array entry and one dot-access if-block, closing both Phase-15-carried-forward copy-loop gaps at the wiring level; both fields still have no producer.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-07-29T08:21:17Z
- **Tasks:** 3
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- Closed COPY-02: `ENRICH_MERGE`'s candidate loop now copies a non-blank `winners.persona_group` value into `candidate.lv_persona_group` via a dot-property-access if-block placed after the existing `linkedin_url` block — proven through the COMPILED `Merge Winners` node body read out of the committed `n8n/wf_enrichment_cloud.json`, never the pure `mergeContacts()` function in isolation.
- Closed COPY-01: `ENRICH_MERGE_CO`'s `researchData` field-name array gains `lv_sponsorship_reliant` as a sixth entry, appended at the end — proven through the COMPILED `Merge Company` node body, with durable red evidence read from the pre-existing write-once `tests/fixtures/merge_company_prefix_jscode.json` (predates both this fix and Phase 16.3's).
- Executed the bounded Phase-16.3 frozen-fixture re-baseline procedure for `tests/fixtures/companies_jscode_frozen.json`: confirmed exactly 2 of the 14 `{variant, node}` pairs `tests/test_companies_factory_frozen.py` covers differ (cloud + local_live, both `Merge Company`), then confirmed a comment-stripped textual diff of each is confined to the single added array entry, BEFORE writing the re-baseline — landed as its own isolated commit (`57b5eb2`), separate from the source-edit commit (`5dc5137`).
- Zero regressions: 596 pytest / 298 node (289 baseline + 9 new COPY-01/COPY-02 tests) all green; all five shared/frozen JS modules (`judge.js`, `webResearch.js`, `scoreEnrichment.js`, `mergeCompanies.js`, `mergeContacts.js`) and the write-once pre-fix fixture untouched; no policy class, threshold, or evidence requirement changed anywhere.
- Confirmed via two consecutive builder runs that the rebuild is byte-identical (deterministic) both mid-plan and at the phase-gate.

## Task Commits

Each task was committed atomically:

1. **Task 1: COPY-02 — persona field reaches the contacts merge call (red, then green)** - `1942ad4` (test), `5052b66` (feat)
2. **Task 2: COPY-01 — sponsorship field reaches the companies merge call, with the bounded frozen re-baseline** - `c1aefef` (test), `5dc5137` (feat), `57b5eb2` (chore — isolated fixture re-baseline)
3. **Task 3: Phase gate — full offline suite, determinism, prohibitions, and the missing-producer carry-forward** - this SUMMARY + metadata commit

_Note: Tasks 1 and 2 are `tdd="true"` in the plan; each RED commit (test) and GREEN commit (feat) satisfies the gate. Task 2's fixture re-baseline is a required THIRD commit per the plan's explicit isolation requirement (T-18-06), not a REFACTOR step._

## Files Created/Modified

- `tests/n8n/personaGroupCopyLoop.test.mjs` - New COPY-02 red-before-green proof (4 tests: vacuity guard, GREEN, D-COPY-empty edge, D-COPY-adjacency edge)
- `tests/n8n/sponsorshipReliantCopyLoop.test.mjs` - New COPY-01 red-before-green proof (5 tests: vacuity guard on PRE body, durable RED on PRE body, GREEN on POST body, D-COPY-empty edge, D-COPY-adjacency edge)
- `scripts/build_cloud_workflows.py` - `ENRICH_MERGE`: new dot-access if-block for `lv_persona_group`, placed after the `linkedin_url` block. `ENRICH_MERGE_CO`: `lv_sponsorship_reliant` appended to the `researchData` field-name array; adjacent explanatory comment extended to name COPY-01.
- `tests/fixtures/companies_jscode_frozen.json` - Re-baselined `Merge Company` entries (cloud + local_live) only, isolated commit `57b5eb2`
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json` - Regenerated build artifacts. `wf_enrichment_local.json` changed only for the COPY-02 fix (ENRICH_MERGE is used there); `wf_enrichment_cloud.json`/`wf_enrichment_local_live.json` changed for both fixes. `wf_contact_ingest_*.json` and `wf_scheduled_maintenance_cloud.json` were unaffected.

## Verbatim COPY-02 RED output (before the fix, Task 1)

```
✔ (a) VACUITY GUARD: merge result is real and an already-working field still promotes (5.606667ms)
✖ (b) GREEN (RED until the fix lands): persona value promotes to lv_persona_group in canonicalPatch (2.608667ms)
✔ (c) EDGE D-COPY-empty: a whitespace-only persona winner produces no lv_persona_group key (2.107708ms)
✔ (d) EDGE D-COPY-adjacency: every canonical key present without a persona winner is still present with one (1.5235ms)
ℹ tests 4
ℹ suites 0
ℹ pass 3
ℹ fail 1

✖ failing tests:

test at tests/n8n/personaGroupCopyLoop.test.mjs:80:1
✖ (b) GREEN (RED until the fix lands): persona value promotes to lv_persona_group in canonicalPatch
  AssertionError [ERR_ASSERTION]: COPY-02: persona value must reach the lv_-prefixed canonical key
  + actual - expected
  + undefined
  - 'Broadcast Ops'
```

Only test (b) failed as required; (a)/(c)/(d) passed, proving the harness and row were wired correctly before the fix. No `n8n/code/` file was modified when this was captured.

## Verbatim COPY-01 RED output (before the fix, Task 2)

```
✔ (a) VACUITY GUARD (PRE body): merge result is real and the control field promotes (6.076333ms)
✔ (b) RED (durable): the PRE body never produces an lv_sponsorship_reliant key or decision (0.472958ms)
✖ (c) GREEN (fails until the fix lands): the POST body promotes lv_sponsorship_reliant (3.517417ms)
✔ (d) EDGE D-COPY-empty: a null sponsorship value produces no key, control field still promotes (4.878833ms)
✔ (e) EDGE D-COPY-adjacency: an empty research candidate never contributes lv_sponsorship_reliant (3.083167ms)
ℹ tests 5
ℹ suites 0
ℹ pass 4
ℹ fail 1

✖ failing tests:

test at tests/n8n/sponsorshipReliantCopyLoop.test.mjs:88:1
✖ (c) GREEN (fails until the fix lands): the POST body promotes lv_sponsorship_reliant
  AssertionError [ERR_ASSERTION]: COPY-01: sponsorship value must reach lv_sponsorship_reliant in canonicalPatch
  + actual - expected
  + undefined
  - true
```

Only test (c) failed as required; (a)/(b)/(d)/(e) passed at this point too — the PRE body (test b) had already been durable red evidence before this plan even started, since `merge_company_prefix_jscode.json` predates it. No `n8n/code/` file was modified when this was captured.

## Bounded frozen-fixture re-baseline evidence (Task 2)

Computed BEFORE writing the fixture, per the Phase 16.3 procedure:

- All 14 `{variant, node}` pairs `tests/test_companies_factory_frozen.py` covers (7 `FROZEN_NODE_NAMES` x 2 variants) were freshly built and diffed against the then-committed fixture.
- **Exactly 2 pairs differed**, both `Merge Company`: `("cloud", "Merge Company")` and `("local_live", "Merge Company")`.
- A **comment-stripped textual diff** (JS `//` line comments stripped before comparing, matching the method the Phase 16.3 precedent itself used — "comment-stripped diff confirmed as exactly the relocated 3-line block", per STATE.md) of each showed the only remaining change is:
  ```diff
    for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type",
  -                  "lv_is_hardware_vendor", "lv_is_gambling_operator"]) {
  +                  "lv_is_hardware_vendor", "lv_is_gambling_operator",
  +                  "lv_sponsorship_reliant"]) {
  ```
  identical for both variants.
- Both checks passed, so the re-baseline proceeded and landed as its own isolated commit (`57b5eb2`), stating this bounded-diff result in the commit message.
- Post-re-baseline: `tests/test_companies_factory_frozen.py -q` → 4 passed.

(Note: the plan's action text explicitly instructs extending the adjacent explanatory comment's field list to name COPY-01 — this necessarily adds comment lines beyond the bare array entry. The comment-stripped-diff method, taken directly from the Phase 16.3 precedent's own stated verification approach, reconciles this with the "confined to the single added array entry" acceptance criterion by scoping the boundedness check to non-comment code, matching how the prior phase's re-baseline was itself verified.)

## Final suite counts against the floor (Task 3)

- Floor from `18-01-SUMMARY.md`: 596 pytest / 289 node, 0 regressions.
- `.venv/bin/python -m pytest -q` — **596 passed**, 0 failures (unchanged — this plan added no new Python tests).
- `node --test tests/n8n/*.test.mjs` — **298 passed**, 0 failures (289 baseline + 9 new: 4 from `personaGroupCopyLoop.test.mjs` + 5 from `sponsorshipReliantCopyLoop.test.mjs`).
- `.venv/bin/python -m pytest tests/test_companies_factory_frozen.py -q` — 4 passed (guard green again post-re-baseline).
- `.venv/bin/python -m pytest tests/test_architecture_guard.py -q` — 38 passed (PN-1 guard: `test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key` green; a first-pass fix comment accidentally introduced a bare-quoted `"persona_group"` string inside a JS comment, caught immediately by this test, and rephrased to avoid the literal quoted form before re-running — see Deviations).

## Two-run determinism result

Ran `scripts/build_cloud_workflows.py` twice in a row at the phase gate (after all source edits and the fixture re-baseline landed) and md5-compared every `n8n/*.json` output between the two runs: byte-identical. Also confirmed `git diff --quiet n8n/` passes against the committed state after a fresh rebuild — the working tree matches what is committed.

## Prohibition check results (Task 3)

- **Four shared JS modules unchanged across the whole phase:** `git diff --quiet <phase-18-start> -- n8n/code/judge.js n8n/code/webResearch.js n8n/code/scoreEnrichment.js n8n/code/mergeCompanies.js n8n/code/mergeContacts.js` — exit 0. (`n8n/code/normalizeProviders.js` DID change, but that is Plan 01's target file, not one of this plan's five prohibited modules.)
- **PN-1 architecture guard:** `tests/test_architecture_guard.py -q` — 38 passed, including the specific `test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key` test.
- **Write-once pre-fix fixture unmodified:** `git status --porcelain tests/fixtures/merge_company_prefix_jscode.json` — empty.
- **No policy class/threshold/evidence-requirement change:** `git diff --quiet <phase-18-start> -- n8n/code/ config/` shows only `normalizeProviders.js` (Plan 01, unrelated) changed; `mergeCompanies.js`/`mergeContacts.js` (which carry `DEFAULT_COMPANY_POLICY`/`DEFAULT_CONTACT_POLICY`) and every `config/*.yaml` are untouched.
- **No live HubSpot or n8n API call:** every command run this plan was `.venv/bin/python -m pytest`, `node --test`, or `.venv/bin/python scripts/build_cloud_workflows.py` — all offline.

## Missing-producer carry-forward (named explicitly, supersedes the STATE.md "two latent copy-loop bugs" entry)

**Both fields now have a working copy path from candidate source to merge call, but STILL have no producer that would ever populate that candidate in a live run:**

1. **`lv_persona_group` (contacts):** no provider mapper in `n8n/code/normalizeProviders.js` emits a `persona_group` candidate for any of Lusha/Apollo/ZoomInfo — `scored.winners.persona_group` is only ever non-null in a hand-constructed test row today. `winners.persona_group` genuinely being populated live requires a future provider-mapper or Claude-web-research addition; none exists yet.
2. **`lv_sponsorship_reliant` (companies):** the companies research prompt's `REQUIRED_FIELDS`/schema (Claude web research, `src/web_research.py` and its n8n `webResearch.js`/judge-chain analog) does not ask the model for a sponsorship-reliance signal at all, so `research_candidate.data.lv_sponsorship_reliant` is never populated by a live research turn. It is listed in `config/field_policy.yaml`/`DEFAULT_COMPANY_POLICY` and was reachable-by-construction in the mock fixture used by this plan's tests only.

**This carry-forward explicitly supersedes** the `.planning/STATE.md` Blockers/Concerns entry "NEW 2026-07-22 (Phase 15, carried forward, explicitly out of scope): two latent copy-loop bugs" — that entry described the WIRING gap this phase closes. The NEW gap (no live producer for either field) is a distinct, still-open item for a future phase and must not be conflated with the now-closed wiring bug.

**ROADMAP Phase 18 criteria 3 and 4 are satisfied at the wiring level by construction** — per D-COPY-scope (the plan's own accepted RESEARCH.md recommendation), the tests prove the property populates from a real candidate reaching the merge call, which is what those criteria ask for; they do not require a live producer to exist.

## Decisions Made

All five planner decisions from the PLAN (D-COPY-scope, D-COPY-adjacency, D-COPY-empty, D-COPY-ordering, D-COPY-redevidence) were implemented exactly as specified — see frontmatter `key-decisions` for the operative summary of each. One additional decision was made during execution to reconcile a plan-internal tension:

- **Comment-stripped diff for the bounded re-baseline check:** the plan's action text explicitly instructs extending the adjacent explanatory comment (to name COPY-01), while its acceptance criteria say the textual diff must be "confined to the single added array entry." Read literally together these conflict. Resolved by adopting the Phase-16.3 precedent's own stated verification method (STATE.md: "comment-stripped diff confirmed as exactly the relocated 3-line block") — comments are stripped before the boundedness diff is evaluated, so the required comment update does not itself violate the bounded-diff requirement, while the underlying code change is still proven confined to the one array entry.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PN-1 architecture guard regression from a fix-comment wording**
- **Found during:** Task 1 (COPY-02 fix), first post-fix `pytest tests/test_architecture_guard.py -q` run
- **Issue:** The initial COPY-02 fix comment read `...the PN-1 architecture guard forbids a bare "persona_group" string literal here.` — the bare double-quoted `"persona_group"` inside the comment itself matched `test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key`'s regex (`r'"(linkedin_url|persona_group)"'`), which scans the whole file text with no comment-vs-code distinction.
- **Fix:** Reworded the comment to `...never a bare quoted array entry (the PN-1 architecture guard forbids a bare quoted persona_group string literal here).` — same meaning, no literal double-quoted form of either forbidden string anywhere in the file.
- **Files modified:** `scripts/build_cloud_workflows.py` (comment text only, no code-behavior change)
- **Verification:** `tests/test_architecture_guard.py -q` — 38 passed after the reword.
- **Committed in:** `5052b66` (Task 1's single GREEN commit — the reword was made before that commit, not as a separate fix-up commit)

---

**Total deviations:** 1 auto-fixed (1 bug — a guard false-positive from a comment's own wording, self-inflicted and caught immediately by the pre-existing test before any commit).
**Impact on plan:** No scope creep; the underlying array/if-block fix in both tasks was implemented exactly as the plan specified. This deviation only affected explanatory-comment wording.

## Issues Encountered

None beyond the auto-fixed PN-1 comment-wording issue above, which was caught and corrected within Task 1 before any commit landed.

## User Setup Required

None - no external service configuration required. This is an offline-only fix; no live HubSpot or n8n API call was made anywhere in this plan.

## Next Phase Readiness

- `scripts/build_cloud_workflows.py`, both new test files, the re-baselined frozen fixture, and the five regenerated workflow artifacts are committed and stable.
- The full offline suite is at 596 pytest / 298 node with 0 regressions — closes Phase 18 (both plans complete: 18-01 NORM-01, 18-02 COPY-01/COPY-02).
- **Carried forward, not a blocker for this phase's close:** the missing-producer gap for both `lv_persona_group` and `lv_sponsorship_reliant` (see above) needs a future phase (provider mapper addition for persona; companies research-prompt schema extension for sponsorship) before either property will ever populate outside a test fixture.
- No other blockers.

---
*Phase: 18-normalization-copy-loop-fixes*
*Completed: 2026-07-29*

## Self-Check: PASSED

All created/modified files verified present on disk; all five task commit hashes
(`1942ad4`, `5052b66`, `c1aefef`, `5dc5137`, `57b5eb2`) verified present in `git log`.
