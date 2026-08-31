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
