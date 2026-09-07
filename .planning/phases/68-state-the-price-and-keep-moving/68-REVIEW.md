---
phase: 68-state-the-price-and-keep-moving
reviewed: 2026-09-07T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - operator-claude-plugin/scripts/watch.py
  - operator-claude-plugin/skills/backend-control/SKILL.md
  - operator-claude-plugin/skills/contact-upload/SKILL.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/tests/test_disclosure_audit.py
  - operator-claude-plugin/tests/test_headless_grant_boundary.py
  - operator-claude-plugin/tests/test_implicit_approval_contract.py
  - operator-claude-plugin/tests/test_interrupt_semantics.py
  - operator-claude-plugin/tests/test_pre_spend_pause.py
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: issues_found
---

# Phase 68: Code Review Report

**Reviewed:** 2026-09-07
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 68 adds one new mechanism (`watch.pre_spend_pause`) and converts four batch skills'
no-grant ask into a state-price-pause-open default, backed by five new/extended test files. The
core mechanism is sound: `pre_spend_pause` is a four-line function behind an injected `sleep`
seam, `watch.py` remains the only plugin script importing `time`, and every test that exercises
it drives a fake clock — no test performs a real wall-clock wait. The call-order contract
(`plan_grant` → `pre_spend_pause` → `open_grant`) is genuinely pinned by
`test_implicit_approval_contract.py` and holds across all four skills. The refusal discipline
(`CapRefused`, `plan_grant`'s `CEILING_OVER`, the STOP-and-relay wording) is intact everywhere I
checked, and the `unknown`-ceiling disclosure never becomes a fence. The headless/cron boundary
(`scheduled_arm.py`, `n8n_arming.py`) is untouched and provably grant-free. The full plugin test
suite (2644 passed, 5 skipped) and the newly added 79 tests all pass genuinely (re-run directly,
not trusted from the harness's own summary line).

The issues below are not in the pause mechanism or the pinned call order — they are in two
places the tests don't reach: a documentation-only gap in how `suggest-contacts`'s new implicit
grant is expected to stay in scope for its own later dispatch, and a foreseeable dead end on the
very "open a bigger grant" path Phase 68 tells operators to take. A fourth finding is a
regression-detection gap in the new disclosure-audit ratchet itself.

## Warnings

### WR-01: `suggest-contacts`'s implicit-open prices `record_domains` from an expression, not a variable reused at dispatch time

**File:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md:92-93`
**Issue:** In the three other converted skills (`enrich-before-ingest`, `enrich-records`,
`contact-upload`), `record_domains=send_domains` is passed to `plan_grant` (grant-open time) and
the identical `send_domains` variable is passed again to `write_grant.authorize_send`/`covers()`
(dispatch time) — see e.g. `enrich-before-ingest/SKILL.md:287` and `:438`. Because `covers()`
does exact-membership checking (`write_grant.py:1317-1328`: every value in `record_domains` must
appear verbatim in `grant["record_domains"]`), that reuse of one named variable is what
guarantees the grant actually covers the send.

`suggest-contacts`'s new implicit-open call inlines the expression instead of binding it to a
named variable:
```python
record_domains=[c.get("website") or c.get("domain") for c in eligible_companies
                 if c.get("website") or c.get("domain")]
```
Step 7/8's own dispatch ("hand `plan` and `minted["spec"]["rows"]` to `enrich-before-ingest/
SKILL.md` step 5's dispatch block verbatim", `suggest-contacts/SKILL.md:299-306`) never shows
what value `send_domains` is bound to for the borrowed `authorize_send`/`covers()` call inside
that block. If whatever binds it there is derived differently (e.g. from each proposed
person's own `company_domain` field rather than re-deriving the same list from
`eligible_companies`), `covers()` refuses the round's own dispatch with "these are outside the
grant" — on the very default path Phase 68 exists to make frictionless. This is a documentation
gap, not something the pytest suite can catch (there is no test executing the SKILL.md prose
end to end), so I cannot confirm it fails live, only that the file gives no explicit assurance it
won't.
**Fix:** Bind the list to a named `send_domains` variable at step 3 (mirroring the other three
skills) and have step 7/8 explicitly state that the SAME `send_domains` is what is passed to the
reused dispatch block's `authorize_send`/`covers()` call, so the value is provably identical at
open time and at dispatch time rather than merely likely to be.

### WR-02: D-68-07's recommended "open a bigger grant" route does not guarantee `suggestion_companies` is priced, so a following `suggest-contacts` round can `CapRefused`

**File:** `operator-claude-plugin/skills/backend-control/SKILL.md:95-111`,
`operator-claude-plugin/skills/suggest-contacts/SKILL.md:76-81`
**Issue:** Every converted skill's inline grant offer (D-68-07) points the operator at
`backend-control/SKILL.md`'s "Opening a write grant" action as "the direct route" to a grant
spanning more than one batch. That action's own text (lines 95-111) describes `plan_grant`/
`open_grant` generically — record count, providers, lanes, creates — and never mentions
`suggestion_companies`, because it's written as a general-purpose action, not scoped to any one
skill's downstream needs.

If an operator follows that recommended route to open a session grant over a company batch, and
`suggest-contacts` is later auto-offered over the same batch, step 3's reuse branch runs:
```python
priced_cap = suggest_contacts.agreed_cap(2, grant["envelope"])
```
`agreed_cap` raises `CapRefused` when `grant["envelope"]["suggestion_allowance"]` was never
priced (`suggest_contacts.py:443-452`) — which is exactly the state a `backend-control`-opened
grant is in unless whoever opens it happens to also pass `suggestion_companies`. The operator
who did exactly what D-68-07 told them to do gets a hard refusal instead of the "reuse it, don't
plan a second one" path the skill promises. This is a WARNING, not a BLOCKER, because the
failure mode is a clean, correctly-worded refusal (never a silent wrong write) — but it
undermines this phase's own stated goal ("state and keep moving") on the path it explicitly
advertises as the one to use for a broader grant.
**Fix:** Either have `backend-control`'s grant-opening action price `suggestion_companies` by
default whenever `object_type` is `companies` (mirroring what `enrich-before-ingest` already does
unconditionally for its own contacts batches), or have `suggest-contacts` step 3's reuse branch
name this specific failure mode in its `CapRefused` handling so the operator is told *why* the
recommended route refused and what to do next, rather than a bare relay of `agreed_cap`'s generic
message.

### WR-03: The disclosure audit ratchet does not detect a newly-introduced halting question

**File:** `operator-claude-plugin/tests/test_disclosure_audit.py:1-10, 107-146`
**Issue:** The module docstring frames this file as "the thing that keeps the verdict true as
Phase 67 edits this same prose next" — implying it will catch a regression where a converted
skill grows a new halting question. It does not. Every assertion in the file is one of:
(a) the `AUDIT` dict's keys match the skills on disk (catches an added/removed *skill*, not
added/removed *prose*), (b) a specific pre-recorded literal is still present (catches deletion of
an already-known-good sentence, not addition of a new one), or (c) a specific symbol
(`pre_spend_pause`, `open_grant`) is absent from the four read-only skills. None of these fail if
someone drops a brand-new "Confirm before proceeding? (yes/no)"-style block into, say,
`enrich-records/SKILL.md`'s already-converted step 5 — there is no assertion anywhere in this
file that scans a converted skill's disclosure surface for newly-added question-like text. This
is a real gap between what the docstring claims ("keeps the verdict true") and what the test
suite actually checks (presence of known-good text, absence of two named symbols in four
unrelated files).
**Fix:** Either soften the docstring's claim to "pins what is already known, does not detect new
halts" (an honest scope statement), or add a genuine regression check — e.g. a heuristic scan of
each converted skill's own disclosure sections for interrogative/confirmation patterns
(`?`, "confirm", "shall I", "do you want") outside the two pre-registered genuine-ask sites
(`suggest-contacts` role ask, and each skill's per-record/per-header exception already named in
`PRESERVED_LITERALS`), so a new halting question fails loudly instead of passing silently.

## Info

### IN-01: `agreed_cap`'s literal call-site position diverges from 68-02-PLAN.md's documented order, with no functional effect

**File:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md:70-120`
**Issue:** `68-02-PLAN.md`'s own must-have truth (line 34) and Task 3's action text (line 258)
describe step 3's order as "`plan_grant` fence, **the stated line**, and the `agreed_cap` call" —
i.e., agreed_cap called *after* the price is stated. The shipped file instead computes
`priced_cap = suggest_contacts.agreed_cap(2, proposal["envelope"])` immediately after the
`plan_grant`/refusal-check block (line 108), and the actual price-disclosure block
(`proposal["envelope"]["block"]`, `proposal["consequence"]`) only renders in step 4 (line
128-135), after `agreed_cap` has already run. Re-reading the plan's own prose, "the stated line"
it refers to at that point is most plausibly the earlier "state the per-company cap default of
2" sentence (line 70-74), which *does* precede `agreed_cap` — so this is very likely a wording
ambiguity in the plan rather than a missed instruction. Functionally there is no defect:
`agreed_cap` is a pure dict read (`suggest_contacts.py:420-465`) that neither spends anything nor
depends on the price having been rendered first, `test_implicit_approval_contract.py` only pins
`plan_grant < pre_spend_pause < open_grant` (never agreed_cap's position), and on the default
path (`chosen_cap=2` against `PRICED_CAP=3`) `agreed_cap` cannot raise `CapRefused` regardless of
where it sits in the prose. Recorded for plan-fidelity auditing only.
**Fix:** None required. If plan-vs-implementation fidelity is being tracked separately, note
that `68-02-SUMMARY.md`'s "no deviations" claim rests on reading "the stated line" as the cap-
default sentence rather than the price block; a future reader auditing literal fence order
against the plan's prose should not read this as an unflagged deviation.

---

_Reviewed: 2026-09-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
