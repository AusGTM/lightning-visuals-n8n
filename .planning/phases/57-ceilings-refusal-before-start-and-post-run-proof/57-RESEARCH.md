# Phase 57: Ceilings, refusal-before-start, and post-run proof - Research

**Researched:** 2026-08-31
**Domain:** In-repo Python control-plane logic (no new external services). Existing modules:
`write_grant.py`, `chunking.py`, `written_records.py`, `held_queue.py`, `run_state.py`,
`confidence.py`, `durable_paths.py`, `n8n_read.py`, `n8n_cadence.py`, plus the n8n-side backend
in `scripts/build_cloud_workflows.py` and `n8n/code/*.js`.
**Confidence:** HIGH — every claim below was verified this session by reading the named file at
the named lines, not from training memory or CONTEXT.md's line numbers (which were captured
during discuss and in several places have drifted; corrected line numbers are given below).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-57-01:** A mid-run ceiling breach **holds the remaining rows and lets the batch finish.**
  Spending stops; unspent rows go to the held queue with a ceiling reason; the run completes and
  the operator gets one review pass. The grant is then closed by emitting `ceiling_breach`
  (`write_grant.CLOSED_CEILING_BREACH`, already accepted at `write_grant.py:667,909,932` and
  pinned by `test_write_grant.py:1507`). Reversibility: costly.
- **D-57-02:** An **unreadable balance does not block the run.** It is disclosed at grant time and
  named in the end-of-run report as an explicit blind spot. Reversibility: reversible. G-4 is in
  scope as a fix, not just a disclosure — improving the Apollo and ZoomInfo balance reads narrows
  the blind spot directly. Because provider balances are partly blind, the mid-run breach does
  more protective work than it otherwise would — detection quality is a first-class concern of
  this phase, not an implementation detail.
- **D-57-03:** The report **preserves the backend's own distinctions.**
  `written_records.classify_item` currently collapses every non-write action into `not_written`;
  that mapping widens to: `written` (`create`/`update` with an `hs_object_id`), `created_id_unknown`
  (`create` with no id — stays as-is; never fabricate an id), `gated` (`write_blocked` — open a
  grant and re-send, this row would have been written), `held` (`review`, `needs_match_review` —
  review the row and decide), `failed` (`research_failed`, `recompute_refused` — retry or fix the
  input), `no_action` (`skip`, `proposed` — nothing, these are successes). Reversibility: costly —
  `written_records` entries are a persisted on-disk artifact.
- **D-57-04:** A run that would exhaust the allowance **auto-splits across runs**: it breaks the
  batch into affordable runs and queues the remainder, so the whole batch completes over time
  without the operator re-deciding each round. Reversibility: costly.
- **D-57-05 (DERIVED — not asked, follows from an existing operator ruling; planner must honour
  it):** **Auto-split queues WORK, never AUTHORITY.** GRANT-06 is that a grant is never persisted
  and never rehydrated, and 61-06 restated it: "A resumed run gets a FRESH grant." So the
  remainder queue holds rows still to do; it does **not** carry permission to write them. Each
  subsequent run opens its own grant. Reversibility: one-way — treat as a hard constraint, not a
  preference. If the planner finds it cannot preserve both auto-split and GRANT-06, that is a
  checkpoint for the operator, not a judgement call.

### Claude's Discretion

- Where the ceiling check lives (client pre-flight, backend node, or both). The arithmetic is
  client-side today (`write_grant.envelope`), the spend is backend-side — follow the evidence.
- The remainder queue's storage shape. Strongly prefer reusing `held_queue.py`'s durable-write
  idiom (`durable_paths._atomic_write_0600`) over a second persistence mechanism. Whether a
  queued remainder belongs *in* the held queue or *beside* it is a real design question.
- How a breach is detected mid-run (post-chunk reconciliation vs a running tally) — but detection
  confidence is load-bearing here per D-57-02.
- Report format and delivery surface, as long as AFTER-01's contents are all present.

### Deferred Ideas (OUT OF SCOPE)

- **Per-provider spend ceilings** (as opposed to one aggregate ceiling) — worth its own
  consideration once the balance reads are fixed; not in scope here.
- **Restoring the post-write confirmation** that would eliminate `created_id_unknown` — scoped
  out in 59-01 and still out. (Research note: Phase 61 Plan 06 Task 2 DID add a post-write id
  capture for the COMPANIES create branch specifically — `ADAPT_COMPANY_CREATE`,
  `scripts/build_cloud_workflows.py:3462-3479` — but it is not wired into
  `written_records.classify_item`. This is flagged as a finding in Code Examples/Architecture
  Patterns below but treated as still out of scope per this explicit deferral, since CONTEXT is
  unambiguous that `created_id_unknown`'s fix belongs to a different phase.)
- **Enrichment throughput optimisation** (82% of every full run is two sequential Anthropic
  calls) — considered and not folded; the ceiling arithmetic should be written so that fixing
  this later does not invalidate it.
- Re-running Phase 52's backfill (deferred indefinitely). The scheduled/cron poller's own double
  pass (OP-54-02) — headless paths are out of this milestone per D-1.1-01. Changing the
  non-clobber merge policy, the write-safety gates, or per-send armed-window narrowing — ceilings
  sit *beside* those guards, never in place of them.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RUN-05 | "A run that would exhaust the monthly execution allowance refuses **before starting**, with the arithmetic, and offers a smaller batch." (`.planning/milestones/v1.1-REQUIREMENTS.md`, unticked) | `write_grant.envelope()` already computes the arithmetic (`write_grant.py:183-278`) but never refuses (D-53-02, the "disclosure not constraint" text at `write_grant.py:113-154`). `n8n_cadence.check_budget_floor` (`n8n_cadence.py:452-491`) is the existing refuse-with-arithmetic precedent to follow. `n8n_read.executions_in_window` (`n8n_read.py:258-381`) is the existing month-to-date sampler `envelope()`'s hardcoded `remaining_allowance_sampled: False` (`write_grant.py:261`) is waiting for — see Pattern 2 and Pitfall 4 for its truncation caveat. |
| AFTER-01 | "One end-of-run report: per-record outcome, association outcome, held rows named individually with reasons, spend actuals vs ceiling, and the disarm verdict." (unticked) | Must join `written_records` (per-run, by `run_id`) with `run_state.read_progress`/`run_manifest` (by `run_id`+`row_id`) and `held_queue` (global, by hold entries). **Verified blocking gap: `written_records.classify_item` never captures `row_id`** even though it is present on the same response item (`written_records.py:161-182` vs `build_cloud_workflows.py:1705,3439,4982`) — there is today no reliable join key for exactly the held/gated rows AFTER-01 most needs to name individually, since those rows have no `hs_object_id`. |
| AFTER-03 | "The report distinguishes 'written' from 'would have been written' — a gated record must never read as a completed one." (unticked) | D-57-03's widened vocabulary (`gated` for `write_blocked`) is the direct mechanism. Verified: the backend action set is 10 values, not 9 — `enrich` (a genuine write) has no explicit row in D-57-03's table and must be reconciled onto `written`, matching `create`/`update`'s treatment (`written_records.WRITE_ACTIONS`, `written_records.py:96`). A second reader of the same vocabulary, `report_enrichment._ACTION_TO_OUTCOME` (`report_enrichment.py:38-49`), independently maps only 6 of 10 actions and silently renders `update`/`review`/`research_failed`/`recompute_refused` as `"unknown"` — a live discrepancy AFTER-03 should account for, whether fixed in this phase or explicitly deferred. |
| G-4 | "Two of three provider balances read `unknown` in the same preview (Apollo `unrecognized_response_shape`, expected; ZoomInfo `provider_error`, new and probably transient)." (`v1.1-REQUIREMENTS.md:56`, minor) — D-57-02 puts the FIX for this in scope, not just disclosure | Verified root causes: **Apollo is structurally unfixable by code** — the account's API key is non-master and Apollo's `usage_stats` endpoint 403s for any non-master key by design (`n8n/code/providerSelection.js:85-89`, `scripts/provider_registry.py:26-33`) — needs a different Apollo credential, an account-level change outside this repo. **ZoomInfo's historically-documented cause (missing `Accept: vnd.api+json`) is already fixed in current code** (`scripts/build_cloud_workflows.py:4614-4630` sends the header) — the 2026-08-25 UAT's `provider_error` cannot be explained by code inspection alone and needs a live re-probe (see Assumption A3) before any further fix is attempted. |

</phase_requirements>

## Summary

This phase has no new library, framework, or external dependency to research — it is entirely
in-repo wiring between five existing, well-documented modules. The research task was therefore
to verify CONTEXT.md's claims against current source and surface what has drifted or is missing.
Four load-bearing findings came out of that verification that CONTEXT.md's canonical refs do not
mention:

1. **`write_grant.record_send_outcome` (the ceiling-breach consumer) has ZERO production
   callers today.** It is invoked only by `test_write_grant.py:1507`. No lane skill, no
   `dispatch_plan` caller, nothing wires a real outcome into it. Wiring the producer (this
   phase's job) also means wiring the *caller* of `record_send_outcome` for the first time.
2. **`written_records.classify_item` discards `row_id`.** The response item it reads
   (`item.get("action")`, `.get("hs_object_id")`, `.get("object_type")`, `.get("reason")`)
   carries a `row_id` field (verified: `scripts/build_cloud_workflows.py:1705,3439,4982`), but
   `written_records.py:161-182`'s built entry never reads it. `run_manifest`/`run_state`
   (AFTER-01's other half) are keyed by `row_id`, not `hs_object_id`. **There is today no
   reliable join key between the two stores AFTER-01 must combine**, and the field most needed
   for the join (held rows, which need a name) is exactly the field `hs_object_id` is null for.
3. **The backend emits 10 distinct `action` values, not the 9 D-57-03's table accounts for.**
   `enrich` (a genuine write, alongside `create`/`update`) has no row in D-57-03's outcome
   table. Separately, `report_enrichment.py`'s own `_ACTION_TO_OUTCOME` (a second, older
   outcome-vocabulary reader) maps only 6 of the 10 values — `update`, `review`,
   `research_failed`, `recompute_refused` all render as `"unknown"` there today, uncovered by
   any test.
4. **`held_queue.py`'s `hold_code` is a validated, closed, two-stage vocabulary
   (`confidence.ALL_HOLD_CODES`) built for per-row *confidence* holds, not run-level *budget*
   holds.** Its `fingerprint()` requires a `preingest.Outcome`-shaped object
   (`.match_tier`/`.candidate_count`); a ceiling-breach row was never assessed by
   `confidence.assess()` and has no such object. Reusing the file's *storage idiom*
   (`durable_paths._atomic_write_0600`, single global file, forbidden-name scan) is cheap;
   reusing its *entry schema* is not — see "Don't Hand-Roll" and the Architecture Patterns
   section for the concrete alternative (`chunking.failed_batch`'s existing shape).

**Primary recommendation:** Wire the ceiling check at BOTH ends the evidence points to — a
pre-flight refusal in `write_grant.envelope()`/`plan_grant()` (RUN-05, reusing
`n8n_cadence.check_budget_floor`'s refuse-with-arithmetic shape and `n8n_read.executions_in_window`
for the "what's left this month" sample the code today hardcodes to `False`), and a mid-run
breach hook inside `chunking.dispatch_plan`'s existing per-chunk loop (a new keyword parameter,
never `grant` — that name is pinned unavailable by
`test_write_grant.py:1455-1463`). Represent the mid-run remainder as a
`chunking.failed_batch()`-shaped spec, not a `held_queue.py` entry — the schemas do not fit.
Widen `written_records.classify_item` to add `row_id` in the same edit that widens its outcome
vocabulary (D-57-03), since AFTER-01 cannot join the two stores without it.

## Project Constraints (from CLAUDE.md)

CLAUDE.md is this project's checked-in build spec (the HubSpot/n8n enrichment system), not a
generic style guide. The directives below are the ones with direct bearing on this phase's scope
— treat with the same authority as a locked decision:

- **§13.0.3 platform facts must be cited with their evidence tag, never upgraded.** Anything
  labelled `[documented]` (e.g. the sub-workflow metering exemption) is "not verified against
  billing"; anything `[observed live]` is this repo's own proof; a `[measured]` figure (P-10's
  over-statement) is a specific number from a specific execution, not a general law. Any ceiling
  arithmetic this phase writes must carry the correct tag.
- **"Never hand-edit the [workflow] JSON" (recurring, e.g. §13.0.1, §13.0.2).** Every change to
  `n8n/wf_enrichment_cloud.json` or `n8n/wf_scheduled_maintenance_cloud.json` must go through
  `scripts/build_cloud_workflows.py`, regenerated, never edited by hand. G-4's ZoomInfo fix (if
  any code change proves necessary after a live re-probe) must land there.
- **"One implementation of a rule" (§13.0.1's closure, restated in CONTEXT.md's own Established
  Patterns).** The remainder queue must not become a second, driftable copy of `held_queue.py`'s
  hold-reason concept; reuse the storage idiom, not a parallel vocabulary.
- **MVP write-governance boundaries (§29) are unrelated to this phase's own writes.** This phase
  writes no new HubSpot properties and adds no canonical-write path; §29's `numberofemployees`
  exception and its "never write automatically" list are not touched by anything here — noted so
  a reader does not conflate this phase's ceiling/ledger work with a canonical-field change.
- **Security/audit discipline established elsewhere in CLAUDE.md (§21-23) — Safety Gates and
  Audit Strategy — already names `MAX_RECORDS_PER_SCHEDULED_RUN` and per-run cost ceilings as a
  design intent.** This phase is the first place those intents get an actual enforcement
  mechanism for the interactive/on-demand path (the scheduled path's own ceiling,
  `max_records_per_chunk`, is unrelated and already enforced).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pre-flight ceiling refusal (RUN-05) | Client (plugin, Python) | — | `write_grant.envelope()`/`plan_grant()` already compute the arithmetic client-side; the backend has no concept of "this batch's ceiling" |
| Mid-run breach detection (D-57-01) | Client (plugin, Python) | — | The client is the only party that sees every chunk's response in sequence (`chunking.dispatch_plan`'s loop); the backend has no cross-chunk state |
| Execution-allowance sampling | Client (plugin, Python) via n8n Cloud REST API | n8n Cloud (data source only) | `n8n_read.executions_in_window` already reads `/api/v1/executions`; n8n exposes no usage/quota endpoint, so "remaining this month" is sampled, never authoritative |
| Provider balance reads (G-4) | n8n Cloud workflow (backend) | Client (reads the backend's report) | Credit balances are read by the deployed `Status Credit Request`/`ZoomInfo Usage` etc. nodes over each provider's own API; the client never calls a provider directly (`cost_guard.fetch_balances` reads the n8n status endpoint, not Apollo/ZoomInfo/Lusha) |
| Written-outcome vocabulary (D-57-03) | Client (plugin, Python) | n8n Cloud (source of the `action` field) | The backend emits `action`; `written_records.classify_item` and `report_enrichment._ACTION_TO_OUTCOME` are the two client-side readers that must agree on what it means |
| Remainder queue storage (D-57-04) | Client (plugin, Python, durable disk) | — | Mirrors `held_queue.py`/`run_manifest.py`/`written_records.py`, all client-side durable artifacts; the backend holds no cross-run state |
| Grant authority (unchanged, GRANT-06) | Client (in-conversation memory only) | — | Never persisted; a ceiling breach closes the grant object in memory, same as every other GRANT-04 reason |

## Standard Stack

No new libraries. This phase adds no dependency to `requirements.txt` (there is none for the
plugin — it is stdlib + `requests`, already installed) or to `operator-claude-plugin/` at all.

### Package Legitimacy Audit

**Not applicable.** This phase installs no external packages in any ecosystem. Skip the gate.

## Architecture Patterns

### System Architecture Diagram

```
                    OPERATOR: "enrich these 340 companies"
                                    |
                                    v
                     write_grant.plan_grant()  <-- RUN-05 lives here
                     (computes envelope() arithmetic:
                      chunk_count, projected_executions,
                      provider credits, Anthropic $)
                                    |
                     [NEW] compare projected_executions
                     against (configured_allowance -
                     n8n_read.executions_in_window sample)
                                    |
                    +---------------+----------------+
                    | over ceiling?                  | within ceiling?
                    v                                 v
        REFUSE, offer a smaller batch      operator says yes -> open_grant()
        (arithmetic shown, RUN-05)                    |
                                                        v
                                    chunking.plan_chunks() -> ChunkPlan
                                                        |
                                                        v
                          chunking.dispatch_plan()  <-- D-57-01 mid-run
                          loops chunks[0..N]              hook lives here
                                    |
                    for each chunk:
                      1. POST to n8n webhook
                      2. written_records.append_chunk(run_id, index, body)
                      3. [NEW] running-tally check against ceiling
                         -> breach? stop sending; remaining
                            chunks become a failed_batch()-shaped
                            "remainder" spec, NOT a held_queue entry
                      4. run_manifest / run_state verdict recorded
                      (caller composes 3 and 4 today; not wired
                       into dispatch_plan itself)
                                    |
                                    v
              [NEW] write_grant.record_send_outcome(grant,
                    {"ceiling_breach": True}, config)
                    -> closes grant with CLOSED_CEILING_BREACH
                    (consumer already exists: write_grant.py:667,932-933;
                     zero production callers today)
                                    |
                                    v
                    run completes (D-59-06: never aborts mid-batch)
                                    |
                                    v
              AFTER-01 report: JOIN written_records (by run_id,
              needs row_id added) + run_state.read_progress
              (by run_id, row_id) + held_queue (global, by run_id
              tag) + the remainder queue (by run_id)
```

### Recommended Project Structure

No new files are structurally required; this phase is additive to existing modules. If the
remainder queue is built as a sibling store (the evidence below recommends this over folding
into `held_queue.py`), it is one new file following the existing five-artifact family's exact
shape:

```
operator-claude-plugin/scripts/
├── write_grant.py       # ADD: pre-flight ceiling refusal in envelope()/plan_grant();
│                         #      a producer that calls record_send_outcome() with
│                         #      ceiling_breach=True — currently nothing calls it
├── chunking.py           # ADD: mid-run breach hook inside dispatch_plan's loop
│                         #      (a new kwarg, never named `grant` — see below)
├── written_records.py    # WIDEN: classify_item's outcome vocabulary (D-57-03) AND
│                         #        add row_id to the entry (undocumented gap found this
│                         #        session — needed for AFTER-01's join)
├── report_enrichment.py  # WIDEN (or flag as a residual): _ACTION_TO_OUTCOME is missing
│                         #        4 of 10 action values; a second vocabulary surface
├── remainder_queue.py    # NEW (if "beside", not "in", held_queue — see discretion below):
│                         #      same durable_paths._atomic_write_0600 idiom, entries shaped
│                         #      like chunking.failed_batch() output, not held_queue entries
└── (AFTER-01 report)     # NEW: a function/script that joins written_records + run_state +
                          #      held_queue + the remainder queue by run_id
```

### Pattern 1: Refuse-with-arithmetic, never a silent guess

**What:** `n8n_cadence.check_budget_floor` (verified: `operator-claude-plugin/scripts/n8n_cadence.py:452-491`)
raises `CadenceRefused` when a scheduling change would bust a configured share of the plan
allowance, and its docstring states the order explicitly: a missing config key refuses first
(never overridable), an over-budget request refuses unless `override=True` (in which case it
returns the arithmetic with `overridden: True`).

**When to use:** RUN-05's refusal is the same shape — refuse, show the arithmetic, offer a
smaller batch. This is the one existing precedent for "refuse before starting" in this codebase;
follow its branch order (missing-config-refuses-first, then over-budget-refuses) rather than
inventing a new one.

**Example:**
```python
# Source: operator-claude-plugin/scripts/n8n_cadence.py:452-491 (verified this session)
def check_budget_floor(workflow_id, node_name, interval, config, workflow_items,
                       override=False):
    allowance = _read_positive_float(config, n8n_read.EXECUTION_ALLOWANCE_KEY)
    if allowance is None:
        raise CadenceRefused(
            f"the config key {n8n_read.EXECUTION_ALLOWANCE_KEY!r} is missing, blank or "
            "not a positive number ... so the change is refused rather than guessed at.",
            _BUDGET_SAFE_EXAMPLES)
    # ... requested_cost vs allowance, refuse unless override=True ...
```

### Pattern 2: Honest sampling of "what's left this month"

**What:** `n8n_read.executions_in_window` (verified: `operator-claude-plugin/scripts/n8n_read.py:258-381`)
already walks a bounded page of `/api/v1/executions`, returning `count_in_window`,
`covers_full_window`, and `truncated_by_page_cap` — the exact tri-state honesty
`write_grant.envelope()`'s `remaining_allowance_sampled: False` (hardcoded, verified:
`write_grant.py:261`) is waiting for.

**When to use:** RUN-05's "against what is left of it this month" (`_ALLOWANCE_GAP`, verified:
`write_grant.py:143-148`) is unbuilt specifically because nothing samples the month-to-date
count. `executions_in_window(config, window_hours=<hours since UTC month start>)` is that
sample. **Constraint discovered this session:** the walk is capped at `MAX_EXECUTION_PAGES = 4`
pages of `EXECUTIONS_WINDOW_PAGE_LIMIT = 250` (verified: `n8n_read.py:69,73`) — 1,000 executions
across ALL workflows on the instance, not just the enrichment lane. Near month-end on a busy
account this cap can be hit before reaching the full month
(`truncated_by_page_cap: True`, `covers_full_window: False`), in which case the sample
under-covers the month and the honest answer is a shorter `observed_span_hours`, not a false
"nothing spent yet."  The projection built on this sample must disclose the same tri-state the
function already returns — never silently treat a truncated sample as a complete one.

### Pattern 3: The dispatch loop is a single Python call across every chunk

**What:** `chunking.dispatch_plan` (verified: `chunking.py:317-451`) iterates `plan.chunks` in
one call — every existing caller (`preingest.py:713`, `scheduled_arm.py:234-235`, both lane
`SKILL.md`s) invokes it ONCE with the whole plan, never per-chunk. There is no "call it once per
chunk and reconcile between calls" pattern anywhere in this codebase today.

**When to use:** This is the deciding evidence for "where mid-run breach detection lives"
(Claude's Discretion in CONTEXT.md). Two real options, with their real costs:

- **A — a running tally inside `dispatch_plan`'s own loop.** Add a keyword parameter (e.g.
  `ceiling=` or a callback), checked after each chunk's `written_records.append_chunk` call
  (line 428 in the current loop), that can `break` the `for` loop early. This is a small,
  contained change and does NOT touch the pinned-unavailable `grant` parameter name
  (`test_write_grant.py:1455-1463` only forbids a parameter literally named `grant`). The
  loop's `for` structure supports an early `break` cleanly — `results`/`responses`/
  `written_records_failures` are already accumulated incrementally, so a `DispatchOutcome`
  built at break time is structurally identical to one built at natural completion, with a new
  field naming the chunks that never got sent.
- **B — post-chunk reconciliation between separate `dispatch_plan` calls.** Would require
  restructuring every existing caller to invoke `dispatch_plan` once per chunk instead of once
  per plan — a change to `preingest.py`, `scheduled_arm.py`, and both lane `SKILL.md`s, for a
  benefit (keeping `dispatch_plan` itself simpler) that option A already gets for free with a
  much smaller diff.

Option A is the lower-cost fit given the evidence; it does add one new thing `dispatch_plan`
does not do today (stop mid-loop for a non-error reason), which is worth flagging explicitly to
the operator/reviewer since D-59-06's "run continues to completion" contract has, until now,
only ever meant "never abort on a recoverable per-chunk failure" — a deliberate budget-driven
stop is a new, different kind of early exit and should be named as such in the plan, not folded
into the existing D-59-10/D-11b failure vocabulary.

### Pattern 4: The remainder should be a `failed_batch`-shaped spec, not a `held_queue` entry

**What:** `chunking.failed_batch()` (verified: `chunking.py:494-517`) already turns a list of
unsent/failed chunk dicts back into ONE well-formed record specification
(`{record_ids: [...], object_type: ...}` or the `rows`/equivalent shape) that the SAME dispatch
path accepts unmodified. `held_queue.py`'s entry schema (verified: `held_queue.py:174-183`)
requires a `hold_code` from `confidence.ALL_HOLD_CODES` (verified: `confidence.py:74-77`, a
CLOSED set built for per-row confidence holds) and a `resume_fingerprint` computed from a
`preingest.Outcome`'s `.match_tier`/`.candidate_count` (verified: `held_queue.py:154-167`) — a
row that never reached a match/confidence assessment (it was simply never dispatched because the
ceiling was hit) has neither.

**When to use:** D-57-04's queued remainder ("auto-splits across runs... queues the remainder")
is structurally the SAME shape `failed_batch()` already produces — a specification of records
not yet sent, re-sendable through the identical armed-dispatch path. **Recommendation for the
planner to weigh (not decided here, per CONTEXT's discretion):** store the remainder as a
`failed_batch()`-shaped spec in a NEW small file using `held_queue.py`'s durable-write idiom
(`durable_paths._atomic_write_0600`, one global or one-per-run file, the same forbidden-name
scan) — reusing the STORAGE PATTERN, never the ENTRY SCHEMA. Forcing a ceiling-breach remainder
through `confidence.ALL_HOLD_CODES` would mean either (a) adding a hold code that
`confidence.assess()` itself never produces, breaking the module's own stated invariant that the
enrichment/match-stage split is total over codes `assess()` can emit, or (b) synthesizing a fake
`preingest.Outcome` for `fingerprint()` to hash, which has no real match-tier/candidate-count to
report. Both are worse than a second small file following the same idiom.

### Anti-Patterns to Avoid

- **Do not name a `dispatch_plan` parameter `grant`.** `test_write_grant.py:1455-1463`
  (`test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against`) asserts `"grant" not in
  inspect.signature(chunking.dispatch_plan).parameters` — a ceiling-related parameter (e.g.
  `ceiling=`, `record_send_outcome_cb=`) is fine; a parameter literally named `grant` will fail
  a test whose purpose is unrelated to ceilings (it pins GRANT-05's chunk-granularity limit) and
  whose failure would be confusing to debug.
- **Do not read `write_grant.EXECUTIONS_BASIS`'s `chunk_count + record_count` formula as
  exact.** `write_grant.py:265-270` documents it was relabelled `PROJECTED` (from a stale
  `MEASURED`) specifically because Phase 54 found no code path anywhere reads back real
  Anthropic usage, and `61-SPIKE-VERDICT.md`'s P-10 measured a real 2-record chunk
  (execution `11950`) projecting 3 executions against a listed 1 — an over-statement of roughly
  3x. `run_state.py:172-180`'s `SPEND_BASIS` string carries this caveat forward verbatim; any new
  ceiling arithmetic quoting this formula must carry the same caveat, not present it as exact.
- **Do not treat the n8n executions-API list as the billing quota.** CLAUDE.md §13.0.3
  (verified in the project's checked-in CLAUDE.md, quoted in `<additional_context>` above) is
  explicit: "The executions API list is not the billing quota. No API key available to this repo
  can observe billing." Every figure `n8n_read.executions_in_window` returns is what the API
  *listed*, never a confirmed billed count.
- **Do not assume the sub-workflow metering exemption when computing a ceiling.** CLAUDE.md
  §13.0.3 tags "sub-workflow executions are documented as neither billed nor concurrency-capped"
  as `[documented]`, explicitly "not verified against billing." Any ceiling arithmetic that
  relies on this exemption (e.g. to argue a fan-out costs less) must carry the same
  `[documented, unverified]` caveat.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Refuse-before-spend with arithmetic | A new refusal helper | `n8n_cadence.check_budget_floor`'s shape (refuse-first-on-missing-config, then refuse-on-over-budget, return arithmetic) | Only existing precedent in this codebase for exactly this behaviour |
| Sampling "spend so far this month" | A new executions-API walker | `n8n_read.executions_in_window` | Already handles pagination, in-flight retention, honest truncation reporting — exactly what `write_grant.envelope()`'s `remaining_allowance_sampled: False` is waiting for |
| Durable, atomic, 0600 artifact writes | A new file-write helper | `durable_paths._atomic_write_0600` | Every one of the five existing artifact stores (`artifact_store`, `run_manifest`, `written_records`, `held_queue`, `run_state`) already uses this; a sixth store (the remainder queue) should too |
| A re-sendable record specification for unsent rows | A new "remainder" shape | `chunking.failed_batch()` | Already turns a list of chunks back into one well-formed spec `dispatch_plan` accepts unmodified; D-57-04's remainder is structurally the same problem |
| Forbidden-name scanning before a disk write | A new scanner | The `_FORBIDDEN_NAME_MARKERS` idiom, reimplemented per-module by design (`written_records.py`, `held_queue.py`, `run_state.py` each carry their own copy, deliberately not imported from one shared list — see each module's own docstring for why) | A future change to one list must not silently weaken another; this is a deliberate anti-DRY choice already established in this codebase, not an oversight to fix |
| A disarmed live-proof harness | A new proof script from scratch | `scripts/prove_async_recovery.py`'s shape (a dedicated `ALLOW_<NAME>_PROOF` env-var gate read EXACTLY as `"true"`, an instance-URL guard mirroring `deploy_n8n_workflows.py::_instance_ok()`, `mode: "propose"` + `providers: []` to make writes/spend structurally impossible) | Exact template for any Phase 57 disarmed proof that needs to touch the real n8n instance |

**Key insight:** Every piece of machinery this phase needs already exists in some form
elsewhere in the repo — the work is almost entirely wiring two ends of an existing, tested
consumer (`record_send_outcome`) to a producer that has never been written, and reconciling two
outcome-vocabulary readers (`written_records.classify_item`, `report_enrichment._ACTION_TO_OUTCOME`)
that have quietly drifted apart. A custom solution anywhere in this phase is very likely
duplicating something that already has a docstring explaining why it was built the way it was.

## Common Pitfalls

### Pitfall 1: Believing `record_send_outcome`'s test coverage means the feature is wired

**What goes wrong:** `test_write_grant.py:1507`
(`test_a_ceiling_breach_closes_the_grant_rather_than_continuing`) passes today and calls
`write_grant.record_send_outcome(grant, {"ceiling_breach": True}, config)` directly. It is easy
to read this green test as evidence the breach-close path is live end-to-end.
**Why it happens:** The test exercises the CONSUMER in isolation, exactly as CONTEXT.md says
("already accepted... already tested. This phase writes the producer"). Grep for
`record_send_outcome(` in non-test files (verified this session) returns zero hits.
**How to avoid:** Any plan for this phase must add BOTH the producer (something that computes
`ceiling_breach: True` and calls `record_send_outcome`) AND, separately, verify that call site
is reached from a real dispatch path (a lane `SKILL.md`'s dispatch step, or `dispatch_plan`
itself) — not just that the function accepts the argument correctly in isolation.
**Warning signs:** A plan whose only verification step is "the existing unit test still passes"
without a new integration-level test that drives an actual over-ceiling dispatch through the
real call chain.

### Pitfall 2: Widening `classify_item`'s outcome vocabulary without widening its entry shape

**What goes wrong:** D-57-03 asks for the outcome WORDS to widen (`gated`/`held`/`failed`/
`no_action` etc). It is easy to treat this as a pure string-mapping change and miss that
`row_id` — needed by AFTER-01 to join this artifact against `run_state`/`run_manifest` — is
already available on the same `item` dict `classify_item` reads and is simply never captured.
**Why it happens:** `classify_item`'s docstring (verified: `written_records.py:131-149`)
describes the function purely in terms of the outcome classification; it does not mention
`row_id` at all, so a reader focused on the D-57-03 table has no cue to look for it.
**How to avoid:** Any plan touching `written_records.classify_item` should add `row_id` to the
entry in the same edit, and note the schema version bump this implies for the per-run JSON file
(existing runs' `written_records-<run_id>.json` files will not have it — degrade gracefully on
read, per every other artifact's own established "missing/malformed -> empty, never partial
trust" rule).
**Warning signs:** A plan that touches `written_records.py`'s outcome constants but not its
`entry = {...}` dict at lines 176-182.

### Pitfall 3: Assuming `report_enrichment.py`'s vocabulary already agrees with `written_records.py`'s

**What goes wrong:** Both modules independently map the same `action` field to a
human-readable word. `written_records.WRITE_ACTIONS` (verified: `written_records.py:96`) treats
`enrich` as a write action; `report_enrichment._ACTION_TO_OUTCOME` (verified:
`report_enrichment.py:38-49`) has NO entry for `update`, `review`, `research_failed`, or
`recompute_refused` — falling through to `.get(action, "unknown")`. A plan that widens ONE
reader's vocabulary and assumes the operator-facing report (`report_enrichment.py`, used by
`enrich-records/SKILL.md` step 9's live-execution report path) automatically reflects it will
ship an inconsistency: two different words for the same backend `action` depending on which
report surface the operator reads.
**Why it happens:** The two modules read the same field from two different transports
(`written_records` from the synchronous dispatch response; `report_enrichment` from the
executions API's stored `runData`) and were built in different phases, so there is no shared
constant between them today.
**How to avoid:** Decide explicitly whether this phase also widens `report_enrichment.py`'s
table (in scope, since it's the same underlying vocabulary gap) or files it as a named residual
for a later phase — but do not silently leave it unmentioned, since AFTER-01/AFTER-03 are about
exactly the outcomes this table currently renders as `"unknown"`.
**Warning signs:** A plan that edits `written_records.py` but never mentions
`report_enrichment.py`.

### Pitfall 4: Treating a truncated `executions_in_window` sample as "nothing spent"

**What goes wrong:** Near the end of a busy month, `executions_in_window`'s 1,000-execution page
cap can be reached before the walk reaches the start of the month
(`truncated_by_page_cap: True`, `covers_full_window: False`) — see Pattern 2 above. A ceiling
computation that reads `count_in_window` without checking `covers_full_window` first will
under-count spend and over-state remaining headroom in exactly the scenario where an accurate
count matters most (a nearly-exhausted allowance).
**Why it happens:** The happy-path fields (`count_in_window`) are easy to reach for; the honesty
fields (`covers_full_window`, `truncated_by_page_cap`) require reading the function's full
return shape.
**How to avoid:** Any RUN-05 refusal computation built on this sample must check
`covers_full_window` and disclose (never silently ignore) a truncated sample — the same
tri-state discipline `write_grant.envelope()` already applies to provider balances
(`_headroom()`, verified: `write_grant.py:167-174`).
**Warning signs:** Code that reads `window["count_in_window"]` without also reading
`window["covers_full_window"]`.

### Pitfall 5: Confusing a deliberate ceiling stop with an existing failure class

**What goes wrong:** `chunking.dispatch_plan`'s existing failure handling (D-11b's timeout
handling, D-59-10's written-records bookkeeping-failure handling) all describe *unwanted*
outcomes the loop recovers from and continues past. A mid-run ceiling breach is different: it is
a *deliberate*, budget-driven stop that D-57-01 requires ("spending stops"). Folding it into the
existing `failed_chunks`/`ChunkResult(ok=False, ...)` vocabulary would make an intentional stop
indistinguishable from an unintentional one in `outcome.results`, and downstream code
(`preingest.merge_enriched`, lane `SKILL.md` reporting steps) that branches on `ok`/`reason`
would report it as a backend error rather than a budget decision.
**Why it happens:** The existing `ChunkResult` dataclass (verified: `chunking.py:88-108`) has
exactly one failure shape (`ok: bool, reason: str`); a ceiling stop is tempting to represent the
same way since the plumbing already exists.
**How to avoid:** Give the ceiling stop its own field on `DispatchOutcome` (mirroring how
`written_records_failures` got its own field rather than being folded into `failed_batch`, per
D-59-10's own precedent at `chunking.py:134-148`), naming which chunks were never attempted
because of the breach, distinct from chunks that were attempted and failed.
**Warning signs:** A plan that represents a ceiling breach purely by adding entries to
`failed_chunks`/`failed_batch()`.

## Code Examples

### The consumer this phase must wire a producer to
```python
# Source: operator-claude-plugin/scripts/write_grant.py:899-949 (verified this session)
def record_send_outcome(grant, outcome, config=None, *, transport=None):
    """..."""
    updated = copy.deepcopy(grant if isinstance(grant, dict) else {})
    outcome = outcome if isinstance(outcome, dict) else {}

    verdict = (outcome.get("disarm") or {}).get("outcome")
    if verdict == n8n_arming.DISARMED:
        updated["consecutive_disarm_failures"] = 0
    elif verdict == n8n_arming.DISARM_FAILED:
        updated["consecutive_disarm_failures"] = \
            int(updated.get("consecutive_disarm_failures") or 0) + 1

    if outcome.get("ceiling_breach"):
        return close_grant(updated, CLOSED_CEILING_BREACH)
    # ... guardrail B's own two disarm-failure paths follow ...
```
`CLOSED_CEILING_BREACH = "ceiling_breach"` at `write_grant.py:667`; the caller supplies the
truthy `ceiling_breach` key. Verified: `grep -rn "record_send_outcome(" operator-claude-plugin/`
returns exactly two hits, both inside `write_grant.py` itself (the definition and the
`ceiling_breach` branch) plus test-only call sites — zero production callers.

### The dispatch loop's per-chunk hook point (Pattern 3's option A)
```python
# Source: operator-claude-plugin/scripts/chunking.py:373-444 (verified this session, excerpted)
for index, chunk in enumerate(plan.chunks):
    rows = plan.row_counts[index]
    watcher = _StatusCapturingTransport(transport)
    try:
        envelope = enrichment.build_envelope(chunk, providers)
        # ... async_ack / scale_up flags ...
        body = enrichment.dispatch_enrichment(envelope, armed, config, transport=watcher)
    except NotArmedError:
        raise
    except DispatchError:
        # ... records ChunkResult(ok=False), continues loop ...
        continue
    # ... success path: append to results/responses ...
    try:
        flushed = written_records.append_chunk(run_id, index, body)
    except written_records.WrittenRecordsError as e:
        flushed = False
        # ... never stops the loop (D-59-10) ...
    # <-- a running-tally ceiling check would read `body`/`chunk_index` here,
    #     and could `break` the for loop, distinct from the existing continue-on-failure paths
```

### The action vocabulary the backend actually emits (verified this session, not assumed)
```
$ grep -noE "action['\"]?\s*[:=]\s*['\"][a-zA-Z_]+['\"]" scripts/build_cloud_workflows.py \
  | sed -E "s/.*['\"]([a-zA-Z_]+)['\"]$/\1/" | sort -u
create
enrich
needs_match_review
proposed
recompute_refused
research_failed
review
skip
update
write_blocked
```
Cross-checked against D-57-03's table: `create`, `update`, `write_blocked`, `review`,
`needs_match_review`, `research_failed`, `recompute_refused`, `skip`, `proposed` (9 values) map
cleanly. **`enrich` has no explicit row** — it is a write action per
`written_records.WRITE_ACTIONS = frozenset({"update", "enrich", "create"})` (`written_records.py:96`)
and must map to `written` (with an id) exactly as `update` does, not fall through to a default.

### The provider-balance root causes (G-4), verified against current code
```python
# Source: n8n/code/providerSelection.js:76-106 (verified this session)
if (p === "apollo") {
    // THIS account's key 403s (non-master) [VERIFIED: live curl 403] -> raw carries no
    // `remaining` field -> null. ...
    return (raw && typeof raw.remaining === "number") ? raw.remaining : null;
}
```
```python
# Source: scripts/provider_registry.py:26-33 (verified this session)
"apollo": {
    "credit": {
        "method": "POST", "url": "https://api.apollo.io/api/v1/usage_stats/api_usage_stats",
        "auth": "header", "header": "X-Api-Key", "path": None,  # 403 w/o master key -> null
    },
},
```
**Apollo cannot be fixed by this phase.** The account's Apollo API key is structurally not a
"master" key, and Apollo's `usage_stats` endpoint 403s for any non-master key by design (per the
code's own live-curl-verified comment). Fixing this requires a different Apollo credential
(a master-tier key), an account-level change outside this repo's control — not a code fix.

```python
# Source: scripts/build_cloud_workflows.py:4614-4630 (verified this session)
res = await this.helpers.httpRequest({
    method: "GET", url: USAGE_URL,
    headers: { Authorization: "Bearer " + token, Accept: "application/vnd.api+json" },
});
```
**The historical "ZoomInfo needs `Accept: vnd.api+json`" fix (recorded in this project's own
memory) is ALREADY present in the current code.** The header is set. G-4's live UAT (2026-08-25)
observed `provider_error`, which per `ENRICH_STATUS_BUILD_RESPONSE`'s own logic
(`build_cloud_workflows.py:6354-6362`, `error = status ? "http_"+status : "provider_error"`)
means the HTTP request itself errored (not merely returned a shape `extractCredits` couldn't
parse — that path yields `unrecognized_response_shape` instead, a DIFFERENT label). **This
cannot be fixed by inspecting code alone** — the 2026-08-25 observation predates or postdates an
unknown set of token-mint/cache changes in the same file (`ZoomInfo Usage Token Gate`/`Mint`/
`Cache Token` subgraph, `build_cloud_workflows.py:4163-4184`), and the root cause (an expired
mint, a stale cached token, a genuine transient 5xx) can only be distinguished by a live re-probe
against the real n8n instance. Flag this explicitly as needing a live credential probe, not a
code change, before claiming G-4 "fixed" for ZoomInfo.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A new `chunking.dispatch_plan` keyword parameter (not named `grant`) for a ceiling hook will not collide with any other pinned-signature test besides `test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against`. Only that one test was found via search; a broader signature-freezing test elsewhere was not exhaustively ruled out beyond grepping `inspect.signature(chunking.dispatch_plan)` across the test suite. | Architecture Patterns, Pattern 3 | A planned parameter addition could break an unfound test; low risk, cheap to discover at plan-checker/execution time |
| A2 | `report_enrichment.py`'s 4-of-10 action-vocabulary gap (`update`/`review`/`research_failed`/`recompute_refused` -> `"unknown"`) is a genuine, currently-uncovered defect rather than a deliberate scope boundary with a test elsewhere asserting it. No test asserting exactly these 6 keys was found in `test_report_enrichment.py`, but the full test suite for that file was not read exhaustively. | Common Pitfall 3 | If deliberate, flagging it as a gap would send the planner chasing a non-issue; low cost either way since the finding is presented as "verify before deciding scope," not as a mandate |
| A3 | The ZoomInfo `provider_error` observed in the 2026-08-25 UAT (G-4) is NOT explained by the missing-Accept-header cause recorded in this project's own memory file, because the header is present in current code. The TRUE current cause was not independently re-probed live this session (no live credential access in this research task). | Code Examples, provider-balance root causes | If the header fix actually landed AFTER 2026-08-25 and the UAT observation is now stale, G-4 may already be silently resolved and only need re-verification, not a code fix — the planner should re-probe live before writing a fix task |

**All other claims in this document were verified this session by reading the cited file at the
cited line range, or by running a grep/search this session and quoting its literal output.**

## Open Questions

1. **Does `written_records.classify_item`'s widening (D-57-03 + the `row_id` gap found this
   session) need a schema version field, given existing per-run JSON files on disk lack it?**
   - What we know: `written_records.py`'s `_entries_from_document`/`load()` already degrade a
     malformed/schema-mismatched document to an empty result per-file, never partial trust
     (verified: `written_records.py:207-219`). A pre-widening file simply has fewer keys per
     entry; readers that only look up `outcome`/`action` by key will not break on it.
   - What's unclear: whether AFTER-01's report needs to distinguish "this row predates the
     widening" from "this row's row_id/wider-outcome genuinely could not be determined."
   - Recommendation: treat a missing `row_id` on an old entry as `None` (unjoinable), same as
     any other absent-field discipline in this codebase; no version field needed unless the
     planner finds a concrete reason one is required.

2. **Should the mid-run ceiling check use a running SUM of the `write_grant.EXECUTIONS_BASIS`
   formula (chunk_count + record_count, known to over-state ~3x per P-10) as its comparison
   basis, or something else?**
   - What we know: it is the ONLY formula this codebase has for projecting n8n execution cost;
     `run_state.spend_against_ceiling` already reuses it verbatim rather than deriving a second
     one (verified: `run_state.py:172-180`).
   - What's unclear: whether an over-stating formula used as a REFUSAL trigger (rather than a
     disclosure) risks false-positive refusals — refusing a batch that would actually have fit.
   - Recommendation: given D-57-01's own reasoning ("nothing found suggests it ever
     under-projects... pre-flight refusal is conservative rather than permissive"), an
     over-stating formula is the SAFE direction for a refusal (it can only refuse too early,
     never let an over-budget batch through) — but this should be stated explicitly in the plan
     as a deliberate, disclosed conservative bias, not left implicit.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud REST API (`/api/v1/executions`, `/api/v1/workflows`) | RUN-05's month-to-date sample, mid-run breach detection | ✓ (code already calls it via `n8n_read.py`) | Starter plan, 5 concurrent / 2,500 executions/month (CLAUDE.md §13.0.3) | none — this is the only source of execution-count data; no usage/quota endpoint exists |
| Apollo `usage_stats` API | G-4 balance read | ✗ (403, non-master key, structural) | — | none available to this repo; requires an Apollo account-level credential change outside this phase's scope |
| ZoomInfo `gtm/data/v1/users/usage` API | G-4 balance read | UNKNOWN — code is correct (Accept header present); live behaviour not re-probed this session | — | disclose as an explicit blind spot per D-57-02 if re-probe still fails; no code fallback known |
| Lusha `v3/account/usage` API | G-4 balance read (already working) | ✓ (`credits.remaining`, verified path in `provider_registry.py:23`) | — | — |
| Anthropic usage/token readback | Any attempt to make the `$` ceiling figure MEASURED rather than PROJECTED | ✗ | — | none — `write_grant.py:265-270` documents no code path in this repo reads back real Anthropic usage; out of scope for this phase per CONTEXT's "Reviewed Todos" note |

**Missing dependencies with no fallback:**
- n8n's month-to-date execution count must be SAMPLED (via `executions_in_window`), never read
  authoritatively — there is no usage endpoint. This is a permanent constraint, not a gap to close
  in this phase.
- Apollo's balance cannot be read with the current credential; fixing it needs an account change,
  not code.

**Missing dependencies with fallback:**
- ZoomInfo's balance: if re-probe confirms `provider_error` persists, D-57-02's "disclose the
  blind spot" is the fallback already designed for exactly this case.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python, `operator-claude-plugin/tests/` and root `tests/`), Node's built-in `node --test` (`tests/n8n/*.test.mjs`) |
| Config file | none committed (`tests/conftest.py` documents there is no `pytest.ini`/`pyproject.toml`/`setup.cfg` `[pytest]` block — verified this session) |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` (plugin-only, fast) |
| Full suite command | `.venv/bin/python -m pytest -q` (root, 3539 passed / 154 skipped as of Phase 61 close per STATE.md) AND `node --test tests/n8n/*.test.mjs` (glob form only — directory form is broken on node 24, per project memory) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Caller Path the Test Must Drive |
|--------|----------|-----------|-------------------|----------------------------------|
| RUN-05 | A batch that would exhaust the allowance refuses BEFORE starting, with arithmetic, offering a smaller batch | unit + integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k ceiling -x` | Must call `write_grant.plan_grant()` or `envelope()` itself (the real refusal path an operator's request reaches) — NOT a bare arithmetic-comparison helper tested in isolation. Phase 59's lesson (ROADMAP.md:168-180): a test that only exercises the comparison function, never the function an operator's request actually calls, passes green while the real path stays unwired. |
| D-57-01 (mid-run breach) | Spending stops mid-batch; remainder held; run completes; grant closes `ceiling_breach` | integration | A REAL multi-chunk `chunking.dispatch_plan()` call (mirroring `test_write_grant.py::test_a_revocation_midway_does_not_stop_a_running_dispatch`'s existing 3-chunk-dispatch idiom) with a scripted transport that lets the ceiling check detect a breach after chunk N | Must drive `dispatch_plan` itself with `stub_module_transport_factory`, not a hand-built `DispatchOutcome`. Must then assert `write_grant.record_send_outcome(...)` is actually CALLED as a consequence of that dispatch (not just that it accepts the right argument shape when called directly, mirroring the Pitfall 1 finding above). |
| D-57-03 (outcome vocabulary) | Every `action` value maps to the correct one of the widened outcome set, including `enrich` | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -x` (extend with one test per new/reconciled action, including `enrich`) | Direct unit test of `classify_item` is appropriate here — it is a pure function; but ALSO add a `report_enrichment.py` test asserting the previously-unmapped 4 actions (`update`/`review`/`research_failed`/`recompute_refused`) render correctly if that module is in scope for this phase (see Common Pitfall 3). |
| AFTER-01 (end-of-run report) | One report joining per-record outcome, held rows named individually, spend vs ceiling, disarm verdict | integration | A new test driving the actual join function against fixture `written_records`/`run_state`/`held_queue` artifacts on disk (via `tmp_path`, following `test_written_records.py`'s existing `_patch_durable_dir` idiom) | Must assert the join actually FINDS held rows by name — i.e. a fixture entry with an `hs_object_id` of `None` (a held/blocked row) must still appear in the joined report keyed by `row_id`, proving the row_id gap identified in this research was actually closed, not merely that the function runs without error. |
| AFTER-03 (written vs would-have-been) | A gated (`write_blocked`) record must never read as completed | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -k gated` | Assert `classify_item({"action": "write_blocked", ...})["outcome"]` is the NEW `gated` word, not `written`/`not_written`'s old collapse, and that the operator-facing render (`enrich-records/SKILL.md` step 9's relay, or the new AFTER-01 report) uses distinct text for `gated` vs `written`. |
| G-4 (provider balance blind spots) | Report says which balances were readable/unreadable, and improves what's fixable | integration (Apollo/Lusha: unit against existing fixtures; ZoomInfo: disarmed live re-probe) | `.venv/bin/python -m pytest operator-claude-plugin/tests -k backend_status_unknown_balance` for the existing Apollo-403 fixture (already covers the "disclose, don't fix" case); a NEW disarmed live probe script (following `prove_async_recovery.py`'s gate idiom) for ZoomInfo's actual current behaviour | The unit tests already exist for the disclosure half (`conftest.py:532-547`'s `backend_status_unknown_balance` fixture). The live-probe half must hit the REAL `Status Credit Request` -> `ZoomInfo Usage` chain on the deployed instance, disarmed (no writes needed — this is a read-only credit-check call, already `onError: continueRegularOutput` per `_credit_http_node`'s own docstring) — no `mode: propose` gate is even needed since the balance check never writes. |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests -q` (plugin-scoped, fast feedback)
- **Per wave merge:** `.venv/bin/python -m pytest -q` (root, full suite) AND `node --test tests/n8n/*.test.mjs`
- **Phase gate:** Full suite green before `/gsd-verify-work`; the ZoomInfo live-probe result (pass/fail/inconclusive) explicitly reported in the phase summary regardless of outcome, since it may not be resolvable from this repo alone (Assumption A3).

### Wave 0 Gaps
- [ ] No test file currently drives `write_grant.record_send_outcome` from a real dispatch path
      (only the direct-call unit test exists) — Wave 0 should add the integration-shaped test
      described in the D-57-01 row above before any implementation task, so the plan-checker has
      a red test to make green.
- [ ] No test exists asserting `chunking.dispatch_plan`'s current signature does NOT already
      support early termination — worth a quick characterization test confirming the current
      `for` loop always completes all chunks, to make the later "stops early on breach" change's
      diff legible against a known baseline.
- [ ] No fixture exists for a ZoomInfo `provider_error` response shape distinct from
      `unrecognized_response_shape` — `conftest.py`'s existing `_balance()`/`backend_status_*`
      fixtures cover Apollo's 403 case but not a ZoomInfo-specific one; add one if G-4's fix
      needs a regression test.

*(Framework and most fixtures already exist; gaps are additive test cases, not new infrastructure.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | This phase touches no auth surface; grant authority (`config_gate.write_grants_enabled`) is unchanged |
| V3 Session Management | yes (narrowly) | The grant's in-memory-only lifetime (GRANT-06) is a session-scoped authority object; this phase's new close reason (`ceiling_breach`) must close it the same way every other GRANT-04 reason does — no new persistence path may be introduced (verified: `write_grant.close_grant`, `write_grant.py:576-593`, performs no network call and writes nothing to disk) |
| V4 Access Control | yes (narrowly) | The record-scoped allowlist (`covers()`, `write_grant.py:596-658`) must remain untouched by this phase; a mid-run breach must never WIDEN what a partial dispatch was authorized to write, only narrow (stop sending) |
| V5 Input Validation | yes | Every new persisted artifact (a remainder queue, a widened `written_records` entry) must run the same forbidden-name scan (`_FORBIDDEN_NAME_MARKERS`) every sibling artifact already carries — reimplemented per-module by established convention, never imported from a shared list |
| V6 Cryptography | no | No cryptographic operation in scope |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A ceiling-breach remainder accidentally carrying write authority across runs | Elevation of privilege | D-57-05 (derived, hard constraint): the remainder queue holds WORK specs only (record ids/domains, following `chunking.failed_batch()`'s shape), never a grant object or any authority token. Test: a resumed run against a remainder queue entry, with no grant open, must refuse the same way any ungranted send does today. |
| An arming grant, API key, or webhook secret leaking into a new persisted artifact | Information disclosure | Reuse the established `_FORBIDDEN_NAME_MARKERS` scan verbatim (a value shaped like `arm`/`secret`/`api_key`/`token`/`credential`/`password`/`grant`/`permission`/`webhook` refuses the write) in any new store this phase creates |
| A false-negative ceiling check silently letting an over-budget batch through | Denial of service (of the account's monthly allowance) | Prefer the conservative direction the existing `EXECUTIONS_BASIS` formula already has (documented to over-state, never under-state, per P-10) when the mid-run tally and the pre-flight projection disagree |
| A ceiling-breach mid-run stop reported identically to an ordinary chunk failure, hiding the real cause from the operator | Repudiation | Give the breach stop its own field on `DispatchOutcome`, distinct from `failed_batch`/`ChunkResult.ok=False` (Common Pitfall 5) |

## Sources

### Primary (HIGH confidence — read this session)
- `operator-claude-plugin/scripts/write_grant.py` (full file structure, lines 1-278, 560-1029) — envelope, close reasons, guardrails, `record_send_outcome`
- `operator-claude-plugin/scripts/written_records.py` (full file, 323 lines) — outcome vocabulary, `classify_item`, `append_chunk`, `load`
- `operator-claude-plugin/scripts/chunking.py` (full file, 545 lines) — `ChunkPlan`, `dispatch_plan`, `failed_batch`, `chunk_ceiling`
- `operator-claude-plugin/scripts/held_queue.py` (full file, 280 lines) — hold-code vocabulary, fingerprint, save/load
- `operator-claude-plugin/scripts/confidence.py` (lines 1-90) — `ALL_HOLD_CODES`, `ENRICHMENT_STAGE_HOLD_CODES`
- `operator-claude-plugin/scripts/durable_paths.py` (full file, 269 lines) — `_atomic_write_0600`, path resolution
- `operator-claude-plugin/scripts/run_state.py` (full file, 379 lines) — progress buckets, `spend_against_ceiling`
- `operator-claude-plugin/scripts/report_enrichment.py` (full file, 338 lines) — `_ACTION_TO_OUTCOME`, `build_sync_report`
- `operator-claude-plugin/scripts/cost_guard.py` (lines 180-320) — `fetch_balances`, `compare`
- `operator-claude-plugin/scripts/n8n_read.py` (lines 66-73, 243-382) — `executions_in_window`
- `operator-claude-plugin/scripts/n8n_cadence.py` (lines 452-491) — `check_budget_floor`
- `scripts/build_cloud_workflows.py` (lines 3296-3480, 4560-4705, 4975-4995, 6300-6365) — `Decide Company Action`, `Build Response`, action vocabulary, `ENRICH_STATUS_BUILD_RESPONSE`
- `n8n/code/providerSelection.js` (lines 76-108) — `extractCredits`
- `scripts/provider_registry.py` (full file, 53 lines) — provider credit endpoint config
- `operator-claude-plugin/tests/test_write_grant.py` (lines 1455-1533) — the pinned no-grant-parameter test, the ceiling-breach unit test
- `operator-claude-plugin/tests/conftest.py` (full file, 639 lines) — fixture idioms, `no_network`/`no_durable_writes`
- `tests/conftest.py` (full file, 67 lines) — `RUN_LIVE_PARITY`/ambient-credential guard
- `scripts/prove_async_recovery.py` (lines 1-80) — disarmed live-proof idiom
- `operator-claude-plugin/skills/enrich-records/SKILL.md` (lines 220-360) — dispatch call site, grant/ungranted-send branching
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` (lines 55-98) — GRANT-06 verbatim, explicit "Phase 57's work" note
- `.planning/phases/61-autonomous-batch-runs/61-06-PLAN.md` (lines 313-366, 519-527) — GRANT-06 verbatim, the created-record admission, Phase 57 deferral
- `.planning/milestones/v1.1-REQUIREMENTS.md` (full file) — RUN-05/AFTER-01/AFTER-03/G-4 verbatim, requirement history
- `.planning/STATE.md` (lines 1-370) — milestone status, suite baselines
- `.planning/config.json` — confirms no `nyquist_validation`/`security_enforcement` overrides (both default-enabled)
- `CLAUDE.md` §13.0.3 (project file, read via system context) — n8n platform facts and their evidence tags

### Secondary (MEDIUM confidence)
- None — every claim in this document traces to a primary source read this session or a live grep/search whose output is quoted.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new libraries, verified by inspection of `requirements.txt`-equivalent surfaces (none exist for this plugin) and this phase's scope
- Architecture: HIGH — every architectural claim (dispatch loop shape, artifact schemas, action vocabulary) verified against current source this session
- Pitfalls: HIGH — each pitfall traces to a specific verified code gap (zero production callers of `record_send_outcome`, the `row_id` omission, the 4-action vocabulary gap in `report_enrichment.py`), not speculation

**Research date:** 2026-08-31
**Valid until:** This is a fast-moving, actively-developed area of the codebase (Phase 61 landed the day before this research). Treat findings as valid for 7 days or until the next phase touching `write_grant.py`/`chunking.py`/`written_records.py` lands, whichever is sooner — re-verify line numbers before the planner locks any file:line citation into a task.
