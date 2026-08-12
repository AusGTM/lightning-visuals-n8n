---
phase: 48-enrichment-coverage
plan: 07
subsystem: enrichment
tags: [icp-scoring, taxonomy, web-research, hubspot]

requires:
  - phase: 48-03
    provides: "The Racing NSW captured research artifact (48-RESEARCH-RACING-NSW.json), the 5th ORG_TYPE_DECISIONS entry, RACING_NSW_ORG_TYPE_SYSTEM"
provides:
  - "Racing NSW 15008671672 corrected to governing_body_league, override recorded as data (override_of/override_rationale) over byte-identical evidence"
  - "config/taxonomy.yaml definition: key on all 9 org_types entries, rendered into both Python research prompts via src.taxonomy.org_type_definitions_block()"
  - "src.taxonomy.org_type_coherence_flags() -- the incoherent-regulator guard, wired additively into validate_research_output and as a 4th resolve_racing_nsw_decision refusal condition"
  - "AT-4: the docs/WEB-RESEARCH-SPEC.md Section 9 Racing NSW golden-set row, now an executable test"
  - "RESEARCH_PATH_OVERRIDES -- fixes the live blocker where the 5-id dry-run raised an uncaught ValueError for Racing NSW"
affects: [48-05, 48-06, 48-04]

actuals:
  tokens: 21000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Operator-reviewed override layered over verbatim evidence: override_of/override_rationale record a divergence from a paid call's returned value as data, never by editing the captured artifact"
    - "One taxonomy field (config/taxonomy.yaml definition:), one derived render function (org_type_definitions_block()), two prompt call sites -- a discriminator in two hand-maintained copies is two things that drift"
    - "Guard flags/refuses, never rewrites: org_type_coherence_flags() is read-only and never substitutes a value; a corrected classification comes only from an authored override table"
    - "Known-divergence disclosure when a Python-side additive contract change can't reach the n8n JS port in-plan (deploy-gated): documented in a pending todo + a dated spec amendment + a tripwire assertion in the GENUINE parity test, rather than silently drifting"

key-files:
  created:
    - .planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md
  modified:
    - scripts/enrich_coverage_companies.py
    - config/taxonomy.yaml
    - src/taxonomy.py
    - src/web_research.py
    - tests/test_enrich_coverage_companies.py
    - tests/test_taxonomy_conformance.py
    - tests/test_web_research_spec.py
    - tests/n8n/parity.test.mjs
    - docs/WEB-RESEARCH-SPEC.md

key-decisions:
  - "Racing NSW's ORG_TYPE_DECISIONS entry is overridden from the returned 'regulator' to 'governing_body_league', per 2026-08-13 operator review. The discriminator is commercial control of the sport (calendar, prizemoney, media rights, sponsorship), not statutory origin -- QRIC (pure regulator) and Racing NSW (governing body) are both creatures of an Act, so statutory origin cannot distinguish them. 48-RESEARCH-RACING-NSW.json stays byte-identical; the divergence is recorded as data via override_of/override_rationale."
  - "All 9 org_types entries in config/taxonomy.yaml gained a definition:, not just the two in dispute -- a half-defined vocabulary invites a model to treat the defined pair as special. Both Python research prompts render the definitions from one source via org_type_definitions_block()."
  - "The coherence guard (org_type_coherence_flags) flags and refuses; it never auto-flips a regulator classification to governing_body_league. An automatic flip would be the same class of guess that produced the original misclassification -- the corrected value comes only from Task 1's authored override table."
  - "Deviation: tests/n8n/parity.test.mjs's GENUINE JS/Python parity assertion strips the new Python-only coherence_flags key before comparing, since the JS port (n8n/code/webResearch.js) cannot be updated in this offline plan (any change under n8n/ requires a rebuild + operator deploy the phase's hard rules forbid). A tripwire assertion fails loudly if the JS side is ever updated, forcing the strip's removal rather than letting it rot silently."

patterns-established:
  - "Definitions-not-values in a taxonomy prompt: an LLM given 9 bare enum labels will key on whichever discriminator the source text emphasises, which may not be the correct one -- every enum value needs a semantic definition, rendered from one source, in any prompt that asks a model to choose among them."

requirements-completed: [COVER-01]

coverage:
  - id: D1
    description: "Racing NSW 15008671672 resolves to governing_body_league; the divergence from the returned 'regulator' is recorded as data (override_of/override_rationale), and the captured evidence artifact stays byte-identical."
    requirement: "COVER-01"
    verification:
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_racing_nsw_decision_is_governing_body_league_overriding_the_returned_value"
        status: pass
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_racing_nsw_captured_artifact_is_unedited_and_the_override_is_recorded"
        status: pass
      - kind: other
        ref: "git diff --exit-code -- .planning/phases/48-enrichment-coverage/48-RESEARCH-RACING-NSW.json"
        status: pass
    human_judgment: false
  - id: D2
    description: "The live blocker in _load_captured_research (Racing NSW has no entry in the 17-keyed 47-RESEARCH-RESULTS.json) is fixed once in the loader via RESEARCH_PATH_OVERRIDES; the 5-id dry-run runs clean end to end instead of raising an uncaught ValueError."
    requirement: "COVER-01"
    verification:
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_load_captured_research_resolves_racing_nsw_via_path_override"
        status: pass
      - kind: other
        ref: "DRY_RUN=true .venv/bin/python scripts/enrich_coverage_companies.py --dry-run (exits 0, prints governing_body_league for Racing NSW)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every lv_org_type option carries a semantic definition in config/taxonomy.yaml; both Python research prompts render the same rendered block from one source, with the regulator/governing_body_league definitions naming QRIC and Racing NSW as anchor cases."
    verification:
      - kind: unit
        ref: "tests/test_taxonomy_conformance.py::test_tx10_every_org_type_has_a_definition_and_both_prompts_render_them"
        status: pass
    human_judgment: false
  - id: D4
    description: "A regulator classification alongside evidence of content output or sponsorship reliance is flagged and refused, never auto-flipped to a different value -- verified against the real captured Racing NSW artifact."
    verification:
      - kind: unit
        ref: "tests/test_web_research_spec.py::test_guard_captured_racing_nsw_artifact_trips_the_coherence_flags"
        status: pass
      - kind: unit
        ref: "tests/test_web_research_spec.py::test_guard_qric_shaped_regulator_is_coherent_and_unflagged"
        status: pass
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_guard_never_flips_an_incoherent_regulator_to_another_value"
        status: pass
    human_judgment: false
  - id: D5
    description: "AT-4: the Racing NSW golden-set row in docs/WEB-RESEARCH-SPEC.md Section 9 is an executable, discriminating test (governing_body_league scores 70/Tier A; regulator negative control scores 10, not A/B)."
    verification:
      - kind: unit
        ref: "tests/test_web_research_spec.py::test_at4_golden_racing_nsw_governing_body_league_scores_tier_a_or_b"
        status: pass
    human_judgment: false
  - id: D6
    description: "Zero spend: no research call, no provider call, no HubSpot write, no n8n rebuild/deploy anywhere in this plan; the artifact and n8n/ both stay byte-identical."
    verification:
      - kind: other
        ref: "git diff --exit-code -- .planning/phases/48-enrichment-coverage/48-RESEARCH-RACING-NSW.json && git diff --exit-code -- n8n/"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest (full suite, 2643 passed / 128 skipped) && node --test tests/n8n/*.test.mjs (673 passed)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-13
status: complete
---

# Phase 48 Plan 07: Racing NSW Correction, Taxonomy Definitions, Coherence Guard Summary

**Racing NSW `15008671672` corrected from `regulator` to `governing_body_league` offline over
already-paid evidence, the commercial-control discriminator that would have prevented the
misclassification is now in the taxonomy and reaches both research prompts, an incoherent-
regulator guard flags-and-refuses without ever auto-flipping, and the Section 9 golden-set
expectation is now an executable, discriminating test.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3 (all `type="auto"`/`type="tracer"`, no checkpoints)
- **Files modified:** 9 (8 declared + 1 deviation)

## Accomplishments

- **Racing NSW corrected, override recorded as data.** `ORG_TYPE_DECISIONS["15008671672"]` now
  reads `org_type: "governing_body_league"`, `override_of: "regulator"`, and a full
  `override_rationale` naming the commercial-control discriminator and both anchor
  organisations (QRIC, Racing NSW) by name. `48-RESEARCH-RACING-NSW.json` is byte-identical —
  confirmed by `git diff --exit-code` at every task boundary.
- **Fixed a genuine live blocker.** `RESEARCH_PATH_OVERRIDES` teaches `_load_captured_research`
  that Racing NSW's evidence lives in its own file (which IS the research dict, unlike
  `47-RESEARCH-RESULTS.json`'s id-keyed shape) — one guard in the loader, every caller benefits.
  Before this fix, `DRY_RUN=true .venv/bin/python scripts/enrich_coverage_companies.py --dry-run`
  exited 1 with an uncaught `ValueError` traceback; it now exits 0 and prints
  `governing_body_league` for the Racing NSW patch. Genuine red-to-green.
- **Taxonomy definitions, one source, two prompts.** All 9 `org_types` entries in
  `config/taxonomy.yaml` gained a `definition:` key (not just the two in dispute).
  `src.taxonomy.org_type_definitions_block()` renders them deterministically; both
  `RESEARCH_SYSTEM` and `RACING_NSW_ORG_TYPE_SYSTEM` in `src/web_research.py` render the same
  block via string concatenation, never retyping it. Confirmed `gen_taxonomy_js.render()` does
  not read the `definition` key — `git diff --exit-code -- n8n/` stayed clean, no rebuild.
- **Coherence guard, flags-and-refuses.** `org_type_coherence_flags(data)` fires only when
  `org_type` normalizes to `regulator` alongside `lv_produces_content=True` and/or
  `lv_sponsorship_reliant=True` — exactly the shape of the verbatim captured Racing NSW
  artifact. Wired additively into `validate_research_output` (new `coherence_flags` key, ORed
  into `needs_review`, `data["lv_org_type"]` untouched) and as a fourth refusal condition in
  `resolve_racing_nsw_decision` (alongside the existing out-of-vocabulary / bare-unknown /
  no-evidence-URL conditions). A test proves the guard returns the `unknown` marker for the real
  artifact and explicitly asserts the result is NOT `governing_body_league` — the corrected value
  provably comes only from Task 1's authored override table, never from the guard guessing.
- **AT-4 makes the golden case executable.** `docs/WEB-RESEARCH-SPEC.md` §9 named the Racing NSW
  golden row since it was written, and nothing ran it. The new test asserts
  `governing_body_league` + content true + AU scores exactly 70 (Tier A threshold arithmetic:
  40+20+10) and lands in `{A, B}`; the `regulator` negative control scores 10 (below the Tier C
  floor of 15) and does NOT land in `{A, B}` — a test that passed for both values would not have
  been testing anything. It also pins `ORG_TYPE_DECISIONS["15008671672"]["org_type"]` so a future
  table edit can't silently re-break the golden case.
- **Known divergences disclosed, not silently dropped.** Two Python-only additions cannot reach
  the production n8n lane inside this offline plan (any change under `n8n/` requires a rebuild +
  operator deploy this plan's hard rules forbid): the prompt definitions (tracked in
  `.planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md` and a
  dated §2 amendment) and the `coherence_flags` key on `validate_research_output` (tracked in a
  dated §9 amendment and a tripwire assertion in `tests/n8n/parity.test.mjs`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Correct Racing NSW end-to-end — override the returned value, offline, zero spend** —
   `e332250` (fix)
2. **Task 2: Define the vocabulary where the model actually sees it — taxonomy definitions,
   rendered into both prompts** — `89c362a` (feat)
3. **Task 3: Guard the contradiction and make the golden case executable** — `3d8ec85` (feat)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified

- `scripts/enrich_coverage_companies.py` — `RESEARCH_PATH_OVERRIDES`; the corrected Racing NSW
  `ORG_TYPE_DECISIONS` entry with `override_of`/`override_rationale`; `resolve_racing_nsw_decision`'s
  fourth refusal condition
- `config/taxonomy.yaml` — `definition:` on all 9 `org_types` entries
- `src/taxonomy.py` — `ORG_TYPE_DEFINITIONS`, `org_type_definitions_block()`,
  `INCOHERENT_WITH_REGULATOR`, `org_type_coherence_flags()`; `validate_research_output` gains
  additive `coherence_flags`
- `src/web_research.py` — both prompt constants render `org_type_definitions_block()`
- `tests/test_enrich_coverage_companies.py` — Task 1/3 tests (renamed two stale tests, added 3 new)
- `tests/test_taxonomy_conformance.py` — TX-10
- `tests/test_web_research_spec.py` — coherence-guard tests + AT-4
- `docs/WEB-RESEARCH-SPEC.md` — dated TX-10 amendment, AT-4, coherence-guard section, both known
  divergences
- `tests/n8n/parity.test.mjs` — deviation fix (see below)
- `.planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md` — new

## Decisions Made

See `key-decisions` in frontmatter. Summarized: the override is data, not prose; every org type
gets a definition, not just the disputed two; the guard flags/refuses and never guesses a
replacement value; and both known Python-vs-n8n divergences this plan created are disclosed
rather than silently absorbed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tests/n8n/parity.test.mjs`'s GENUINE JS/Python parity assertion broke
when `validate_research_output` gained the additive `coherence_flags` key**
- **Found during:** Task 3, running the required `node --test tests/n8n/*.test.mjs` verify command
- **Issue:** The test does a raw `assert.deepStrictEqual` between the JS `validateResearchOutput`
  output and the Python `validate_research_output` output over a shared fixture. Python's new
  additive key has no JS counterpart, so every case failed on the extra key alone. The JS port
  (`n8n/code/webResearch.js`) cannot be updated in this plan — editing anything under `n8n/`
  requires a rebuild via `scripts/build_cloud_workflows.py` and an operator-only deploy, both
  explicitly prohibited by this plan's hard rules (`git status` must show no change under `n8n/`).
- **Fix:** In `tests/n8n/parity.test.mjs`, strip the `coherence_flags` key from the Python side
  before the `deepStrictEqual`, with a same-block tripwire assertion (`pyRaw` must carry the key,
  `jsValidate` must not) that fails loudly and forces the strip's removal if the JS side is ever
  updated to carry it — so the workaround cannot silently rot once the underlying gap closes.
- **Files modified:** `tests/n8n/parity.test.mjs` (not in the plan's declared `files_modified`)
- **Verification:** `node --test tests/n8n/*.test.mjs` — 673/673 pass; `git diff --exit-code -- n8n/`
  stays clean (only the test harness under `tests/n8n/` changed, not production `n8n/`)
- **Committed in:** `3d8ec85` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** Necessary to satisfy the plan's own `node --test tests/n8n/*.test.mjs` verify
requirement without violating the "no change under `n8n/`" hard rule. No scope creep — the fix is
scoped to the one broken assertion and documents the divergence it papers over rather than hiding it.

## Issues Encountered

None beyond the deviation above. All three tasks' acceptance criteria were met without further
auto-fixes. `.venv/bin/python -m pytest` (full suite): 2643 passed, 128 skipped, 0 failed.
`node --test tests/n8n/*.test.mjs`: 673 passed, 0 failed.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- 48-05's armed write window is unblocked on Racing NSW's corrected value: the five-id dry-run
  now completes end to end and prints `governing_body_league` for Racing NSW instead of raising.
- 48-04's deploy (owned separately, D-06) should read the new todo file when it plans its scope —
  the n8n-side org-type-definitions gap and the `coherence_flags` JS-port gap are both real,
  disclosed, and NOT this plan's or 48-04's obligation unless the operator chooses to fold them in.
- No arming, no deploy, no HubSpot writes, no research call, no provider call occurred in this
  plan — confirmed by `git diff --exit-code` on both the captured artifact and `n8n/`, and by
  the forbidden-derived-fields grep reading 0.

---
*Phase: 48-enrichment-coverage*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 10 files listed under Files Created/Modified confirmed present on disk. All 3 task
commit hashes (`e332250`, `89c362a`, `3d8ec85`) confirmed present in `git log --oneline --all`.
