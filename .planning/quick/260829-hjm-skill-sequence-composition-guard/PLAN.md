---
task: 260829-hjm-skill-sequence-composition-guard
type: quick
mode: full
created: 2026-08-29
autonomous: true
files_modified:
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
production_code_changes: none
---

<objective>
Ship a **sequence-inventory meta-test**: one new pytest module that extracts the documented
`module.function(...)` call sequences from the `SKILL.md` python blocks and FAILS when a
sequence is neither claimed by a named composition test nor deliberately allowlisted with a
reason.

Purpose: five defects in one week shipped past three green suites. All five were the same
shape — every unit correct and individually tested, the documented sequence joining them
tested nowhere (`.planning/debug/knowledge-base.md` § `composition-boundary-blind-spot`).
The per-seam fixes landed; nothing yet stops a sixth seam. This is the ratchet.

Output: `operator-claude-plugin/tests/test_skill_sequence_coverage.py`, a version bump, a
CHANGELOG entry.

**Zero production-code changes are required, and none are permitted.** This task adds a test
that reads `SKILL.md` text and test-file text. It never imports, executes, or modifies any
script under `operator-claude-plugin/scripts/`. Every item on the hard-constraint
do-not-touch list (`write_grant.plan_grant` authorization, n8n write-safety gate nodes, the
material-conflict judge gate, the non-clobber merge policy, per-send armed-window narrowing,
the verbatim no-invention sentence in `extraction.md`) is untouched by construction.

**Scope fence: this task ships the ratchet. It does NOT backfill missing composition tests.**
A sequence found uncovered today is recorded honestly in `GRANDFATHERED_UNCOVERED` with a
written reason and a shrink-only ceiling. Writing those tests is follow-on work.
</objective>

---

## Design (decided — the executor implements this, it does not re-derive it)

### What counts as "a sequence"

**Rule: a python fenced block in a `SKILL.md` that contains two or more calls whose base name
is a module under `operator-claude-plugin/scripts/`.**

The module set is derived at runtime from `{p.stem for p in scripts_dir.glob("*.py")}` — zero
maintenance, and it is exactly the documented idiom (skills always call `module.function`).
This filter is load-bearing: without it, `config.get(...)` and `responses.extend(...)` pollute
the identity tuples and they stop being stable.

**Deliberately NOT required: dataflow between the calls.** Tracking "a later call consumes an
earlier call's result" needs assignment tracking, and a clever filter that quietly drops a
real seam is the exact failure mode being guarded against. Over-include, then allowlist with a
reason. On today's corpus this costs exactly one entry (`review-triage` block 1, two
independent read-only lookups) and buys a rule a reader can verify by eye.

### Sequence identity

`(skill_name, ordered tuple of "module.function" names, in source order)`.

- **Not** the block index — inserting a block earlier in a file must not churn every key.
- A **new** sequence = a tuple absent from every registry/allowlist → fails.
- A **changed** sequence = the old tuple orphans its registry entry (fails: "entry matches no
  documented block, update or remove it") *and* the new tuple is unregistered (fails). Both
  fire. That is the systemic guard the knowledge base says is still open: the operative manual
  rule is "any change that edits a documented call sequence must land a test that drives it".
- Two blocks in one skill documenting the identical tuple collapse to one identity. Fine — one
  entry covers both. `contact-upload` block 1 and `enrich-before-ingest` block 8 have the same
  tuple but different skills, so they stay two identities.

### The three known extraction gotchas (do not rediscover these)

1. **Blocks are indented ~3 spaces** — they sit inside numbered lists. `grep '^```python'`
   finds nothing. Match `^[ \t]*```python` and `textwrap.dedent` before parsing.
2. **Most high-value blocks are not valid Python.** They carry placeholders:
   `<this send's ids>`, `<override or None>`, `<allow_create>`, `<object_type>`, `<path>`,
   `<spec>`. Substitute `<[^<>\n]*>` → a dummy identifier before `ast.parse`.
   **If a block still fails to parse after substitution, the meta-test FAILS naming the skill
   and line.** A silently skipped block is precisely the blind spot this exists to close.
3. Blocks contain `...` (Ellipsis) and comments — both parse fine after (1) and (2).

### How a test claims a sequence

A module-level `COVERED` dict: identity → test nodeid string (`"test_file.py::test_name"`).
The meta-test asserts the file exists and contains `def <test_name>(`.

Plus one cheap **staleness guard**: extract that function's source text and assert it mentions
the sequence's *sink* (last) function name. This catches a typo'd nodeid and a covering test
refactored out from under its name. It is a staleness guard, **not** proof of coverage — do
not extend it to require every name in the tuple: realistic covering tests use the
`fake_config` fixture rather than calling `config_gate.load_config`, and demanding all names
would force a dishonest weakening later.

### Two allowlists, not one

- `NOT_A_PIPELINE` — permanent, `reason` per entry. Blocks the over-inclusive rule flags that
  are genuinely not pipelines.
- `GRANDFATHERED_UNCOVERED` — shrink-only, `reason` per entry, ratcheted by
  `MAX_GRANDFATHERED = <census count>` asserted `len(GRANDFATHERED_UNCOVERED) <= MAX_GRANDFATHERED`.
  Adding one requires a deliberate, reviewable constant bump.

Assert also: every allowlist key still matches an extracted sequence (an orphan fails, forcing
removal when a grandfathered block is rewritten), and `COVERED ∪ GRANDFATHERED ∪ NOT_A_PIPELINE`
is disjoint and exhaustive over the extracted set.

### Expected census — 8 identities on today's corpus

Pin this as an assertion. Verified by extraction against the current files:

| # | Skill | Block (line) | Tuple, in source order |
|---|---|---|---|
| 1 | `contact-upload` | 1 (~L288) | `config_gate.load_config`, `write_grant.authorize_send`, `write_grant.authorize_ungranted_send`, `n8n_arming.armed_window`, `dispatch.dispatch` |
| 2 | `enrich-before-ingest` | 3 (~L114) | `config_gate.load_config`, `chunking.plan_chunks`, `chunking.chunk_ceiling`, `preingest.match_batch`, `preingest.classify_matches` |
| 3 | `enrich-before-ingest` | 6 (~L291) | `config_gate.load_config`, `enrichment.resolve_providers`, `chunking.plan_chunks`, `chunking.chunk_ceiling`, `write_grant.authorize_send`, `write_grant.authorize_ungranted_send`, `n8n_arming.armed_window`, `chunking.dispatch_plan`, `preingest.merge_enriched` |
| 4 | `enrich-before-ingest` | 8 (~L401) | same tuple as #1 |
| 5 | `enrich-before-ingest` | 9 (~L447) | `extraction.hold_emailless`, `extraction.strip_row_id`, `extraction.write_dispatch_csv` |
| 6 | `enrich-before-ingest` | 12 (~L527) | `run_manifest.load`, `run_manifest.rows_to_resume` |
| 7 | `enrich-records` | 1 (~L281) | `config_gate.load_config`, `enrichment.resolve_providers`, `chunking.plan_chunks`, `chunking.chunk_ceiling`, `write_grant.authorize_send`, `write_grant.authorize_ungranted_send`, `n8n_arming.armed_window`, `chunking.dispatch_plan` |
| 8 | `review-triage` | 1 (~L70) | `review_queue.policy_class`, `review_queue.record_link` |

Nested-call ordering (`chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg))`) follows
`ast.walk`/source order — whatever the implementation yields deterministically is fine, but
the tuples above assume outer-before-inner. Adjust the table to match the implementation if it
differs; do not contort the implementation to match the table.

The seven remaining python blocks carry fewer than two scripts-module calls and are correctly
invisible: `enrich-before-ingest` 1, 2, 4, 5, 7, 10, 11.

### Census truth as of writing

- **#5 is COVERED**, confirmed by reading it:
  `tests/test_preingest_merge.py::test_the_documented_step_7_sequence_reaches_a_written_dispatch_csv`
  chains `hold_emailless → strip_row_id → write_dispatch_csv`.
- **#8 is NOT_A_PIPELINE**: two independent read-only lookups (`policy_class`, `record_link`)
  bound into lambdas, no result flows between them.
- **#1–#4, #6, #7 are UNDETERMINED — the executor performs the census** (see Task 1
  acceptance criteria). Two unverified priors, flagged as such: #1 and #4 are the
  `authorize → armed_window → dispatch` chain that is defect F2's shape, and the knowledge
  base records a live operator walk as its one still-open dimension — expect these to
  grandfather citing that open item. #3 has neighbours in
  `tests/test_enrich_before_ingest_skill_contract.py` (`test_step_5_flattens_dispatch_plans_responses_before_merging`)
  that assert the *prose*, not the sequence's execution — a prose assertion is not coverage.

**Honesty rule:** an entry may claim a test only if that test actually drives the
result-consuming joins of the sequence. Importing the modules, naming them in a docstring, or
asserting the SKILL.md wording is NOT coverage. When in doubt, grandfather it.

---

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: sequence-inventory meta-test + honest census</name>

  <read_first>
    - `.planning/debug/knowledge-base.md` — last entry, `composition-boundary-blind-spot` (the spec)
    - `operator-claude-plugin/tests/test_preingest_merge.py` lines 246–279 — exemplar A,
      `test_the_documented_step_7_sequence_reaches_a_written_dispatch_csv`
    - `operator-claude-plugin/tests/test_chunking.py` line 846 —
      exemplar B, `test_enrichment_and_contacts_writes_from_the_same_run_share_one_file`.
      **NOTE: the planning brief attributes this test to `tests/test_dispatch_multipart.py`.
      That attribution is wrong — grep confirms it lives in `test_chunking.py:846`. Do not
      chase the wrong file, and register the true nodeid if this test is cited.**
    - `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` lines 1–60 —
      precedent for a test that parses `SKILL.md` with `re` + `pathlib`
    - `operator-claude-plugin/tests/conftest.py` — the autouse `no_durable_writes` fixture
    - `operator-claude-plugin/tests/test_plugin_manifest.py` — the most likely home of a
      version↔CHANGELOG coupling assertion; read it BEFORE bumping so the bump does not
      surprise you mid-run
    - `operator-claude-plugin/.claude-plugin/plugin.json` and
      `operator-claude-plugin/CHANGELOG.md` — the two files being modified; the CHANGELOG's
      existing entry format is the one to follow
    - all nine `operator-claude-plugin/skills/*/SKILL.md`
  </read_first>

  <files>
    operator-claude-plugin/tests/test_skill_sequence_coverage.py (new),
    operator-claude-plugin/.claude-plugin/plugin.json,
    operator-claude-plugin/CHANGELOG.md
  </files>

  <behavior>
    Write the module-level helpers as PURE FUNCTIONS taking text, so the guard's own logic is
    unit-testable against a synthetic `SKILL.md` string with no filesystem involved:
    - `extract_python_blocks(text)` → list of (block_index, line_number, dedented_source)
    - `parse_calls(source, module_names)` → ordered tuple of "module.function" strings
    - `sequences_in(skill_name, text, module_names)` → list of identities
    - `scripts_modules()` → the module-name set from `scripts/*.py`
    - a violation formatter returning the failure message text, so the message is assertable

    Test expectations, written before the implementation:
    - a synthetic SKILL.md string with an indented ```python block containing two
      scripts-module calls yields exactly one identity with the calls in source order
    - a block with one scripts-module call plus a `config.get(...)` and a
      `responses.extend(...)` yields NO identity (the module filter works)
    - a block that will not parse even after placeholder substitution raises/fails naming the
      skill and line — never silently skipped
    - placeholder substitution: a block containing `<this send's ids>` and `<override or None>`
      parses
    - the violation message for an unregistered synthetic sequence contains: the skill name,
      the block line number, the rendered call tuple, and BOTH remedies (write a composition
      test and register its nodeid in `COVERED`; or add it to `NOT_A_PIPELINE` with a reason)
    - the live corpus's extracted identity set equals the union of the three registries —
      one set-equality assertion, which is simultaneously the census pin (the registries hold
      the 8 identities of the census table). No second hard-coded count or list.
    - `len(GRANDFATHERED_UNCOVERED) <= MAX_GRANDFATHERED`
    - every `COVERED`/`GRANDFATHERED_UNCOVERED`/`NOT_A_PIPELINE` key matches a live extracted
      identity (no orphans)
    - the three sets are pairwise disjoint and jointly exhaust the extracted set
    - every `COVERED` nodeid resolves: the file exists, contains `def <name>(`, and that
      function's source mentions the sequence's sink function name
  </behavior>

  <action>
    Create `operator-claude-plugin/tests/test_skill_sequence_coverage.py` implementing the
    Design section above verbatim: `extract_python_blocks` matching `^[ \t]*```python` and
    `textwrap.dedent`-ing the body; placeholder substitution `<[^<>\n]*>` → a dummy identifier
    before `ast.parse`; `parse_calls` keeping only `ast.Call` nodes whose func is an
    `ast.Attribute` over an `ast.Name` whose id is in `scripts_modules()`; identity =
    `(skill_name, call_tuple)`.

    Declare three module-level mappings — `COVERED` (identity → nodeid), `NOT_A_PIPELINE`
    (identity → reason), `GRANDFATHERED_UNCOVERED` (identity → reason) — plus
    `MAX_GRANDFATHERED` set to the census count you actually find. Seed `COVERED` with census
    #5 → `test_preingest_merge.py::test_the_documented_step_7_sequence_reaches_a_written_dispatch_csv`
    and `NOT_A_PIPELINE` with census #8 → "two independent read-only lookups bound into
    lambdas; no result flows between them".

    Perform the census for identities #1, #2, #3, #4, #6, #7: for each, grep
    `operator-claude-plugin/tests/` for the sequence's sink function name, read the candidate
    tests, and decide. Register in `COVERED` ONLY if the candidate test actually calls the
    result-consuming joins; otherwise place it in `GRANDFATHERED_UNCOVERED` with a specific
    reason naming what is missing (not "no test found" — say which join is undriven). Apply
    the honesty rule from the Design section: a prose/wording assertion about SKILL.md is not
    coverage.

    The module performs pure text and AST analysis of files on disk. It must not import any
    module from `operator-claude-plugin/scripts/`, must not execute skill code, must make no
    network call, and must not write anything — the autouse `no_durable_writes` fixture stays
    in force and is never bypassed or overridden.

    Bump `operator-claude-plugin/.claude-plugin/plugin.json` version 0.28.2 → 0.28.3 and add
    a matching `operator-claude-plugin/CHANGELOG.md` entry naming the guard and its purpose,
    in the SAME commit as the test file.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py -q</automated>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests -q</automated>
  </verify>

  <acceptance_criteria>
    1. `operator-claude-plugin/tests/test_skill_sequence_coverage.py` exists and
       `.venv/bin/python -m pytest operator-claude-plugin/tests -q` reports **1710 + N passed
       / 5 skipped, zero failures**, where N is the number of tests added by this file.
       No pre-existing test changes result.
    2. `grep -cE "^(    )?def test_" operator-claude-plugin/tests/test_skill_sequence_coverage.py`
       is ≥ 8 (the behaviors listed in `<behavior>` are each their own test).
    3. The extractor pin is the **set equality itself** — `COVERED ∪ GRANDFATHERED_UNCOVERED ∪
       NOT_A_PIPELINE == extracted identities`, asserted as one comparison, with the three
       registries collectively holding exactly the 8 census identities and no others. Do NOT
       add a separate hard-coded "exactly 8" list: the registry keys already ARE the census,
       and a second copy means every legitimate future addition edits two places and makes the
       criterion-8 demo fail twice, only one of which names the offending block.
    4. `grep -n "MAX_GRANDFATHERED" operator-claude-plugin/tests/test_skill_sequence_coverage.py`
       shows the constant declared once and asserted once as `<=`.
    5. Every entry in `NOT_A_PIPELINE` and `GRANDFATHERED_UNCOVERED` carries a non-empty
       reason string; a test asserts this for every entry rather than by eye.
    6. Every `COVERED` nodeid resolves: file exists, `def <name>(` present, that function's
       source mentions the sequence's sink function name. Asserted by the module itself.
    7. **The guard bites (permanent):** a test feeds a synthetic `SKILL.md` string containing
       an indented ```python block with two unregistered scripts-module calls to the pure
       helpers and asserts the violation fires, AND that the formatted message contains the
       skill name, the block line number, the call tuple, and both remedies.
    8. **The guard bites (one-time live demo, recorded in the commit message or the task
       record):** append a fake python block documenting `preingest.build_rows_spec(...)` then
       `extraction.write_dispatch_csv(...)` to a real `SKILL.md`; run
       `.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py -q`;
       observe it FAIL naming that skill and block; revert the SKILL.md edit
       (`git checkout -- <path>`); re-run and observe it PASS. Paste the failure message text
       into the task record. `git status` must be clean of that file afterwards.
    9. `git diff --stat` touches nothing under `operator-claude-plugin/` except the three
       named paths (`tests/test_skill_sequence_coverage.py`, `.claude-plugin/plugin.json`,
       `CHANGELOG.md`), plus at most one existing test file if it pins the plugin version.
       **Zero files under `operator-claude-plugin/scripts/`, `src/`, `n8n/`, or `scripts/`.**
       Files under `.planning/` (the task record) may ride along or land in a separate
       docs-only commit — a commit touching no `operator-claude-plugin/` file needs no
       version bump.
    10. `plugin.json` reads `"version": "0.28.3"` and `CHANGELOG.md` has a `0.28.3` entry, in
        that same commit.
  </acceptance_criteria>

  <done>
    A new documented `SKILL.md` call sequence with no registered composition test fails the
    plugin suite with a message naming the skill, the block, the sequence, and what to do —
    demonstrated live, then reverted. The census is recorded honestly: which sequences are
    covered today, which are grandfathered and why, ratcheted shrink-only.
  </done>
</task>

</tasks>

---

<verify>
Commands of record. Never bare `python -m pytest`.

```
.venv/bin/python -m pytest operator-claude-plugin/tests -q
```
Expected: **1710 + N passed, 5 skipped, 0 failed** (baseline 1710/5).

```
.venv/bin/python -m pytest -q
```
**Zero failures is the gate; the count is conditional.** Baseline is 3317 passed / 154
skipped. Root collection very likely *includes* `operator-claude-plugin/tests` — the
knowledge-base entry records root 3285 / plugin 1678 while the current baselines are root
3317 / plugin 1710, both up by exactly 32 with node flat at 776. If so, root becomes
**3317 + N**, not 3317, and your own new tests are not a regression. Determine it once and
record which:

```
.venv/bin/python -m pytest --collect-only -q | grep -c skill_sequence_coverage
```

Non-zero → root collects the plugin tests → expect 3317 + N. Zero → expect 3317 exactly.

Separately: if any test (root or plugin) pins the plugin version or a CHANGELOG shape, update
it in the same commit — see `read_first` for `test_plugin_manifest.py`.

```
node --test tests/n8n/*.test.mjs
```
Expected: **776 passed, 0 failed** — unchanged by construction (no file under `n8n/` or
`tests/n8n/` is touched). Glob form only; the directory form is broken on node 24.
</verify>

---

## Artifacts this task produces

| Path | Status | What it is |
|---|---|---|
| `operator-claude-plugin/tests/test_skill_sequence_coverage.py` | new | The sequence-inventory meta-test: extractor, three registries, the ratchet, and the permanent bite-demo unit test |
| `operator-claude-plugin/.claude-plugin/plugin.json` | modified | version 0.28.2 → 0.28.3 |
| `operator-claude-plugin/CHANGELOG.md` | modified | 0.28.3 entry |
| task record (this directory) | appended | the census table as found, and the pasted failure message from acceptance criterion 8 |

## Follow-on, deliberately not built here

The operator considered and rejected two alternatives for this task; record them, do not build
them:

- **A stub harness that actually runs each skill's documented sequence** — strongest proof, but
  needs a stub per lane and ongoing upkeep. This is the natural next step if the inventory test
  proves its worth.
- **A typed pipeline object making seam mismatches construction-time errors** — a wide refactor
  of a hot path, and it only covers type-shaped seams, not behavioural ones.

Also deferred: writing the composition tests for whatever lands in `GRANDFATHERED_UNCOVERED`.
Each is its own task, and each shrinks `MAX_GRANDFATHERED` by one.
