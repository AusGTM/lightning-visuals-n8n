---
phase: 61
cycle: 2
reviewers: [gpt-5-6-sol, kimi-k3, gemini-3-6-flash]
reviewed_at: 2026-08-30T03:15:00Z
plans_reviewed: [61-01-PLAN.md, 61-02-PLAN.md, 61-03-PLAN.md, 61-04-PLAN.md, 61-05-PLAN.md, 61-06-PLAN.md]
---

# Cross-AI Plan Review — Phase 61 (CYCLE 2)

> Cycle 1's full findings live at commit `b331163` (this file's previous version); the plans'
> `<review_dispositions>` sections restate every cycle-1 finding with its disposition. This
> cycle counts RESIDUALS only: cycle-1 findings whose disposition is missing or inadequate,
> plus NEW findings introduced by the revision (commit `8aa942b`).

> Note: gpt-5-6-sol, kimi-k3 and gemini-3-6-flash all share the opencode adapter; their consensus is cross-model, not cross-tool.

## OpenCode Review (gpt-5-6-sol)

I’m validating the revised plans against the cycle-1 review and the cited source symbols, then I’ll report only residual or newly introduced issues.
# Phase 61 Cycle 2 Review

The revisions resolve most cycle-1 findings, particularly identity-property coverage, multi-hit handling, durable no-invention protection, generated-artifact inventory, held-row transport, progress invariants, and Phase 57 gating. Plans 61-02, 61-04, 61-05, and 61-06 still contain implementation-level gaps. The most consequential are the immediate-run-handle assumption in 61-05, incomplete confidence and resume contracts in 61-04, LinkedIn cardinality/search-shape contradictions in 61-02, and unspecified created-ID provenance and transport in 61-06.

## 61-01: Execution-Model Spike

### Summary

The revised spike substantially addresses cycle 1’s unowned-premise finding. Unknowns now have dependents, commands, and human owners, and 61-05 can mechanically determine whether it must halt. The remaining concern is that parts of the checkpoint still state substrate conclusions before the spike establishes them.

### Strengths

- Premises require explicit dependent plan/task IDs, making later halt decisions mechanical rather than discretionary: `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:188-215`.
- Every unresolved premise must carry a probe command and an operator/admin owner: `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:202-215`.
- The blocking checkpoint requires the operator to see and disposition every unresolved premise: `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:227-250`.
- The revised “claim line” definition is concrete enough for deterministic linting: `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:119-126`.
- The plan correctly preserves the distinction between measured single-chunk cost and unmeasured multi-chunk behavior: `.planning/phases/54-single-pass-armed-dispatch/54-MEASUREMENT.md:108-120`.
- The executions API correlation limitation is real: current matching is time-based because the workflow does not return an execution ID, as documented in `operator-claude-plugin/scripts/watch.py:33-36` and `operator-claude-plugin/scripts/watch.py:93-97`.

### Concerns

- **MEDIUM, residual:** The checkpoint options still assert facts that the spike itself says may remain unknown. For example, the HubSpot option says state survives an n8n restart, while the static-data option states one execution per poll. Restart behavior and billing are explicitly identified as likely unresolved at `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:236-243`, but the unqualified claims appear at `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:253-271`.
- **MEDIUM, new:** The must-have refers to “the spike’s six questions,” but no stable six-question set is enumerated. Task 1 defines four questions per substrate, while arithmetic and concurrency are added separately: `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:21`, `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:80-95`, `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:146-170`.
- **LOW, new:** Plan metadata says `tasks: 3`, but the plan contains three automatic tasks and one blocking decision checkpoint: `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:16`, `.planning/phases/61-autonomous-batch-runs/61-01-PLAN.md:227`.

### Suggestions

- Assign explicit IDs such as `Q-01` through `Q-06` and make the test assert those IDs.
- Generate the checkpoint’s pros and cons from the completed verdict, or mark provisional claims with basis tokens.
- Change the task count to four, or rename it to `automatic_tasks: 3`.

### Risk Assessment

**LOW-MEDIUM.** No production code changes here. The remaining risk is an operator selecting a substrate from checkpoint wording stronger than the evidence produced by the spike.

---

## 61-02: LinkedIn Backend Match Lane

### Summary

The revision resolves the central cycle-1 concerns around bounded normalization, native-property coverage, cardinality, stale Python property names, and generated artifacts. Two newly introduced mechanism problems remain: `summarizeMatch()` is instructed to reuse an arm incapable of representing multiple candidates, and the potentially large OR-filter request is not checked against HubSpot search limits.

### Strengths

- The diagnosis of the dead lane is source-grounded: `laneOf()` currently supports ID, email, name, and none, but not LinkedIn: `n8n/code/matchProposal.js:30-41`.
- The plugin currently strips LinkedIn from rows envelopes exactly as claimed: `operator-claude-plugin/scripts/enrichment.py:66-71`.
- The Python oracle currently names the wrong property in both its property list and search filter: `src/identity.py:15-16`, `src/identity.py:63-71`.
- The revision replaces an unbounded normalization promise with an explicitly bounded, test-pinned variant set: `.planning/phases/61-autonomous-batch-runs/61-02-PLAN.md:247-268`.
- Searching both `lv_linkedin_url` and `hs_linkedin_url`, re-verifying values, deduplicating by contact ID, and refusing self-conflicting records is a strong false-positive defense: `.planning/phases/61-autonomous-batch-runs/61-02-PLAN.md:177-194`.
- All eight workflow files written by the builder are now listed. The builder writes them at `scripts/build_cloud_workflows.py:7731-7765`.

### Concerns

- **HIGH, new:** The plan requires multiple verified LinkedIn hits to return `medium` with candidates, but instructs the implementation to join LinkedIn to the existing `fetch_by_id`/email arm: `.planning/phases/61-autonomous-batch-runs/61-02-PLAN.md:129-151`. That arm only examines `existingRecord` and does not consume candidate cardinality: `n8n/code/matchProposal.js:128-134`. If ambiguity is represented by candidates with no selected `existingRecord`, the reused arm produces `none`, not `medium`.
- **HIGH, new:** The enumerated variant cross-product may require a large number of OR filter groups across variants and two properties. The plan neither establishes HubSpot’s filter-group limit nor specifies bounded request splitting. `_hs_http_search_node` emits all supplied filter groups into one request without batching or limit validation: `scripts/build_cloud_workflows.py:6425-6432`, `scripts/build_cloud_workflows.py:6442-6479`.
- **MEDIUM, new:** The n8n lane is required to search both custom and native LinkedIn properties, but `src/identity.py` is only planned to search/request `lv_linkedin_url`: `.planning/phases/61-autonomous-batch-runs/61-02-PLAN.md:177-190`, `.planning/phases/61-autonomous-batch-runs/61-02-PLAN.md:283-300`. The claim that the Python oracle and lane tell the same story is therefore overstated for native-property-only contacts.
- **LOW, new:** One `read_first` location points near the company-name fallback rather than the contact fetch-property constant. The action later says to locate the constant by name, reducing this to navigation ambiguity: `.planning/phases/61-autonomous-batch-runs/61-02-PLAN.md:112-114`, `.planning/phases/61-autonomous-batch-runs/61-02-PLAN.md:164-169`.

### Suggestions

- Define a dedicated LinkedIn arm in `summarizeMatch()`:
  - Lookup failure: `unknown`
  - Zero verified hits: `none`
  - One verified hit: `high`
  - Multiple verified hits: `medium` with candidates
- Establish the CRM search filter-group limit before implementation. Split the searches by property or variant batch if necessary, then merge and deduplicate.
- Either make `src/identity.py` search both properties or explicitly declare that it is not a parity oracle for native-property-only records.

### Risk Assessment

**MEDIUM-HIGH.** The safety policy is good, but the current instructions could either mishandle ambiguity or generate an invalid HubSpot search request, leaving the LinkedIn lane functionally dead.

---

## 61-03: Front-End Identity Contract

### Summary

This plan is close to implementation-ready. It correctly coordinates the YAML, Python, JavaScript, prose, tests, and generated workflow artifacts. The cycle-1 findings assigned to this plan are effectively resolved.

### Strengths

- The authoritative groups currently exist in the root YAML at `config/column_mapping.yaml:54-57`.
- The independent JavaScript implementation is correctly identified at `n8n/code/columnMap.js:78-83`.
- The existing permanent byte-parity assertion already protects the two YAML copies: `operator-claude-plugin/tests/test_column_mapping_shipped.py:29-39`.
- The plan explicitly handles the exact refusal-string assertion that must change: `operator-claude-plugin/tests/test_extraction_contract.py:233-241`.
- The no-invention rule gains a durable exact-string test rather than relying on a one-time summary check.
- `tests/test_e2e_ingest.py` is included because `src/file_loader.py` consumes the same root YAML.

### Concerns

- **LOW, new:** Task 2 explicitly requires changing `test_extraction_contract.py`, but that file is absent from Task 2’s local `<files>` declaration. It is present in the plan-level `files_modified`, so this is executor-scope ambiguity rather than missing overall scope: `.planning/phases/61-autonomous-batch-runs/61-03-PLAN.md:146-181`.

### Suggestions

- Add `operator-claude-plugin/tests/test_extraction_contract.py` to Task 2’s `<files>` list.

### Risk Assessment

**LOW.** The only remaining issue is procedural metadata. The implementation mechanisms and regression coverage are coherent.

---

## 61-04: Confidence and Held Queue

### Summary

The revision makes substantial progress by defining a versioned n8n-to-plugin outcome projection, adding fail-closed parsing, recording hold fingerprints, scoping manifests by run, and introducing a client-side durable held queue. However, the actual confidence table remains incomplete, and the fingerprint-resume mechanism does not yet define how queue state reaches `rows_to_resume()`.

### Strengths

- `Build Response` already spreads the row, so extending the current response is appropriately smaller than inventing a second envelope: `scripts/build_cloud_workflows.py:4397-4408`.
- `agreedBy` is a real existing signal generated by scoring: `n8n/code/scoreEnrichment.js:74-97`.
- Material conflict groups are already generated in the workflow builder: `scripts/build_cloud_workflows.py:2466-2474`.
- `judge_confidence_by_field` exists at `scripts/build_cloud_workflows.py:1346`, `scripts/build_cloud_workflows.py:2322`, and `scripts/build_cloud_workflows.py:2485`.
- Unknown or absent outcome-contract versions explicitly fail toward hold: `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:124-145`.
- The proposed queue follows the existing atomic `0600` persistence authority: `operator-claude-plugin/scripts/durable_paths.py:57-81`.
- The revision correctly moves from arbitrary row persistence to an allowlisted row projection: `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:291-298`.
- Per-run manifest scoping addresses the current global-path behavior in `operator-claude-plugin/scripts/run_manifest.py:56` and `operator-claude-plugin/scripts/run_manifest.py:103-114`.

### Concerns

- **HIGH, residual:** Provider agreement is named as a confidence input but has no decision rows. The behavior covers match tier, conflict, and judge adjudication, but does not define single-provider evidence, multi-provider agreement, disagreement, or explicit no-enrichment cases: `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:186-219`.
- **HIGH, residual:** The queue stores the fingerprint, while the manifest owns the resume verdict, but the comparison join is undefined. Current `rows_to_resume(rows, manifest)` accepts only rows and a verdict map: `operator-claude-plugin/scripts/run_manifest.py:207-210`. The revised plan does not specify a new signature or another function joining current outcomes to held-queue entries: `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:279-317`.
- **HIGH, new:** The confidence rule needs ambiguity cardinality, but Task 1’s four-field outcome contract includes only match tier, provider agreement, material conflicts, and adjudicated fields: `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:124-126`. Existing client classification determines ambiguity from candidate count: `operator-claude-plugin/scripts/preingest.py:304-320`.
- **MEDIUM, new:** Changing `load()` to return a stored `run_id` alongside verdicts changes an established return contract. Current consumers treat the return directly as the verdict map, including `rows_to_resume`: `operator-claude-plugin/scripts/run_manifest.py:207-210`. The plan does not define a compatibility shape or caller migration: `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:339-351`.
- **MEDIUM, new:** Failed chunks are supposed to enter the held queue, but the closed `hold_code` set is not enumerated and no fingerprint semantics are defined for transport failures: `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:263-289`, `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:394-402`.

### Suggestions

- Put the complete ordered confidence table in the plan, including agreement, disagreement, one-provider, no-provider, ambiguous-match, malformed, and unknown-version rows.
- Add candidate count or match uniqueness to the outcome contract.
- Define one concrete resume API that receives manifest verdicts, held entries, and current typed outcomes joined by `run_id` and `row_id`.
- Preserve `load()` compatibility by adding a separate typed `load_document()` result, or explicitly migrate every caller to `.verdicts`.
- Enumerate `hold_code` values and distinguish confidence holds from chunk/transport failures.

### Risk Assessment

**MEDIUM-HIGH.** The persistence direction is sound, but isolated helper tests could pass while the real confidence and resume composition remains undefined.

---

## 61-05: Async Submit, Progress, and Resume

### Summary

The revision improves premise gating, progress arithmetic, report-state distinctions, and live-checkpoint bounds. It is not yet implementation-ready because it treats a `run_id` returned after synchronous dispatch as an immediate submission handle and does not resolve how detached n8n work updates local plugin state.

### Strengths

- The progress invariant is explicit and testable: `.planning/phases/61-autonomous-batch-runs/61-05-PLAN.md:155-160`.
- The selected substrate must be cited in `run_state.py`, preventing silent architectural substitution: `.planning/phases/61-autonomous-batch-runs/61-05-PLAN.md:150-153`.
- Missing, corrupt, and wrong-run state receive distinct report treatment: `.planning/phases/61-autonomous-batch-runs/61-05-PLAN.md:220-234`.
- The checkpoint is bounded to no creates, no provider spend, one chunk, and test/return-only records: `.planning/phases/61-autonomous-batch-runs/61-05-PLAN.md:286-297`.
- Per-run state naming has a valid precedent in `operator-claude-plugin/scripts/written_records.py:118-128`.

### Concerns

- **CRITICAL, new:** `DispatchOutcome.run_id` is not an immediate submission handle. `dispatch_plan()` creates the ID internally but returns it only after the synchronous chunk loop completes: `operator-claude-plugin/scripts/chunking.py:315-337`, `operator-claude-plugin/scripts/chunking.py:344-417`. This contradicts the assertion that the handle already exists in the required sense: `.planning/phases/61-autonomous-batch-runs/61-05-PLAN.md:137-138`.
- **CRITICAL, residual:** The plan unconditionally says `run_state.py` reports over local `held_queue.py` and `run_manifest.py`: `.planning/phases/61-autonomous-batch-runs/61-05-PLAN.md:173-175`. If n8n continues after the client has returned, n8n Cloud cannot update files on the operator’s machine. The selected substrate must determine the authoritative state writer and read path.
- **HIGH, residual:** The plan still calls unreadable state “fail loudly” while deliberately rerunning the whole batch with a warning: `.planning/phases/61-autonomous-batch-runs/61-05-PLAN.md:199-203`, `.planning/phases/61-autonomous-batch-runs/61-05-PLAN.md:220-233`. That is “rerun whole with loud disclosure,” not a failed run.
- **HIGH, new:** “Write verdicts per chunk” does not define an atomic read-merge-write update. Current `run_manifest.save()` writes the supplied verdict map as the complete document: `operator-claude-plugin/scripts/run_manifest.py:117-153`. Saving only the latest chunk would erase previous completion state.
- **MEDIUM, new:** This plan depends on the revised manifest API from 61-04, but does not pin how a result containing `run_id` plus verdicts is passed into the existing `rows_to_resume()` contract.

### Suggestions

- Mint the `run_id` before submission and pass it into the detached worker.
- Make the selected substrate’s store the authoritative progress state. Local files may cache or render it, but cannot be the remote writer after disconnect.
- Add an atomic `update_verdicts(run_id, chunk_verdicts)` operation that merges with accumulated state.
- Rename the corrupt-state behavior to “full rerun with loud disclosure,” or change it to an actual halt.
- Pin the exact 61-04 manifest result type and resume call.

### Risk Assessment

**HIGH.** The plan could pass injected-transport tests while still returning the handle after completion or reporting stale local state during detached execution.

---

## 61-06: Unattended Pair Pipeline

### Summary

The revision correctly chooses the ingest lane for association, places held-row persistence on the client side, and replaces search-index waiting with direct same-run company-ID propagation. The remaining gaps are the lack of a named post-create ID adapter, an under-specified security boundary for admitting created IDs to a grant, and an unscoped written-records report.

### Strengths

- The association route is now decided rather than delegated to executor preference: `.planning/phases/61-autonomous-batch-runs/61-06-PLAN.md:117-125`.
- Existing ingest behavior already holds unresolved creates: `scripts/build_cloud_workflows.py:567-577`.
- Existing association requests already join responses by value rather than index: `scripts/build_cloud_workflows.py:429-468`.
- The revision correctly recognizes that n8n cannot write the operator’s local queue and therefore returns hold outcomes for client-side persistence: `.planning/phases/61-autonomous-batch-runs/61-06-PLAN.md:132-151`.
- Contacts sharing one newly created company are explicitly required to coalesce: `.planning/phases/61-autonomous-batch-runs/61-06-PLAN.md:184-209`.
- Resume correctly requires a fresh grant rather than restoring authority from disk: `.planning/phases/61-autonomous-batch-runs/61-06-PLAN.md:299-302`.

### Concerns

- **HIGH, residual:** The plan requires direct propagation of the company-create response ID but does not name the adapter or join that will preserve company dependency context. Current accounting calls company creates `created_id_unknown` because the response contract lacks `hs_object_id`: `operator-claude-plugin/scripts/written_records.py:38-48`, `operator-claude-plugin/scripts/written_records.py:161-174`. The builder currently routes `HubSpot Company Create` directly to generic `Build Response`: `scripts/build_cloud_workflows.py:5676-5680`.
- **HIGH, new:** Created-ID grant admission lacks an enforceable provenance API. Current `covers()` only compares supplied IDs/domains against grant scope: `operator-claude-plugin/scripts/write_grant.py:596-642`. A generic function accepting a caller-supplied created ID would let the caller widen the grant by assertion unless it consumes a validated response from a send authorized by that same grant.
- **HIGH, new:** The end-of-run account is not explicitly scoped to the current run. `written_records.load()` without a path aggregates historical run artifacts: `operator-claude-plugin/scripts/written_records.py:291-323`. The plan should require `written_records_path(run_id)`, which exists at `operator-claude-plugin/scripts/written_records.py:118-128`.
- **MEDIUM, new:** Once the authoritative company ID is carried directly from create response to association, the remaining “create-evidenced zero-hit lag” branch appears unnecessary. The plan does not identify an operation that still requires an indexed search: `.planning/phases/61-autonomous-batch-runs/61-06-PLAN.md:211-220`.
- **MEDIUM, new:** The plan presupposes that Python `covers()` evaluates internal same-run created IDs, but `authorize_send()` checks scope at client-send boundaries: `operator-claude-plugin/scripts/write_grant.py:729-789`. Internal n8n writes do not independently invoke that Python function. The exact second send and its scoped IDs/domains need tracing before grant mutation is prescribed.

### Suggestions

- Add a named post-company-create adapter that joins the HTTP response to a run dependency and returns `{company_dependency_id, company_id}`.
- Define a closed admission API that accepts a validated authorized-send result, not a bare caller-supplied ID.
- Require the report to load `written_records_path(run_id)`.
- Remove lag polling unless a specific downstream operation still needs indexed search visibility.
- Test grant scope at the actual two-send boundary using the exact IDs and domains passed to each `authorize_send()` call.

### Risk Assessment

**HIGH.** The selected association route is sound, but missing created-ID transport or overly permissive grant admission could either strand valid contacts or widen authority beyond operator consent.

## Source-Grounding Verification

- **VERIFIED:** `write_grant.covers()` exists at `operator-claude-plugin/scripts/write_grant.py:596`. It checks lane/workflow/record/domain scope; it currently has no same-grant created-ID provenance mechanism.
- **VERIFIED:** `written_records_path(run_id)` exists at `operator-claude-plugin/scripts/written_records.py:118`. It returns a run-specific artifact path and is the correct precedent for per-run manifest/report paths.
- **VERIFIED:** `run_manifest.ALLOWED_VERDICTS` exists at `operator-claude-plugin/scripts/run_manifest.py:76` and currently contains five values. Tests pin the count at `operator-claude-plugin/tests/test_run_manifest.py:92-93`.
- **MISSING, planned addition:** `outcome_contract_version` does not currently exist in production source. Its only current repository occurrences are in the revised 61-04 plan, including `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:124-145`.
- **MISSING, planned addition:** A production `hold_code` schema does not currently exist. Current occurrences are plan text in `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:263-289`; `held_queue.py` is itself a planned new file.
- **MISSING, planned addition:** Confidence-hold signal fingerprinting does not currently exist. It is proposed at `.planning/phases/61-autonomous-batch-runs/61-04-PLAN.md:260-288`.
- **VERIFIED:** `Build Response` currently spreads all input row fields and adds remaining credits at `scripts/build_cloud_workflows.py:4397-4408`. The plan is correct that transport exists, though signal survival still requires explicit projection tests.
- **VERIFIED:** `agreedBy` is generated in `n8n/code/scoreEnrichment.js:74-97`.
- **VERIFIED:** `judge_confidence_by_field` exists at `scripts/build_cloud_workflows.py:1346`, `scripts/build_cloud_workflows.py:2322`, and `scripts/build_cloud_workflows.py:2485`.
- **VERIFIED:** `laneOf()` currently has no LinkedIn lane at `n8n/code/matchProposal.js:30-41`.
- **VERIFIED:** The current strong-key `summarizeMatch()` arm ignores candidate cardinality at `n8n/code/matchProposal.js:128-134`.
- **VERIFIED:** `MATCH_LOOKUP_KEYS` currently excludes `linkedin_url` at `operator-claude-plugin/scripts/enrichment.py:66-71`.
- **VERIFIED:** `src/identity.py` currently searches and requests bare `linkedin_url` at `src/identity.py:15-16` and `src/identity.py:63-71`.
- **VERIFIED:** `run_manifest.rows_to_resume()` currently accepts rows and a verdict mapping, with no held-queue/fingerprint input, at `operator-claude-plugin/scripts/run_manifest.py:207-210`.
- **VERIFIED:** `dispatch_plan()` creates a `run_id` but returns its `DispatchOutcome` only after the synchronous dispatch loop: `operator-claude-plugin/scripts/chunking.py:315-417`. It is not currently an immediate async submission handle.
- **VERIFIED:** `written_records.load()` can aggregate historical run files when no run-specific path is supplied: `operator-claude-plugin/scripts/written_records.py:291-323`.
- **VERIFIED:** The builder writes eight workflow JSON artifacts from `main()` at `scripts/build_cloud_workflows.py:7731-7765`.
- **AMBIGUOUS:** The maximum number of HubSpot CRM v3 search filter groups accepted by the intended request is not established in repository source. The revised 61-02 variant cross-product therefore remains unverified.
- **UNCHECKABLE offline:** n8n Cloud restart survival, detached sub-workflow behavior, concurrent execution limits, and exact execution billing. Plan 61-01 correctly routes these to `[unknown]` plus operator/admin probes, but its prewritten checkpoint descriptions should not state them as settled facts.

---

## OpenCode Review (kimi-k3)

I'll work through this systematically: first read cycle-1 findings, then verify dispositions and source-ground the cited symbols in the repo.
I have cycle-1's full findings. Now let me run the source-grounding pass on the symbols the revised plans cite. Starting with the most load-bearing ones in parallel.
`covers()` at :596-642 confirmed: `outside_ids`/`outside_domains` are checked against the grant's snapshot and refused with the GRANT-03 wording — the 61-06 REVIEW-11 premise is real. Now batch-checking the remaining cited symbols.
All verification is complete. Compiling the final review.
# Cross-AI Plan Review — Phase 61 Convergence, CYCLE 2 (kimi-k3)

Verified against the repo using ripgrep/Read. Cycle-1 findings were read in full from `.planning/phases/61-autonomous-batch-runs/61-REVIEWS.md` (all three reviewers, plus the orchestrator's adjudication and verification-coverage table). Residuals and new findings below are the only counted items per the cycle-2 rules.

## Overall assessment

The revision is substantially better than the cycle-1 draft, and most dispositions are genuinely resolved on repo evidence, not on plan prose. The six plans now decide the things cycle 1 said they left open (EQ-over-variant-set vs `CONTAINS_TOKEN`, both-properties LinkedIn search, closed cardinality rule, task 1 route, and `covers()`'s created-record gap), and the new citations check out against source almost everywhere. Respectively: one **MEDIUM residual** survives (61-04's corrupt-queue→empty semantics, un-dispositioned), plus two trivially **LOW residuals**. No revision-introduced **HIGH** findings were found.

---

## Per-plan summaries

**61-01 (spike).** The dependents-column/`## Unresolved` machinery is exactly what HIGH 4 needed in cycle 1: it turns 61-05's halt into a lookup. Task 4 reads the unknowns out by name with per-entry close options. The "claim line is defined in the test's docstring" fix is adequate for a text lint. The two REJECTED findings are defensible given the no-live-calls constraint. Residual LOW: candidate 4 (synchronous loop) is still listed as an eligible substrate rather than labeled the baseline — the verdict doc will presumably settle it, but the suggestion wasn't dispositioned.

**61-02 (backend lane).** The EQ-over-written-down-variant-set decision is the correct resolution of cycle 1's agreed concern 1; rejecting `CONTAINS_TOKEN` with an `[unknown]` + probe command is the right failure-direction (miss, never wrong person). Searching both `lv_linkedin_url` and `hs_linkedin_url`, deduplicating by contact id, and disqualifying self-disagreeing records closes the duplicate-creation path. The cardinality rule (0 → `none`, 1 → `high`, >1 → `medium`) reuses the existing candidates surface with no new vocabulary. I verified the portal snapshot directly: `lv_linkedin_url` present, `hs_linkedin_url` present (hubspotDefined), no bare `linkedin_url`, among 430 contact properties.

**61-03 (front-end).** The verbatim-pinned assertion in `test_extraction_contract.py` (actual line :237) is named as a planned edit rather than discovered-by-failure; the no-invention sentence moves from summary-check to a durable exact-string test — both were cycle-1's actionable items. The mirror-drift "refutation" is correct: `test_column_mapping_shipped.py:35` asserts byte equality permanently.

**61-04 (confidence + held queue).** The new Task 1 correctly identified that `Build Response` already spreads the row (verified: `return $input.all().map((item) => ({ json: { ...item.json, remaining_credits } }))`), so the fix is a named, versioned projection — not a new envelope. `hold_code` + fingerprint makes "resume when the signal changes" a comparison. Per-run manifest path follows the `written_records_path(run_id)` precedent (verified at `written_records.py:118`). The sixth-verdict-word rationale is a real money bug caught at plan time. **One MEDIUM residual survives here — see below.**

**61-05 (async).** The two-consumers/two-rules resolution of the resume conflict is coherent with the actual `load()` semantics I read at `run_manifest.py:156-185` (degrade whole to `{}`) — a probe classifies the file for the report path while the resume path keeps degrade-whole. The halt gate reads the dependents column mechanically. The replay bound uses the documented same-value-PATCH no-op (corroborated in `.planning/WINDOWS.md`, confirmed by grep). Checkpoint bounds (return-only/test records, no creates, empty provider list, one chunk, own window) make the live observation a plumbing check, not the first unattended run.

**61-06 (pair pipeline).** Task 1 now *decides* — route creates through the ingest lane (one association implementation), deviation requires measurement. REVIEW-11's claim about `covers()` refusing created-during-run IDs is **true by source**: `write_grant.py:629-640` computes `outside_ids` against the grant's snapshot, with "widening it needs a new grant (GRANT-03)" wording. The partial rejection (`plan_grant(:411)`/`authorize_send(:729)`/`authorize_ungranted_send(:792)` exist) is also confirmed. By-value ID propagation removes the search-lag ambiguity, leaving only one bounded residual case.

---

## Strengths (revision-level, source-verified)

- All eight workflow JSONs `main()` writes are now in every plan's `files_modified`, with "report which actually changed" required — verified at `build_cloud_workflows.py:7731-7765` (8 files: ingest local/cloud, enrichment local/cloud, enrichment live, scheduled, status, review).
- 61-02's objective text now correctly says "an `email EQ` search and a name search" — the A2 phrasing fix is literal.
- 61-04's `read_first` now says "LOCATE `judge_confidence_by_field` BY GREP" — and it exists at `build_cloud_workflows.py:1346/:1349/:2322/:2485` (verified; original ~2800 citation was indeed wrong).
- The plugin version rule — "read the file, bump the MINOR" — is consistent across 61-02/61-03/61-04/61-05/61-06, eliminating the cross-plan version drift cycle 1 found.
- `MATCH_LOOKUP_KEYS` widening rewrites the boundary rationale rather than deleting it, with the disallow list (`phone`/`jobtitle`) re-pinned in the same task — verified the current tuple at `enrichment.py:71`.
- 61-06 Task 3 pins all four `covers()`-admission constraints in `test_write_grant.py` (admitted under-grant id passes; unrelated id refuses; admission not persisted; fresh grant on resume) — T-61-24 registered rather than trust-free.

---

## Concerns — cycle-2 residuals + new

- **MEDIUM — residual (un-dispositioned cycle-1 finding).** gpt's cycle-1 HIGH on 61-04: *"Corrupt held-queue data degrading to empty silently loses rows that were intentionally not written"* (`61-REVIEWS.md:172`). The revised 61-04 Task 3 `<behavior>` still reads: *"A queue file that is missing, truncated, malformed or schema-mismatched degrades to an empty queue, never to a partially-trusted one."* 61-05's manifest got the absent/parseable/anomalous/wrong-run probe resolution, but the held queue — the operator's entire review surface — did not. Under the counting rules, this finding's disposition is missing and remains open.
- **LOW — residual.** 61-01 still lists candidate 4 (synchronous chunk loop) without labeling it the baseline; gpt's MEDIUM suggestion on this was not dispositioned. The spike's verdict arithmetic will in practice disqualify it; flagging for completeness.
- **LOW — residual.** kimi's unverifiable baseline figures (plugin "1725 / 5", root "3365 / 154") persist in every verification block; only the root 3365 is corroborated by `.planning/STATE.md:11`. Harmless, but the verification blocks assert them as known.
- No revision-introduced HIGH/MEDIUM findings were identified. All new cited symbols I checked (see below) verified, except the two created-by-plan symbols (`outcome_contract_version`, `hold_code`), which are clean-slate names with no collision risk.

## Suggestions

- Fold 61-05's absent/parseable/anomalous classification into `held_queue`'s read path too, so the review queue and the manifest share one corrupt-vs-absent rule (closes the MEDIUM residual above).
- In 61-01 Task 1, mark candidate 4 as "baseline, not eligible" in the doc template so the verdict text can't accidentally promote it.
- In 61-02, note the bounded variant-set size (~9 filter groups) in the node comment so the operator can audit the promise the plan makes.

## Risk assessment — **MEDIUM**

Cycle 1 split HIGH (gpt) / MEDIUM (kimi) / LOW-MEDIUM (gemini). This revision genuinely resolves the HIGH items (signal transport, schema, run-scope, `covers()` gap, route decision, checkpoint bounds, EQ variant set, closed cardinality, native property). The remaining open items are one MEDIUM residual (61-04 queue degrade semantics) and two LOWs. Downgraded to MEDIUM; risk drops to LOW when the 61-04 queue-read rule is unified with the manifest's.

---

## Source-grounding verification

Symbols are graded against actual repo reads, not plan text. Cycle-1's orchestrator table (U1-U5 uncheckables excluded from verified set) was also re-checked where the revision touched it.

- `covers()` — **VERIFIED** (`operator-claude-plugin/scripts/write_grant.py:596-642`; outside-ids/`outside_domains` refusal at :629-640 carrying the "GRANT-03" wording — 61-06 REVIEW-11 premise holds by source).
- `plan_grant()` — **VERIFIED** (`write_grant.py:411`; lanes parameter with unknown-lane refusal and empty-record-set refusal — the "machinery exists" partial-rejection of REVIEW-11 is also true).
- `authorize_send()` / `authorize_ungranted_send()` — **VERIFIED** (`write_grant.py:729` / `:792`).
- `written_records_path(run_id)` — **VERIFIED** (`operator-claude-plugin/scripts/written_records.py:118`; docstring at :31 describes the per-run id pattern — 61-04's precedent claim holds).
- `outcome_contract_version` — **NEW-BY-PLAN, NO COLLISION** (zero repo matches across `*.py`/`*.js`/`*.md`; created by 61-04 Task 1).
- `hold_code` — **NEW-BY-PLAN, NO COLLISION** (zero repo matches; created by 61-04 Task 3).
- Portal snapshot `config/hubspot_migration/baseline/portal-schema-contacts-54-03-contacts-check.json` — **VERIFIED** (`lv_linkedin_url` present, `hs_linkedin_url` present, bare `linkedin_url` absent; walk-based scan over the JSON confirms 430 property names).
- `laneOf()` shape — **VERIFIED** (`n8n/code/matchProposal.js:30-42`: fetch_by_id→email→name→none; nothing reads `linkedin_url`; `trimmedOrValue` at :26).
- `summarizeMatch()` arm — **VERIFIED** (`matchProposal.js:119-146`: fetch_by_id/email arm at :128-133 joined as 61-02 proposes).
- `resolveCompanyLink` / `company_hold_reason` — **VERIFIED** (`n8n/code/companyLink.js:124`, markers at :134/:140/:145/:158).
- `resolveIdentity.js` linkedin branch + `canonicalizeLinkedin` — **VERIFIED** (`n8n/code/resolveIdentity.js:17`, branch :76-90).
- `Build Response` spread — **VERIFIED** (`build_cloud_workflows.py:4397-4408`, `return $input.all().map((item) => ({ json: { ...item.json, remaining_credits } }))` — 61-04's "transport exists" premise is literally true).
- `judge_confidence_by_field` — **VERIFIED** (`build_cloud_workflows.py:1346/:1349`, plus :2322/:2485).
- `main()` writes 8 JSONs — **VERIFIED** (`build_cloud_workflows.py:7731-7765`).
- `ADAPT_SEARCH_RESULTS` email-only — **VERIFIED** (`build_cloud_workflows.py:245-252`; only `srk.email` populated).
- `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV` includes `lv_linkedin_url` — **VERIFIED** (`build_cloud_workflows.py:4459`).
- `test_column_mapping_shipped.py:35` — **VERIFIED** (permanent byte-equality assertion exists).
- `MATCH_LOOKUP_KEYS` frozen tuple — **VERIFIED** (`enrichment.py:71` = `("email","firstname","lastname","company")`; boundary comment :66-70).
- `extraction.md` no-invention vs identity sentences — **VERIFIED** (items 1-2 at :22-26; identity sentence at :27-29; a RECORDED EDIT block at :31-49 separates the D-59-08 resolution loop; the sentences are independently editable as 61-03 claims).
- `test_extraction_contract.py` pinned assertion — **VERIFIED** (verbatim string at :237 within the plan's cited :233-241 range).
- `src/identity.py:65` bare `linkedin_url` filter + `_SEARCH_PROPS:16` — **VERIFIED**.
- `scoreEnrichment.js agreedBy` — **VERIFIED** (`n8n/code/scoreEnrichment.js:76-96`).
- `providerConflict.js` exports — **VERIFIED** (`n8n/code/providerConflict.js:58`: `detectConflicts, groupConflicts`).
- `run_manifest.ALLOWED_VERDICTS` five words — **VERIFIED** (`run_manifest.py:76`).
- `load()` degrade-whole-to-{} — **VERIFIED** (`run_manifest.py:156-185`).
- `rows_to_resume` held branch email-gated — **VERIFIED** (`run_manifest.py:228-232`).
- `_FORBIDDEN_NAME_MARKERS` — **VERIFIED** (`run_manifest.py:86-100`).
- `durable_paths._atomic_write_0600` / `resolve_state_path` — **VERIFIED** (`:57` / `:234`).
- `DispatchOutcome.run_id` — **VERIFIED** (`chunking.py:110` field :151; minted :336-337).
- `failed_batch` — **VERIFIED** (`chunking.py:420`).
- `_POLL_LOOP_ALLOWED = {"watch.py"}` — **VERIFIED** (`test_report_sufficiency.py:193`).
- `plugin.json` version 0.28.6 — **VERIFIED** (`:4`).
- 61-02/61-03/61-05/61-06 test-file references — all present on disk (`companyNameFallbackFlow`, `bareEventChainFlow`, `companyAssociationFlow`, `contactCreateGateFlow`, `columnMapAliasParity`, `matchProposal`, `mergeContacts`; `test_e2e_ingest.py`, `test_identity.py`, `test_rows_envelope_contract.py`, `test_enrichment_envelope.py`, `watch.py`, `executions_client.py`, `54-MEASUREMENT.md`).
- Same-value PATCH no-op (61-05 Task 3) — **VERIFIED-as-documented** (`.planning/WINDOWS.md` records "same-value PATCH fires no HubSpot property-change event" as accepted project fact; graded VERIFIED, not UNCHECKABLE, since the plan cites it as a documented behavior from repo docs, which is precisely what it is).
- `outcome_contract_version` / `hold_code` — covered above (no collision; created by plan).

All other symbols the plans cite trace to real files at the cited lines or adjacent lines, with the corrections the revision itself names (A1/A2/A3 fix-ups applied). No **MISSING** verdicts; no **AMBIGUOUS** verdicts among the new citations.

---

## OpenCode Review (gemini-3-6-flash)

# Cross-AI Plan Review — Phase 61, CONVERGENCE CYCLE 2

**Reviewer:** opencode (google/gemini-3.6-flash)  
**Session Date:** 2026-08-30  
**Repository Working Dir:** `/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc`  
**Target Phase:** Phase 61 (Autonomous batch runs) — Cycle 2 Plan Re-Review  
**Revised Plans Reviewed:** `61-01-PLAN.md` through `61-06-PLAN.md` (commit `8aa942b`)  

---

### Source-grounding verification

| Symbol / Claim | Location / Citation in Codebase | Verdict | Notes |
| :--- | :--- | :--- | :--- |
| `covers(grant, *, lane=None, workflow_id, record_ids, record_domains)` | `operator-claude-plugin/scripts/write_grant.py:596` | **VERIFIED** | Real function definition with keyword-only arguments. |
| `written_records_path(run_id)` | `operator-claude-plugin/scripts/written_records.py:118` | **VERIFIED** | Real helper returning `written_records-<run_id>.json`. |
| `outcome_contract_version` | N/A (New proposed contract field) | **UNCHECKABLE / PROPOSED** | New contract field to be stamped by `scripts/build_cloud_workflows.py` in Task 1 of 61-04. |
| `hold_code` fingerprints / `held_queue.py` | N/A (New proposed artifact) | **UNCHECKABLE / PROPOSED** | New persistent queue module to be created in Task 3 of 61-04. |
| `canonicalizeLinkedin` / `canonicalize_linkedin` | `n8n/code/resolveIdentity.js:16-41` & `src/identity.py:19-31` | **VERIFIED** | Real LinkedIn canonicalization functions present in both JS and Python. |
| `lv_linkedin_url` (contacts schema) | `config/hubspot_migration/baseline/portal-schema-contacts-54-03-contacts-check.json` | **VERIFIED** | Verified as the live custom contact property; no bare `linkedin_url` exists. |
| `MATCH_LOOKUP_KEYS` | `operator-claude-plugin/scripts/enrichment.py:66` | **VERIFIED** | Tuple `("email", "firstname", "lastname", "company")` verified present. |
| `resolveCompanyLink` | `n8n/code/companyLink.js:131-172` | **VERIFIED** | Real company link resolution function. |
| `_POLL_LOOP_ALLOWED` | `operator-claude-plugin/tests/test_report_sufficiency.py:193` | **VERIFIED** | Set `{"watch.py"}` verified in the test file. |

---

## 1. Summary

- **61-01-PLAN.md**: A thorough, offline-first decision spike for n8n Cloud's execution model and state storage. Incorporates Cycle 1's feedback by requiring machine-readable premises with explicit dependent plan/task IDs, an `## Unresolved` section that must be presented to the operator by name, and an exact definition of "claim line" in the doc test.
- **61-02-PLAN.md**: The backend half of the LinkedIn tracer. Addresses Cycle 1 findings by searching both `lv_linkedin_url` and native `hs_linkedin_url` (deduplicating by contact ID), defining explicit multi-hit cardinality (routing >1 verified hit to `medium` candidates), and replacing fuzzy URL matching with an exact EQ search across an explicit, test-pinned set of normalized URL variants.
- **61-03-PLAN.md**: The front-end contract update. Fixes the identity pre-flight across all sites simultaneously, derives the refusal message from `identity_groups()`, pins the YAML-to-JS parity check in tests, and explicitly updates `test_extraction_contract.py:233-241` where the refusal sentence was verbatim-pinned.
- **61-04-PLAN.md**: Confidence assessment and held queue. Substantially improved from Cycle 1 by introducing a version-stamped per-row outcome projection (`outcome_contract_version`) on the n8n response, constructing `held_queue.py` as a durable local store with signal fingerprints and `hold_code`s, and adding a 6th verdict word to `run_manifest.py` to prevent re-spending credits on resume.
- **61-05-PLAN.md**: Async submit, progress, and resume. Properly gated on 61-01 premises via Task 1. Resolves Cycle 1 resume ambiguity by keeping whole-degrade for the resume engine while forcing the report engine to classify and report corrupted/mismatched state out loud rather than silently presenting it as a fresh run.
- **61-06-PLAN.md**: Unattended pair pipeline. Closes the same-run association gap by passing newly created company IDs forward by value (eliminating index-lag polling), updates `write_grant.py::covers()` in code so that records created *under* an open grant are authorized for subsequent operations within the same run, and routes n8n-generated held outcomes into the local `held_queue.py`.

---

## 2. Strengths

- **Rigorous Cycle 1 Disposition Tracking**: Every plan features a clear `<review_dispositions>` section mapping Cycle 1 concerns directly to executable tasks or justified rejections.
- **Data-Driven & Grounded Decisions**: Key schema choices (such as filtering on `lv_linkedin_url` and `hs_linkedin_url` while excluding bare `linkedin_url`) are backed by real portal schema snapshots rather than guesses.
- **Elimination of Duplicated Logics**: 61-03 derives error strings dynamically from `identity_groups()`, deleting a hardcoded text drift site; 61-06 routes contact creates through the ingest lane to preserve a single, authoritative association implementation.
- **By-Value Propagation over Polling**: 61-06 replaces search-index lag polling with direct by-value ID propagation for same-run company creations, eliminating unnecessary latency and race conditions.
- **Strict Safety Boundaries Maintained**: Non-clobber merge policies, write-safety gate nodes, per-send armed windows, and Phase 57 readiness gates remain fully enforced across all plans.

---

## 3. Concerns (Residuals & New)

*All Cycle 1 findings have been resolved or properly justified. The following are low-risk residual/new findings.*

- **61-02-PLAN.md — [LOW - new]**: *Variant Set Bound vs Future Custom URL Formats.* In Task 2, `HubSpot Linkedin Search` uses EQ over an enumerated set of URL variants. While safe against false positives, if an operator enters a LinkedIn URL format not in the variant set (e.g. mobile `m.linkedin.com`), it will register as tier `none`.
  *Severity:* **LOW** | *Tag:* `new`
- **61-04-PLAN.md & 61-06-PLAN.md — [LOW - new]**: *Fingerprint Invalidation Scope in Held Queue.* In 61-04 Task 3, "resume once the holding signal changes" compares signal fingerprints. If a fingerprint check is overly sensitive to non-material metadata changes in the n8n response, it could trigger an unnecessary re-evaluation.
  *Severity:* **LOW** | *Tag:* `new`
- **61-05-PLAN.md — [MEDIUM - residual]**: *Manual Verification Checkpoint Scope.* Task 4 includes a live test execution of an async run before Phase 57 controls are in place. Although Task 4 constrains this run to return-only/test records with 0 creates and empty provider calls, care must be taken during execution to strictly enforce these flags.
  *Severity:* **MEDIUM** | *Tag:* `residual`

---

## 4. Suggestions

- **61-02-PLAN.md**: Document the exact list of supported LinkedIn URL variants in `n8n/code/resolveIdentity.js` and `scripts/build_cloud_workflows.py` so future operators know which formats are guaranteed to match.
- **61-04-PLAN.md**: In `held_queue.py`, ensure the signal fingerprint excludes volatile fields (such as timestamps or temporary execution IDs) and only hashes core match/conflict/adjudication signals.
- **61-05-PLAN.md**: Ensure Task 4's manual test run uses an explicitly constructed test-record payload with `allow_create: false` and `providers: []` hardcoded in the test script invocation.

---

## 5. Risk Assessment

**Overall Risk Level: LOW**

**Justification:**  
The revised plans present a tightly integrated, source-grounded architecture. The critical architectural gaps from Cycle 1 (such as client/cloud transport of confidence signals, same-run grant authorization for created records, and corrupted manifest report ambiguity) have all been resolved with explicit code edits, TDD tests, and strict invariants. Safety gates and disarmed defaults are preserved throughout.

---

## 6. Source-grounding verification

*(Repeated from top for section completeness)*

- `write_grant.py::covers()`: **VERIFIED** (`operator-claude-plugin/scripts/write_grant.py:596`)
- `written_records.py::written_records_path()`: **VERIFIED** (`operator-claude-plugin/scripts/written_records.py:118`)
- `canonicalizeLinkedin` / `canonicalize_linkedin`: **VERIFIED** (`n8n/code/resolveIdentity.js:16` & `src/identity.py:19`)
- `lv_linkedin_url`: **VERIFIED** (`config/hubspot_migration/baseline/portal-schema-contacts-54-03-contacts-check.json`)
- `MATCH_LOOKUP_KEYS`: **VERIFIED** (`operator-claude-plugin/scripts/enrichment.py:66`)
- `resolveCompanyLink`: **VERIFIED** (`n8n/code/companyLink.js:131`)
- `_POLL_LOOP_ALLOWED`: **VERIFIED** (`operator-claude-plugin/tests/test_report_sufficiency.py:193`)
- Proposed symbols (`outcome_contract_version`, `held_queue.py`, `hold_code`): **UNCHECKABLE / PROPOSED** (Correctly listed as new deliverables to be created during implementation).

---

## Consensus Summary

All three reviewers had repo access and produced source-grounded reviews (no
`[reviewed-without-repo-access]` markers). All three share the opencode adapter, so agreement is
cross-model, not cross-tool. gpt-5-6-sol again used a CRITICAL tier above HIGH; for counting,
CRITICAL is treated as HIGH-severity. Where reviewer severity conflicted with source, the
orchestrator's adjudication (authority = grep) is recorded below and reflected in the counts.

**The three verdicts diverge sharply this cycle**: gpt-5-6-sol rates 61-05/61-06 HIGH-risk and
raises two CRITICALs plus eight HIGHs; kimi-k3 finds one MEDIUM residual and no new
HIGH/MEDIUM at all (risk MEDIUM, trending LOW); gemini-3-6-flash finds one MEDIUM residual and
two LOWs (risk LOW). All three agree the revision genuinely resolved the cycle-1 core: signal
transport (61-04 Task 1), the EQ-variant-set search, both-LinkedIn-properties coverage, closed
cardinality, per-run manifest scoping, the `covers()` created-record gap, the association route
decision, and by-value company-ID propagation.

### Agreed Strengths (2+ reviewers)
- Every plan's `<review_dispositions>` section maps cycle-1 findings to executable tasks or
  reasoned rejections; the rejections check out against source (all three).
- The versioned per-row outcome projection over the existing `Build Response` spread
  (verified `build_cloud_workflows.py:4397-4408`) is the right-sized fix for the cycle-1
  transport CRITICAL — a named projection, not a new envelope (gpt, kimi).
- EQ-over-enumerated-variants with `CONTAINS_TOKEN` recorded `[unknown]`+probe fails in the
  safe direction — a miss, never a wrong person (gpt, kimi, gemini).
- By-value propagation of created company ids replaces index-lag polling; lag machinery
  shrinks to the single evidence-backed residual case (all three).
- `covers()`'s grant-time id snapshot (write_grant.py:596-642) is confirmed the real gap, and
  Task 3's four pinned admission constraints (T-61-24) register the threat rather than trusting
  prose (gpt, kimi).
- The two-consumers/two-rules resolution of the resume conflict matches `run_manifest.load()`'s
  actual semantics (run_manifest.py:156-185) (kimi, gemini; gpt objects to the naming only).

### Orchestrator adjudication of gpt-5-6-sol's HIGH/CRITICAL findings (authority = grep)

gpt-5-6-sol was the only reviewer to rate anything above MEDIUM this cycle. Each of its ten
HIGH+ findings was checked against source; none survives at HIGH:

1. **61-05 CRITICAL "run_id is not an immediate submission handle" — DOWNGRADED to LOW.**
   `dispatch_plan` accepts `run_id` as a caller-suppliable keyword argument
   (chunking.py:315; minted at :336-337 only when omitted). The handle IS client-minted and
   can exist before submit — gpt's own remedy ("mint before submission") is what the existing
   kwarg supports. The plan's claim ("the handle exists and does not need inventing") is
   accurate; Task 2 builds the new submit path on the substrate 61-01 selects. Actionable
   remainder: one sentence stating run_id is minted before submit.
2. **61-05 CRITICAL "local stores cannot serve detached execution" — NOT COUNTED.** This
   re-litigates the substrate question the revision deliberately gates: Task 1's halt gate
   reads 61-01's dependents column mechanically, `run_state.py`'s shape "follows the substrate
   decision", and the held-queue's client-side location was adjudicated by elimination in
   cycle 1 (61-04's disposition: a never-landed row has no HubSpot record; staticData has no
   client read endpoint). A substrate verdict contradicting a 61-05 premise halts the plan —
   that is the mechanism the disposition installed, and it addresses the concern.
3. **61-02 HIGH "join to the fetch_by_id/email arm cannot express medium+candidates" —
   DOWNGRADED to MEDIUM, actionable.** The contradiction is real as instruction text: the
   existing arm is two-outcome (matchProposal.js:128-133) while the `<behavior>` block demands
   0→none / 1→high / >1→medium+candidates. But `<behavior>` is the acceptance surface and its
   cardinality cases are explicitly test-pinned, so a two-outcome implementation cannot pass
   the plan's own verify; the action's wording needs one fix, not the design.
4. **61-02 HIGH "variant cross-product may exceed HubSpot's filter-group limit" —
   DOWNGRADED to MEDIUM, actionable.** Legitimate and the sharpest new find this cycle
   (~9-12 EQ groups across two properties; kimi independently counted ~9 without flagging the
   limit). The limit itself is unverifiable offline (the repo's operator-vocabulary comment at
   build_cloud_workflows.py:4838 is itself `[ASSUMED]`), the failure mode is a LOUD live 400
   (not a silent miss or a wrong write), and the closed vocabulary the plan already mandates
   includes `IN` — two filter groups total, one per property. A one-line plan amendment closes
   it; it does not warrant a HIGH on a lane whose writes remain gated.
5. **61-04 HIGH "confidence table has no provider-agreement rows" — DOWNGRADED to MEDIUM,
   actionable.** True: `agreedBy` is named as one of three inputs but no `<behavior>` row
   consumes it, and first-match-wins row 1 (high tier + no material conflict → confident)
   bypasses agreement entirely. The terminal `else → held` bounds drift, and the executor is
   told to write the full table; the plan should still state agreement's role explicitly.
6. **61-04 HIGH "fingerprint-resume join undefined" — DOWNGRADED to MEDIUM, actionable.**
   The semantics are specified (fingerprint inequality; missing fingerprint = changed) but the
   API seam is not: `rows_to_resume(rows, manifest)` (run_manifest.py:207-210) takes no queue
   input and 61-05 forbids a second resume rule. Name the join point.
7. **61-04 HIGH "ambiguity cardinality missing from the projection" — DOWNGRADED to MEDIUM,
   actionable.** The decision table's medium-row needs candidate count; Task 1's four named
   signals don't include it. The row spread likely carries candidates anyway (and
   `preingest.classify_matches` already derives ambiguity client-side, preingest.py:304-320),
   but a named projection should name it.
8. **61-05 HIGH "fail-loudly wording vs full-rerun-with-disclosure" — DOWNGRADED to LOW.**
   The action resolves REVIEW-08 precisely (two consumers, two rules; the report path SAYS
   which of absent/parseable/anomalous/another-run's it saw); one `<behavior>` bullet still
   carries the old "fails loudly" phrasing. Wording alignment only.
9. **61-05 HIGH "per-chunk verdict writes vs save()'s whole-document semantics" — DOWNGRADED
   to MEDIUM, actionable.** `run_manifest.save()` does write the supplied map as the complete
   document (run_manifest.py:117-153), so "write verdicts per chunk" needs read-merge-write
   stated — a crash between load and save is the window to reason about. Natural
   implementations do this; the plan should say it.
10. **61-06 HIGH triplet (created-id adapter unnamed; covers() admission provenance;
    written_records report scope) — DOWNGRADED to MEDIUM/LOW, actionable.** The created-id
    join is implementable lane-side (the create node's HTTP response carries the id inside the
    workflow; `Build Association Request` already joins responses by value) and
    `scripts/build_cloud_workflows.py` is in Task 2's files — but the plan should
    acknowledge that the CLIENT-visible response contract currently discards create ids
    (written_records.py:38-48 documents `created_id_unknown`; the post-write confirmation
    node was scoped OUT in 59-01) and name where "durable create evidence" comes from. The
    admission-provenance constraint is already stated in T-61-24 ("only ids returned by writes
    THIS grant authorized"); the API shape is executor detail. The end-of-run account should
    be required to load `written_records_path(run_id)` — `written_records.load()` without a
    path aggregates historical runs (written_records.py:291-323).

### Agreed / counted residual concerns (deduplicated, post-adjudication)

No finding stands at HIGH after adjudication. The actionable set (MEDIUM/LOW, not yet
incorporated into plan text):

| # | Plan | Concern | Raised by |
|---|---|---|---|
| C1 | 61-01 | Checkpoint option texts assert facts (restart survival, billing) the spike may leave `[unknown]` — basis-token them or generate from the verdict | gpt (M residual) |
| C2 | 61-01 | "The spike's six questions" has no stable enumerated set — assign Q-01..Q-06 IDs and assert them in the doc test | gpt (M new) |
| C3 | 61-01 | Candidate 4 (synchronous loop) not labeled baseline-not-eligible | kimi (L residual) |
| C4 | 61-02 | Reword Task 2's "join to the fetch_by_id/email arm" so the linkedin arm consumes candidate cardinality (adjudication #3) | gpt |
| C5 | 61-02 | Bound the search's filter-group count vs HubSpot's (offline-unverifiable) limit — prefer one `IN` group per property from the documented closed vocabulary, or record the limit `[unknown]`+probe (adjudication #4) | gpt; kimi counted ~9 groups |
| C6 | 61-02 | `src/identity.py` will search `lv_linkedin_url` only while the lane searches both properties — search both, or declare the oracle non-parity for native-only records | gpt (M new) |
| C7 | 61-03 | Add `test_extraction_contract.py` to Task 2's `<files>` (present in plan-level files_modified only) | gpt (L new) |
| C8 | 61-04 | State `agreedBy`'s role in the decision table (adjudication #5) | gpt |
| C9 | 61-04 | Add candidate count to Task 1's named projection (adjudication #7) | gpt |
| C10 | 61-04 | Name the fingerprint/manifest resume join point (adjudication #6) | gpt |
| C11 | 61-04 | Held-queue read path keeps blanket degrade-to-empty (61-04-PLAN.md:268-269) while the manifest gained absent/parseable/anomalous/another-run's classification — the cycle-1 HIGH at 61-REVIEWS(b331163):172 has NO disposition entry. Mitigants: manifest `held` verdicts survive a corrupt queue, and no-fingerprint = re-run not strand — so rows re-run rather than vanish, which is why this counts MEDIUM not HIGH. Give the queue the same classify-and-disclose rule | kimi (M residual, un-dispositioned) |
| C12 | 61-04 | Fingerprint hashes core signals only — exclude volatile fields (timestamps, execution ids) | gemini (L new) |
| C13 | 61-05 | State that per-chunk verdict persistence is read-merge-write over the accumulated document (adjudication #9) | gpt |
| C14 | 61-05 | State that run_id is minted before submit and passed in (adjudication #1) | gpt (L) |
| C15 | 61-05 | Align the "fails loudly" `<behavior>` bullet with the rerun-with-disclosure resolution (adjudication #8) | gpt (L) |
| C16 | 61-06 | Require the end-of-run account to load `written_records_path(run_id)` (adjudication #10) | gpt |
| C17 | 61-06 | Name the created-id capture point for client-visible "durable create evidence" (adjudication #10) | gpt |

### Divergent Views
- **Overall risk:** gpt HIGH (61-05/61-06) vs kimi MEDIUM-trending-LOW vs gemini LOW. The split
  is the same architectural fault line as cycle 1 — gpt treats specification seams an executor
  must resolve as blocking; kimi and gemini treat the plans' behavior-block + pinned-test
  discipline as the binding surface. The orchestrator's adjudication sides with the latter
  where the plan's own tests would catch the failure (C4) and with gpt where nothing would
  (C5, C11).
- **kimi's "no revision-introduced HIGH/MEDIUM"** missed the C4 contradiction (it read the
  same matchProposal.js lines and called the join "as 61-02 proposes") and the C5 group-count
  risk it itself measured (~9 groups). Cross-model review earning its keep in both directions.
- **gemini's MEDIUM residual on 61-05 Task 4** (live-checkpoint execution discipline) is not
  counted: the five bounds it asks to be careful about are already explicit plan text; its
  hardcode suggestion is folded into C-list-adjacent suggestions, not a required amendment.

---

## Verification coverage (orchestrator source-grounding pass, cycle 2, authority = grep)

New symbols cited by the revision, resolved against the repo with grep/Read. Verdicts from the
two reviewers' own grounding passes agreed with these on every overlapping symbol.

| Symbol (revision citation) | Verdict | Evidence |
|---|---|---|
| `write_grant.covers()` refuses ids absent from the grant at grant time (61-06 Task 3) | VERIFIED | write_grant.py:596 (def), :629-640 outside_ids/outside_domains refusal with GRANT-03 wording |
| `written_records.written_records_path(run_id)` as per-run path precedent (61-04 Task 3) | VERIFIED | written_records.py:118; docstring :31 |
| `plan_grant(lanes=[...])` (61-06 disposition) | VERIFIED | write_grant.py:411 |
| `_consequence()` two-lane text (61-06 disposition) | VERIFIED | write_grant.py:348 |
| `authorize_send` (61-06 disposition) | VERIFIED | write_grant.py:729 |
| `company_hold_reason` vocabulary reused for returned holds (61-06 Task 1) | VERIFIED | n8n/code/companyLink.js:134,140,145,158 |
| `outcome_contract_version` (61-04 Task 1) | PROPOSED — plan-introduced; zero occurrences in source (absence verified), no collision | rg over *.py/*.js/*.mjs |
| `hold_code` closed set + signal fingerprint (61-04 Task 3) | PROPOSED — plan-introduced; zero occurrences in source, no collision | rg over *.py/*.js/*.mjs |
| `load(expected_run_id=...)` (61-04 Task 3) | PROPOSED — current signature is `load(path=None)` | run_manifest.py:156 |
| `_SEARCH_PROPS` requests bare `linkedin_url` (61-02 Task 2, REVIEW-A2 fix) | VERIFIED | src/identity.py:16 |
| `test_column_mapping_shipped.py:35` byte-identity assert (61-03 disposition) | VERIFIED | assert PLUGIN_COPY.read_bytes() == REPO_COPY.read_bytes() at :35 |
| Closed HubSpot operator vocabulary includes `IN` (basis for C5's remedy) | VERIFIED | build_cloud_workflows.py:4838-4845 comment (itself `[ASSUMED]` offline) |
| `dispatch_plan(..., *, run_id=None)` caller-suppliable (basis for adjudication #1) | VERIFIED | chunking.py:315; minted :336-337 only when omitted |
| `summarizeMatch` strong-key arm is two-outcome (basis for adjudication #3) | VERIFIED | matchProposal.js:128-133 |
| `created_id_unknown` — company create response carries no id client-side (basis for adjudication #10) | VERIFIED | written_records.py:38-48 |
| `run_manifest.save()` writes supplied map as complete document (basis for adjudication #9) | VERIFIED | run_manifest.py:117-153 |
| 61-04 queue degrade-to-empty behavior line (C11) | VERIFIED | 61-04-PLAN.md:268-269 |

Reviewer-reported verdicts not independently re-run were spot-checked where load-bearing; no
reviewer VERIFIED verdict was contradicted. gpt's AMBIGUOUS (HubSpot filter-group limit) and
both reviewers' UNCHECKABLE set (n8n restart survival, concurrency caps, billing, URL
tokenization, index-lag magnitude) match cycle 1's U1-U5 — all remain routed to `[unknown]`
+probe in the plans, which is the correct offline treatment.

### Reviewer-lane status

Sequential invocation through the opencode adapter. gpt-5-6-sol: exit 0, ~2.7 min, full review.
gemini-3-6-flash: exit 0, ~1 min, full review. kimi-k3: first attempt exited 0 after ~11 min
but returned only progress narration with no review body (treated as an empty-output lane,
#2605); a single re-run completed in ~4 min with a full review, which is the version included
above. 3 of 3 lanes ultimately produced source-grounded reviews.
