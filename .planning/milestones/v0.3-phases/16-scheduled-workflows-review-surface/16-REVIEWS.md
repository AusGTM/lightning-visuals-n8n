---
phase: 16
reviewers: [gpt-5-6-sol, kimi-k3, gemini-3-6-flash]
reviewed_at: 2026-07-23T03:11:41Z
plans_reviewed: [16-01-PLAN.md, 16-02-PLAN.md]
adapter: opencode
provider: openrouter
---

> Note: gpt-5-6-sol, kimi-k3, and gemini-3-6-flash all run through the opencode adapter (OpenRouter). Their consensus is cross-model, not cross-tool.

# Cross-AI Plan Review — Phase 16

## OpenCode Review (gpt-5-6-sol)

**Model:** openrouter/openai/gpt-5.6-sol

**Summary**
The two-plan split is sensible, and the plans correctly identify the credential migration, missing SJ-3 properties, schedule predicates, and RT-5 test gap. However, the plan set is not execution-ready. Several static and BFS tests could pass while the Cloud workflow remains unsafe or nonfunctional: the proposed company branch begins with hard-coded fixture companies, credential provisioning is not connected to node credential IDs, HubSpot search/write nodes are placeholders, scheduled searches do not dispatch records into enrichment, and review approval can overwrite newer manual data. These are production blockers because Phase 16 introduces the first live HubSpot record writes.

**Strengths**
- The two sequential plans separate deployment plumbing from scheduled business logic and correctly make 16-02 depend on 16-01.
- The ZoomInfo decision checkpoint is appropriate. The current helper only sets generic authentication types and cannot solve Code-node secret access by itself (`scripts/build_cloud_workflows.py:2018-2042`).
- The plans correctly identify that the Cloud workflow is currently contacts-only; the builder explicitly documents this gap (`scripts/build_cloud_workflows.py:2045-2049`).
- SJ-1 and SJ-3 use the correct HubSpot search logic: OR across filter groups for unresolved fields and AND within one group for requested/not-running.
- The direct RT-5 tests are valuable. `decideAction` deterministically handles missing, stale, fresh, and present-but-never-verified values (`n8n/code/enrichmentGate.js:55-106`).
- Separating dedupe classification from writes is correct. `dedupeSweep` is pure and returns review IDs without mutating HubSpot (`n8n/code/dedupeSweep.js:28-76`).
- The proposed two-key gates and offline mocked tests follow the safe precedent established by `scripts/sync_hubspot_properties.py`.
- The plans consistently avoid derived ICP fields in SJ predicates, preserving the Approach-C scheduling boundary.

**Concerns**
- **HIGH: The proposed Cloud company branch starts with hard-coded fixture companies.** `ENRICH_EMIT_COMPANIES` ignores its input and always emits Harvey Norman, Racing NSW, Melbourne Racing Club, Australian Turf Club, and FanDuel (`scripts/build_cloud_workflows.py:1247-1264`). Porting this node as directed would cause every webhook execution to process those companies rather than the company represented by the event. A BFS reachability test would certify the wrong behavior.
- **HIGH: The webhook is not production-shaped or authenticated.** The Cloud webhook has no signature/shared-secret verification and immediately sends its body to `Build Identity` (`scripts/build_cloud_workflows.py:2055-2064`), which expects direct fields (`email`, `domain`, `firstname`), not a HubSpot event array containing `objectId` (`:662-681`). This exposes provider spend and future CRM writes to unauthenticated or replayed requests.
- **HIGH: Credential provisioning has no credential-binding step.** `_http_node` sets `genericCredentialType` but does not include a node `credentials` object with a provisioned ID (`:2018-2042`); native HubSpot nodes likewise have no binding (`:2067-2073`, `:2156-2168`). Deploying unchanged JSON leaves nodes unbound unless the plan explicitly resolves IDs and injects them.
- **HIGH: The existing HubSpot nodes are placeholders, not a proven live-write pattern.** Contact search has no filters, create maps only email, update has an empty `updateFields` (`:2067-2073`, `:2156-2168`). Porting this does not prove the calculated property patch reaches HubSpot.
- **HIGH: Lookup failures can be mistaken for confirmed absence and route to create.** Search nodes use `continueRegularOutput`; adapters turn missing/unrecognized results into `{}` (`:778-795`, `:1303-1318`); `decideAction({})` returns `create` (`enrichmentGate.js:61-64`). A 401/timeout/rate-limit/malformed response could create a duplicate.
- **HIGH: Existing HubSpot record IDs are discarded.** Company/contact adapters keep only `results[0].properties` and drop the top-level ID (`:1303-1318`, `:778-795`). An update path cannot reliably identify its target record.
- **HIGH: The six planned config constants omit the actual write-safety controls.** The workflow already routes `create`/`enrich` directly to HubSpot nodes (`:2150-2198`). Need explicit `ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_CANONICAL_WRITES`, create switches, and a test-record allowlist. Activation alone must not become the write-enable switch.
- **HIGH: Plan 16-02 searches for records but does not dispatch them into enrichment.** `Company Gate` only calculates `create`/`enrich`/`skip` from `row.existingRecord` (`:1328-1341`); a scheduled-maintenance node cannot jump into the separate webhook graph. SJ-1/2/3 can pass predicate tests while never calling providers, research, merge, or writeback.
- **HIGH: Review approval targets the wrong decisions / bypasses non-clobber.** Fields requiring approval are emitted as `needs_review`, but only `promote` decisions enter `canonicalPatch` (`mergeCompanies.js:107-136`, `:209-224`), so re-applying recorded `promote` decisions clears the queue without applying the reviewed candidate; and applying stored historical values without refetching can overwrite a newer manual edit.
- **HIGH: Approach C is not structurally guaranteed by `mergeCompanies`.** Unknown fields default to `fill_blank_only` (promotes when blank; `:126-130`, `:181-189`); policy still promotes `lv_anti_icp_flag`/`lv_anti_icp_reason` as veto outputs (`:46-51`). Review/final-write boundaries need a positive allowlist of permitted ICP-input properties.
- **MEDIUM:** SJ-2 misses present-but-never-verified records (add `NOT_HAS_PROPERTY` for both `_verified_at`); SJ-3 may miss requested records with blank status; scheduled searches have no pagination/batching; dedupe output can't feed one Update node directly and reads the obsolete `linkedin_url` key (canonical is `lv_linkedin_url`); "Active" conflates with source-manifest membership and doesn't prove activation; wrong-instance guard fails open if `N8N_EXPECTED_URL` defaults to `N8N_URL`.
- **LOW:** "Six credentials" is inaccurate — 6 secret values but ~5 credential objects (ZoomInfo holds client ID + secret); deploying every top-level `wf_*.json` would import local fixture workflows.

**Risk Assessment: HIGH.** Architectural direction is viable, but implementing literally could expose an unauthenticated write-capable webhook, process hard-coded fixtures, deploy unbound credentials, create duplicates after lookup failures, and overwrite newer manual CRM values via approval. The proposed tests emphasize static graph shape and pure functions, so they would not detect several of these.

---

## OpenCode Review (kimi-k3)

**Model:** openrouter/moonshotai/kimi-k3

**Summary**
An unusually well-grounded plan set: ~20 line citations in `scripts/build_cloud_workflows.py` all verified accurate; the 6-secret/6-flag inventory matches the built JSON exactly; the headline research findings (RT-5 already implemented, SJ-3 blocked on missing properties, ZoomInfo's Code-node credential impossibility) all verified. The split (deployable → complete, sequential waves in one phase) is correctly justified by shared-file contention on `build_cloud_workflows.py`. However, two mechanical gaps sit on the critical path: **the producer side of the review loop is specified in neither plan**, and **the credential-ID binding step between provisioning and deploy is missing**. Several MEDIUM wiring details would surface mid-execution. All fixable within the existing task structure.

**Strengths**
- **Citation accuracy is excellent** — verified `inline`:67, `code_node`:361, `chain`:369, `ENRICH_CO_GATE`:1328, `_http_node`:2018, `build_enrichment_cloud`:2050 (contacts-only, zero company nodes), etc. Materially de-risks execution.
- **RT-5 "already built" is correct and is the phase's best insight** — `enrichmentGate.js:83-93` enforces staleness via `_verified_at` (unknown→stale); `mergeCompanies.js:205-207` stamps `cacheKeys` regardless of decision. Criterion 9 genuinely is scheduling + test authoring.
- **SJ-3 property gap is real and correctly promoted into 16-01 Task 3** — read all 400 lines of `config/hubspot_properties.yaml`: zero `lv_enrichment_requested`/`lv_enrichment_status`; 9 review props exist on both objects. 16-02 Task 1 `<precondition>` declares the dependency.
- **`$env`/`$vars` inventory is exact** — matches the research table row-for-row; the `$vars || $env` defensive fallback is confirmed present.
- **ZoomInfo spike-gated checkpoint is the right structure** — `zoominfoToken.js` is pure with tests protecting re-mint-once-on-401; `checkpoint:decision` before implementing exactly one path.
- **Approach C is real in source** — `mergeCompanies.js:46-49` omits `lv_icp_fit_score`/`lv_icp_tier`; both plans add negative tests.
- **Two-key gate + wrong-instance guard mirrors a proven idiom** (`sync_hubspot_properties.py:47-60`), copied faithfully incl. skip-to-exit-0.
- Frozen-files prohibition is honest; the companies port truly is a topology copy.

**Concerns**
- **HIGH — Review-loop producer side is specified in neither plan.** 16-02 Task 4 consumes `lv_enrichment_review_candidate_json` and re-applies recorded `promote` decisions, but nothing produces those flags/files. `mergeCompanies`' `canonicalPatch` contains only `promote` decisions (`:209-211`), so if the decide node applies `canonicalPatch` on a needs_review run, reviewApply's "re-apply promote decisions" is a permanent no-op — the loop only works if the decide node **holds** canonical writes when any decision is `needs_review`, which neither plan mentions. The phase can pass every acceptance test while the §22.2 loop (criterion 3) is never exercised end-to-end. **Fix:** 16-01 Task 5's `ENRICH_DECIDE_CO_CLOUD` must, on any `needs_review`, write `lv_enrichment_needs_review=true`, `lv_enrichment_review_reason`, `lv_enrichment_review_candidate_json=stableStringify(decisions)`, and define hold-vs-apply explicitly; 16-02 Task 4's test must assert the apply consumes exactly what the producer writes.
- **HIGH — Credential-ID binding step missing between provisioning and deploy.** Zero `"credentials"` keys in both built Cloud JSONs. Lusha/Apollo/Anthropic are three *different* credentials of the same `httpHeaderAuth` type, so binding needs a node-name→credential-name map, not just type matching. **Fix:** provision writes a name→ID map (or re-GETs `/api/v1/credentials`); deploy attaches `"credentials": {...}` per node before POST/PUT; or document per-node UI binding in the runbook.
- **MEDIUM — SJ branches have no specified terminal action.** Nothing connects scheduled discovery to enrichment execution (the companies pipeline lives in the *webhook* workflow). Cleanest: SJ-1/SJ-2 set `lv_enrichment_requested=true` and let SJ-3's poller / an Execute-Workflow node do the work — but decide and write it down.
- **MEDIUM — SJ-2's Company Gate wiring misses the Adapt step.** `ENRICH_CO_GATE` reads `row.existingRecord`, produced by `ENRICH_ADAPT_CO_SEARCH` (`:1303-1319`). Fed raw search results, `existingRecord` is `{}` → `action="create"` for every row, and neither new test catches it.
- **MEDIUM — RT-5 test fixture inherited from the research is buggy.** `REQUIRED = ["lv_org_type","lv_produces_content"]`; a blank required field short-circuits to `enrich`. The research's fresh fixture sets only `lv_org_type`, so the first direct `decideAction` test would fail (or be silently "fixed"). Fresh fixture must set both required fields + both `_verified_at`.
- **LOW:** env-guard regex evadable (use `\$env\b|\$vars\b`); native HubSpot search node unproven as a *configured* search (`NOT_HAS_PROPERTY`/epoch-ms `LT` unverified); company record ID sourcing for Update nodes unaddressed (`hs_object_id` not requested); `lv_enrichment_status` enum drift vs CLAUDE.md §4.1 (missing `skipped`); Task 3 precondition miscount (35 vs 33/2); reviewApply lacks malformed-JSON fail-closed + apply-time re-check; dedupe branch object type unspecified (contacts-shaped).

**Risk Assessment: MEDIUM.** Exceptionally well-verified against source; safety architecture sound and idiomatic. Risk concentrates in two seams — the review-loop producer end (between 16-01 Task 5 and 16-02 Task 4) and credential binding. Both are one-paragraph-plus-one-test fixes, not re-planning events. Downgrade to LOW once those two + the MEDIUM wiring details (SJ terminal actions, gate Adapt step, RT-5 fixture) are folded in.

---

## OpenCode Review (gemini-3-6-flash)

**Model:** openrouter/google/gemini-3.6-flash

**Summary**
A well-structured, two-wave strategy. 16-01 addresses deployment infrastructure (secrets→credentials, build-time flag constants, companies-branch port, API-driven deploys under a two-key gate, control-property manifest completion). 16-02 implements the background reconciliation layer (SJ-1/2/3 triggers, classify-only dedupe, RT-5 staleness proof, §22.2 review loop). Strict adherence to zero-middleware principles (AR-1..AR-4) and Approach C. Addressing two minor edge cases makes execution airtight.

**Strengths**
- **Single-source flag + secret parity** (Task 4): `CONFIG_FLAG_DEFAULTS` + `SECRET_ENV_NAMES` across both builders prevents drift, enforced offline via `tests/test_builder_flag_parity.py`.
- **Strict Approach C** — `mergeCompanies.js:46-49` excludes derived fields; neither `ENRICH_DECIDE_CO_CLOUD` nor `reviewApply.js` can emit them.
- **Accurate HubSpot `filterGroups` logic** — SJ-3 AND within one group; SJ-1 OR across groups.
- **Classify-only maintenance sweep** preserves `dedupeSweep.js` as a pure function, verified via `dedupeSweepWiring.test.mjs`.
- **Hermetic testing & safety gates** — deploy/provision scripts replicate `sync_hubspot_properties.py:50-61` two-key gate + graceful skip.

**Concerns**
- **[MEDIUM] Weak default in wrong-instance guard.** `_instance_ok()` uses `os.getenv("N8N_EXPECTED_URL", N8N_URL)` → when unset, `N8N_URL == N8N_URL` is always True, allowing execution against an unintended instance (unlike the hardcoded `EXPECTED_PORTAL_ID`).
- **[MEDIUM] Unhandled truncated/malformed JSON in `reviewApply.js`.** A record hitting HubSpot's 60,000-char property limit crashes the node on `JSON.parse`.
- **[LOW] Unhandled schema-introspection HTTP failures in `provision_n8n_credentials.py`** — a differing credential-type name / 400 / 404 aborts provisioning without a clean banner.

**Suggestions:** require `N8N_EXPECTED_URL` explicit (or validate against the `.n8n.cloud` domain); wrap `JSON.parse` in try/catch returning empty patches + a `malformed review candidate JSON` reason; wrap schema introspection in try/except with clean status logging.

**Risk Assessment: LOW.** Thorough codebase grounding, strict AR-1..AR-4 + Approach C, comprehensive offline unit + graph-structure coverage before any live execution.

---

## Consensus Summary

Three OpenRouter models via one opencode adapter (cross-model, not cross-tool). All three ran source-grounded against the repo. **Risk ratings diverged sharply: gpt-5.6-sol HIGH · kimi-k3 MEDIUM · gemini-3.6-flash LOW** — driven by how deep each traced into the *existing* Cloud builder's placeholder state (sol went deepest).

### Agreed Strengths (2+ reviewers)
- Two-plan split (deployable → complete, one phase) correctly justified by shared-file contention on `build_cloud_workflows.py`. *(all 3)*
- Approach C is real in source — `mergeCompanies.js:46-49` excludes `lv_icp_fit_score`/`lv_icp_tier`; both plans add negative tests. *(all 3)*
- SJ filterGroups AND/OR logic correct. *(all 3)*
- Two-key gate mirrors the proven `sync_hubspot_properties.py` idiom. *(all 3)*
- Dedupe classify-only preserves the pure `dedupeSweep.js`. *(all 3)*
- RT-5 "already built" finding is correct — criterion 9 = scheduling + test, not new merge logic. *(sol, kimi)*
- ZoomInfo spike-gated checkpoint is the right structure. *(sol, kimi)*

### Agreed Concerns (2+ reviewers — highest priority)
1. **Credential-ID binding missing between provisioning and deploy** *(sol HIGH, kimi HIGH)* — built Cloud JSONs carry zero `credentials` blocks; nodes import unbound. Lusha/Apollo/Anthropic share `httpHeaderAuth`, so a node→credential map is required, not just type matching.
2. **Review-loop producer side unspecified** *(sol HIGH, kimi HIGH)* — nothing writes `lv_enrichment_needs_review`/`lv_enrichment_review_candidate_json`; `canonicalPatch` holds only `promote` decisions, so reviewApply is a no-op unless the decide node *holds* canonical writes on `needs_review`. The §22.2 loop (criterion 3) can go unexercised while all tests pass. This is the seam between 16-01 Task 5 and 16-02 Task 4.
3. **Non-clobber breaks at approval time** *(sol HIGH, kimi LOW/MEDIUM, gemini MEDIUM)* — applying stored candidate values without refetching can overwrite a newer manual edit; also no malformed/truncated-JSON fail-closed path. Needs compare-and-set at apply + try/catch.
4. **Wrong-instance guard fails open** *(sol MEDIUM, gemini MEDIUM)* — `N8N_EXPECTED_URL` defaulting to `N8N_URL` makes the check always pass; require it explicit.
5. **Scheduled searches don't dispatch into enrichment / Company Gate input contract** *(sol HIGH, kimi MEDIUM)* — SJ branches end at search/gate; no terminal action wires discovery into the webhook enrichment graph, and raw search rows fed to `ENRICH_CO_GATE` (no Adapt step) yield `{}`→`create`.

### Divergent Views (worth investigating)
- **sol-only HIGH blockers** *(not surfaced by kimi/gemini)*: the ported `ENRICH_EMIT_COMPANIES` emits **hard-coded fixture companies** (Harvey Norman, Racing NSW, …) ignoring its input; the Cloud webhook is **unauthenticated** and shaped for direct fields not a HubSpot event array; existing HubSpot search/create/update nodes are **empty placeholders**; adapters **discard the record ID**; lookup failure → `create` **duplicate**. If accurate, these are the difference between MEDIUM and HIGH — worth verifying against `build_cloud_workflows.py:1247-1264` / `:2055-2073` before execution.
- **RT-5 fixture bug** — only kimi caught that the research's "fresh" fixture sets one of two REQUIRED fields, so the first direct `decideAction` test would fail as written.
- **Risk rating spread** (HIGH/MEDIUM/LOW) reflects trace depth, not disagreement on facts — the underlying findings are largely additive across the three.

### Recommended next step
Feed this back into planning: `/gsd-plan-phase 16 --reviews`. The planner must incorporate or explicitly reject each actionable finding — priority the two HIGH seams (credential binding, review-loop producer), then verify sol's fixture-company / unauthenticated-webhook / placeholder-node claims against source (they change the risk rating), then the wrong-instance-guard default, RT-5 fixture, and SJ terminal-action wiring.
