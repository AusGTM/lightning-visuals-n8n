---
phase: 74-code-review-follow-ups-from-phase-73
reviewed: 2026-09-19T10:46:12Z
depth: standard
files_reviewed: 44
files_reviewed_list:
  - CLAUDE.md
  - n8n/code/pairCreateOutcome.js
  - n8n/wf_contact_ingest_cloud.json
  - n8n/wf_enrichment_cloud.json
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/csv_dedupe.py
  - operator-claude-plugin/scripts/preview.py
  - operator-claude-plugin/scripts/report_enrichment.py
  - operator-claude-plugin/scripts/review_decision.py
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/tests/test_chunking.py
  - operator-claude-plugin/tests/test_control_flag_parity.py
  - operator-claude-plugin/tests/test_csv_dedupe.py
  - operator-claude-plugin/tests/test_preview_rendering.py
  - operator-claude-plugin/tests/test_report_enrichment.py
  - operator-claude-plugin/tests/test_review_decision.py
  - operator-claude-plugin/tests/test_write_grant.py
  - operator-claude-plugin/tests/test_written_records.py
  - scripts/build_cloud_workflows.py
  - scripts/freeze_execution_rundata.py
  - tests/n8n/enrichmentConvergenceMerge.test.mjs
  - tests/n8n/fixtures/frozen/exec_12354.runData.json
  - tests/n8n/fixtures/frozen/exec_12355.runData.json
  - tests/n8n/fixtures/frozen/exec_12356.runData.json
  - tests/n8n/fixtures/frozen/exec_12357.runData.json
  - tests/n8n/fixtures/frozen/exec_12358.runData.json
  - tests/n8n/fixtures/frozen/exec_12434.runData.json
  - tests/n8n/fixtures/frozen/exec_12449.runData.json
  - tests/n8n/fixtures/frozen/exec_12522.runData.json
  - tests/n8n/fixtures/frozen/exec_12676.runData.json
  - tests/n8n/fixtures/frozen/exec_12677.runData.json
  - tests/n8n/fixtures/frozen/README.md
  - tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json
  - tests/n8n/frozenFixtureSecrets.test.mjs
  - tests/n8n/ingestCarryMerge.test.mjs
  - tests/n8n/ingestCreateErrorLane.test.mjs
  - tests/n8n/ingestMixedBatch.test.mjs
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/pairCreateOutcome.test.mjs
  - tests/n8n/researchErrorGateFlow.test.mjs
  - tests/n8n/walkerEngineFidelityV1.test.mjs
  - tests/n8n/walkWorkflow.test.mjs
  - tests/test_extract_js_const.py
  - tests/test_freeze_execution_rundata.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 74: Code-review follow-ups from phase 73 - Code Review Report

**Reviewed:** 2026-09-19T10:46:12Z
**Depth:** standard
**Files Reviewed:** 44 (diff against `dd7d8110..HEAD`)
**Status:** issues_found (1 warning, 2 info — no blockers)

## Summary

This phase closes the 16 findings (CR-01..04, WR-01..12) carried out of
`73-REVIEW.md`. I reviewed every file's diff against `dd7d8110`, cross-checked each
fix against its finding's original text and against the D-74-xx decisions in
`74-CONTEXT.md`, ran the full in-scope test suites (`node --test` on the nine required
`tests/n8n/*.test.mjs` files: 86/86 pass; `pytest` on the ten required Python test
files: 600/600 pass), and regenerated all nine `n8n/wf_*.json` workflows from
`scripts/build_cloud_workflows.py` to confirm the two committed generated files carry
zero drift from the generator (`git status --short n8n/` empty after regeneration).

**All 16 closed findings hold up.** I traced each one individually:

- **CR-01** (create-error lane convergence): the plan correctly abandoned the original
  `alwaysOutputData`-rescues-the-error-branch theory once execution `12522` disproved
  it (AOD only ever rescues output index 0 — confirmed against the real engine source
  symbol cited, and against the frozen `12522` recording). The final shape (a real
  `Create Error Stamp` producer feeding `Create Carry Merge`'s third input, `Create
  Carry Merge` completing via the v1 end-of-run drain) is verified live and pinned by
  `walkerEngineFidelityV1.test.mjs`.
- **CR-02/D-74-04/D-74-05**: `pairCreateOutcome.js`'s new `_isStampedError` check runs
  strictly before both shape heuristics, correctly making the explicit stamp
  authoritative regardless of what an error item happens to also carry. Read-only from
  the pairing module's side; the one producer is the new builder-generated node — no
  double-write risk.
  Verified against `n8n/code/pairCreateOutcome.js:82-94,113-122`.
- **CR-03/D-74-06**: `create_outcome !== "success"` (widened from `=== "error"`)
  correctly captures the two previously-silent `"none"`/`"refused"` outcomes, and
  `create_unconfirmed` is wired through `written_records.ACTION_TO_OUTCOME` to `FAILED`
  — never a success-shaped outcome, matching the finding's own "never guess" framing.
- **CR-04/D-74-07..09**: the widened `_scrub` in `freeze_execution_rundata.py` now
  walks the WHOLE node-run entry recursively (not just `data.main`), catching the
  `zoom_token`/`access_token` leak the five specified keys alone would have missed —
  a Task-1-documented, correctly-reasoned deviation. `--rescrub` re-applies the current
  scrubber to already-committed fixtures without a live API call. The guard test
  (`frozenFixtureSecrets.test.mjs`) globs the whole `fixtures/frozen/` directory and
  passes; I additionally spot-checked every fixture with `/usr/bin/grep -c` for
  `eyJ`/`Bearer`/`pat-na1`/`x-enrichment-secret` value shapes — all zero outside the
  intentional key-name occurrences inside the 4 frozen workflow-body fixtures' jsCode
  (see IN-01 below for one latent, currently-inert issue in this guard's own regex).
- **WR-01/02/05/06/09/10/11/13**: each verified against its own new, well-targeted
  test coverage and against the live call graph (`_writeSafetyAllows` argument shapes,
  `estimate.get(...)` ordering, `_ACTION_LANE_ORDER` keying, `resolve_bound_seconds`
  wiring, presence-before-equality in `verify_decision`, balanced-bracket validation in
  `extract_js_const`, positional `_canonical_rows` indexing).
- **D-74-14** (the enrichment lane's research-error branch, folded from CR-01's same
  root cause): `Companies Research Errored Sentinel`'s mutual-exclusion argument checks
  out structurally against `Research Carry Merge`'s real successor set, and the
  generated `wf_enrichment_cloud.json` shows the sentinel gate wired to exactly
  `Merge Company Fan-In` inputs 1 and 2, matching the two real producers it substitutes
  for on the all-errored path.

One warning and two info-level issues are new observations from this review — not
findings inherited from 73-REVIEW.md, and none block the phase.

## Warnings

### WR-13: `csv_dedupe.py`'s WR-12 fix relocates generated artifacts into the operator's own file-system tree with no corresponding cleanup step

**File:** `operator-claude-plugin/scripts/csv_dedupe.py:96-134` (also
`operator-claude-plugin/skills/contact-upload/SKILL.md`, unchanged by this phase)
**Issue:** 73-REVIEW.md's WR-12 finding asked for `apply_dedupe`'s output paths to be
disambiguated *within the existing gitignored `scratch/` directory* (its suggested fix
appended a hash of the resolved source path to the filename, keeping the write
location unchanged). The implementation instead changed the *default directory itself*
to the input file's own resolved parent — `out_dir = Path(scratch_dir) if scratch_dir
is not None else path.parent`. This does resolve the collision (two same-stem sources
in different directories now write to different directories), and is well-tested
(`test_apply_dedupe_writes_beside_the_input_by_default`,
`test_apply_dedupe_default_output_does_not_collide_across_directories_sharing_a_stem`).

But it is a materially different fix from the one reviewed, with a consequence the
phase's own documentation doesn't account for: `apply_dedupe` is called unconditionally
by `contact-upload/SKILL.md` step 2c on every batch with no explicit `scratch_dir`
argument, so `deduped-<stem>.csv` and `dedupe-report-<stem>.json` now land beside
whatever file the operator handed in — e.g. their own Downloads folder, a shared
drive, wherever their source CSV lives — rather than in the repo's gitignored
`scratch/` directory. `SKILL.md` step 10 ("Clean up") explicitly deletes the step-2b
corrected/split-name copies "same scratch directory, same end-of-batch rule" but says
nothing about the step-2c `deduped_path`/`collapsed_path` outputs (confirmed: `git diff
dd7d8110..HEAD -- operator-claude-plugin/skills/contact-upload/SKILL.md` is empty —
this phase touched no skill doc). Before this fix, every artifact `apply_dedupe`
produced was confined to `SCRATCH_DIR` (gitignored, plugin-internal); after it, two new
files are written next to the operator's own source data on every batch, and nothing
in this repository deletes them.

**Fix:** Either follow the review's original suggested fix (keep the write location at
`SCRATCH_DIR`, disambiguate the filename with a hash of the resolved source path) so no
new file-placement/cleanup surface is introduced, or — if writing beside the input is
kept — add a step to `contact-upload/SKILL.md`'s cleanup section naming
`deduped_path`/`collapsed_path` for deletion, and default the CLI/skill call site to
pass an explicit `scratch_dir` when the operator's own directory shouldn't be written
into (e.g. a network share or a directory outside the operator's control).

## Info

### IN-01: `n8n_arming.set_write_safety`'s rewrite-count assertions moved with the new sentinel, but no other write-gate consumer's fixed-count expectation was audited in this phase's diff

**File:** `operator-claude-plugin/tests/test_control_flag_parity.py:115-161`
**Issue:** This is a lower-confidence observation, not a proven defect: the review
scope's `tests/test_control_flag_parity.py` diff correctly bumps the two counts that
changed (`ALLOW_HUBSPOT_RECORD_WRITES` 3→4, `ALLOW_HUBSPOT_CREATE` 4→5) to account for
the new `Create Failure Row Sentinel` node, and `test_rewrite_counts_are_derived_across
_every_committed_cloud_workflow` (unchanged, still present) re-derives counts from the
live node scan rather than a second hardcoded table, which is the right general
defense. I did not find a second, still-stale hardcoded count anywhere in the diff or
in the surrounding file. Flagging only because the D-74-02 sentinel is a second
instance of a pattern (`WRITE_SAFETY_GATE_JS`-prefixed Code node, scanned by name
rather than declared in a registry) that a *third* future sentinel could silently
duplicate again in a place this phase's tests don't cover — worth a registry or a
single source-of-truth list the count test derives from, rather than one crafted
test per addition, the next time a write-gated lane grows another starved-lane
sentinel. Not a finding against this phase's own correctness.

### IN-02: `frozenFixtureSecrets.test.mjs`'s placeholder-exclusion regex doesn't match the actual `REDACTED_PLACEHOLDER` text — currently inert, not a live gap

**File:** `tests/n8n/frozenFixtureSecrets.test.mjs:38`
**Issue:** `VALUE_PATTERNS[2]` is `/"x-enrichment-secret":\s*"(?!<redacted>)[^"]+"/` —
the negative lookahead is meant to let the safe placeholder value through without
tripping the guard, but the real placeholder text
(`scripts/freeze_execution_rundata.py`'s `REDACTED_PLACEHOLDER = "<redacted — see
tests/n8n/fixtures/frozen/README.md 'Redaction rule'>"`) does not literally start with
`<redacted>` (it continues with an em-dash, not an immediate `>`), so the lookahead
would NOT exclude it — a fixture containing the literal, safe placeholder string under
an `"x-enrichment-secret"` key would fail this test rather than pass it (verified with
a standalone regex probe: `re.test('"x-enrichment-secret": "<redacted — see
tests/n8n/fixtures/frozen/README.md \'Redaction rule\'>"')` → `true`, i.e. flagged).

This is currently harmless and non-blocking: the widened `_scrub` (CR-04) redacts the
entire `headers` object as a single wholesale replacement rather than redacting one
key within it, so a standalone `"x-enrichment-secret": "<value>"` JSON key never
appears in any committed fixture today (confirmed: zero occurrences of the literal
string `"x-enrichment-secret"` with a trailing colon across every file in
`tests/n8n/fixtures/frozen/`; the only 3 matches for the bare substring are prose
inside sticky-note text in the 4 frozen workflow-body fixtures, which this pattern
correctly does not match). The regex's intended exclusion is therefore dead code today
— it would misfire (false alarm, not false negative — fails closed, not open) only if
a future redaction shape ever reintroduced a per-key placeholder in that exact
position.

**Fix:** Either drop the now-unreachable exclusion clause (the pattern would then just
correctly flag any `"x-enrichment-secret": "<real value>"` shape, which is all it can
currently see), or fix the lookahead to match the real placeholder prefix, e.g.
`(?!<redacted)` (no trailing `>`) so it actually excludes
`REDACTED_PLACEHOLDER`-shaped values if that per-key shape is ever reintroduced.

---

_Reviewed: 2026-09-19T10:46:12Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
