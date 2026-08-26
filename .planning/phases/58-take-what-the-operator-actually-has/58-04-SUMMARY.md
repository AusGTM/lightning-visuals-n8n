---
phase: 58-take-what-the-operator-actually-has
plan: 04
subsystem: operator-claude-plugin
tags: [cost-guard, company-lane, domain-confirm, envelope-disclosure, non-clobber]

requires:
  - phase: 58-02-propose-mode-observation-spike
    provides: "the operator's recorded defer-residual decision on backend domain research (58-SPIKE-VERDICT.md), which this plan's Task 3 reads and branches on"
  - phase: 58-03-confirm-the-proposed-domain
    provides: "company_domain.py's apply_domain_decisions / DECLINE_DOMAIN / to_envelope_spec -- the exact code path this plan's decline_research converges onto"
provides:
  - "cost_guard.research_line -- prices a caller-supplied row set for backend domain research: zero rows, an unmeasured rate, and a measured rate are three distinct rendered states, never a fabricated or zero-standing-in-for-unknown figure"
  - "company_domain.needs_research -- names every row Claude could not confidently propose a domain for, plus any the operator asked to check"
  - "company_domain.decline_research -- strikes the research line by feeding needs-research rows into the SAME DECLINE_DOMAIN sentinel a manual decline already uses, never overriding an explicit operator decision"
  - "enrich-records/SKILL.md documents the research line in the operator's own terms, in the same confirm-table block 58-03 built"
  - "INPUT-02 residual named in writing: defer-residual, operator, 2026-08-26 -- no backend code touched by this plan"
affects: [58-05]

actuals:
  tokens: 4784
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A struck cost line converges on an existing decision sentinel (DECLINE_DOMAIN) rather than adding a second bucket or a second code path -- the same pattern 58-03 established for a manual decline, now reused for a bulk strike."
    - "A pricing function takes the row set as a parameter rather than deriving it -- the priced count and the decided count can never independently drift into two numbers about the same rows."

key-files:
  created:
    - operator-claude-plugin/tests/test_company_research_envelope.py
  modified:
    - operator-claude-plugin/config/cost_rates.json
    - operator-claude-plugin/scripts/cost_guard.py
    - operator-claude-plugin/scripts/company_domain.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/tests/test_cost_guard.py

key-decisions:
  - "Task 3 (operator, 2026-08-26, recorded in 58-SPIKE-VERDICT.md, read by this plan): defer-residual stands. No code change to scripts/build_cloud_workflows.py, src/web_research.py, or any n8n/wf_*.json -- verified empty by git diff --stat and git status --porcelain."
  - "A struck research line is not a new bucket in apply_domain_decisions -- it is resolved-map entries (DECLINE_DOMAIN) merged in before the existing function runs, so a struck row and a manually declined row are provably the same code path, not two that could drift apart."
  - "cost_guard.research_line checks zero-rows FIRST, before checking whether the rate is measured -- a measured rate priced against zero rows must never render a $0 line implying spend was considered and found free."

patterns-established:
  - "needs_research(proposals, requested_check) / decline_research(resolved, needs_research_rows) is a two-function seam: the first names rows, the second converts a bulk strike into individual sentinel decisions the existing apply/decide machinery already understands. A future capability that needs a similar 'strike everything in this set' operator move can reuse the same shape."

requirements-completed: [INPUT-02, INPUT-04]

coverage:
  - id: D1
    description: "The research-line pricing renders count, named rows, and an honest cost state (unmeasured / measured / no-rows), never a fabricated or zero-standing-in-for-unknown figure"
    requirement: "INPUT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_an_unmeasured_rate_renders_no_dollar_figure_and_no_zero"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_a_measured_rate_renders_a_figure_proving_the_null_branch_is_not_the_only_path"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_zero_rows_says_no_company_needs_research_not_a_zero_cost_line"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_zero_rows_says_no_research_needed_even_with_a_measured_rate"
        status: pass
    human_judgment: false
  - id: D2
    description: "The priced row set and the decision structure's needs-research row set are the identical set, asserted by comparison"
    requirement: "INPUT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_the_named_rows_and_the_decision_structures_needs_research_rows_are_the_same_set"
        status: pass
    human_judgment: false
  - id: D3
    description: "Striking the research line converges every affected row onto the same name-only path a manual decline already takes, without disturbing any other row's decision or making any row undecided"
    requirement: "INPUT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_striking_the_line_moves_exactly_the_needs_research_rows_to_name_only_and_nothing_else"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_a_declined_research_row_and_a_declined_proposal_row_are_the_same_shape"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_striking_the_line_leaves_an_empty_undecided_group_empty_so_envelope_spec_does_not_raise"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_decline_research_never_overrides_an_explicit_operator_decision"
        status: pass
    human_judgment: false
  - id: D4
    description: "enrich-records/SKILL.md documents the research line in the operator's own register: silence means it proceeds, striking it means name-only matching"
    requirement: "INPUT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_research_envelope.py::test_enrich_records_skill_documents_the_research_line"
        status: pass
    human_judgment: false
  - id: D5
    description: "INPUT-02's residual (backend research node not extended to seek a domain) is named in writing with decider, date, reason, and what would close it -- no code touched under the defer branch"
    requirement: "INPUT-02"
    verification:
      - kind: manual_procedural
        ref: "58-SPIKE-VERDICT.md (operator decision, read by this plan) plus this SUMMARY's INPUT-02 Disposition section; git diff --stat scripts/build_cloud_workflows.py src/web_research.py n8n/ and git status --porcelain n8n/wf_*.json both empty"
        status: pass
    human_judgment: true
    rationale: "The disposition is an operator scope decision already recorded elsewhere (58-02's checkpoint); this plan's job is to read it and write the residual down accurately, which is a comprehension check rather than something a test classifies pass/fail."

duration: ~25min
completed: 2026-08-26
status: complete
---

# Phase 58 Plan 04: Price and Decline Backend Domain Research Summary

**Backend domain research is now a priced, declinable envelope line -- `cost_guard.research_line` never renders a fabricated or zero-standing-in-for-unknown figure, and `company_domain.decline_research` converges a struck line onto the exact same name-only code path a manual decline already uses -- while Task 3's backend extension stays deferred, exactly as the operator decided at 58-02's checkpoint, with zero code touched.**

## Performance

- **Duration:** ~25min
- **Tasks:** 3 (2 code tasks, 1 written-disposition task)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- `cost_guard.research_line(rows, rates)` prices a caller-supplied set of company rows
  needing backend domain research. Three states, checked in order: zero rows (checked
  first, regardless of whether the rate is measured) says no company needs it; an
  unmeasured rate says the cost is not measured; a measured rate renders a real dollar
  figure. None of the three ever renders a `$0` line.
- `config/cost_rates.json` gained one `company_domain_research` entry, `value: null`,
  shaped identically to the existing `apollo_per_match` null-rate precedent -- no figure
  was fabricated by scaling the all-in `anthropic_usd_per_record` chain.
- `company_domain.needs_research(proposals, requested_check)` names every row Claude
  could not confidently propose a domain for, plus any row the operator explicitly asked
  to have checked. A row Claude already proposed a domain for is absent from the set --
  the free in-conversation proposal remains the primary path (D-58-01).
- `company_domain.decline_research(resolved, needs_research_rows)` strikes the line: it
  feeds every needs-research row not already decided into the SAME `DECLINE_DOMAIN`
  sentinel `apply_domain_decisions` already uses for a manual decline. A struck row and a
  manually declined row are provably the same shape because they run through the same
  function -- not two paths that could drift apart. An explicit operator decision already
  present in `resolved` is never overridden.
- `enrich-records/SKILL.md` documents the research line inside the same companies
  confirm-table block 58-03 built: how many rows, which ones, the cost or its unmeasured
  state, that silence covers it under the same batch yes, and what striking it costs the
  operator (name-only matching, less certain).
- Task 3 read `58-SPIKE-VERDICT.md`, confirmed the recorded decision is `defer-residual`,
  and made **zero code changes** -- `scripts/build_cloud_workflows.py`, `src/web_research.py`,
  and every `n8n/wf_*.json` are byte-identical to before this plan ran.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): failing tests for the research line** - `14742e7` (test)
2. **Task 1 (GREEN): price backend domain research honestly** - `bc83225` (feat)
3. **Task 2: default-on declinable research line** - `2a94667` (feat)
4. **Task 3: no code change (defer branch)** - no commit; the deliverable is this
   SUMMARY's INPUT-02 Disposition section below, per the plan's own instruction to
   "stop -- the task is done" once the residual is named in writing.

**Plan metadata:** (this commit) `docs(58-04): complete price-and-decline domain research plan`

**Note on commit history (transparency, not a deviation from plan content):** a
concurrent commit on this branch (`fb64043`, revising `58-05-PLAN.md`, made by another
agent working the sibling plan) intervened between this plan's RED commit and its first
GREEN commit. In the process a `git reset` on that branch discarded this plan's original
`feat(58-04)` Task 1 commit (`07a8ff8`) before it was noticed. The content was never lost
from the working tree; it was re-verified green against the current suite and
re-committed as `bc83225`. No 58-05 file was read, written, or included in any commit
made by this plan.

## Files Created/Modified

- `operator-claude-plugin/tests/test_company_research_envelope.py` - new; one test per
  `<behavior>` bullet across both code tasks, plus the SKILL.md-documents-the-line test
- `operator-claude-plugin/config/cost_rates.json` - added `company_domain_research`
  (null value, `USD/company` unit, unmeasured confidence)
- `operator-claude-plugin/scripts/cost_guard.py` - added `RESEARCH_RATE_KEY` and
  `research_line()`
- `operator-claude-plugin/scripts/company_domain.py` - added `needs_research()` and
  `decline_research()`
- `operator-claude-plugin/skills/enrich-records/SKILL.md` - added the research-line
  paragraph inside the companies confirm-table step
- `operator-claude-plugin/tests/test_cost_guard.py` - added the rate-shape parity test

## Decisions Made

- **`research_line` takes the row set as a parameter, never derives it itself** -- this
  is what makes the priced count and `needs_research`'s decided count provably the same
  set rather than two independently maintained numbers that could silently diverge.
- **Zero-rows is checked before rate-known-ness** -- a measured rate priced against zero
  rows must say "no company needs it," never render a `$0` figure implying spend was
  considered and found free.
- **`decline_research` reuses `DECLINE_DOMAIN`, adds no new bucket** -- confirmed with
  the advisor before writing code: the plan's own key-link text says the convergence
  happens "inside `apply_domain_decisions`," and a new bucket would change what
  "undecided" means, which Task 2's action text explicitly forbids.

## Deviations from Plan

None on scope or approach — both code tasks executed exactly as planned and Task 3 took
the defer branch exactly as the recorded operator decision requires. See "Note on commit
history" above for the one process-level incident (a concurrent commit's `git reset`
discarding an already-made commit) — content was unaffected and fully re-verified; this
is disclosed for transparency, not because plan content changed.

## Issues Encountered

A concurrent agent committing to `master` on the sibling `58-05` plan ran a `git reset`
between two of this plan's commits, discarding this plan's first `feat(58-04)` commit
before it was noticed. Caught immediately via `git log`/`git reflog` inspection when the
expected commit was missing from `--cached --stat`; the working-tree content was intact,
re-verified against the full test suite, and re-committed. No file belonging to the
sibling plan was touched by this plan's commits at any point.

## INPUT-02 Disposition (Task 3, defer branch)

**Decision: defer-residual.** Recorded by the operator, 2026-08-26, in
`58-SPIKE-VERDICT.md` (58-02's Task 3 checkpoint) and read, not re-decided, by this plan.

**What is closed:** every row Claude can confidently propose a domain for from what it
already sees in conversation, and every row the operator can supply or correct one on
via the confirm table (58-03) or now decline via the research line (this plan). That
covers the common case at zero backend deploy cost.

**What is NOT closed:** a row where Claude cannot confidently propose a domain AND the
operator cannot supply one. That row falls to the accept-by-name lookup path (58-01/58-03)
rather than a backend-researched domain — the backend research node has not been taught
to seek a company's own website.

**Reason (verbatim from the verdict, operator, 2026-08-26):** Claude-in-conversation
already proposes a domain from what it sees in most cases, free and instant (D-58-01),
and the operator confirms, corrects, or denies it. Every row Claude cannot confidently
propose already falls to the accept-by-name path shipped in 0.16.0. Extending the backend
research node's prompt/schema to also seek a domain would require a
`build_cloud_workflows.py` change, a rebuild, a deploy, a bounce, and a live proof
execution that spends a real Anthropic call to satisfy this project's "a stored read-back
proves nothing" standard — cost not justified this phase against a client-side path that
already covers the common case at zero n8n deploy cost.

**What would close it (per the plan's own Task 3 action text, plus 58-02's shape
finding):**
1. Add the company's own website to `scripts/build_cloud_workflows.py`'s
   `required_fields` list and the literal schema string `researchSystemPrompt()`
   specifies, following the `{"data":{...}}` shape the seven existing fields already use.
2. Land `src/web_research.py`'s `REQUIRED_FIELDS` and system prompt in the SAME commit
   (Phase 46 parity rule — one contract, two engines, never changed alone).
3. Verify (not edit) that `n8n/code/webResearch.js`'s `validateResearchOutput` passes an
   unrecognised data field through unchanged, and pin that verification with a test.
4. Build, deploy, bounce, and prove the running content with a live execution whose own
   `runData` shows the research node ran with the new field in its request — a stored
   read-back proves nothing, per this project's standing rule.
5. **Additionally, per 58-02's shape finding** (not in this plan's Task 3 text, but
   handed forward by 58-02's own SUMMARY for whichever future plan does this work): the
   `propose`-mode response's `match`/`candidates` shape is built for a contact identity
   check (email/object-id/name+company), not a company one. A caller cannot read a
   proposed company domain out of that response body as it stands today — closing
   INPUT-02's residual via the backend also needs a company-shaped `match`/`candidates`
   response contract, not just the prompt/schema change.

**Cost actuals against the plan's own budget (2 executions / 1 Anthropic call cap for
Task 3's live-proof step):** 0 executions, 0 Anthropic calls, 0 deploys. The defer branch
spends nothing because it makes no backend call at all.

**Residual carries forward** to whichever future phase picks up backend domain research
extension; this plan creates no follow-up plan for it (per the plan's own instruction:
"stop — the task is done").

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`58-05` (native-field promotion gap-closure, planned separately per 58-03's operator
ruling) is unaffected by this plan and was not touched by it. Any future phase extending
the backend research node to seek a company's own website should read this SUMMARY's
INPUT-02 Disposition section for the two-part closure list (prompt/schema change plus the
company-shaped response contract 58-02 already flagged) before starting.

---
*Phase: 58-take-what-the-operator-actually-has*
*Completed: 2026-08-26*
