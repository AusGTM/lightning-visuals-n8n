---
phase: 53-operator-openable-write-grant
plan: 02
subsystem: operator-plugin
tags: [write-grant, envelope, cost-ceiling, revocation, guardrails, arming, python]

# Dependency graph
requires:
  - phase: 53-operator-openable-write-grant
    provides: write_grant.plan_grant/open_grant/close_grant/covers in final signature shape, plus the envelope + consecutive_disarm_failures + preflight seams
  - phase: 25-preview-and-cost
    provides: cost_guard.load_rates/estimate_batch/fetch_balances/compare -- the dated, tri-state cost model
  - phase: 25-preview-and-cost
    provides: chunking.chunk_ceiling/plan_chunks/dispatch_plan
  - phase: 27-status
    provides: n8n_read.get_workflow, read_write_safety, EXECUTION_ALLOWANCE_KEY
  - phase: 28-backend-control
    provides: n8n_arming.DISPATCH_FLAGS, disarm (ungated by design), DISARMED/DISARM_FAILED
provides:
  - "write_grant.envelope(): GRANT-02's four figures + a rendered operator block, built only out of cost_guard and chunking -- no second cost model"
  - "write_grant.GRANT_04_REASONS (exactly five) / GUARDRAIL_B_REASONS (two) / CLOSE_REASONS; close_grant RAISES on a free-text reason"
  - "write_grant.revoke() + check_before_send(): the ONE question every send asks, biting at the next SEND (GRANT-05)"
  - "write_grant.record_send_outcome(): the disarm-failure counter, the ceiling-breach close, and guardrail B's two-failure bound"
  - "write_grant.guardrail_a() + read_live_write_state(): plan_grant's MANDATORY preflight (D-53-03), offer-only"
  - "write_grant.preflight_before_send(): guardrail B's pre-flight live read (D-53-04)"
  - "operator-claude-plugin/tests/test_write_grant_guardrails.py: the phase's two proposed defences, in the file a reviewer looks in"
affects: [53-03-operator-surface, 53-04-skills-docs-release, 57-ceiling-enforcement]

actuals:
  tokens: 41000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Disclosure figures carry their own basis: every envelope number is labelled measured / projected / unconfigured, so an operator never has to infer which kind of number they are reading."
    - "Degrade one line, never the whole open: a missing allowance key or a missing chunk ceiling removes exactly the line it feeds and leaves every other figure computed."
    - "Guardrail asymmetry as a documented invariant: A found a state it did not create and OFFERS; B is closing a window its own run opened and ACTS. Written where both live so a later edit cannot 'harmonise' them."
    - "Close-either-way: a failed closing disarm is recorded on the closed grant, never a reason to leave it open."
    - "Named-set-over-cardinality pinning: GRANT_04_REASONS is asserted by NAME so a later phase can add close reasons without reddening a len() assertion that proved nothing."
    - "Frozen call order documented in the function that owns it, because every scripted transport in two test files depends on it."

key-files:
  created:
    - operator-claude-plugin/tests/test_write_grant_guardrails.py
  modified:
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/tests/test_write_grant.py

key-decisions:
  - "The envelope is computed in plan_grant, not in open_grant. GRANT-02 requires the arithmetic BEFORE the yes; open_grant has no transport and ships in its wave-1 final signature. open_grant's contribution is that its deepcopy carries the envelope onto the grant unchanged, and that its refusals attach the proposal's envelope."
  - "GRANT_04_REASONS stays EXACTLY the five GRANT-04 names; guardrail B's two closes get their own constants in a separate GUARDRAIL_B_REASONS, unioned into CLOSE_REASONS. 'Two consecutive disarm failures' is not batch completion, a ceiling breach, a revocation, a session end, or an unhandled error -- nothing raised. Folding it into one of the five would misreport the one close the operator most needs to read correctly."
  - "guardrail A is plan_grant's DEFAULT preflight and a non-callable preflight is a TypeError, not a skipped check. A preflight=None that meant 'no check' would be a toggle by omission (T-53-12)."
  - "guardrail B's pre-flight closes ONLY on an actually-live write, not on an unreadable or disagreeing read. Guardrail A refuses on unreadable at the OPEN, where refusing costs nothing; mid-run an unreadable read is more likely an API blip, and D-53-04's whole point is that a blip must not abort a long run."
  - "The envelope prices ids + domains as separate records (worst case). Nothing at plan time can prove a grant's domains are not more companies than its ids."
  - "No status POST is made when the batch prices no provider -- there is no balance to read, so none is read. This keeps fake_config-based tests at zero POSTs and makes the priced path explicit."

patterns-established:
  - "Test-the-limitation-not-the-decoration: GRANT-05's revocation is proven by driving a real multi-chunk dispatch_plan with a mid-run revoke and asserting every chunk STILL ran, plus a signature test that notices if dispatch_plan ever gains a grant parameter. The drafted two-hand-calls test was refused because it would pass while the feature was absent."

requirements-completed: [GRANT-05]
requirements-partial:
  - "GRANT-01: the ceilings now ship (envelope states them, the grant carries them unchanged). Only the one-exchange operator surface (53-03 T2) is outstanding."
  - "GRANT-02: all four figures compute and an unreadable balance reads unconfirmed. NOT closed: the projection is against the CONFIGURED monthly allowance rather than the remaining one (Phase 57 samples it), and the operator surface that shows the block is 53-03 T2."
  - "GRANT-04: five named reasons, free text refused, disarm clause vacuous on three paths and real on guardrail B's two. NOT closed: ceiling_breach has no producer until Phase 57, and the reporting surface is 53-03."
  - "GRANT-06: holds over 53-02's surfaces (re-pinned by a source scan; neither guardrail is switchable). 53-03/53-04 still owe their own."

coverage:
  - id: E1
    description: "Opening a grant returns record count, per-provider worst-case credits, worst-case Anthropic dollars, projected executions and the configured allowance -- computed before any yes is asked for"
    requirement: "GRANT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_envelope_reports_every_figure_grant_02_names"
        status: pass
    human_judgment: false
  - id: E2
    description: "An unreadable provider balance reads unconfirmed, never as headroom and never as zero; a READ balance that is genuinely too small still reads as insufficient (cost_guard's tri-state carried through unchanged)"
    requirement: "GRANT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_an_unreadable_provider_balance_reads_unconfirmed_never_as_headroom"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_an_insufficient_balance_is_not_collapsed_into_unconfirmed"
        status: pass
    human_judgment: false
  - id: E3
    description: "The rate table's measured-on date and its age in days reach the operator's block"
    requirement: "GRANT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_envelope_carries_the_rate_tables_measured_on_date_and_its_age"
        status: pass
    human_judgment: false
  - id: E4
    description: "An absent allowance key and an absent max_records_per_chunk each degrade ONE line; every other figure still computes and the grant is not refused"
    requirement: "GRANT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_config_with_no_allowance_key_degrades_one_line_not_the_whole_open"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_missing_chunk_ceiling_degrades_the_projection_not_the_grant"
        status: pass
    human_judgment: false
  - id: E5
    description: "D-53-02's disclosure-not-constraint sentence and the remaining-allowance gap are both in the block an OPERATOR reads, not only in a docstring"
    requirement: "GRANT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_block_says_the_ceiling_discloses_rather_than_constrains"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_block_states_the_remaining_allowance_gap"
        status: pass
    human_judgment: false
  - id: E6
    description: "D-53-05's at-the-yes disclosure is PINNED: a two-lane grant's consequence names both lanes individually AND says the HubSpot write is authorized before the enriched preview exists; a single-lane grant claims no preview trade"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_two_lane_grant_names_both_lanes_and_states_the_preview_trade"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_single_lane_grant_claims_no_preview_trade_that_is_not_happening"
        status: pass
    human_judgment: false
  - id: E7
    description: "The five GRANT-04 close reasons are named constants pinned BY NAME, and close_grant raises on a free-text reason"
    requirement: "GRANT-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_grant_04s_expiry_set_is_exactly_the_five_it_names"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_close_grant_refuses_a_free_text_reason"
        status: pass
    human_judgment: false
  - id: E8
    description: "GRANT-05 as re-scoped: a revocation applied midway through a REAL 3-chunk dispatch_plan stops none of its remaining chunks, and the following check_before_send refuses by name"
    requirement: "GRANT-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_revocation_midway_does_not_stop_a_running_dispatch"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against"
        status: pass
    human_judgment: false
  - id: E9
    description: "GUARDRAIL A: an open over a live-armed backend refuses and names the workflow (name + id), every dispatch flag and its value, and the record allowlist currently in force -- offering a disarm without taking one"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_an_open_over_a_live_armed_backend_refuses_and_names_what_it_found"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_the_refusal_offers_a_disarm_and_does_not_perform_one"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_guardrail_as_transport_log_holds_reads_only"
        status: pass
    human_judgment: false
  - id: E10
    description: "GUARDRAIL A refuses on an UNREADABLE workflow and on declaring nodes that disagree -- an unreadable write-safety state is not a disarmed one"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_a_workflow_that_cannot_be_read_refuses_the_open"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_a_workflow_with_no_declarations_at_all_refuses_the_open"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_declaring_nodes_that_disagree_refuse_the_open_and_say_so"
        status: pass
    human_judgment: false
  - id: E11
    description: "GUARDRAIL B: one disarm failure leaves the grant open and attempts no extra disarm; two consecutive failures close it, ATTEMPT a disarm and carry the verdict; the next send is refused"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_one_failure_then_a_verified_disarm_leaves_the_grant_open_and_disarms_nothing_extra"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_two_consecutive_disarm_failures_close_the_grant_and_attempt_a_disarm"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_the_next_send_after_a_two_failure_close_is_refused"
        status: pass
    human_judgment: false
  - id: E12
    description: "T-53-08b: a grant closes EVEN WHEN THE CLOSING DISARM FAILS, and the failed verdict rides on the closed grant"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_the_grant_closes_even_when_the_closing_disarm_itself_fails"
        status: pass
    human_judgment: false
  - id: E13
    description: "GUARDRAIL B: a pre-flight read finding writes still live closes the grant, attempts a disarm and refuses that send whatever the counter reads; a disarmed lane lets the send through with no mutating call"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_a_preflight_finding_writes_still_live_closes_the_grant_and_refuses_that_send"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_a_preflight_over_a_disarmed_lane_lets_the_send_through"
        status: pass
    human_judgment: false
  - id: E14
    description: "T-53-12: neither guardrail reads an environment variable, a disabling config key or a phrase, guardrail A runs by default with no preflight argument, and a non-callable preflight is a TypeError rather than a bypass"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_neither_guardrail_reads_an_environment_variable_or_a_disabling_config_key"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_guardrail_a_cannot_be_skipped_by_passing_a_non_callable_preflight"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py::test_guardrail_a_runs_by_default_with_no_preflight_argument_at_all"
        status: pass
    human_judgment: false
  - id: E15
    description: "No new n8n execution, HubSpot write or provider credit is spent by this plan; n/8n, scheduled_arm.py and the three pinned test files are unmodified"
    verification:
      - kind: command
        ref: "git diff --stat c9aaee6 HEAD -- operator-claude-plugin -- three files only; nothing under n8n/ or scheduled_arm.py"
        status: pass
      - kind: command
        ref: "node --test tests/n8n/*.test.mjs -- 711 pass, 0 fail"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-25
status: complete
---

# Phase 53 Plan 02: Envelope, Lifetime and the Two Guardrails Summary

**The grant now shows its arithmetic before the yes, ends in named ways that can be reported, refuses the next send after a revoke, and — the two defences 53-CONTEXT asked the planner to surface rather than assume — refuses to open over a backend that is already armed and closes itself when it can no longer confirm the backend is disarmed.**

## Performance

- **Duration:** ~35min
- **Completed:** 2026-08-25
- **Tasks:** 3
- **Files modified:** 3 (1 new, 2 edited)

## Accomplishments

- **GRANT-02's arithmetic exists and is bound to the grant.** `write_grant.envelope()`
  returns the record count, one worst-case credit figure per provider, a worst-case
  Anthropic dollar figure, a projected execution count and the configured monthly
  allowance, plus a rendered block. It is built entirely out of `cost_guard`
  (`load_rates` / `estimate_batch` / `fetch_balances` / `compare`) and `chunking`
  (`chunk_ceiling` / `plan_chunks`). No second cost model exists, so nothing can drift
  from the dated, deliberately over-stating one. `open_grant`'s deepcopy carries the
  figures onto the grant unchanged — what was shown and what the grant is bound to are
  one object, not a recomputation that could differ.
- **The two things an operator would otherwise infer wrongly are in the block they
  read, not only in a docstring.** D-53-02's *these figures describe what this batch can
  cost — they do not prevent it*, and the remaining-allowance gap (*the projection is
  against the plan's CONFIGURED allowance, not what is left of it this month; n8n exposes
  no usage endpoint to an API key*). Both are pinned by tests.
- **`cost_guard`'s tri-state survives the trip.** An unreadable balance renders as
  `unconfirmed`, never as headroom and never as zero — and a balance that IS readable and
  genuinely too small still renders as `NOT ENOUGH`, so the two answers are not collapsed
  in either direction.
- **Degradation is per-line.** A config with no `n8n_monthly_execution_allowance` loses
  the allowance line; a config with no `max_records_per_chunk` loses the execution
  projection. Neither refuses the grant, and each says in the block which line went
  missing and why.
- **The at-the-yes disclosure (D-53-05) is pinned by a test.** For a two-lane grant the
  consequence names the enrichment and contacts lanes **individually** (never collapsed
  into a collective phrase — the operator is approving two distinct write surfaces) and
  states that the HubSpot write is authorized **before the enriched preview exists**. A
  single-lane grant claims no preview trade that is not happening. This is the one
  rendering of the traded protection the operator actually reads; the skill contract pins
  SKILL.md and 53-04's checkpoint pins the human walk, but neither pins this sentence.
- **A grant ends in named ways.** Five constants for GRANT-04's five expiries, plus
  `close_grant` **raising** on a free-text reason. GRANT-04 requires each expiry to be
  reported, and a reason that can be anything is a reason nobody can report on.
- **Revocation bites at the next SEND, and the limitation is tested rather than
  decorated.** A real 3-chunk `dispatch_plan` is driven with a revoke applied after
  chunk one; all three chunks still send, and the following `check_before_send` refuses
  by name. A second test asserts `dispatch_plan` has no `grant` parameter, so the day
  someone makes the shared loop grant-aware, that test is what notices.
- **Guardrail A (D-53-03) is `plan_grant`'s mandatory preflight and is offer-only.** It
  reads each covered lane once through the shipped `n8n_read.read_write_safety` over
  `n8n_arming.DISPATCH_FLAGS`, refuses on any write-enabling flag reading enabled, on a
  workflow that could not be read at all, and on declaring nodes that disagree — and its
  refusal names the workflow, every flag and its value, and the record allowlist in force.
  Its transport log is asserted to hold **reads only**, so a later edit cannot quietly
  make it act.
- **Guardrail B (D-53-04) bounds the disarm unknown, and both its closes disarm.** A
  second consecutive disarm failure, or a pre-flight read finding writes still live,
  closes the grant, **attempts** a disarm through the ungated `n8n_arming.disarm`, carries
  its verdict on the closed grant, and **closes either way**. One failure still fails only
  that send — D-53-04's chosen behaviour, kept intact.

## Task Commits

1. **Task 1: The envelope — the arithmetic read before the yes** — `76c10fa` (feat, tdd)
2. **Task 2: Lifetime and revocation — five named closes, biting at the next send** — `2ba5cf9` (feat, tdd)
3. **Task 3: The two guardrails — refuse to open over an armed backend, bound the unknown** — `c517b88` (feat, tdd)

## Files Created/Modified

- `operator-claude-plugin/scripts/write_grant.py` *(274 → 932 lines)* — the envelope
  section (`envelope`, `_envelope_block`, `_consequence`), the lifetime section
  (five close-reason constants, `revoke`, `check_before_send`, `record_send_outcome`),
  and the guardrail section (`read_live_write_state`, `_live_write_faults`, `guardrail_a`,
  `_close_with_disarm`, `preflight_before_send`, `GUARDRAIL_B_REASONS`). `plan_grant`
  gained `providers`, `today` and a **mandatory** guardrail-A preflight; `open_grant`'s
  refusals now carry the proposal's envelope.
- `operator-claude-plugin/tests/test_write_grant.py` *(598 → 1093 lines)* — 32 new tests
  across Tasks 1 and 2, plus a `_plan_reads()` helper documenting `plan_grant`'s frozen
  call order (every scripted transport in the file routes through it now).
- `operator-claude-plugin/tests/test_write_grant_guardrails.py` *(new, 435 lines,
  22 tests)* — the two proposed defences in their own file.

## Decisions Made

- **The envelope is computed in `plan_grant`, not `open_grant`.** Task 1's action text
  reads "wire the envelope into `open_grant`", but GRANT-02 requires the arithmetic
  **before any yes is asked for**, and `open_grant` ships in wave 1's final signature with
  no transport. `open_grant`'s wiring is that its deepcopy carries the envelope unchanged
  and its refusals attach the proposal's. Recorded as a deviation below.
- **GRANT_04_REASONS stays exactly five; guardrail B gets its own two.** See Deviations.
- **`preflight=None` means the real guardrail, and a non-callable is a `TypeError`.**
  A `preflight=None` that meant "no check" would be a toggle by omission, which is
  T-53-12's defect wearing quieter clothes.
- **Guardrail B's pre-flight closes only on an actually-live write** — not on an
  unreadable or disagreeing read. Guardrail A refuses on unreadable at the *open*, where
  refusing costs nothing; mid-run an unreadable read is more likely an API blip, and
  D-53-04's whole point is that a blip must not abort a long run. Stated in the docstring
  and pinned by `test_a_preflight_that_cannot_read_does_not_close_the_grant`.
- **The envelope prices ids + domains as separate records.** Worst case, deliberately:
  nothing at plan time can prove a grant's domains are not more companies than its ids.
- **No status POST when the batch prices no provider.** There is no balance to read, so
  none is read — which also keeps `fake_config`-based tests at zero POSTs and makes the
  priced path explicit in `_priced_plan_reads()`.
- **`read_live_write_state` is its own narrow read, not a call into
  `status.describe_workflow`.** `describe_workflow` reads two of the four dispatch flags
  and returns no allowlists, while a refusal an operator can act on has to name the
  allowlist currently in force. A comment says so where the next reader would otherwise
  remove it as duplication.

## Deviations from Plan

**1. [Structural] The envelope is computed at PLAN time, not inside `open_grant`.**
- **Found during:** Task 1, reading `open_grant`'s wave-1 signature.
- **Issue:** Task 1's action says "wire the envelope into `open_grant`: compute it before
  the grant dict is built". `open_grant(proposal, confirmation, config)` takes no
  transport and cannot make the balance read, and the plan's own must_haves require the
  envelope "before any yes is asked for" — which is plan time, not open time. Wave 1's
  seam is `proposal["envelope"] = None`, in the proposal.
- **Fix:** `plan_grant` computes and attaches it; `open_grant`'s deepcopy carries it
  unchanged (satisfying "shown and bound-to are the same object") and its refusals attach
  the proposal's envelope.
- **Files modified:** `write_grant.py`. **Commit:** `76c10fa`.

**2. [Reason-set] `GRANT_04_REASONS` is exactly five; guardrail B's two closes are their
own constants.**
- **Found during:** Task 2, reconciling Task 2's "the reason set is exactly [five]" with
  Task 3's "closes the grant with **its own named reason**".
- **Issue:** The two cannot both hold on one flat set. Folding guardrail B's closes into
  one of the five would misreport them — "two consecutive disarm failures" is not batch
  completion, not a ceiling breach, not a revocation, not a session end, and not an
  unhandled error (nothing raised).
- **Fix:** `GRANT_04_REASONS` (exactly five, pinned **by name** so a later addition cannot
  redden it) is a subset of `CLOSE_REASONS`, which also carries `GUARDRAIL_B_REASONS`
  (`two_consecutive_disarm_failures`, `writes_still_live_at_next_send`). `GUARDRAIL_B_REASONS`
  was seeded empty in Task 2 and filled in Task 3, so the union was a fill and not a
  reshape.
- **Files modified:** `write_grant.py`, `test_write_grant.py`. **Commits:** `2ba5cf9`, `c517b88`.

**3. [Test-shape] The drafted two-hand-calls revocation test was NOT written.** The plan
forbids it and the reason holds: calling `check_before_send` twice by hand proves only
that a revoked grant refuses, which would pass while GRANT-05 was entirely unimplemented.
Replaced by driving a real 3-chunk `dispatch_plan` with a mid-run revoke.

**4. [Signature] `record_send_outcome` shipped in Task 2 with Task 3's `config` /
`transport` parameters.** Task 2 describes it as "a pure function returning an updated
grant copy", but Task 3 requires its second-failure path to attempt a disarm, which needs
both. Shipping the final signature in Task 2 made Task 3 a fill rather than a reshape —
the same discipline 53-01 used on `plan_grant`/`open_grant`.

**5. [Test-fixtures] `plan_grant`'s call order grew, so every scripted transport in
`test_write_grant.py` was re-pointed in one deliberate pass.** Guardrail A adds one
workflow GET per lane and the priced envelope adds one status POST. A `_plan_reads()`
helper now documents the frozen order in one place; the tracer's positional script gained
one entry. No assertion was weakened — the two `verbs == ["get"]` assertions became
`["get", "get"]` with a comment naming which read is which.

**None that change scope.** No package was installed, no auth gate was hit, no
architectural decision was needed.

## TDD Gate Compliance

All three tasks carried `tdd="true"`. Task 1 and Task 2's tests were written before their
implementations and failed on arrival (`AttributeError` on the absent functions, then two
genuine expectation failures corrected in the tests). Task 3's tests were written against
an implementation drafted in the same task; its RED property was established by the two
tests that failed on first run against the real code (`ALLOW_HUBSPOT_RECORD_WRITES, ...
reads enabled` wording and the exhausted-script guardrail reads) rather than by
manufacturing a failure. `test`-only commits were not cut separately: each task's tests and
source are one atomic commit, matching 53-01's shape in this phase.

## Known Stubs

| Stub | File | Reason | Resolved by |
|---|---|---|---|
| `CLOSED_CEILING_BREACH` has no producer | `operator-claude-plugin/scripts/write_grant.py` | Nothing in Phase 53 measures spend as it happens; the reason is reachable only by a caller that supplies it. Named now so its emptiness is deliberate rather than a missed wire. | Phase 57 |
| `projected_executions` is projected, never measured | `operator-claude-plugin/scripts/write_grant.py` | 1 webhook execution per chunk + 1 sub-execution per record follows from the enrichment workflow having no batching node, but nobody has counted executions for a multi-chunk grant end to end. Labelled `projected` in the dict and in the block. | Phase 54 |

Both are recorded in `.planning/WINDOWS.md` (ids 25 and 26). 53-01's two seams (ids 23 and
24) are marked **resolved** — this plan filled them.

Neither stub prevents this plan's goal. Two further limitations are flagged rather than
stubbed:

- **Guardrail A cannot see a lane the grant does not name.** A backend armed on some other
  workflow stays unnoticed. Widening it to every workflow the API key can see is a
  one-line change against `n8n_read.list_workflows` and was left out because a refusal
  citing an unrelated workflow would train the operator to override it.
- **GRANT-05's send boundary is a real reduction in what a revoke buys**, and the operator
  chose it. At `max_records_per_chunk` of 2, a 40-record send is 20 chunks and a revoke
  arriving at chunk three stops none of them.

## Threat Flags

None. No file created or modified here introduces a network endpoint, an auth path, a
file-access pattern or a schema change that is not already in the plan's threat register.
`write_grant.py` gained two live-read paths (both through the existing `n8n_read` client
and the existing API key) and one write path (`n8n_arming.disarm`, which is ungated by
design and takes authority away rather than granting it).

## Issues Encountered

No auth gates, no architectural decisions, no package installs.

**The GSD bookkeeping verbs were not used, on 53-01's recorded advice.**
`state.advance-plan` corrupted `.planning/STATE.md` during 53-01's closeout (it miscounts
against this phase's four plans and flattened the carried Phase-52 deferral context);
`requirements.mark-complete` reads `.planning/REQUIREMENTS.md` while v1.1's requirements
live at `.planning/milestones/v1.1-REQUIREMENTS.md`; and `roadmap.update-plan-progress`
finds no plans-progress row for phase 53. All four files
(`STATE.md`, `WINDOWS.md`, `v1.1-REQUIREMENTS.md`, `v1.1-ROADMAP.md`) were edited directly
and diffed.

## User Setup Required

Unchanged from 53-01: an n8n admin still adds `{"allow_write_grants": true}` to
`operator.local.json`, as the JSON boolean. Nothing in this plan is reachable from a skill
yet — the operator-facing surface is 53-03/53-04.

Two config keys now feed the envelope and each degrades one line when absent:
`n8n_monthly_execution_allowance` (the allowance figure) and `max_records_per_chunk` (the
execution projection). Both are already in `config/operator.local.example.json`.

## Next Phase Readiness

- **53-03** builds the operator surface. Everything it renders exists:
  `proposal["envelope"]["block"]` is the arithmetic, `proposal["consequence"]` is the
  at-the-yes sentence, and `guardrail_a`'s refusal carries `live_write_state`, `faults`
  and `offered_action="disarm"` structured for a surface to act on.
- **53-04** still owes the one deliberate contract-test edit for D-53-05.
  `test_enrich_before_ingest_skill_contract.py` is untouched by this plan; the
  before-the-enriched-preview sentence is now rendered and pinned here, which is the
  disclosure that edit trades for.
- **Phase 57** owns the refuse-before-starting check against the *remaining* allowance and
  is the only thing that will actually constrain spend. `envelope()`'s block already says
  so where the operator reads it, and `CLOSED_CEILING_BREACH` is waiting for a producer.
- Zero n8n executions, zero HubSpot writes and zero provider credits were spent.
  `n8n/`, `scripts/build_cloud_workflows.py` and
  `operator-claude-plugin/scripts/scheduled_arm.py` are unmodified.

## Verification Output (as run, 2026-08-25)

```
$ .venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py \
    operator-claude-plugin/tests/test_cost_guard.py \
    operator-claude-plugin/tests/test_preview_enrichment.py -q
140 passed in 0.87s                                          # Task 1 verify

$ .venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py \
    operator-claude-plugin/tests/test_chunking.py -q
143 passed in 0.20s                                          # Task 2 verify

$ .venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_guardrails.py \
    operator-claude-plugin/tests/test_write_grant.py -q
115 passed in 0.26s                                          # Task 3 verify

$ .venv/bin/python -m pytest operator-claude-plugin/tests/ -q
1453 passed, 5 skipped in 4.27s

$ .venv/bin/python -m pytest -q
3016 passed, 154 skipped, 1 warning in 8.86s

$ node --test tests/n8n/*.test.mjs
ℹ tests 711
ℹ pass 711
ℹ fail 0

$ git status --porcelain           # after the three task commits
 M operator-claude-plugin/scripts/write_grant.py
 M operator-claude-plugin/tests/test_write_grant.py
?? operator-claude-plugin/tests/test_write_grant_guardrails.py
                                   # (nothing under n8n/, nothing in scheduled_arm.py)

$ git diff --stat c9aaee6 HEAD -- operator-claude-plugin
 operator-claude-plugin/scripts/write_grant.py      | 706 ++++++++++++++++++++-
 operator-claude-plugin/tests/test_write_grant.py   | 553 +++++++++++++++-
 .../tests/test_write_grant_guardrails.py           | 435 +++++++++++++

$ git diff c9aaee6 HEAD --name-only -- \
    operator-claude-plugin/tests/test_control_arming.py \
    operator-claude-plugin/tests/test_control_flag_parity.py \
    operator-claude-plugin/tests/test_scheduled_arm.py \
    n8n/ operator-claude-plugin/scripts/scheduled_arm.py
(empty — all five untouched)
```

Exactly three files changed by this plan's task commits. The three pinned test files
(`test_control_arming.py`, `test_control_flag_parity.py`, `test_scheduled_arm.py`) are
byte-identical to their 53-01 state.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/write_grant.py` — FOUND (932 lines)
- `operator-claude-plugin/tests/test_write_grant.py` — FOUND (1093 lines)
- `operator-claude-plugin/tests/test_write_grant_guardrails.py` — FOUND (435 lines, 22 tests, all passing)
- `.planning/phases/53-operator-openable-write-grant/53-02-SUMMARY.md` — FOUND
- Commits `76c10fa`, `2ba5cf9`, `c517b88` — all FOUND in `git log`
