---
phase: 57-ceilings-refusal-before-start-and-post-run-proof
verified: 2026-09-01T00:46:58Z
status: passed
score: 8/9 must-haves verified (1 partial-by-design, disclosed, not a defect)
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "STATE.md / ROADMAP.md administrative sealing (checkboxes, current_phase, stopped_at) is stale — it still reads as though 57-03 is the last completed work, current_phase=61. Confirm this is intentional pre-seal state and not evidence some 57-04/57-05 work was silently dropped."
    expected: "Operator/orchestrator runs the phase-seal step to tick 57-05's ROADMAP checkbox, update STATE.md's current_phase to 57 (complete) and refresh the milestone requirements table's G-4/AFTER-01 rows to point at this VERIFICATION.md."
    why_human: "Bookkeeping files are edited by a separate seal step this agent does not run; a human (or the orchestrator) needs to confirm the sealing step is queued, not skipped."
  - test: "Read the end-of-run report format once (D-57-05/57-05 Task 4's own precondition) before authorising even the small, operator-supervised first live batch."
    expected: "Operator has actually looked at a `run_report.build_run_report(...)['block']` render — from a disarmed dry run or from the small supervised batch itself — before trusting its wording live."
    why_human: "This is a human-judgment precondition the phase itself imposes on the NEXT action (the first live batch), not something code can self-certify."
---

# Phase 57: Ceilings, refusal-before-start, and post-run proof — Verification Report

**Phase Goal:** "An operator can start a batch knowing it will be refused before it starts if it
cannot afford itself, will stop spending rather than overrun if reality diverges mid-run, and can
read afterwards exactly what happened to every row — with a record that would have been written
never reading as one that was."

**Verified:** 2026-09-01T00:46:58Z
**Status:** passed — both human-verification items discharged 2026-09-03 (57-UAT.md) (no code-level gaps found; one disclosed partial-by-design and one
administrative-sealing item need a human look, per the escalation-gate pattern this agent runs
under)
**Re-verification:** No — initial verification.

## Summary Up Front

This is the rare case where the codebase evidence is **stronger** than a cursory read of
`ROADMAP.md`/`STATE.md` would suggest — those two files are simply not yet sealed for this
phase (they still show current_phase=61 and 57-03 as the last completed step), even though all
five plans (`57-01`..`57-05`) have SUMMARY.md files, all their claimed code exists, is wired, and
is covered by tests that drive the real caller path rather than a hand-built unit. I verified
every "claim that deserves independent scrutiny" the task named, by reading the actual
implementation and its tests (not by trusting SUMMARY.md prose), and every one held up. The one
substantive thing genuinely NOT closed by this phase — AFTER-01's join gap on the pair pipeline's
final ingest leg — is disclosed by the phase itself, in the code, in a `gaps` list an operator
reads, exactly as the roadmap entry claims ("Partial (57-05)"). I found no fabricated claim, no
silently dropped truth, and no regression against GRANT-06.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A batch that would exhaust the sampled monthly allowance is refused **before anything is armed**, with the arithmetic and a smaller-batch offer | ✓ VERIFIED | `write_grant.plan_grant()` returns `REFUSED` on `CEILING_OVER` before any live write-safety transport call — `test_plan_grant_refuses_an_over_ceiling_batch_before_anything_is_armed` asserts `transport.mutating_calls == []`. Refusal text carries `projected_executions`/`remaining_sampled`/`shortfall` and, when `split_for_allowance` can offer one, a concrete smaller batch (`test_plan_grant_refusal_carries_a_split_offer`). |
| 2 | `chunking.dispatch_plan` stops **pre-send** on a mid-run ceiling breach — the breaching chunk's transport is never called | ✓ VERIFIED | Read the loop body directly: the tally at `chunking.py:440-483` runs and `break`s BEFORE `_StatusCapturingTransport`/`enrichment.build_envelope`/`dispatch_enrichment` are reached. `test_a_pre_send_ceiling_stops_before_the_breaching_chunk_is_sent` drives a REAL 3-chunk `dispatch_plan()` call and asserts `transport.verbs == ["post", "post"]` (2 posts for 3 chunks) plus `sent_ids(transport) == [["1","2"],["3","4"]]` — not a hand-built `DispatchOutcome`. |
| 3 | ALL FOUR dispatch paths are ceiling-guarded, including the two single-shot `dispatch.dispatch` legs with no chunk boundary | ✓ VERIFIED | An AST test suite (`test_write_grant.py:2225-2440`) `compile()`s the real fenced Python blocks in all three runbooks (`enrich-records`, `enrich-before-ingest`, `contact-upload`) and asserts, via parsed-tree inspection (not grep/string match): (a) both `dispatch_plan` lanes carry an `execution_ceiling` keyword; (b) the single-shot `dispatch.dispatch` call is enclosed by an `If` that also calls `single_dispatch_outcome` in the same branch. Source confirms the pre-call check (`would_be > execution_ceiling`) writes to `remainder_queue` and returns BEFORE `dispatch.dispatch` is invoked. |
| 4 | `split_for_allowance` authorises exactly the records it dispatches — never a scope cut independently of the work | ✓ VERIFIED | `split_for_allowance`'s own docstring states the fix (one ordered sequence, cut once, both sides PROJECTED from it) and `test_the_membership_test_an_interleaved_batch_projects_the_correct_scope` is a genuine MEMBERSHIP test (not a count test): `[domain-create A, id-backed B]` at N=1 asserts A alone on `affordable`/`affordable_spec` and B alone on `remainder`/`remainder_spec`. A sibling `_a_grouped_batch_` test is the control that a broken "cut ids then domains" implementation would still pass. |
| 5 | The forbidden-name scan never destroys legitimate data (`Armstrong`, `pharmacy`, etc.) | ✓ VERIFIED | `test_armstrong_racing_persists`, `test_armidale_jockey_club_persists`, `test_pharmacy_supplier_notes_persist` all pass (`.venv/bin/python -m pytest -k "armstrong or armidale or pharmacy or forbidden"` → 20 passed). The scan is key-triggered, narrowed to keys plus containers, not a blanket value scan. |
| 6 | `gated` is distinct from `written`/`write_attempted` on both client surfaces (eight-word vocabulary, not seven) | ✓ VERIFIED | `written_records.py:139-146` defines exactly 8 words (`WRITTEN`, `WRITE_ATTEMPTED`, `CREATED_ID_UNKNOWN`, `WRITTEN_ID_UNKNOWN`, `GATED`, `HELD`, `FAILED`, `NO_ACTION`). `test_the_two_client_readers_agree_on_every_action` parametrizes all 10 real backend `action` values and asserts `report_enrichment._outcome_for_row(row) == written_records.classify_item(row)["outcome"]`. `test_gated_row_renders_with_distinct_text_from_a_written_row` asserts the RENDERED text differs and names "grant"/"re-send" in the gated text. |
| 7 | GRANT-06 has not regressed — no grant/allowlist/arming token persisted by `remainder_queue` or the new per-run audit record | ✓ VERIFIED | `remainder_queue`'s own forbidden-marker tests refuse a `grant`-shaped key at any depth. `run_report.record_audit`'s authority test (`test_record_audit_raises_on_a_grant_shaped_key_anywhere_in_its_arguments`) pins the same rule for the NEW per-run audit record. Confirmed no code path reads `remainder_queue.load()` to authorize a send — its only reader is `run_report.py:746`, for display only. |
| 8 | AFTER-01's join gap (pair pipeline's final ingest leg strips `row_id`) is disclosed, not silently dropped — rows are KEPT and rendered UNJOINABLE | ✓ VERIFIED, PARTIAL BY DESIGN | `run_report._build_run_report` appends a named gap string containing `strip_row_id` whenever an unjoinable row is seen; `test_unjoinable_leg_is_kept_and_named_in_gaps` asserts `len(report["records"]) == 1` (kept, not dropped), the gap text names `strip_row_id`, and `"UNJOINABLE"` appears in the rendered block. This is the ONE named partial the roadmap/requirements doc itself calls out — not a hidden gap. |
| 9 | An eight-outcome vocabulary and one end-of-run report join all five durable stores plus the audit record, naming contradictions rather than resolving them | ✓ VERIFIED | `run_report.build_run_report` joins `written_records`, `run_state`, `run_manifest`, `held_queue`, `remainder_queue` (five stores; `test_run_report.py` has dedicated `test_contradiction_*` tests for at least 5 named disagreement shapes) plus `load_audit` for the per-run ephemeral-observations record. `test_multi_event_rows_on_different_lanes_both_survive` proves `(row_id, lane)` keying keeps both events for one `row_id`. `REPORT INCOMPLETE` banners at the top on any gap/contradiction, per `test_report_incomplete_banner_is_at_the_top_when_gaps_or_contradictions_exist`. |

**Score:** 9/9 truths hold as claimed (8 fully closed, 1 explicitly and correctly reported as
partial-by-design rather than falsely claimed closed).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `operator-claude-plugin/scripts/write_grant.py` | Ceiling verdict, `plan_grant` refusal, `split_for_allowance` | ✓ VERIFIED | `CEILING_OVER`/`CEILING_OK`/`CEILING_UNKNOWN`, `CLOSED_CEILING_BREACH="ceiling_breach"`, `split_for_allowance` all present and exercised by tests above. |
| `operator-claude-plugin/scripts/chunking.py` | `CeilingStop`, pre-send stop in `dispatch_plan`, `single_dispatch_outcome` | ✓ VERIFIED | Read directly; pre-send tally at line 440, `single_dispatch_outcome` at line 587. |
| `operator-claude-plugin/scripts/remainder_queue.py` | Work-only durable queue, forbidden-marker refusal, false-positive persistence | ✓ VERIFIED | Module exists; 41 tests pass (`test_remainder_queue.py`). |
| `operator-claude-plugin/scripts/written_records.py` | 8-word outcome vocabulary, `outcome_for_action`, `classify_read` | ✓ VERIFIED | Lines 139-248 confirmed directly. |
| `operator-claude-plugin/scripts/report_enrichment.py` | Same vocabulary via the pure function, never a second one | ✓ VERIFIED | `test_the_two_client_readers_agree_on_every_action` cross-checks both readers for all 10 actions. |
| `operator-claude-plugin/scripts/run_report.py` | `build_run_report`, `record_audit`/`load_audit`/`classify_audit_read` | ✓ VERIFIED | Module exists (created this phase); 5-store join, audit record, contradiction detection, `REPORT INCOMPLETE` banner all read directly in source. |
| `scripts/prove_zoominfo_balance.py` | Disarmed, gated, zero-network-call-when-off probe | ✓ VERIFIED | 10/10 tests pass; gate proven by transport-call-count assertion, not string/AST inspection of the source. |
| `n8n/wf_contact_ingest_cloud.json` | `row_id` present in `Build Ingest Response`, regenerated (never hand-edited) | ✓ VERIFIED | `row_id: row.row_id ?? null` present in the committed jsCode. Deploy/bounce/read-back of the LIVE instance is a live claim reported in `57-05-SUMMARY.md`/`57-DISCUSSION-LOG.md` and is treated per this task's stipulated ground truth — not independently re-probed live by this verification (no live credentials exercised). |
| Both lane `SKILL.md` runbooks calling `build_run_report`/`record_audit` | Wired at real production call sites | ✓ VERIFIED | AST tests (`test_build_run_report_is_called_with_an_outcomes_keyword`, `test_a_record_audit_call_exists_before_the_dispatch`, `test_a_record_audit_call_exists_inside_the_finally`) compile the real blocks and assert on parsed calls. `contact-upload` deliberately excluded, disclosed as out-of-scope (single-shot, operator-watched, not AFTER-01's unattended multi-leg case). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `plan_grant()` | `allowance_headroom()` -> `n8n_read.executions_in_window` | sampled-remainder reachability | ✓ WIRED | Live 2026-08-31 measurement (`sampled: true` via `listing_exhausted`, `covers_full_window: false`, allowance 2500/spent 134/remaining 2366) confirms the reachability fix from 57-01 Task 1 actually makes RUN-05's refusal reachable on this account, per `57-01-SUMMARY.md` and `57-DISCUSSION-LOG.md`. |
| `dispatch_plan()` | `DispatchOutcome.ceiling_stop` -> `write_grant.record_dispatch_outcome()` | grant closure on ceiling breach | ✓ WIRED | `test_a_mid_run_ceiling_stop_writes_the_unsent_record_ids_to_the_remainder_queue` and sibling tests drive this through a real dispatch, not a hand-built outcome. Runbook AST tests confirm production callers exist (previously zero, per `57-VALIDATION.md` line 98 — now resolved, 6 production call sites across 3 SKILL.md files). |
| `Decide Action`'s `row.row_id` | `Build Ingest Response` -> `classify_item` -> AFTER-01 join | ingest-lane held-row naming | ✓ WIRED (partial for the pair-pipeline's final leg — disclosed) | `row_id` present in the deployed node's jsCode; `ingestResponseRowId.test.mjs` (4/4) pins the mapping. `strip_row_id` gap for the pair-pipeline leg is a NAMED, tested exception, not silent breakage. |
| Both lane runbooks | `run_report.build_run_report` | production call site | ✓ WIRED | AST-compiled, parametrized over both applicable runbooks. |
| `held_queue.load()` + `remainder_queue.load()` | one review section | operator's single review pass | ✓ WIRED | `run_report.py` reads both stores into the report; confirmed by reading source around line 746 and the "Remainder queue" section renderer. |

### Behavioral Spot-Checks / Test Execution

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Python suite | `.venv/bin/python -m pytest -q` | `3808 passed, 154 skipped` | ✓ PASS — matches task's stated baseline exactly |
| Full Node suite | `node --test tests/n8n/*.test.mjs` | `848 pass, 0 fail` | ✓ PASS — matches task's stated baseline exactly |
| Phase-relevant unit/integration modules | `.venv/bin/python -m pytest -q operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_written_records.py operator-claude-plugin/tests/test_report_enrichment.py operator-claude-plugin/tests/test_remainder_queue.py operator-claude-plugin/tests/test_chunking.py` | `472 passed` | ✓ PASS |
| Deploy tooling `--only` filter, offline | `.venv/bin/python -m pytest -q tests/test_deploy_n8n_workflows.py` | `38 passed` | ✓ PASS |
| ZoomInfo probe gate, zero-network-call proof | `.venv/bin/python -m pytest -q operator-claude-plugin/tests/test_prove_zoominfo_balance.py -v` | `10 passed` | ✓ PASS |
| ingest workflow `row_id` mapping | `node --test tests/n8n/ingestResponseRowId.test.mjs` | `4 pass, 0 fail` | ✓ PASS |

No full-suite command was re-run per-truth; each targeted run above narrowed to the relevant
file(s), and the two full-suite commands were each run exactly once, matching the constraint
against re-running a whole suite per must-have.

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| RUN-05 | 57-01, 57-03 | ✓ SATISFIED | Pre-start refusal + arithmetic (57-01) and the smaller-batch offer via `split_for_allowance` (57-03) both verified above with real test evidence, not prose. |
| AFTER-01 | 57-05 | ✓ SATISFIED, DISCLOSED PARTIAL | One report joins all five stores + audit record; the pair-pipeline's final ingest leg's `row_id`-strip gap is named in `gaps`, kept, rendered UNJOINABLE — matches the roadmap's own "Partial (57-05)" framing exactly, not overclaimed. |
| AFTER-03 | 57-02, 57-05 | ✓ SATISFIED | Eight-word vocabulary, cross-module agreement over all 10 actions, distinct rendered text for `gated` vs `written`/`write_attempted`, both verified with passing tests read directly. |
| G-4 | 57-04, 57-05 | ✓ SATISFIED (ZoomInfo half); Apollo disclosed permanent; Lusha correctly reported unconfirmed | Live probe (2026-08-31, `alexherman.app.n8n.cloud`) returned `readable`, 9381 credits — recorded in `57-04-SUMMARY.md`/`57-ZOOMINFO-BALANCE-VERDICT.json`/`57-DISCUSSION-LOG.md`. This verification did not itself re-run the live probe (a fact the task instructed me to hold, not re-derive) but confirmed the gate code that makes the probe safe (zero network calls when unarmed) via test evidence. Nothing found asserts Lusha is readable — the report generically renders whatever `balances` dict a caller supplies, and no code or doc in this phase claims Lusha readability; the task's caution against accepting that claim is respected (no such claim exists to accept). |
| GRANT-06 (preserved invariant) | all | ✓ NOT REGRESSED | Authority tests exist in both `remainder_queue` and the new `run_report.record_audit`; no code path reads `remainder_queue` to authorize a send. |

### Anti-Patterns Found

No `TBD`/`FIXME`/`XXX` markers found in the phase's modified files that lack a tracked reference.
One genuinely interesting finding, already self-disclosed and fixed by the team before I looked:
`f072e09` fixed a moment-in-time literal (`2026-08-31` hardcoded as "newer than the cutoff") that
had already caused one day of test rot. I searched the rest of the phase's test diff for the same
class of defect (`git diff 1184a69..HEAD -- operator-claude-plugin/tests/ | grep -E '"202[5-9]-..-.."'`)
and found only far-past fixture dates (`2026-01-01`, safely inert) and one opaque
`"checked_at": "2026-08-31T00:00:00Z"` string in a mock ZoomInfo response body that is never
compared against `datetime.now()` in test logic — not a second instance of the same bug.

### Deviations From Plan (logged by executors, checked here)

- TDD RED/GREEN commits combined in 57-03 — process deviation, no correctness impact found; the
  resulting tests pass and cover the claimed behavior directly.
- `test_skill_sequence_coverage.py`/`test_watch_settle_reporting.py` touched outside their plans'
  `files_modified` — necessary consequence of the SKILL.md runbooks changing shape; full suite is
  green including these files.
- Binary search rewritten as a linear scan in `_affordable_record_count` to satisfy this repo's
  D-07 no-`while`-loop AST guard — correctness rests on monotonicity of `ceil(n/ceiling)+n` in
  `n`, which is pinned by its own test (`test_affordable_record_count_cost_is_monotonic_over_a_range_of_n`)
  rather than merely assumed. For realistic batch sizes this is not a performance concern.
- `contact-upload` gained a `tabular.read_table` read so held rows can be named individually in
  the remainder queue on a pre-call ceiling stop — read directly in the runbook, consistent with
  the plan's intent.

### Human Verification Required

> **BOTH ITEMS DISCHARGED 2026-09-03 — see `57-UAT.md`.** Item 1 was already resolved when this
> report was written against a pre-seal snapshot: every condition it names is sealed at HEAD
> (all five plan checkboxes ticked including 57-05, `Phase 57 ... COMPLETE 2026-09-01`,
> `current_phase: 60` not 61, `stopped_at` off 57-03). The verifier's question was "queued or
> skipped?" — the answer is neither: it was DONE, on 2026-09-01/02. Item 2 was discharged by the
> operator reading the end-of-run report format in session on 2026-09-03.
>
> **The read precondition is the ONLY thing discharged.** 57-05 Task 4's other limit still binds:
> the first live batch outside this phase must be SMALL and OPERATOR-SUPERVISED. Nothing here
> authorises an unattended run.

1. **Administrative sealing is stale.** `STATE.md` still reads `current_phase: 61`,
   `stopped_at: Completed 57-03-PLAN.md`, and `ROADMAP.md` still shows 57-05's checkbox
   unticked, even though `57-04-SUMMARY.md` and `57-05-SUMMARY.md` both exist and their claimed
   code is present, wired, and tested. I found nothing suggesting 57-04/57-05's work was
   dropped — the code, tests, and DISCUSSION-LOG entries for both are complete and internally
   consistent with each other and with the task's own "facts you should hold." This reads as
   the phase simply not yet having gone through its seal step (ROADMAP checkbox ticks, STATE.md
   phase-close update, requirements-table pointer updates) — routine, but a human/orchestrator
   should confirm that seal step is queued rather than skipped, since I cannot distinguish "not
   yet sealed" from "silently abandoned" purely from git history and file contents.
2. **The phase's own precondition on the next action.** 57-05 Task 4's recorded ruling requires
   the operator to have read the end-of-run report format at least once before any UNATTENDED
   run, and authorises only a SMALL, operator-supervised first live batch outside this phase.
   That is a human-judgment gate on the NEXT action, not something this verification can
   discharge — flagging it here so it isn't lost between phase-verification and the next
   authorized run.

### Gaps Summary

No code-level gap was found that contradicts what the phase claims. The one substantive
limitation — AFTER-01's join gap on the pair pipeline's final ingest leg (`extraction.strip_row_id`)
— is exactly as disclosed: named in the report's own `gaps` list, covered by a passing test that
proves the row is KEPT and rendered UNJOINABLE rather than dropped or silently counted as a
completed join. This is not a defect relative to the phase's stated scope; it is the one thing
the roadmap itself says stays "Partial." The two items above are routed to human verification
because they are administrative/judgment items outside what static code inspection can resolve,
not because any implementation claim was found to be false.

---

_Verified: 2026-09-01T00:46:58Z_
_Verifier: Claude (gsd-verifier)_
