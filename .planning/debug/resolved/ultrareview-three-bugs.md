---
slug: ultrareview-three-bugs
status: awaiting_human_verify
trigger: "properly fix bug_002 bug_001 bug_003"
created: 2026-08-29
updated: 2026-08-29
---

# Debug session — three defects from the 2026-08-29 cloud review

Three bugs, already root-caused and independently corroborated. This session is a **fix-and-verify**
session, not a discovery one: the investigation is done, the mechanisms are proven, and the
approach for the largest one has been ruled on by the operator. Do not re-derive the causes;
verify them, fix them, and — critically — close the test gap that let them ship.

## Symptoms

**Expected behavior.** An operator following `enrich-before-ingest/SKILL.md` verbatim carries a
batch through ingest → enrichment → HubSpot write under one grant, unattended. The plugin's test
suite leaves no trace in the operator's real state directory. The two skills relay the same
machine-readable resolution guidance in the same terms.

**Actual behavior.**
1. The documented step 7 sequence raises before writing anything — **the flow cannot reach a
   HubSpot write at all**.
2. Running the plugin test suite deposits hundreds of `written_records-*.json` files into the
   operator's live durable state directory.
3. The two skills disagree on whether `resolution_sources` is one value or several.

**Error message (bug_002), reproduced live during the 2026-08-29 operator walk:**

```
ExtractionError: Row 0 carries key(s) outside the canonical set and cannot be
written to the dispatch CSV: ['row_id']
```

**Timeline.** All three were introduced or exposed by Phase 59 (plugin 0.21.0 → 0.28.0, shipped
2026-08-28/29). bug_002 was found by the Phase 53 operator walk run 2 (2026-08-29) and
independently confirmed by cloud review. bug_001 was found in the same walk. bug_003 is new from
the review. **All three survived three fully green suites** (root 3285/3308, plugin 1678/1701,
node 776) — that is the defining fact of this session.

**Reproduction.**
- bug_002: follow `enrich-before-ingest/SKILL.md` steps 2 → 5 → 7 on any input. Deterministic.
- bug_001: run `.venv/bin/python -m pytest operator-claude-plugin/tests -q`, then list
  `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/written_records-*.json`.
- bug_003: read `enrich-records/SKILL.md:329-332` beside `enrich-before-ingest/SKILL.md:336-340`.

## Evidence (already gathered — do not re-derive)

### bug_002 — `normal` — the ingest composition cannot execute

Three individually-correct behaviours meet at a boundary no test crosses:

- `preingest.build_rows_spec` (**preingest.py:82**) mints `row_id` INTO each row:
  `spec_rows.append({**row, "row_id": f"row-{i + 1}"})`. Skill step 2 requires calling it, and
  every downstream stage joins by `row_id`, so it must be minted there.
- `preingest.merge_enriched` (**preingest.py:561**) folds with `merged = dict(row)`, preserving
  every existing key including `row_id`. The unanswered branch (**:565**) uses the same dict.
- `extraction.write_dispatch_csv` (**extraction.py:875-882**) is the STRUCT-01 enforcement site:
  `extra = sorted(set(row.keys()) - allowed)` where `allowed = set(canonical_props(mapping_path))`.
  `row_id` is absent from `config/column_mapping.yaml` — correctly, it is a join key, not a
  HubSpot property. The raise fires BEFORE `out_path` is opened, so no file is created.
- `extraction.hold_emailless` (**extraction.py:833-847**) partitions on email only and preserves
  all keys — it never strips.
- **No strip helper exists anywhere.** grep for `strip` / `canonical_only` / `for_dispatch` /
  `drop_plugin_internal` across `extraction.py` and `preingest.py` returns nothing, and no
  SKILL.md names one. `contact-upload/SKILL.md` never mentions `write_dispatch_csv`, so
  `enrich-before-ingest/SKILL.md:434-435` is the sole documented site for this sequence.

**Why the tests missed it:** each unit is tested — `build_rows_spec`'s mint, `merge_enriched`'s
merge, and `write_dispatch_csv`'s raise (`test_write_dispatch_csv_raises_on_row_with_key_outside_canonical_set`,
which proves the guard *deliberately*). **No test chains the four together.**

### bug_001 — `nit` — the test suite writes into the operator's real state directory

- Phase 59-01 put `written_records.append_chunk(run_id, index, body)` inline in
  `chunking.dispatch_plan`'s loop (**chunking.py:394-407**).
- `append_chunk` resolves via `written_records_path(run_id)` →
  `durable_paths.resolve_state_path().parent`. With `LV_OPERATOR_CONFIG` / `CLAUDE_PLUGIN_DATA`
  unset (the normal test environment) that is the operator's **real** directory.
- `operator-claude-plugin/tests/conftest.py` has an autouse `no_network` fixture
  (**lines 575-592**) but **no** equivalent guarding durable-state writes.
- The five tests 59-08/59-09 added DO monkeypatch `written_records.written_records_path` to
  `tmp_path` (test_chunking.py:677, 699, 721, 748, 766). The ~25 pre-existing `dispatch_plan`
  callers (test_chunking.py:373-790) were never back-fixed.
- Measured: **413** files created at 07:00 on 2026-08-29, exactly when this session ran the
  suites; 1 more at 08:00 from the operator walk.

**Severity correction, verified this session — do not overstate this bug.** `written_records.load()`
with no path argument globs and unions everything, but **it has ZERO shipped callers** — only
tests (18 references). Both skills point the operator at `written_records-<run_id>.json` *by
run_id*, which is the per-run read and is correct. So this is a **latent** defect on the union
reader plus real pollution of the operator's directory — **not** a live operator-visible
data-quality failure. An earlier claim in this session that an operator would see 400+ stale rows
was wrong and has been retracted.

### bug_003 — `nit` — singular/plural drift between two aligned skills

- `RecordSpecError.__init__` (**enrichment.py:95-118**) types `sources` as a tuple, plural by
  construction, validated against `RESOLUTION_SOURCES`.
- GATE-02 (**enrichment.py:352-367**) emits `company: ("hubspot_lookup", "operator_statement")`,
  `email: ("provider_result", "hubspot_lookup")`, `linkedin_url: ("same_row_derivation",)`.
  GATE-03 (**enrichment.py:427-436**) emits a `name` entry with **three** sources.
- `enrich-records/SKILL.md:329-332` says *"name which of the four `resolution_sources` values …
  it claims"*; `enrich-before-ingest/SKILL.md:336-340` says *"naming the `resolution_sources`
  value the entry claims"* — the second is unambiguously singular, and the two disagree.
- Impact is limited because each entry's `detail` prose enumerates the options in words and the
  same instruction requires relaying `detail`. It is a quality/consistency defect on the
  machine-readable line, which is meant to be the source of truth.

## Operator ruling on scope (2026-08-29) — binding, do not re-open

**bug_002 is fixed with a strip helper plus the missing composition test.** Add `strip_row_id`
(or an equivalent `drop_plugin_internal_keys`) in `extraction.py` and call it between
`hold_emailless` and `write_dispatch_csv` in the skill's step 7. This keeps the STRUCT-01 guard
genuine.

**Rejected, with reasons recorded:**
- *Exempting `row_id` from the canonical check* — smallest diff, but it blurs what STRUCT-01
  means and every future internal key inherits the exemption by precedent.
- *Carrying `row_id` alongside rows rather than inside them* — the real structural fix, and the
  operator agrees it is the better end state, but it touches `build_rows_spec`, `merge_enriched`,
  `classify_matches`, `chunking` and every lane that joins by `row_id`. Too wide a blast radius
  to bolt onto a fix session; it wants its own plan. **Record it as the follow-up**, do not
  silently drop it.

## Current Focus

hypothesis: CONFIRMED for all three. All three fixes applied, each with a regression test that
reproduces red on the pre-fix code and passes green after. Full suites re-run clean at every step;
no stray files added to the operator's real durable directory during any test run.
test: Self-verification complete — root suite (3312/154 vs baseline 3308/154, +4 new tests), plugin
suite (1705/5 vs baseline 1701/5, +4 new tests), node suite (776/0 unchanged). Real durable
directory file count checked before and after every suite run: 413, unchanged throughout.
expecting: Awaiting operator confirmation this holds in their real workflow, and a decision on the
413 stray files (proposed for cleanup, not deleted).
next_action: awaiting human verification — see CHECKPOINT REACHED in this session's return

## Hard constraints for the fix

1. **Every fix lands with a test that would have caught it.** This is the fourth defect class this
   week to survive three green suites because tests drive unit boundaries and not documented
   sequences. A fix without its composition test repeats the mistake.
2. **bug_001's fix goes in ONE place** — an autouse fixture in
   `operator-claude-plugin/tests/conftest.py` monkeypatching `durable_paths.resolve_state_path`
   (or `written_records.written_records_path`) to a per-test `tmp_path`, mirroring the existing
   `no_network` idiom. Do NOT patch ~25 call sites. Consider additionally refusing a durable write
   when `PYTEST_CURRENT_TEST` is set, as defence in depth.
3. **Do NOT touch** — operator-confirmed load-bearing: `write_grant.plan_grant`'s authorization
   control and its no-HubSpot-search structural test; the n8n write-safety gate nodes; the
   material-conflict judge gate; the non-clobber merge policy; the verbatim no-invention sentence
   in `extraction.md`; per-send armed-window narrowing.
4. **`write_dispatch_csv`'s email gate stays.** Only the non-canonical-key check is in scope, and
   only via an upstream strip — the guard itself is not weakened.
5. **Release hygiene:** any commit touching `operator-claude-plugin/` bumps
   `.claude-plugin/plugin.json` AND adds a `CHANGELOG.md` entry in the SAME commit. Current
   shipped version is **0.28.0**.
6. **Do not hand-edit `n8n/wf_enrichment_cloud.json`** (generated). Phase 46 parity rule applies if
   any shared predicate is touched — it should not be.
7. **The 413 stray files are the operator's data directory.** Cleaning them is reasonable but is a
   deletion in the operator's live state — propose it, do not do it silently.

## Test commands of record

System python lacks the deps. Use exactly:

```
.venv/bin/python -m pytest -q                               # baseline 3308 passed / 154 skipped
.venv/bin/python -m pytest operator-claude-plugin/tests -q  # baseline 1701 passed / 5 skipped
node --test tests/n8n/*.test.mjs                            # baseline 776 pass / 0 fail (glob form ONLY)
```

## Primary sources

- `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD-2.md` — FINDING A and
  FINDING B, live evidence
- `.planning/HANDOFF-2026-08-29-ultrareview.md` — project purpose, operator constraint, § 5 the
  recurring failure mode
- `.planning/phases/59-frictionless-write-path/59-CONTEXT.md` — D-59-07..D-59-10
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — the broken sequence, step 7

## Evidence

- timestamp: 2026-08-29 (this session)
  checked: reproduced bug_002 by scripting the documented sequence directly —
  `preingest.build_rows_spec` → `preingest.merge_enriched` → `extraction.hold_emailless` →
  `extraction.write_dispatch_csv`.
  found: `write_dispatch_csv` raised `ExtractionError: Row 0 carries key(s) outside the
  canonical set and cannot be written to the dispatch CSV: ['row_id']`, matching the operator
  walk's live error verbatim. Confirmed red before any fix.
  implication: bug_002 confirmed reproducible in isolation, matches the prior investigation's
  root cause exactly.

- timestamp: 2026-08-29 (this session)
  checked: real durable state directory file count before touching anything —
  `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/written_records-*.json`.
  found: 413 files, matching the prior investigation's measurement exactly.
  implication: bug_001's pollution is real and unchanged since the prior session; establishes
  the baseline this session's fix must not grow.

- timestamp: 2026-08-29 (this session)
  checked: `operator-claude-plugin/tests/test_written_records.py`'s `_patch_durable_dir` idiom
  (patches `durable_paths.resolve_state_path` directly) versus the planned autouse fixture
  (patching `written_records.written_records_path`) — first attempt broke 4 pre-existing
  `load()`-round-trip tests, since `written_records.load()`'s no-path branch resolves via
  `durable_paths.resolve_state_path().parent` DIRECTLY, bypassing `written_records_path`
  entirely, while `append_chunk` (and my fixture) went through `written_records_path`.
  found: an unconditional autouse override of `written_records_path` diverges from a test's
  own `_patch_durable_dir` isolation, since the two resolve through different call chains for
  writes (`written_records_path`) versus no-path reads (`durable_paths.resolve_state_path`
  directly). Fixed by making the autouse wrapper check whether `durable_paths.resolve_state_path`
  is still the real, unpatched function at call time — only substituting the safe tmp_path
  default when nothing else has isolated it, deferring to the real chain otherwise.
  implication: `durable_paths.resolve_state_path`/`durable_dir` themselves cannot be patched
  globally either — `test_durable_paths.py` asserts on their real return values directly
  in-process (by its own documented design), so a blanket override there would break that
  file's whole purpose. `written_records.written_records_path`, patched conditionally, was the
  only safe target.

- timestamp: 2026-08-29 (this session)
  checked: full suite runs after each fix (root, plugin, node) plus real durable directory file
  count before/after each run.
  found: root suite 3312 passed / 154 skipped (baseline 3308/154, +4 new tests: bug_002
  composition test, bug_001 regression test, bug_003's 2 parity tests); plugin suite 1705
  passed / 5 skipped (baseline 1701/5); node suite 776 pass / 0 fail (baseline unchanged).
  Real durable directory file count: 413 before and after every run — no new pollution.
  implication: all three fixes are green with no regressions; the fixes close exactly the gaps
  named without touching anything on the hard-constraints "do not touch" list.

## Eliminated

_(none — no hypothesis was disproven this session; all three causes were confirmed exactly as
the prior investigation root-caused them)_

## Resolution

root_cause:
- bug_002: `preingest.build_rows_spec` mints `row_id` into every row; `merge_enriched` and
  `hold_emailless` both preserve it (by necessity — every stage upstream of dispatch joins by
  it); `write_dispatch_csv`'s STRUCT-01 guard correctly refuses any row carrying a key outside
  the canonical set. No strip existed at the one boundary where the key must be dropped.
- bug_001: `chunking.dispatch_plan`'s inline `written_records.append_chunk` flush resolves its
  path via `written_records_path(run_id)` with no test-suite-wide guard; the plugin's autouse
  `no_network` fixture had no durable-write equivalent, so the ~25 pre-existing `dispatch_plan`
  test callers wrote into the operator's real state directory.
- bug_003: `enrich-records/SKILL.md` and `enrich-before-ingest/SKILL.md` were edited
  independently for the same D-59-08 gap closure and drifted to different (one ambiguous, one
  unambiguously singular) phrasings of how many `resolution_sources` values a `resolvable`
  entry can carry, when the underlying data (`sources` tuple, up to 3 of 4 values per entry)
  is plural.

fix:
- bug_002: added `extraction.strip_row_id(rows)` — drops the `row_id` key, non-mutating.
  `enrich-before-ingest/SKILL.md` step 7 now calls it between `hold_emailless` and
  `write_dispatch_csv`.
- bug_001: added autouse `no_durable_writes` fixture (`tests/conftest.py`) redirecting
  `written_records.written_records_path` to a per-test `tmp_path`, deferring to a test's own
  `durable_paths.resolve_state_path` patch (the pre-existing `_patch_durable_dir` idiom) when
  present, so both isolation mechanisms compose rather than fight. Added defense-in-depth in
  `written_records.append_chunk`: refuses (degrades, does not raise) a write that still
  resolves into the real durable directory while `PYTEST_CURRENT_TEST` is set.
- bug_003: reworded both skills' `resolvable`-relay instructions to "name every
  `resolution_sources` value" / "naming every `resolution_sources` value" the entry's
  `sources` tuple carries — matching prose in both files now.

verification:
- bug_002: new composition test `test_the_documented_step_7_sequence_reaches_a_written_dispatch_csv`
  (`operator-claude-plugin/tests/test_preingest_merge.py`) drives all four documented functions
  in sequence and asserts a CSV is written with no `row_id` column.
- bug_001: new regression test
  `test_dispatch_plan_never_writes_into_the_operators_real_durable_directory`
  (`operator-claude-plugin/tests/test_chunking.py`) calls `dispatch_plan` with no
  written-records patching of its own and asserts the real directory's file count is
  unchanged. Confirmed manually: real directory held 413 files before and after every full
  suite run in this session.
- bug_003: new file `operator-claude-plugin/tests/test_resolution_sources_relay_parity.py`
  (2 tests) asserts both skills instruct enumerating every value and neither implies a single
  value. Confirmed by hand against the pre-fix git-committed text (`git show HEAD:...`) that
  both new assertions would have failed on the original wording — a genuine red→green test.
- Full suites, all green, all baselines matched or exceeded (see Current Focus for exact
  counts). No hard-constraint "do not touch" surface was edited (verified by `git diff --stat`
  below).

files_changed:
- operator-claude-plugin/scripts/extraction.py (bug_002: `strip_row_id`)
- operator-claude-plugin/scripts/written_records.py (bug_001: defense-in-depth guard)
- operator-claude-plugin/skills/enrich-before-ingest/SKILL.md (bug_002 step 7 call; bug_003 reword)
- operator-claude-plugin/skills/enrich-records/SKILL.md (bug_003 reword)
- operator-claude-plugin/tests/conftest.py (bug_001: `no_durable_writes` autouse fixture)
- operator-claude-plugin/tests/test_chunking.py (bug_001 regression test)
- operator-claude-plugin/tests/test_preingest_merge.py (bug_002 composition test)
- operator-claude-plugin/tests/test_resolution_sources_relay_parity.py (new file, bug_003 parity tests)
- operator-claude-plugin/.claude-plugin/plugin.json (0.28.0 → 0.28.1)
- operator-claude-plugin/CHANGELOG.md (0.28.1 entry)

oracle_type: derived (contract) — each new test asserts against the documented/coded contract
(STRUCT-01's canonical-key set, the autouse-fixture idiom `no_network` already establishes, and
the `RecordSpecError.resolvable` schema's own `sources` tuple), not merely against a crash.

open_items_for_operator:
- The 413 pre-existing stray `written_records-*.json` files in the real durable directory are
  UNCHANGED by this session (proposed for cleanup below, not deleted per hard constraint 7).
- The wider structural fix for bug_002 (carrying `row_id` beside rows rather than inside them)
  remains a named, deferred follow-up — not started this session, recorded in the CHANGELOG.
