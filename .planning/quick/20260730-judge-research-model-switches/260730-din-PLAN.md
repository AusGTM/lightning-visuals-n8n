---
phase: quick-260730-din
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/build_cloud_workflows.py
  - scripts/deploy_n8n_workflows.py
  - src/validator_sonnet.py
  - src/web_research.py
  - n8n/code/judge.js
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - .env.example
  - CLAUDE.md
  - tests/test_builder_flag_parity.py
  - tests/test_deploy_flag_overlay.py
  - tests/test_deploy_write_safety_overlay.py
  - tests/test_enabled_build_invariants.py
  - tests/test_main.py
  - tests/test_service.py
  - tests/test_e2e_ingest.py
  - tests/test_contact_ingest.py
  - tests/n8n/enabledResearchLaneFlow.test.mjs
  - tests/n8n/researchRequestSponsorshipContract.test.mjs
  - tests/n8n/contactResearchChainRowFlow.test.mjs
  - tests/fixtures/companies_jscode_frozen.json
  - .planning/STATE.md
autonomous: true
requirements: [SC-1, SC-2, SC-3, SC-4]

must_haves:
  truths:
    - "SC-1: the three old names have zero occurrences under scripts/, src/, tests/, n8n/, .env.example, CLAUDE.md (git-tracked scope; .planning/milestones + docs/reports exempt as historical)"
    - "SC-3 arm-by-default: the DEFAULT (non-overlay) build bakes `const ALLOW_JUDGE_ESCALATION = true;` and this is pinned by a test that fails if it ever regresses to false"
    - "SC-3 cap: the default build bakes MAX_JUDGE_VALIDATIONS_PER_RUN = \"50\""
    - "SC-3 split models: research request nodes read ANTHROPIC_RESEARCH_MODEL, judge request nodes read ANTHROPIC_JUDGE_MODEL, both defaulting claude-sonnet-5 (no behavior change to which model runs)"
    - "SC-2: `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` both green"
    - "SC-3 live: the deployed n8n Cloud workflow, read back via API, carries the same three facts as the committed artifact"
    - "SC-4: every write-safety flag still reads \"false\" in the deployed artifact; zero HubSpot writes occur at any step"
    - "ALLOW_JUDGE_ESCALATION is no longer overlayable — it is absent from _OVERLAY_FLAG_SPEC and pinned into the never-overlayable set"
  artifacts:
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - n8n/code/judge.js
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - .env.example
    - tests/fixtures/companies_jscode_frozen.json
    - "a NEW inverted invariant test in tests/test_enabled_build_invariants.py asserting judge escalation is always true in the committed build"
  key_links:
    - "CONFIG_FLAG_DEFAULTS (build_cloud_workflows.py ~L781) <-> every _flag_const() call site: _flag_const asserts membership, so a missed rename fails loudly at build time rather than silently"
    - "n8n/code/judge.js comments <-> compiled jsCode: inline() concatenates judge.js verbatim into 3 frozen + 3 contacts node bodies, so a judge.js comment IS an occurrence inside n8n/*.json (this is why the comment rename is mandatory, not cosmetic)"
    - "_OVERLAY_FLAG_SPEC deletion <-> tests/test_deploy_flag_overlay.py + tests/test_deploy_write_safety_overlay.py: enable_baked_flags/_requested_overlay_flags RAISE on any unknown flag name, so stale call sites error rather than fail an assert"
    - "the 4 changed frozen nodes <-> tests/fixtures/companies_jscode_frozen.json: exactly 8 of 14 {variant,node} pairs may differ; anything else moving is STOP-and-report"
---

<objective>
Split `ANTHROPIC_SONNET_MODEL` into `ANTHROPIC_RESEARCH_MODEL` + `ANTHROPIC_JUDGE_MODEL`
(both defaulting `claude-sonnet-5` — behavior-preserving), rename
`ALLOW_SONNET_ESCALATION` -> `ALLOW_JUDGE_ESCALATION` with the default flipped to `true`,
and rename `MAX_SONNET_VALIDATIONS_PER_RUN` -> `MAX_JUDGE_VALIDATIONS_PER_RUN` with the
default raised to `50`.

Purpose: arm the judge by default (it is the only guard against the confidently-wrong
Haiku tail observed in the 2026-07-30 A/B eval) and give research vs. judge independent
model levers, so the later Haiku experiment is a one-line default change.

Output: renamed source + rebuilt n8n artifacts, both suites green, a disarmed redeploy
verified by live read-back.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@.planning/quick/20260730-judge-research-model-switches/PLAN.md
@.planning/quick/20260730-judge-research-model-switches/260730-din-CONTEXT.md
@.planning/quick/20260730-judge-research-model-switches/260730-din-RESEARCH.md
</context>

<!-- planner-discipline-allow: ALLOW_SONNET_ESCALATION -->
<!-- planner-discipline-allow: MAX_SONNET_VALIDATIONS_PER_RUN -->
<!-- planner-discipline-allow: ANTHROPIC_SONNET_MODEL -->

<planner_correction>
**RESEARCH.md §1 and §6 are wrong on one load-bearing point — this plan corrects it.**

RESEARCH.md §1 concluded "exactly 3 of 7 frozen nodes change (6/14 pairs)" and §6 filed the
`n8n/code/judge.js` comment mentions as optional greppability. Both were derived from the
Python factory strings alone. Measured against the *compiled* artifacts (verified this
session by walking `n8n/wf_enrichment_cloud.json` / `wf_enrichment_local_live.json` node by
node), `inline()` concatenates judge.js verbatim into the node bodies, so judge.js's two
comment mentions land inside `n8n/*.json`:

| Frozen node | old-name hits in compiled jsCode (cloud) | source of hits |
|---|---|---|
| Research Trigger Gate | 0 | — |
| Build Research Request | 2 | model const + usage |
| Validate Research Output | 0 | — |
| Judge Gate | 6 | flag const + cap const + inlined judge.js comments |
| Build Judge Request | 4 | model const + usage + inlined judge.js comment |
| **Apply Judge Verdict** | **2** | **inlined judge.js comments ONLY** |
| Merge Company | 0 | — |

Two consequences, both binding:

1. **The judge.js comment rename is MANDATORY, not optional.** Success criterion 1 scopes
   `n8n/*.json` at zero occurrences; leaving judge.js alone leaves 6 occurrences across
   both built artifacts. (Zero logic edits — comment text only. No test pins judge.js's
   bytes or hash; `tests/test_judge_spec.py:217` reads it only to regex `_JUDGE_DATA_FIELDS`.)
2. **The frozen-fixture bound is 4 of 7 nodes = 8 of 14 {variant,node} pairs**, not 6/14.
   `Apply Judge Verdict` moves comment-only. Anything OUTSIDE those 4 named nodes moving is
   still STOP-and-report.

Two smaller corrections to the spec's Task 5/Task 8 surveys, also measured this session:
- `tests/test_deploy_write_safety_overlay.py` has a **second** affected site the spec did
  not cite: L159-161 (`test_unrequested_write_flags_are_untouched_by_a_research_only_request`)
  passes the escalation flag through `_requested_overlay_flags()`, which will RAISE (not
  fail an assert) once the overlay entry is deleted. The spec cited only the L140 parametrize.
- `README.md` and `n8n/README.md` contain **zero** occurrences of any of the three old names
  (README.md:112's `ENABLE_BAKED_FLAGS` mention names no flag). The Phase-19 runbook lives
  under `.planning/milestones/v0.4-phases/` = archived/historical = exempt. So the spec's
  Task 8 doc work reduces to `CLAUDE.md` (11 mentions) + the `.planning/STATE.md` note.
</planner_correction>

<tasks>

<task type="auto">
  <name>Task 1: Rename at source (builder, deploy, src, judge.js comments, env example, CLAUDE.md) and rebuild artifacts</name>
  <files>scripts/build_cloud_workflows.py, scripts/deploy_n8n_workflows.py, src/validator_sonnet.py, src/web_research.py, n8n/code/judge.js, .env.example, CLAUDE.md, n8n/wf_enrichment_cloud.json, n8n/wf_enrichment_local_live.json</files>
  <read_first>scripts/build_cloud_workflows.py L778-820 (CONFIG_FLAG_DEFAULTS + _flag_const), L2100-2220 (the four affected node factories); scripts/deploy_n8n_workflows.py L104-140 (_OVERLAY_FLAG_SPEC + module docstring), L370-400 (harness-env docstring); n8n/code/judge.js L38-44 and L179-185 (the two comment blocks)</read_first>
  <action>
Rename in source only — no test edits in this task (Task 2 owns those). Per CONTEXT D-locked
decisions: both model switches default `claude-sonnet-5`; escalation default flips to `true`;
cap default raises to `50`; the deploy overlay entry is DELETED (not renamed).

**scripts/build_cloud_workflows.py**
- `CONFIG_FLAG_DEFAULTS` (~L781): drop the single sonnet model key; add
  `ANTHROPIC_RESEARCH_MODEL: "claude-sonnet-5"` and `ANTHROPIC_JUDGE_MODEL: "claude-sonnet-5"`;
  rename the escalation key to `ALLOW_JUDGE_ESCALATION` with default `"true"`; rename the cap
  key to `MAX_JUDGE_VALIDATIONS_PER_RUN` with default `"50"`. Net 6 -> 7 keys.
- Build Research Request factory (`_enrich_build_research_request_js`, ~L2111/L2117, serves
  BOTH targets): `_flag_const("ANTHROPIC_RESEARCH_MODEL", cloud)` and
  `const model = ANTHROPIC_RESEARCH_MODEL;`.
- Judge Trigger Gate (~L2176-2178): the renamed flag + cap consts and their `allowOn` /
  `MAX_PER_RUN` reads.
- Build Judge Request (~L2209/L2213): `ANTHROPIC_JUDGE_MODEL` const + `const model =` read.
- Sweep the Python `#` comments/docstrings at ~L2102-2103, L2165-2166, L2202-2203 for old names.
- `_flag_const()` asserts the name is in `CONFIG_FLAG_DEFAULTS`, so any call site you miss
  raises at build time — the rebuild in `<verify>` is the completeness check.

**scripts/deploy_n8n_workflows.py**
- `_OVERLAY_FLAG_SPEC` (~L125): DELETE the escalation entry outright (per D: the overlay only
  widens disabled->enabled, so a default-true flag has no meaningful entry). Do NOT add an
  entry under the new name. Emergency-off path is: edit `CONFIG_FLAG_DEFAULTS` + rebuild +
  disarmed redeploy.
- Update the module docstring (~L104) and the harness-env docstring (~L378) to match: only
  `ALLOW_WEB_RESEARCH` plus the write-safety flags remain overlayable, and note that judge
  escalation is now armed at build time.

**src/validator_sonnet.py** — read `ALLOW_JUDGE_ESCALATION` (default `"true"`) and
`ANTHROPIC_JUDGE_MODEL` (default `"claude-sonnet-5"`; drop the stale `-latest` suffix).
**src/web_research.py** — read `ANTHROPIC_RESEARCH_MODEL` (default `"claude-sonnet-5"`).
Keep the module filenames as they are; only the env-var names and defaults change.

**n8n/code/judge.js** — comment text ONLY, zero logic edits. Rename the escalation mention in
the `applyEvidenceSufficiency` header comment (~L41) and in the `applyCostCap` header comment
(~L182). This is mandatory: `inline()` concatenates judge.js into 6 compiled node bodies, so
these two comments are occurrences inside `n8n/*.json`, which criterion 1 scopes at zero. Do
not touch any executable line in this file.

**.env.example** — replace the 3 old lines (L10, L39, L53) with 4: the two model vars (both
`claude-sonnet-5`), `ALLOW_JUDGE_ESCALATION=true`, `MAX_JUDGE_VALIDATIONS_PER_RUN=50`. Keep
each var in its existing section (models near L10, the allow-flag near L39, the cap near L53).

**CLAUDE.md** — rename all 11 mentions (L895, 910, 923, 1243, 1477-1479, 2135, 2144, 3030,
3037, 3346), state the new defaults (`true` / `50`), and add the second model var to the
§11.2 `.env.example` block and the §21.1 kill-switch block. `config/escalation_policy.yaml`'s
`sonnet_5:` section name stays — it names the judge ROLE, not an env var; touch it only if an
old env-var name literally appears there.

Then rebuild: `.venv/bin/python scripts/build_cloud_workflows.py`. `tests/test_companies_factory_frozen.py`
is EXPECTED red after this task (Task 2 re-baselines the fixture) — do not chase it here.
  </action>
  <verify>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python scripts/build_cloud_workflows.py && ! git grep -q -E 'ALLOW_SONNET_ESCALATION|MAX_SONNET_VALIDATIONS_PER_RUN|ANTHROPIC_SONNET_MODEL' -- scripts src n8n .env.example CLAUDE.md && echo SOURCE_CLEAN</automated>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && test "$(grep -c 'const ALLOW_JUDGE_ESCALATION = true;' n8n/wf_enrichment_cloud.json)" = 2 && grep -q 'const MAX_JUDGE_VALIDATIONS_PER_RUN = "50";' n8n/wf_enrichment_cloud.json && test "$(grep -c 'ANTHROPIC_RESEARCH_MODEL' n8n/wf_enrichment_cloud.json)" -ge 1 && test "$(grep -c 'ANTHROPIC_JUDGE_MODEL' n8n/wf_enrichment_cloud.json)" -ge 1 && grep -q 'claude-sonnet-5' n8n/wf_enrichment_cloud.json && echo BAKED_OK</automated>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import build_cloud_workflows as m; d=m.CONFIG_FLAG_DEFAULTS; assert len(d)==7, d; assert d['ALLOW_JUDGE_ESCALATION']=='true', d; assert d['MAX_JUDGE_VALIDATIONS_PER_RUN']=='50', d; assert d['ANTHROPIC_RESEARCH_MODEL']=='claude-sonnet-5', d; assert d['ANTHROPIC_JUDGE_MODEL']=='claude-sonnet-5', d; print('DEFAULTS_OK')"</automated>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import deploy_n8n_workflows as d; assert not any('ESCALATION' in k for k in d._OVERLAY_FLAG_SPEC), d._OVERLAY_FLAG_SPEC.keys(); assert 'ALLOW_WEB_RESEARCH' in d._OVERLAY_FLAG_SPEC; print('OVERLAY_OK', sorted(d._OVERLAY_FLAG_SPEC))"</automated>
  </verify>
  <done>Builder rebuilds cleanly with 7 config flags; the three old names have zero git-tracked occurrences under scripts/, src/, n8n/, .env.example, CLAUDE.md; both built artifacts bake judge escalation `true` (x2), cap `"50"`, and the two split model consts still resolving to claude-sonnet-5; no escalation entry remains in _OVERLAY_FLAG_SPEC; judge.js has zero executable-line changes.</done>
</task>

<task type="auto">
  <name>Task 2: Test churn, frozen-fixture re-baseline (bounded to 8/14 pairs), new arm-by-default invariant test, both suites green</name>
  <files>tests/test_builder_flag_parity.py, tests/test_deploy_flag_overlay.py, tests/test_deploy_write_safety_overlay.py, tests/test_enabled_build_invariants.py, tests/test_main.py, tests/test_service.py, tests/test_e2e_ingest.py, tests/test_contact_ingest.py, tests/n8n/enabledResearchLaneFlow.test.mjs, tests/n8n/researchRequestSponsorshipContract.test.mjs, tests/n8n/contactResearchChainRowFlow.test.mjs, tests/fixtures/companies_jscode_frozen.json</files>
  <read_first>RESEARCH.md §2 (per-function disposition table for test_deploy_flag_overlay.py), §3 (enabledResearchLaneFlow OVERLAY_FLAGS), §4 (test_enabled_build_invariants per-function changes), §1 (frozen regen procedure) — all already in this plan's context; plus tests/test_companies_factory_frozen.py's header comment block</read_first>
  <behavior>
    - Rename, never weaken: no test loses an assertion without an equal-or-stronger replacement.
    - NEW: the committed build declares judge escalation `true` at every declaration site (the arm-by-default guarantee this whole task exists to deliver — it has zero coverage otherwise).
    - The numeric-literal drift-detection branch of enable_baked_flags keeps a live test case.
    - `ALLOW_JUDGE_ESCALATION` is pinned as permanently NON-overlayable.
    - Frozen fixture: exactly 8 of 14 {variant,node} pairs differ; the 6 untouched pairs stay byte-identical.
  </behavior>
  <action>
Apply RESEARCH.md's per-file dispositions. Note that `enable_baked_flags()` and
`_requested_overlay_flags()` RAISE `ValueError` on an unknown flag name BEFORE any counting,
so every stale call site errors rather than failing an assert — rename-in-place is wrong for
those; the flag argument must be dropped.

**tests/test_builder_flag_parity.py** — `EXPECTED_FLAGS` (L30-37) becomes the 7-name set. The
four tests that iterate it are name-driven loops and need no logic change; rename the "six" in
their names/docstrings to "seven".

**tests/test_deploy_flag_overlay.py** (largest diff, 10/13 functions) — per RESEARCH §2's table:
rename the `hermetic` fixture's delenv entry; delete the escalation half of the real-artifact
exactness test; flip `independence_research_only` to assert the new flag reads `true`
unconditionally; DELETE `independence_escalation_only` entirely (that behavior no longer
exists); in the zero-declarations test and both real-path tests (`ENABLE_BAKED_FLAGS=...`) drop
the escalation argument and its literal assertions, keeping `ALLOW_WEB_RESEARCH` only; in the
`bad_flag` parametrize rename the cap, split the model into two entries, and ADD
`ALLOW_JUDGE_ESCALATION` (its permanent non-overlayable pin). In the ambient-env independence
test, set the ambient value to `"false"` (the NON-default) and assert the baked output still
reads `true` — setting it to `true` would coincide with the default and prove nothing.
COVERAGE TRAP (RESEARCH §2): `test_enable_baked_flags_raises_on_numeric_literal_variant` uses
the escalation flag as its subject; once that name leaves the spec the call raises the
"not overlayable" error and never reaches the numeric-literal re-scan branch. Switch the
subject to a still-overlayable flag (`ALLOW_WEB_RESEARCH`) so that branch keeps its only test.

**tests/test_deploy_write_safety_overlay.py** — TWO sites: the `cap` parametrize (~L140:
rename the cap, split the model into two entries) AND
`test_unrequested_write_flags_are_untouched_by_a_research_only_request` (~L159-161), whose
`ENABLE_BAKED_FLAGS` value and expected dict must drop the escalation flag (it would otherwise
raise inside `_requested_overlay_flags()`).

**tests/test_enabled_build_invariants.py** — per RESEARCH §4: shrink module-level `FLAGS`
(L23) to the research flag alone; add the NEW inverted test asserting every judge-escalation
literal found across the cloud workflow files is `"true"` (this is the arm-by-default pin);
rewrite the "both flags" non-vacuity test for the single remaining flag or fold it into the new
test; rename the four-flag-lines diff test to two; rename the cap entry in the cost-caps tuple
(L161); in the overlayable-subset test drop the escalation name from the expected
`_OVERLAYABLE_FLAGS` set (5 entries remain) and move it into the "structurally out of reach"
set alongside the renamed cap and BOTH renamed model names.

**tests/n8n/enabledResearchLaneFlow.test.mjs** — shrink `OVERLAY_FLAGS` (L36) to
`["ALLOW_WEB_RESEARCH"]`; do not rename the escalation entry in place (it needs no enabling
now). Update the header comment (L4) to say judge escalation is armed by default and only
research still needs the deploy-time overlay. No downstream assertion changes: the renamed
consts are locals inside the `new Function` body and invisible to the harness.

**Comment-only prose edits** — `tests/n8n/researchRequestSponsorshipContract.test.mjs:21`,
`tests/n8n/contactResearchChainRowFlow.test.mjs:68` (plus that file's budget-fixture comment).
No assertion references these literals.

**Env-setter renames** — `tests/test_main.py`, `tests/test_service.py`,
`tests/test_e2e_ingest.py`, `tests/test_contact_ingest.py`: rename the `monkeypatch.setenv`
names only.

**Frozen fixture re-baseline** — the pre-rename baseline is already in git
(`git show HEAD:tests/fixtures/companies_jscode_frozen.json`); no pre-capture step needed.
Write a throwaway script in the SESSION SCRATCHPAD (not the repo — there is deliberately no
generator script, and adding one would end the "explicit reviewed act" property) that imports
`build_cloud_workflows`, calls `build_enrichment_cloud()` and `build_enrichment_local_live()`,
extracts jsCode for the 7 `FROZEN_NODE_NAMES` in both variants, and diffs against the OLD
fixture. PROVE the diff is exactly 8 of 14 pairs, and exactly these 4 node names in each
variant: Build Research Request, Judge Gate, Build Judge Request, Apply Judge Verdict. Confirm
`Apply Judge Verdict`'s diff is comment-text only. If ANY other pair differs, STOP and report
— do not write the fixture. Then overwrite ONLY those 8 entries; leave the other 6 untouched.
Never hand-patch bytes. Commit the fixture ALONE, isolated from every other change, with a
message stating the bound (e.g. "4/7 frozen nodes x 2 variants = 8/14 pairs: Build Research
Request, Judge Gate, Build Judge Request, Apply Judge Verdict — model/flag rename + inlined
judge.js comment text, zero logic change").

Do NOT rebuild the artifacts again in this task unless a source fix is required; if one is,
rebuild and re-prove the bound before touching the fixture.
  </action>
  <verify>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python -m pytest -q</automated>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && node --test tests/n8n/*.test.mjs</automated>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && ! git grep -q -E 'ALLOW_SONNET_ESCALATION|MAX_SONNET_VALIDATIONS_PER_RUN|ANTHROPIC_SONNET_MODEL' -- scripts src tests n8n .env.example CLAUDE.md && echo SC1_CLEAN</automated>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python -m pytest -q tests/test_enabled_build_invariants.py -k "judge" -v 2>&1 | grep -E "passed|PASSED" && echo ARM_PIN_PRESENT</automated>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && test "$(git show HEAD:tests/fixtures/companies_jscode_frozen.json | .venv/bin/python -c "import json,sys; old=json.load(sys.stdin); new=json.load(open('tests/fixtures/companies_jscode_frozen.json')); print(sum(1 for v in old for n in old[v] if old[v][n]!=new[v][n]))")" = 8 && echo BOUND_8_OF_14</automated>
  </verify>
  <done>Both suites green (pytest + `node --test tests/n8n/*.test.mjs`); zero old-name occurrences across the full git-tracked scope including tests/; a new test pins judge escalation as always `true` in the committed build; ALLOW_JUDGE_ESCALATION is pinned non-overlayable; the numeric-literal drift branch still has a passing test case with an overlayable subject; the frozen fixture differs from HEAD in exactly 8 of 14 pairs, all four named nodes, committed in isolation.</done>
</task>

<task type="auto">
  <name>Task 3: Disarmed redeploy, live read-back verification, STATE note</name>
  <files>.planning/STATE.md</files>
  <read_first>.planning/milestones/v0.4-phases/19-verification-debt-closure/19-OPERATOR-RUNBOOK.md (the dotenv-wrapper deploy command form and the read-back pattern)</read_first>
  <action>
Deploy DISARMED. Do not set `ENABLE_BAKED_FLAGS` — every write-safety flag stays baked
`"false"`, and judge escalation needs no overlay now (it is `true` in the committed artifact).
`.env` is permission-blocked to the agent, so use the Phase-19 in-process dotenv wrapper form
rather than shell-sourcing:

`.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"`

with `DRY_RUN=false ALLOW_N8N_DEPLOY=true` in the environment of that one command. Expect the
same three-workflow 200 pattern the runbook records.

Then read the deployed `LV Enrichment` workflow JSON back via the n8n API (disarmed reads are
permitted) using the same in-process dotenv wrapper, and assert against the LIVE copy — a
content probe, not a name-only diff, because a name-only comparison is exactly what let
bug-26 hide a stale deployment:
- judge escalation declared `true` (2 sites), cap `"50"`;
- `ANTHROPIC_RESEARCH_MODEL` present in both research request nodes,
  `ANTHROPIC_JUDGE_MODEL` present in both judge request nodes, both resolving `claude-sonnet-5`;
- zero occurrences of any of the three old names anywhere in the live JSON;
- every write-safety flag still `"false"` and the test-record allowlist still empty
  (unchanged by this deploy — assert, do not modify).

Zero HubSpot calls in this task. `n8n/wf_scheduled_maintenance_cloud.json` has zero
occurrences of any old name (verified) and needs no separate content probe.

Finally add one line to `.planning/STATE.md` under Session Continuity recording: the rename
landed, judge armed by default (cap 50), models split and both still claude-sonnet-5, live
deployment redeployed disarmed and read-back verified. Touch ONLY the Session Continuity
section — the historical narrative lines elsewhere in STATE.md that mention the old names
describe what was true in past phases and stay as-is.
  </action>
  <verify>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"</automated>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
import json,sys,urllib.request; sys.path.insert(0,'scripts')
import deploy_n8n_workflows as dep
base=dep._base_url(); hdrs=dep._n8n_headers()
assert base, 'N8N_URL not set after load_dotenv'
def get(p):
    r=urllib.request.Request(base+p, headers=hdrs)
    return json.load(urllib.request.urlopen(r,timeout=30))
wfs=get('/api/v1/workflows')['data']
wf=[w for w in wfs if 'Enrichment' in w['name']][0]
doc=get('/api/v1/workflows/'+wf['id']); raw=json.dumps(doc)
for old in ('ALLOW_SONNET_ESCALATION','MAX_SONNET_VALIDATIONS_PER_RUN','ANTHROPIC_SONNET_MODEL'):
    assert old not in raw, ('LIVE still carries '+old)
assert raw.count('const ALLOW_JUDGE_ESCALATION = true;')==2, raw.count('const ALLOW_JUDGE_ESCALATION = true;')
assert 'const MAX_JUDGE_VALIDATIONS_PER_RUN = \"50\";' in raw
assert 'ANTHROPIC_RESEARCH_MODEL' in raw and 'ANTHROPIC_JUDGE_MODEL' in raw
assert 'claude-sonnet-5' in raw
import re
ws=set(re.findall(r'const (ALLOW_HUBSPOT_[A-Z_]+) = (\"[a-z]+\")', raw))
assert ws and all(v=='\"false\"' for _,v in ws), ws
print('LIVE_OK', wf['name'], wf['id'], sorted(ws))
"</automated>
  </verify>
  <done>All three workflows redeployed disarmed; the live `LV Enrichment` JSON read back via the n8n API carries judge escalation `true` x2, cap `"50"`, both split model consts resolving claude-sonnet-5, and zero occurrences of any old name; every live write-safety flag still reads `"false"`; no HubSpot request was made; STATE.md Session Continuity records the change in one line.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| repo source -> deployed n8n Cloud workflow | a rename that lands in git but not in the live deployment reproduces bug-26 (live behind git, invisible to a name-only diff) |
| build-time baked flag -> live LLM spend | flipping judge escalation to default-true arms real Sonnet judge calls on the next armed enrichment run |
| deploy script -> HubSpot write gates | any deploy that widens a write-safety flag would arm production writes |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-din-01 | Tampering | frozen jsCode fixture | high | mitigate | Task 2 proves the diff is bounded to 8/14 pairs and 4 named nodes BEFORE writing; anything else moving is STOP-and-report; fixture committed in isolation so the re-baseline is reviewable on its own |
| T-din-02 | Elevation of Privilege | deploy overlay / write-safety flags | high | mitigate | Task 3 deploys with no `ENABLE_BAKED_FLAGS`; Task 3's read-back asserts every live `ALLOW_HUBSPOT_*` still `"false"`; Task 2 pins the renamed flag as permanently non-overlayable |
| T-din-03 | Repudiation | live-vs-git drift | high | mitigate | Task 3 verifies by CONTENT probe against the live JSON (the bug-26 lesson), not a name-only workflow diff |
| T-din-04 | Denial of Service | judge cost ceiling | medium | accept | Cap 50 x ~$0.03 ~= $1.50/run is the accepted ceiling per the spec; `ALLOW_WEB_RESEARCH` stays false so judge fires only on provider-conflict paths until research is separately enabled |
| T-din-05 | Information Disclosure | live `.env` secrets | low | mitigate | `.env` is never read or written by the agent; the operator `!` sed command is surfaced in the summary; the read-back verify prints flag names/values only, never secrets |
| T-din-06 | Tampering | npm/pip/cargo installs | n/a | accept | No dependency is added or changed by this task; no package-manager install runs |
</threat_model>

<verification>
1. `! git grep -q -E 'ALLOW_SONNET_ESCALATION|MAX_SONNET_VALIDATIONS_PER_RUN|ANTHROPIC_SONNET_MODEL' -- scripts src tests n8n .env.example CLAUDE.md` (SC-1; `.planning/milestones` and `docs/reports` deliberately out of pathspec as historical record).
2. `.venv/bin/python -m pytest` green AND `node --test tests/n8n/*.test.mjs` green (SC-2).
3. Live read-back content probe: judge armed `true` x2, cap `"50"`, both split model consts, both models claude-sonnet-5, zero old names (SC-3).
4. Live read-back: every `ALLOW_HUBSPOT_*` flag still `"false"`, allowlist unchanged; zero HubSpot requests issued in any task (SC-4).
5. Frozen fixture diff vs `HEAD` is exactly 8 of 14 pairs across exactly the 4 named nodes.
</verification>

<success_criteria>
- SC-1 satisfied: zero old-name occurrences in the git-tracked source/test/artifact scope.
- SC-2 satisfied: both suites green with no assertion weakened and one net-new invariant added.
- SC-3 satisfied: the live disarmed deployment carries the armed judge, cap 50, and the two
  split model consts, both still claude-sonnet-5 (behavior-preserving split).
- SC-4 satisfied: no write-safety flag changed anywhere; no HubSpot write occurred.
- The Haiku experiment is now a one-line default change: set `ANTHROPIC_RESEARCH_MODEL` to
  `claude-haiku-4-5` + rebuild + disarmed redeploy. Nothing else moves.
</success_criteria>

<output>
Write `.planning/quick/20260730-judge-research-model-switches/SUMMARY.md` on completion.
The summary MUST surface, verbatim and unrun, the operator `!` command from the spec's Task 4
that updates the live `.env` (the agent cannot touch that dotfile), plus its name-only
verification grep.
</output>
