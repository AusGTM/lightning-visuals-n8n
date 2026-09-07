---
phase: 68-state-the-price-and-keep-moving
fixed_at: 2026-09-07T05:09:36Z
review_path: .planning/phases/68-state-the-price-and-keep-moving/68-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 68: Code Review Fix Report

**Fixed at:** 2026-09-07T05:09:36Z
**Source review:** .planning/phases/68-state-the-price-and-keep-moving/68-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03 — `critical_and_warning` per config; IN-01
  explicitly out of scope, recorded below as `no_change_needed`)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `suggest-contacts`'s implicit-open priced `record_domains` from an expression, not a reused variable

**Files modified:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md`,
`operator-claude-plugin/tests/test_implicit_approval_contract.py`
**Commit:** a8b5e4d
**Applied fix:** Bound the domain-list expression to a named `send_domains` variable
at step 3 (mirroring `enrich-before-ingest`, `enrich-records`, `contact-upload`), used
`record_domains=send_domains` in the `plan_grant` call, and added prose at step 7
stating explicitly that the SAME `send_domains` variable feeds the reused
`enrich-before-ingest` dispatch block's `write_grant.authorize_send`/`covers()` call at
dispatch time — provably identical rather than merely likely to be. Pinned both halves
with a new test,
`test_suggest_contacts_binds_send_domains_as_a_named_variable_reused_at_dispatch`.

### WR-02: D-68-07's recommended grant-opening route can `CapRefused` a following `suggest-contacts` round

**Files modified:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md`,
`operator-claude-plugin/tests/test_implicit_approval_contract.py`
**Commit:** d2167bd
**Applied fix:** Took the review's preferred fix (name the specific failure mode in
`suggest-contacts` rather than change `backend-control`'s general-purpose action).
Step 3's reuse branch now names the specific, foreseeable `CapRefused` cause (a grant
opened via `backend-control/SKILL.md`'s "Opening a write grant" action without
`suggestion_companies` priced) and states the specific next step — re-run that action
with `suggestion_companies=<count of this batch's eligible companies>` passed
explicitly — instead of only relaying `agreed_cap`'s generic message. Left
`backend-control/SKILL.md` and `write_grant.py`/`suggest_contacts.py` (pinned
byte-identical to `f0ab716`) untouched. Pinned with a new test,
`test_suggest_contacts_names_the_caprefused_cause_on_the_reuse_branch`. Confirmed the
new operator-facing wording contains neither "tier" nor "icp" (repo-wide D-10b guard).

### WR-03: The disclosure audit ratchet does not detect a newly-introduced halting question

**Files modified:** `operator-claude-plugin/tests/test_disclosure_audit.py`
**Commit:** f8eab2b
**Applied fix:** Took the review's alternative fix (soften the docstring's claim to an
honest scope statement) rather than add a heuristic scan. Before committing to either,
probed what a scan would need: `grep -in "confirm\|shall i\|do you want\|?"` across all
four converted skills' `SKILL.md` files turned up dozens of legitimate hits per file —
the PRESERVED decision points this same phase deliberately kept (held-row review,
per-header confirmation, company-domain confirmation) use "confirm" pervasively and
throughout their already-converted steps, not only at the two pre-registered
genuine-ask sites the finding names. A scanner precise enough to separate those from a
genuinely new halt would need a large, per-line allowlist needing upkeep on every
future prose edit — the exact maintenance burden the file's own docstring already
warns against, and self-defeating for a file whose point is to stay cheap to keep
true. Rewrote the module docstring to state plainly what the file does and does not
detect (symbol/literal presence and skill-list coverage only; no scan for newly-added
question-like text), matching the review's suggested wording. No test-code change
needed — the fix corrects a documentation overclaim, not a missing check.

## No Fix Needed (out of scope)

### IN-01: `agreed_cap`'s literal call-site position diverges from 68-02-PLAN.md's documented order

**Outcome:** `no_change_needed` (explicitly out of scope per `fix_scope` config: "IN-01
is out of scope"). The review itself recommends no fix ("Fix: None required"), noting
this is very likely a wording ambiguity in the plan rather than a missed instruction,
with no functional defect on the default path.

---

## Test Results

- `operator-claude-plugin/tests/`: **2646 passed, 5 skipped** (baseline 2644 passed / 5
  skipped + 2 new regression tests added for WR-01/WR-02).
- `node --test tests/n8n/*.test.mjs`: **940 pass**, 0 fail (unchanged from baseline —
  no n8n-side files touched).
- `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py`: empty.
- Pinned scripts (`write_grant.py`, `suggest_contacts.py`, `scheduled_arm.py`,
  `n8n_arming.py`) confirmed byte-identical to commit `f0ab716` (no diff).
- No `while`/`import time`/`sleep()` introduced in any plugin script; only
  `SKILL.md` prose and test files were touched.

---

_Fixed: 2026-09-07T05:09:36Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
