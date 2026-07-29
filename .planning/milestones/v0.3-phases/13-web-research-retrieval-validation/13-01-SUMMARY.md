---
phase: 13-web-research-retrieval-validation
plan: 01
subsystem: enrichment
tags: [n8n, anthropic, web_search, taxonomy, mergeCompanies, hubspot, icp-scoring, python-js-parity]

requires:
  - phase: 12-taxonomy-single-source
    provides: "src/taxonomy.py normalizers (normalize_org_type_result, normalize_content_types), n8n/code/taxonomy.js + taxonomy.generated.js, NM-6 parity harness"
provides:
  - "src/taxonomy.py: validate_research_output() / to_provider_result() — the output contract for Claude web-research results (OC-1..4, TS-1..3, AT-2, ER-1)"
  - "n8n/code/webResearch.js: JS twin (validateResearchOutput/toProviderResult) + researchCandidateFromHttpItem (never-throws HTTP-response-to-candidate helper) + extractFinalJson"
  - "Four new n8n Code nodes + one HTTP node wired into wf_enrichment_local_live.json's companies branch: Research Trigger Gate, Build Research Request, Claude Web Research, Validate Research Output, IF Research Needed"
  - "ENRICH_MERGE_CO folds the research candidate into mergeCompanies via a second call (D6); mergeCompanies.js itself untouched"
  - "tests/n8n/webResearchFailure.test.mjs: offline proof that a failed research call is a SKIP, never a retry/throw"
  - "scripts/smoke_closed_won_research.py: non-gating live smoke against closed-won HubSpot accounts"
affects: [14-judge-wiring, 15-hubspot-property-migration, 16-scheduled-workflows-review-surface]

tech-stack:
  added: []
  patterns:
    - "Prompted free-text JSON + tolerant extraction (not forced tool_use) when mixing a client schema with Anthropic's web_search server tool in one turn"
    - "Cost gates (ALLOW_WEB_RESEARCH, MAX_WEB_RESEARCH_PER_RUN) enforced in a Code node BEFORE the HTTP node, never after"
    - "Tri-state coercion keyed on evidence-key presence, never a confidence threshold"
    - "Second mergeCompanies() call + shallow patch merge to fold an additional single-source candidate without touching the merge engine itself"

key-files:
  created:
    - n8n/code/webResearch.js
    - tests/fixtures/research_validation_cases.json
    - tests/n8n/webResearchFailure.test.mjs
    - scripts/smoke_closed_won_research.py
  modified:
    - src/schemas.py
    - src/taxonomy.py
    - tests/test_web_research_spec.py
    - tests/n8n/parity.test.mjs
    - scripts/build_cloud_workflows.py
    - src/web_research.py
    - n8n/wf_enrichment_local_live.json

key-decisions:
  - "Tri-state coercion (TS-1/2/3) is mechanical: lv_produces_content=false coerces to null iff evidence_by_field.lv_produces_content is absent — no confidence threshold anywhere (D2)."
  - "Retrieval prompt is free-text JSON extracted from the model's final text blocks, not a forced tool_use schema — mixing a client tool with web_search in one turn defers the search to a second round trip, incompatible with the single-HTTP-call n8n pattern (D3)."
  - "Research wiring lands ONLY in wf_enrichment_local_live.json — build_enrichment_cloud() has no companies branch yet; that lands in Phase 16 (D4)."
  - "mergeCompanies.js stays byte-identical; the research candidate folds in as a SECOND mergeCompanies() call in ENRICH_MERGE_CO, shallow-merged with the firmographic result (D6)."
  - "researchCandidateFromHttpItem (not a jsCode-eval harness) is the testable unit behind the Validate Research Output node — same pattern this repo already uses for every other inlined Code-node module (enrichmentGate.js, zoominfoToken.js, etc.)."

requirements-completed: [REQ-web-retrieval, REQ-evidence-by-field, REQ-tristate-content]

coverage:
  - id: D1
    description: "The 7 xfail(strict=True) acceptance tests in tests/test_web_research_spec.py flip to passing (7 flipped, markers removed); full pytest suite green with zero regressions"
    requirement: REQ-web-retrieval
    verification:
      - kind: unit
        ref: ".venv/bin/pytest tests/test_web_research_spec.py -q -> 22 passed, 0 xfailed, 0 xpassed"
        status: pass
      - kind: unit
        ref: ".venv/bin/pytest -q -> 139 passed, 0 xfailed, 0 xpassed, 0 failed"
        status: pass
    human_judgment: false
  - id: D2
    description: "to_provider_result carries evidence_by_field keyed per field (OC-1); TS-2/TS-3 tri-state coercion verified by direct spot-check"
    requirement: REQ-evidence-by-field
    verification:
      - kind: unit
        ref: "plan Task 1 spot-check script (evidence_by_field pass-through + TS-2 null coercion) -> Task1 spot-check OK"
        status: pass
    human_judgment: false
  - id: D3
    description: "JS twin webResearch.js matches Python validate_research_output/to_provider_result on the shared fixture table; deliberate-break guard genuinely fires"
    requirement: REQ-tristate-content
    verification:
      - kind: unit
        ref: "node --test tests/n8n/parity.test.mjs -> webResearch parity test passes; full node --test tests/n8n/*.test.mjs -> 51 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "n8n retrieval + validation nodes wired into wf_enrichment_local_live.json companies branch; rebuild deterministic; only Merge Company's jsCode changed among existing nodes"
    verification:
      - kind: unit
        ref: ".venv/bin/python scripts/build_cloud_workflows.py; git diff --exit-code n8n/ (second build is a no-op); node-diff check confirming only Merge Company jsCode changed"
        status: pass
      - kind: unit
        ref: "runtime smoke test (mocked $input/$vars/$env) of Research Trigger Gate / Build Research Request / Validate Research Output / Merge Company fold"
        status: pass
    human_judgment: false
  - id: D5
    description: "Research-failure skip-not-retry path proven offline; deliberate-break guard genuinely fires"
    verification:
      - kind: unit
        ref: "node --test tests/n8n/webResearchFailure.test.mjs -> 4 passed"
        status: pass
    human_judgment: false
  - id: D6
    description: "Closed-won live smoke script exits 0 with no credentials, never imported by pytest"
    verification:
      - kind: unit
        ref: "env -u HUBSPOT_PRIVATE_APP_TOKEN -u ANTHROPIC_API_KEY .venv/bin/python scripts/smoke_closed_won_research.py -> skip message, exit 0; .venv/bin/pytest -q unaffected"
        status: pass
    human_judgment: false

duration: 23min
completed: 2026-07-21
status: complete
---

# Phase 13 Plan 01: Web Research Retrieval & Validation Summary

**`lv_org_type` and `lv_produces_content` now resolve from Anthropic's native `web_search` tool through a vocabulary-safe, per-field-evidenced validation layer that feeds the existing evidence-gated `mergeCompanies` unchanged.**

## Performance

- **Duration:** 23 min (2026-07-21T13:24:33+10:00 → 2026-07-21T13:47:51+10:00, plus this docs pass)
- **Tasks:** 4/4 completed
- **Files modified:** 8 (2 new source files, 2 new test files, 1 new fixture, 1 new script, plus schema/taxonomy/build-script/prompt/workflow edits)

## Accomplishments

- `src/taxonomy.py` gained `validate_research_output()` and `to_provider_result()`, built on the Phase-12 normalizers, satisfying OC-1..4/TS-1..3/AT-2/ER-1. All 7 `xfail(strict=True)` acceptance tests in `tests/test_web_research_spec.py` flipped to passing; markers removed. `ProviderResult.evidence_by_field: Dict[str, str]` added additively.
- `n8n/code/webResearch.js` — a hand-written JS twin, parity-proven against Python on a shared fixture table (`tests/fixtures/research_validation_cases.json`) via a new `tests/n8n/parity.test.mjs` test. Also exports `researchCandidateFromHttpItem`/`extractFinalJson`, the reusable logic behind the production "Validate Research Output" Code node.
- Four new Code nodes + one HTTP node wired into `wf_enrichment_local_live.json`'s companies branch (Research Trigger Gate → IF Research Needed → [true: Build Research Request → Claude Web Research → Validate Research Output] / [false: straight through] → Merge Company), gated by `ALLOW_WEB_RESEARCH` + `MAX_WEB_RESEARCH_PER_RUN` enforced BEFORE the HTTP call. `mergeCompanies.js` stays byte-identical; `ENRICH_MERGE_CO` folds the research candidate in via a second `mergeCompanies()` call.
- `tests/n8n/webResearchFailure.test.mjs` proves offline that a failed/empty/error-shaped research HTTP response never throws and the company continues through Merge Company exactly as it would with research disabled.
- `scripts/smoke_closed_won_research.py` — a non-gating, env-gated, read-only live smoke tool that flags an evidenced `false` on a closed-won HubSpot account (ground truth for `lv_produces_content=true`) as a red-flag exit code 2.

## Task Commits

Each task was committed atomically:

1. **Task 1: Python output-contract** — `9b892c2` (feat) — `validate_research_output`/`to_provider_result` in `src/taxonomy.py`, `ProviderResult.evidence_by_field`, 7 xfail markers removed.
2. **Task 2: JS twin + shared fixture + parity test** — `a17e207` (feat) — `n8n/code/webResearch.js`, `tests/fixtures/research_validation_cases.json`, `tests/n8n/parity.test.mjs` extended.
3. **Task 3: n8n retrieval + validation nodes wired into local-live** — `dc02858` (feat) — four new Code node bodies + one HTTP node in `scripts/build_cloud_workflows.py`, wired into `build_enrichment_local_live()`'s companies branch; `src/web_research.py` prompt parity update.
4. **Task 4: deliberate-break skip proof + closed-won live smoke** — `a63283a` (feat) — `tests/n8n/webResearchFailure.test.mjs`, `scripts/smoke_closed_won_research.py`.
5. **Fixup: rebuild workflow for Task 4 doc-comment change** — `a13a101` (chore) — `n8n/wf_enrichment_local_live.json` rebuilt so it matches source after a comment-only edit in Task 4 (see Deviations).

**Plan metadata:** (this commit) — docs: complete plan.

## Files Created/Modified

- `src/schemas.py` — additive `ProviderResult.evidence_by_field: Dict[str, str]`.
- `src/taxonomy.py` — `validate_research_output`, `to_provider_result`, `ALLOWED_REPRESENTS`.
- `tests/test_web_research_spec.py` — 7 `@unbuilt` markers removed.
- `n8n/code/webResearch.js` — new JS twin + `researchCandidateFromHttpItem`/`extractFinalJson`.
- `tests/fixtures/research_validation_cases.json` — new shared Python/JS fixture table.
- `tests/n8n/parity.test.mjs` — new `pyResearch` oracle helper + webResearch parity test.
- `scripts/build_cloud_workflows.py` — `ENRICH_RESEARCH_GATE`, `ENRICH_BUILD_RESEARCH_REQUEST`, `ENRICH_VALIDATE_RESEARCH`, `_if_bool_node`, `_live_http(timeout=...)`, `ENRICH_MERGE_CO` research fold, `strip_module()` multi-line-require fix, `build_enrichment_local_live()` rewiring, Phase-16 note on `build_enrichment_cloud()`.
- `src/web_research.py` — `RESEARCH_SYSTEM` prompt updated for entity_resolution/evidence_by_field parity with the n8n production prompt.
- `n8n/wf_enrichment_local_live.json` — regenerated; 5 new nodes in the companies branch, `Merge Company`'s `jsCode` changed, every other node byte-identical.
- `tests/n8n/webResearchFailure.test.mjs` — new offline failure-path test.
- `scripts/smoke_closed_won_research.py` — new non-gating live smoke tool.

## Decisions Made

- **D2 (tri-state, plan-authored):** `lv_produces_content=false` coerces to `null` iff `evidence_by_field.lv_produces_content` is absent — never a confidence threshold. Implemented exactly as specified in both Python and JS.
- **D3 (retrieval shape, plan-authored):** Prompted free-text JSON + tolerant extraction, not a forced `tool_use` schema, to keep the whole retrieval+validation flow a single HTTP call.
- **D4 (wiring scope, plan-authored):** Confirmed by reading `build_enrichment_cloud()` — it has no companies branch — so research nodes land only in `wf_enrichment_local_live.json`, with a builder comment noting the Cloud workflow picks this up when its companies branch lands (Phase 16).
- **D6 (merge fold, plan-authored):** Research candidate folds into `mergeCompanies` via a second call in `ENRICH_MERGE_CO`, shallow-merged with the firmographic result — `mergeCompanies.js` itself never touched.
- **Task 4 test design (executor decision):** The plan's "same extract-the-node-code harness the existing tests/n8n/*.test.mjs files use" does not describe an actual harness present in this repo (verified: no existing test evals a node's `jsCode` string extracted from a built workflow JSON — every existing test requires() a pure JS module directly, e.g. `zoominfoToken.js`, `enrichmentGate.js`). Rather than inventing a new eval-based harness, the validation logic itself (`researchCandidateFromHttpItem`) was made a first-class exported function from `n8n/code/webResearch.js`, and the Code node body is a one-line wrapper calling it. `tests/n8n/webResearchFailure.test.mjs` requires and tests that function directly — consistent with every other Code-node test in this repo, and the actual logic under test is identical to what runs inside the built node.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `strip_module()` did not handle a multi-line destructuring `require`**
- **Found during:** Task 3, first runtime smoke test of the built "Validate Research Output" node body.
- **Issue:** `n8n/code/taxonomy.js`'s `require` statement spans 4 lines (`const {\n  ORG_TYPES, ...\n} = require(...)`), but `_REQUIRE_RE` in `scripts/build_cloud_workflows.py` only matched a single-line form. Task 3 was the first time `taxonomy.js` was ever `inline()`d into a Code node (previously only tested directly via `require()`), so this latent bug had never been exercised. Inlining left orphaned destructuring-target lines in the generated node body — a JavaScript `SyntaxError`.
- **Fix:** Added multi-line-require handling to `strip_module()` (a small state machine: a bare `const {` opening line starts a skip region that ends at the line containing `require(`). Verified no other `n8n/code/*.js` module has this pattern, so the fix is a no-op for every other inlined module.
- **Files modified:** `scripts/build_cloud_workflows.py`.
- **Verification:** Rebuilt; `node --check` on the extracted node body (via a mocked-`$input` runtime smoke test) succeeds; second build is byte-for-byte identical to the first (diffed directly).
- **Committed in:** `dc02858` (Task 3 commit).

**2. [Rule 1 - Bug] `toProviderResult({})` does not actually yield `matched:false`**
- **Found during:** Task 3, runtime smoke test of the Validate Research Output → Merge Company path.
- **Issue:** The plan states `toProviderResult({})` on failure gives "i.e. matched:false" — but an empty dict `{}` IS a dict, so `validate_research_output`'s `isinstance(raw, dict)` guard (which is what actually produces `matched:False`, per OC-4) does not fire; the function falls through to the "else" branch where `matched` defaults to `True` (`bool(raw.get("matched", True))`). Calling `toProviderResult({})` on every research-HTTP failure path would have silently produced `matched:true` candidates from failed calls.
- **Fix:** `researchCandidateFromHttpItem` now calls `toProviderResult({matched: false})` explicitly on every failure path (both branches), matching the plan's stated intent unambiguously regardless of the dict-vs-non-dict OC-4 quirk.
- **Files modified:** `n8n/code/webResearch.js`.
- **Verification:** Direct runtime check of all three Task-4 failure shapes (n8n execution-error item, Anthropic HTTP error body, empty content) confirms `matched:false` post-fix; `tests/n8n/webResearchFailure.test.mjs` asserts this for all four cases.
- **Committed in:** `dc02858` (Task 3 commit).

**3. [Rule 3 - Blocking] Rebuild left stale after a Task 4 comment-only edit**
- **Found during:** Post-Task-4 phase-verification pass (rerunning `git diff --exit-code n8n/` after rebuild).
- **Issue:** Task 4 corrected a stale docstring comment in `n8n/code/webResearch.js` (describing `toProviderResult({})` instead of the actual `toProviderResult({matched:false})` call from the Task 3 fix above) but committed it without rebuilding `wf_enrichment_local_live.json`, which inlines that file — leaving the committed workflow JSON's comment text stale relative to source. A rebuild after the Task 4 commit produced a one-line diff.
- **Fix:** Rebuilt and committed the refreshed `n8n/wf_enrichment_local_live.json` in a small follow-up commit.
- **Files modified:** `n8n/wf_enrichment_local_live.json`.
- **Verification:** `git diff --exit-code n8n/` clean after the fixup commit; full pytest (139) and node (51) unaffected.
- **Committed in:** `a13a101` (separate small commit, not folded into Task 4's commit per the "create NEW commits, don't amend" rule).

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 3 blocking/rebuild-staleness).
**Impact on plan:** All three were caught by executor-added runtime smoke tests that went beyond the plan's own verify blocks (the plan's verification commands check `node --check` syntax and `git diff --exit-code n8n/` after a clean two-step rebuild, but do not execute the generated node bodies against a mocked `$input`/`$vars`/`$env`, which is what surfaced bugs #1 and #2). No scope creep — all three are corrections that keep the delivered behavior matching the plan's stated intent.

## Issues Encountered

None beyond the three auto-fixed deviations above.

## Verification Evidence

```
.venv/bin/pytest tests/test_web_research_spec.py -q
  -> 22 passed (15 prior + 7 flipped), 0 xfailed, 0 xpassed, 0 failed

.venv/bin/pytest -q
  -> 139 passed, 0 xfailed, 0 xpassed, 0 failed, 1 warning (pre-existing httpx deprecation)

node --test tests/n8n/*.test.mjs
  -> 51 passed, 0 failed (46 baseline + 1 webResearch parity + 4 webResearchFailure)

.venv/bin/python scripts/build_cloud_workflows.py  (run twice, diffed directly)
  -> IDENTICAL — rebuild is deterministic
git diff --exit-code n8n/
  -> clean after each rebuild

Node-diff check (only wf_enrichment_local_live.json changed; only Merge Company's jsCode changed):
  n8n/wf_contact_ingest_cloud.json: unchanged
  n8n/wf_contact_ingest_local.json: unchanged
  n8n/wf_enrichment_cloud.json: unchanged
  n8n/wf_enrichment_local.json: unchanged
  n8n/wf_enrichment_local_live.json: changed=['Merge Company']
    added=['Research Trigger Gate','IF Research Needed','Build Research Request',
            'Claude Web Research','Validate Research Output']

git diff --stat n8n/code/mergeCompanies.js  -> (empty) — byte-identical, confirmed

Task 1 spot-check:
  r = to_provider_result({'data':{'lv_org_type':'peak body','lv_produces_content':False},
                           'evidence_by_field':{'lv_org_type':'https://x/about'}})
  r.evidence_by_field == {'lv_org_type': 'https://x/about'}   [PASS]
  r.data['lv_org_type'] == 'governing_body_league'            [PASS]
  r.data['lv_produces_content'] is None                        [PASS]
  -> "Task1 spot-check OK"

Task 2 deliberate-break proof (parity guard):
  perl -0pi -e 's/&&\s*!evidenceByField\.lv_produces_content//' n8n/code/webResearch.js
  node --test --test-name-pattern="webResearch.*parity" tests/n8n/parity.test.mjs
  -> pass 0, fail 1 (genuine AssertionError, TS-3 evidenced-false case:
     actual lv_produces_content:null vs expected:false)
  cp /tmp/webResearch.bak n8n/code/webResearch.js   (restored)
  git diff --exit-code n8n/code/webResearch.js -> clean; re-run -> 47 passed

Task 4 deliberate-break proof (failure-path guard):
  Replaced researchCandidateFromHttpItem's guard+try/catch with a naive
  `extractFinalJson(item.content); toProviderResult(parsed)` call chain (no protection).
  node --test tests/n8n/webResearchFailure.test.mjs
  -> pass 1, fail 3 — each failure a genuine uncaught SyntaxError naming the broken case
     (error-key item, empty content, malformed-text control case)
  cp /tmp/webResearch_task4.bak n8n/code/webResearch.js  (restored)
  git diff --exit-code n8n/code/webResearch.js -> clean; re-run -> 4 passed

Smoke script (no credentials):
  env -u HUBSPOT_PRIVATE_APP_TOKEN -u ANTHROPIC_API_KEY .venv/bin/python scripts/smoke_closed_won_research.py
  -> "skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN and ANTHROPIC_API_KEY must both be set..."
     exit 0
  .venv/bin/pytest -q (script never imported) -> 139 passed, unaffected

Architecture guard (api.anthropic.com already allowlisted, no new host):
  .venv/bin/pytest tests/test_architecture_guard.py -q -> 17 passed
```

## User Setup Required

None — no external service configuration required. (Live Anthropic web-research calls, when eventually enabled via `ALLOW_WEB_RESEARCH=true` in the n8n Cloud instance, reuse the existing `ANTHROPIC_API_KEY` already provisioned for the dev oracle — no new credential.)

## Next Phase Readiness

- Phase 14 (Judge Wiring) can build directly on `row.research_candidate` and the `Validate Research Output` node's output shape — the Sonnet escalation path (RO-1/RO-2/JG-1..3) has a validated, evidence-keyed candidate to reason over, exactly as the spec assumes.
- Phase 15 (HubSpot Property Migration) unblocks RT-5 (research caching by domain) once `lv_org_type_verified_at`/`lv_produces_content_verified_at` exist — until then this phase's research nodes re-research every eligible company every run, as designed and documented.
- Phase 16 (Scheduled Workflows) is the natural home for extending `build_enrichment_cloud()` with a companies branch, at which point the Phase-13 research nodes land there too (builder comment already notes this).
- No blockers. Both bugs found during verification (multi-line require, `toProviderResult({})` matched semantics) are now fixed and covered by the runtime smoke test / `webResearchFailure.test.mjs` respectively — a future contributor extending `ENRICH_VALIDATE_RESEARCH` or adding another `inline("taxonomy.js", ...)` consumer will not silently reintroduce either.

## Self-Check: PASSED

- `src/taxonomy.py` — FOUND (validate_research_output, to_provider_result present)
- `n8n/code/webResearch.js` — FOUND
- `tests/fixtures/research_validation_cases.json` — FOUND
- `tests/n8n/webResearchFailure.test.mjs` — FOUND
- `scripts/smoke_closed_won_research.py` — FOUND
- `n8n/wf_enrichment_local_live.json` — FOUND (5 new nodes confirmed via node-diff check)
- Commit `9b892c2` — FOUND in `git log --oneline`
- Commit `a17e207` — FOUND in `git log --oneline`
- Commit `dc02858` — FOUND in `git log --oneline`
- Commit `a63283a` — FOUND in `git log --oneline`
- Commit `a13a101` — FOUND in `git log --oneline`

---
*Phase: 13-web-research-retrieval-validation*
*Completed: 2026-07-21*
