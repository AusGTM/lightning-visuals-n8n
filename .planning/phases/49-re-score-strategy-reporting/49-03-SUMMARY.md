---
phase: 49-re-score-strategy-reporting
plan: 03
subsystem: n8n
tags: [taxonomy, lv_org_type, research-prompt, code-generation, n8n-cloud, jscode-frozen-fixture]

# Dependency graph
requires:
  - phase: 48-enrichment-coverage
    provides: "config/taxonomy.yaml definition: keys, src.taxonomy.ORG_TYPE_DEFINITIONS, org_type_definitions_block(), both Python research prompts rendering it (Phase 48 Plan 07, TX-10)"
provides:
  - "n8n/code/taxonomy.generated.js carries an ORG_TYPE_DEFINITIONS const, generated from config/taxonomy.yaml"
  - "The production n8n research prompt (COMPANIES_TARGET.research_system_prompt_fn_js, node 'Build Research Request') renders org-type definitions into its returned system prompt string, not just a bare key list"
  - "A committed, not-yet-deployed build of n8n/wf_enrichment_cloud.json and n8n/wf_enrichment_local_live.json carrying the fix"
  - "tests/n8n/orgTypeDefinitionsPrompt.test.mjs -- a regression guard that runs the node's own jsCode and asserts on the returned prompt string, with a negative control proving the assertion has teeth"
  - "tests/fixtures/companies_jscode_frozen.json re-baselined as an explicit, reviewed act"
affects: ["49-04-deploy-and-close-todo"]

# Actuals (#2632)
actuals:
  tokens: 362864   # chars/4 over `git diff dac9a8d^..HEAD` (full realized diff, RED commit through re-baseline). Large relative to the plan's 90000 estimate because two of the four changed n8n/*.json files store each Code node's jsCode as a single very long JSON string line -- a 4-line jsCode delta serializes as a handful of enormous diff lines, not a proportionally small text diff.
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Generated-artifact-as-single-source: config/taxonomy.yaml's definition: key now flows through TWO independent renderers (org_type_definitions_block() for Python prompts, gen_taxonomy_js.render()'s new ORG_TYPE_DEFINITIONS const for n8n) from one YAML source, never restated inline in either."
    - "Run-the-node-not-grep-the-jsCode: when a shared inlined module can carry data unused by the specific function under test, the regression guard must execute the node's own jsCode (new Function(), the researchChainRowFlow.test.mjs idiom) and assert on its ACTUAL RETURN VALUE, not on raw jsCode substring presence -- a substring check over inlined-but-dead module text is not proof the behavior changed."

key-files:
  created:
    - tests/n8n/orgTypeDefinitionsPrompt.test.mjs
  modified:
    - scripts/gen_taxonomy_js.py
    - src/taxonomy.py
    - n8n/code/taxonomy.generated.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - n8n/wf_review_decision_cloud.json
    - docs/WEB-RESEARCH-SPEC.md
    - tests/fixtures/companies_jscode_frozen.json
    - tests/test_taxonomy_conformance.py

key-decisions:
  - "Left CONTACTS_TARGET.research_system_prompt_fn_js byte-unchanged after inspection -- it is a contact-role (jobtitle/seniority) research prompt and never enumerates lv_org_type at all, so there was nothing to fix there."
  - "Committed two n8n workflow JSON files beyond the plan's predicted set (wf_scheduled_maintenance_cloud.json, wf_review_decision_cloud.json) because both inline n8n/code/taxonomy.generated.js via the Apply Review node (ENRICH_APPLY_REVIEW), for reasons unrelated to the research prompt. Growing the shared module in Task 1 grew every Code node that inlines it. Reverting them would have manufactured stale-checked-in-artifact drift with no currency test to ever catch it; committing the honestly-regenerated output is the correct move and keeps the repo's build-from-source invariant intact."
  - "Rewrote Task 3's node test to assert against Build Research Request's ACTUAL RETURNED system-prompt string (research_request_body.system, obtained by executing the node's own committed jsCode via new Function), not against raw jsCode text. A raw-jsCode substring check would have trivially passed even on a reverted researchSystemPrompt(), because the (then-unused) ORG_TYPE_DEFINITIONS const is inlined into that node's jsCode anyway (the module is already inlined there for ORG_TYPES/CONTENT_TYPES)."

patterns-established:
  - "Any future n8n Code-node string-content regression test must assert on the function's return value where the wrapper inlines a shared module the function under test may or may not actually consume -- see tests/n8n/orgTypeDefinitionsPrompt.test.mjs's header note."

requirements-completed: [RESCORE-01]

coverage:
  - id: D1
    description: "n8n/code/taxonomy.generated.js exports ORG_TYPE_DEFINITIONS with exactly the nine org-type keys and non-empty definition strings matching src.taxonomy.ORG_TYPE_DEFINITIONS"
    requirement: "RESCORE-01"
    verification:
      - kind: unit
        ref: "tests/test_taxonomy_conformance.py::test_tx10_generated_js_carries_org_type_definitions"
        status: pass
      - kind: other
        ref: "node -e \"require('./n8n/code/taxonomy.generated.js').ORG_TYPE_DEFINITIONS\" -- 9 keys, all non-empty strings, key set equals ORG_TYPES"
        status: pass
    human_judgment: false
  - id: D2
    description: "The companies research system prompt returned by the built 'Build Research Request' node renders every org type's key AND definition text (not just a bare key list), while the strict nine-key enum constraint stays unweakened"
    requirement: "RESCORE-01"
    verification:
      - kind: unit
        ref: "tests/n8n/orgTypeDefinitionsPrompt.test.mjs -- wf_enrichment_cloud.json and wf_enrichment_local_live.json cases, plus the negative control"
        status: pass
    human_judgment: false
  - id: D3
    description: "n8n/wf_enrichment_cloud.json and n8n/wf_enrichment_local_live.json are byte-reproducible from scripts/build_cloud_workflows.py (a second build is a no-op diff)"
    requirement: "RESCORE-01"
    verification:
      - kind: other
        ref: "two consecutive runs of `.venv/bin/python scripts/gen_taxonomy_js.py && .venv/bin/python scripts/build_cloud_workflows.py`; `git status --short -- n8n/` empty after the second run"
        status: pass
    human_judgment: false
  - id: D4
    description: "tests/fixtures/companies_jscode_frozen.json re-baselined as an explicit, reviewed act, with the reason recorded in the commit message and this summary; no assertion in tests/test_companies_factory_frozen.py was added, removed, or reworded"
    requirement: "RESCORE-01"
    verification:
      - kind: unit
        ref: "tests/test_companies_factory_frozen.py (both cloud and local_live byte-identity tests) -- pass"
        status: pass
      - kind: other
        ref: "git diff HEAD -- tests/test_companies_factory_frozen.py | grep -cE '^[-+][[:space:]]*assert ' returns 0"
        status: pass
    human_judgment: false

# Metrics
duration: 9min
completed: 2026-08-13
status: complete
---

# Phase 49 Plan 03: n8n research prompt org-type definitions Summary

**The production n8n enrichment lane's research prompt now defines each `lv_org_type` option instead of listing nine bare keys — closing the last of three blockers on the folded Racing-NSW-misclassification todo, entirely offline, with the fixture re-baseline recorded as the explicit reviewed act its own rule requires.**

## Performance

- **Duration:** 9 min (first RED commit `dac9a8d` 14:12:57 → last commit `c671ebf` 14:22:02, 2026-08-13)
- **Tasks:** 3/3 completed
- **Files modified:** 11 modified, 1 created (12 total)

## Accomplishments

- `scripts/gen_taxonomy_js.py::render()` now emits an `ORG_TYPE_DEFINITIONS` const into `n8n/code/taxonomy.generated.js`, generated from `config/taxonomy.yaml`'s `definition:` key — the same source both Python research prompts already render via `src.taxonomy.org_type_definitions_block()`.
- `COMPANIES_TARGET.research_system_prompt_fn_js` (the `Build Research Request` node) now renders those definitions into its RETURNED system-prompt string, verified by executing the node's own committed jsCode, not by grepping it — the QRIC / Racing NSW anchor examples from Phase 48-07 are present, and the strict nine-key `allowed_org_types` enum constraint is unchanged.
- `CONTACTS_TARGET.research_system_prompt_fn_js` was inspected and confirmed to never enumerate `lv_org_type` (it is a contact-role research prompt) — left byte-unchanged, as directed.
- `tests/fixtures/companies_jscode_frozen.json` re-baselined as an explicit, reviewed act; four of seven frozen node names changed (`Research Trigger Gate`, `Build Research Request`, `Validate Research Output`, `Merge Company` — all inline `taxonomy.generated.js`), three did not (`Judge Gate`, `Build Judge Request`, `Apply Judge Verdict`).
- `tests/n8n/orgTypeDefinitionsPrompt.test.mjs` added — a regression guard proven to have teeth via a negative control, designed to fail on a reverted `researchSystemPrompt()` even though the raw jsCode still carries the (then-unused) definitions const from the shared inlined module.
- `docs/WEB-RESEARCH-SPEC.md` §2's dated TX-10 block amended with a new dated entry recording the divergence closed at the build-source level (not yet deployed).
- Full offline suite green: `.venv/bin/python -m pytest -q` → 2705 passed, 128 skipped, 0 failed. `node --test tests/n8n/*.test.mjs` → 676 passed, 0 failed. Zero n8n executions, zero Anthropic calls, zero provider credits, zero HubSpot writes, zero deploys — this plan stayed fully offline as required.

## Task Commits

Each task was committed atomically (Tasks 1 and 3 as TDD RED/GREEN pairs, per plan):

1. **Task 49-03-01: gen_taxonomy_js.render() emits ORG_TYPE_DEFINITIONS**
   - RED: `dac9a8d` — `test(49-03): RED - assert generated taxonomy JS carries ORG_TYPE_DEFINITIONS`
   - GREEN: `41064de` — `feat(49-03): gen_taxonomy_js.render() emits ORG_TYPE_DEFINITIONS`
2. **Task 49-03-02: researchSystemPrompt() builds the allowed org-type line from definitions**
   - `986e58f` — `feat(49-03): researchSystemPrompt() renders org-type definitions`
3. **Task 49-03-03: node test on definition text, and the explicit fixture re-baseline**
   - `5356528` — `test(49-03): guard the emitted research prompt's org-type definitions`
   - `c671ebf` — `test(49-03): re-baseline companies_jscode_frozen.json -- explicit, reviewed act`

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `scripts/gen_taxonomy_js.py` — imports `ORG_TYPE_DEFINITIONS`, emits a new const after `ORG_TYPES`, adds it to `module.exports`
- `src/taxonomy.py` — corrected `org_type_definitions_block()`'s docstring, which previously (and now falsely) claimed the generator never reads the `definition` key
- `n8n/code/taxonomy.generated.js` — regenerated; new `ORG_TYPE_DEFINITIONS` const and export
- `scripts/build_cloud_workflows.py` — `COMPANIES_TARGET.research_system_prompt_fn_js` builds and returns an `lv_org_type option definitions:` line from `ORG_TYPE_DEFINITIONS`
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` — rebuilt from source (never hand-edited); the two artifacts this plan targeted
- `n8n/wf_scheduled_maintenance_cloud.json`, `n8n/wf_review_decision_cloud.json` — also rebuilt from source (never hand-edited); unplanned but correct side effect, see Deviations
- `docs/WEB-RESEARCH-SPEC.md` — new dated amendment under §2's TX-10 block
- `tests/fixtures/companies_jscode_frozen.json` — re-baselined (4 of 7 frozen nodes changed)
- `tests/n8n/orgTypeDefinitionsPrompt.test.mjs` — new regression guard, with negative control
- `tests/test_taxonomy_conformance.py` — new `test_tx10_generated_js_carries_org_type_definitions` assertion

## Decisions Made

1. **Contacts target left untouched.** `CONTACTS_TARGET.research_system_prompt_fn_js` is a contact-role (jobtitle/seniority) research prompt and does not enumerate `lv_org_type` at all — confirmed by direct read, not inferred. No edit was made there; recorded per the plan's own acceptance criterion.
2. **Committed two workflow JSON files beyond the plan's declared scope.** See Deviations below — this was the single substantive judgment call this plan required, made after consulting the advisor.
3. **Task 3's node test asserts on the returned prompt string, not raw jsCode.** The plan's literal action text ("assert two things: every org-type key ... appears, and every corresponding definition string ... also appears") would, if implemented as a raw-jsCode substring check, have been provably toothless — `n8n/code/taxonomy.generated.js`'s `ORG_TYPE_DEFINITIONS` const is inlined into `Build Research Request`'s jsCode regardless of whether `researchSystemPrompt()` uses it (the module is already inlined there for `ORG_TYPES`/`CONTENT_TYPES`), so a jsCode-text check would pass even on a fully reverted prompt function. The test instead executes the node's own committed jsCode (the `researchChainRowFlow.test.mjs` idiom) and asserts on `research_request_body.system`, the string actually sent to the model. This satisfies the plan's stated behavior line ("The test fails if the prompt is reverted to a bare key list") literally, where the substring-over-jsCode reading of the action text would not have.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — plan acceptance criterion did not match the actual dependency graph] Two extra n8n workflow JSON files changed and were committed**
- **Found during:** Task 49-03-02, after running `scripts/build_cloud_workflows.py` and checking `git status --short -- n8n/`
- **Issue:** The plan's acceptance criteria state "`git diff --name-only` after the build lists no file under `n8n/` other than the two generated workflow JSON files and the generated taxonomy module." In fact `n8n/wf_scheduled_maintenance_cloud.json` and `n8n/wf_review_decision_cloud.json` also changed, because both inline `n8n/code/taxonomy.generated.js` via the `ENRICH_APPLY_REVIEW` constant (the `Apply Review` node), for reasons unrelated to the research prompt (they need `EVIDENCE_GATED_ORG_TYPES` there, not `ORG_TYPE_DEFINITIONS`). Growing the shared inlined module in Task 1 grew every Code node that inlines it verbatim (`inline()` concatenates full stripped module text — RESEARCH SS1.1), not only the two enrichment workflows the plan's author anticipated.
- **Fix:** Committed the honestly-regenerated `wf_scheduled_maintenance_cloud.json` and `wf_review_decision_cloud.json` alongside the two planned files, rather than reverting them. Consulted the advisor before proceeding given this touches files outside the plan's declared `files_modified` list and contradicts a stated acceptance criterion. Reverting them would have manufactured exactly the "checked-in generated file stale vs. what the generator currently produces" drift class this repo's whole build-from-source philosophy exists to prevent — and no currency test exists for either of those two files to ever catch a later silent revert. The changed content is inert (an unused `ORG_TYPE_DEFINITIONS` const sitting beside the `EVIDENCE_GATED_ORG_TYPES` those two workflows actually use).
- **Files modified:** `n8n/wf_scheduled_maintenance_cloud.json`, `n8n/wf_review_decision_cloud.json`
- **Verification:** `git diff --stat` identical across two consecutive full builds (byte-reproducible); full offline `pytest -q` and `node --test tests/n8n/*.test.mjs` both green; no currency/frozen-fixture test references either file, so nothing else in the suite was put at risk.
- **Committed in:** `986e58f` (part of Task 49-03-02's commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — a bug in the plan's stated dependency-graph assumption, not in the implementation)
**Impact on plan:** No scope creep in behavior — the extra two files are a correct-by-construction side effect of the single source-of-truth change Task 1 made, not new functionality. Nothing was hand-edited; both extra files remain byte-reproducible from `scripts/build_cloud_workflows.py`. Neither file is deployed by this plan (offline throughout) or by Plan 49-04 (which deploys only `wf_enrichment_cloud.json`), so the live n8n instances of the scheduled-maintenance and review-decision workflows are unaffected until some future deploy of those specific workflows.

## Issues Encountered

None beyond the deviation above. All verify commands and acceptance criteria from the plan passed once implemented; no auth gates, no blocking issues, no architectural questions.

## User Setup Required

None — no external service configuration required. This plan made zero network calls, zero deploys, zero HubSpot writes (offline throughout, per plan constraint).

## Next Phase Readiness

Plan 49-04 has a deployable, byte-reproducible build of `n8n/wf_enrichment_cloud.json` waiting, and can spend its one declared deploy and bounce to make this live and close
`.planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md` with post-deploy evidence, per that plan's own must-haves. No blockers. `docs/WEB-RESEARCH-SPEC.md`'s new dated amendment already records that this plan built but did not deploy the fix, so Plan 49-04 does not need to re-derive that context.

---
*Phase: 49-re-score-strategy-reporting*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 13 files listed under Files Created/Modified plus this SUMMARY.md confirmed present on disk. All 5 task commit hashes (`dac9a8d`, `41064de`, `986e58f`, `5356528`, `c671ebf`) confirmed present in `git log --oneline --all`.
