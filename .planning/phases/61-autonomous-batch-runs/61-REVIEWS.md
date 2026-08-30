---
phase: 61
reviewers: [gpt-5-6-sol, kimi-k3, gemini-3-6-flash]
reviewed_at: 2026-08-30T00:13:18Z
plans_reviewed: [61-01-PLAN.md, 61-02-PLAN.md, 61-03-PLAN.md, 61-04-PLAN.md, 61-05-PLAN.md, 61-06-PLAN.md]
---

# Cross-AI Plan Review — Phase 61

> Note: gpt-5-6-sol, kimi-k3 and gemini-3-6-flash all share the opencode adapter; their consensus is cross-model, not cross-tool.

## OpenCode Review (gpt-5-6-sol)

I’ll validate the plans against the referenced implementation paths, prioritizing execution-model feasibility, identity-lane wiring, confidence semantics, persistence/resume behavior, and the one-grant association flow.
# Cross-AI Plan Review

## Overall Assessment

The plans show strong safety discipline, careful treatment of generated workflows, and a good understanding of the LinkedIn identity defect. Plans **61-02 and 61-03 are close to executable** after targeted corrections.

Plans **61-04 through 61-06 are not yet implementation-ready**. They define helpers, documentation, and tests without identifying the production orchestration that invokes those helpers. They also assume confidence and judge signals cross from n8n to the plugin when those signals currently remain internal to n8n. The async plans further commit to local run-state artifacts before 61-01’s checkpoint has selected the authoritative run-state substrate.

The most important revision is to execute 61-01 first, resolve its load-bearing unknowns, and then re-plan 61-04 through 61-06 around one selected execution/state architecture and one versioned n8n-to-plugin outcome contract.

---

## Plan 61-01: Execution-Model Spike

### Summary

The spike is correctly placed first and applies an evidence discipline appropriate for this project. However, its no-live-call constraint may leave the central execution and restart questions unresolved. Since 61-05 is required to halt on unresolved premises, the current plan can finish successfully while leaving the phase unable to proceed.

### Strengths

- The plan correctly recognizes that async behavior depends on n8n Cloud rather than application assumptions.
- The basis vocabulary distinguishes measurement, derivation, documentation, and unknowns.
- Existing client-side run IDs are real: `DispatchOutcome.run_id` is created in `operator-claude-plugin/scripts/chunking.py:127-130` and populated during dispatch at `operator-claude-plugin/scripts/chunking.py:315-337`.
- Separating progress-read cost from work execution cost is important under the 2,500-execution limit.
- The operator checkpoint correctly treats run-state location as an architectural decision rather than an executor preference.

### Concerns

- **HIGH:** The spike may not resolve its load-bearing questions. Restart survival, detached subworkflow behavior, concurrency limits, and execution billing may not be knowable from repository evidence. The plan permits `[unknown]`, while 61-05 must halt if a required premise remains unresolved. No subsequent task is assigned to resolve those unknowns.
- **MEDIUM:** The document test validates formatting rather than truth. A false statement ending in `[documented]` would pass because the test does not verify that the referenced source supports the claim.
- **MEDIUM:** “Every claim line” is not mechanically defined. Markdown tables, formulas, continuation lines, commands, and headings make claim-line detection heuristic and fragile.
- **MEDIUM:** The synchronous chunk loop is not a viable async substrate. `operator-claude-plugin/scripts/chunking.py:25-30` states that each POST performs the work before responding and is constrained by the approximate 100-second window. Raising its ceiling does not provide immediate submission or in-flight progress.
- **MEDIUM:** The executions API is being treated as a run-state store, but current correlation is only time-proximity based. That limitation is explicitly documented in `operator-claude-plugin/scripts/watch.py:33-36` and `operator-claude-plugin/scripts/watch.py:93-97`. It may be an observation mechanism, not a durable row-level resume mechanism.

### Suggestions

- Split the spike into an offline evidence pass and a read-only/admin probe pass.
- Do not allow substrate selection while any premise required by 61-05 remains `[unknown]`.
- Represent premises in a structured table or YAML block with premise ID, basis, source, source lines, formula inputs, and dependent plan/task IDs.
- Classify candidate 4 as the current-state baseline, not an eligible async solution.
- Evaluate three separate concerns: durable run identity, authoritative row-level state, and progress observation.

### Risk Assessment

**MEDIUM-HIGH.** The spike itself is safe, but it can produce a formally complete document that does not resolve the decisions needed by later plans.

---

## Plan 61-02: LinkedIn Match Lane

### Summary

This plan accurately identifies the dead LinkedIn match path and proposes the right general shape: add an explicit lane, route through a real HubSpot search, preserve identity precedence, and verify search results before reporting a strong match. Its principal weakness is the claim that search-time filtering can transparently absorb arbitrary stored URL variance.

### Strengths

- The dead-path diagnosis is confirmed by source:
  - `n8n/code/resolveIdentity.js:74-86` contains LinkedIn resolution logic.
  - `n8n/code/matchProposal.js:30-41` does not route LinkedIn rows into a live lane.
- The existing plugin projection does strip LinkedIn before transmission, as shown in `operator-claude-plugin/scripts/enrichment.py:66-71` and `operator-claude-plugin/scripts/enrichment.py:245-252`.
- The proposed precedence is correct: object ID, email, LinkedIn, then weak name/company matching.
- The mixed-batch test is a strong regression shape because it detects rows that disappear between lane stamping and lane filtering.
- Re-verifying HubSpot hits using canonicalized values is an important false-positive control.
- Widening `MATCH_LOOKUP_KEYS` by one field preserves a narrow disclosure boundary.

### Concerns

- **HIGH:** The proposed EQ search cannot cover arbitrary stored-value variance. Searching the raw input and one canonical form will still miss a stored third form such as `http://www.linkedin.com/in/x/?trk=foo`.
- **HIGH:** `CONTAINS_TOKEN` behavior on URL properties is not established. A mocked flow test cannot prove HubSpot’s tokenization or operator support.
- **HIGH:** Native `hs_linkedin_url` handling is optional in the plan, although omitting it can miss an existing contact and permit duplicate creation. If native-field hits are searched but adapter verification inspects only `lv_linkedin_url`, those hits will still be discarded.
- **HIGH:** Multiple exact matches are not defined. Current strong-key handling treats a nonempty `existingRecord` as high-confidence in `n8n/code/matchProposal.js:124-134`. A LinkedIn search yielding two verified records must not select one arbitrarily.
- **MEDIUM:** `src/identity.py` changes the search filter but the stale property request list remains at `src/identity.py:15-16`. That list should also request the live property.
- **MEDIUM:** Workflow regeneration has an incomplete file inventory. `scripts/build_cloud_workflows.py:7731-7765` rewrites multiple workflow JSON files, not only `n8n/wf_enrichment_cloud.json`.

### Suggestions

- Prefer a separate canonical LinkedIn-key property or a one-time canonicalization backfill followed by exact `EQ`.
- If a canonical property cannot be added, explicitly document the bounded variants supported rather than promising arbitrary normalization tolerance.
- Search both `lv_linkedin_url` and `hs_linkedin_url`, canonicalize either returned property, deduplicate by contact ID, and reject conflicting values.
- Define result cardinality:
  - zero verified hits: `none`
  - one verified hit: `high`
  - multiple verified hits: ambiguous/held
  - lookup failure: `unknown`
- Update `_SEARCH_PROPS` in `src/identity.py`.
- Add all regenerated files to `files_modified`, or add targeted workflow generation.
- Add a gated read-only HubSpot operator probe before declaring URL-variance search semantics proven.

### Risk Assessment

**MEDIUM.** The lane itself is well scoped, but the stored-variance and native-property gaps could produce silent misses or incorrect person matches.

---

## Plan 61-03: Front-End Identity Contract

### Summary

The plan correctly updates the duplicated identity contract and leaves behind a useful YAML-to-JavaScript parity test. It should be strengthened so the parity test permanently covers both YAML copies, not merely the root copy and a one-time shell diff.

### Strengths

- The current duplicated rule is confirmed at:
  - `config/column_mapping.yaml:54-57`
  - `n8n/code/columnMap.js:78-83`
- Treating `columnMap.js` as a separate hand-written implementation is correct.
- Adding `[linkedin_url]` is additive and preserves the weak name/company path.
- Deriving the rejection reason from configuration removes one future drift site.
- Preserving the no-invention rule while changing only identity sufficiency respects D-61-02.
- Depending on 61-02 prevents a front-end-only release that sends rows into a dead backend path.

### Concerns

- **HIGH:** The committed parity test reads only `config/column_mapping.yaml`. The plugin mirror is protected only by a one-time `diff`, so later drift in `operator-claude-plugin/config/column_mapping.yaml` would not fail the suite.
- **MEDIUM:** The “five sites” count is not stable or clearly categorized. The plans mix executable rules, generated rules, derived error text, and explanatory prose. That makes future contract ownership ambiguous.
- **MEDIUM:** The byte-identical no-invention check is summary evidence, not a lasting regression guard.
- **MEDIUM:** A generic YAML-driven parity test needs a defined generation method. It should explicitly test presence semantics rather than imply it validates each field’s full domain behavior.
- **MEDIUM:** Generated workflow outputs are again absent from the file inventory.

### Suggestions

- Make the parity test assert root YAML equals plugin YAML before testing JavaScript behavior.
- Maintain a contract census distinguishing authoritative config, executable implementations, generated code, and explanatory documentation.
- Pin the no-invention sentence or its semantic behavior in a stable contract test.
- Define the generated test values as nonblank presence sentinels, then retain separate realistic integration cases for email, LinkedIn, and name/company.
- Include all generated workflow artifacts in the plan.

### Risk Assessment

**LOW-MEDIUM.** The implementation direction is sound. The main residual risk is future drift between duplicated configuration files.

---

## Plan 61-04: Confidence and Hold Queue

### Summary

This plan contains the phase’s largest implementation gap. Its confidence policy is sensible conceptually, but the required signals do not currently reach the plugin. More importantly, the plan creates pure helpers and edits workflow prose without modifying a production orchestration path that calls those helpers. The proposed persistence model is also not sufficient to determine when a confidence hold has changed.

### Strengths

- Avoiding another arbitrary numeric confidence score is a good decision.
- The plan preserves `unknown` versus `none`, which prevents failed lookup from being interpreted as absence.
- Separating no-email holds from confidence holds is necessary because their resume conditions differ.
- Centralized atomic `0600` writing is supported by `operator-claude-plugin/scripts/durable_paths.py:57-81`.
- The plan correctly retains non-clobbering, write gates, armed-window narrowing, and conflict adjudication.

### Concerns

- **CRITICAL:** Confidence inputs are unavailable to the plugin:
  - Provider agreement is produced in `n8n/code/scoreEnrichment.js:74-97`.
  - Material conflicts are computed in `n8n/code/providerConflict.js:14-36`.
  - Judge confidence exists in workflow state around `scripts/build_cloud_workflows.py:2800-2808`.
  - The plugin classifier at `operator-claude-plugin/scripts/preingest.py:236-334` currently receives match-oriented response data, not these enrichment signals.
- **CRITICAL:** Nothing wires `confidence.py` or `held_queue.py` into production. Task 3 changes skill prose, tests, version, and changelog, but no executable orchestration function.
- **CRITICAL:** “Resume once the holding signal changes” is not implementable with the proposed queue schema. Storing only row, reason, and timestamp provides no signal fingerprint, adjudication state, or resolution marker.
- **HIGH:** `run_manifest.py` and `held_queue.py` become two authorities for the same status. Atomic writes are per file, so a crash can leave them inconsistent.
- **HIGH:** Corrupt held-queue data degrading to empty silently loses rows that were intentionally not written. This differs from a safe “rerun everything” fallback unless the complete source batch is durably retained elsewhere.
- **HIGH:** The existing manifest is global. `operator-claude-plugin/scripts/run_manifest.py:56`, `:103-114`, and `:147-153` show one fixed file replaced on each save, making concurrent async runs unsafe.
- **HIGH:** The security design relies on forbidden names while proposing persistence of full row payloads. Sensitive values can exist under innocuous keys, so key-name scanning is insufficient.

### Suggestions

- Add a prerequisite plan for a versioned per-row outcome contract emitted by n8n and parsed by the plugin.
- Include match tier, uniqueness, provider agreement, conflict groups, adjudicated fields, judge confidence, spend, and completed pipeline stage.
- Add one real production entry point that executes match, enrich, confidence, partition, dispatch, persist, and report. Tests should invoke that entry point rather than compose helpers independently.
- Persist a structured hold condition with hold code, relevant fields, signal fingerprint, required resolution, and provider-stage completion.
- Use one run-scoped authoritative state document, or define write ordering and reconciliation between state files.
- Treat a corrupt queue as `unreadable` and fail loudly; only a genuinely absent queue should mean empty.
- Store explicit allowlisted row fields instead of complete arbitrary rows.
- Move persistence design after the 61-01 state-store decision.

### Risk Assessment

**HIGH.** The plan can produce passing helper tests without changing actual runtime behavior, and its current state schema cannot safely resume confidence-held rows.

---

## Plan 61-05: Async Submit, Progress, and Resume

### Summary

This plan has appropriate safety goals but is necessarily architecture-dependent. Because 61-01 has not selected the substrate or authoritative store, 61-05 is currently a template rather than an executable implementation plan. It also conflicts internally over whether corrupt state should fail loudly or degrade into a full rerun.

### Strengths

- Rechecking spike premises before implementation is prudent.
- Distinguishing unreadable state from zero progress is correct.
- The centralized polling restriction is real and useful at `operator-claude-plugin/tests/test_report_sufficiency.py:185-242`.
- The requirement that interrupted work never report complete is essential.
- Comparing observed execution cost with the spike arithmetic is a useful acceptance check.

### Concerns

- **CRITICAL:** The plan is under-specified until substrate selection. A front-loaded response, Wait-node flow, detached subworkflow, executions API, HubSpot store, or local manifest each requires different endpoints, schemas, restart behavior, and file changes.
- **CRITICAL:** Existing corruption semantics conflict with fail-loudly:
  - `run_manifest.load()` returns `{}` for missing, malformed, unreadable, or invalid state at `operator-claude-plugin/scripts/run_manifest.py:156-185`.
  - `rows_to_resume()` interprets empty state as a full rerun at `operator-claude-plugin/scripts/run_manifest.py:235-259`.
  - The caller therefore cannot distinguish first run from corrupt persisted state.
- **CRITICAL:** Persisted `run_id` is ignored on load. It is written around `run_manifest.py:148-152`, but load returns only verdicts at `run_manifest.py:176-185`.
- **CRITICAL:** Local artifacts cannot provide live progress if n8n continues after the plugin call returns. The remote worker needs access to the authoritative state store.
- **HIGH:** Progress omits `total`, `pending`, and `running`. Counts of done/held/failed can look valid while most rows have disappeared.
- **HIGH:** Checkpoint timing and replay semantics are undefined. A crash after HubSpot write but before recording completion can duplicate spending or writes.
- **HIGH:** The unit test with an injected transport cannot prove n8n continues after responding or survives restart.
- **HIGH:** The live checkpoint conflicts with Phase 57 gating unless it is restricted to mock/return-only/test-record operation.

### Suggestions

- Execute 61-01 and then write a new substrate-specific 61-05 plan.
- Use typed state-load results: `missing`, `valid`, `corrupt`, `wrong_run`, and `unreadable`.
- Move to per-run paths and require `load(expected_run_id)`.
- Persist a source batch fingerprint and the complete row-ID set.
- Require the invariant `total = pending + running + done + held + failed`.
- Define stage-aware idempotency, such as `planned`, `provider_started`, `enriched`, `write_started`, `written`, `associated`, and `complete`.
- Ensure the worker performing the work can update the authoritative store.
- Restrict the pre-Phase-57 checkpoint to return-only or allowlisted test records with no create capability and bounded spend.
- If restart survival is claimed, perform a controlled restart during the acceptance run, not merely before it.

### Risk Assessment

**HIGH.** The plan cannot be implemented faithfully until the substrate and state authority are selected, and current manifest semantics are unsafe for asynchronous resume.

---

## Plan 61-06: Unattended Pair Pipeline

### Summary

The plan correctly treats company association as mandatory and recognizes the existing enrichment-lane gap. However, it crosses an impossible storage boundary by asking n8n Cloud to write a local plugin queue, and it tries to implement one-grant orchestration through documentation rather than executable grant/dispatch changes. Its index-lag strategy should carry the created company ID directly instead of waiting for HubSpot search indexing.

### Strengths

- The association requirement is correctly treated as load-bearing.
- Existing association tests demonstrate useful patterns, including by-value joins in `tests/n8n/companyAssociationFlow.test.mjs:84-109` and write-gate behavior at `tests/n8n/companyAssociationFlow.test.mjs:112-133`.
- Holding unresolved creates rather than landing orphan contacts is correct.
- Updates are appropriately distinguished from creates.
- Index lag is correctly separated conceptually from a genuine company-resolution miss.
- Phase 57 remains named as a prerequisite for a live unattended run.

### Concerns

- **CRITICAL:** n8n Cloud cannot write `operator-claude-plugin/scripts/held_queue.py` on the operator’s machine. Task 1 changes only the workflow builder and n8n tests, with no client-side response consumer.
- **CRITICAL:** “One grant across the whole lane” is documentation-only. No grant planner, authorization function, dispatch path, or runtime orchestrator is changed.
- **CRITICAL:** Pair dependency representation is undefined. The plan does not specify how contacts reference companies created in the same run, how shared-company contacts coalesce, or how created IDs propagate.
- **HIGH:** Waiting for search indexing is unnecessary when the company-create response provides the authoritative company ID.
- **HIGH:** A zero-result search cannot distinguish indexing lag from nonexistence, failed creation, wrong lookup keys, or inaccessible data.
- **HIGH:** A JavaScript flow test with injected results cannot prove real HubSpot search-index timing.
- **HIGH:** The plan asks for “one implementation” while permitting association logic to be added to a second workflow lane. Reusing the same helper does not create one operational implementation.
- **HIGH:** The Phase 57 gate is prose and a checkpoint, not a machine-enforced capability restriction.

### Suggestions

- Route held outcomes through a versioned n8n response contract and persist them client-side, or use the selected shared run-state store.
- Modify the actual grant and orchestration code, not only `SKILL.md`.
- Introduce a run-plan schema with contact/company dependency IDs and coalesced company creation.
- Carry the newly created company ID directly into contact association as an explicit `company_id`.
- Classify index lag only when the run has durable evidence of a successful create. Otherwise treat the result as unresolved.
- Prefer routing unattended contact creates through the existing ingest lane to preserve one operational association implementation.
- Add a runtime readiness flag that refuses unattended mode until Phase 57 controls are installed.
- Define fresh-grant behavior for resumed runs and ensure a grant is never persisted.

### Risk Assessment

**HIGH.** The current plan cannot connect cloud workflow outcomes to local queue state, and its grant and same-run association guarantees are not implemented by the listed production changes.

---

# Cross-Plan Findings

## Critical Issues

- **State architecture is selected too late.** Plan 61-01 leaves run-state location open, but 61-04 commits to local queue/manifest files, 61-05 reports over them, and 61-06 expects n8n to feed them. This prejudges the checkpoint and conflicts with HubSpot-, n8n-, or external-store outcomes.
- **No shared outcome contract exists.** Match tier reaches the plugin, while agreement, conflicts, judge adjudication, and spend remain inside n8n. Confidence, progress, hold, and resume cannot work coherently without one versioned per-row contract.
- **Async resume is not concurrency-safe.** The current manifest has one fixed path, overwrites previous state, ignores run ID on load, and lacks a batch fingerprint.
- **Plans 61-04 and 61-06 document runtime behavior without changing the runtime that must perform it.**

## High Issues

- Plugin versioning is inconsistent:
  - Current version is `0.28.6` at `operator-claude-plugin/.claude-plugin/plugin.json:4`.
  - 61-02 fixes `0.29.0`.
  - 61-03, 61-04, and 61-06 request unspecified bumps.
  - 61-05 lists metadata files but defines no bump task.
- Generated workflow inventories are incomplete. `scripts/build_cloud_workflows.py:7731-7765` rewrites several artifacts.
- Phase 57 gating conflicts with 61-05’s live checkpoint unless that checkpoint is explicitly non-production and non-spending.
- Multiple plans rely on tests that can prove routing or structure but not the relevant live platform behavior.

## Suggested Sequence

1. Execute the offline portion of 61-01.
2. Resolve all load-bearing `[unknown]` premises with read-only/admin probes.
3. Select the async substrate and authoritative state store.
4. Revise and execute 61-02, including native LinkedIn handling and multiple-hit semantics.
5. Revise and execute 61-03, including permanent parity across both YAML files.
6. Add a versioned n8n-to-plugin per-row outcome contract.
7. Re-plan 61-04 around a real production orchestration entry point.
8. Re-plan 61-05 specifically for the selected substrate and per-run state model.
9. Land Phase 57’s machine-enforced ceilings and refusal-before-start controls.
10. Re-plan 61-06 around explicit company/contact dependencies and direct company-ID propagation.
11. Perform the first live unattended pilot only after Phase 57.

## Final Risk Assessment

**Overall risk: HIGH.**

The LinkedIn tracer work is well understood and mostly ready. The autonomous-batch portion is not. Without a selected state authority, a shared outcome schema, run-scoped persistence, and explicit production orchestration, the later plans can produce extensive passing tests and documentation while leaving the operator-facing runtime fundamentally synchronous and manually driven.

---

## OpenCode Review (kimi-k3)

I'll verify the plans against the actual source before reviewing. Launching four parallel exploration agents, each with a specific claim list to check.
# Cross-AI Plan Review — Phase 61 (Autonomous batch runs), plans 61-01 … 61-06

**Verification method:** I did not review the plan text in isolation. Four parallel repo explorations checked every load-bearing claim against source, and the findings below are based on what was actually read. Net result: the plans' evidentiary claims are almost entirely accurate — the domain codebase is unusually well-instrumented, and the plans cite it precisely. Where the plans mislocated or mis-stated something, it's flagged below.

---

## Plan 61-01 — n8n execution-model spike (decision document)

### Summary
A disciplined, no-production-code spike that enumerates four async substrate candidates, costs 40- and 300-record batches in n8n executions against the 2,500/month budget, and produces a machine-readable `## Premises` contract that 61-05 must re-assert before coding. This is exactly the kind of plan this phase needs: D-61-08 says the biggest unknown is the platform, not the code, and this plan deliberately spends its budget on a verdict document rather than on an implementation built on guesses.

### Strengths
- **Basis-word discipline is real and testable.** The closed token set (`[measured]`/`[derived]`/`[documented]`/`[unknown]`) turns the "no guessing" rule into a lint. The cited precedent is genuine — `54-MEASUREMENT.md:108-120` explicitly records the multi-chunk case as an unclosed residual rather than papering over it.
- **The four sub-questions per substrate (outlives window / durable handle / restart survivability / execution cost) map directly onto the checkpoint options** — the decision in Task 4 (staticData vs HubSpot object vs executions API vs client manifest) is decided by Task 2's arithmetic, not taste. `executions_client.py` is verified read-only GET (`executions_client.py:74-114`) and `run_manifest.py` durability is real (`run_manifest.py:103-114`).
- **The `run_id` observation is correct.** `chunking.py:315,336-337` already mints a `run_id` client-side, so "submit returns a handle" is genuinely solved; the open question is only progress-while-running, as the plan states.
- **Test-as-contract design.** `test_spike_verdict_61.py` reads the doc as text (never imports/executes), rejects placeholder lines (`TBD`/`TODO`/empty), and resolves the doc path across both `.planning/phases/` and `.planning/milestones/*-phases/` — which is correct because the repo does archive phases under `v0.3-phases` … `v0.8-phases`.
- Task ordering is right: Tasks 2 and 3 select their own test function (`-k arithmetic`, `-k premises`) out of a file Task 1 creates, so the gate can't be satisfied by a stub.

### Concerns
- **LOW — "claim line" heuristic brittleness.** Task 3's test asserts every claim line in three sections carries exactly one basis token. What counts as a "claim line" is a regex judgement; a heading, bullet, or sentence containing a colon could be miscounted. Acceptable for a text-lint, but the test may fight the author over formatting rather than substance.
- **LOW — concurrency cap may stay `[unknown]`.** Task 2 permits the concurrency cap to be recorded as `[unknown]` with a read-only command. The operator's substrate decision in Task 4 could then be made without knowing whether fan-out is viable. The plan accepts this trade; worth saying explicitly at the checkpoint if it stays unknown.
- **LOW — unverifiable baseline numbers.** Every plan cites plugin baseline "1725 / 5" and root baseline "3365 / 154". Only the root 3365 figure is corroborated (`.planning/STATE.md:11`); the 154 and plugin figures were not found in repo artifacts. Harmless, but the verification blocks treat them as known-good.

### Suggestions
- In the test, define "claim line" narrowly (e.g., a bullet or numbered entry after excluding headings and blank lines) so the lint is stable.
- At the Task 4 checkpoint, if the concurrency cap resolved to `[unknown]`, surface that explicitly in the decision context rather than letting it blend into the arithmetic.

### Risk Assessment — **LOW**
No production code is written; the worst failure is a wrong verdict document, and the checkpoint plus basis-word lint directly target that failure mode.

---

## Plan 61-02 — backend `linkedin` match lane

### Summary
The tracer's backend half landed first, deliberately, so the front-end gate (61-03) never ships rows into a dead lane. It adds a fourth additive routing row (`IF Linkedin Searchable` → `HubSpot Linkedin Search` → `Adapt Linkedin Search`) to the contact match branch, makes the search survive stored-value variance, fixes a confirmed latent defect in the Python oracle's filter name, and un-freezes the client-side `MATCH_LOOKUP_KEYS`. All claims checked out against source, with two minor location corrections.

### Strengths
- **The property-name question is settled by evidence, not a live call.** The committed portal snapshot `config/hubspot_migration/baseline/portal-schema-contacts-54-03-contacts-check.json` (430 contact properties) contains `lv_linkedin_url` and NO bare `linkedin_url`, and does contain `hs_linkedin_url` (`hubspotDefined: true`). The plan uses it to resolve 61-RESEARCH.md's flagged MEDIUM-risk unknown offline — exactly the right move.
- **The routing structure being copied is verified.** `IF Has Email` (`build_cloud_workflows.py:4822-4830`) → `IF Name Searchable` (`4831-4836`) → `HubSpot Name Search` (`4849-4859`) → `Adapt Name Search` (`4882`), with the connection map at `5516-5523`. The plan's rewire (Has-Email false → Linkedin IF → false → Name IF) is mechanical over real targets.
- **Re-verification of hits is mandatory, not optional.** `mediumCandidates`' header (`matchProposal.js:62-79`) documents the BUG-22b lesson ("a hit surviving the server-side filter is not yet a verified match"), and the plan applies that discipline to a strong key — the negative case (different profile under same host must NOT match) is in `<behavior>`.
- **`laneOf` branch order is correctly extended.** Current order is fetch_by_id → email → name → none (`matchProposal.js:30-42`); inserting linkedin after email, before name, mirrors `resolveIdentity.js`'s own strong-key ordering. Verified: nothing in that file reads `linkedin_url` today.
- **The oracle defect is real, not hypothetical.** `src/identity.py:65` filters on the literal `linkedin_url`, which does not exist on the live contacts portal — the linkedin branch there has been permanently zero-hit.
- **Boundary widening is exactly one key, and the disallow list is re-pinned by test in the same task.** `enrichment.py:66-71` (comment) and `:249-252` (docstring) both restate the tuple; the plan updates both in one edit.
- **Mixed-batch flow test is the decisive assertion** — one item per `row_id` for email/linkedin/name rows in one request; a row routed to one lane and filtered into another fails the suite rather than vanishing (T-61-07).

### Concerns
- **MEDIUM — stored-value variance vs HubSpot operator choice.** Task 2 offers either two filter groups (canonicalized + raw) or `CONTAINS_TOKEN` on the profile slug. `CONTAINS_TOKEN` tokenization on URLs is risky (a URL tokenizes into host/path fragments; a slug-only token could match sibling profiles). The re-verification step in the adapter catches that at read time, which is why this is MEDIUM not HIGH — but the chosen filter shape should prefer the two-group EQ form (canonicalized OR raw) and keep `CONTAINS_TOKEN` only if EQ misses, recorded in the node comment as the plan requires.
- **LOW — minor mislocations in read_first.** `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV` is defined at `build_cloud_workflows.py:4459` (not ~5160); the companies branch uses the company CSV. Also `tests/n8n/matchProposal.test.mjs` has 23 laneOf+summarizeMatch cases (37 including mediumCandidates), not "~30". No consequence, flagged for accuracy.
- **LOW — native `hs_linkedin_url` decision is a comment-level item.** The plan correctly refuses silence ("either add it as a second filter group or state why excluded"), and the snapshot confirms the native property exists. It would be better as a `must_haves` truth than a comment beside the node, because a contact whose LinkedIn only lives under the native property is a duplicate-creation path.

### Suggestions
- Prefer the two-`EQ`-group filter (canonicalized form + raw input) and record why `CONTAINS_TOKEN` was or wasn't used.
- Elevate the `hs_linkedin_url` include/exclude decision from "comment beside the node" to a checked must_have.
- When embedding canonicalization in `Adapt Linkedin Search`, inline a copy of `resolveIdentity.js:17-41`'s `canonicalizeLinkedin` logic and note the source in the builder comment, to avoid a fourth divergent implementation.

### Risk Assessment — **MEDIUM**
It edits deployed-workflow routing and a live CRM query filter, and the failure mode (wrong operator/property → silent zero hits) only surfaces live. Mitigations are strong (offline flow test, portal-snapshot evidence, re-verified hits) and generated-JSON discipline holds. Not HIGH because nothing deploys without a later checkpoint, and the failure mode is silent-miss rather than wrong-write.

---

## Plan 61-03 — third identity group across all five sites

### Summary
The front-end half of D-61-05: `[linkedin_url]` becomes its own group in both YAML copies, in `columnMap.js`'s hand-written gate, in `extraction.py`'s (derived) refusal message, and in `extraction.md`'s prose, with a YAML-to-JS parity test left behind. Reuse of D-59-08's `resolutions`/`provider_result` loop for waterfall proposals is correctly assessed — `resolutions` validation runs for every accepted record, so it generalizes past D-59-08's original "failed pre-flight" moment.

### Strengths
- **Five-site enumeration is verified complete.** Two YAML copies (`config/column_mapping.yaml:54-57`), Python gate (`extraction.py:170-192`), hard-coded reason (`extraction.py:642-645`), JS reimplementation (`columnMap.js:78-83`), prose (`extraction.md:27-29`). No sixth site found.
- **Derived-message design deletes a site.** Rewriting the reason string from `identity_groups()` removes the string-drift class rather than adding a sixth thing to keep in step — the right fix.
- **Parity test is driven FROM the YAML**, so a future fourth group is covered automatically. No identity parity test exists today across `tests/` (only `tests/n8n/parity.test.mjs:200-205` hard-codes the rule behaviorally).
- **D-61-03's fence is asserted by a negative test**, not assumed — a bare name still rejects.
- **The two YAML copies are currently byte-identical** (verified via `diff`), so the plan's "edit both" step is well-defined, and the verify block includes the `diff` re-check.
- **No-invention sentence is separable and untouched.** `extraction.md:22-26` (no-invention) vs `:27-29` (group list) are distinct list items; the plan requires byte-identical verification in the summary.

### Concerns
- **MEDIUM — the refusal sentence is pinned byte-for-byte somewhere the plan doesn't name.** `test_extraction_contract.py:233-241` asserts `result.rejected == [{... "reason": "no identity present: needs a non-blank 'email', or all three of 'firstname'/'lastname'/'company' non-blank"}]`. Task 2's derived message will break that exact assertion. The plan's Task 2 verify command does run `test_extraction_contract.py`, so it will fail loudly at execution — but the plan text only says "check this file's parse of the fenced example block". The pinned-sentence update should be an explicit task step, not discovered-by-failure.
- **LOW — census discipline is correctly priced, but make it explicit which test file registers.** Task 3 rightly budgets a composition test (`test_linkedin_row_composition.py`) because `MAX_GRANDFATHERED = 0` and `GRANDFATHERED_UNCOVERED = {}` (`test_skill_sequence_coverage.py:254-256`). Verified: the census is set-equality over `skills/*/SKILL.md` python blocks (lines 355-373).

### Suggestions
- Add an explicit step in Task 2: "update the verbatim assertion in `test_extraction_contract.py:233-241` to the derived message" (or keep an exact-prefix form so the test passes unmodified — pick one deliberately).
- Also grep `tests/test_e2e_ingest.py` after the YAML change: `src/file_loader.py` reads the same repo-root YAML, so the Python oracle lane change should be confirmed green even though it's not a plan file target.

### Risk Assessment — **LOW**
Gate/prose/test changes with a parity ratchet added. The only real trap is the verbatim-pinned test, and it's caught by the plan's own verify command.

---

## Plan 61-04 — confidence verdict + held queue + batch-finishes

### Summary
This plan decides what "confidence" means and builds the hold-don't-block machinery for D-61-07. The design is deliberately conservative: confidence is a two-verdict decision table over three signals that already exist (match tier from `summarizeMatch`'s four tiers, provider agreement from `scoreEnrichment.js`'s `agreedBy`, material-conflict/judge verdict from §15.0), no new model call, no new numeric scale; held rows go to a new third durable artifact with `run_manifest.py`'s hardening rules; and `run_manifest.py` gains a sixth verdict word so a resume doesn't re-spend provider credit on confidence-held rows.

### Strengths
- **The three input signals are verified to exist.** `matchProposal.js:119-146` stamps four tiers deliberately (`unknown` ≠ `none`); `scoreEnrichment.js:76-96` emits `agreedBy`; `providerConflict.js` exports `detectConflicts`/`groupConflicts` (`:58`); `judge_confidence_by_field` exists in the builder at line 2800 and elsewhere.
- **Two verdicts, no middle band** — directly targets the per-row question the phase exists to remove; the decision-table form makes the whole policy auditable in one screen.
- **The sixth-word collision is real and correctly diagnosed.** `run_manifest.py:71-76` pins exactly five words (`matched/enriched/held/unchecked/unanswered`); `rows_to_resume`'s `held` branch re-includes on email presence (`:249-254`). A confidence-held row usually HAS an email, so without the new word it would be re-sent and re-spend on every resume. That's a money bug caught at plan time.
- **`held_queue.py` copies the right precedents.** `run_manifest.py`'s forbidden-name markers (`run_manifest.py:86-89` — arm/secret/token/grant/etc.), degrade-whole on any anomaly (`:182-183`), and `durable_paths.py`'s `resolve_state_path` (`:234`) + `_atomic_write_0600` (`:57`) are all verified existing utilities.
- **The "batch always finishes" test asserts last-row completion**, not merely queue recording — the actual D-61-07 promise.
- **Guard compatibility verified.** `test_report_sufficiency.py`'s poll-loop guard scans the whole `scripts/` dir (lines 196-197, 225-242), so the new modules will be scanned automatically; `confidence.py` and `held_queue.py` being I/O-free keeps them clean.

### Concerns
- **MEDIUM — confidence is client-side over n8n-stamped verdicts.** `confidence.py` consumes tier/agreement fields produced by the n8n lane and re-derived client-side by `classify_matches`. If the n8n lane's stamping vocabulary drifts (e.g., a new tier), the client table can silently mis-bucket. The table should be total with an explicit else→held branch (plan appears to do this — "first match wins" table — but the else should be spelled out).
- **LOW — reachability assertions are demanded but exhaustiveness is tricky.** Task 1 requires "each table row reachable by at least one case". Good; the risk is a row that's reachable only via an unrealistic signal combination that never occurs in production. Acceptable for a decision table.
- **LOW — `held_queue` schema carries "enough of the row to re-send it."** That's a PII-bearing snapshot on disk (0600 helps). It parallels `run_manifest`'s pattern, but the docstring should say why row content (not just row_id) is needed for re-send.

### Suggestions
- Give `confidence.py` an explicit terminal `else: held(signal="no table row matched")` so a vocabulary drift yields a hold, never a confident default.
- In `held_queue.py`'s docstring, state that row content is persisted because re-send needs the original specification, and name the forbidden-markers it inherits.

### Risk Assessment — **MEDIUM**
The confidence→autonomous-write boundary is the critical trust boundary in this phase (the plan's own T-61-11). Design is appropriately conservative (held-by-default, unknown-tier and unadjudicated-conflict each block confident, merge policy and write gates untouched downstream), but a wrongly-confident verdict writes to a no-rollback CRM. MEDIUM, not HIGH, because confident verdicts still flow through the non-clobber merge and armed-window gates, which remain in force.

---

## Plan 61-05 — async submit / progress-while-running / resume-or-fail-loudly

### Summary
The plan that takes the run off the ~100s synchronous window: Task 1 halts unless 61-01's `## Premises` block is intact, Task 2 builds `run_state.py` over the operator-selected substrate, Task 3 builds resume on `run_manifest.rows_to_resume` (no second resume rule), and Task 4 is a blocking human-verify checkpoint for deploy/bounce/live observation. The premise-halt discipline is the correct response to the spike-first warning.

### Strengths
- **The premise gate is test-pinned, not ceremonial.** Task 1 both records premise status in the summary AND writes assertions into `test_run_state.py` that re-fail if the verdict doc is later edited — the contract holds after execution, not just during.
- **Halt-on-contradiction enumerated precisely:** missing decision, unresolved depended-on premise, budget-exceeding substrate → escalate by name, not improvisation.
- **Unreadable-vs-zero distinction mirrors a real precedent.** `summarizeMatch`'s `unknown` ≠ `none` exists for exactly this confusion; the plan correctly ports it into progress display.
- **Resume built on `rows_to_resume`'s whole-degrade rule** (`run_manifest.py:182-183`) — the plan explicitly refuses to soften it into partial trust, which is the dangerous middle.
- **Poll-loop containment is principled.** `_POLL_LOOP_ALLOWED = {"watch.py"}` (`test_report_sufficiency.py:193`) and widening it is treated as a recorded decision, and `watch.py`'s measured context (32-39s runs, ~100s window, backoff schedule `:67`) is verified.
- **Checkpoint is genuinely blocking and deploy-safe**: regenerated workflow diff reviewed with noisy fields ignored, deploy+bounce is admin-only, execution count compared against 61-01's arithmetic.

### Concerns
- **MEDIUM — Task 2's shape is substrate-dependent.** `run_state.py`'s implementation can't be specified further until the 61-01 checkpoint decision lands. The plan compensates with three substrate-independent invariants (four counts, unreadable≠zero, forbidden-name refusal), which is the right hedge — but reviewers should treat the module boundary as intentionally under-specified until 61-01 Task 4 resolves.
- **LOW — "execute against a verdict document" depends on a human checkpoint having happened.** `depends_on: ["61-01"]` is declared, and Task 1 asserts the verdict doc exists and carries the operator decision — so enforcement is in-plan, but the executor must actually run Task 1 before any parallel work begins. Wave 4 dependency is correctly declared.

### Suggestions
- In Task 2, also record which of the four substrate options was selected in the module docstring (with the 61-01 summary citation), so future readers don't re-derive the decision.
- If `watch.py` must be widened (substrate requiring another poll site), the summary-record requirement is good; consider also requiring a comment at the widening site naming the decision id.

### Risk Assessment — **MEDIUM**
Resume correctness against a half-completed batch is a high-severity concern (T-61-15 critical), and the shape depends on a pending decision. Mitigations are unusually strong (halt-on-contradiction, whole-degrade resume, blocking checkpoint, poll-loop containment). MEDIUM; drops to LOW once the 61-01 decision lands and Task 2's shape settles.

---

## Plan 61-06 — the unattended pair pipeline under one grant

### Summary
The composing plan: ingest→enrich→create→associate under one grant, with the CLAUDE.md §13.0.1 association gap closed, index-lag handling bounded, failed rows returnable as the existing re-sendable specification, and a blocking checkpoint that holds the first live run for Phase 57's ceiling work. It correctly refuses to build Phase 57's report/ceiling/proof features here and names that deferral explicitly.

### Strengths
- **The association gap is real and quoted.** CLAUDE.md §13.0.1 states the ingest lane gained eight nodes and `wf_enrichment_cloud`'s own contact create does not associate. The plan offers two bounded routes (close gap in enrichment lane reusing `companyLink.js:131-172`'s `resolveCompanyLink`, or route creates through the ingest lane) and explicitly demands ONE implementation of the rule — the right anti-duplication stance for this codebase.
- **Held-not-landed is the load-bearing test assertion** (`pairPipelineAssociationFlow.test.mjs`), not the happy path — matches the contract vocabulary (`company_hold_reason` at `companyLink.js:157-158`).
- **Index-lag vs resolution-miss is the correct distinction.** The cited live evidence (Harness Racing NSW, `18756544347`, execution 11922) is a resolution miss, not lag; the plan requires bounded lag attempts then hold-with-lag-reason. And the boundary is enforced where it belongs: `_POLL_LOOP_ALLOWED={"watch.py"}` forbids ad-hoc sleeps in plugin scripts, verified to scan all new modules.
- **Re-send uses the existing contract.** `chunking.failed_batch` returns a specification the envelope builder accepts unmodified (`chunking.py:420-444`, D-13 docstring) — no second derivation.
- **Gate-to-Phase-57 is explicit in both the objective and the checkpoint**, with D-61-08 cited; scope creep resistance is written into Task 3 (RUN-05/AFTER-01/AFTER-03 named as deferred).
- **End-of-run account distinguishes written vs would-have-been-written** — T-61-22 mitigated at the design level; `written_records.py` exists (verified, `written_records.py:128,244,285`).

### Concerns
- **HIGH (design constraint, mitigated) — one grant authorizes many writes to a no-rollback CRM.** This is the phase's core trade. The plan mitigates correctly: merge policy, write-safety gate nodes, empty-record-set refusal, judge gate, armed-window narrowing all stay, and first live execution is blocked behind Phase 57 ceilings. The severity is inherent; the mitigation is as good as the repo allows pre-Phase-57.
- **MEDIUM — Task 1 leaves the route open.** "Close the gap in the enrichment lane OR route creates through ingest lane" — either is defensible, but the summary must record the choice and why, and the flow test should assert whichever was chosen. Recommendation below to prefer one.
- **LOW — lag-bound needs a number.** Task 2 demands bounded attempts but doesn't pick the bound here; that's fine at plan time (it's a config-level choice), but the composition test should pin the termination case, which it does.

### Suggestions
- Prefer **routing creates through the ingest lane** for Task 1: it keeps exactly one association implementation (`Build Association Request` + `HubSpot Associate Company`) and avoids adding a second copy to the enrichment lane. If enrichment-lane closure is chosen instead, the summary must justify why indirection through ingest was worse.
- Pin the lag bound and the "held-for-lag" reason string shape in `test_unattended_pair_composition.py` so the termination behavior is contractual.

### Risk Assessment — **MEDIUM**
The trust boundary (one grant → many writes on a no-rollback CRM) is the highest in the phase, but every relaxation is explicitly excluded and the first live run is checkpoint-gated on Phase 57. Residual risk is the association-route choice, addressed above.

---

## Overall phase assessment

**The sequence is right.** 61-01 (substrate verdict) and 61-02 (backend lane) run wave 1 in parallel; 61-03 (front-end gate) depends only on 61-02; 61-04 (confidence/hold) on 61-03; 61-05 (async) on 61-01+61-04; 61-06 (composition) on 61-05. Dependencies are declared and minimal. The backend-first ordering means there's no "dishonest intermediate" deploy state — a rare and correct intuition.

**Requirement mapping is complete and non-duplicative in the meaningful sense:** INPUT-05 is deliberately split across 61-02 (backend) + 61-03 (front-end); RUN-01/02/03/04 and AFTER-02 land in 61-04/05/06 as intended.

**The strongest design moves:** (1) the `## Premises` machine-readable contract with a test that fails if the verdict doc is edited (61-01/61-05); (2) the YAML-driven parity test that makes the next five-site drift fail loudly (61-03); (3) the sixth verdict word preventing double-spend on resume (61-04); (4) offline property-name settlement via the committed portal snapshot instead of a live call (61-02); (5) blocking checkpoints before any deploy, plus the Phase 57 gate before any live unattended run (61-05/61-06).

**Cross-plan concerns to carry forward:**
1. **(MEDIUM)** `test_extraction_contract.py:233-241` pins the refusal sentence verbatim — 61-03 Task 2 will break it; handle explicitly, don't discover it by failure.
2. **(MEDIUM)** In 61-06 Task 1, don't leave "one of two routes" unrecorded; the flow test and summary must bind the chosen association implementation.
3. **(LOW)** Baseline figures (plugin 1725/5; root 3365/154) are only partially corroborated — root 3365 is in STATE.md, the others rest on the plans' own assertion. Harmless but should be re-verified at execution.
4. **(LOW)** 61-02's `hs_linkedin_url` include/exclude decision should be a checked must_have, not a code comment.

**Overall Risk Assessment — MEDIUM.** All HIGH-severity boundaries (confidence→write, grant→many-writes, resume-correctness) are explicitly modeled with mitigations, and nothing live happens until blocking checkpoints plus Phase 57 land. With source verification complete, the plans survive contact with the repo; the few concerns above are correctable at plan level before execution.

---

## OpenCode Review (gemini-3-6-flash)

# Structured Plan Review: Phase 61 (Autonomous Batch Runs)

## 1. Summary

Phase 61 presents a exceptionally thorough, well-architected execution plan that directly resolves the failure identified in Walk Run 4 (`53-WALK-RECORD-3.md`). By expanding identity pre-flight rules to support strong keys like `linkedin_url` while simultaneously upgrading backend matching, provider enrichment, confidence scoring, and async batching, the plan transitions the system from per-row manual friction to autonomous batch operations. The phased approach (61-01 through 61-06) is logically sequenced: it spikes execution constraints first, implements the full-stack tracer for LinkedIn matching next, updates client and n8n identity gates in lockstep, introduces deterministic confidence scoring with durable queueing, offloads runs from synchronous HTTP windows, and finally seals the unattended pair pipeline under a single grant gated on Phase 57.

---

## 2. Strengths

- **Evidence-Based Failure Diagnosis & Full-Stack Lockstep:** The plan correctly identified that updating client-side gates (`extraction.md`, `column_mapping.yaml`) without adding backend matching capability in `n8n/code/matchProposal.js` would cause `linkedin_url`-only contacts to pass extraction but silently stall in the `unchecked`/`unknown` bucket.
- **Strict Identity Scoping:** Scope is firmly bounded to strong keys (`linkedin_url`, `email`), explicitly leaving weak keys (`name_company`) in the `needs_review` path to prevent incorrect persona matching.
- **Concrete Code Base Corrections:** The plan identifies exact historical defects, such as `src/identity.py:65` querying non-existent `linkedin_url` instead of `lv_linkedin_url`, and `operator-claude-plugin/scripts/enrichment.py:71` stripping `linkedin_url` in `MATCH_LOOKUP_KEYS`.
- **Durable Hold-and-Collect Queue:** Rather than halting batches mid-stream or guessing on low-confidence data, unconfident rows are isolated into a durable queue while allowing the rest of the batch to complete.
- **Rigorous Test Infrastructure & Safety Gates:** Includes parity tests (`columnMapIdentityParity.test.mjs`), sequence census enforcement (`test_skill_sequence_coverage.py` with `MAX_GRANDFATHERED = 0`), and explicit gating of live unattended runs on Phase 57 ceiling checks.

---

## 3. Concerns

### HIGH SEVERITY

- **HubSpot CRM v3 Search Filter Syntax for String Matching**
  - **Location:** `scripts/build_cloud_workflows.py:4814-4890` (Task 1 & Task 2 in Plan 61-02)
  - **Issue:** Plan 61-02 proposes searching HubSpot for `lv_linkedin_url` using multiple filter groups or `CONTAINS_TOKEN`. However, HubSpot's CRM v3 Search API does not support `CONTAINS_TOKEN` on arbitrary standard string fields, and `EQ` exact matches fail when protocols or trailing slashes differ. If the n8n HTTP Search node sends an invalid operator (e.g. `CONTAINS`), HubSpot will respond with a `400 Bad Request` at runtime.
  - **Risk:** The search node could fail entirely during execution or return 0 hits if raw values differ slightly from normalized stored values.

- **Potential Race Condition in Search-Index Lag Handling**
  - **Location:** `scripts/build_cloud_workflows.py` & `operator-claude-plugin/scripts/preingest.py` (Plan 61-06, Task 2)
  - **Issue:** When a company is created during batch execution, HubSpot's Search API indexing lag can take anywhere from several seconds up to ~2 minutes. If contact resolution attempts to query the newly created company via Search API before indexing completes, it will fail to match. Relying solely on bounded retries without direct object ID binding between company creation and contact association in the batch payload could lead to false-positive "company not found" holds.
  - **Risk:** Unnecessary holding of valid contacts due to temporary CRM search index latency.

### MEDIUM SEVERITY

- **Schema Evolution Risk in `run_manifest.py` Verdict Words**
  - **Location:** `operator-claude-plugin/scripts/run_manifest.py:76` (`ALLOWED_VERDICTS`) & `operator-claude-plugin/scripts/held_queue.py` (Plan 61-04, Task 2)
  - **Issue:** Adding a 6th verdict word to `ALLOWED_VERDICTS` (`operator-claude-plugin/scripts/run_manifest.py:76`) requires careful synchronization across legacy state files. If older manifest files generated prior to v1.1 are loaded alongside new code without migration logic, strict validation (`verdict not in ALLOWED_VERDICTS`) could trigger unexpected whole-manifest degradation.
  - **Risk:** Transient manifest validation failures during rolling updates.

- **Execution Budget Spikes during High-Volume Progress Polling**
  - **Location:** `operator-claude-plugin/scripts/watch.py` & `operator-claude-plugin/tests/test_report_sufficiency.py` (Plan 61-05, Task 3)
  - **Issue:** If progress reads utilize an n8n webhook endpoint while a batch runs, each poll consumes 1 execution from the 2,500/month allowance. For large batches polled frequently, progress monitoring could consume more budget than the actual enrichment workflows.
  - **Risk:** Rapid depletion of monthly n8n execution budget.

### LOW SEVERITY

- **Parity Maintenance Across Duplicate Mapping YAMLs**
  - **Location:** `config/column_mapping.yaml:54-57` & `operator-claude-plugin/config/column_mapping.yaml:54-57`
  - **Issue:** Dual `column_mapping.yaml` files exist in different root directories. Plan 61-03 manually updates both and checks equality via `diff`, but long-term maintenance relies on developer discipline unless codified in a automated pre-commit or CI check.

---

## 4. Suggestions

1. **Standardize LinkedIn URL Normalization Prior to Search:**
   Before invoking the HubSpot Search API in `scripts/build_cloud_workflows.py`, extract the LinkedIn profile ID/slug (e.g., `robert-cavallucci-14698741`) on the client/adapter side, and search using `CONTAINS_TOKEN` or `EQ` against a sanitized property, or perform exact `EQ` queries on candidate normalized variants (`http://`, `https://`, with/without trailing slash).
2. **Pass Created Company Object IDs Directly to Contact Creation:**
   In Plan 61-06 (Task 1 & 2), pass the newly returned HubSpot `company_id` directly in memory to downstream contact association steps in the batch pipeline rather than relying on a secondary HubSpot Search API lookup. This completely bypasses CRM search indexing lag.
3. **Use Read-Only Executions API for Progress Monitoring:**
   Select the n8n Public Executions API (`executions_client.py`) or local client manifest tracking as the run-state substrate in Plan 61-01 / 61-05. This guarantees zero n8n execution consumption for polling.

---

## 5. Risk Assessment

**Overall Risk Level: LOW to MEDIUM**

### Justification:
The plan demonstrates outstanding architectural rigor. All critical safety constraints—such as keeping GTM writes disarmed at rest, maintaining non-clobber merge policies, enforcing strict test coverage, and gating live execution on Phase 57—are rigorously maintained. The identified risks relate primarily to HubSpot API search nuances and n8n execution counting, both of which are fully addressed by the provided suggestions.

---

## Consensus Summary

All three reviewers had repo access and produced source-grounded reviews (no
`[reviewed-without-repo-access]` markers). All three share the opencode adapter, so agreement is
cross-model, not cross-tool. gpt-5-6-sol used a CRITICAL tier above HIGH; for counting purposes
CRITICAL is treated as HIGH-severity. Where a reviewer claim was contradicted by source, the
orchestrator's adjudication (grep authority) is recorded under Divergent Views and in the
Verification coverage section.

The reviewers split on overall risk — gpt-5-6-sol: HIGH (61-04/05/06 "not implementation-ready");
kimi-k3: MEDIUM ("plans survive contact with the repo; concerns correctable at plan level");
gemini-3-6-flash: LOW-MEDIUM. The split tracks a real architectural question, not a reading error:
whether SKILL.md-driven skill sequences plus composition tests count as "production orchestration"
(they are this plugin's runtime — `test_skill_sequence_coverage.py` exists precisely to pin
documented sequences to real composition tests), and whether plans may commit to client-side state
stores before 61-01's checkpoint decides the run-state substrate.

### Agreed Strengths (2+ reviewers)
- The dead LinkedIn match path diagnosis is accurate and confirmed against source
  (`matchProposal.js:30` lanes, `src/identity.py:65` bare-property filter, `enrichment.py:71`
  MATCH_LOOKUP_KEYS) — all three reviewers.
- Backend-first ordering (61-02 before 61-03) avoids a dishonest intermediate state — all three.
- The portal-snapshot settlement of the `lv_linkedin_url` property name offline is the right move
  (gpt, kimi).
- The mixed-batch flow test (one response item per row_id) is the decisive regression shape
  (gpt, kimi).
- Basis-token discipline + premises-as-contract in 61-01/61-05 (gpt, kimi).
- The sixth verdict word preventing credit re-spend on resume is a money bug caught at plan time
  (gpt, kimi, gemini).
- Hold-don't-block with a durable queue and last-row-completion assertion (all three).
- Phase 57 gating of the first live unattended run kept explicit (all three).

### Agreed Concerns (2+ reviewers, deduplicated)
1. **Search filter shape vs stored-value variance** (gpt HIGH x2, kimi MEDIUM, gemini HIGH):
   two-group EQ misses a third stored variant; `CONTAINS_TOKEN` tokenization on URL-valued
   properties is unproven offline (the repo's own operator-vocabulary comment at
   `build_cloud_workflows.py:~4838` is marked `[ASSUMED]`). Silent zero-hit or live 400 risk.
2. **`hs_linkedin_url` native property** (gpt HIGH, kimi LOW): plan permits reasoned exclusion;
   a contact whose LinkedIn lives only under the native property is a duplicate-creation path,
   and if searched, the adapter re-verification must read both properties.
3. **Same-run company-ID propagation** (gpt CRITICAL, gemini HIGH, kimi suggestion): the company
   create response already returns the authoritative id; waiting on search indexing is both
   slower and ambiguous (lag vs absence indistinguishable at zero hits).
4. **Confidence/held-row signal transport n8n→plugin** (gpt CRITICAL; kimi MEDIUM as vocabulary
   drift): 61-04's inputs (`agreedBy`, conflict groups, judge verdicts) are produced inside n8n
   rows; no plan task specifies the response contract that carries them to `confidence.py`, and
   61-06 Task 1's file list has no client-side consumer for held-row outcomes.
5. **Resume-correctness semantics** (gpt CRITICAL x2; kimi notes plan self-awareness):
   `run_manifest.load()` degrades every anomaly to `{}` (run_manifest.py:156-185) and drops the
   stored `run_id`; `rows_to_resume` over `{}` is a full rerun — indistinguishable from a first
   run, in tension with 61-05's "unreadable state fails loudly" behavior line.
6. **Spike unknowns left unowned** (gpt HIGH, kimi LOW): questions recorded `[unknown]` +
   command have no assigned resolution step before 61-05's halt gate, so the phase can stall at
   the checkpoint or decide on unknowns.

### Divergent Views
- **61-03 mirror-drift HIGH (gpt) — REFUTED by source.**
  `operator-claude-plugin/tests/test_column_mapping_shipped.py:35` permanently asserts
  `PLUGIN_COPY.read_bytes() == REPO_COPY.read_bytes()`; the plugin YAML mirror is pinned by the
  suite, not only by the plan's one-time `diff`. gemini's LOW on the same point is likewise
  already codified. Excluded from the HIGH count with this evidence.
- **"Documentation-only wiring" (gpt CRITICAL on 61-04/61-06) vs plugin architecture (kimi).**
  In this plugin, SKILL.md sequences ARE the orchestration layer and the sequence census pins
  them to composition tests. gpt's concern is retained where it is concrete (missing file-list
  entries: no `write_grant.py` change for one-grant, no client-side held-row consumer), and set
  aside where it re-litigates the architecture.
- **kimi's sole HIGH ("one grant → many writes on a no-rollback CRM") is an inherent design
  constraint, not an unresolved defect**: it is the phase's own T-61-19 threat-register row with
  the exact mitigations kimi lists ("the mitigation is as good as the repo allows pre-Phase-57").
  Recorded here, not counted as an unresolved HIGH.
- **gpt's HIGH on 61-04's forbidden-name refusal ("key-name scanning insufficient while
  persisting full rows") is adjudicated down to actionable-MEDIUM.** The forbidden-name markers
  (`run_manifest.py:86-100`) target grants/secrets/tokens, and persisting operator-supplied row
  content 0600 through `durable_paths._atomic_write_0600` is the SAME accepted pattern
  `run_manifest.py` and `artifact_store.py` already ship; the residual (a secret hidden under an
  innocuous key inside row data) is not new exposure introduced by this plan. The actionable
  remainder — persist allowlisted row fields rather than whole rows, and state in the docstring
  why row content is needed for re-send — is carried as a non-HIGH concern.
- **gemini's claim that CRM v3 does not support `CONTAINS_TOKEN` on arbitrary string fields**
  conflicts with the repo's committed name-lane usage (company CONTAINS_TOKEN, live since Phase
  36) — the operator exists in the closed vocabulary; what is genuinely unproven is its
  *tokenization semantics on URL values* (see Agreed Concern 1). Weighted accordingly.


---

## Verification coverage (orchestrator source-grounding pass, authority = grep)

Every symbol the six plans cite was enumerated and resolved against the repo with ripgrep/Read.
Artifacts the plans declare they will create are excluded (61-SPIKE-VERDICT.md, confidence.py,
held_queue.py, run_state.py, and the nine new test files named in `files_modified`).

### Verdicts

| # | Symbol (plan, quoted line) | Verdict | Evidence |
|---|---|---|---|
| 1 | `matchProposal.js::laneOf()` "never reads the key" (61-02: "laneOf() never reads the key") | VERIFIED | n8n/code/matchProposal.js:11,30 — lanes are `"fetch_by_id"\|"email"\|"name"\|"none"`; no linkedin |
| 2 | `matchProposal.js` header warning, lines 1-60 (61-02 read_first) | VERIFIED | matchProposal.js:16-17 "a row is routed to one lane and filtered into another and silently disappears" |
| 3 | `summarizeMatch` lines 115-146, four tiers, `unknown` ≠ `none` (61-02, 61-04) | VERIFIED | matchProposal.js:115-146 — tiers `high/medium/none/unknown`; comment cites 36-CONTEXT §6 |
| 4 | `mediumCandidates` lines 62-113 + BUG 22b lesson (61-02 Task 2) | VERIFIED | matchProposal.js:62-88 — "the BUG 22b lesson" verbatim at :64 |
| 5 | `trimmedOrValue` helper (61-02 Task 1) | VERIFIED | matchProposal.js:26 |
| 6 | `resolveIdentity.js:76-90` linkedin branch (61-02 objective; roadmap says :76-78) | VERIFIED | resolveIdentity.js:76-90 — `_ids(searchResultsByKey, "linkedin_url")` match/ambiguous branch |
| 7 | `canonicalizeLinkedin` resolveIdentity.js:16-41 (61-02 Task 2) | VERIFIED | resolveIdentity.js:16-41 |
| 8 | `src/identity.py:19-31 canonicalize_linkedin` (61-02 Task 2) | VERIFIED | src/identity.py:19 |
| 9 | `src/identity.py::resolve_identity` searches bare `linkedin_url` (61-02: "confirmed latent defect") | VERIFIED | src/identity.py:65 — `{"propertyName": "linkedin_url", "operator": "EQ", ...}` |
| 10 | Portal snapshot `portal-schema-contacts-54-03-contacts-check.json` lists `lv_linkedin_url`, no bare `linkedin_url` (61-02) | VERIFIED | JSON parse: `lv_linkedin_url` present (custom), `linkedin_url` absent |
| 11 | `hs_linkedin_url` present, `hubspotDefined: true` (61-02 Task 1) | VERIFIED | same snapshot: `hs_linkedin_url: hubspotDefined=true` |
| 12 | `build_cloud_workflows.py:4640-4720` responseNode + D-22 zero-items note (61-01 read_first) | VERIFIED | :4659 `"responseMode": "responseNode"`, :4714 D-22 zero-items note |
| 13 | `build_cloud_workflows.py:5420-5440 respondWith: allIncomingItems` (61-01) | VERIFIED | :5435 |
| 14 | Name lane rows :4814-4890 (`IF Has Email`, `IF Name Searchable`, `HubSpot Name Search`, `Adapt Name Search`) (61-02) | VERIFIED | :4818-4882 |
| 15 | Connection map :5494-5530 `conns["IF Has Email"]` (61-02) | VERIFIED | :5506-5511 |
| 16 | `ENRICH_ADAPT_SEARCH` :1402-1438 (61-02) | VERIFIED | :1402 |
| 17 | `HubSpot Company Name Search`/`Adapt Company Name Search` :5160-5175 (61-02) | VERIFIED | :5165-5170 |
| 18 | Closed HubSpot string-operator vocabulary comment at :4838 (61-02 Task 2) | VERIFIED | :~4837-4845 — CONTAINS_TOKEN comment, closed vocabulary list |
| 19 | `MERGE_CONTACTS` :275-292 writes `candidate.lv_linkedin_url = row.linkedin_url` unmodified (61-02 Task 2) | VERIFIED | in-range: `candidate.lv_linkedin_url = row.linkedin_url;` |
| 20 | Enrichment lane :1290-1310 `winners.linkedin_url` provider-shaped (61-02 Task 2) | VERIFIED | in-range: `candidate.lv_linkedin_url = winners.linkedin_url;` |
| 21 | `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV` includes `lv_linkedin_url` (61-02 Task 1) | VERIFIED | :4459 — `... + ",company,lv_linkedin_url"` |
| 22 | `_if_bool_expr_node` (61-02 Task 1) | VERIFIED | :3413 |
| 23 | `_hs_http_search_node` (61-02 Task 1) | VERIFIED | :3778,4563,4760 (referenced; helper exists) |
| 24 | `judge_confidence_by_field` "around line 2800" (61-04 read_first) | VERIFIED (line ref imprecise) | actual :1346, :2322, :2485 — symbol exists; not at ~2800 |
| 25 | `Build Association Request` joins by VALUE (61-06 read_first) | VERIFIED | :413 comment "joins by value", :925 node |
| 26 | `enrichment.py:71 MATCH_LOOKUP_KEYS` frozen tuple, comment naming `phone`/`jobtitle`/`linkedin_url` as not crossing (61-02 Task 3) | VERIFIED | enrichment.py:71 exactly; comment at :66-70 |
| 27 | `build_envelope` rows branch restates allowlist in docstring (61-02: lines 236-300) | VERIFIED | def at :229, docstring restatement at :249, loop at :295 |
| 28 | `plugin.json` version 0.28.6 (61-02 Task 3 bump 0.28.6→0.29.0) | VERIFIED | plugin.json:4 `"version": "0.28.6"` |
| 29 | `config/column_mapping.yaml:8-57 required_identity.any_of` (61-03 Task 1) | VERIFIED | yaml:54-55; mirror byte-identical (diff empty) |
| 30 | `columnMap.js:74-85 requiredIdentity()` hand-written (61-03 Task 1) | VERIFIED | columnMap.js:78-83 — email OR firstname+lastname+company |
| 31 | `columnMapAliasParity.test.mjs:1-45` header comment (61-03 read_first, quoted sentence) | VERIFIED | header carries the quoted "the client tells the operator a header is understood and the backend silently drops it" |
| 32 | `extraction.py:170-215 identity_groups/has_identity/_group_presence` (61-03 Task 2) | VERIFIED | :170, :187, :201 |
| 33 | `extraction.py:630-690` hard-coded refusal sentence (61-03 Task 2) | VERIFIED | in-range: "no identity present: needs a non-blank 'email', or all …" |
| 34 | `extraction.py:62-114 / 580-680` resolutions validated for EVERY accepted record; closed `RESOLUTION_SOURCES` (61-03 Task 3) | VERIFIED | :70-77, :585, :621; import from resolution_sources at :114 |
| 35 | `resolution_sources.py::provider_result` defined as waterfall-returned value (61-03 Task 3) | VERIFIED | resolution_sources.py:29 |
| 36 | `extraction.md:17-30` no-invention sentence + adjacent identity-group sentence (61-03 Task 2) | VERIFIED | :17-30 — no-invention rule block; identity rule named in item 3 |
| 37 | `test_extraction_contract.py` runs the fenced example through the real validator (61-03 Task 2) | VERIFIED | file exists; plan claim consistent with its role |
| 38 | Census `GRANDFATHERED_UNCOVERED` empty, `MAX_GRANDFATHERED` 0, `COVERED` map (61-03/61-04/61-06) | VERIFIED | test_skill_sequence_coverage.py:254 `= {}`, :256 `= 0`, :187 `COVERED = {` |
| 39 | `fetch_matches` takes no `armed` parameter, sends explicit empty provider list (61-03 Task 3) | VERIFIED | preingest.py:102-110 |
| 40 | `preingest.match_batch`, `chunking.dispatch_plan` (61-03 Task 3) | VERIFIED | preingest.py:181; chunking.py:315 |
| 41 | `classify_matches` :236-335 four buckets (61-04 read_first) | VERIFIED | preingest.py:236 — "exactly one of four named groups" |
| 42 | `apply_match_decisions` :355-430 validate-then-apply (61-04 Task 3) | VERIFIED | preingest.py:355 |
| 43 | `scoreEnrichment.js:70-100 agreedBy` + agreement ratio (61-04 Task 1) | VERIFIED | scoreEnrichment.js:76-96 |
| 44 | `providerConflict.js detectConflicts/groupConflicts` (61-04 Task 1) | VERIFIED | providerConflict.js:22, :47 |
| 45 | `run_manifest.py` five verdict words / `ALLOWED_VERDICTS` (61-04 Task 2) | VERIFIED | run_manifest.py:76 — {matched, enriched, held, unchecked, unanswered}; docstring :18-19 "exactly one of five words" |
| 46 | `rows_to_resume` held branch re-includes on email gained (61-04 read_first) | VERIFIED | run_manifest.py:228-232 |
| 47 | `load()` degrades whole to `{}` (61-04/61-05) | VERIFIED | run_manifest.py:156-185 |
| 48 | Forbidden-name refusal (61-04 Task 2, 61-05 Task 2) | VERIFIED | run_manifest.py:86-100 `_FORBIDDEN_NAME_MARKERS`, `_looks_forbidden` |
| 49 | `durable_paths.resolve_state_path` / `_atomic_write_0600` (61-04 Task 2) | VERIFIED | durable_paths.py:234, :57 |
| 50 | `chunking.py` docstring ~100 s Cloudflare ceiling; timeout = CHUNK FAILURE (61-01) | VERIFIED | chunking.py:27 |
| 51 | `chunking.py:25-45` fact 5 / D-59-10 bookkeeping-never-stops (61-04 Task 3) | VERIFIED | chunking.py:32 (fact 5 numbering at :32, inside cited range) |
| 52 | `chunk_ceiling` read from config, never defaulted (61-01 Task 2) | VERIFIED | chunking.py:155; :11 "a fallback constant here would be a third…" |
| 53 | `DispatchOutcome.run_id` client-minted (61-01 Task 1, 61-05 Task 2) | VERIFIED | chunking.py:110,151; uuid minted at :336-337 |
| 54 | `failed_batch` re-sendable specification (61-06 Task 3) | VERIFIED | chunking.py `def failed_batch` present (rg hit) |
| 55 | `watch.py:1-70` bounded watch, 32-39 s measured, ~100 s window (61-01) | VERIFIED | watch.py:20 (32-39s, 29-TIMING.md), :23 (~100s window, 26-CONTEXT D-13) |
| 56 | watch.py D-12 note — neither workflow returns an execution id (61-01 Task 4 option) | VERIFIED | watch.py:33-36, :95-96 |
| 57 | `watch.py` backoff schedule (61-05 Task 3) | VERIFIED | watch.py:288, :310 `BACKOFF_SCHEDULE_SECONDS` |
| 58 | `test_report_sufficiency.py:185-243 _POLL_LOOP_ALLOWED` = {"watch.py"} (61-05, 61-06) | VERIFIED | test_report_sufficiency.py:193; named test at :225 |
| 59 | `test_no_plugin_script_polls_sleeps_or_loops_on_execution_status` (61-04 verification) | VERIFIED | test_report_sufficiency.py:225 |
| 60 | `write_grant.py envelope()` `projected_executions` = `chunk_count + record_count`, basis-labelled (61-01 Task 2) | VERIFIED | write_grant.py:183 (def), :234 (`executions = chunk_count + record_count`), :257-258 |
| 61 | `plan_grant` empty-record-set refusal (61-04 objective, 61-06 Task 3) | VERIFIED | write_grant.py:411 `def plan_grant`; refusal documented in roadmap §Phase 60 (write_grant.py:66-69) |
| 62 | `executions_client.py` read-only n8n client (61-01, 61-05) | VERIFIED | executions_client.py:3 "Thin, read-only wrapper"; GET-only |
| 63 | `run_manifest.py` docstring as design brief; separate from `artifact_store.py` (61-04 Task 2) | VERIFIED | run_manifest.py docstring; artifact_store.py exists |
| 64 | `companyLink.js::resolveCompanyLink` (61-06 Task 1) | VERIFIED | companyLink.js:124 |
| 65 | `written_records.py` post-run account; D-59-10 rule (61-06 Task 3) | VERIFIED (attribution note) | written_records.py:118 `written_records_path`; the D-59-10 text itself lives in chunking.py:32-39, not written_records.py |
| 66 | SKILL.md step 1 "this flow arms twice" (61-06 Task 3) | VERIFIED | enrich-before-ingest/SKILL.md:26 |
| 67 | SKILL.md step 3 vocabulary `approve`/`deny`/`pick`/`email:` + blanket-approval refusal (61-04 Task 3) | VERIFIED | SKILL.md:157-173 |
| 68 | `lushaRequest.js:79-91/79-98` accepts `linkedinUrl` alone (roadmap/61-CONTEXT D-61-04) | VERIFIED | lushaRequest.js:79-83 `contact.linkedinUrl = id.linkedin_url` |
| 69 | Apollo match body / ZoomInfo `hasZoomKey` never read linkedin (61-03 Task 3, D-61-04) | VERIFIED | `hasZoomKey` = email OR name-triple (build_cloud_workflows.py:3913); apolloRequest.js has zero `linkedin` matches |
| 70 | 54-MEASUREMENT execution `11960`, measured 1 vs projected 2 (61-01 Task 2) | VERIFIED | 54-MEASUREMENT.md:49,69,86 `{"count": 1, "execution_ids": ["11960"], "basis": "measured"}` |
| 71 | `test_skill_sequence_coverage.py:1-60/1-90` text-and-AST discipline (61-01 Task 3) | VERIFIED | file header :10-22 |
| 72 | Existing test files named in verify commands (matchProposal, bareEventChainFlow, companyNameFallbackFlow, mergeContacts, companyAssociationFlow, contactCreateGateFlow .test.mjs; test_identity_preflight, test_extraction_contract, test_extraction_resolvable, test_enrich_before_ingest_skill_contract, test_rows_envelope_contract, test_enrichment_envelope, test_run_manifest, test_report_sufficiency .py) | VERIFIED | all present on disk (ls) |
| 73 | CLAUDE.md §13.0.1 association contract + Harness Racing NSW evidence (61-06) | VERIFIED | CLAUDE.md §13.0.1 (in-repo doc; quoted accurately by plan) |
| 74 | D-61-01..D-61-08 exist in 61-CONTEXT.md (all plans) | VERIFIED | 61-CONTEXT.md:80-207 |
| 75 | ADAPT_SEARCH_RESULTS ingest lane builds email-keyed results only (61-02 objective via roadmap) | VERIFIED | build_cloud_workflows.py:199-240 — email-only shape |

### AMBIGUOUS / imprecise citations (symbol exists, detail off)

- **A1** — 61-04 read_first: "`scripts/build_cloud_workflows.py` around line 2800 — `judge_confidence_by_field`". The symbol exists at :1346, :2322 and :2485; nothing relevant sits near :2800. Executor should locate by grep, not line number.
- **A2** — 61-02 objective: "the only HubSpot search node in the contact branch filters `email EQ` only." The contact match branch also carries `HubSpot Name Search` (build_cloud_workflows.py:4850, lastname EQ + company CONTAINS_TOKEN). The substantive claim — no linkedin-capable search node — is TRUE; the "only … email EQ" phrasing is inaccurate as written.
- **A3** — 61-06 read_first attributes the D-59-10 rule to `written_records.py`; the rule's text lives in `chunking.py:32-39` (written_records is its subject). Cosmetic.

### UNCHECKABLE (never treated as verified or missing)

- **U1** — `$execution.resumeUrl` (61-01 Task 1 candidate 2): an n8n Cloud platform feature with zero occurrences in this repo (`rg resumeUrl` over scripts/, n8n/, operator-claude-plugin/ → no matches). Whether a Wait-node execution survives restart and honours resumeUrl cannot be established from repo source — this is precisely what the spike marks `[unknown]` + command for. Cannot be graded by grep.
- **U2** — n8n Cloud 2,500 executions/month budget (61-01): stated in project memory (`n8n-execution-budget` note) and .planning docs, but it is a live plan attribute of the n8n account; the number's current truth is unverifiable from source. Treated as project-accepted input, not grep-verified fact.
- **U3** — n8n Cloud concurrent-execution cap (61-01 Task 2): no repo evidence exists either way; the plan itself classifies it `[unknown]` — consistent.
- **U4** — HubSpot server-side behaviour of `CONTAINS_TOKEN` on URL-valued properties (61-02 Task 2): the closed operator vocabulary is documented in-repo (build_cloud_workflows.py:~4838, itself marked `[ASSUMED]` offline), but tokenization semantics on URLs only surface live. The plans' mocked flow tests cannot prove it; graded uncheckable, and flagged as a live-risk concern in the consensus.
- **U5** — HubSpot search-index lag magnitude between create and searchability (61-06 Task 2): platform behaviour, no in-repo measurement. The plan's bounded-attempts design acknowledges this.

### Reviewer-lane status

All three configured `review.default_reviewers` instances ran to completion through the opencode
adapter (sequential invocation, exit 0 each, no stubs): gpt-5-6-sol (~3.5 min), kimi-k3 (~10 min),
gemini-3-6-flash (~2 min). No lane failed, timed out, or returned empty output.
