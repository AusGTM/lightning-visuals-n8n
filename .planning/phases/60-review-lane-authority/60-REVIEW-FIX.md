---
phase: 60-review-lane-authority
fixed_at: 2026-09-01T00:00:00Z
review_path: .planning/phases/60-review-lane-authority/60-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 60: Code Review Fix Report

**Fixed at:** 2026-09-01
**Source review:** .planning/phases/60-review-lane-authority/60-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (CR-01, WR-01, WR-02 — the 3 IN-* Info findings were out of scope for this pass)
- Fixed: 3
- Skipped: 0

Isolation note: `workflow.use_worktrees` is `false` in `.planning/config.json`, so all edits and
commits below were made directly in the main checkout on `master` (no worktree was created, per
the documented opt-out). Verification (the three test suites) ran in that same checkout, so the
reported numbers are reproducible from the tree as it now stands.

## Fixed Issues

### CR-01: `write_grant.envelope()`'s chunk-size disclosure renders a dict, not a number

**Files modified:** `operator-claude-plugin/scripts/write_grant.py`, `operator-claude-plugin/tests/test_write_grant.py`
**Commit:** `955c5b0`
**Applied fix:** Renamed the local that held the per-chunk record cap (an `int`, from
`chunking.chunk_ceiling(config)`) from `ceiling` to `chunk_record_ceiling`, so it no longer gets
clobbered by the later reassignment of `ceiling` to the sampled-allowance verdict dict returned by
`ceiling_verdict(...)`. `figures["chunk_ceiling"]` now carries the int and `figures["ceiling"]`
still carries the verdict dict — both readers downstream (`_ceiling_line`, which reads
`figures["ceiling"]`, and `plan_grant`'s over-ceiling refusal path at `figures["ceiling"]`,
~lines 1015-1078) were checked and are unaffected, since the `ceiling` name's *final* value and
type were never changed by this fix — only the earlier, colliding use of that same name was
renamed.

Note on scope: per the review's own finding text, this defect predates Phase 60 (`git blame`
attributes the collision to Phase 57's commit `f02113d`). This fix is scoped to the defect only —
no other Phase 57 code was touched.

Added `test_the_grant_02_disclosure_renders_the_chunk_ceiling_as_a_number_not_a_dict`, which pins
`figures["chunk_ceiling"]` to a plain `int` and asserts the rendered GRANT-02 disclosure line
contains `"of at most 2 record(s)"` and never the substring `"verdict"` (which would only appear
if the dict repr leaked back in). Verified this test fails against the pre-fix code path
description in the review (the old code would have rendered
`{'verdict': 'unknown', ...}` in that line) and passes against the fix.

### WR-01: Multi-lane grant summary sentence names "enrichment" even when the grant does not include it

**Files modified:** `operator-claude-plugin/scripts/write_grant.py`, `operator-claude-plugin/tests/test_write_grant.py`
**Commit:** `cc0a661`
**Applied fix:** `_consequence()`'s multi-lane summary clause now derives its verb phrase from
`lane_names` instead of hardcoding `"enrichment"`. Adapted from the review's suggested fix rather
than applied verbatim: the review's own suggested code (`if "enrichment" in lane_names or
"contacts" in lane_names: verbs.append("enrichment")`) would still have claimed "enrichment" for a
`("review", "contacts")` grant — the exact false claim the finding names — because it treats a
`"contacts"`-only lane as an "enrichment" trigger. The shipped fix instead adds the `"enrichment"`
verb only when `"enrichment"` is itself in `lane_names`, and adds `"review decisions"` only when
the review lane is present; a `"contacts"`-only write needs no verb of its own because it is
already named by the sentence's trailing `"...and writes to HubSpot"` clause — which is also why
the pre-existing `("enrichment", "contacts")` combo's pinned wording
(`"enables enrichment and writes to HubSpot"`) is unchanged.

Added two tests: `test_a_review_and_contacts_grant_does_not_falsely_claim_enrichment` (asserts the
word `"enrichment"` is absent and `"review decisions"` is present for `lanes=("review",
"contacts")`) and `test_a_review_and_enrichment_grant_names_both_verbs` (asserts both verbs appear
for `lanes=("review", "enrichment")`). Both drive `write_grant._consequence(...)` directly rather
than through the full `plan_grant` transport-read plumbing, since the function under test needs
only `lane_names`/`ids`/`domains`/`allow_create`. All pre-existing multi-lane and single-lane
consequence tests (including the two-lane pin at
`test_a_two_lane_grant_names_both_lanes_and_points_at_the_written_records_list`) still pass
unmodified.

### WR-02: README.md's "Write grants" section contradicts the shipped Phase 57 ceiling refusal

**Files modified:** `operator-claude-plugin/README.md`
**Commit:** `04aaf10`
**Applied fix:** Replaced the stale bullet ("...the remaining monthly execution allowance is not
yet checked before a run starts") with the review's suggested correction, describing the actual
shipped behavior: the projected n8n-execution count is checked against the sampled remaining
monthly allowance before a grant opens, and a batch that would exceed it is refused unless the
operator explicitly overrides with a reason; every other cost figure (provider credits, Anthropic
spend) discloses only and does not gate the open. Documentation-only change — no code touched, no
test applicable (Tier 3 fallback: re-read the section to confirm it renders correctly and no
adjacent bullets were disturbed).

## Verification

All three project-mandated suites were re-run after all three fixes, in the same checkout the
fixes were committed in (no worktree isolation — `workflow.use_worktrees=false`):

| Suite | Command | Result | Baseline |
|---|---|---|---|
| Root pytest | `.venv/bin/python -m pytest -q` | 3852 passed, 154 skipped | 3849 passed, 154 skipped |
| Plugin pytest | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | 2182 passed, 5 skipped | 2179 passed, 5 skipped |
| Node | `node --test tests/n8n/*.test.mjs` | 848 pass, 0 fail | 848 pass, 0 fail |

The +3 passed-count delta in both Python suites is exactly the 3 new regression tests added by
this pass (1 for CR-01, 2 for WR-01); no existing test's outcome changed. No skip counts changed.
No suite reduced. The node suite (unaffected by any of these fixes — all three touched Python or
Markdown only) is unchanged at 848/0.

No findings in this pass required a logic-classified fix beyond straightforward
rename/derive/documentation corrections, so no finding is flagged `"fixed: requires human
verification"`.

---

_Fixed: 2026-09-01_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
