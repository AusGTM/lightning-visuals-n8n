---
status: complete
quick_id: 260829-hjm
task: "Sequence-inventory meta-test: extract every documented module.function(...) call sequence from SKILL.md python blocks and fail when it is neither claimed by a composition test nor deliberately allowlisted with a reason"
date: 2026-08-29
requirements: []
actuals:
  tokens: 5900
  tasks: 1
  commits: 2
---

# Quick 260829-hjm: skill-sequence composition guard — Summary

New `operator-claude-plugin/tests/test_skill_sequence_coverage.py` (11 tests, all pure
functions of text/AST plus one live-corpus census pin) extracts every documented
`module.function(...)` call sequence of two-or-more `scripts/`-module calls from every
`skills/*/SKILL.md` python block and fails the suite when a sequence is neither claimed
by a named composition test (`COVERED`) nor deliberately excluded with a reason
(`NOT_A_PIPELINE` / `GRANDFATHERED_UNCOVERED`). A block that will not parse even after
placeholder substitution (`<override or None>` → dummy identifier) fails loudly, naming
the skill and line, rather than being silently skipped. This closes the recurrence
vector `.planning/debug/knowledge-base.md`'s `composition-boundary-blind-spot` entry left
open: five defects in one week shipped past three green suites because every unit was
tested and the documented sequences joining them were tested nowhere; nothing yet
stopped a sixth.

Zero production-code changes, as required. `operator-claude-plugin/.claude-plugin/plugin.json`
bumped 0.28.2 → 0.28.3 with a matching CHANGELOG entry, same commit as the test file.

## The census (8 identities, extracted from the live corpus 2026-08-29)

| # | Skill | Line | Tuple | Disposition |
|---|---|---|---|---|
| 1 | `contact-upload` | 288 | `config_gate.load_config → write_grant.authorize_send → write_grant.authorize_ungranted_send → n8n_arming.armed_window → dispatch.dispatch` | GRANDFATHERED |
| 2 | `enrich-before-ingest` | 114 | `config_gate.load_config → chunking.plan_chunks → chunking.chunk_ceiling → preingest.match_batch → preingest.classify_matches` | GRANDFATHERED |
| 3 | `enrich-before-ingest` | 291 | `config_gate.load_config → enrichment.resolve_providers → chunking.plan_chunks → chunking.chunk_ceiling → write_grant.authorize_send → write_grant.authorize_ungranted_send → n8n_arming.armed_window → chunking.dispatch_plan → preingest.merge_enriched` | GRANDFATHERED |
| 4 | `enrich-before-ingest` | 401 | same tuple as #1, different skill | GRANDFATHERED |
| 5 | `enrich-before-ingest` | 447 | `extraction.hold_emailless → extraction.strip_row_id → extraction.write_dispatch_csv` | **COVERED** |
| 6 | `enrich-before-ingest` | 527 | `run_manifest.load → run_manifest.rows_to_resume` | **COVERED** |
| 7 | `enrich-records` | 281 | `config_gate.load_config → enrichment.resolve_providers → chunking.plan_chunks → chunking.chunk_ceiling → write_grant.authorize_send → write_grant.authorize_ungranted_send → n8n_arming.armed_window → chunking.dispatch_plan` | GRANDFATHERED |
| 8 | `review-triage` | 70 | `review_queue.policy_class → review_queue.record_link` | NOT_A_PIPELINE |

`MAX_GRANDFATHERED = 5`, exactly matching the 5 GRANDFATHERED_UNCOVERED entries. Each
carries a reason naming the specific undriven join (not "no test found") — see the
registry in the test file for full text. Two priors flagged in the plan as likely
grandfathered were confirmed exactly so: #1/#4 (the `authorize → armed_window →
dispatch` chain, defect F2's shape — `walk-write-path-defects` KB entry records the
live operator walk as its one still-open dimension) and #3 (whose only apparent
neighbour, `test_step_5_flattens_dispatch_plans_responses_before_merging`, asserts
SKILL.md *wording/ordering as text*, not the sequence's execution — not coverage per
the honesty rule). #2 and #7 were newly determined during this task's census: in both
cases `chunking.chunk_ceiling`'s real return value (vs. a literal ceiling) or the
authorization layer (`resolve_providers`/`authorize_*`/`armed_window`) never actually
feeds the downstream call in any existing test.

#5 and #6 were confirmed COVERED by reading the candidate test's body and verifying it
actually drives the result-consuming joins (not just imports or asserts prose):
`test_preingest_merge.py::test_the_documented_step_7_sequence_reaches_a_written_dispatch_csv`
chains `hold_emailless → strip_row_id → write_dispatch_csv`;
`test_run_manifest.py::test_a_resume_re_requests_only_rows_that_still_needed_work`
chains `run_manifest.save → run_manifest.load → run_manifest.rows_to_resume` and then
re-drives `match_batch` on the resumed rows, asserting on the resulting request ids.

## The guard bites — twice, as required

**Permanent (unit test, no filesystem):**
`test_the_guard_bites_permanently_on_a_synthetic_unregistered_sequence` feeds the pure
helpers a synthetic SKILL.md string with an unregistered two-call block and asserts the
formatted violation message names the skill, the line, the call tuple, and both
remedies.

**Live, once (real SKILL.md, reverted):** appended a fake block to
`operator-claude-plugin/skills/review-triage/SKILL.md` (after its final section)
documenting `preingest.build_rows_spec(rows)` then
`extraction.write_dispatch_csv(spec["rows"], out_path)`, ran
`.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py -q`,
observed it FAIL, reverted with `git checkout -- operator-claude-plugin/skills/review-triage/SKILL.md`,
confirmed `git diff` empty (byte-identical), re-ran and observed PASS. The actual
failure message, pasted verbatim:

```
AssertionError: new, unregistered SKILL.md sequence(s): ['UNREGISTERED SKILL SEQUENCE: review-triage/SKILL.md line 191 documents the call sequence [preingest.build_rows_spec -> extraction.write_dispatch_csv], which no composition test claims (COVERED) and no registry deliberately excludes (NOT_A_PIPELINE / GRANDFATHERED_UNCOVERED). Either (1) write a composition test that drives this sequence end to end -- not its units in isolation -- and register its nodeid in COVERED, or (2) if this is genuinely not a pipeline (no result flows between the calls), add it to NOT_A_PIPELINE with a reason.']
assert not {('review-triage', ('preingest.build_rows_spec', 'extraction.write_dispatch_csv'))}
```

## Verification

- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` → **1721 passed, 5
  skipped** (baseline 1710/5 + 11 new tests, 0 failures).
- `.venv/bin/python -m pytest --collect-only -q | grep -c skill_sequence_coverage` →
  `11` (non-zero) → root collection includes the plugin tests, so root's expected
  count is `3317 + 11`, not `3317`.
- `.venv/bin/python -m pytest -q` → **3328 passed, 154 skipped** — exactly `3317 + 11`,
  confirming the prediction and zero regressions.
- `node --test tests/n8n/*.test.mjs` → **776 passed, 0 failed** — unchanged by
  construction (no file under `n8n/` or `tests/n8n/` touched).
- `git diff --stat` — only `operator-claude-plugin/.claude-plugin/plugin.json` and
  `operator-claude-plugin/CHANGELOG.md` modified (plus the new test file, untracked);
  no `test_plugin_manifest.py` change needed (it does not pin a version string).
  Zero files under `operator-claude-plugin/scripts/`, `src/`, `n8n/`, or `scripts/`.
- Operator's durable directory
  (`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`):
  md5sum of every `.json` file identical before and after a full
  `operator-claude-plugin/tests` run. **Correction to the plan's stated baseline:**
  the directory holds 5 files as of this task, not the "exactly 3" the plan's
  constraint 7 stated — all 5 predate this session (timestamps 07:09–11:05 vs. task
  start ~13:06 local), i.e. left over from other same-day work, not something this
  task added or should have zeroed out. What matters for the constraint — that this
  task's own test run adds/changes nothing in that directory — is confirmed by the
  identical before/after md5sums.

## Decisions Made

- **Placeholder-substitution + AST parsing over regex extraction.** The design (PLAN.md)
  specified this; implemented via `ast.NodeVisitor.visit_Call` with `generic_visit`
  recursion, which yields a pre-order (outer-before-inner) traversal — matches every
  nested-call ordering in the live census (`chunking.plan_chunks(spec,
  chunking.chunk_ceiling(cfg))` extracts as `plan_chunks` then `chunk_ceiling`) without
  needing a manual sort by source position.
- **Identity excludes block index, includes skill_name.** Per design: reordering blocks
  must not churn registry keys; `contact-upload` block 1 and `enrich-before-ingest`
  block 8 share a call tuple but are two identities because their skill_name differs.
- **Staleness guard checks only the sink (last) call's bare function name**, not every
  name in the tuple — a realistic covering test substitutes a fixture (`fake_config`)
  for `config_gate.load_config` by design, so demanding every name would force a
  dishonest weakening of the guard later (explicit design constraint).
- **Grandfathered every UNDETERMINED census item where the honesty rule was even
  slightly ambiguous**, per the plan's explicit "when in doubt, grandfather it"
  instruction — 5 of 8 identities ended up grandfathered rather than 3. This is
  consistent with the plan's own expectation ("expect these to grandfather citing that
  open item" for #1/#4) and the scope fence (this task ships the ratchet, not the
  backfill).

## Deviations from Plan

None — plan executed exactly as written. The one factual correction (durable-directory
file count, 5 not 3) is documented above under Verification, not a deviation from
required behavior — the actual required invariant (no files added/changed by this
task's test runs) holds.

## Follow-on, deliberately not built here (per plan)

- A stub harness that actually runs each skill's documented sequence.
- A typed pipeline object making a seam mismatch a construction-time error.
- Composition tests for the 5 `GRANDFATHERED_UNCOVERED` entries — each is its own task,
  and each shrinks `MAX_GRANDFATHERED` by one. The most actionable next one is #1/#4
  (the `authorize → armed_window → dispatch` chain, defect F2's shape) since
  `walk-write-path-defects` already names the live-walk methodology needed to close it.

## Next Steps

None required — this is a standalone guard. It will fire automatically the next time
any `SKILL.md` gains a new two-or-more-call documented sequence without a matching
`COVERED`/`NOT_A_PIPELINE` registry entry.

---
*Quick task: 260829-hjm-skill-sequence-composition-guard*
*Completed: 2026-08-29*
