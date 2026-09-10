---
phase: quick-260911-anv
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/judge_reason_distribution.py
  - tests/test_judge_reason_distribution.py
  - .planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md
autonomous: true

must_haves:
  truths:
    - "The todo records, with its evidence, that Judge Gate already emits judge_reasons on every row it passes downstream — no builder change was needed."
    - "The todo records the max_uses value baked into the committed n8n/wf_enrichment_cloud.json research nodes, and states that a cloud body's value is a build-time literal rather than a runtime env read."
    - "The todo records either a measured judge-reason distribution sampled from past executions, or an explicit statement that the sample was not achievable offline plus the reason."
    - "scripts/build_cloud_workflows.py and every n8n/wf_*.json are byte-unchanged by this plan."
    - "The escalation confidence band stays [75, 85] and the RO-2 judge-gate test stays green."
  artifacts:
    - scripts/judge_reason_distribution.py
    - tests/test_judge_reason_distribution.py
    - .planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md
  key_links:
    - "scripts/judge_reason_distribution.py reuses enrichment_cost_ledger._list_executions / _get_execution / _node_output_items rather than opening its own n8n reader."
    - "The distribution reads the 'Judge Gate' and 'Contact Judge Gate' node output (every row, escalated or not) — the denominator scripts/replay_judge_models.py cannot supply, because it reads 'Build Judge Request' and drops rows whose judge_request_body is null."
---

<objective>
Answer the operator's 2026-09-11 "measure first" ruling on todo
`2026-08-04-enrichment-throughput-ceiling` and write the three answers into the todo.
No gate change. Band bounds stay `[75, 85]`.

**Conflict resolution with sibling item 260911-ao1 (which also edits
`scripts/build_cloud_workflows.py` and regenerates `n8n/wf_*.json`): neither of the two
options the batch note offered is needed. This plan makes ZERO edits to the builder and
ZERO edits to any `n8n/wf_*.json`,** because part (a) is already true as-built:

- `_enrich_judge_gate_js`'s pass-1 block (`scripts/build_cloud_workflows.py`, both the
  companies and contacts targets) sets `judge_reasons` on EVERY row unconditionally, not
  only on escalating rows;
- `applyCostCap` (`n8n/code/judge.js:207`) spreads the row, preserving it;
- pass 3 returns every row;
- `tests/n8n/judge.test.mjs:444` already pins `judge_reasons: []` on a non-escalating row
  through the built `JUDGE_GATE_BODY`;
- and live runData confirms it: `tests/n8n/fixtures/frozen/exec_12354.runData.json`,
  `Contact Judge Gate`, both rows carry `"judge_reasons": []`.

So `depends_on: []` and the two items cannot collide.

Purpose: turn "confidence_band dominates" from a code read into a recorded number, and
close lever 3's open question, so a future decision on lever 1 has evidence behind it.
Output: one read-only measurement script, its test, and an updated todo.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md
@scripts/replay_judge_models.py
@scripts/enrichment_cost_ledger.py
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Confirm (a) and (b) from the committed artefacts — no edit</name>
  <files>(read-only: scripts/build_cloud_workflows.py, n8n/wf_enrichment_cloud.json, n8n/code/judge.js, tests/n8n/fixtures/frozen/exec_12354.runData.json)</files>
  <action>Establish both offline facts and hold them for Task 3 to record. Do NOT edit the builder and do NOT regenerate any workflow JSON.

(a) Confirm Judge Gate already emits its reasons on the row it passes downstream. Read `_enrich_judge_gate_js` and both targets' `judge_pass1_block_js` in `scripts/build_cloud_workflows.py`, `applyCostCap` in `n8n/code/judge.js`, the assertion at `tests/n8n/judge.test.mjs:444`, and the `Contact Judge Gate` output items in `tests/n8n/fixtures/frozen/exec_12354.runData.json`. Note for the record which rows carry it (all of them, including rows that never escalate, which carry an empty array) and which node names carry it in the committed cloud workflow (`Judge Gate`, `Contact Judge Gate`).

(b) Confirm the web-research search budget actually in effect in the committed `n8n/wf_enrichment_cloud.json`. Both research-request builder nodes bake the value as a build-time literal via `_flag_const(..., cloud=True)` reading `CONFIG_FLAG_DEFAULTS`, so record BOTH the number and the mechanism: on a cloud body the runtime environment variable of the same name is not read, which means lever 3 is a regenerate-plus-deploy change and not an env edit. Corroborate with the live-observed value in the frozen runData (`research_request_body.tools[0].max_uses` in `exec_12354` / `exec_12356`), and note that committed and live are level as of Gate 10 (CLAUDE.md §13.0.2).</action>
  <verify>
    <automated>.venv/bin/python -c "import json;d=json.load(open('n8n/wf_enrichment_cloud.json'));n={x['name']:x.get('parameters',{}).get('jsCode','') for x in d['nodes']};assert 'WEB_RESEARCH_MAX_SEARCHES = 5' in n['Build Research Request'] and 'WEB_RESEARCH_MAX_SEARCHES = 5' in n['Build Contact Research Request'];assert 'judge_reasons' in n['Judge Gate'] and 'judge_reasons' in n['Contact Judge Gate'];print('ok')"</automated>
    <automated>node --test tests/n8n/judge.test.mjs</automated>
  </verify>
  <done>Both facts are established from committed artefacts, and the working tree is unchanged (`git status --porcelain` shows nothing new from this task).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Read-only judge-reason distribution reader over past executions</name>
  <files>scripts/judge_reason_distribution.py, tests/test_judge_reason_distribution.py</files>
  <behavior>
    - `summarize(run_data)` folds one execution's runData into counts only, over the `Judge Gate` (companies) and `Contact Judge Gate` (contacts) nodes.
    - Every run of a node is folded, not just the first: a node with two runs contributes both runs' items (under v1 a node can fire twice — CLAUDE.md §13.0.3; the run-0-only reader was 62-11's `reader_reads_run_0` defect).
    - Counts per lane and in total: `rows_through_gate`; `rows_research_matched` (items whose `research_candidate.matched` is exactly `true`); `rows_with_reasons` (items whose `judge_reasons` array is non-empty); `rows_capped` (items whose `judge_capped` is exactly `true`); `by_reason`; `by_reason_set` (comma-joined sorted reasons, so a multi-reason row is one set entry).
    - `rows_with_reasons` is counted from the reasons array, never from `needs_judge` — a capped row has reasons and `needs_judge: false`, and counting the flag would under-report the trigger rate.
    - `rows_research_matched` is the honest denominator: `computeEscalation` returns no reasons at all when the research candidate did not match, so unmatched rows would otherwise inflate the base.
    - Malformed input never raises: a missing node, a run without a `data.main` branch, a non-dict item, or an absent `judge_reasons` key each contribute zero rather than an exception.
    - The returned structure holds integers and reason strings only — no row payload, no identity field, no header.
  </behavior>
  <action>Write `scripts/judge_reason_distribution.py`: a read-only CLI that reports the judge-trigger distribution over n8n executions that already happened. It produces no new n8n execution and writes nothing anywhere except its own stdout.

Reuse, do not re-implement: import `_list_executions`, `_get_execution` and `_node_output_items` from `scripts/enrichment_cost_ledger.py` exactly as `scripts/replay_judge_models.py` does (same `sys.path` bootstrap, same module-level `load_dotenv()` call — `.env` is not readable directly, so the credentials must come from that call). Every n8n access is a GET through those two readers and nothing else. Do NOT import `scripts/build_cloud_workflows.py`: importing it regenerates `n8n/code/*.generated.js` as a side effect, which this plan must not do.

Structure it as one pure function plus a thin shell:

- `summarize(run_data)` — pure, no network, implements the `<behavior>` block above. Fold both node names, iterating every run of each.
- `collect(execution_ids=None, limit=100)` — resolves ids (an explicit list, else `_list_executions(limit)` filtered to executions of the enrichment workflow), calls `_get_execution` once per id, reads `data.resultData.runData`, folds `summarize` over each, and merges the counts. Skip an execution that raises rather than sinking the walk, exactly as `extract_corpus` does.
- `main(argv)` — argparse with `--execution-ids` (comma-separated, mirroring `replay_judge_models.py --extract`'s explicit-id convenience), `--limit`, and `--json`. Print the tallies plus the derived share `rows_with_reasons / rows_research_matched` and, for each reason, its share of `rows_research_matched`. Print counts and reason names only.

Note in the module docstring that this reads the `Judge Gate` nodes on purpose, because `replay_judge_models.py` reads `Build Judge Request` and drops every row whose `judge_request_body` is null — which is the whole non-escalating population, so it has escalated rows but no denominator.

Write `tests/test_judge_reason_distribution.py` against `summarize` only (no network). Build one small hand-made runData dict covering, in a single fixture: a node with two runs whose items must BOTH be folded; a row with two reasons; a capped row (reasons present, `needs_judge` false, `judge_capped` true); a row whose research candidate did not match; a row with an empty reasons array; and one malformed run. Assert the exact counts, and assert the returned structure carries no row payload key. Observe the assertions fail before the implementation exists.</action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_judge_reason_distribution.py -x -q</automated>
    <automated>test "$(/usr/bin/grep -v '^[[:space:]]*#' scripts/judge_reason_distribution.py | /usr/bin/grep -cE 'requests\.(post|put|patch|delete)')" = "0"</automated>
    <automated>.venv/bin/python -c "import sys;sys.path.insert(0,'scripts');import judge_reason_distribution as m;print(m.summarize({}))"</automated>
  </verify>
  <done>`summarize` returns zeroed counts on an empty runData without raising, the test file passes, and the module reaches n8n only through the ledger's GET readers.</done>
</task>

<task type="auto">
  <name>Task 3: Run the sample if it is reachable, and record all three answers in the todo</name>
  <files>.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md</files>
  <action>Run `.venv/bin/python scripts/judge_reason_distribution.py --limit 100` (add `--execution-ids` if a targeted set of past enrichment executions is known — the todo's original measurement names executions `1152`, `1109`, `443`, `442`, `337`, `332`, `328`, `18`, and Phase 63's corpus came from the same workflow). If the credentials or the API are unreachable, run it once, capture the exact failure, and stop — do not retry against a different endpoint, do not dispatch anything, do not arm anything. A small sample is a real result: n8n prunes executions and Phase 63 found only 5 judge inputs in total, so record whatever count comes back.

Then append one new section to `.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md`, titled for this measurement and dated 2026-09-11, and bump the frontmatter `updated:` key to `2026-09-11`. The todo stays OPEN and keeps its severity — this records a measurement, it does not close a defect. The section carries all three answers:

(a) The reasons array is already emitted on every row Judge Gate passes downstream, escalating or not, with the four pieces of evidence from Task 1 (builder pass-1 sets it unconditionally for both targets; `applyCostCap` preserves it; `tests/n8n/judge.test.mjs:444` pins the empty-array case through the built node body; frozen live runData `exec_12354` shows it on `Contact Judge Gate`). State plainly that no builder change was made and that the committed `n8n/wf_*.json` are byte-unchanged, and correct the todo's own "Do this first" line, which assumed the logging did not exist yet.

(b) The number Task 1 established for the research search budget in the committed `n8n/wf_enrichment_cloud.json`, for both research-request nodes, whether it agrees with the value named in the todo's lever 3, and the mechanism: a cloud body bakes it as a build-time literal, so changing it is a regeneration plus a deploy, not an environment edit. Cite the frozen runData corroboration and note committed and live are level as of Gate 10.

(c) Either the measured distribution — a small table of counts and the share of research-matched rows on which each reason fired, plus the execution ids and the count scanned — or, if the run did not reach the API, an explicit statement that the sample was not achievable in this session, quoting the failure, with nothing inferred to fill the gap. In BOTH branches, cite the distribution already on disk from Phase 63 as prior evidence: `.planning/milestones/v1.1-phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-REPLAY-VERDICT.json`, whose `reasons_distribution` records 5 escalated judge inputs with `confidence_band` present in all 5 and the sole reason in 3 of 5. Name its limit — it is drawn from `Build Judge Request`, so it counts escalated rows only and has no denominator — and, when (c) succeeded, compare the two.

Record only counts and reason names. Do not paste runData rows into the todo: an execution's runData carries the webhook secret header and contact PII.

Finally, state that lever 1 remains unauthorised and the band is untouched.</action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts -x -q</automated>
    <automated>.venv/bin/python -c "import json,hashlib;d=json.load(open('n8n/wf_enrichment_cloud.json'));n={x['name']:x.get('parameters',{}).get('jsCode','') for x in d['nodes']};assert len(d['nodes'])==287,len(d['nodes']);assert hashlib.sha256(n['Judge Gate'].encode()).hexdigest()[:16]=='5804fec76c32c600';print('workflow untouched')"</automated>
    <automated>test "$(/usr/bin/grep -c 'ESCALATION_CONFIDENCE_BAND = \[75, 85\]' n8n/code/escalation.generated.js)" = "1"</automated>
    <automated>/usr/bin/grep -q '2026-09-11' .planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md && /usr/bin/grep -q '63-JUDGE-REPLAY-VERDICT.json' .planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md</automated>
    <automated>node --test tests/n8n/judge.test.mjs</automated>
  </verify>
  <done>The todo carries a dated section answering (a), (b) and (c) — (c) either as a measured table with its execution ids or as an explicit not-achievable statement quoting the failure — cites the Phase 63 artifact in either branch, and has `updated: 2026-09-11`. The RO-2 test is green, the band literal is unchanged, and `n8n/` plus the builder show no diff.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| repo → n8n Cloud API | credentials from `.env` cross here; only reads are intended |
| n8n runData → committed todo | execution data carrying secrets and PII crosses into a tracked file |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-anv-01 | Information Disclosure | `scripts/judge_reason_distribution.py` output → todo | high | mitigate | Output is integers and reason names only; Task 3 forbids pasting runData rows, which carry `x-enrichment-secret` and contact PII |
| T-anv-02 | Tampering | n8n Cloud workflows / HubSpot records | high | mitigate | Every n8n access is a GET through `enrichment_cost_ledger._list_executions` / `_get_execution`; verified by a gate on the module; nothing is dispatched, deployed, bounced or armed |
| T-anv-03 | Tampering | `n8n/wf_*.json`, `scripts/build_cloud_workflows.py` | medium | mitigate | Part (a) needs no builder edit; Task 3 gates on an empty `git diff` for both paths, which also keeps sibling item 260911-ao1 collision-free |
| T-anv-04 | Elevation of Privilege | judge escalation gate | high | mitigate | No change to `computeEscalation`, `config/escalation_policy.yaml` or the generated band; gated by the RO-2 test plus a literal check that the band is still `[75, 85]` |
| T-anv-05 | Denial of Service | n8n execution budget (Starter, 2.5K/month) | medium | mitigate | Read-only walk over executions that already exist; no new execution is produced |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/test_judge_reason_distribution.py tests/test_judge_spec.py -q`
- `node --test tests/n8n/*.test.mjs`
- `git diff --stat -- n8n/ scripts/build_cloud_workflows.py` prints nothing
</verification>

<success_criteria>
- The todo carries a dated 2026-09-11 section with answers to (a), (b) and (c), and `updated: 2026-09-11`.
- `scripts/judge_reason_distribution.py` exists, reaches n8n by GET only, and reports counts.
- `tests/test_judge_reason_distribution.py` passes and was observed failing first.
- The RO-2 test is green, the band is still `[75, 85]`, and neither the builder nor any workflow JSON changed.
</success_criteria>

<output>
No SUMMARY file — quick-batch item. The deliverable is the updated todo plus the two new files.
</output>
