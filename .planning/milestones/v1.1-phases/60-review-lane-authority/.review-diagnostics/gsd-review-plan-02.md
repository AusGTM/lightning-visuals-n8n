---
phase: 60-review-lane-authority
plan: 03
type: execute
wave: 2
depends_on: ["60-01"]
files_modified:
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/review_decision.py
  - operator-claude-plugin/tests/test_written_records.py
  - operator-claude-plugin/tests/test_review_decision.py
autonomous: true
requirements: [D-60-08]
user_setup: []

estimate:
  tokens: 60000
  raw_tokens: 60000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "D-60-08: a review decision appears in the per-run `written_records-<run_id>.json` artifact, so one artifact answers \"what did this session write to HubSpot\" across all three grantable lanes."
    - "D-60-08 carries D-59-09: the artifact is keyed by a `run_id` minted once per triage batch — one file per run, readers glob and union, never a shared append."
    - "D-60-08 carries D-59-10: a written-records failure NEVER stops or aborts a review write — the write's own outcome is returned regardless, with the bookkeeping failure recorded in the returned envelope and surfaced loudly."
  artifacts:
    - operator-claude-plugin/scripts/written_records.py
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_written_records.py
  key_links:
    - "`review_decision.submit_decision(run_id=...)` -> `written_records.append_chunk(run_id, 0, response_item, classify=classify_review_item)` -> `durable_paths._atomic_write_0600`, called AFTER the POST returns, never before."
    - "`classify_review_item` -> `REVIEW_OUTCOME_TO_OUTCOME` -> the SAME eight-word vocabulary `report_enrichment` and `run_report` already key on, so no downstream reader learns a new word."
---

<objective>
Make a review decision show up in the run's durable "what actually got written" artifact,
using the artifact's existing per-run file, existing entry shape and existing eight-word
outcome vocabulary — and make it structurally impossible for that bookkeeping to stop a
write.

Purpose: now that all three lanes are grantable, one artifact should answer "what did this
session write to HubSpot" for all three. Review decisions go through `submit_decision`, never
`chunking.dispatch_plan`, so this is new plumbing rather than a reused call site — and the
review response's five-key contract carries no `action`, no `hs_object_id` and no `row_id`,
so `classify_item` cannot be pointed at it as-is.

Output: `classify_review_item`, `REVIEW_OUTCOME_TO_OUTCOME`, a `classify=` keyword on
`append_chunk`, a `run_id` keyword on `submit_decision`, and the two failure-mode tests that
prove the write always wins over the bookkeeping.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-review-lane-authority/60-CONTEXT.md
@.planning/phases/60-review-lane-authority/60-RESEARCH.md
@.planning/phases/60-review-lane-authority/60-PATTERNS.md
@.planning/phases/59-frictionless-write-path/59-CONTEXT.md
@.planning/phases/60-review-lane-authority/60-01-SUMMARY.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: A review decision, in the artifact's own vocabulary</name>

  <read_first>
    - operator-claude-plugin/scripts/written_records.py (whole file; especially the module docstring, `_FORBIDDEN_NAME_MARKERS` at 180-183 — note `arm`, `grant` and `permission` are SUBSTRING markers — the eight outcome constants at 137-156, `WRITE_ACTIONS`/`ACTION_TO_OUTCOME` at 158-176, `written_records_path` at 206-216, `outcome_for_action` at 219-245, `classify_item` at 248-304, `append_chunk` at 353-405)
    - operator-claude-plugin/scripts/review_decision.py as Plan 01 left it (the outcome vocabulary at 96-98, `_unavailable` at 148-150, `_post_decision`'s success return at 202-210, `submit_decision`)
    - operator-claude-plugin/scripts/report_enrichment.py lines 100-115 (the counter keyed on `written_records.ALL_OUTCOMES`, the reason review outcomes must map INTO that vocabulary rather than add words to it)
    - operator-claude-plugin/scripts/run_report.py lines 697-712 (`_build_run_report`'s glob-and-filter-by-run_id read, the consumer of these entries)
    - .planning/phases/60-review-lane-authority/60-PATTERNS.md § written_records.py (the shape-mismatch analysis)
  </read_first>

  <files>operator-claude-plugin/scripts/written_records.py, operator-claude-plugin/tests/test_written_records.py</files>

  <behavior>
    - Test 1: `classify_review_item` on an `applied` approve with a record id returns an entry
      whose `outcome` is `WRITE_ATTEMPTED`, `action` is `review_approve`, `hs_object_id` is the
      record id, and `reason`/`row_id`/`association` are all `None`.
    - Test 2: `rejected` maps the same way with `action` `review_reject`.
    - Test 3: `not_allowlisted` maps to `GATED`; `stale`, `no_candidate` and `not_flagged` map
      to `NO_ACTION`; `refused` maps to `FAILED`.
    - Test 4: an `{available: False, ...}` envelope and an unrecognised outcome word both map
      to `FAILED` — never to a silent success.
    - Test 5: every value `classify_review_item` can produce for `outcome` is in
      `written_records.ALL_OUTCOMES` — derived from the constant, not restated.
    - Test 6: the entry's key set is exactly `classify_item`'s seven keys, so `run_report` and
      `report_enrichment` need no change.
    - Test 7: `append_chunk(..., classify=classify_review_item)` writes a document at
      `written_records_path(run_id)` whose `run_id` field is that run id, and appends to a
      second call rather than replacing it.
  </behavior>

  <action>
Add `REVIEW_OUTCOME_TO_OUTCOME` to `written_records.py`, directly below `ACTION_TO_OUTCOME`, mapping the review endpoint's seven outcome words onto the existing eight-word vocabulary: `applied` and `rejected` to `WRITE_ATTEMPTED`; `not_allowlisted` to `GATED`; `stale`, `no_candidate` and `not_flagged` to `NO_ACTION`; `refused` to `FAILED`. Comment the two choices a reader will question. First, why `WRITE_ATTEMPTED` and not `WRITTEN`: `outcome_for_action`'s own rule is that an id known before the write proves only that the write was attempted, and a review decision always names its record up front, so `WRITE_ATTEMPTED` is the honest word — and the response's `verified` field is explicitly documented in `review_decision.verify_decision` as a convenience and never the authority, so this module must not promote an entry on the strength of it. Second, why `not_allowlisted` is `GATED` and not `FAILED`: it is the deployed write gate refusing, the same event `write_blocked` already maps to `GATED` for dispatch, and calling one of them a failure and the other a gate would split one fact across two words.

Add `classify_review_item(item)` beside `classify_item`, pure and no I/O, raising `WrittenRecordsError` on a non-dict for the same fail-loud reason. It reads `object_type`, `record_id`/`hs_object_id`, `decision` and `outcome` off the item and emits EXACTLY `classify_item`'s seven keys: `object_type` (defaulting to `"contacts"`, matching `classify_item`'s own default so one convention exists), `action` as `review_approve` or `review_reject` derived from the decision word (anything else is `review_unknown`), `hs_object_id`, `outcome` from the mapping with `FAILED` as the total fallback, and `reason`, `row_id`, `association` all `None`. Document why `reason` is deliberately `None` and must stay so: the operator's own words already live on the record itself in `lv_enrichment_review_reason`, so the artifact loses nothing by omitting them — and free operator prose containing `arm`, `grant` or `permission` would trip `_looks_forbidden`, which is a substring check, and raise on a bookkeeping write that must never be able to raise. Run the same `_looks_forbidden` sweep over the finished entry that `classify_item` runs, so the Phase 23 D-11 guarantee holds identically on this path.

Give `append_chunk` a keyword-only `classify=classify_item` parameter and call `classify(item)` in its comprehension instead of the hard-coded name. Amend its docstring's "two call sites" paragraph to three, naming `review_decision.submit_decision` as the third and stating that its `chunk_index` is always `0` because that function sends exactly one request per decision, exactly as `dispatch.dispatch` already does — and that entries accumulate across decisions because a document already at this path is always this run's own earlier writes (D-59-09).

Add the seven tests above to `test_written_records.py`, in a section headed with a dated comment naming D-60-08 and stating why the review response could not be fed to `classify_item` unmodified: it carries no `action` key at all, so `outcome_for_action(None, ...)` would resolve every single review decision through the `FAILED` fallback — an approve that landed would be filed as a failure. Keep the file's existing discipline of redirecting `written_records_path` to a `tmp_path` through monkeypatch; never touch the operator's real durable directory.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -x</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_report_enrichment.py -q</automated>
    <fails_when>non-zero exit — a review entry must not change what an existing artifact reader sees</fails_when>
  </verify>

  <acceptance_criteria>
    - Source assertion: `python3 -c "import sys; sys.path.insert(0,'operator-claude-plugin/scripts'); import written_records as w; assert set(w.REVIEW_OUTCOME_TO_OUTCOME.values()) <= w.ALL_OUTCOMES"` exits 0.
    - Behavior assertion: `classify_review_item({'outcome': 'applied', 'decision': 'approve', 'record_id': '9605284724', 'object_type': 'companies'})` returns a dict whose keys equal `classify_item`'s key set and whose `reason` is `None`.
    - Behavior assertion: `classify_review_item({'available': False, 'reason': 'endpoint_unreachable'})` returns `outcome == written_records.FAILED`.
    - Behavior assertion: an item whose `decision` is the string `"approve"` but whose operator-supplied text elsewhere contains a forbidden marker still classifies without raising, because no free text reaches the entry.
    - Test command: both pytest commands above exit 0.
  </acceptance_criteria>

  <reversibility rating="costly">D-60-08: review decisions never pass through `chunking.dispatch_plan`, so this is a second writer of the artifact rather than a reused call site; removing it later means unpicking that second writer.</reversibility>

  <done>A review decision maps into the artifact's existing seven-key entry and eight-word outcome vocabulary, carries no free text, and `append_chunk` can write it without a second atomic-write implementation.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire it at the write, and make the bookkeeping unable to stop it</name>

  <read_first>
    - operator-claude-plugin/scripts/review_decision.py as Plan 01 left it (`submit_decision`, `_post_decision`, `_unavailable`)
    - operator-claude-plugin/scripts/chunking.py lines 530-560 (the canonical `append_chunk` call site, INSIDE the loop immediately after the response is appended — the placement rule this task copies) and lines 25-45 (the docstring paragraph on the two ways `append_chunk` can go short)
    - operator-claude-plugin/scripts/dispatch.py lines 95-115 (the single-request call site, the closer analog for review)
    - operator-claude-plugin/scripts/run_state.py (`new_run_id` — the minter the skills already use)
    - operator-claude-plugin/scripts/remainder_queue.py lines 225-240 (the precedent for a catch WIDER than `OSError`, and its stated reason)
    - .planning/phases/59-frictionless-write-path/59-CONTEXT.md § D-59-09 and D-59-10
  </read_first>

  <files>operator-claude-plugin/scripts/review_decision.py, operator-claude-plugin/tests/test_review_decision.py</files>

  <behavior>
    - Test 1: `submit_decision(..., run_id="r-1")` on a successful approve writes one entry to
      `written_records_path("r-1")`, and the returned envelope is unchanged from the no-run_id
      case apart from a new `written_records` key reporting `True`.
    - Test 2: with `run_id=None` nothing is written and no path is resolved — the artifact is
      opt-in, and a caller that never passes a run id behaves exactly as before this plan.
    - Test 3: the append is called AFTER the POST — a transport whose POST raises never
      reaches the artifact, and the returned envelope is the ordinary `endpoint_unreachable`
      one.
    - Test 4 (D-59-10, the load-bearing one): with `append_chunk` monkeypatched to raise
      `OSError`, `submit_decision` still returns the write's own outcome, and the envelope's
      `written_records` key reports the failure rather than swallowing it.
    - Test 5 (D-59-10, second shape): with `append_chunk` monkeypatched to raise
      `WrittenRecordsError`, the same holds — this is the shape that DOES propagate out of
      `append_chunk` by design, so the review call site is the one that must contain it.
    - Test 6: three decisions under one `run_id` produce three entries in ONE file, and a
      fourth decision under a different `run_id` produces a separate file.
  </behavior>

  <action>
Give `submit_decision` a keyword-only `run_id=None` appended after `transport`. After `_post_decision` returns and only then, when `run_id` is not None, build the item the classifier reads — `object_type`, the record id, the decision word and the response's `outcome` — and call `written_records.append_chunk(run_id, 0, item, classify=written_records.classify_review_item)` inside a `try` whose `except` catches `Exception`, not `OSError`. Say why the wider catch, citing `remainder_queue.py`'s own precedent: `append_chunk` swallows `OSError` but deliberately propagates `WrittenRecordsError`, and on the dispatch path that propagation is correct because a shape defect there is a defect in the backend's own response — but here the item is built locally and a bookkeeping refusal must never convert into a mid-decision stop, which is exactly what D-59-10 forbids. Attach the result to the returned envelope under a `written_records` key: `True` on success, `False` when the append returned falsey, and a short refusal string naming the exception TYPE (never its text, which can carry a path or a header) when it raised. Do not swallow it silently and do not log it away — the key is what makes the failure loud. Import `written_records` at module top level; it imports only `durable_paths` and stdlib, so there is no cycle and no client/backend boundary crossing.

Amend `submit_decision`'s docstring with the run-id contract: `run_id` is minted ONCE per triage batch by the caller through `run_state.new_run_id()`, before any HTTP call, the same idiom `enrich-records/SKILL.md` already uses for a dispatch run; it is never generated inside this function, because a per-decision id would scatter one sitting across N files and defeat the one-artifact-per-run rule (D-59-09). State that `run_id=None` writes nothing at all, so every existing caller is unaffected.

Add the six tests above to `test_review_decision.py`, monkeypatching `written_records.written_records_path` to a `tmp_path` file exactly as `test_written_records.py` does, so the operator's real durable directory is never touched.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py operator-claude-plugin/tests/test_written_records.py -x</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests -q && .venv/bin/python -m pytest -q</automated>
    <fails_when>non-zero exit from either suite, or either summary line reports a failed or errored test</fails_when>
  </verify>

  <acceptance_criteria>
    - Behavior assertion: with `append_chunk` raising `OSError`, `submit_decision`'s return value still carries the endpoint's `outcome` and `would_write`, and `result["written_records"]` is a non-`True` value naming the exception type.
    - Behavior assertion: the same holds with `WrittenRecordsError` — this is the case the wider catch exists for and it must be a separate test, not a parametrisation that could be deleted as a duplicate.
    - Behavior assertion: with `run_id=None`, `written_records.written_records_path` is never called (assert via a monkeypatched spy).
    - Source assertion: `grep -c 'except Exception' operator-claude-plugin/scripts/review_decision.py` is at least 2 — the pre-existing transport catch plus this one — and the new one sits AFTER the `_post_decision` call, not around it.
    - Test command: both suite commands above exit 0.
  </acceptance_criteria>

  <reversibility rating="costly">D-60-08, as above: this is the second writer of the artifact.</reversibility>

  <done>A review decision under a run id lands in that run's own written-records file, the append happens only after the write already happened, and no bookkeeping failure of either shape can stop, abort or hide a review write.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator free text → durable disk | A review reason is the operator's own words; the artifact must never persist an arming-, grant- or secret-shaped value (Phase 23 D-11). |
| bookkeeping → the live write | A durable-state failure must never be able to stop or reverse a HubSpot write already in flight (D-59-10). |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-60-10 | Information Disclosure | the review entry's `reason` field | high | mitigate | The entry's `reason` is fixed at `None` — operator prose never reaches disk through this path; the reason already lives on the HubSpot record. `_looks_forbidden` still sweeps every finished entry, so the Phase 23 D-11 guarantee holds identically. Pinned by a test that feeds a marker-bearing input and asserts no raise and no persisted text. |
| T-60-11 | Denial of Service | `append_chunk` raising into a live decision | high | mitigate | The review call site catches `Exception`, not `OSError`, because `WrittenRecordsError` propagates out of `append_chunk` by design. Two separate tests pin both raise shapes returning the write's outcome intact. |
| T-60-12 | Repudiation | a review write missing from the run's artifact | medium | mitigate | The append is keyed by the batch's own `run_id` and happens immediately after the POST, so a session that dies later still leaves every decision that landed before the crash on disk — the same partial-run guarantee D-59-07 gives dispatch. |
| T-60-13 | Tampering | a review outcome word leaking into downstream readers | medium | mitigate | `REVIEW_OUTCOME_TO_OUTCOME`'s values are asserted to be a subset of `ALL_OUTCOMES`, so `report_enrichment`'s counter and `run_report`'s record builder need no change and cannot meet an unknown word. |
| T-60-SC | Tampering | npm/pip/cargo installs | low | accept | No package is installed by this plan; `60-RESEARCH.md` records the same. |
</threat_model>

<artifacts_this_plan_produces>
- `written_records.REVIEW_OUTCOME_TO_OUTCOME` — the review-to-shared outcome map
- `written_records.classify_review_item(item)` — pure, seven-key, `reason=None` by design
- `written_records.append_chunk(..., classify=classify_item)` — new keyword-only parameter
- `review_decision.submit_decision(..., run_id=None)` — new keyword; envelope gains a `written_records` key
- New tests: the seven mapping/shape cases, and the six wiring cases including both raise shapes

The full phase-level artifact list is in `60-01-PLAN.md` § Artifacts this phase produces.
</artifacts_this_plan_produces>

<verification>
- `.venv/bin/python -m pytest -q` and `.venv/bin/python -m pytest operator-claude-plugin/tests -q` both green.
- `node --test tests/n8n/*.test.mjs` green — this plan touches no JS.
- `git status --porcelain n8n/` empty.
- No test writes to the operator's real durable directory: `test_written_records.py`'s existing pytest guard stays in force and every new test monkeypatches the path.
</verification>

<success_criteria>
One file per run answers "what did this session write to HubSpot" for the review lane as well
as the two dispatch lanes, in the vocabulary every existing reader already speaks — and no
failure of that bookkeeping, of either raise shape, can stop or hide a review write.
</success_criteria>

<output>
Create `.planning/phases/60-review-lane-authority/60-03-SUMMARY.md` when done
</output>
