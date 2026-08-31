---
phase: 57
reviewers: [gpt-5-6-sol, kimi-k3, gemini-3-6-flash]
reviewed_at: 2026-08-31T12:30:00+10:00
plans_reviewed:
  - 57-01-PLAN.md
  - 57-02-PLAN.md
  - 57-03-PLAN.md
  - 57-04-PLAN.md
  - 57-05-PLAN.md
source_grounding: run (authority `grep`)
---

> Note: gpt-5-6-sol, kimi-k3 and gemini-3-6-flash all share the `opencode` adapter; their
> consensus is cross-model, not cross-tool.

> Requirements context: the reviewers were given `.planning/milestones/v1.1-REQUIREMENTS.md`,
> not the root `.planning/REQUIREMENTS.md`. RUN-05, AFTER-01, AFTER-03 and G-4 exist only in the
> v1.1 milestone file; the stock review workflow would have shipped the stale root file, in
> which none of the four appear.

# Cross-AI Plan Review — Phase 57

## Consensus Summary

Phase 57 gates the first live unattended, credit-spending batch (D-61-08), so the reviewers were
asked to weigh the plans as a safety proposition rather than as a feature set, and to judge the
deliberate overturn of operator ruling D-53-02 ("the ceiling is disclosure, not constraint") on
its merits.

**All reviewers agree the D-53-02 reversal is justified.** Disclosure-only was defensible while a
human supervised every send; it is not defensible for unattended spending. The evidence in
`57-CONTEXT.md` and `57-RESEARCH.md` supports the change, and the plans make it explicitly rather
than silently. `write_grant.py:150` (`_DISCLOSURE_NOT_CONSTRAINT`) is the live text being
replaced — verified.

**The reviewers split sharply on whether the plans are ready to execute.** gpt-5-6-sol returned
HIGH overall risk with two plans (57-03, 57-05) carrying findings it labelled CRITICAL, citing
`file:line` throughout. gemini-3-6-flash returned LOW overall risk and declared the plan set
"approved and ready for execution", but grounded far fewer of its claims and did not surface any
of the defects the orchestrator independently confirmed in source. Per the review contract,
`file:line`-grounded findings are weighted more heavily: consensus severity follows gpt-5-6-sol
plus the orchestrator's own verification, and gemini's LOW is recorded below as the divergent
view rather than as an offsetting vote.

### Agreed Strengths

- **The reversal is argued, not smuggled.** Both reviewers found the change explained in plan
  text and in the code comment that replaces `_DISCLOSURE_NOT_CONSTRAINT`.
- **`CEILING_UNKNOWN` does not refuse (D-57-02).** Both reviewers independently endorsed the
  choice that an unsampleable allowance proceeds with the blind spot named rather than blocking —
  a guard that always fires is indistinguishable from one that is off.
- **A budget stop is modelled separately from a chunk failure.** `DispatchOutcome` already keeps
  `written_records_failures` distinct from `failed_chunks` (`chunking.py:112-148`); a separate
  `ceiling_stop` field follows the established precedent, and Pitfall 5 pins that a stop never
  flips `ChunkResult.ok`.
- **The default-`None` `execution_ceiling` preserves every existing caller byte-identically.**
- **Provider-balance honesty.** Neither an unreadable balance nor an inconclusive probe is
  converted into zero or into headroom; `cost_guard.compare()` already returns `unknown` with
  `remaining_credits=None` (`cost_guard.py:288-293`).
- **No grant is persisted.** The remainder store carries work only, and the D-57-05 authority
  boundary is treated as hard.

### Agreed Concerns

**HIGH — the ceiling's sampling predicate makes the preflight guard unreachable at both ends of
the traffic range.** This is the strongest cross-reviewer finding: each reviewer saw one half,
and the orchestrator confirmed the shared mechanism in source. `n8n_read.executions_in_window`
sets `covers_full_window = saw_older_than_cutoff` (`n8n_read.py:378`) — that is "we paged back far
enough to see something older than the window", **not** "the sample is complete". Two
consequences:

- *Quiet instance* (gpt-5-6-sol, MEDIUM): the API listing can exhaust because there is no next
  cursor (`n8n_read.py:358-360`) without ever encountering an older execution, so
  `covers_full_window` stays False and `truncated_by_page_cap` stays False. The sample is in fact
  complete, yet `allowance_headroom` reports `sampled: False` and the verdict falls to
  `CEILING_UNKNOWN` — the preflight refusal never fires.
- *Busy instance* (gemini-3-6-flash, HIGH): `MAX_EXECUTION_PAGES = 4` x
  `EXECUTIONS_WINDOW_PAGE_LIMIT = 250` (`n8n_read.py:69,73`) caps the walk at 1,000 executions
  across **all** workflows on the instance. Near month-end on an active instance the cap is hit
  first, `truncated_by_page_cap` goes True, and the verdict again falls to `CEILING_UNKNOWN`.

Between the two, the band in which the preflight ceiling actually binds is narrow, and this
account's own execution history sits toward the quiet end. RUN-05's "refuses **before** start"
is the requirement most exposed by this.

**HIGH — the mid-run stop fires after the breaching chunk has already been sent.** `57-01-PLAN.md`
places the tally "immediately after the `append_chunk` guard block", which in `chunking.py` is
after `dispatch_enrichment` has run for that chunk (`chunking.py:376-427`). The plan's own `<done>`
says "stops after the breaching chunk", so the overshoot is disclosed — but disclosure of a
design that contradicts the phase goal ("a run cannot spend what it does not have") is not the
same as resolving it. gpt-5-6-sol recommends checking the *next* chunk's projected cost before
dispatch.

**HIGH — a real production dispatch path is deliberately left outside the ceiling.**
`preingest.rerequest_unanswered` (`preingest.py:662`) calls `dispatch_plan` internally, and
`57-01-PLAN.md:248` states `preingest.py:713` "needs no change at all and must not be edited",
with acceptance criterion `57-01-PLAN.md:293` asserting `grep -c "execution_ceiling"` reports 0
for that file. The `enrich-before-ingest` lane runs a match pass and an enrich pass under one
grant, so this is not a hypothetical path.

**HIGH — "written" is inferred, not proven.** The outcome vocabulary derives from decision-node
actions that precede the HubSpot HTTP write, and for an update `hs_object_id` is already known
before the PATCH. AFTER-03 asks that a record that would have been written never read as one that
was; `write_blocked -> gated` closes one direction, but a failed terminal write can still classify
as `written`. gpt-5-6-sol proposes `write_attempted` / `write_result_unknown` as honest
intermediates.

**HIGH — the `row_id` join key does not survive the pair pipeline.**
`operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:639` calls
`extraction.strip_row_id(sendable_rows)` before the final ingest dispatch, and `:643` documents
that this is deliberate. Adding `row_id` to the backend response cannot restore a value the
request never carried. AFTER-01's join is therefore incomplete on that lane.

**MEDIUM — no cross-store reconciliation policy.** 57-05 describes joining four durable stores;
counting `remainder_queue`, it is five, all independently written and all able to disagree after a
crash. No contradiction matrix is specified (ledger says `written` / manifest says `held`; a row
present in both the remainder queue and the written records; run state still `running` alongside
durable results).

**MEDIUM — factual error about the existing Apollo fixture.** Independently confirmed by the
orchestrator's grounding pass: `57-04-PLAN.md` describes Apollo's existing disclosure as
`unrecognized_response_shape` (lines 46-47, 168, 184), but
`operator-claude-plugin/tests/conftest.py:541` sets `error="http_403", status=403`, and the
string `unrecognized_response_shape` does not occur in `conftest.py` at all.

**MEDIUM — the phase has no requirement-coverage artifact.** `COVERAGE.md` is an *API* coverage
matrix (`COVERAGE.md:1`, "Phase 57 — API Coverage Matrix", rows are `INTEGRATE`/`OPT-OUT`
dispositions per API capability). Nothing in the phase directory maps RUN-05 / AFTER-01 /
AFTER-03 / G-4 to the plans that close them. Caught by the dropped `kimi-k3` lane's last
fragment; verified by the orchestrator. gemini-3-6-flash cited `COVERAGE.md` as evidence that the
four requirements are covered — it is not that document.

**MEDIUM — G-4 closure is conditional and undefined.** Apollo is structurally unreadable with the
current credential; ZoomInfo's outcome depends on a live probe that may return `provider_error` or
`inconclusive`. The phase does not state whether honest `unknown` disclosure counts as closure.

**MEDIUM — structural Markdown tests do not prove production reachability.** Several acceptance
criteria assert that a SKILL.md contains an identifier (`57-01-PLAN.md:404-405`). That passes when
the identifier appears in prose.

### Divergent Views

- **Overall risk.** gpt-5-6-sol: HIGH ("not safe to execute as written", 10 blocking revisions).
  gemini-3-6-flash: LOW ("approved and ready for execution", COVERAGE.md's claims hold). The
  disagreement is not about interpretation of a shared finding — gemini did not surface the
  post-send stop, the `rerequest_unanswered` bypass, the `strip_row_id` boundary, the
  `failed_batch` shape loss, or the Apollo fixture mislabel, each of which the orchestrator
  confirmed directly in source. Weighted per the review contract, the divergence resolves toward
  the grounded findings.
- **`chunking.failed_batch` shape coverage.** gpt-5-6-sol rates this CRITICAL: `plan_chunks`
  accepts `rows`, `people`, `companies` and `record_ids`, but `failed_batch`
  (`chunking.py:494-517`) merges only `rows` and `record_ids`, so a multi-chunk `people` or
  `companies` remainder can lose everything but the first chunk. No other reviewer examined
  `failed_batch`'s branches.
- **`REASON_ALLOWANCE_SPLIT` has no producer.** gpt-5-6-sol reports the preflight auto-split
  remainder is offered on the refusal but never actually queued. gemini treated the split as
  working and raised only a UX concern about the projection over-stating by ~3x.
- **Dependency ordering.** gpt-5-6-sol argues 57-05 must depend on 57-04 (both claim G-4) and that
  57-04 could move to wave 1. gemini accepted the wave structure as given.

---

## OpenCode Review (gpt-5-6-sol)

I’ll verify the five plans against the phase artifacts and current source, then report findings per plan with line-level evidence. I’m treating the D-53-02 reversal, crash/partial-run behavior, and production reachability as the primary safety gates.
# Phase 57 Plan Review

## Executive Summary

The plans are unusually thorough and correctly identify several real gaps: `record_send_outcome()` has no production caller, `written_records.classify_item()` discards `row_id`, the two reporting modules use divergent outcome vocabularies, and provider-balance failures need honest tri-state handling.

However, the phase is **not safe to execute as written**. Several issues directly undermine its core goal:

- The mid-run guard checks the ceiling **after** sending the chunk that breaches it.
- A real re-dispatch path, `preingest.rerequest_unanswered()`, bypasses the proposed ceiling accounting.
- `chunking.failed_batch()` cannot faithfully reconstruct multi-chunk `people` or `companies` remainders.
- The preflight auto-split remainder is offered but never actually queued.
- “Written” is still inferred from a pre-write action and an object ID, not proven from a successful HubSpot write.
- The final report joins five independently written stores, not four, without contradiction or crash-reconciliation rules.
- The reversal of D-53-02 is explained in the phase documents but is not propagated to canonical project decision records.
- Plan 57-05 does not depend on 57-04 even though both claim G-4 closure.

The D-53-02 reversal is justified: a disclosure-only ceiling was reasonable while a human supervised every send, but it is inadequate for unattended spending. The evidence in `57-CONTEXT.md` and `57-RESEARCH.md` supports a conservative binding constraint. The implementation and decision-record propagation need revision before that reversal is safely complete.

**Overall risk: HIGH**, with Plan 57-03 and Plan 57-05 carrying critical defects.

---

# Plan 57-01: Ceiling Refusal and Mid-Run Stop

## Summary

The plan selects the right broad architecture: preflight refusal in `write_grant.plan_grant()`, a separate budget-stop outcome in `chunking.dispatch_plan()`, and reuse of `record_send_outcome()` for grant closure. Its tri-state treatment of an incomplete execution sample is sound. The proposed mid-run enforcement is not yet sufficient, though: it sends the breaching chunk before checking, misses a production re-request path, cannot account for concurrent instance-wide execution consumption, and does not guarantee grant closure after unexpected exceptions.

## Strengths

- The preflight check is placed in the correct part of the grant flow. `plan_grant()` currently computes the envelope before guardrail preflight at `operator-claude-plugin/scripts/write_grant.py:411-435`, so a refusal inserted there can occur before arming or dispatch.
- The plan correctly recognizes that `record_send_outcome()` is only a consumer today. Its ceiling branch exists at `operator-claude-plugin/scripts/write_grant.py:899-949`, but there is no production call chain feeding it.
- Treating a deliberate budget stop separately from chunk failure is well designed. `DispatchOutcome` already separates written-record bookkeeping failures from ordinary failed chunks at `operator-claude-plugin/scripts/chunking.py:112-148`; a separate `ceiling_stop` follows that established pattern.
- The proposed `execution_ceiling=None` default preserves existing callers and current dispatch-envelope behavior at `operator-claude-plugin/scripts/chunking.py:317-383`.
- The plan correctly refuses to derive headroom from a truncated sample. `executions_in_window()` exposes `covers_full_window` and truncation information at `operator-claude-plugin/scripts/n8n_read.py:355-381`.
- The reversal of D-53-02 is explicitly explained in the plan and source-text task, rather than silently changing behavior.

## Concerns

- **HIGH: The stop occurs after spending beyond the ceiling.** The plan calculates the tally after dispatch and stops when `projected >= execution_ceiling`. The current send happens at `operator-claude-plugin/scripts/chunking.py:373-408`, before bookkeeping. With two-record chunks and five units remaining, the second chunk raises projected spend from three to six before the guard stops. That contradicts “cannot spend what it does not have.”
- **HIGH: `preingest.rerequest_unanswered()` bypasses the proposed ceiling.** It creates another plan and calls `dispatch_plan()` internally at `operator-claude-plugin/scripts/preingest.py:699-713`, then returns only a merge result at `operator-claude-plugin/scripts/preingest.py:722-741`. The runbook cannot pass a remaining ceiling into that dispatch or subtract its spend. This is especially important because the plan itself identifies repeated dispatches under one grant as a breach scenario.
- **HIGH: The point-in-time sample cannot enforce a global monthly ceiling.** `executions_in_window()` observes instance-wide executions at `operator-claude-plugin/scripts/n8n_read.py:258-266`, but the proposed mid-run guard only tracks local projected spend. Schedulers, another session, or another grant can consume the sampled headroom concurrently.
- **HIGH: Unexpected exceptions can leave the grant open.** `dispatch_plan()` catches selected dispatch exceptions at `operator-claude-plugin/scripts/chunking.py:376-402`, but an unexpected exception can escape before `record_dispatch_outcome()` is called. The runbook integration does not specify `try/except/finally` closure with `CLOSED_UNHANDLED_ERROR`.
- **MEDIUM: A fully exhausted API listing may still be treated as incomplete.** `executions_in_window()` can terminate because there is no next cursor at `operator-claude-plugin/scripts/n8n_read.py:358-360`, while `covers_full_window` may remain false unless an older execution was encountered. A quiet account could therefore produce `unknown` even though all executions were read.
- **MEDIUM: The new override weakens the safety promise.** An unrestricted `override=True` allows an operator-facing path to knowingly exceed the sampled monthly remainder. That may mirror `n8n_cadence`, but this phase gates unattended real spending. The authority and audit requirements for invoking that override are not defined.
- **MEDIUM: Markdown identifier tests do not prove production execution.** Checking that both skills contain `record_dispatch_outcome` and `execution_ceiling` can pass when identifiers appear only in prose or unreachable snippets.
- **MEDIUM: The plan describes the mid-run maximum overshoot as one chunk, but that ignores external concurrency.** One chunk is only the maximum local overshoot under a stable sampled allowance, not the maximum instance-wide overrun.

## Suggestions

- Check the next chunk’s projected cost **before** dispatch:
  - Compute `next_projected = attempted_chunks + 1 + sent_rows + next_rows`.
  - Stop when `next_projected > execution_ceiling`.
  - Permit equality if consuming the exact remaining allowance is valid.
- Add `execution_ceiling` and outcome/spend propagation to `preingest.rerequest_unanswered()`.
- Add an integration test covering the initial enrichment dispatch and the unanswered-row re-request under one grant.
- Define the guarantee honestly as a conservative point-in-time control unless a shared reservation or pre-send re-sampling mechanism is introduced.
- Add explicit `try/except/finally` runbook behavior:
  - Close with `ceiling_breach` for normal ceiling stops.
  - Close with `unhandled_error` for ordinary exceptions.
  - Preserve and report disarm failure separately.
- Extend `executions_in_window()` or its interpretation to distinguish API-pagination exhaustion from truncation.
- Either remove `override=True` from the unattended operator path or define who can use it, how it is confirmed, and how it appears in the final report.
- Move the grant-aware dispatch sequence into executable Python so tests exercise the production path rather than Markdown string presence.

## Risk Assessment

**HIGH.** The architecture is directionally correct, but the current design can exceed the local ceiling, misses a real production dispatch, and can leave a grant open after an exception.

---

# Plan 57-02: Outcome Vocabulary and Join Keys

## Summary

The plan correctly identifies and resolves the duplicated client outcome vocabulary, adds the missing `row_id`, preserves `created_id_unknown`, and fixes the ingest response projection boundary. Its central weakness is more fundamental: it still labels rows as `written` using a decision-stage action and an object ID, neither of which proves that the downstream HubSpot HTTP request succeeded. The proposed `row_id` propagation also does not survive the pair pipeline’s existing `strip_row_id()` boundary.

## Strengths

- The current vocabulary collapse is real. `written_records.classify_item()` produces only three outcomes at `operator-claude-plugin/scripts/written_records.py:161-182`.
- The second mapping has genuinely drifted. `report_enrichment._ACTION_TO_OUTCOME` is defined independently at `operator-claude-plugin/scripts/report_enrichment.py:31-50` and falls back through `_outcome_for_row()` at `operator-claude-plugin/scripts/report_enrichment.py:121-122`.
- `row_id` is available upstream but discarded:
  - Contact decision output: `scripts/build_cloud_workflows.py:1699-1707`
  - Company decision output: `scripts/build_cloud_workflows.py:3433-3441`
  - Current classifier entry: `operator-claude-plugin/scripts/written_records.py:161-182`
- `Build Ingest Response` is an explicit field projection and currently omits `row_id` at `scripts/build_cloud_workflows.py:494-518`; changing the builder and regenerating the workflow is correct.
- Preserving `created_id_unknown` respects the existing no-fabrication behavior at `operator-claude-plugin/scripts/written_records.py:166-174`.
- Reconciling the tenth action, `enrich`, is necessary. `WRITE_ACTIONS` already includes it at `operator-claude-plugin/scripts/written_records.py:93-96`.
- Keeping raw `action` while consolidating the higher-level outcome preserves useful detail.

## Concerns

- **CRITICAL: “Written” is not proven by the available evidence.** The actions originate in decision nodes before the HubSpot HTTP write. `scripts/build_cloud_workflows.py:3414-3419` converts an action to `write_blocked` when the safety gate rejects it, but an action that survives proves only that writing was permitted. For updates, `hs_object_id` is already known before PATCH, so an HTTP failure can still be classified as `written`.
- **HIGH: The pair pipeline strips `row_id` before final ingest dispatch.** `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:635-647` deliberately removes it. Adding `row_id: row.row_id ?? null` to the backend response does not restore a value absent from the request.
- **HIGH: Delegating `report_enrichment` directly to `classify_item()` imports persistence validation into a never-raise report path.** `classify_item()` raises for malformed input and forbidden markers at `operator-claude-plugin/scripts/written_records.py:100-115` and `:150-190`. `build_enrichment_report()` promises not to raise at `operator-claude-plugin/scripts/report_enrichment.py:285-304`.
- **MEDIUM: `written_id_unknown` only solves one side of the evidence problem.** It acknowledges uncertainty when an ID is absent, but a present ID still does not prove write success.
- **MEDIUM: The old-entry contract is inconsistent.** The plan says old entries read back with `row_id: None`, while the proposed test says they remain unchanged and callers use `.get()`. Current explicit-path loading returns entries unchanged at `operator-claude-plugin/scripts/written_records.py:291-308`.
- **MEDIUM: The ten-action test is circular.** Hard-coding the expected ten actions in the consumer test does not detect an eleventh action added to `scripts/build_cloud_workflows.py`.
- **LOW: The generated-workflow test is syntactic.** Checking that jsCode contains `row_id` does not prove it comes from the correct source or is non-null for held rows.

## Suggestions

- Do not use `written` unless a terminal write response proves success.
- If post-write confirmation remains out of scope, use an honest intermediate outcome such as `write_allowed`, `write_attempted`, or `write_result_unknown`.
- Separate the pure mapping from persistence:
  ```python
  outcome_for_action(action, hs_object_id=None, write_confirmed=None)
  ```
  Let both report modules use that pure function while `classify_item()` retains forbidden-value checks and durable-entry construction.
- Preserve a correlation ID through the pair pipeline as transport metadata, not as a HubSpot property and not in the stripped CSV payload.
- Add a test that extracts action literals from the workflow builder or generated workflows and compares them with the client mapping.
- Execute `BUILD_INGEST_RESPONSE` against representative held, update, create, and association inputs instead of only searching its source.
- Choose one legacy schema contract:
  - Normalize missing fields to explicit `None` on load, or
  - Document that old entries omit the keys.

## Risk Assessment

**HIGH.** The vocabulary unification is valuable, but the phase’s most important word, `written`, remains unsupported by terminal write evidence. The claimed join closure also fails on the current pair-pipeline boundary.

---

# Plan 57-03: Auto-Split and Remainder Queue

## Summary

The separation of work from authority is the right safety model, and a sibling durable store is preferable to forcing budget remainders into `held_queue`’s confidence schema. As written, though, this plan has multiple blocking defects: `failed_batch()` loses supported record shapes, the preflight split remainder is not actually queued, IDs and domains are not preserved correctly, and crash recovery only exists for deliberate ceiling stops.

## Strengths

- D-57-05 is correctly treated as a hard authorization boundary. The current grant module explicitly prohibits grant persistence at `operator-claude-plugin/scripts/write_grant.py:20-24`.
- A sibling remainder store is more appropriate than extending `held_queue`:
  - `held_queue` uses a closed hold-code vocabulary and a confidence-specific fingerprint.
  - The research correctly notes that never-dispatched rows lack those fields.
- Reusing `_atomic_write_0600` follows the established durable-write pattern at `operator-claude-plugin/scripts/durable_paths.py:57-81`.
- Per-run paths reduce cross-run collisions and follow `written_records`’ design at `operator-claude-plugin/scripts/written_records.py:14-27` and `:118-128`.
- The forbidden-marker scan provides useful defense against accidentally persisting a grant, token, permission, or secret.
- Returning no split when affordability is unknown avoids fabricating an answer.
- Keeping deliberate ceiling remainders separate from failed chunks is correct.

## Concerns

- **CRITICAL: `failed_batch()` cannot reconstruct all supported work shapes.** Planning accepts:
  - `rows` at `operator-claude-plugin/scripts/chunking.py:206-222`
  - `people` at `:224-239`
  - `companies` at `:241-259`
  - `record_ids` at `:261-277`

  But `failed_batch()` merges only `rows` and `record_ids` at `operator-claude-plugin/scripts/chunking.py:494-517`. Multi-chunk `people` or `companies` remainders can lose all but the first chunk.
- **CRITICAL: The advertised preflight auto-split remainder is never queued.** Task 3 attaches `split_offer` to the refusal and persists only a later mid-run `ceiling_stop`. `REASON_ALLOWANCE_SPLIT` has no producer.
- **HIGH: Persisting the split at refusal time would mutate durable state before acceptance.** `plan_grant()` is currently a planning surface at `operator-claude-plugin/scripts/write_grant.py:411-435`. The plan does not say whether queue persistence happens before or after the operator confirms the affordable subset.
- **HIGH: ID/domain semantics are not preserved.** Grant scope distinguishes record IDs and domains at `operator-claude-plugin/scripts/write_grant.py:607-620` and `:645-656`, while the proposed split returns `{record_ids, object_type}`. Domains authorize create candidates and cannot safely be converted to IDs or discarded.
- **HIGH: Crash-mid-run remainders are not durable.** Current per-chunk written-record evidence is persisted at `operator-claude-plugin/scripts/chunking.py:409-427`, but the new remainder is only written when the ceiling predicate fires. A process crash before the next chunk leaves no durable account of unsent work.
- **HIGH: The plan’s “whole batch completes over time” claim is inconsistent with fresh authorization per split.** D-57-05 says each subsequent run needs a fresh grant. Therefore the system can queue future work, but it cannot say the whole batch will complete automatically unless something later obtains authorization.
- **MEDIUM: Per-run files do not prevent same-run lost updates.** Read-append-rewrite with atomic replacement prevents partial files, but two writers sharing a `run_id` can overwrite each other.
- **MEDIUM: Persistence exception policy is unclear.** `_atomic_write_0600` can re-raise exceptions at `operator-claude-plugin/scripts/durable_paths.py:57-81`, while the plan only clearly degrades `OSError` and false returns.
- **MEDIUM: The plan says breach-held rows share a shape with confidence/no-company holds, but then deliberately stores them outside `held_queue`.** The reversibility rationale should be corrected to describe a sibling budget-remainder category, not a shared hold schema.

## Suggestions

- Generalize `chunking.failed_batch()` to preserve every supported shape, with tests for:
  - `record_ids`
  - `rows`
  - `people`
  - `companies`
- Split a canonical work specification rather than separate `record_ids` and `record_domains`.
- Make the state transition explicit:
  1. `plan_grant()` returns a pure split offer and writes nothing.
  2. Operator accepts the affordable subset.
  3. A fresh grant opens for that subset.
  4. Only then is the work-only remainder persisted.
- Add a test asserting an unconfirmed refusal creates no queue file.
- Either persist the initial plan/checkpoint the remaining chunks after every successful chunk, or explicitly state that crash recovery is outside the remainder guarantee.
- Guarantee one writer per `run_id`, or add locking/version checks around appends.
- Add recursive forbidden-value tests covering dictionaries, tuples, nested collections, and mixed values.
- Clarify that queued work does not imply scheduled or authorized completion.

## Risk Assessment

**CRITICAL.** The current remainder conversion can lose valid `people` and `companies` records, and the claimed preflight queue is not actually implemented. The split also fails to preserve ID/domain semantics.

---

# Plan 57-04: Provider Balance Blind Spots

## Summary

The plan correctly distinguishes structural Apollo authorization failure from the unresolved ZoomInfo runtime failure and wisely requires a live probe before changing ZoomInfo code. It does not yet demonstrate G-4 closure, however. The Apollo failure label is described incorrectly, the probe’s blast radius is understated, and static verification does not prove the opt-in gate prevents all network calls.

## Strengths

- The plan correctly avoids guessing at a ZoomInfo code fix. The required `Accept` header is already present at `scripts/build_cloud_workflows.py:4614-4630`.
- It correctly distinguishes:
  - HTTP/request failure: `http_<status>` or `provider_error`
  - Successful but unparseable response: `unrecognized_response_shape`
  
  The backend classification is at `scripts/build_cloud_workflows.py:6354-6361`.
- Apollo’s balance limitation is structurally outside this repository. `n8n/code/providerSelection.js:85-89` records the non-master-key 403 behavior.
- A dedicated exact-string environment gate and instance guard are appropriate for a live probe.
- The verdict avoids persisting provider tokens or raw response bodies.
- The plan appropriately accepts an inconclusive observation rather than fabricating a balance.

## Concerns

- **HIGH: G-4 is not clearly closed.** The phase context says G-4 is in scope as a fix, not just disclosure, but this plan explicitly makes no production change. `cost_guard.compare()` already represents unreadable balances as `unknown` with `remaining_credits=None` at `operator-claude-plugin/scripts/cost_guard.py:288-293`, so much of Task 2 only characterizes existing behavior.
- **HIGH: Apollo’s actual error is mislabeled.** The existing fixture carries `error="http_403"` and `status=403` at `operator-claude-plugin/tests/conftest.py:532-547`, not `unrecognized_response_shape`.
- **HIGH: The probe is not simply a read-only GET.** The client POSTs to the status endpoint through `operator-claude-plugin/scripts/backend_status.py:40-54`. The backend then probes providers; Apollo usage is itself configured as POST at `scripts/provider_registry.py:26-33`, and ZoomInfo may mint/cache a token at `scripts/build_cloud_workflows.py:4168-4184`.
- **HIGH: No test proves the unset gate causes zero network calls.** The planned AST/string check only proves the gate text exists, not that it executes before transport construction or requests.
- **MEDIUM: Zero provider-credit spend is asserted but not evidenced.** Usage endpoints are likely non-billable, but the plan should cite provider documentation or record an observed before/after balance where possible.
- **MEDIUM: `RUN_LIVE_PARITY` handling is ambiguous.** The plan references the root test guard but specifies only `ALLOW_ZOOMINFO_BALANCE_PROBE`.
- **MEDIUM: The plan’s success criteria allow an inconclusive result while still associating the plan with G-4 closure.** A probe artifact alone does not necessarily improve the blind spot.

## Suggestions

- Correct Apollo terminology everywhere to `http_403`, with the structural non-master-key explanation.
- Add unit tests around the probe entry point:
  - Gate missing: no transport construction or call.
  - Gate not exactly `"true"`: no call.
  - Wrong instance: no call.
  - Valid gate and instance: one status request.
- Document the complete network path, including status POST, provider usage calls, and possible ZoomInfo token mint.
- Define G-4 completion explicitly:
  - `readable`: ZoomInfo fixed by observation.
  - `provider_error`: unresolved but safely disclosed; G-4 remains partial unless the milestone accepts disclosure as closure.
  - `inconclusive`: not closed.
- Clarify whether `RUN_LIVE_PARITY` is required in addition to the dedicated probe flag.
- Record evidence for the claim that usage and token-mint calls do not consume enrichment credits.

## Risk Assessment

**MEDIUM-HIGH.** The plan is operationally cautious, but its error taxonomy and safety proof need correction, and it may claim G-4 closure without improving balance readability.

---

# Plan 57-05: End-of-Run Report

## Summary

The proposed report contains the right user-facing sections and treats missing evidence as a gap rather than silently omitting it. It cannot yet provide the promised proof. The source data does not confirm successful writes, there are five durable stores rather than four, existing loader APIs erase the distinction between missing and malformed artifacts, row correlation remains incomplete, and no reconciliation policy exists for contradictory crash-partial state.

## Strengths

- The report contents match AFTER-01:
  - Per-record outcome
  - Association outcome
  - Held rows and reasons
  - Spend against ceiling
  - Disarm verdict
- Per-run filtering is correctly treated as mandatory. Pathless `written_records.load()` aggregates all run files at `operator-claude-plugin/scripts/written_records.py:291-323`.
- The global held queue is correctly labeled as backlog rather than attributed to a specific run. `held_queue` is global at `operator-claude-plugin/scripts/held_queue.py:74-79`, and `run_state` intentionally excludes it at `operator-claude-plugin/scripts/run_state.py:107-112`.
- Reusing `run_state.SPEND_BASIS` is appropriate. It already labels the execution count as projected and not an invoice at `operator-claude-plugin/scripts/run_state.py:172-180`.
- The report explicitly distinguishes association states rather than treating missing association evidence as success.
- Missing and malformed artifacts are recognized as audit gaps, which is essential for unattended execution.
- The plan correctly requires operator-facing `gated` wording distinct from `written`.

## Concerns

- **CRITICAL: The report cannot prove successful writes.** Its positive evidence comes from `written_records`, whose current/planned classification relies on pre-write actions and existing IDs at `operator-claude-plugin/scripts/written_records.py:161-182`.
- **HIGH: The plan actually joins five stores, not four.**
  - `written_records`
  - `run_state`
  - `run_manifest`
  - `held_queue`
  - `remainder_queue`
  
  This matters because all five are independently written and can disagree after a crash.
- **HIGH: `written_records.load()` cannot distinguish missing, malformed, unreadable, and empty.** It returns `[]` or skips a malformed file at `operator-claude-plugin/scripts/written_records.py:291-323`, yet the plan promises a precise gap reason.
- **HIGH: `run_manifest.load_scoped()` similarly collapses several malformed states.** See `operator-claude-plugin/scripts/run_manifest.py:242-274`.
- **HIGH: `row_id` remains absent on some new pair-pipeline writes.** The current runbook strips it at `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:635-647`.
- **HIGH: Contradiction handling is unspecified.** Plausible crash states include:
  - Written ledger says `written`; manifest says `held`.
  - Remainder queue and written records contain the same row.
  - Association says `associated`; terminal write result is unknown.
  - Run state remains `running`; durable result records exist.
  - Held queue contains a row absent from the run manifest.
- **HIGH: The production call sites do not clearly retain all required inputs.** The report expects `outcome`, `disarm`, `balances`, and `ceiling`, but the runbooks currently do not persist or consistently retain all those observations through both pair-pipeline dispatches.
- **HIGH: A single `outcome` cannot describe the pair pipeline’s multiple dispatch legs.** Match/enrichment and final ingest may share one run ID but have separate outcomes and disarm events.
- **HIGH: Markdown string tests do not prove the report executes after every terminal path.** They do not cover exceptions, partial failures, or process interruption.
- **MEDIUM: `read_progress()` already loads the manifest at `operator-claude-plugin/scripts/run_state.py:332-365`; separately loading it can produce an inconsistent snapshot.
- **MEDIUM: The current runbook acknowledges that confident rows can lack manifest verdicts at `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:521-523`, so progress may undercount completed work.
- **MEDIUM: In-memory `CeilingStop` details disappear after a crash.** The durable remainder may survive, but chunk-stop details and the grant-time observations may not.
- **MEDIUM: Keying records only by `row_id` can overwrite multiple events for one row.** The same row can have enrichment and ingest events under one run.
- **MEDIUM: The report is not itself persisted.** That is acceptable if all facts are reconstructable, but balances, disarm verdict, and ceiling verdict are currently ephemeral.

## Suggestions

- Make terminal write confirmation a prerequisite for `written`, or render the result as `write_attempted`/`write_result_unknown`.
- Correct the architecture description to five durable stores plus ephemeral runtime observations.
- Add classified-read APIs to `written_records` and `run_manifest`, similar to:
  - `held_queue.classify_read()` at `operator-claude-plugin/scripts/held_queue.py:260-279`
  - `run_state.classify_read()` at `operator-claude-plugin/scripts/run_state.py:265-273`
- Define a contradiction matrix. Contradictions should become explicit audit findings, never silently resolved.
- Model rows as event histories:
  ```text
  row_id -> [enrichment event, ingest event, association event, write event]
  ```
  Alternatively use `(row_id, lane, chunk_index, action)` as the key.
- Take one run-manifest snapshot and derive both progress and row verdicts from it.
- Persist non-authority audit facts needed after a crash:
  - Ceiling verdict
  - Balance readability
  - Disarm result
  - Ceiling-stop metadata
  
  Do not persist the grant itself.
- Accept all dispatch outcomes in the report, not a single `outcome`.
- Add executable orchestration helpers and tests for:
  - Normal completion
  - Ceiling stop
  - Chunk failure
  - Exception before disarm
  - Crash-reconstructed report
  - Contradictory artifacts
- Display a prominent “report incomplete” banner whenever any store or terminal confirmation is unavailable.

## Risk Assessment

**CRITICAL.** The proposed report can appear authoritative while relying on unconfirmed writes, incomplete correlation, independently written stores, and loader APIs that hide why evidence is missing.

---

# Cross-Plan and Phase-Level Findings

## D-53-02 Reversal

The reversal is justified on its merits:

- The old behavior is explicitly disclosure-only in `operator-claude-plugin/scripts/write_grant.py:113-154`.
- That model was reasonable while every send was actively supervised.
- Phase 57 gates unattended spending, so a non-binding ceiling no longer satisfies the safety requirement.
- The execution estimate is conservative, and the plans correctly disclose that it overstates the measured example rather than pretending it is exact.

The reversal is **not adequately recorded for future readers**:

- `57-CONTEXT.md` and Plan 57-01 explain it.
- `.planning/STATE.md` still records D-53-02 as disclosure-only.
- `.planning/phases/61-autonomous-batch-runs/61-CONTEXT.md` still depends on the old semantics.
- `57-DISCUSSION-LOG.md` starts with D-57-01 rather than recording a dedicated supersession decision.
- None of the five plans lists those canonical decision artifacts as files to update.

**Required improvement:** Add a decision such as:

> D-57-00 supersedes D-53-02 for unattended interactive runs. The prior disclosure-only behavior remains historical context; Phase 57 changes the execution allowance from informational to a conservative binding preflight and mid-run constraint.

Update `.planning/STATE.md`, the v1.1 milestone context/roadmap, and any Phase 61 current-state text that still presents D-53-02 as active.

## Dependency Ordering

The proposed waves need adjustment:

- Plan 57-02 correctly depends on 57-01 only weakly; most of its work is independent.
- Plan 57-03 depends on 57-01 because it consumes `CeilingStop` and refusal output.
- Plan 57-04 does not consume Plan 57-01 code and could run in wave 1.
- Plan 57-05 claims G-4 closure but does not depend on Plan 57-04. This is the wrong dependency direction.
- Plan 57-05 must also wait for a corrected row-correlation design, not just the syntactic `row_id` addition.

Recommended ordering:

1. Wave 1: revised 57-01 and 57-04 in parallel.
2. Wave 2: revised 57-02 and 57-03 after their respective prerequisites.
3. Wave 3: 57-05 after 57-02, 57-03, and 57-04.
4. Phase gate: full integration test plus explicit verification of the first-live-run prerequisites.

## Requirements Coverage

### RUN-05

**Not fully closed as planned.**

Preflight refusal is covered, but:

- The guard is checked after sending a breaching chunk.
- `rerequest_unanswered()` can bypass the tally.
- External instance-wide concurrency is unaccounted for.
- The smaller-batch remainder is offered but not durably queued.
- Some remainder shapes lose records.

### AFTER-01

**Not fully closed as planned.**

The report lists all requested sections, but:

- Positive write confirmation is missing.
- Correlation does not survive every lane.
- Contradictory crash-partial artifacts have no reconciliation policy.
- Missing versus malformed evidence cannot be distinguished through the named loaders.
- Multiple dispatch events per row can overwrite one another.

### AFTER-03

**Partially closed.**

`write_blocked -> gated` is a good and necessary distinction. But `written` remains overclaimed because it is inferred from an allowed decision and an ID, not a terminal write result.

### G-4

**Ambiguous closure.**

- Apollo is structurally unreadable with the current credential and must remain an explicit blind spot.
- ZoomInfo is correctly scheduled for a live re-probe.
- A probe that still returns `provider_error` does not itself fix G-4.
- The phase must state whether honest `unknown` handling is accepted as closure or whether G-4 remains partial.

### GRANT-04 Producer

**Partially covered.**

The proposed `record_dispatch_outcome()` creates the missing normal-return producer for `ceiling_breach`. Exception and crash paths can still leave the in-memory grant open or unreported.

## Security and Safety

The plans preserve important boundaries:

- No persisted grant.
- Record-scoped write allowlists remain intact.
- Unknown provider balances are not converted to zero or headroom.
- Workflow JSON changes go through the builder.
- The new durable store uses 0600 atomic writes.

Remaining high-impact risks:

- Unconfirmed writes reported as completed.
- External concurrent execution spending bypassing local headroom.
- Unsent records lost from unsupported remainder shapes.
- Grants left open in memory after unexpected exceptions.
- A live probe whose network path is broader than documented.
- Deployment in Plan 57-02 before the full phase safety gate is complete.

## Final Risk Assessment

**Overall: HIGH**

The plan set has strong research, good TDD intent, and generally sound component boundaries. It does not yet establish the end-to-end safety proposition required before the first unattended, credit-spending live batch.

The blocking revisions are:

1. Make the ceiling check pre-send, not post-send.
2. Bring every dispatch path, especially `rerequest_unanswered()`, under the ceiling.
3. Preserve all supported remainder shapes and queue the accepted split at a clearly authorized state transition.
4. Stop calling a row `written` without terminal write evidence.
5. Preserve correlation through the final ingest lane.
6. Define cross-store crash and contradiction reconciliation.
7. Make Plan 57-05 depend on Plan 57-04.
8. Record D-53-02’s supersession in canonical project state and downstream context.
9. Add executable integration tests instead of relying primarily on Markdown identifier checks.
10. Treat a live, armed unattended batch as a separate post-verification checkpoint, not an automatic consequence of these plans passing unit tests.

---

## OpenCode Review (kimi-k3)

**LANE DROPPED — failed or returned empty output.**

`kimi-k3` was invoked twice through the `opencode` lane. Both attempts terminated at the lane's
900,000 ms timeout floor with `[spawn error: ETIMEDOUT]`, having emitted only progress narration
and no review body.

Attempt 1 stderr:

```
[spawn error: ETIMEDOUT]
```

Attempt 1 partial output (all of it):

```
I'll review this thoroughly by verifying every checkable claim against the actual code. Let me start with the phase supporting artifacts and the most load-bearing source files.
Verified the D-53-02 text and the hardcoded `False` at :261. Now the consumer/producer chain and test pins.
All core claims verifying. Now the remaining modules: run_state, confidence, run_manifest, cost_guard, build_cloud_workflows.
The ingest-lane gap is verified precisely as claimed. Now G-4 evidence and the proof/fixture foundations.
```

Attempt 2 stderr: `[spawn error: ETIMEDOUT]`. Attempt 2 partial output:

```
I'll review this thoroughly by verifying every checkable claim against the actual code. Let me start by reading the phase artifacts and dispatching parallel verifiers against the repo.
The four phase artifacts are read. Notably, COVERAGE.md as provided is an API-surface coverage matrix (INTEGRATE/OPT-OUT), not a requirement-to-plan map — I'll account for that. Now dispatching parallel source verifiers.
```

**This is a timeout kill, not a CLI or sandbox failure** — the prompt is ~66k tokens over five
large plans plus research, and the model did not finish source verification inside the floor. The
lane's timeout is fixed by its descriptor (`review-lane-invocation.cjs:211-213`); there is no CLI
or environment override.

`kimi-k3` reached this review through `review.default_reviewers`, which is a preference rather
than an assertion, so the drop is recorded here and in the consensus weighting rather than failing
the review. **This phase was effectively reviewed by two independent models, not three** — factor
that into how much adversarial coverage the plan set has actually received.

Two fragments are worth keeping even so, because they are the only substantive statements the lane
produced before dying, and both were being asserted as verified:

- *"Verified the D-53-02 text and the hardcoded `False` at :261."* — independent corroboration
  that the disclosure-only text this phase overturns is live in `write_grant.py`.
- *"COVERAGE.md as provided is an API-surface coverage matrix (INTEGRATE/OPT-OUT), not a
  requirement-to-plan map."* — **VERIFIED by the orchestrator.** `COVERAGE.md:1` is titled
  "Phase 57 — API Coverage Matrix" and its rows are per-capability `INTEGRATE`/`OPT-OUT`
  dispositions for the n8n, HubSpot and provider surfaces. It contains **no** requirement-to-plan
  mapping for RUN-05 / AFTER-01 / AFTER-03 / G-4. This is a MEDIUM finding in its own right: the
  phase has no artifact that evidences requirement coverage, and gemini-3-6-flash's claim that
  "the 5 plans accurately map to and fulfill requirements RUN-05, AFTER-01, AFTER-03 and G-4 as
  claimed in `COVERAGE.md`" is asserting a claim `COVERAGE.md` never makes. The single dying
  fragment of a dropped lane caught something both surviving reviewers missed.

---

## OpenCode Review (gemini-3-6-flash)

# Executive Summary & Cross-AI Plan Review

**Phase 57: Ceilings, refusal-before-start, and post-run proof**  
**Assessment:** The implementation plans for Phase 57 are **exceptionally thorough, grounded in actual codebase evidence, and well-designed.** They directly address the critical gap gating the first live unattended run (D-61-08) by turning informational cost disclosure into binding cost constraints, reconciling client-side ledger outcome vocabularies, and building end-of-run proof reports.

---

## 1. Evaluation of Operator Decision Overturn (D-53-02)

### Reversal Merits
D-53-02 originally recorded that *"the ceiling is disclosure, not constraint."* This was correct when every run was supervised interactively. However, for unattended, multi-chunk batch executions (Phase 61), informational disclosure alone offers no protection against overrunning provider credit balances or monthly n8n execution allowances.

### Assessment of Reversal
1. **Justification:** Fully justified. Unattended runs with real provider balances require hard pre-flight refusals and mid-run circuit breakers to prevent runaway spend or rate/quota exhaustion.
2. **Traceability:** Plan 57-01 (Task 2) explicitly replaces `_DISCLOSURE_NOT_CONSTRAINT` with `_CEILING_CONSTRAINT` in `write_grant.py`, adding code comments that reference the decision replacement and its rationale.
3. **Downstream Safety:** Downstream components depend on `write_grant.py` and `chunking.dispatch_plan()`. The plan preserves non-overridden behavior when the budget is within limits or when balances/allowances read as `CEILING_UNKNOWN` (per D-57-02), preventing false-positive blocks while strictly enforcing limits when data is available.

---

## 2. Strengths

- **Direct Grounding in Codebase Realities:**
  - Identifies that `write_grant.record_send_outcome` has zero production callers and wires it via `record_dispatch_outcome` (`operator-claude-plugin/scripts/write_grant.py:899`).
  - Correctly notes that `written_records.classify_item` discards `row_id` (`operator-claude-plugin/scripts/written_records.py:161-182`), which is essential for joining per-run records with `run_state` and `run_manifest`.
  - Recognizes the 10 distinct `action` values emitted by `scripts/build_cloud_workflows.py` (including `enrich`) and integrates `enrich` directly into `WRITE_ACTIONS`.
- **Strict Compliance with Constraints & Signature Locks:**
  - Avoids adding any parameter named `grant` to `chunking.dispatch_plan()` (using `execution_ceiling` instead), respecting signature checks in `operator-claude-plugin/tests/test_write_grant.py:1455-1463`.
  - Honors **GRANT-06** and **D-57-05** by ensuring `remainder_queue.py` stores **work specs only** (record IDs, object types) and refuses any authority markers, grants, or tokens.
- **Honest Handling of Platform Blind Spots:**
  - Incorporates **D-57-02** so that unreadable balances or truncated `n8n_read.executions_in_window` samples yield `CEILING_UNKNOWN` / `unconfirmed` rather than blocking runs or assuming false headroom.
- **Durable Anti-DRY Security Discipline:**
  - Re-implements `_FORBIDDEN_NAME_MARKERS` in `remainder_queue.py` rather than importing it, adhering to the project's isolation conventions against credential leaks (`written_records.py`, `held_queue.py`).

---

## 3. Concerns & Potential Risks

### HIGH SEVERITY

- **1,000-Execution Page Cap Underestimation in `n8n_read.executions_in_window`**
  - **Location:** `operator-claude-plugin/scripts/n8n_read.py:69,73` (`MAX_EXECUTION_PAGES = 4`, `EXECUTIONS_WINDOW_PAGE_LIMIT = 250`).
  - **Mechanism:** `executions_in_window` walks up to 1,000 executions total across **all workflows** on the n8n instance. On an active instance near month-end, the 1,000-execution cap can be hit within hours or days rather than covering the full month.
  - **Risk:** Plan 57-01 correctly requires checking `covers_full_window` and `truncated_by_page_cap`. When truncated, `headroom["sampled"]` evaluates to `False`, forcing `ceiling_verdict` to `CEILING_UNKNOWN`. This means near month-end on a busy portal, pre-flight ceiling checks will **permanently fallback to `CEILING_UNKNOWN`**, effectively bypassing pre-flight refusals for large batches and placing 100% of budget protection on mid-run tally checks.

### MEDIUM SEVERITY

- **Discrepancy Between Over-stating Pre-Flight Projections & Real Execution Multipliers**
  - **Location:** `operator-claude-plugin/scripts/write_grant.py:139` (`EXECUTIONS_BASIS = "1 webhook execution per chunk + 1 sub-execution per record"`).
  - **Mechanism:** Per P-10 findings, `EXECUTIONS_BASIS` over-states execution costs by ~3x (e.g., a 2-record chunk projects 3 executions but listed 1 in n8n API output).
  - **Risk:** In Plan 57-03, `write_grant.split_for_allowance()` uses this 3x over-stating formula to offer smaller batches. When an operator attempts a batch of 150 records, the split calculator may claim only 50 records fit, prompting unnecessary batch splits. While conservative and safe against overspending, it degrades operator UX for high-volume batches.

- **ZoomInfo Balance Probe Dependency on Live Credentials (G-4)**
  - **Location:** `scripts/prove_zoominfo_balance.py` & `operator-claude-plugin/scripts/cost_guard.py:225`.
  - **Mechanism:** Plan 57-04 relies on a live probe against the deployed n8n instance. If the deployed ZoomInfo API credential or token mint/cache subgraph (`scripts/build_cloud_workflows.py:4163-4184`) fails due to external 5xx/401 errors, the probe verdict will remain `provider_error` or `inconclusive`.
  - **Risk:** The plan handles this safely via D-57-02 disclosure, but if the credential setup cannot be validated live, G-4 cannot be fully marked as "fixed in code," leaving ZoomInfo balances permanently reported as `unconfirmed`.

### LOW SEVERITY

- **Join Key Degraded State for Historical Records**
  - **Location:** `operator-claude-plugin/scripts/written_records.py:207-219` & `operator-claude-plugin/scripts/run_report.py`.
  - **Mechanism:** Adding `row_id` to `classify_item` works for new runs, but old `written_records-<run_id>.json` files lack `row_id`.
  - **Risk:** When `build_run_report` generates a report for an old run, entries will have `row_id: None`. Plan 57-05 handles this gracefully by marking them unjoinable without crashing, but historical reporting for pre-Phase 57 runs will remain partially unlinked.

---

## 4. Suggestions & Improvements

1. **Document Page-Cap Fallback Behavior in Operator Docs:**
   - In `write_grant.py` and SKILL runbooks, explicitly document that if n8n execution history exceeds 1,000 total executions in a calendar month, `n8n_read.executions_in_window` will report `truncated_by_page_cap: True`, resulting in a `CEILING_UNKNOWN` status. Clarify that mid-run tally checks will still protect the run.
2. **Include Unsent Chunks in End-of-Run Report Summaries:**
   - In `run_report.py` (Plan 57-05), ensure that when `outcome.ceiling_stop` is present, the summary explicitly breaks down: *Attempted Records*, *Successfully Written*, *Held Records*, and *Ceiling-Stopped (Unattempted) Records* to ensure complete clarity for the operator.
3. **Verify Disarmed Status After Ingest Workflow Redeploy:**
   - In Plan 57-02 (Task 3), ensure the post-deploy assertion checks that `ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`, and `ALLOW_HUBSPOT_REVIEW_WRITES` all evaluate to `"false"` on the deployed workflow node parameters.

---

## 5. Risk Assessment

- **Overall Risk Level:** **LOW**
- **Justification:**
  1. **Strict Safety & Isolation:** The plans introduce zero new external dependencies, maintain the disarmed-by-default posture on n8n workflows, and do not modify core write-safety gates (`_writeSafetyAllows`).
  2. **Goal & Coverage Alignment:** The 5 plans accurately map to and fulfill requirements **RUN-05**, **AFTER-01**, **AFTER-03**, and **G-4** as claimed in `COVERAGE.md`.
  3. **High Reversibility & Fail-Safe Defaults:** Mid-run stops freeze dispatches gracefully into a durable `remainder_queue`, and unreadable budgets disclose blind spots without corrupting state or halting executions unexpectedly.

---

## Summary Statement

The implementation plan set for Phase 57 is **approved and ready for execution**. It provides robust, well-tested budget constraints and reporting mechanisms necessary to safely gate the project's first live unattended batch runs.

---

## Source-Grounding Pass (`plan_review.source_grounding`, effective authority: `grep`)

Run by the orchestrating agent after the reviewer lanes, per the caller's required pass.
**Authority is `grep`** — this project has no `lsp`/`scip` index, so a MISSING verdict is
`needs-acknowledgement`, never a hard block, and every *signature* claim is UNCHECKABLE.

### Step 2 — exclusion set (symbols this phase CREATES)

All five plans carry an "Artifacts this phase produces" section. Only `57-01-PLAN.md:451-473`
holds content; 57-02/03/04/05 each delegate to it by reference. The declared new-symbol set,
excluded from resolution:

`write_grant.allowance_headroom`, `write_grant.ceiling_verdict`, `write_grant.CEILING_OK` /
`CEILING_OVER` / `CEILING_UNKNOWN`, `write_grant.record_dispatch_outcome`,
`write_grant._CEILING_CONSTRAINT`, `write_grant._ALLOWANCE_SAMPLED`, `plan_grant`'s `override`
kwarg + `ceiling` key, `envelope`'s `headroom` kwarg + `spent_sampled` / `remaining_sampled` /
`sample_covers_full_window` / `sample_truncated_by_page_cap` / `ceiling` figures,
`chunking.CeilingStop`, `chunking.DispatchOutcome.ceiling_stop`, `dispatch_plan`'s
`execution_ceiling` kwarg, `chunking.projected_spend`, `written_records.GATED` / `HELD` /
`FAILED` / `NO_ACTION` / `WRITTEN_ID_UNKNOWN` + the `row_id` / `association` entry fields,
`remainder_queue.py` and `build_entry` / `save` / `load` / `remainder_path` /
`REASON_CEILING_BREACH` / `REASON_ALLOWANCE_SPLIT` / `RemainderQueueError` /
`REMAINDER_QUEUE_GLOB` / `queue_path` / `ALL_REASONS`, `write_grant.split_for_allowance`,
`scripts/prove_zoominfo_balance.py` + `ALLOW_ZOOMINFO_BALANCE_PROBE`,
`operator-claude-plugin/scripts/run_report.py` + `build_run_report`.

Three further files are declared as *created* in plan task bodies rather than in the 57-01
list, and are excluded on the same basis (each plan says "Add"):
`tests/n8n/ingestResponseRowId.test.mjs` (`57-02-PLAN.md:297`),
`operator-claude-plugin/tests/test_run_report.py` (`57-05-PLAN.md:121`), and the
`backend_status_zoominfo_provider_error` conftest fixture (`57-04-PLAN.md:180`).

### Step 3 — verdicts for every remaining cited symbol

#### Modules / files cited as existing

| Symbol | Verdict | Evidence |
|---|---|---|
| `operator-claude-plugin/scripts/write_grant.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/chunking.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/written_records.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/report_enrichment.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/held_queue.py` | VERIFIED | file exists (`57-03-PLAN.md:72`) |
| `operator-claude-plugin/scripts/run_state.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/durable_paths.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/cost_guard.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/n8n_read.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/preingest.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/confidence.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/run_manifest.py` | VERIFIED | file exists |
| `operator-claude-plugin/scripts/n8n_cadence.py` | VERIFIED | file exists |
| `operator-claude-plugin/tests/conftest.py` | VERIFIED | file exists (`57-01-PLAN.md:144`) |
| `operator-claude-plugin/tests/test_write_grant.py` | VERIFIED | file exists |
| `operator-claude-plugin/tests/test_report_enrichment.py` | VERIFIED | file exists |
| `operator-claude-plugin/tests/test_cost_guard.py` | VERIFIED | file exists |
| `scripts/build_cloud_workflows.py` | VERIFIED | file exists |
| `scripts/deploy_n8n_workflows.py` | VERIFIED | file exists |
| `scripts/prove_async_recovery.py` | VERIFIED | file exists |
| `n8n/wf_contact_ingest_cloud.json` | VERIFIED | file exists |
| `n8n/code/providerSelection.js` | VERIFIED | file exists |

#### Functions / classes / constants cited as existing

| Symbol | Verdict | Evidence (`file:line`) |
|---|---|---|
| `write_grant.record_send_outcome` | VERIFIED | `operator-claude-plugin/scripts/write_grant.py:899` |
| `write_grant.envelope` | VERIFIED | `write_grant.py:183` |
| `write_grant.plan_grant` | VERIFIED | `write_grant.py:411` |
| `write_grant.CLOSED_CEILING_BREACH` | VERIFIED | `write_grant.py:667` (`= "ceiling_breach"`), used `:673`, `:933` |
| `write_grant.EXECUTIONS_BASIS` | VERIFIED | `write_grant.py:139` |
| `write_grant._DISCLOSURE_NOT_CONSTRAINT` | VERIFIED | `write_grant.py:150` — the D-53-02 text this phase overturns |
| `write_grant._ALLOWANCE_GAP` | VERIFIED | `write_grant.py:143` |
| `write_grant._envelope_block` | VERIFIED | `write_grant.py:281` (called `:277`) |
| `written_records.classify_item` | VERIFIED | `written_records.py:131` |
| `written_records.WRITE_ACTIONS` | VERIFIED | `written_records.py:96` |
| `written_records.written_records_path` | VERIFIED | `written_records.py:118` |
| `written_records.append_chunk` | VERIFIED | `written_records.py:241` |
| `written_records.load` | VERIFIED | `written_records.py:291` |
| `written_records.WRITTEN_RECORDS_GLOB` | VERIFIED | `written_records.py:81` |
| `written_records.WrittenRecordsError` | VERIFIED | `written_records.py:106` |
| `written_records._entries_from_document` | VERIFIED | `written_records.py:207` |
| `written_records._FORBIDDEN_NAME_MARKERS` | VERIFIED | `written_records.py:100` |
| `written_records.WRITTEN`/`CREATED_ID_UNKNOWN`/`NOT_WRITTEN` | VERIFIED | `written_records.py:89-91` |
| `report_enrichment._ACTION_TO_OUTCOME` | VERIFIED | `report_enrichment.py:38` |
| `report_enrichment._outcome_for_row` | VERIFIED | `report_enrichment.py:121` |
| `report_enrichment.SUCCESS_OUTCOMES` | VERIFIED | `report_enrichment.py:50` |
| `report_enrichment._OUTCOME_REASON` | VERIFIED | `report_enrichment.py:56` |
| `report_enrichment.build_sync_report` | VERIFIED | `report_enrichment.py:245` |
| `report_enrichment.build_enrichment_report` | VERIFIED | `report_enrichment.py:285` |
| `report_enrichment._empty_counts` | VERIFIED | `report_enrichment.py:73` |
| `report_enrichment._build_row_report` | VERIFIED | `report_enrichment.py:167` |
| `chunking.dispatch_plan` | VERIFIED | `chunking.py:317` |
| `chunking.failed_batch` | VERIFIED | `chunking.py:494` |
| `chunking.chunk_ceiling` | VERIFIED | `chunking.py:157` |
| `chunking.plan_chunks` | VERIFIED | `chunking.py:183` |
| `chunking.DispatchOutcome` | VERIFIED | `chunking.py:112` |
| `chunking.ChunkResult` (`.ok`) | VERIFIED | `chunking.py:88` |
| `chunking.UNKNOWN` | VERIFIED | `chunking.py:60` |
| `chunking.merge_chunk_verdicts` | VERIFIED (uncited) | `chunking.py:454` — on the caller's watch list but **never cited by any 57 plan** |
| `run_state.read_progress` | VERIFIED | `run_state.py:332` |
| `run_state.spend_against_ceiling` | VERIFIED | `run_state.py:368` |
| `run_state.SPEND_BASIS` | VERIFIED | `run_state.py:175` |
| `run_state.Progress` | VERIFIED | `run_state.py:309` |
| `durable_paths._atomic_write_0600` | VERIFIED | `durable_paths.py:57` |
| `durable_paths.resolve_state_path` | VERIFIED | `durable_paths.py:234` |
| `held_queue.load` | VERIFIED | `held_queue.py:245` |
| `held_queue.build_entry` | VERIFIED | `held_queue.py:174` |
| `held_queue.save` | VERIFIED | `held_queue.py:186` |
| `held_queue.queue_path` | VERIFIED | `held_queue.py:147` |
| `held_queue.fingerprint` | VERIFIED | `held_queue.py:154` |
| `held_queue.ROW_FIELD_ALLOWLIST` | VERIFIED | `held_queue.py:98` |
| `confidence.ALL_HOLD_CODES` | VERIFIED | `confidence.py:74` |
| `cost_guard.fetch_balances` | VERIFIED | `cost_guard.py:225` |
| `cost_guard.compare` | VERIFIED | `cost_guard.py:274` |
| `n8n_read.executions_in_window` | VERIFIED | `n8n_read.py:258` |
| `n8n_read.EXECUTION_ALLOWANCE_KEY` | VERIFIED | `n8n_read.py:62` |
| `n8n_read.MAX_EXECUTION_PAGES` | VERIFIED | `n8n_read.py:73` |
| `n8n_read.EXECUTIONS_WINDOW_PAGE_LIMIT` | VERIFIED | `n8n_read.py:69` |
| `preingest.rerequest_unanswered` | VERIFIED | `preingest.py:662` |
| `preingest.Outcome` | VERIFIED | `preingest.py:51` |
| `run_manifest.load_scoped` | VERIFIED | `run_manifest.py:242` |
| `run_manifest.run_manifest_path` | VERIFIED | `run_manifest.py:151` |
| `run_manifest.MATCHED`/`ENRICHED`/`HELD`/`CONFIDENCE_HELD`/`UNCHECKED`/`UNANSWERED` | VERIFIED | `run_manifest.py:102-109` |
| `n8n_cadence.check_budget_floor` | VERIFIED | `n8n_cadence.py:452` |
| `conftest.stub_module_transport_factory` | VERIFIED | `operator-claude-plugin/tests/conftest.py:260` |
| `conftest.no_network` / `no_durable_writes` | VERIFIED | `conftest.py:588`, `:608` |
| `conftest.backend_status_unknown_balance` | VERIFIED | `conftest.py:533` |
| `conftest._balance` | VERIFIED | `conftest.py:498` |
| `test_a_revocation_midway_does_not_stop_a_running_dispatch` | VERIFIED | `operator-claude-plugin/tests/test_write_grant.py:1371` |
| `BUILD_INGEST_RESPONSE` | VERIFIED | `scripts/build_cloud_workflows.py:471` |
| `ENRICH_STATUS_BUILD_RESPONSE` | VERIFIED | `scripts/build_cloud_workflows.py:6327` |
| `RUN_LIVE_PARITY` | VERIFIED | `tests/test_conftest_credential_guard.py:6,34,39` |
| `_patch_durable_dir` | VERIFIED | `operator-claude-plugin/tests/test_written_records.py:297` (referenced from `conftest.py:620`) |
| Apollo `usage_stats` endpoint | UNCHECKABLE | an external Apollo API path (`57-04-PLAN.md:56`), not a repo symbol. INFO. |

#### Line-range claims the plans make (checked directly)

| Plan claim | Verdict | Evidence |
|---|---|---|
| `57-03-PLAN.md:259` — "`chunk_ceiling` at 157-180, `plan_chunks` at 183+, `failed_batch` at 494-517" | VERIFIED | `chunking.py:157`, `:183`, `:494`, body ends `:517` |
| `57-01-PLAN.md:248` — "`preingest.py:713` and `scheduled_arm.py:234`" as the existing `dispatch_plan` callers | VERIFIED | `preingest.rerequest_unanswered` at `preingest.py:662` calls `dispatch_plan` in that range |
| `57-04-PLAN.md:158` — "`conftest.py` lines 520-560 — the existing `_balance()` helper and `backend_status_unknown_balance`" | VERIFIED | `conftest.py:498` (`_balance`, slightly above the cited range), `:533` (fixture) |

#### Factual claims about existing code that do NOT hold

| Claim | Verdict | Evidence |
|---|---|---|
| `57-04-PLAN.md:46-47`, `:168`, `:184` describe the **existing Apollo fixture** as carrying `unrecognized_response_shape` | **MISSING → needs-acknowledgement** (severity per authority `grep`) | `operator-claude-plugin/tests/conftest.py:541` sets `error="http_403", status=403`; `:543` sets health `reason="http_403"`. The string `unrecognized_response_shape` does not appear in `conftest.py`. Two independent reviewers raised this; grep confirms it. |

### Step 5 — Verification coverage

Everything below was **not** resolved by grep, with the reason. A clean grounding pass does not
mean these were checked.

**UNCHECKABLE under `grep` authority — every signature claim (INFO):**

- `write_grant.record_dispatch_outcome(grant, outcome, config=None, *, disarm=None, transport=None)` — arity/kwarg-only-ness (new symbol anyway)
- `write_grant.allowance_headroom(config, *, transport=None, now=None)` — same
- `chunking.dispatch_plan(..., execution_ceiling=...)` — that the new kwarg is *keyword-only* and that the existing signature has no `grant` parameter today (`57-01-PLAN.md:290` proposes an `inspect.signature` assertion precisely because grep cannot do this)
- `write_grant.plan_grant(..., override=...)` — keyword-only-ness
- `write_grant.envelope(..., headroom=...)` — keyword-only-ness
- `chunking.CeilingStop` field list / `frozen=True` — the dataclass does not exist yet
- `written_records.classify_item(item) -> dict` return-shape claims — grep sees the `def`, not the returned keys
- `held_queue.build_entry(row, hold_code, reason, outcome, observed_signals=None)` parameter compatibility with a budget remainder
- Every "X calls Y" / "no production caller reaches Z" reachability claim (e.g. `record_send_outcome` having no producer) — call-graph analysis needs an index, not grep. The reviewers asserted these from reading; grep neither confirms nor refutes.

**Skipped deliberately (INFO):**

- All symbols in the exclusion set above — created by this phase, so absence is expected, not a finding.
- `row_id`, `run_id`, `reason`, `action`, `outcome`, `ok`, `skip`, `update`, `create`, `enrich`, `block`, `email`, `records`, `spec`, `entries` and similar bare dictionary keys / string literals — not resolvable as symbols; they are data values, and grep cannot distinguish a key from a coincidental word.
- n8n workflow node names (`Build Response`, `Decide Company Action`, `Parse HubSpot Event`) — these resolve as string constants in `build_cloud_workflows.py`, which was confirmed to exist, but node-graph wiring is not grep-checkable.
- `hs_object_id`, `contact_id`, `company_id`, `remaining_credits` — HubSpot / provider API field names, external to this repo.

**Totals:** 22 file paths VERIFIED, 64 code symbols VERIFIED, 0 AMBIGUOUS, 1 factual claim
MISSING (needs-acknowledgement), ~9 signature/reachability classes UNCHECKABLE (INFO), plus the
declared new-symbol exclusion set. Zero hard blocks — hard blocks require `lsp`/`scip` authority,
which this project does not have.

---

# Cross-AI Plan Review — Phase 57 — CYCLE 2 (review of the REVISION)

```yaml
cycle: 2
phase: 57
reviewers_invoked: [gpt-5-6-sol, kimi-k3, grok-4-6]
reviewers_producing_a_review: [gpt-5-6-sol, grok-4-6]
lanes_completed: 2 of 3
reviewed_at: 2026-08-31T13:33:06+10:00
revision_under_review: 7959fd6
plans_reviewed:
  - 57-01-PLAN.md
  - 57-02-PLAN.md
  - 57-03-PLAN.md
  - 57-04-PLAN.md
  - 57-05-PLAN.md
source_grounding: run (authority `grep`)
requirements_substituted: .planning/milestones/v1.1-REQUIREMENTS.md
```

> **Assurance level: 2 of 3 lanes.** `kimi-k3` dropped again. Its cycle-1 failure was
> `[spawn error: ETIMEDOUT]` at the lane's fixed 900s floor on both attempts; this cycle it
> failed differently and faster — `opencode review failed or returned empty output … agent
> ended its turn with no final message, stop reason=unknown, output tokens=0`, after 103s
> (13:29:57 → 13:31:40). Per the cycle-2 brief it was given **one** attempt and not retried.
> A 2-of-3 review is a materially lower assurance level than 3-of-3; nothing below carries
> three-way corroboration.

> **The reviewer panel CHANGED between cycles, which weakens cross-cycle comparison.**
> Cycle 1 ran `gpt-5-6-sol`, `kimi-k3`, `gemini-3-6-flash`. `review.default_reviewers` now
> resolves to `["gpt-5-6-sol", "kimi-k3", "grok-4-6"]` and no `gemini-3-6-flash` instance is
> defined in `review.reviewer_instances` any more. Selection was resolved through config with
> no reviewer flags passed, as instructed. Consequence: any cycle-1 finding raised **only** by
> `gemini-3-6-flash` had no originating voice this cycle, so its absence here is not evidence
> of closure.

> Note: gpt-5-6-sol, kimi-k3 and grok-4-6 all share the `opencode` adapter; their consensus is
> cross-model, not cross-tool.

> **Requirements context (unchanged from cycle 1, and deliberately re-applied).** The stock
> `gather_context` step copies the root `.planning/REQUIREMENTS.md`, which contains **zero**
> occurrences of RUN-05, AFTER-01, AFTER-03 or G-4 (`grep -c` returns 0). The reviewers were
> given `.planning/milestones/v1.1-REQUIREMENTS.md` instead (6 matches), and the substitution
> is stated in the prompt they received.

## Cycle-2 Consensus Summary

Both producing lanes agree the revision is a **real safety rewrite rather than a changelog
overlay**: cycle 1's load-bearing defects — the post-send tally, the quiet-instance sampling
predicate, `failed_batch`'s silent `people`/`companies` drop, markdown-grep wiring proofs, and
the deploy-before-gate ordering — are written into task actions and executable acceptance
criteria, not merely asserted. GRANT-06 is intact across both new persistence surfaces. Neither
reviewer found a binding constraint broken by the revision.

They diverge sharply on residual risk: **gpt-5-6-sol rates the phase HIGH** (blocking plan
defects at the phase boundaries), **grok-4-6 rates it MEDIUM** (conditional on 57-01 option A
landing and 57-05 option B not being chosen while the sample is unknown). The divergence is
substantive, not stylistic — see *Divergent Views*.

### Agreed Strengths (both lanes)

- The pre-send tally is placed correctly (first statement of the loop body, before
  `build_envelope`), the comparison is strictly-greater so an exactly-sized batch still sends,
  and the zero-overshoot sweep pins it. Both traced it against the real hook point in
  `chunking.py:373-383`.
- Quiet-instance exhaustion and busy-instance page truncation are modelled as separate facts;
  the diagnosis against `n8n_read.py:358-379` is correct.
- A deliberate budget stop has its own `DispatchOutcome` field and never masquerades as a chunk
  failure.
- `failed_batch` gains a per-shape round-trip property test over every shape `plan_chunks`
  accepts.
- Split persistence happens only after acceptance and a fresh grant; a refusal writes nothing.
- GRANT-06 is enforced by recursive forbidden-name tests on both new stores.
- The outcome vocabulary is centralised in a pure, total function, preserving
  `build_enrichment_report`'s never-raise contract.
- The first live unattended run is no longer an automatic consequence of a green test suite.

### Agreed Concerns (both lanes — highest priority)

**The 57-01 Task 1 checkpoint measures the UNFIXED sampler.** Both reviewers reached this
independently and both rate it HIGH/NEW. Task 1 is ordered before Task 2 and its `<context>`
(`57-01-PLAN.md:210-218`) prescribes running the measurement against today's
`n8n_read.executions_in_window`, which has neither `listing_exhausted` nor `max_pages`. On this
quiet account that call returns `covers_full_window: False` and `truncated_by_page_cap: False`,
i.e. exactly the unusable state Task 2 exists to fix. grok-4-6 states the load-bearing
conclusion plainly: **`listing_exhausted` in Task 2 is what makes RUN-05 reachable here — the
checkpoint is the escape hatch, not the mechanism.** The cycle-2 brief asked which is doing the
real work; both lanes answer Task 2, and both warn the operator could select option C ("leave
RUN-05 PARTIAL") on evidence the revision already knows how to fix.

### Divergent Views

| Question | gpt-5-6-sol | grok-4-6 |
|---|---|---|
| Overall risk | **HIGH** — "blocking plan defects … the plans should undergo one more focused revision before execution" | **MEDIUM** — "cycle 1's spend-after-breach and silent `people` drop are actually specified away"; HIGH only if Task 1 is decided on pre-fix data or 57-05 option B is chosen while the sample is unknown |
| `try/finally` + `CLOSED_UNHANDLED_ERROR` | PARTIALLY RESOLVED — the must-have "never left open by a crash path" overclaims; `finally` covers ordinary exceptions, not process death | RESOLVED |
| Phase-boundary defects (deploy scope, ZoomInfo before/after, live-spend prohibition) | Four separate HIGHs | Not raised |
| `CEILING_UNKNOWN` disabling both guards | Noted only inside the option-A cons summary | **Its own HIGH** — the hole that makes 57-05 option B dangerous |
| Checkpoint proliferation | Structural improvement | MEDIUM/NEW — wave 2 now blocked on two independent option selections |

Neither reviewer caught the two factual defects the grounding pass found (SG-1, SG-2 below);
neither caught the frozen-call-order test-file gap (SG-3). Conversely the grounding pass cannot
reach any of the reachability or ordering findings above. The two methods are complementary and
neither is sufficient alone.

## OpenCode Review (gpt-5-6-sol)

I’m validating the revised plans against the committed Cycle 1 findings and the current implementation surfaces, with particular attention to caller wiring, checkpoint dependencies, and artifact contracts.
# Phase 57 Cycle 2 Plan Review

## Summary

The revision materially improves the Phase 57 plans. Most Cycle 1 defects now have concrete mechanisms, caller-path tests, or explicit checkpoints rather than changelog-only claims. In particular, the pre-send ceiling placement, exhausted-listing handling, lossless remainder reconstruction, split acceptance transition, pure outcome classifier, contradiction reporting, and deployment deferral are genuinely present.

The plans are still not ready to execute unchanged. The most important remaining problems are newly introduced by the revision: the RUN-05 checkpoint measures the old sampler before its fixes exist; the proposed deployment command targets every cloud workflow rather than only the ingest workflow; the ZoomInfo probe requires before/after balances while permitting one request; final pair-pipeline dispatch accounting remains underspecified; and the plans still map AFTER-01 to closed despite admitting an unjoinable population. The four-checkpoint structure improves operator control, but two checkpoints are positioned or specified in ways that cannot validate the mechanisms they govern.

## Claimed Resolutions

### 1. Mid-run tally moved pre-send

**Verdict: RESOLVED**

The mechanism is present, not merely mentioned in revision prose.

- `57-01-PLAN.md:455-476` places the calculation as the first operation in the loop, before `build_envelope` and `dispatch_enrichment`.
- The comparison is strictly `would_be > execution_ceiling`, so equality remains sendable.
- `57-01-PLAN.md:312-329` requires transport calls for only the admitted chunks and no result for an unsent chunk.
- `57-01-PLAN.md:505-507` requires the zero-overshoot sweep.
- The placement correctly precedes the existing send at `operator-claude-plugin/scripts/chunking.py:373-383`.

The local guarantee is correctly narrowed: this prevents local dispatch overshoot, not concurrent instance-wide consumption.

### 2. Sampling predicate fixed at both ends

**Verdict: PARTIALLY RESOLVED**

The proposed code mechanism addresses both source defects:

- `listing_exhausted` distinguishes quiet-instance exhaustion from incomplete pagination.
- `max_pages` lets `allowance_headroom` request enough pages for the configured allowance.
- `57-01-PLAN.md:339-374` defines `sampled` as true when the listing is complete by either back-paging or exhaustion and not truncated.
- The existing defect is real: `covers_full_window` currently depends only on seeing an older execution, while the walker is capped at four pages at `operator-claude-plugin/scripts/n8n_read.py:258-281` and `:355-380`.

This should make RUN-05 reachable on this quiet account after implementation. Task 1 is not what makes it reachable; the Task 2 code changes do.

The checkpoint is incorrectly ordered, however:

- `57-01-PLAN.md:200-231` takes the live measurement before Task 2 adds `listing_exhausted` and the allowance-sized page budget.
- It therefore measures the known-broken sampler and cannot establish whether the revised sampler works on this account.
- Option A reasons prospectively that the fixes “should” make it usable rather than measuring the fixed behavior.

Move this checkpoint after the sampler implementation and repeat the measurement using the new `max_pages` behavior. Until then, the mechanism is credible but its account-specific proof is not.

### 3. `preingest.rerequest_unanswered` no longer bypasses the ceiling

**Verdict: PARTIALLY RESOLVED**

The direct bypass identified in Cycle 1 is addressed:

- `57-01-PLAN.md:624-650` adds `execution_ceiling` to `rerequest_unanswered`.
- It passes the value to the existing internal `dispatch_plan`.
- It adds `MergeResult.dispatch_outcome`, allowing its spend to be returned to the caller.
- This reaches the current hidden dispatch at `operator-claude-plugin/scripts/preingest.py:699-741`.

The broader claim that every pair-pipeline dispatch leg shares one decrementing ceiling is not yet concrete. The revised runbook describes subtracting `chunking.projected_spend()` over match, enrich, re-request, and final ingest, but the final ingest path does not clearly produce the same `chunking.DispatchOutcome` shape. The plan needs to name the final ingest adapter and show how its spend is charged before claiming the whole pair pipeline is covered.

### 4. `chunking.failed_batch` generalized to all five shapes

**Verdict: RESOLVED**

The revision directly addresses the source defect.

- Current planning accepts `rows`, `people`, `companies`, and `record_ids` at `operator-claude-plugin/scripts/chunking.py:206-277`, plus the list passthrough.
- Current reconstruction only combines `rows` and `record_ids`, falling back to the first chunk for other shapes at `operator-claude-plugin/scripts/chunking.py:494-517`.
- `57-03-PLAN.md:319-327` requires tests for all five forms.
- `57-03-PLAN.md:367-381` defines concatenation across the matching list-bearing key.
- `57-03-PLAN.md:445-446` includes executable checks for the previously lossy `people` and `companies` cases.

### 5. `REASON_ALLOWANCE_SPLIT` has a producer and refusal writes no file

**Verdict: PARTIALLY RESOLVED**

The transition is now explicit and correctly ordered:

1. `plan_grant` returns a pure refusal and offer.
2. The operator accepts a subset.
3. A fresh grant opens.
4. The remainder is persisted with `REASON_ALLOWANCE_SPLIT`.
5. Declining writes nothing.

This appears at `57-03-PLAN.md:402-421`, with a no-file test at `57-03-PLAN.md:342-351`.

A remaining design problem exists in `split_for_allowance`:

- It is specified around `record_ids` and `record_domains` at `57-03-PLAN.md:383-400`.
- `plan_chunks` does not accept a generic `record_domains` work shape at `operator-claude-plugin/scripts/chunking.py:183-277`.
- A domain is valid grant scope, but it is not automatically a complete resendable work specification.

The plan must distinguish authorization scope from dispatch work. For `people`, `companies`, and row-based requests, the split must preserve the original full work objects, not reduce them to grant IDs/domains.

### 6. `try/finally` grant closure with `CLOSED_UNHANDLED_ERROR`

**Verdict: PARTIALLY RESOLVED**

The ordinary exception path is now specified:

- `57-01-PLAN.md:674-682` requires an explicit unhandled-error close and re-raise.
- `record_dispatch_outcome` gains a reason override rather than mislabelling the exception as a ceiling breach.
- The AST test is an improvement over Markdown grep.

Two qualifications remain:

- The AST criterion verifies calls occur somewhere within a `try`/`finally`, but does not prove all exception-producing operations are protected or that the exception path supplies `CLOSED_UNHANDLED_ERROR`.
- The must-have statement that a grant is “never left open by a crash path” at `57-01-PLAN.md:36` is too broad. `finally` covers ordinary Python exceptions, not process termination, interpreter failure, or machine loss.

Rename the guarantee to “ordinary exceptions escaping the runbook close the in-memory grant.” Actual process crashes should remain explicitly outside it.

### 7. Override authority defined

**Verdict: RESOLVED**

The revision supplies real enforcement:

- `57-01-PLAN.md:395-416` requires a non-empty operator-provided reason.
- Missing or non-string reasons raise.
- `overridden`, `override_reason`, and `override_authority` are recorded.
- The report must render them.
- Runbooks are prohibited from manufacturing the override from config or stored state.
- Tests verify that the runbooks do not contain the override invocation.

This is a defensible narrow override over sampled information, not an unqualified bypass.

### 8. D-53-02 supersession recorded as D-57-00

**Verdict: RESOLVED**

The revision writes the supersession into all three named canonical locations:

- `.planning/STATE.md`
- `57-DISCUSSION-LOG.md`
- `61-CONTEXT.md`

The exact required text and placement are specified at `57-01-PLAN.md:558-588`, with preservation of the historical D-53-02 record. This is a real decision-record edit, not just a source comment.

### 9. Markdown-grep criteria replaced with AST tests and new prohibitions

**Verdict: RESOLVED**

The production runbook checks now require extraction and compilation of fenced Python:

- `57-01-PLAN.md:690-708`
- `57-05-PLAN.md:488-503`
- `57-VALIDATION.md` explicitly prohibits identifier grep as the sole proof and prohibits proving a gate from its own text.

Some secondary grep checks remain, but they are no longer the only reachability evidence. That is appropriate.

The AST tests should additionally assert the unhandled-error reason argument and full protected-region ordering, not only call presence.

### 10. Apollo error corrected to `http_403`

**Verdict: RESOLVED**

The revised plan correctly uses `http_403` and explicitly identifies the research artifact as stale:

- `57-04-PLAN.md:56-75`
- Existing fixture evidence is `error="http_403", status=403` at `operator-claude-plugin/tests/conftest.py:541-543`.

The plan also correctly distinguishes refused credentials, transport failure, and successful-but-unparseable responses.

### 11. `report_enrichment` delegates to pure total `outcome_for_action`

**Verdict: RESOLVED**

The revision explicitly rejects direct delegation to raising persistence logic:

- `57-02-PLAN.md:299-307` defines `outcome_for_action` as pure and total.
- `57-02-PLAN.md:359-410` removes the second mapping and routes the report through the pure function.
- This preserves `build_enrichment_report`’s never-raise contract while keeping validation in `classify_item`.

This directly addresses the mismatch between current `written_records.classify_item` and `report_enrichment._ACTION_TO_OUTCOME`.

### 12. Expanded 57-05 evidence/report work and phase gate

**Verdict: PARTIALLY RESOLVED**

Substantial Cycle 1 concerns are genuinely addressed:

- `classify_read` distinguishes absent, malformed, parseable, and another-run artifacts.
- `record_audit` persists the four previously ephemeral observations.
- The report now describes five state stores and a five-row contradiction matrix.
- `REPORT INCOMPLETE` appears at the top when evidence is incomplete.
- Multiple dispatch outcomes are accepted.
- Deployment and first-live authorization are separated into a blocking checkpoint.
- `57-05` now depends on `57-02`, `57-03`, and `57-04`.

Remaining gaps:

- `run_audit` is itself another durable input, so the report consumes six durable artifacts, not five. The audit store needs classified-read and gap handling too.
- The promised single manifest snapshot is not implementable through current `run_state.read_progress`, which loads the manifest internally at `operator-claude-plugin/scripts/run_state.py:332-365`. The plan modifies neither `run_state.py` nor its API.
- Pair-pipeline final-ingest rows can still be unjoinable.
- Task 4’s live-spend options conflict with the plan-wide statement that no task spends provider credit.
- The deploy command is not actually scoped to the ingest workflow.

### 13. 57-02 live redeploy removed and folded into 57-05

**Verdict: PARTIALLY RESOLVED**

The ordering intent is improved:

- `57-02-PLAN.md:448-459` regenerates and tests without deploying.
- `57-05-PLAN.md:536-602` places deployment behind the phase gate.

But the proposed deployment is not mechanically narrow. `scripts/deploy_n8n_workflows.py:265-269` loads every `wf_*_cloud.json`. A checkpoint described as deploying only `wf_contact_ingest_cloud.json` could update unrelated workflows.

The phase gate needs either a single-workflow selector or a pre-deploy diff that refuses unless the ingest workflow is the only changed deployment target.

## Deferral Verdicts

### 1. Crash-mid-run remainder durability

**Verdict: HONEST**

`57-03-PLAN.md:116-124` clearly states that only deliberate ceiling stops create remainder entries, while a process crash between chunks does not. It gives a real trade-off:

- Per-chunk remainder checkpointing adds a durable write on the hot path.
- Existing written-record evidence makes reconstruction possible, though not automatic.
- `57-05` must report the missing remainder as a gap.

This is a genuine scope and cost decision, not a dismissal. The phrase “reconstructable” should not be allowed to become “reconstructed”; no such recovery mechanism is planned.

### 2. Restoring `row_id` through the final pair-pipeline ingest

**Verdict: HONEST as a deferral, but incompatible with claimed AFTER-01 closure**

The rationale is explicit at `57-02-PLAN.md:124-140` and `:437-446`:

- `extraction.strip_row_id` intentionally enforces canonical CSV structure.
- Carrying the key beside the rows would require broader transport changes.
- Joining by email would persist PII in a ledger that deliberately excludes it.

Source confirms the strip at `operator-claude-plugin/scripts/extraction.py:876-892` and its use at `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:632-647`.

The deferral is honest. The requirement accounting is not: AFTER-01 requires per-record outcomes, yet `57-01-PLAN.md:800` still maps it to closure while 57-05 admits some records remain unjoinable. Mark AFTER-01 partial or restore correlation.

### 3. Instance-wide concurrent consumption

**Verdict: HONEST**

`57-01-PLAN.md:117-123` and threat `T-57-05c` at `57-01-PLAN.md:739` state:

- The control is point-in-time and local.
- Other sessions and schedulers can consume the allowance.
- No reservation or billing-quota API exists.
- The limitation is accepted and disclosed.

This is a genuine platform limitation and correctly avoids upgrading a local tally into an instance-wide guarantee.

### 4. Retention pruning under-counting spend

**Verdict: HONEST**

`57-01-PLAN.md:369-374` states the permissive direction explicitly:

- Sampled spend is a lower bound.
- Remaining headroom is an upper bound.
- Pruned executions may still have been billed.
- The fact is tagged `[documented]`, not `[observed live]`.

The caveat is also required in the final report at `57-05-PLAN.md:430-435`. This follows the project’s evidence-tag discipline.

### 5. Per-provider spend ceilings

**Verdict: NOT ACTUALLY WRITTEN in the revised execution plans**

The deferral exists in `57-CONTEXT.md`, but the revised plans do not provide an in-plan engineering rationale comparable to the crash and row-correlation deferrals. Plan 57-04 discusses unreadable provider balances, which is related but not the same as deciding why aggregate rather than provider-specific enforcement is sufficient for the first live unattended run.

Add a short explicit deferral paragraph stating:

- Aggregate provider-credit projection remains the only enforced provider ceiling.
- Per-provider ceilings need reliable per-provider balance/usage inputs.
- Apollo is structurally unreadable and ZoomInfo is probe-dependent.
- Therefore provider-specific enforcement cannot honestly be implemented in this phase.

### 6. Post-write confirmation

**Verdict: HONEST**

`57-02-PLAN.md:168-188` explicitly explains that an update/enrich ID may predate the PATCH and cannot prove write success. It correctly sends the unresolved vocabulary decision to a checkpoint instead of claiming terminal evidence exists.

The deferral becomes unsafe only if Task 1 selects option A and the phase still closes AFTER-03 as fully satisfied.

### 7. Throughput optimization

**Verdict: NOT ACTUALLY WRITTEN in the revised execution plans**

The context explains why the 82% sequential Anthropic cost is optimization rather than guardrail work, but the revised plan text does not carry that rationale as a named deferral. Because the revision expanded scope substantially, this should be stated in 57-01 or 57-05 to prevent an executor from folding optimization into already large tasks.

## Strengths

- The pre-send guard now has the correct ordering and comparison direction.
- Quiet-instance exhaustion and busy-instance page truncation are modeled separately.
- The revision no longer hides `rerequest_unanswered` outside the ceiling.
- Deliberate budget stops have their own outcome field rather than masquerading as failures.
- `failed_batch` is tested as a round-trip property over every accepted work shape.
- Split persistence occurs only after acceptance and a fresh grant.
- GRANT-06 is repeatedly enforced with recursive forbidden-value tests.
- Outcome vocabulary is centralized in a pure, total function.
- The post-write evidence conflict is escalated to an operator decision rather than silently decided.
- Missing, malformed, and contradictory audit evidence becomes visible at the top of the report.
- 57-05 now consumes the outputs of 57-02, 57-03, and 57-04 in the correct wave.
- The first live unattended run is no longer an automatic consequence of green tests.

## Concerns

### HIGH, NEW: RUN-05 checkpoint measures the old sampler

`57-01-PLAN.md:200-231` takes the account-specific measurement before Task 2 implements `listing_exhausted` and the allowance-sized page budget. The checkpoint cannot determine whether the revised sampler is usable.

### HIGH, NEW: Deployment is broader than the checkpoint says

Task 4 describes an ingest-only deployment at `57-05-PLAN.md:553-559`, but `scripts/deploy_n8n_workflows.py:265-269` loads all cloud workflows. Unrelated local/live drift could be deployed.

### HIGH, NEW: ZoomInfo before/after proof is impossible with one request

`57-04-PLAN.md:181-182` allows exactly one status request, while `:214-220` requires Lusha balances before and after the probe. One response cannot bracket itself. A second status request would also trigger the provider status chain again.

### HIGH, NEW: Live-spend checkpoint conflicts with global prohibitions

`57-05-PLAN.md:66-70` and `:637-641` say no task spends provider credit. Option A explicitly says provider credits are spent at `:581-589`, and option B authorizes an unattended credit-spending batch. It is unclear whether Task 4 merely records authorization or executes the run.

### HIGH, CARRIED: AFTER-01 remains incomplete on final ingest

The plan now honestly discloses the `strip_row_id` boundary but still maps AFTER-01 to closure. Keeping an unjoinable row in the report is safer than dropping it, but it does not supply the required per-record joined outcome.

### HIGH, NEW: Final pair-pipeline spend accounting is underspecified

The plans explain decrementing the ceiling across dispatch outcomes but do not concretely adapt the final ingest dispatch to the same `DispatchOutcome` and `projected_spend` mechanism.

### HIGH, NEW: Split scope is not necessarily resendable work

`record_domains` preserves authorization semantics, but a domain-only object is not necessarily enough to reconstruct `people`, `companies`, or row-based dispatch input.

### MEDIUM, NEW: Single manifest snapshot is not supported by the current API

The plan promises one snapshot, while `run_state.read_progress` loads internally and returns only progress. No API change is assigned.

### MEDIUM, NEW: 57-03 checkpoint ownership is undeclared

57-02 and 57-03 run in Wave 2. 57-02 owns `57-DISCUSSION-LOG.md`; 57-03 has a one-way operator checkpoint but does not declare a decision-record file. Either the checkpoint is not durably recorded or two parallel plans can edit the same undeclared artifact.

### MEDIUM, NEW: 57-04 is marked autonomous despite a live gated probe

`57-04-PLAN.md` is `autonomous: true`, yet the plan requires an explicit live gate, credentials, a backend POST, and possible ZoomInfo token-cache mutation. It should be non-autonomous or split into autonomous fixture work plus a checkpointed probe.

### MEDIUM, NEW: GRANT-06 lacks requirement-level closure ownership

The phase introduces two new persistence surfaces adjacent to authority, but the requirement map omits GRANT-06 and none of the plans updates the milestone requirement file. The code-level tests are strong; traceability is missing.

### MEDIUM, NEW: Audit-store terminology and handling are incomplete

57-05 says it joins five stores, then consumes `run_audit-<run_id>.json` as a sixth durable input. The audit artifact needs the same absent/malformed/another-run reporting discipline or an explicit reason it differs.

### LOW, NEW: Deployment artifact ownership is inaccurate

57-02 creates the generated JSON. 57-05 optionally deploys it. A deployed state is not an unconditional repository artifact, especially when Task 4 option D permits no deployment.

## Suggestions

1. Move 57-01 Task 1 after Task 2, then measure using the revised sampler and allowance-sized page budget.
2. Add a concrete adapter for charging the final ingest dispatch against the same grant ceiling and include it in the AST/caller-path test.
3. Change `split_for_allowance` to split the original canonical work specification, preserving complete `rows`, `people`, or `companies` objects as appropriate.
4. Mark AFTER-01 partial unless final-ingest correlation is restored through sidecar metadata.
5. Make 57-05 Task 4 explicitly authorization-only, or add a separate live-run task and remove the contradictory no-spend claims.
6. Add a single-workflow deployment selector or require a pre-deploy diff that refuses if any workflow other than contact ingest would change.
7. Replace the ZoomInfo before/after credit claim with either a two-request protocol or a narrower claim that the probe does not invoke enrichment endpoints.
8. Add `run_state.read_progress(..., manifest_snapshot=...)` or return the loaded snapshot so the one-snapshot report claim is implementable.
9. Make 57-04 non-autonomous for the live portion.
10. Assign each checkpoint a durable decision-record owner and serialize plans that modify the same log.
11. Include GRANT-06 in the phase requirement map and assign its closure update to 57-05.
12. Add explicit in-plan deferral rationales for per-provider ceilings and throughput optimization.

## Risk Assessment

**Overall risk: HIGH**

The revision is significantly safer than Cycle 1 and resolves most original implementation defects. The remaining risk is concentrated at the phase boundaries rather than in the core pre-send algorithm:

- RUN-05’s account-specific checkpoint currently cannot validate the revised sampler.
- AFTER-01 is still claimed as closed despite acknowledged unjoinable rows.
- The complete pair pipeline is not yet demonstrably charged against one ceiling.
- The deployment mechanism can touch more workflows than the checkpoint describes.
- The live-spend checkpoint contradicts the phase’s own prohibition.
- The provider-balance proof contains an impossible one-request before/after requirement.

Because Phase 57 gates the first unattended credit-spending batch, these are blocking plan defects. The core approach is sound, but the plans should undergo one more focused revision before execution.

---

## OpenCode Review (kimi-k3)

LANE DROPPED — no review produced. Raw lane output:

```
opencode review failed or returned empty output. stderr:

Raw response body:
OpenCode review returned no assistant text (#1936: agent ended its turn with no final message).
Diagnostic: stop reason=unknown, output tokens=0
```

Given one attempt per the cycle-2 brief and not retried. See the assurance-level note in
the cycle-2 frontmatter above.

---

## OpenCode Review (grok-4-6)

I'll verify claimed cycle-2 fixes against source, not changelog lines.
# Phase 57 Cycle 2 — Plan Revision Review

Verified against current source: `n8n_read.py:258-381`, `chunking.py:317-517`, `conftest.py:541-544`, `STATE.md:410`, `61-CONTEXT.md:57`. Plans are still unimplemented; this judges **plan text**, not landed code.

## 1. Summary

The revision is a real safety rewrite, not a changelog overlay. Cycle 1’s load-bearing defects (post-send tally, quiet-instance sampling, `failed_batch` drop, markdown-grep wiring, deploy-before-gate) are **written into task actions and tests**. GRANT-06 is intact. Residual risk is concentrated in **checkpoint ordering** (T1 measures *before* the sampling fix), the **`CEILING_UNKNOWN` double-off hole** that option A itself names, and **new coupling** (four blocking gates, remainder write inside `dispatch_plan`, audit merge). As a gate on first live spend: **MEDIUM** if option A + T2 land as specified; **HIGH** if T1 is decided on pre-fix measurements or option B unattended is chosen while sample is `unknown`.

## 2. Claimed resolutions

| Claim | Verdict | Evidence |
|---|---|---|
| Mid-run tally **pre-send** | **RESOLVED** | 57-01 T2: first statement of loop, before `build_envelope`; `would_be > execution_ceiling`; equality sends all; zero-overshoot sweep. Matches `chunking.py:373-377` hook point. Comparison direction cannot off-by-one if implemented as specified. |
| Sampling predicate both ends | **PARTIALLY RESOLVED** | Plan specifies `listing_exhausted` + `max_pages` + `sampled = truncated_by_page_cap False AND (covers_full_window OR listing_exhausted)` (`n8n_read.py:378-379` is still `covers_full_window = saw_older_than_cutoff` today). **On this quiet account, `listing_exhausted` is what makes RUN-05 reachable**, not the checkpoint. T1 still runs the **unfixed** walker first — the checkpoint can *override* closure, but it is not the mechanism that makes refusal fire here. Retention caveat is honest (`[documented]`, lower-bound spend). |
| `rerequest_unanswered` under ceiling | **RESOLVED** | 57-01 T4: `execution_ceiling` + `MergeResult.dispatch_outcome`; withdrawn grep-0 pin. |
| `failed_batch` all five shapes | **RESOLVED** | 57-03 T3: ordered key concat; per-shape round-trip. Current `chunking.py:506-516` still returns `chunks[0]` for `people`/`companies`. |
| `REASON_ALLOWANCE_SPLIT` producer | **RESOLVED** | Five-step transition; `plan_grant` writes nothing; runbook after fresh grant; disk-empty test. |
| `try/finally` + `CLOSED_UNHANDLED_ERROR` | **RESOLVED** | 57-01 T4; crash ≠ `ceiling_breach`. |
| Override authority | **RESOLVED** | raise without reason; recorded; `override=True` grep 0 in SKILLs. |
| D-53-02 → D-57-00 | **RESOLVED in plan** | Edit `STATE.md:410`, discussion log, `61-CONTEXT.md:57`. Not in repo yet. |
| Markdown-grep → AST | **RESOLVED** | 57-VALIDATION prohibitions + compile fenced python. |
| Apollo `http_403` | **RESOLVED** | `conftest.py:541-544`; 57-04 supersedes stale RESEARCH. |
| `outcome_for_action` not `classify_item` | **RESOLVED** | 57-02 T2/T3; never-raise pin. |
| 57-05 classify_read / audit / matrix / phase gate | **RESOLVED as specified** | Five-store join, GRANT-06 authority test, deploy folded from 57-02. |
| 57-02 live redeploy removed | **RESOLVED** | Explicit prohibition; deploy = 57-05 T4. |

## 3. Deferrals

1. **Crash-mid-run remainder** — **HONEST**. 57-03 objective: remainder only on deliberate stop; reconstruct from `written_records` + plan; 57-05 names the gap. Trade-off (hot-path write vs reconstructability) is written, not waved.
2. **`row_id` through pair ingest** — **HONEST**. 57-02 must_haves + T4 + 57-05 unjoinable-leg; `extraction.strip_row_id` at `extraction.py:876` / SKILL ~639. AFTER-01 join incomplete on that lane — plan says so.
3. **Instance-wide concurrent spend** — **HONEST**. T-57-05c **accept**; P-12; disclosed as local control. Real trade-off (no reservation API).
4. **Retention pruning** — **HONEST**. `retention_caveat`, `[documented]`, permissive direction named.
5. **Per-provider ceilings / post-write confirm / throughput** — **HONEST**. Unchanged `<deferred>`.

## 4. Strengths

- Pre-send tally + `CeilingStop` field matches Pitfall 5 and current loop structure (`chunking.py:373-451`).
- Quiet-instance sampling is correctly diagnosed against `n8n_read.py:358-379`.
- GRANT-06 never broken: remainder/audit observations only; authority tests.
- Phase gate (57-05 T4) separates landing from first live spend (D-61-08).
- G-4 closure table: `inconclusive` does not close.
- Wave 1 parallel (57-01 ∥ 57-04) is sound; 57-04 consumes nothing from 57-01.

## 5. Concerns

**HIGH / NEW — T1 measures the unfixed sampler.** Checkpoint is *before* T2. Quiet instance today: `covers_full_window=False`, `truncated_by_page_cap=False` (`n8n_read.py:358-364,379`). Operator may pick option C (leave RUN-05 PARTIAL) on evidence the revision already knows how to fix. **Which does the real work here:** T2’s `listing_exhausted`, **not** the checkpoint. Reorder: land T2 (or run the measurement script *as if* patched), then decide.

**HIGH / NEW (named in-plan, still open) — `CEILING_UNKNOWN` turns off both guards.** 57-01 option A cons: unknown → `execution_ceiling=None` → no preflight *and* no mid-run stop. D-57-02 forbids refusing on unknown. For unattended first spend this is the hole that makes option B of 57-05 dangerous. Not a missed fix — a residual the phase gate must treat as blocking if sample is still unusable after T2.

**MEDIUM / NEW — Remainder persist inside `dispatch_plan`.** 57-03 T3 writes `remainder_queue` on stop. Couples chunking to a sixth store; D-59-10 wrap specified. Grant-unaware preserved (`import write_grant` grep 0). Acceptable if degrade-on-fail is as specified.

**MEDIUM / NEW — Four checkpoints vs one.** Wave 2 blocked on 57-02 T1 (`written` vs `write_attempted`) *and* 57-03 T1 (auto-split). 57-05 T2 must wait for both option selections. Scope grew (57-01 3→4, 57-05 2→4) but coupling is explicit.

**MEDIUM / CARRIED — `plan.row_counts == UNKNOWN` skips tally.** 57-01 T2: list spec, single chunk, `ceiling_stop` None. Honest; still a mid-run hole for that shape.

**LOW / NEW — `record_audit` merge.** Two calls (grant-time + finally); crash between is the point. Spec is merge-not-replace; executor must not last-write-wins.

**LOW / NEW — AST vs fenced blocks.** Skills have multiple fences; test must extract the *dispatch* block or it goes green on a comment fence.

Binding constraints: **not broken** (GRANT-06, no arm in 01–04, distinct `DispatchOutcome` field, tags, no fabricated ids). 57-05 T4 deploy is the only live action and is gated.

## 6. Suggestions

1. Move 57-01 T1 **after** T2, or measure with a one-off that applies `listing_exhausted` logic to the live listing so the decision uses post-fix reachability.
2. In 57-05 T4 facts list: if post-T2 sample is still `CEILING_UNKNOWN`, **forbid option B** (unattended) in the option text, not only in cons.
3. Pin `would_be` against `write_grant.EXECUTIONS_BASIS` / `run_state.spend_against_ceiling` in one shared helper so the loop formula cannot drift.
4. AST extractor: name the fence heading or require `dispatch_plan(` in the compiled unit.

## 7. Risk Assessment

**MEDIUM** for executing the revised plans as a safety proposition.

Justification: cycle 1’s spend-after-breach and silent `people` drop are actually specified away; GRANT-06 holds; first live run is no longer an automatic consequence of green tests. Remaining HIGH items are **decision-order** and the **unknown-ceiling dual-off path**, both visible in the plans. They do not make the revision dishonest; they do mean RUN-05 on *this* quiet account is closed by **`listing_exhausted` in T2**, with T1 as an escape hatch if that still fails — not the other way around.

If T1 is taken on pre-fix data and the operator chooses option C, the phase under-closes a fix it already designed. If 57-05 option B is chosen while `execution_ceiling` is None, the phase fails its own goal.

---

## Source-Grounding Pass — Cycle 2 (authority: `grep`)

Run after the reviews, per the cycle-2 brief. Method: enumerate every symbol the five revised
plans cite, subtract each plan's own "Artifacts this phase produces" section, resolve the
remainder with ripgrep/Read. Severity under `grep`: MISSING → `needs-acknowledgement` (NOT a
hard block — hard blocks require `lsp`/`scip`); AMBIGUOUS → MEDIUM; UNCHECKABLE → INFO.

### Step 2 — Exclusion set (declared "Artifacts this phase produces", all five plans read)

All five plans now carry a populated section (cycle 1 had only 57-01 populated). Excluded from
resolution because absence is expected:

- **57-01:** `write_grant.allowance_headroom`, `ceiling_verdict`, `CEILING_OK`/`CEILING_OVER`/
  `CEILING_UNKNOWN`, `record_dispatch_outcome`, `_CEILING_CONSTRAINT`, `_ALLOWANCE_SAMPLED`,
  `plan_grant`'s `override`/`override_reason`, `envelope`'s `headroom` param and new figures,
  `n8n_read.executions_in_window`'s `max_pages`/`listing_exhausted`, `chunking.CeilingStop`,
  `DispatchOutcome.ceiling_stop`, `dispatch_plan`'s `execution_ceiling`,
  `chunking.projected_spend`, `preingest.rerequest_unanswered`'s `execution_ceiling`,
  `preingest.MergeResult.dispatch_outcome`, the `D-57-00` records.
  — **and `write_grant.CLOSED_UNHANDLED_ERROR`, which is listed here but ALREADY EXISTS. See
  Step 3, finding SG-1.**
- **57-02:** `written_records.GATED`/`HELD`/`FAILED`/`NO_ACTION`/`WRITTEN_ID_UNKNOWN`/
  (`WRITE_ATTEMPTED`), `ALL_OUTCOMES`, `ACTION_TO_OUTCOME`, `outcome_for_action`, the
  `row_id`/`association` entry fields, `row_id` on `BUILD_INGEST_RESPONSE`,
  `tests/n8n/ingestResponseRowId.test.mjs`.
- **57-03:** `remainder_queue.py` and its whole surface (`RemainderQueueError`,
  `remainder_path`, `build_entry`, `save`, `load`, `REMAINDER_QUEUE_GLOB`,
  `REASON_CEILING_BREACH`, `REASON_ALLOWANCE_SPLIT`, `ALL_REASONS`),
  `write_grant.split_for_allowance`, the `split_offer` key.
- **57-04:** `scripts/prove_zoominfo_balance.py`, `ALLOW_ZOOMINFO_BALANCE_PROBE`,
  `test_prove_zoominfo_balance.py`, `57-ZOOMINFO-BALANCE-VERDICT.json`,
  `backend_status_zoominfo_provider_error` fixture.
- **57-05:** `run_report.py`, `build_run_report`, `record_audit`, `load_audit`,
  `run_audit-<run_id>.json`, `written_records.classify_read`, `run_manifest.classify_read`,
  `test_run_report.py`.

### Step 3 — Resolution of the remaining cited symbols

#### VERIFIED (existing code the plans cite)

| Plan citation | Verdict | Evidence |
|---|---|---|
| `n8n_read.executions_in_window` at 258-382, `covers_full_window = saw_older_than_cutoff` at `:378` | VERIFIED | def at `n8n_read.py:258`; `"covers_full_window": saw_older_than_cutoff` at `:379` (one line off the cited 378) |
| `MAX_EXECUTION_PAGES` / `EXECUTIONS_WINDOW_PAGE_LIMIT` at `n8n_read.py:69,73`; 1,000-execution cap | VERIFIED | `:69` = 250, `:73` = 4; the cap is stated in the source comment at `:71-72` |
| quiet-instance exit "no next cursor" at `n8n_read.py:358-360` | VERIFIED | `next_cursor = body.get("nextCursor")` `:358`; `if saw_older_than_cutoff or not next_cursor: break` `:359` |
| `truncated_by_page_cap` only set in the `for/else` when not broken | VERIFIED | `:363-364` `if not saw_older_than_cutoff: truncated_by_page_cap = True` |
| `EXECUTION_ALLOWANCE_KEY` at `n8n_read.py:62` | VERIFIED | `:62` |
| `config_gate.load_config` at `config_gate.py:131` | VERIFIED | `:131` |
| its callers `cost_guard.py:323`, `chunking.py:531`, `dispatch.py:131` | VERIFIED | all three exact |
| `write_grant` D-53-02 text `_DISCLOSURE_NOT_CONSTRAINT`, `_ALLOWANCE_GAP` at 111-155 | VERIFIED | `_ALLOWANCE_GAP` `:143`, `_DISCLOSURE_NOT_CONSTRAINT` `:150`, `EXECUTIONS_BASIS` `:139` |
| hardcoded `remaining_allowance_sampled` false literal at `write_grant.py:261` | VERIFIED | `:261` `"remaining_allowance_sampled": False,` |
| `_headroom()` tri-state renderer at 167-174 | VERIFIED | def at `:167` |
| `envelope()` at 183-278 / `_envelope_block()` | VERIFIED | `envelope` `:183`, `_envelope_block` `:281` |
| `plan_grant` at 411-520 | VERIFIED | def at `:411` |
| `record_send_outcome` at 899-949 | VERIFIED | def at `:899` |
| the close reasons at 660-705 | VERIFIED | `CLOSED_BATCH_COMPLETE` `:666` … `CLOSED_UNHANDLED_ERROR` `:670`; `GRANT_04_REASONS` `:672-675` |
| `_refusal` / `_normalise` / `PROPOSAL_KIND` / `REFUSED` | VERIFIED | `:103`, `:107`, `:57`, `:61` |
| grant scope id-vs-domain handling at `write_grant.py:607-620`, `:645-656` | VERIFIED | both ranges are inside the `covers`/scope block ending `:658` |
| `chunking.ChunkResult` / `DispatchOutcome` at 87-155 | VERIFIED | `:88`, `:112` |
| `chunking.dispatch_plan` at 317-451 | VERIFIED | def at `:317` |
| `chunking.failed_batch` at 494-517, returns `chunks[0]` for `people`/`companies` | VERIFIED | def `:494`; `list` passthrough `:502`; `rows` branch `:505`; `record_ids` fallthrough `:513-518` — a `people`/`companies` spec finds no `record_ids` and returns `dict(chunks[0])` at `:517` |
| `chunk_ceiling` at 157-180, `plan_chunks` at 183-277 with four shapes | VERIFIED | `:157`, `:183`; rows `:215`, people `:232`, companies `:252`, record_ids `:270` |
| `chunking.UNKNOWN` | VERIFIED | `:60` |
| `n8n_cadence.check_budget_floor` at 452-491 | VERIFIED | def at `:452` |
| `run_state.SPEND_BASIS`, `spend_against_ceiling`, `classify_read`, `read_progress` | VERIFIED | `:175`, `:368`, `:265`, `:332` |
| `run_state.read_progress` loads the manifest internally (`run_state.py:332-365`) | VERIFIED | def at `:332`, body inside the cited range |
| `run_state` `ABSENT`/`PARSEABLE`/`ANOMALOUS` at 152-158 | VERIFIED | `:152`, `:153`, `:154` — note `ANOTHER_RUN` is **not** defined in `run_state.py` |
| `held_queue.classify_read` at `held_queue.py:260` | VERIFIED | `:260` |
| `held_queue` `ABSENT`/`PARSEABLE`/`ANOMALOUS`/`ANOTHER_RUN`, `queue_path`, `load`, `fingerprint`, `ROW_FIELD_ALLOWLIST` | VERIFIED | `:107-110`, `:147`, `:245`, `:154`, `:98` |
| `run_manifest.load_scoped` at 242-274, `run_manifest_path` at 151-160 | VERIFIED | `:242`, `:151`; no `classify_read` present (correctly, it is this phase's work) |
| `durable_paths._atomic_write_0600` at 57-77/57-81, `resolve_state_path` | VERIFIED | `:57`, `:234` |
| `written_records`: `classify_item` 131-192, forbidden markers 100-115, `WRITE_ACTIONS` `:96`, `load` 291-323, `_entries_from_document` 207-219, `append_chunk` 241-288, `written_records_path` 118-128 | VERIFIED | `:131`, `:100`, `:96`, `:291`, `:207`, `:241`, `:118`; `WRITTEN_RECORDS_GLOB` `:81`; `WRITTEN`/`CREATED_ID_UNKNOWN`/`NOT_WRITTEN` `:89-91` |
| `report_enrichment._ACTION_TO_OUTCOME` (lines 1-80), `SUCCESS_OUTCOMES`, `_OUTCOME_REASON`, `_outcome_for_row` 121-185, `build_sync_report`/`build_enrichment_report` 245-337, never-raise contract 285-304 | VERIFIED | `:38`, `:50`, `:56`, `:122` (`_ACTION_TO_OUTCOME.get(..., "unknown")` — the 4-of-10 gap), all within the cited ranges |
| `preingest.MergeResult` at 520-545; `rerequest_unanswered` at 662-745 with a single internal `dispatch_plan` | VERIFIED | `:525`, `:662`; the "only ever handed on to `dispatch_plan`" invariant comment at `:708` |
| `scheduled_arm.py:234` calls `dispatch_plan` | VERIFIED | `:234` |
| `extraction.strip_row_id` at 876-895 | VERIFIED | def at `:876` |
| `enrich-before-ingest/SKILL.md:639` strips `row_id` before `write_dispatch_csv` | VERIFIED | `strip_row_id(sendable_rows)` at `:639`, `write_dispatch_csv` at `:640`, STRUCT-01 rationale `:643-645` |
| `build_cloud_workflows.BUILD_INGEST_RESPONSE` at 465-520 | VERIFIED | `:471` |
| decision nodes emit `row_id: row.row_id ?? null` at `:1699`/`:1705` and `:3439` | VERIFIED | `:1705` and `:3439` exactly |
| `ENRICH_STATUS_BUILD_RESPONSE` error labelling at 6340-6370 / 6354-6362 | VERIFIED | node at `:6327`; `error = status ? ("http_" + status) : "provider_error"` `:6357`; `unrecognized_response_shape` `:6360` |
| `conftest.py` `_balance` helper at `:498` | VERIFIED | `:498` |
| `conftest.py` `no_network` `:588`, `no_durable_writes` `:608`, `stub_module_transport_factory` `:260` | VERIFIED | all exact |
| `cost_guard` `_all_unreadable`/`fetch_balances`/`compare`/`_verdict` (221-320) | VERIFIED | `:221`, `:225`, `:274`, `:316` |
| `confidence.ALL_HOLD_CODES`, `confidence.assess` | VERIFIED | `:74`, `:109` |
| `enrichment.build_envelope` | VERIFIED | `enrichment.py:237` |
| `n8n_arming.DISARMED` / `DISARM_FAILED` | VERIFIED | `:188`, `:189` |
| `backend_status.py:40-54` issues the status POST | VERIFIED | `fetch_backend_status(config, transport=requests.post)` at `:40` |
| `deploy_n8n_workflows.py::_instance_ok()` | VERIFIED | `:238` |
| `provider_registry.py:26-33` Apollo non-master-key 403 comment | VERIFIED | the `apollo` credit block, `# 403 w/o master key -> null` |
| `n8n/code/providerSelection.js:76-106` `extractCredits` + live-verified comment | VERIFIED | `:76` |
| `tests/test_conftest_credential_guard.py` `RUN_LIVE_PARITY` | VERIFIED | `:6` |
| `scripts/prove_async_recovery.py`, `scripts/prove_scale_up_runtime.py` (templates) | VERIFIED | both exist |
| `test_write_grant.py:1455-1463` pins no `grant` parameter on `dispatch_plan` | VERIFIED | `test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against`, ~`:1456-1466` |
| `test_a_revocation_midway_does_not_stop_a_running_dispatch`'s 3-chunk idiom | VERIFIED | `test_write_grant.py:1371` |
| `test_retry_reuses_dispatch.py::_EXPECTED_SEND_SHAPED` | VERIFIED | present in that file |
| `written_records` / `held_queue` / `run_state` each carrying their own `_FORBIDDEN_NAME_MARKERS` (anti-DRY convention) | VERIFIED | `written_records.py:100`; the convention holds |

#### MISSING / factually wrong claims about existing code (`needs-acknowledgement`)

| Claim | Verdict | Evidence |
|---|---|---|
| **SG-1.** `57-01-PLAN.md:680-682` — "Add `CLOSED_UNHANDLED_ERROR` to `write_grant`'s close-reason set **beside the existing five**"; and `57-01-PLAN.md:765` lists `write_grant.CLOSED_UNHANDLED_ERROR` under "Artifacts this phase produces … these symbols do not exist yet" (also echoed in 57-03's and 57-05's "created elsewhere" lists) | **MISSING → needs-acknowledgement** | The constant **already exists**: `write_grant.py:670` `CLOSED_UNHANDLED_ERROR = "unhandled_error"`, already a member of `GRANT_04_REASONS` at `:672-675`, already asserted at `test_write_grant.py:1278`. It **IS** one of "the existing five" the same plan cites at 660-705. Consequences: (a) the plan's own acceptance criterion `assert w.CLOSED_UNHANDLED_ERROR` (`57-01-PLAN.md:707`) passes **today, before any work** — a criterion that cannot fail; (b) the source comment at `write_grant.py:679-681` says "GRANT_04_REASONS stays exactly five and is pinned by name", so an executor following the action literally could try to add a sixth against an explicit in-source guard; (c) listing it in the exclusion set tells a drift check to skip a symbol that exists. The *mechanism* cycle 1's H8 asked for (the `try`/`finally` closing the grant with that reason) is genuinely new and correctly specified — only the "add the constant" framing is wrong. |
| **SG-2.** `57-01-PLAN.md:86-88` — "`record_send_outcome(` has ZERO production callers — **the only invocation outside `write_grant.py` itself is `test_write_grant.py:1507`**" (repeated at `57-VALIDATION.md:97`, "today only the direct-call unit test exists (`test_write_grant.py:1507`)") | **half VERIFIED, half MISSING → needs-acknowledgement** | The load-bearing half holds: `grep -rn "record_send_outcome" --include=*.py` finds **no non-test caller**. The specific half does not: there are **ten** test invocations across **two** files — `test_write_grant.py:1474, 1489, 1502, 1512` and `test_write_grant_guardrails.py:251, 256, 274, 293, 317, 396` — and **none at line 1507** (nearest are `:1502` and `:1512`). This matters because `test_write_grant_guardrails.py` is in no plan's `files_modified`. |

#### AMBIGUOUS (MEDIUM)

| Claim | Verdict | Evidence |
|---|---|---|
| **SG-3.** `57-01-PLAN.md:413-419` — the frozen-call-order change "Existing scripted-transport tests that count or sequence calls WILL fail … re-sequence them", with only `test_write_grant.py` in `files_modified` | **AMBIGUOUS → MEDIUM (and the basis of HIGH-4 below)** | `plan_grant` is called from **five** test files: `test_write_grant.py` (52 `_plan_reads()` uses) and `test_chunking.py` — both listed — plus `test_write_grant_surface.py` (**13** `_plan_reads()` uses; its helper docstring at `:67-69` literally reads "`plan_grant`'s frozen call order: one workflow-list read per lane … then one workflow read per lane"), `test_write_grant_guardrails.py` (ordered 2-element scripts, e.g. `:112`), and `test_unattended_pair_composition.py` (`:220` + scripted transport `:237`). The last three are in **no** plan's `files_modified`. |
| **SG-4.** `57-05-PLAN.md:268` cites "`run_state.py` lines 100-135 and 308-378 — the `Progress` dataclass … and `SPEND_BASIS`" | AMBIGUOUS → MEDIUM (citation drift, harmless) | `Progress` `:309` ✓ and `read_progress` `:332` ✓ and `spend_against_ceiling` `:368` ✓ are all inside 308-378, but `SPEND_BASIS` is at `:175`, inside neither cited range. |
| **SG-5.** `57-04-PLAN.md:24`, `:61`, `:285` cite `conftest.py:541` (`error="http_403"`) and `:543` (health `reason="http_403"`) | AMBIGUOUS → MEDIUM (off by one, claim itself correct) | The values are real and the cycle-1 correction is right, but they sit at `conftest.py:542` and `:544`, not `:541`/`:543`. |
| **SG-6.** `57-05-PLAN.md:36` — "`run_state.classify_read` (`run_state.py:265`) already exist[s]" and the four words `ABSENT`/`PARSEABLE`/`ANOMALOUS`/`ANOTHER_RUN` are to be mirrored from it | AMBIGUOUS → MEDIUM | `run_state.classify_read` exists at `:265` ✓, but `run_state.py` defines only **three** of the four constants (`:152-154`); `ANOTHER_RUN` exists in `held_queue.py:110` only. 57-05 Task 1's behaviour spec requires all four words from both new `classify_read`s, so the executor must take the fourth from `held_queue`, and `run_state` is not the template it is named as for that word. The plan's "define them alongside where it does not" clause covers this, but the two named templates are not interchangeable. |

### Step 5 — Verification coverage

Not resolved by `grep`, with the reason. A clean grounding pass does not mean these were checked.

**UNCHECKABLE under `grep` authority (INFO) — every *signature* claim:**

- Keyword-only-ness and arity of every new parameter: `dispatch_plan(..., execution_ceiling=)`,
  `executions_in_window(..., max_pages=)`, `plan_grant(..., override=, override_reason=)`,
  `envelope(..., headroom=)`, `rerequest_unanswered(..., execution_ceiling=)`,
  `record_dispatch_outcome(..., reason=)`, `build_run_report(..., outcomes=)`,
  `record_audit(...)`, `split_for_allowance(...)`. (The plans propose `inspect.signature`
  assertions precisely because grep cannot do this.)
- `chunking.CeilingStop`'s field list and `frozen=True` — the dataclass does not exist yet.
- `written_records.classify_item`'s returned key set; `outcome_for_action`'s totality
  (never-raises) — grep sees a `def`, not a return shape or an exception profile.
- `remainder_queue.build_entry`'s recursive forbidden scan reaching a marker nested inside a
  list-of-dicts — a behavioural property, not a text one.
- Every "X calls Y" / "no production caller reaches Z" **reachability** claim beyond the one
  literal-name grep in SG-2. Call-graph analysis needs an index, not grep.
- Whether `n8n_read.executions_in_window`'s proposed `listing_exhausted` is *correct* for a
  failed-later-page walk — a control-flow property of code not yet written.
- Whether `run_state.read_progress` can be made to hand back its internal manifest snapshot
  without an API change (gpt-5-6-sol's MEDIUM) — the *current* internal load is VERIFIED at
  `:332-365`; whether the plan's "pass that same loaded manifest into the row-verdict step" is
  achievable without editing `run_state.py` (which is in **no** plan's `files_modified`) is a
  design question grep cannot settle.

**Skipped deliberately (INFO):**

- Everything in the Step 2 exclusion set — created by this phase, so absence is expected.
- Bare dictionary keys and string literals used as data: `row_id`, `run_id`, `action`,
  `outcome`, `association`, `reason`, `spec`, `entries`, `records`, and the ten backend action
  words (`create`, `update`, `enrich`, `write_blocked`, `review`, `needs_match_review`,
  `research_failed`, `recompute_refused`, `skip`, `proposed`). Grep cannot distinguish a key
  from a coincidental word. (The ten-action set itself is partly checkable — `:1705`/`:3439`
  confirm the decision nodes exist — but the completeness of the set is exactly what 57-02
  Task 2's builder-derived test is for, and that test does not exist yet.)
- n8n node names as graph positions (`Build Ingest Response`, `Decide Action`,
  `Build Response`, `Status Credit Request`, `ZoomInfo Usage`) — they resolve as string
  constants in `build_cloud_workflows.py` (confirmed) but node-graph wiring is not
  grep-checkable.
- HubSpot / provider API field names external to this repo (`hs_object_id`, `contact_id`,
  `company_id`, `credits.remaining`, `nextCursor`).
- Line-range citations were spot-checked at their anchors (the `def`/constant), not
  exhaustively range-by-range.

**Totals:** ~55 file paths and code symbols VERIFIED, 2 factual claims about existing code
MISSING (`needs-acknowledgement`), 4 AMBIGUOUS (MEDIUM), ~10 signature/reachability classes
UNCHECKABLE (INFO), plus the declared five-plan exclusion set. **Zero hard blocks** — hard
blocks require `lsp`/`scip` authority, which this project does not have.

---

## Cycle-2 Unresolved Findings Register

Counted against the **current plan text** (commit `7959fd6`), not by grepping cycle 1's audit
trail. A cycle-1 HIGH the revision genuinely closed is excluded as FULLY RESOLVED; a cycle-1
finding the plans explicitly deferred with written rationale is treated as incorporated.

**All ten cycle-1 HIGHs were checked and are excluded as FULLY RESOLVED**, each with a
mechanism now present in plan text and verified against source by at least one lane: pre-send
tally (H2), sampling predicate (H1 — mechanism resolved; its *checkpoint ordering* is a new
finding, not the old one), `rerequest_unanswered` ceiling bypass (H3), `failed_batch` shape loss
(H4), `REASON_ALLOWANCE_SPLIT` producer (H5), `written` provability escalated to a checkpoint
(H6), `row_id` pair-pipeline gap disclosed (H7 — the *deferral* is honest; the requirement
accounting is a carried finding), `try/finally` closure (H8), D-53-02 supersession recorded
(H9), five-store contradiction handling (the 57-05 join HIGH).

### HIGH — unresolved (9)

| # | Status | Source | Finding | Plan change still needed |
|---|---|---|---|---|
| H-1 | NEW | both lanes | **57-01 Task 1 measures the pre-fix sampler.** The checkpoint is ordered before Task 2 and its command (`57-01-PLAN.md:210-218`) drives today's `executions_in_window`, which lacks `listing_exhausted`/`max_pages`. On this quiet account that returns the unusable state Task 2 exists to remove, so the checkpoint cannot establish whether the *revised* sampler works here. | Move Task 1 after Task 2, or take the measurement with the `listing_exhausted` logic applied, then decide. |
| H-2 | NEW | gpt-5-6-sol (grep-confirmed) | **The deploy is broader than the checkpoint says.** 57-05 Task 4 describes deploying the regenerated ingest workflow; `deploy_n8n_workflows.py:264-269` globs **every** `wf_*_cloud.json` and the script has no argparse, `--only` or per-workflow selector anywhere. Unrelated local/live drift on the other four cloud workflows would deploy with it. | Add a single-workflow selector, or a pre-deploy diff that refuses unless `wf_contact_ingest_cloud.json` is the only changed target. |
| H-3 | NEW | gpt-5-6-sol | **The ZoomInfo before/after proof is impossible as specified.** `57-04-PLAN.md` `<behavior>` requires "exactly ONE status request"; `<action>` requires the Lusha `credits.remaining` figure "BEFORE and AFTER this run". One response cannot bracket itself, and a second status request re-runs the whole provider chain. | Either a two-request protocol (and say so in `<behavior>`), or narrow the claim to "the probe invokes no enrichment endpoint". |
| H-4 | NEW | gpt-5-6-sol | **57-05's own prohibition contradicts its Task 4 options.** `57-05-PLAN.md:66` and `:637-641` state no task in the plan may spend a provider credit; option A's cons say "Provider credits are spent" and option B authorises an unattended credit-spending batch. It is unresolved whether Task 4 *records* an authorisation or *executes* the run — on the phase whose binding constraint is that nothing in it spends a credit. | Make Task 4 authorisation-only in its own words, or split the live run into a separate task and drop the blanket no-spend claim. |
| H-5 | CARRIED | gpt-5-6-sol | **AFTER-01 is still mapped to closure while the plans admit an unjoinable population.** 57-01's requirement-coverage table (`:800`) closes AFTER-01 via 57-05; 57-02 and 57-05 both correctly disclose that the pair pipeline's final ingest leg returns `row_id: null`. The deferral rationale is honest and written; the coverage row contradicts it. | Mark AFTER-01 PARTIAL in the coverage table, or restore correlation via sidecar metadata. |
| H-6 | NEW | grok-4-6 | **`CEILING_UNKNOWN` switches OFF both guards.** An unsampleable allowance yields verdict `unknown` → no preflight refusal (D-57-02) *and* `execution_ceiling=None` → no mid-run tally. 57-01 option A names this in its `<cons>`, which is disclosure, not mitigation. 57-05 option B would authorise an unattended run in exactly that state. | Forbid 57-05 option B in the option text (not only the cons) when the post-Task-2 sample is still `CEILING_UNKNOWN`. |
| H-7 | NEW | gpt-5-6-sol (sharpened by grounding) | **The pair pipeline's final ingest leg cannot be charged against the grant ceiling.** 57-05 Task 3 says the lane "collects the match pass, the enrich pass, `rerequest_unanswered`'s `result.dispatch_outcome` and **the final ingest dispatch**, and passes all of them". But `enrich-before-ingest/SKILL.md:653` delegates that leg to `contact-upload/SKILL.md`'s steps "by heading, unmodified", and `contact-upload/SKILL.md` is in **no** plan's `files_modified`. That leg produces no `chunking.DispatchOutcome`, so `chunking.projected_spend` cannot charge it and `outcomes=` cannot receive it. | Name the final-ingest adapter and show how its spend is charged, or drop it from the `outcomes` claim and name it as an uncharged leg. |
| H-8 | NEW | gpt-5-6-sol | **`split_for_allowance` splits grant scope, not resendable work.** It is specified over `record_ids`/`record_domains` (`57-03-PLAN.md:383-400`), but `plan_chunks` accepts `rows`, `people`, `companies`, `record_ids` and `list` (`chunking.py:206-277`) and has no `record_domains` work shape. A domain-only spec cannot reconstruct a `people`/`companies`/row batch. | Split the original canonical work specification, preserving complete `rows`/`people`/`companies` objects. |
| H-9 | NEW | grounding pass (SG-3) | **Three test files pinning `plan_grant`'s frozen call order are in no plan's `files_modified`.** 57-01 Task 2 inserts a new executions-list GET into that order and acknowledges "scripted-transport tests … WILL fail", but lists only `test_write_grant.py`. Also affected: `test_write_grant_surface.py` (13 `_plan_reads()` uses; its helper docstring at `:67-69` literally encodes the frozen order), `test_write_grant_guardrails.py` (ordered 2-element scripts, e.g. `:112`), `test_unattended_pair_composition.py` (`:220` + scripted transport `:237`). Under GSD, editing a file outside `files_modified` is a deviation. | Add the three files to 57-01's `files_modified` and name the re-sequencing as expected work. |

### Actionable non-HIGH — unresolved (11)

| # | Sev | Source | Finding | Plan change still needed |
|---|---|---|---|---|
| M-1 | MEDIUM | gpt-5-6-sol (grep-confirmed) | 57-05's `key_links` promises ONE manifest snapshot shared between `read_progress` and the row-verdict step, but `run_state.read_progress` loads the manifest internally (`run_state.py:332-365`) and returns only a `Progress`. **`run_state.py` is in no plan's `files_modified`** (0 hits in all three blocks), so the promise is unimplementable and degrades to the double-load the plan itself calls a risk. | Add a `manifest_snapshot` return/param to `read_progress` and put `run_state.py` in `files_modified`, or withdraw the one-snapshot claim. |
| M-2 | MEDIUM | gpt-5-6-sol | 57-03's one-way checkpoint declares no decision-record owner. 57-02 owns `57-DISCUSSION-LOG.md` and both run in wave 2 — so either the ruling is not durably recorded, or two parallel plans edit the same undeclared file. | Assign each checkpoint a durable decision-record owner and serialise plans sharing one log. |
| M-3 | MEDIUM | gpt-5-6-sol | `57-04-PLAN.md:12` is `autonomous: true`, yet Task 1 requires a live gate, credentials, a backend POST and possible ZoomInfo token-cache mutation on the instance. | Make it non-autonomous, or split autonomous fixture work (Task 2) from a checkpointed live probe (Task 1). |
| M-4 | MEDIUM | gpt-5-6-sol | 57-05 says it joins FIVE stores, then consumes `run_audit-<run_id>.json` as a sixth durable input with no `classify_read` and no `gaps` handling of its own. | Give the audit store the same absent/malformed/another-run discipline, or state why it differs. |
| M-5 | MEDIUM | gpt-5-6-sol (grep-confirmed) | GRANT-06 is absent from 57-01's requirement-coverage table (rows are RUN-05/AFTER-01/AFTER-03/G-4 only); the phase adds two persistence surfaces adjacent to authority. Code-level tests are strong; traceability is missing. | Add a GRANT-06 row and assign its closure. |
| M-6 | MEDIUM | gpt-5-6-sol (grep-confirmed) | The per-provider-spend-ceiling deferral has **no in-plan rationale**: `grep` for `per-provider`/`throughput` across all five plans returns one unrelated hit (`57-04-PLAN.md:312`, "per-provider policy switch"). It lives only in `57-CONTEXT.md`'s `<deferred>`. Same for throughput optimisation. Given the revision grew scope substantially, an executor could fold either into an already-large task. | Add a short named deferral paragraph to 57-01 or 57-05 stating why aggregate-only enforcement is sufficient for the first live run. |
| M-7 | MEDIUM | grounding (SG-1) | **`write_grant.CLOSED_UNHANDLED_ERROR` already exists** at `write_grant.py:670`, is already in `GRANT_04_REASONS` (`:672-675`) and is already asserted at `test_write_grant.py:1278`. 57-01 Task 4 says to "add" it "beside the existing five" — it *is* one of those five; `57-01-PLAN.md:765` lists it as a symbol that "does not exist yet"; and the acceptance criterion `assert w.CLOSED_UNHANDLED_ERROR` passes today, before any work. The source comment at `:679-681` says "GRANT_04_REASONS stays exactly five and is pinned by name", so a literal reading of the action runs into an in-source guard. The `try`/`finally` *mechanism* is genuinely new and correctly specified. | Reword to "wire the existing `CLOSED_UNHANDLED_ERROR` through `record_dispatch_outcome`'s `reason=` override", remove it from the exclusion set, and replace the vacuous criterion with one that can fail. |
| M-8 | MEDIUM | grounding (SG-2) | `57-01-PLAN.md:86-88` and `57-VALIDATION.md:97` claim "the only invocation outside `write_grant.py` itself is `test_write_grant.py:1507`". The load-bearing half (zero production callers) holds; the specific half does not — there are **ten** invocations across **two** files (`test_write_grant.py:1474,1489,1502,1512` and `test_write_grant_guardrails.py:251,256,274,293,317,396`) and none at line 1507. | Correct the claim; it compounds H-9 by understating what a `record_send_outcome` contract change touches. |
| M-9 | MEDIUM | grounding (SG-6) | 57-05 Task 1 names `run_state.classify_read` as a template for all four words, but `run_state.py` defines only three (`:152-154`); `ANOTHER_RUN` exists only in `held_queue.py:110`. The plan's "define them alongside where it does not" clause covers it, but the two named templates are not interchangeable for that word. | Name `held_queue` as the template for `ANOTHER_RUN`. |
| M-10 | LOW | grounding (SG-4/SG-5) | Citation drift in `read_first` anchors: `conftest.py:541`/`:543` are actually `:542`/`:544` (the `http_403` claim itself is correct); `57-05-PLAN.md:268` cites `SPEND_BASIS` inside ranges 100-135/308-378 but it is at `run_state.py:175`. | Correct the line anchors an executor is told to read. |
| M-11 | LOW | grok-4-6 | `record_audit`'s two calls (grant-time and `finally`) must merge, not last-write-wins — a crash between them is the entire reason the record exists. Specified as merge in the action; not pinned by an acceptance criterion. | Add an acceptance criterion asserting the second call preserves the first call's keys. |

### Not counted (incorporated or resolved)

- **AST extractor targeting the right fence** (grok LOW) — 57-01 Task 4's criterion already
  asserts `dispatch_plan(..., execution_ceiling=)` on the parsed tree, so a comment fence fails it.
- **Remainder persistence inside `dispatch_plan`** (grok MEDIUM) — grok's own "acceptable if
  degrade-on-fail is as specified" condition is met by 57-03 Task 3's explicit D-59-10 wrap.
- **`plan.row_counts == UNKNOWN` skips the tally** (grok MEDIUM/CARRIED) — stated in
  `57-01-PLAN.md:478-481` with the reason (a backend-resolved list spec is a single chunk by
  construction, so there is nothing to stop mid-run). Disclosed deferral, incorporated.
- **The "never left open by a crash path" overclaim** (gpt-5) — a wording tightening on
  `57-01-PLAN.md:36`; folded into H-4/M-7's neighbourhood rather than counted separately.
- **Deployment artifact ownership** (gpt-5 LOW) — 57-05's artifact list already conditions the
  deploy on the Task 4 checkpoint, including option D (no deploy).

**CYCLE_SUMMARY: current_high=9 current_actionable=11**

---

# Cross-AI Plan Review — Phase 57 — CYCLE 3 (review of the cycle-2 revision)

```yaml
cycle: 3
phase: 57
reviewers_invoked: [gpt-5-6-sol, kimi-k3, grok-4-6]
reviewers_producing_a_review: [gpt-5-6-sol, grok-4-6]
lanes_completed: 2 of 3
reviewed_at: 2026-08-31T15:10:00+10:00
revision_under_review: 0cb40e7 (plans as of 9b89d7f + 2828061)
plans_reviewed:
  - 57-01-PLAN.md
  - 57-02-PLAN.md
  - 57-03-PLAN.md
  - 57-04-PLAN.md
  - 57-05-PLAN.md
source_grounding: run (authority `grep` / direct file reads)
requirements_substituted: .planning/milestones/v1.1-REQUIREMENTS.md
```

> Note: gpt-5-6-sol, kimi-k3 and grok-4-6 all share the `opencode` adapter; their consensus is
> cross-model, not cross-tool.

> **Assurance level: 2 of 3 lanes — the same panel as cycle 2, so cross-cycle comparison is
> valid this time.** `kimi-k3` dropped for the THIRD consecutive time. Cycle 1: `[spawn error:
> ETIMEDOUT]` at the lane's 900s floor, twice. Cycle 2: empty output after 103s. Cycle 3:
> `[spawn error: ETIMEDOUT]` again, at ~900s, after emitting five lines of progress narration
> and no review. One of those lines carried a usable grounded fragment, which is recorded as
> L-4 below; everything else it said was verification chatter. It was given one attempt and not
> retried, per the established pattern.

> **Requirements context, again substituted by hand.** The stock review workflow stages the root
> `.planning/REQUIREMENTS.md`, which is v1.0's and contains ZERO occurrences of RUN-05,
> AFTER-01, AFTER-03 or G-4. `.planning/milestones/v1.1-REQUIREMENTS.md` was substituted before
> any lane was invoked, as in both prior cycles.

## Cycle-3 Consensus Summary

**The cycle-2 revision worked.** Both producing lanes independently walked the nine cycle-2 HIGHs
and found them addressed in the current plan text, each citing source. gpt-5-6-sol moved from
"not safe to execute as written" (cycle 2, HIGH, ten blocking revisions) to MEDIUM with three
named corrections; grok-4-6 returned LOW and explicitly closed with "do not manufacture more
HIGHs". Neither lane re-raised a single cycle-2 finding as still-open, and neither challenged any
of the four disclosed deliberate partials (AFTER-01's unjoinable ingest leg, RUN-05's
monthly-allowance blind spot, the per-provider/throughput deferral, the no-armed-spend rule).

**Two NEW HIGHs were found, both by gpt-5-6-sol, both confirmed by the orchestrator in source,
and both introduced BY the cycle-2 revision itself** — they are the cost of the two largest
cycle-2 fixes (H-8's two-product split, and 57-05's contradiction matrix), not survivals from
earlier cycles. Neither is a safety regression on the live system; both are specification defects
that would surface as a wrong authorisation scope or an unimplementable test at execution time.

The lanes DIVERGE on severity, not on facts: grok examined `split_for_allowance`'s two-product
shape and called it a strength without testing the ordering invariant, and did not examine the
contradiction matrix's held-queue row at all. gpt-5-6-sol's two findings are `file:line`-grounded
and were independently verified; per the review contract they carry, and grok's LOW is recorded
as the divergent view rather than as an offsetting vote.

### Agreed Strengths (both lanes)

- **Pre-send, not post-send.** Both lanes confirmed the stop now precedes `enrichment.build_envelope`
  and the transport call (`chunking.py:373-383`), closing cycle-2's one-chunk overshoot.
- **All four dispatch paths are in.** `preingest.rerequest_unanswered`'s internal `dispatch_plan`
  (`preingest.py:703-713`, outcome discarded at `:731-741`) and the single-shot
  `dispatch.dispatch` legs (`enrich-before-ingest/SKILL.md:610`, `contact-upload/SKILL.md:309`)
  are both accounted for, the latter through `single_dispatch_outcome` — one spend vocabulary.
- **The sampling predicate is fixed at both ends.** `listing_exhausted` separates exhaustion from
  coverage (`n8n_read.py:355-380`, `covers_full_window = saw_older_than_cutoff` at `:378`), and
  an allowance-sized `max_pages` removes the busy-instance 1,000-execution cap.
- **`failed_batch` loss is real and the fix is load-bearing.** Both lanes independently confirmed
  `chunking.py:494-517` falls through to `dict(chunks[0])` for `people`/`companies` today.
- **`CLOSED_UNHANDLED_ERROR` is wired, not added.** Both confirmed it already exists
  (`write_grant.py:670`, `GRANT_04_REASONS` at `:672-675`) and that Task 4 now correctly extends
  `record_dispatch_outcome` with a `reason=` override instead of adding a sixth reason.
- **Authorisation is separated from execution.** 57-05 Task 4 records an authorisation; it runs
  no batch. Option-b is hard-gated on 57-01 Task 2's recorded `sampled: False`, which is the
  value Task 2 can actually produce.
- **`--only` is necessary and correct.** Both confirmed `deploy_n8n_workflows.py:265-269` globs
  every `wf_*_cloud.json` and `main()` has no selector.
- **Apollo's label is source-true.** `conftest.py:542-544` sets `http_403`; the cycle-2
  mislabel is gone, and the probe's gate is proved behaviourally (zero transport calls) rather
  than by grepping for the env var.
- **`manifest_snapshot=` is a real gap correctly identified.** `run_state.read_progress`'s
  current signature at `:332` cannot carry the snapshot the one-load promise needs.
- **`held_queue.py:106-110` is the right four-word template**, not `run_state`, which defines
  only three.

### Agreed Concerns (both lanes)

**MEDIUM — Threat T-57-19a still says "exactly one" request.** Raised independently by both lanes.
`57-04-PLAN.md:402` reads "exactly one for the valid case", which contradicts the two-request
Lusha protocol Task 1's `<behavior>` now requires (`:265`, `:269`). An executor working the
STRIDE table writes the wrong test.

### Divergent Views

- **Overall risk.** gpt-5-6-sol: MEDIUM, "subject to those corrections, the phase is ready to
  execute", with two findings it rates HIGH. grok-4-6: LOW, "the set is ready to execute; do not
  manufacture more HIGHs", with zero HIGHs. The divergence is one of coverage, not of
  interpretation: grok did not examine `split_for_allowance`'s work-to-scope ordering invariant
  or 57-05's held-queue contradiction row. The orchestrator verified both gpt-5 findings directly
  in source (see H-1 and H-2 below), so they stand.
- **The forbidden-value scanner.** gpt-5-6-sol rates the recursive substring scan over
  unallowlisted `rows`/`people`/`companies` records a MEDIUM false-positive risk. grok did not
  examine it. The orchestrator confirmed the mechanism: `held_queue._looks_forbidden`
  (`held_queue.py:120-122`) is a plain substring test over ten markers including `"arm"`, and
  `_first_forbidden` (`:125-144`) recurses into string leaves. In `held_queue` the blast radius
  is bounded by `ROW_FIELD_ALLOWLIST` (`:97`); in the remainder queue, by the plan's own design,
  it is not.
- **`contact-upload`'s report.** grok flags that `contact-upload` is a ceiling-guarded dispatch
  path in 57-01/57-03 but appears ZERO times in `57-05-PLAN.md`, so whether it is inside or
  outside AFTER-01's close condition is implicit. gpt-5 did not raise it.

---

## OpenCode Review (gpt-5-6-sol)

I’ll verify the revised plans against the current implementation and prior review record, concentrating on newly changed integration seams rather than repeating closed findings.
# Phase 57 Plan Review

## Overall Summary

The current plans are substantially stronger than the cycle-2 versions. The major safety defects previously identified are now addressed: the ceiling check is pre-send, all four dispatch paths are included, `failed_batch()` is generalized, split work is separated from authority, deployment is narrowed to one workflow, report vocabulary is centralized, and known partial closures are stated honestly.

Three new issues remain. One is a blocking report-model mismatch: Plan 57-05 asks for per-entry held-queue run attribution that the existing schema does not contain. Two implementation-contract inconsistencies in Plan 57-03 should also be resolved before execution. Subject to those corrections, the phase is ready to execute.

**Overall risk: MEDIUM.** The architecture is sound, but one planned report assertion is currently impossible and the remainder persistence contract contains contradictory instructions.

---

# Plan 57-01: Ceiling Refusal and Dispatch Enforcement

## Summary

Plan 57-01 now provides a coherent vertical implementation of RUN-05: it repairs execution sampling, refuses before arming, checks projected spend before dispatch, accounts for repeated and single-shot dispatches, and routes a real dispatch outcome into grant closure. The cycle-2 blocking findings against this plan are genuinely resolved.

## Strengths

- **RESOLVED:** The ceiling stop has moved before the transport call. The current dispatch occurs at `operator-claude-plugin/scripts/chunking.py:373-383`; the revised plan explicitly inserts the check before `_StatusCapturingTransport` and `enrichment.build_envelope`, eliminating the prior one-chunk overshoot.
- **RESOLVED:** `preingest.rerequest_unanswered()` is no longer excluded. It currently invokes `dispatch_plan()` internally at `operator-claude-plugin/scripts/preingest.py:703-713` and discards the resulting outcome at `operator-claude-plugin/scripts/preingest.py:731-741`; the plan now adds both `execution_ceiling` and `MergeResult.dispatch_outcome`.
- **RESOLVED:** The single-shot ingest path is now accounted for. The real calls are outside `dispatch_plan()` at `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:610` and `operator-claude-plugin/skills/contact-upload/SKILL.md:309`. `single_dispatch_outcome()` plus a pre-call check is the correct integration shape.
- **RESOLVED:** Quiet and busy execution-list cases are both addressed. The existing walker conflates exhaustion with incomplete coverage at `operator-claude-plugin/scripts/n8n_read.py:355-380` and hard-caps at `MAX_EXECUTION_PAGES`; `listing_exhausted` plus allowance-sized `max_pages` directly fixes both cases.
- **RESOLVED:** The plan now treats external concurrency honestly as a point-in-time limitation rather than claiming a global reservation.
- **RESOLVED:** The unknown-sample state no longer disables both protections. Binding it to the approved batch quote is a meaningful partial mitigation.
- The proposed `CeilingStop` remains separate from failures, matching the existing separation of `written_records_failures` from `failed_batch` in `operator-claude-plugin/scripts/chunking.py:134-154`.
- The plan correctly preserves exact-budget equality and stops only when the next chunk would exceed the ceiling.
- The override now requires an operator-provided reason and carries auditable authority metadata.

## Concerns

- **PARTIAL, LOW:** The runbook-level ordinary-exception closure remains inherently dependent on correctly handling a possibly unassigned `outcome`. An exception can occur before `dispatch_plan()` returns, including inside `enrichment.build_envelope()` or the transport path at `operator-claude-plugin/scripts/chunking.py:376-403`. The plan requires `record_dispatch_outcome(grant, outcome, ...)` in `except`/`finally`, but should explicitly require `outcome = None` before entering the `try`. Otherwise the exception handler can itself raise `UnboundLocalError`.
- **PARTIAL, LOW:** Sampling remains a lower bound because of retention, as the plan explicitly acknowledges. This is not a planning omission, but it means RUN-05 remains conditional on the checkpoint result.

## Suggestions

- Initialize every runbook’s `outcome` and `disarm` variables before `try`, then test an exception thrown before the first dispatch result is assigned.
- Add a test where `dispatch_plan()` raises before returning any `DispatchOutcome`, and assert the grant still closes with `unhandled_error`.
- Keep the Task 2 measurement and option selection in the summary exactly as planned; it is the evidence determining whether RUN-05 closes or remains partial.

## Risk Assessment

**LOW-MEDIUM.** The principal cycle-2 defects are resolved. Remaining risk is primarily runbook implementation precision around early exceptions and the known non-authoritative execution sample.

---

# Plan 57-02: Outcome Vocabulary and Join Keys

## Summary

Plan 57-02 now correctly treats “written” as an unresolved operator decision, centralizes action classification in a pure function, captures join metadata, and avoids deploying before the phase gate. The prior report-validation and pair-pipeline join objections are addressed or explicitly accepted as partial.

## Strengths

- **RESOLVED:** The unsupported `written` claim is now a blocking checkpoint rather than an assumption. This is justified by current code: write actions are classified from the response item at `operator-claude-plugin/scripts/written_records.py:161-174`, but an update ID may predate the actual PATCH.
- **RESOLVED:** The plan no longer delegates the never-raise report path to raising persistence logic. Current `classify_item()` raises at `operator-claude-plugin/scripts/written_records.py:150-159` and `:184-190`; extracting total `outcome_for_action()` is the correct boundary.
- **RESOLVED:** The old-entry contract is now consistent: old entries remain unchanged, and readers use `.get()`.
- **RESOLVED:** The action-coverage test is derived from the workflow builder rather than circularly hard-coding the ten values only in the consumer.
- **RESOLVED:** The pair pipeline’s stripped `row_id` is openly recorded as an unjoinable population rather than falsely claimed as closed. The actual boundary is `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:638-643`.
- **RESOLVED:** Deployment was removed from this plan and moved behind the phase gate.
- Centralizing the vocabulary eliminates the current divergence between `written_records` and `report_enrichment`.
- Preserving `created_id_unknown` respects the existing no-fabrication branch at `operator-claude-plugin/scripts/written_records.py:166-172`.
- Adding `association` and `row_id` to the restricted ledger entry while continuing to exclude email is appropriately scoped.

## Concerns

- **PARTIAL, LOW:** The plan’s final `<done>` still says “every entry carries `row_id`” and the phase success text says “every row ... carries the key,” while the same plan correctly states the final pair-pipeline ingest leg returns `row_id: None`. The detailed plan is honest, but the summary wording is broader than the actual guarantee.
- **PARTIAL, LOW:** If checkpoint option A is selected, terminal write success remains unproven for updates and enriches. The plan correctly presents this as an operator decision, not as closed evidence.

## Suggestions

- Change the Plan 57-02 `<done>` statement to: “Every newly classified entry carries a `row_id` key, whose value may be `None` when the backend did not receive one.”
- Apply the same qualification to the plan-level success criterion.
- If option A is selected, ensure AFTER-01 is not described elsewhere as proof that writes landed; it is then a report of backend write decisions and returned identifiers.

## Risk Assessment

**LOW-MEDIUM.** The technical design is now sound. Residual risk depends on the operator’s checkpoint selection and should be reflected consistently in summary wording.

---

# Plan 57-03: Split Offer and Remainder Queue

## Summary

Plan 57-03 now correctly separates dispatchable work from grant scope, generalizes remainder reconstruction across all accepted work shapes, persists only accepted splits or actual ceiling stops, and explicitly takes ownership of the single-shot dispatch handoff. These changes close the most serious cycle-2 defects. Two new implementation-contract issues should be corrected before execution.

## Strengths

- **RESOLVED:** `failed_batch()` will cover every shape accepted by `plan_chunks()`. Current support includes `rows`, `people`, `companies`, and `record_ids` at `operator-claude-plugin/scripts/chunking.py:206-277`, while current reconstruction only handles `rows` and `record_ids` at `:494-517`.
- **RESOLVED:** The split now returns two distinct products:
  - A dispatchable work specification.
  - A parallel authorization scope.
- **RESOLVED:** A refusal itself writes nothing; persistence occurs only after acceptance and a fresh grant.
- **RESOLVED:** `REASON_ALLOWANCE_SPLIT` now has an explicit producer.
- **RESOLVED:** The single-shot ingest breach branch is explicitly completed in this plan, with AST coverage.
- **RESOLVED:** Crash-mid-run persistence is explicitly out of scope rather than implied.
- **RESOLVED:** Same-run lost-update risk is documented as a one-writer contract.
- A per-run file is preferable to placing budget remainders into the confidence-specific held queue. The mismatch is visible in `held_queue.build_entry()` and its required fingerprint at `operator-claude-plugin/scripts/held_queue.py:154-183`.
- Reusing `_atomic_write_0600` maintains the existing durable-write security model.

## Concerns

- **NEW, HIGH:** The plan does not guarantee positional correspondence between `spec` records and the separately supplied grant scope. It says both products are cut at the same index and validates only matching counts. That is insufficient when the work is a `people`, `rows`, or `companies` list and authorization is supplied separately as `record_ids` followed by `record_domains`.

  The existing grant model treats IDs and domains as semantically distinct at `operator-claude-plugin/scripts/write_grant.py:607-620` and `:645-656`. A work list may interleave existing-ID rows and domain-only create rows, while the proposed scope sequence always orders all IDs before all domains. Cutting both at index `N` can therefore authorize records different from the first `N` work entries, even when counts match.

  Example: work order `[domain-create A, existing-id B]`, scope order `[id B, domain A]`, affordable `N=1`. The affordable work is A, but the affordable grant scope authorizes B.

- **NEW, MEDIUM:** `remainder_queue.save()` has contradictory exception semantics. The behavior section requires a falsey return for `OSError` **or any other exception** from `_atomic_write_0600`, but the action section explicitly says “Returns False on `OSError`.” The current sibling implementation catches only `OSError` in `written_records.append_chunk()` at `operator-claude-plugin/scripts/written_records.py:276-288`, so an executor following the action literally will fail the planned non-`OSError` test.
- **NEW, MEDIUM:** The recursive forbidden-value scanner is likely too broad for full work specifications. The proposed markers include `"arm"` and scan every string leaf. Unlike `held_queue`, whose persisted row is narrowed through `ROW_FIELD_ALLOWLIST` at `operator-claude-plugin/scripts/held_queue.py:97-103` and `:170-183`, the remainder queue persists complete `rows`, `people`, or `companies` records. Legitimate values such as `Armstrong`, `Armidale`, or `pharmacy` would be rejected as authority-shaped content, causing the queue to fail exactly when recovery is needed.

## Suggestions

- Replace parallel positional scope splitting with identity-derived scope splitting:
  - Derive each affordable work record’s corresponding ID or domain from that record.
  - Or require a per-record scope descriptor aligned with the work list.
  - Refuse the split when a one-to-one mapping cannot be proven.
- Add a test with interleaved ID-backed and domain-backed work entries. Assert that the affordable grant covers the affordable work values, not merely the same count.
- Resolve the `save()` exception contract explicitly:
  - Catch `Exception` around `_atomic_write_0600` if all environmental write failures must degrade.
  - Keep validation errors outside that block so `RemainderQueueError` still raises.
- Restrict forbidden scanning to keys and authority-bearing structured fields rather than arbitrary business-data string leaves. If values must be scanned, use exact secret-field names or typed authority objects, not broad substrings across names and company data.

## Risk Assessment

**MEDIUM-HIGH.** The cycle-2 data-loss and missing-producer defects are resolved, but incorrect work-to-scope alignment could authorize the wrong affordable subset. This should be fixed before implementation.

---

# Plan 57-04: Provider Balance Probe

## Summary

Plan 57-04 now accurately distinguishes Apollo’s structural `http_403` from ZoomInfo transport and parsing failures, proves gate-off network abstinence through an injected transport, and places the live run behind a human checkpoint. The two-request protocol is explicit and appropriately limits its claim.

## Strengths

- **RESOLVED:** Apollo’s actual label is now correctly grounded as `http_403`.
- **RESOLVED:** The full network path is disclosed, including the status POST and possible ZoomInfo token mint/cache.
- **RESOLVED:** Gate safety is behavioral rather than syntactic: tests require zero injected transport calls for all refusal conditions.
- **RESOLVED:** The probe run is separated from probe construction by a blocking checkpoint.
- **RESOLVED:** G-4 closure semantics are now defined for every verdict.
- **RESOLVED:** The Lusha before/after contradiction is corrected with a two-request protocol, and the second request’s cost is explicitly unmeasured.
- The plan correctly avoids patching the existing ZoomInfo code before observing the current failure. The required `Accept` header is already present in the workflow builder.
- No production provider behavior is modified based only on fixtures.
- The verdict excludes response bodies and credentials.

## Concerns

- **NEW, LOW:** Task 1 says refusal paths write no verdict file, while Task 2 requires a verdict file even when the live run cannot proceed. The `option-skip` path explicitly writes an inconclusive verdict, but the “option-run selected, precondition unavailable” path is less explicit. Without a rule, a selected run that refuses for missing credentials can leave Task 2’s acceptance criterion unmet.
- **PARTIAL, LOW:** The two-request Lusha delta proves only that request 1 did not change Lusha’s reported balance. The plan states this correctly and does not overclaim.

## Suggestions

- Specify that if option-run is selected but the probe refuses because its precondition is unavailable, Task 2 writes an `inconclusive` verdict with the exact refusal reason. Keep Task 1’s rule unchanged: the probe entry point itself should not write a verdict when it made no observation.
- Correct Threat T-57-19a’s stale wording if present: the valid path now makes exactly two requests, not one.
- Ensure the summary distinguishes “probe code refused before network” from “backend returned inconclusive.”

## Risk Assessment

**LOW.** The probe is carefully gated and makes no write-path change. Remaining concern is a small checkpoint-state ambiguity.

---

# Plan 57-05: End-of-Run Report and Phase Gate

## Summary

Plan 57-05 is materially improved: it treats durable artifacts as independent evidence sources, introduces read classification, records ephemeral observations without persisting authority, preserves multiple dispatch legs, defines contradiction handling, narrows deployment to one workflow, and separates phase landing from live-run authorization. One report requirement is incompatible with the existing held-queue schema and must be revised.

## Strengths

- **RESOLVED:** The report now joins five primary stores and its own audit record rather than incorrectly claiming four inputs.
- **RESOLVED:** The plan adds `classify_read` for stores whose current `load()` methods collapse absence and corruption. Current `written_records.load()` does that at `operator-claude-plugin/scripts/written_records.py:291-323`; current `run_manifest.load_scoped()` similarly degrades malformed states at `operator-claude-plugin/scripts/run_manifest.py:242-274`.
- **RESOLVED:** The audit artifact gets its own read classifier and merge-preservation test.
- **RESOLVED:** A single manifest snapshot is shared with `run_state.read_progress`; its current signature at `operator-claude-plugin/scripts/run_state.py:332-365` indeed requires the planned additive parameter.
- **RESOLVED:** Multi-leg outcomes are modeled as a sequence, including the single-shot ingest adapter.
- **RESOLVED:** Known unjoinable pair-ingest rows are retained and explicitly marked.
- **RESOLVED:** Cross-store contradictions now have a concrete matrix and an incomplete banner.
- **RESOLVED:** Deployment is narrowed through `--only`. Current deployment loads every cloud workflow at `scripts/deploy_n8n_workflows.py:265-269`, so the selector is necessary.
- **RESOLVED:** The final checkpoint is authorization-only; it does not itself run a batch.
- **RESOLVED:** The unattended option is unselectable when Task 2 recorded `sampled: False`.
- Persisting observations but not the grant is a sound GRANT-06 boundary.
- Recording grant-time audit facts before dispatch and disarm facts in `finally` improves crash reconstruction.
- The report’s projected-spend language correctly aligns with `SPEND_BASIS` at `operator-claude-plugin/scripts/run_state.py:172-180`.

## Concerns

- **NEW, HIGH:** One contradiction-matrix row and its expected test cannot be implemented from the existing held-queue schema:

  > “a `held_queue` row names a `run_id` absent from this run’s manifest”

  Held-queue entries contain `hold_code`, `reason`, `observed_signals`, `resume_fingerprint`, and an allowlisted `row` at `operator-claude-plugin/scripts/held_queue.py:174-183`. The row allowlist is `("row_id",) + MATCH_LOOKUP_KEYS` at `:97-99`; it does not include `run_id`. The run ID exists only at document level when saved at `:218-223`, and `held_queue.load()` returns only the entries map, discarding the document’s run ID at `:245-257`.

  Therefore no individual held-queue row can “name a run_id,” and the proposed contradiction cannot be detected by `build_run_report()` without changing the held-queue reader or schema.

- **NEW, MEDIUM:** The plan is inconsistent about input count. It repeatedly says “five durable stores,” then adds the run-audit record and correctly calls it six durable inputs in Task 1. This is mostly wording, but the distinction matters because audit corruption is independently classified and contributes to `REPORT INCOMPLETE`.
- **PARTIAL, LOW:** The report cannot fully close AFTER-01 because final ingest rows without both `row_id` and `hs_object_id` remain unjoinable. This is explicitly acknowledged and should not be treated as a new defect.
- **PARTIAL, LOW:** If Plan 57-02 checkpoint option A is selected, the report’s `written` outcome still represents a backend decision plus an ID rather than terminal write confirmation. The plan discloses this correctly.

## Suggestions

- Replace the impossible held-queue contradiction with one supported by current evidence:
  - Report the global held queue as unattributed backlog with its document-level last-writer `run_id`, if a new `held_queue.classify_read`/metadata reader exposes it.
  - Or remove run-attribution contradiction checking entirely and state that held entries cannot be assigned to a run under the present schema.
- If document-level attribution is useful, add a non-breaking `held_queue.load_scoped()` or `load_document_metadata()` returning `{entries, run_id}`. Do not inject `run_id` into each existing entry unless a migration need is established.
- Normalize language throughout:
  - “Five primary operational stores plus one run-audit record.”
  - Or simply “six durable inputs.”
- Add a test proving that global held backlog is not counted as this run’s held population, regardless of the document-level run ID.
- Preserve the `--only` default behavior exactly as planned and ensure argument parsing occurs before any credential or network check so selector tests stay offline.

## Risk Assessment

**MEDIUM.** The report and phase-gate design are strong, but one required contradiction test is impossible against the current data model. Fixing that requirement is necessary before execution.

---

# Resolved Cycle-2 Findings

The following earlier findings are genuinely resolved and should not be reopened:

- **RESOLVED:** Pre-send rather than post-send ceiling enforcement.
- **RESOLVED:** Quiet-instance listing exhaustion and busy-instance page-cap handling.
- **RESOLVED:** `preingest.rerequest_unanswered()` ceiling propagation.
- **RESOLVED:** Single-shot ingest dispatch accounting.
- **RESOLVED:** Self-bound ceiling under `CEILING_UNKNOWN`.
- **RESOLVED:** Ordinary-exception grant closure is explicitly designed, subject only to the initialization detail above.
- **RESOLVED:** Override authority and audit requirements.
- **RESOLVED:** `written` evidence conflict moved to an operator checkpoint.
- **RESOLVED:** Pure outcome mapping preserves the report’s never-raise contract.
- **RESOLVED:** Pair-pipeline `row_id` loss is disclosed as an intentional partial closure.
- **RESOLVED:** `failed_batch()` coverage for `people` and `companies`.
- **RESOLVED:** Accepted-split persistence and `REASON_ALLOWANCE_SPLIT` producer.
- **RESOLVED:** Single-shot breach persistence handoff from 57-01 to 57-03.
- **RESOLVED:** Apollo `http_403` terminology.
- **RESOLVED:** ZoomInfo probe network gate and closure table.
- **RESOLVED:** Five-store contradiction analysis.
- **RESOLVED:** Single-workflow deployment selector.
- **RESOLVED:** Phase landing separated from live-run authorization.
- **RESOLVED:** Wave-specific ownership of checkpoint decision records.

# Recommended Revisions

Before execution:

1. Fix `split_for_allowance()` so grant scope is derived from or provably aligned with the selected work records, not merely cut at the same numeric index.
2. Resolve `remainder_queue.save()`’s contradictory exception contract.
3. Narrow the remainder queue’s forbidden-value scanner so legitimate business data cannot trigger broad substring rejection.
4. Replace or redesign Plan 57-05’s impossible per-entry held-queue `run_id` contradiction.
5. Clarify the Plan 57-04 inconclusive-verdict behavior when option-run is selected but preconditions fail.
6. Initialize runbook outcome variables before `try` to make early-exception closure executable.

With those changes, the plans are ready to execute.

---

## OpenCode Review (kimi-k3)

> **Lane dropped — `[spawn error: ETIMEDOUT]` at the lane's 900s floor, the third
> consecutive cycle-3-style failure for this reviewer.** It produced no review. What it did
> emit before the timeout was progress narration; the verbatim capture follows, kept only
> because its fourth line carries a grounded factual fragment (the ten-vs-nine marker count)
> that the orchestrator verified and recorded as L-4.

```
I'll verify the plans against the actual source. First, let me check the recent commits and read the key referenced files.
I have the cycle-2 baseline. Now I'll verify the plans' factual claims against source, starting with the most load-bearing modules.
Key claims confirmed so far. Now the shape coverage in `plan_chunks`, the `written_records`/`report_enrichment` vocabulary readers, and the `held_queue`/`run_state` classifier templates.
The 10-action vocabulary and `fail_batch` shape loss are confirmed. I found a discrepancy: the forbidden-marker tuple has **10** entries, while plans say "nine." Let me verify the remaining modules.
All provider/balance claims verified. Now checking the cadence analog, cost_guard tri-state, the test pins, and the remaining module details.

[stderr] [spawn error: ETIMEDOUT]
```

---

## OpenCode Review (grok-4-6)

I'll ground this cycle-3 review in source and prior findings, then assess the current plans.
# Phase 57 Plan Review — Cycle 3

Grounded against current source (`n8n_read.py:258-381`, `chunking.py:317-517`, `write_grant.py:411/:670/:899`, `preingest.py:662-741`, `written_records.py:96/:131`, `report_enrichment.py:38`, `BUILD_INGEST_RESPONSE` at `build_cloud_workflows.py:471-519`, `deploy_n8n_workflows.py:265-269/:565`, `conftest.py:542-544`, `held_queue.py:106-110`, `run_state.py:175/:332`). Cycle-2 items treated as closed unless residual remains.

---

## Plan 57-01

### Summary
The tracer is now the right vertical: sample → refuse in `plan_grant()` → pre-send stop in `dispatch_plan()` → `record_dispatch_outcome` from a real dispatch. Cycle-2 H-1/H-2/H-3/H-6/H-7/H-8 are in the task text, not in cons. Ready to execute, with four human checkpoints later in the phase.

### Strengths
- Pre-send tally matches `chunking.py:373+` (send is `dispatch_enrichment` inside the loop). Stop before `build_envelope` is the only placement that meets “cannot spend what it does not have.”
- `listing_exhausted` vs `covers_full_window` matches `n8n_read.py:358-360` and `:378` (`covers_full_window = saw_older_than_cutoff`). Quiet-account reachability is a real fix, not theatre.
- Fourth dispatch path is real: `rerequest_unanswered` at `preingest.py:713`; ingest at `contact-upload/SKILL.md:309`.
- `CLOSED_UNHANDLED_ERROR` already exists (`write_grant.py:670`) — Task 4 wires it instead of adding a sixth GRANT-04 reason.
- Self-bound ceiling under `CEILING_UNKNOWN` closes the double-off hole without reversing D-57-02.

### Concerns
- **LOW / NEW** — Task 1 artifacts list `record_dispatch_outcome(..., reason=None)` before Task 4 adds `reason=`. Harmless if Task 1 omits it; confusing if an executor implements the full signature early.
- **MEDIUM / NEW** — AST compile of SKILL fences will fail on today’s placeholders (`contact-upload/SKILL.md:288-309` uses `<path>`, `<this send's ids>`). The plan says a non-parsing block fails the test. Executor must rewrite those fences into valid Python as part of Task 4, not wrap them.

### Suggestions
- Task 1 action should say `reason=` lands in Task 4.
- Task 4 should say: replace angle-bracket placeholders so `compile(..., "exec")` succeeds.

### Risk
**LOW** for this plan. Cycle-2 HIGHs on this plan are **RESOLVED** in text.

---

## Plan 57-02

### Summary
Widens the ledger, extracts a pure mapper, does not deploy. The `written` checkpoint is the right operator call. `BUILD_INGEST_RESPONSE` (`build_cloud_workflows.py:507-518`) still has no `row_id` — Task 4 is necessary and correctly non-deploying.

### Strengths
- Pure `outcome_for_action` vs `classify_item` raise path (`written_records.py:150-159`) vs never-raise report (`report_enrichment.py:285-304`) is the right split.
- `enrich` is in `WRITE_ACTIONS` (`written_records.py:96`) and missing from D-57-03 — called out.
- Builder-derived action set test will catch an 11th `action` in `build_cloud_workflows.py`.
- Deploy deferred to 57-05 matches `deploy_n8n_workflows.py:575` (loads every `wf_*_cloud.json`).

### Concerns
- **PARTIAL (cycle 2 H-6)** — “written” still inferred from a pre-write decision. Now a blocking checkpoint, not a silent claim. Residual until Task 1 is answered. Do not treat as a new gap.
- **RESOLVED** — discussion-log ownership narrowed to waves 1–2.

### Suggestions
- After Task 1, pin `ALL_OUTCOMES` to one frozenset in the repo; do not leave three variants in comments.

### Risk
**LOW**, gated on the checkpoint.

---

## Plan 57-03

### Summary
Remainder is a sibling store; `failed_batch` is lossless; split has two products; 57-01’s ingest-leg handoff is taken. This was cycle 2’s weakest plan; it is now coherent.

### Strengths
- `failed_batch` at `chunking.py:506-517` really drops `people`/`companies` (falls through to `chunks[0]`). H-4 fix is load-bearing.
- GRANT-06: work specs only; `plan_grant` writes nothing (H-5).
- `spec=` + parallel grant-scope split matches `write_grant.py:607-656` vs `plan_chunks` shapes.
- AST handoff for `remainder_queue.save` on both ingest runbooks is the right pin.

### Concerns
- **LOW / NEW** — `save` is read-append-rewrite with a stated single-writer contract, not a lock. Fine given no current concurrent writer; keep it as documented invariant.
- Crash-mid-run remainder silence is **deliberate** (do not re-raise).

### Suggestions
- Round-trip test over all five `plan_chunks` shapes before wiring `CeilingStop.remainder`.

### Risk
**LOW**.

---

## Plan 57-04

### Summary
Apollo is `http_403` (`conftest.py:542-544`), not `unrecognized_response_shape`. Probe is gated, two-request, checkpointed before live. G-4 closure table is binding.

### Strengths
- M-1 label correction is source-true.
- Gate proved by zero calls on an injected transport under `no_network`, not by grepping the env var.
- `--only` is not this plan; live run is a human checkpoint (`autonomous: false`).
- Closure table: `inconclusive` does not close G-4.

### Concerns
- **MEDIUM / NEW** — Threat **T-57-19a** still says “exactly **one**” request on the valid path; Task 1 behaviour correctly requires **two**. An executor following the STRIDE table will write the wrong test.
- **RESOLVED** — H-3 one-vs-two request contradiction in Task 1 itself.

### Suggestions
- Change T-57-19a to “exactly two status POSTs to one host.”

### Risk
**LOW**.

---

## Plan 57-05

### Summary
The report joins five stores plus an audit record, names contradictions, and does not treat a green suite as live authorisation. `--only` is required: `_load_local_workflows()` at `deploy_n8n_workflows.py:269` globs every cloud workflow; `main()` at `:575` has no selector.

### Strengths
- `read_progress(run_id, path=None)` at `run_state.py:332` cannot take a snapshot today — `manifest_snapshot=` is a real gap, correctly added.
- `SPEND_BASIS` is at `run_state.py:175`.
- `held_queue.py:106-110` is the four-word template including `ANOTHER_RUN`; `run_state` has three. Copying the right sibling matters.
- Option-b keyed on `sampled: False` matches what Task 2 of 57-01 actually records.
- Authorisation-only on (b); no batch inside this task.

### Concerns
- **LOW / NEW** — `contact-upload` is a ceiling-guarded dispatch path (57-01/57-03) but 57-05 Task 3 does not call `build_run_report` there. AFTER-01’s primary surface is the pair pipeline; standalone ingest still has the old step-7 report. Acceptable if named as out of AFTER-01’s close condition; today it is only implicit.
- **PARTIAL** — unjoinable ingest leg: disclosed, kept, named in `gaps`. Not a new finding.

### Suggestions
- One sentence in Task 3: AFTER-01’s production call sites are the two enrichment lanes; contact-upload keeps step 7.

### Risk
**LOW**.

---

## Cross-plan / phase

### Cycle-2 status
| ID | Status |
|---|---|
| H-1 sampling predicate / task order | **RESOLVED** (Task 1 then Task 2; `listing_exhausted` + `max_pages`) |
| H-2 post-send stop | **RESOLVED** (pre-send) |
| H-3 rerequest bypass | **RESOLVED** |
| H-4 failed_batch shapes | **RESOLVED** (57-03) |
| H-5 REASON_ALLOWANCE_SPLIT producer | **RESOLVED** |
| H-6 written inference | **PARTIAL** — checkpoint, not closed in data |
| H-6 CEILING_UNKNOWN double-off | **RESOLVED** (self-bound + option-b unselectable) |
| H-7 strip_row_id / ingest spend | **PARTIAL** (spend charged; join still UNJOINABLE by design) |
| H-8 grant close / split two products / discussion-log ownership | **RESOLVED** |
| H-2 deploy-all-five | **RESOLVED** (`--only`) |
| H-4 authorisation vs running a batch | **RESOLVED** |
| M-1/M-3/M-4/M-8/M-9/M-10/M-11 | **RESOLVED** in plan text |
| 57-03 ingest remainder handoff | **RESOLVED** (`2828061`) |

### New this cycle (actionable)
1. Align 57-04 T-57-19a with two requests.
2. State that SKILL fences must become parseable Python (drop `<placeholders>`).
3. Optionally name contact-upload as outside AFTER-01’s report close.

None of these should block execution.

### Requirement coverage (still correct)
- **RUN-05** — 57-01 + 57-03; conditional on Task 2 `sampled`.
- **AFTER-01** — **PARTIAL** at seal (unjoinable ingest leg).
- **AFTER-03** — 57-02 + 57-05; word `written` depends on 57-02 Task 1.
- **G-4** — 57-04 table; `inconclusive` ≠ closed.
- **GRANT-06** — preserved via remainder + `record_audit` authority tests.

### Overall risk
**LOW.** Cycle-2’s 9 HIGHs are addressed in the current plans. Remaining holes are the ones the phase **chose** to disclose (monthly sample, retention, unjoinable ingest, inferred `written` until the checkpoint). The set is ready to execute; do not manufacture more HIGHs.

**Do not re-raise:** AFTER-01 PARTIAL, RUN-05 conditional, deferred per-provider/throughput, no armed spend in this phase.

---

## Source-Grounding Pass — Cycle 3 (orchestrator, authority: direct file reads)

Every finding counted below was re-verified against the working tree at `0cb40e7`. Findings that
did not survive that pass are listed under "Not counted".

**SG-1 — `held_queue` rows cannot name a `run_id`. CONFIRMED.**
`ROW_FIELD_ALLOWLIST = ("row_id",) + enrichment.MATCH_LOOKUP_KEYS` (`held_queue.py:97`), and
`MATCH_LOOKUP_KEYS` is `("email", "firstname", "lastname", "company", "linkedin_url")`
(`enrichment.py:79`) — no `run_id`. `_allowlisted_row` (`:172-173`) projects the row through it.
`save()` puts `run_id` at DOCUMENT level (`:219-224`). `load()` returns `dict(entries)` and
discards the document entirely (`:245-257`). `57-05-PLAN.md:438`'s contradiction row — "a
`held_queue` row names a `run_id` absent from this run's manifest" — therefore cannot be detected
by `build_run_report()` against the current reader.

**SG-2 — the two-product split's ordering invariant is asserted, not constructed. CONFIRMED.**
`57-03-PLAN.md:440-452` returns `affordable_spec`/`remainder_spec` split "by its own list-bearing
key" in the spec's own order, and `affordable`/`remainder` "built from the same ordered
`(kind, value)` sequence across ids then domains". `:448` then asserts the two "are cut at the
SAME index N and are consistent by construction". They are not: the scope sequence is ids-then-
domains while the work sequence is the caller's own order, and `write_grant.py:607-620` / `:645-656`
treat ids and domains as semantically distinct. A work list interleaving id-backed and domain-only
records cuts to a different membership on each side at the same N.

**SG-3 — `remainder_queue.save()`'s exception contract self-contradicts. CONFIRMED.**
`57-03-PLAN.md:231-235` (`<behavior>`): falsey "on an `OSError` OR on any other exception", with a
test that drives a non-`OSError` failure. `57-03-PLAN.md:294` (`<action>`): "Returns False on
`OSError`." The sibling it names, `written_records.append_chunk` (`written_records.py:276-288`),
catches `OSError` only. An executor following `<action>` fails `<behavior>`'s test.

**SG-4 — the forbidden-marker count is TEN, not nine. CONFIRMED** (surviving fragment from the
dropped `kimi-k3` lane, verified). `_FORBIDDEN_NAME_MARKERS` is
`("arm", "secret", "api_key", "apikey", "token", "credential", "password", "grant", "permission",
"webhook")` — ten entries — identically in `held_queue.py:101-104`, `written_records.py` and
`run_manifest.py`. `57-03-PLAN.md` says "nine" at `:278`, `:526` and `:556`.

**SG-5 — the SKILL.md fences do not compile. CONFIRMED.**
`contact-upload/SKILL.md:288-309` contains `record_ids=<this send's ids>`,
`allow_create=<allow_create>` and `dispatch.dispatch(<path>, True, cfg)`. `<this send's ids>`
alone is a `SyntaxError` (unterminated string literal from the apostrophe). `57-01-PLAN.md:896`
requires `compile(src, name, "exec")` to succeed and states "a block that does not parse fails the
test". No plan instructs the executor to replace the placeholders; `57-03-PLAN.md:509`'s "replace
57-01's placeholder" refers to the prose breach branch, not to these.

**SG-6 — T-57-19a is stale. CONFIRMED.** `57-04-PLAN.md:402` ends "...and exactly one for the
valid case", against `:265`'s "exactly TWO requests to one host".

**SG-7 — the store count is inconsistent within 57-05. CONFIRMED.** "FIVE durable stores" at
`:43`, `:86`, `:110` and `:508`; "six durable inputs" at `:272`.

**SG-8 — 57-02's `<done>` overclaims. CONFIRMED.** `:358` reads "every entry carries `row_id` and
`association`", while the same plan's backstop truth correctly says the pair pipeline's final
ingest leg returns `row_id: None`.

**SG-9 — `contact-upload` is absent from 57-05. CONFIRMED.** Zero occurrences in
`57-05-PLAN.md`, while `57-01-PLAN.md:60` names it as one of the four ceiling-guarded dispatch
paths.

**SG-10 — grok's "Task 1 lists `reason=None` early" does NOT hold. NOT COUNTED.** Task 1's
signature at `57-01-PLAN.md:467` is
`record_dispatch_outcome(grant, outcome, config=None, *, disarm=None, transport=None)` — no
`reason=`. The only `reason=` occurrence is `:766`, inside Task 4, which is where the plan says it
lands.

---

## Cycle-3 Unresolved HIGH Concerns

| # | Sev | Source | Finding | Plan change still needed |
|---|---|---|---|---|
| H-1 | HIGH | gpt-5-6-sol (SG-2 confirmed) | **`split_for_allowance`'s two products can authorise different records than they dispatch.** The work spec is cut in the caller's own record order; the grant scope is built "across ids then domains" (`57-03-PLAN.md:440-447`) and both are cut at index N with only a count check. `write_grant.py:607-620`/`:645-656` treat ids and domains as distinct kinds. Counterexample: work `[domain-create A, existing-id B]`, scope `[id B, domain A]`, N=1 — the affordable work is A, the affordable grant authorises B. On the phase whose entire subject is not spending outside an approved scope, the split's central correctness claim ("consistent by construction") is an assertion the described construction does not deliver. | Derive the scope from the selected work records (or require a per-record scope descriptor) rather than cutting a parallel ids-then-domains sequence; refuse the split when a one-to-one mapping cannot be proven. Add an interleaved-shape test asserting the affordable grant covers the affordable work VALUES, not merely the same count. |
| H-2 | HIGH | gpt-5-6-sol (SG-1 confirmed) | **57-05's contradiction matrix contains a row that cannot be implemented against the current held-queue schema.** `57-05-PLAN.md:438` requires detecting "a `held_queue` row names a `run_id` absent from this run's manifest". Held-queue entries carry `hold_code`, `reason`, `observed_signals`, `resume_fingerprint` and an allowlisted `row` (`held_queue.py:174-183`); the allowlist is `("row_id",) + MATCH_LOOKUP_KEYS` (`:97`) and excludes `run_id`; `load()` discards the document-level `run_id` (`:245-257`). The matrix row and its expected test are unimplementable as written, on a plan whose stated purpose is that a contradiction is "never silently resolved". | Replace the row with one the schema supports — document-level attribution via a non-breaking `held_queue.load_document_metadata()`/`load_scoped()`, or `classify_read(expected_run_id=...)`'s existing `ANOTHER_RUN` — or drop run-attribution contradiction checking and state that held entries cannot be assigned to a run under the present schema. Add a test proving the global backlog is never counted into this run's held population. |

## Cycle-3 Actionable Non-HIGH Concerns

| # | Sev | Source | Finding | Plan change still needed |
|---|---|---|---|---|
| M-1 | MEDIUM | gpt-5-6-sol (SG-3) | `remainder_queue.save()`'s exception contract contradicts itself between `<behavior>` (`57-03-PLAN.md:231-235`, any exception) and `<action>` (`:294`, `OSError` only). The named sibling catches `OSError` alone. | Pick one and state it in both places; keep `RemainderQueueError` outside whatever block is chosen so a data defect still raises. |
| M-2 | MEDIUM | gpt-5-6-sol | The remainder queue's recursive forbidden-value scan runs over COMPLETE `rows`/`people`/`companies` records with no `ROW_FIELD_ALLOWLIST` narrowing, using plain substring markers including `"arm"` (`held_queue.py:120-122`, `:125-144`). `Armstrong`, `Armidale`, `pharmacy`, `armature` all match. A refusal here loses the unsent rows — and 57-03's own degrade-rather-than-halt rule makes that loss quiet (recorded only on `CeilingStop.reason`). The queue would fail exactly when recovery is needed. | Narrow the scan to keys and authority-bearing structured fields, or allowlist the persisted work record's columns as `held_queue` does; state which. |
| M-3 | MEDIUM | gpt-5-6-sol + grok-4-6 (SG-6) | Threat `T-57-19a` (`57-04-PLAN.md:402`) still says "exactly one for the valid case", contradicting Task 1's two-request protocol at `:265`. Raised independently by both lanes. | Change T-57-19a's mitigation to "exactly two status POSTs to one host". |
| M-4 | MEDIUM | grok-4-6 (SG-5) | 57-01 Task 4's AST test requires every SKILL.md dispatch fence to `compile()`, but `contact-upload/SKILL.md:288-309` (and the sibling fences) carry angle-bracket placeholders — `<path>`, `<this send's ids>`, `<allow_create>` — that are hard `SyntaxError`s. No plan instructs the executor to rewrite them. The acceptance criterion cannot pass on any of the three files as they stand. | Add an explicit instruction in 57-01 Task 4 that the fences are rewritten into parseable Python (real names or literals) as part of the wiring, not merely wrapped. |
| M-5 | MEDIUM | gpt-5-6-sol | 57-01 Task 4 wraps the dispatch in `try`/`except`/`finally` and closes through `record_dispatch_outcome(grant, outcome, cfg)` (`57-01-PLAN.md:857-861`), but never requires `outcome = None` before the `try`. An exception raised before `dispatch_plan()` returns — inside `enrichment.build_envelope` or the transport (`chunking.py:376-403`) — makes the closure handler itself raise `UnboundLocalError`, defeating the guarantee it exists to provide. | Require every runbook to initialise `outcome` (and `disarm`) before `try`, and add a test where `dispatch_plan` raises before returning, asserting the grant still closes with `unhandled_error`. |
| L-1 | LOW | gpt-5-6-sol | 57-04 Task 1 says a refusal path writes no verdict file; Task 2's acceptance criterion requires one. The `option-skip` path writes an `inconclusive` verdict explicitly, but "option-run selected, precondition unavailable" has no rule, so a selected run that refuses on missing credentials leaves the criterion unmet. | State that option-run + precondition failure writes an `inconclusive` verdict carrying the refusal reason; leave Task 1's entry-point rule unchanged. |
| L-2 | LOW | gpt-5-6-sol (SG-7) | 57-05 says "FIVE durable stores" at `:43`, `:86`, `:110`, `:508` and "six durable inputs" at `:272`. The distinction matters because the audit record is independently `classify_read`-ed and contributes to `REPORT INCOMPLETE`. | Normalise to "five primary stores plus one run-audit record", or to "six durable inputs", throughout. |
| L-3 | LOW | gpt-5-6-sol (SG-8) | 57-02's `<done>` (`:358`) says "every entry carries `row_id`", broader than the guarantee the same plan's backstop truth correctly states (the pair-ingest leg returns `None`). | Reword to "every newly classified entry carries a `row_id` KEY, whose value may be `None`". Apply the same qualification to the plan-level success criterion. |
| L-4 | LOW | kimi-k3 (surviving fragment, SG-4 confirmed) | 57-03 says "nine forbidden-name markers" at `:278`, `:526` and `:556`. Every sibling tuple has TEN. An executor reimplementing "the nine" drops one — and the tuple's own first entry, `"arm"`, is the one the module exists to catch. | Correct to ten in all three places, or state the tuple by enumeration rather than by count. |
| L-5 | LOW | grok-4-6 (SG-9) | `contact-upload` is one of 57-01's four ceiling-guarded dispatch paths (`57-01-PLAN.md:60`) but appears ZERO times in `57-05-PLAN.md`, so whether its rows are inside or outside AFTER-01's close condition is left implicit. | One sentence in 57-05 Task 3: AFTER-01's production call sites are the two enrichment lanes; `contact-upload` keeps its existing step-7 report. |

### Not counted (incorporated, deferred, or not surviving grounding)

- **All nine cycle-2 HIGHs (H-1..H-9).** Both producing lanes independently confirmed each in the
  current plan text, with source citations; the orchestrator spot-verified `--only`
  (`57-05-PLAN.md:639-645`), AFTER-01 marked PARTIAL in the coverage table
  (`57-01-PLAN.md:1016`), option-b's `sampled: False` hard gate (`57-05-PLAN.md:675`), the
  two-request protocol (`57-04-PLAN.md:228,265`), `autonomous: false` on all five plans, and
  57-03 Task 3's explicit handoff for the single-shot breach branch.
- **All eleven cycle-2 actionable MEDIUM/LOWs (M-1..M-11).** grok's table marks the set RESOLVED;
  no lane re-raised any of them.
- **AFTER-01's unjoinable pair-ingest population** — disclosed at plan, roadmap and coverage-table
  level; both lanes explicitly declined to treat it as a new defect.
- **RUN-05's monthly-allowance blind spot under `CEILING_UNKNOWN`** — disclosed in three places,
  mitigated by the self-bound ceiling, and gated by option-b's unselectability. gpt-5 rates the
  residual "PARTIAL, LOW — not a planning omission".
- **`written` inferred rather than proven under 57-02 option A** — now a blocking operator
  checkpoint. Both lanes say it is correctly presented as an operator decision, not as closed
  evidence.
- **Retention under-counting the execution sample** — explicitly acknowledged in plan text.
- **Per-provider ceilings and throughput optimisation** — deferred with rationale; neither lane
  re-raised them.
- **Same-run lost update on the remainder queue** — grok LOW; documented as a single-writer
  contract in `57-03-PLAN.md`'s backstop truth, which is the incorporation.
- **Crash-mid-run remainder silence** — grok explicitly calls it deliberate.
- **grok's "57-01 Task 1 lists `reason=None` early"** — did not survive grounding (SG-10).

**CYCLE_SUMMARY: current_high=2 current_actionable=10**
