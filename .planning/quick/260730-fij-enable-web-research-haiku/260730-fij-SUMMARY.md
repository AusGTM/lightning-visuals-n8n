---
type: quick
slug: 260730-fij
subsystem: enrichment-pipeline
tags: [n8n, research, anthropic-model, haiku, config-flags, deploy]

key-files:
  created: []
  modified:
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - CLAUDE.md
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - tests/test_deploy_flag_overlay.py
    - tests/test_deploy_write_safety_overlay.py
    - tests/test_enabled_build_invariants.py
    - tests/n8n/enabledResearchLaneFlow.test.mjs
    - tests/fixtures/companies_jscode_frozen.json
    - .planning/STATE.md

key-decisions:
  - "ALLOW_WEB_RESEARCH default flips false->true and is DELETED from _OVERLAY_FLAG_SPEC entirely (not renamed) — mirrors 260730-din's ALLOW_JUDGE_ESCALATION deletion. A default-true flag has no meaningful overlay entry; emergency-off path is edit CONFIG_FLAG_DEFAULTS + rebuild + disarmed redeploy."
  - "The write-safety family (ALLOW_HUBSPOT_RECORD_WRITES/ALLOW_HUBSPOT_CREATE/TEST_RECORD_IDS/TEST_RECORD_DOMAINS) is now the ONLY overlayable flag set left — both research kill switches (ALLOW_WEB_RESEARCH, ALLOW_JUDGE_ESCALATION) bake `true` unconditionally at build time. Every mechanism/artifact-invariant test that previously used ALLOW_WEB_RESEARCH as its demonstration subject retargets to ALLOW_HUBSPOT_RECORD_WRITES (still overlayable) rather than being deleted, since it is the sole surviving flag class that can demonstrate purity/exactness/independence/fail-closed-drift/diff-only-flag-lines."
  - "ANTHROPIC_RESEARCH_MODEL flips claude-sonnet-5 -> claude-haiku-4-5 in CONFIG_FLAG_DEFAULTS only. ANTHROPIC_JUDGE_MODEL, ALLOW_JUDGE_ESCALATION, MAX_JUDGE_VALIDATIONS_PER_RUN, and MAX_WEB_RESEARCH_PER_RUN are all untouched — this is a research-lane-only cost/model change, judge behavior is unaffected."
  - "enabledResearchLaneFlow.test.mjs's 'enabled' fixture collapses into the plain committed build (no in-test rewrite needed anymore, since ALLOW_WEB_RESEARCH already bakes true) — the disabled CONTROL now needs an explicit in-test true->false rewrite instead, since there is no longer a disabled-by-default committed build to read directly for that role."
  - "Frozen fixture re-baseline bounded and proven via a scratchpad diff script BEFORE writing: exactly 4 of 14 {variant,node} pairs differ (Research Trigger Gate + Build Research Request, x2 variants: cloud/local-live) — each a single-line ALLOW_WEB_RESEARCH or ANTHROPIC_RESEARCH_MODEL default change, no unrelated drift. Committed in its own isolated commit."

duration: ~35min
completed: 2026-07-30
status: complete
---

# Quick 260730-fij: Enable web research + Haiku research model — Summary

**Flipped `ALLOW_WEB_RESEARCH` default to armed and `ANTHROPIC_RESEARCH_MODEL` to `claude-haiku-4-5`, deleted the now-redundant overlay entry, retargeted every affected test to the write-safety family (the sole remaining overlayable flag set), re-baselined the frozen fixture, and redeployed disarmed with a live content-probe read-back.**

## Performance

- **Tasks:** 3/3 complete
- **Files modified:** 10 (source, tests, artifacts, docs) + STATE.md note (left uncommitted per orchestrator convention)
- **Suites:** 603 pytest / 309 node — both fully green, zero regressions vs the 601/309 baseline

## Accomplishments

- **Research armed by default, cheap model:** `CONFIG_FLAG_DEFAULTS["ALLOW_WEB_RESEARCH"]` `"false"` -> `"true"`; `CONFIG_FLAG_DEFAULTS["ANTHROPIC_RESEARCH_MODEL"]` `"claude-sonnet-5"` -> `"claude-haiku-4-5"`. The other 5 CONFIG_FLAG_DEFAULTS entries (`MAX_WEB_RESEARCH_PER_RUN`, `ANTHROPIC_JUDGE_MODEL`, `WEB_RESEARCH_MAX_SEARCHES`, `ALLOW_JUDGE_ESCALATION`, `MAX_JUDGE_VALIDATIONS_PER_RUN`) are byte-unchanged.
- **`ALLOW_WEB_RESEARCH` left `_OVERLAY_FLAG_SPEC` entirely** (not renamed) — a default-true flag has no meaningful "enable" overlay entry, mirroring 260730-din's `ALLOW_JUDGE_ESCALATION` deletion exactly. Module/function docstrings in `scripts/deploy_n8n_workflows.py` updated to state there is now ZERO remaining non-write-safety overlay target.
- **CLAUDE.md flag-default mentions updated**, historical narrative left intact: the `.env.example` walkthrough (§11.2) and the global kill-switches block (§21.1) now show `ALLOW_WEB_RESEARCH=true` / `ANTHROPIC_RESEARCH_MODEL=claude-haiku-4-5`; the Phase-4 rollout-plan narrative (§25.5) already showed `ALLOW_WEB_RESEARCH=true` as a *future* state and needed no change.
- **Both cloud artifacts rebuilt:** `n8n/wf_enrichment_cloud.json` / `n8n/wf_enrichment_local_live.json` now bake `const ALLOW_WEB_RESEARCH = true;` (x2 each) and `const ANTHROPIC_RESEARCH_MODEL = "claude-haiku-4-5";` (x2 each); `ANTHROPIC_JUDGE_MODEL` still resolves `"claude-sonnet-5"` (x2), `MAX_WEB_RESEARCH_PER_RUN` still `10` (x2).
- **Full test retarget, not deletion:** since ALLOW_WEB_RESEARCH was the LAST non-write-safety overlayable flag, `tests/test_deploy_flag_overlay.py`'s entire mechanism suite (purity, exactness, independence, fail-closed drift x2, non-overlayable rejection, zero-declarations, deploy-set refusal, ambient-env inertness, default-through-real-path, enabled-through-real-path, dry-run visibility) retargets its exercised subject to `ALLOW_HUBSPOT_RECORD_WRITES` — the only flag left that is both committed-disabled and overlayable. `tests/test_deploy_write_safety_overlay.py`'s two ALLOW_WEB_RESEARCH-subject tests likewise retarget (boolean-kill-switch-rejects-a-value -> `ALLOW_HUBSPOT_RECORD_WRITES=true`; unrequested-flags-untouched -> a bare `TEST_RECORD_IDS=201` request).
- **`test_enabled_build_invariants.py` restructured:** `FLAGS` tuple retargeted from `("ALLOW_WEB_RESEARCH",)` to `("ALLOW_HUBSPOT_RECORD_WRITES",)` for the Criterion-5-survives-enablement and diff-only-flag-lines sections (the only remaining overlayable demonstration subject); the "committed stays disabled" section for research retired (would duplicate `test_deploy_write_safety_overlay.py`'s existing write-safety guard); new arm-by-default invariant `test_committed_build_web_research_is_always_true` + non-vacuity companion added beside the existing judge-escalation pair; `MAX_WEB_RESEARCH_PER_RUN` explicitly re-pinned at `"10"` in the cost-cap test.
- **`enabledResearchLaneFlow.test.mjs` simplified:** the "enabled" fixture now loads the committed `wf_enrichment_cloud.json` directly (both kill switches already bake `true`) instead of performing an in-test rewrite; a new `loadDisabledControlWorkflow()` performs the inverse (true->false) rewrite so the disabled-CONTROL test can still prove the flag — not something incidental — causes the research gate to fire.
- **Frozen fixture re-baselined under a proven bound:** a session-scratchpad script built fresh output from `build_enrichment_cloud()`/`build_enrichment_local_live()`, diffed it against the pre-change fixture, and PROVED the diff was exactly 4/14 `{variant,node}` pairs (`Research Trigger Gate` + `Build Research Request`, x2 variants) — each a single-line `ALLOW_WEB_RESEARCH`/`ANTHROPIC_RESEARCH_MODEL` change — before writing anything. Committed in its own isolated commit.
- **Live redeploy, disarmed, content-probe verified:** all three workflows redeployed via the exact in-process dotenv wrapper with `DRY_RUN=false ALLOW_N8N_DEPLOY=true` and NO `ENABLE_BAKED_FLAGS` (200 x3). Read-back against the live `LV Enrichment` workflow confirms `ALLOW_WEB_RESEARCH=true` (x2), `ANTHROPIC_RESEARCH_MODEL="claude-haiku-4-5"` (x2), `ANTHROPIC_JUDGE_MODEL="claude-sonnet-5"` (x2), `ALLOW_JUDGE_ESCALATION=true` (x2), `MAX_WEB_RESEARCH_PER_RUN=10` (x2), `MAX_JUDGE_VALIDATIONS_PER_RUN=50` (x2), and every `ALLOW_HUBSPOT_*` write-safety flag still `"false"` (x2) with the test-record allowlist still empty (x2). Zero HubSpot API calls were made at any point in this task.

## Task Commits

1. **Task 1: builder + overlay + docs flip + rebuilt artifacts** — `982503f` (feat)
2. **Task 2a: test churn (retarget mechanism tests to write-safety family, new invariant)** — `43c27c5` (test)
3. **Task 2b: frozen fixture re-baseline (isolated)** — `4d87fb3` (test)
4. **Task 3: disarmed redeploy + live read-back** — no code commit (live deploy action + a `.planning/STATE.md` Session Continuity note, left uncommitted for the orchestrator's docs commit per the harness's `commit_docs` convention)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `CONFIG_FLAG_DEFAULTS["ALLOW_WEB_RESEARCH"]` -> `"true"`, `CONFIG_FLAG_DEFAULTS["ANTHROPIC_RESEARCH_MODEL"]` -> `"claude-haiku-4-5"`.
- `scripts/deploy_n8n_workflows.py` — `_OVERLAY_FLAG_SPEC`'s `ALLOW_WEB_RESEARCH` entry deleted; comment block above `_OVERLAY_FLAG_SPEC` and `_requested_overlay_flags()`'s docstring updated to state there is no remaining non-write-safety overlay target.
- `CLAUDE.md` — 2 lines changed (§11.2 `.env.example` walkthrough, §21.1 global kill switches); historical §25.5 rollout narrative untouched (already showed the future-armed state).
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` — rebuilt from the new source defaults.
- `tests/test_deploy_flag_overlay.py` — every ALLOW_WEB_RESEARCH-subject test retargeted to `ALLOW_HUBSPOT_RECORD_WRITES`; non-overlayable-names parametrize lists gained `ALLOW_WEB_RESEARCH`; ambient-env-inertness and default-through-real-path tests updated to reflect BOTH kill switches now baking `true`.
- `tests/test_deploy_write_safety_overlay.py` — 2 tests retargeted off `ALLOW_WEB_RESEARCH`.
- `tests/test_enabled_build_invariants.py` — `FLAGS` retargeted; new `test_committed_build_web_research_is_always_true` + non-vacuity companion; "committed stays disabled" section for research retired; cost-cap test explicitly re-pins `MAX_WEB_RESEARCH_PER_RUN == "10"`; parity test's non-overlayable exclusion set gained `ALLOW_WEB_RESEARCH`.
- `tests/n8n/enabledResearchLaneFlow.test.mjs` — enabled-fixture loader simplified (no rewrite needed); new `loadDisabledControlWorkflow()` for the disabled-control test.
- `tests/fixtures/companies_jscode_frozen.json` — 4/14 pairs re-baselined, isolated commit.
- `.planning/STATE.md` — one Session Continuity line added (uncommitted, per convention).

## Deviations from Plan

### Auto-fixed / corrected issues (non-blocking, documented per Rule 1/2)

**1. [Test-design] Mechanism tests retargeted rather than deleted**
- **Found during:** Task 2 planning.
- **Issue:** The plan's Task 2 instruction ("The numeric-literal-drift test subject: if it now uses ALLOW_WEB_RESEARCH, move to a still-overlayable flag") explicitly named only ONE test for this treatment. In practice essentially every mechanism test in `tests/test_deploy_flag_overlay.py` (purity, exactness, independence, both fail-closed-drift tests, zero-declarations, deploy-set refusal, ambient-env inertness, default-through-real-path, enabled-through-real-path, dry-run visibility) used `ALLOW_WEB_RESEARCH` as its exercised subject, because — unlike 260730-din's precedent, which left one non-write-safety flag (`ALLOW_WEB_RESEARCH`) still overlayable — this task removes the LAST one, leaving the write-safety family as the only flag class that can demonstrate these properties at all.
- **Fix:** Retargeted every such test's subject to `ALLOW_HUBSPOT_RECORD_WRITES` (and, where a value-taking flag was needed, `TEST_RECORD_IDS`), preserving each test's original intent and assertions rather than deleting coverage. `test_deploy_write_safety_overlay.py` and `test_enabled_build_invariants.py` received the same treatment for their own ALLOW_WEB_RESEARCH-subject cases.
- **Files affected:** `tests/test_deploy_flag_overlay.py`, `tests/test_deploy_write_safety_overlay.py`, `tests/test_enabled_build_invariants.py`.
- **Verification:** All three suites green (25/20/14 tests respectively), no coverage lost.

**2. [Test-design] `test_enabled_build_invariants.py` section (1) retired instead of retargeted**
- **Found during:** Task 2, restructuring `test_enabled_build_invariants.py`.
- **Issue:** The old "committed build stays disabled" parametrized guard (Criterion 1) existed specifically for the class of flags that are BOTH committed-disabled AND overlayable. Retargeting it to the write-safety family would exactly duplicate `tests/test_deploy_write_safety_overlay.py::test_committed_build_carries_the_disabled_write_safety_literals`, which already covers all four write-safety flags.
- **Fix:** Retired the two tests in that section (`test_committed_build_flag_declarations_are_always_disabled`, `test_enrichment_workflow_declares_research_flag_at_least_once`) rather than duplicating existing coverage; added a comment pointing at the existing guard. Sections (2)/(3) (Criterion 5 survival, diff-only-flag-lines), which prove a DIFFERENT, non-duplicated property, were retargeted to `ALLOW_HUBSPOT_RECORD_WRITES` as planned.
- **Files affected:** `tests/test_enabled_build_invariants.py`.
- **Verification:** 14/14 tests green; no invariant lost (write-safety-stays-disabled is still covered, just in its original home).

None of the above required touching `scripts/`, `src/`, `n8n/code/`, or any production `n8n/*.json` beyond what Task 1 already specified.

## Live Verification Detail (Task 3)

```
Workflows to create: []
Workflows to update: ['LV Contact Ingest (Cloud template)', 'LV Enrichment (Cloud template)', 'LV Scheduled Maintenance (Cloud)']
updated workflow LV Contact Ingest (Cloud template) (200)
updated workflow LV Enrichment (Cloud template) (200)
updated workflow LV Scheduled Maintenance (Cloud) (200)
```

Read-back against `LV Enrichment (Cloud template)` (`950HPb7a1GgSAIyZ`), probing `doc['nodes']` directly (not the full envelope — the `activeVersion` duplicate-node-copy gotcha 260730-din documented):

- `const ALLOW_WEB_RESEARCH = true;` x2 (companies Research Trigger Gate + Contact Research Trigger Gate)
- `ANTHROPIC_RESEARCH_MODEL = "claude-haiku-4-5"` x2
- `ANTHROPIC_JUDGE_MODEL = "claude-sonnet-5"` x2 (unchanged)
- `const ALLOW_JUDGE_ESCALATION = true;` x2 (unchanged)
- `MAX_WEB_RESEARCH_PER_RUN = 10;` x2 (unchanged — pacing untouched)
- `MAX_JUDGE_VALIDATIONS_PER_RUN = 50;` x2 (unchanged)
- `ALLOW_HUBSPOT_RECORD_WRITES = "false"` x2, `ALLOW_HUBSPOT_CREATE = "false"` x2 — unchanged
- `TEST_RECORD_IDS = ""` x2, `TEST_RECORD_DOMAINS = ""` x2 — allowlist unchanged, still empty
- Zero occurrences of `ALLOW_WEB_RESEARCH = false` (old default) anywhere live.
- Zero HubSpot API calls made at any point in this task.

## Operator Action Required — Live `.env` (agent cannot touch this dotfile)

The agent never reads or writes `.env` (permission-blocked). Run this in the session with `!` once the code has landed:

```
! sed -i '' -e 's/^ALLOW_WEB_RESEARCH=.*/ALLOW_WEB_RESEARCH=true/' -e 's/^ANTHROPIC_RESEARCH_MODEL=.*/ANTHROPIC_RESEARCH_MODEL=claude-haiku-4-5/' .env .env.example && grep -hE '^(ALLOW_WEB_RESEARCH|ANTHROPIC_RESEARCH_MODEL)=' .env .env.example
```

## Cost Note

Research lane now LIVE on scheduled runs: Haiku research ≈ $0.07/company-call incl. search fees, paced by `MAX_WEB_RESEARCH_PER_RUN=10` per run (≈960/day ceiling at 15-min cadence). Judge escalations (Sonnet) expected on ~15-100% of researched companies per eval; capped 50/run.

## Test Suite Note

One `node --test` run flagged a transient failure in an unrelated millisecond-precision timestamp assertion (a pre-existing race in a cache-key `verified_at` comparison, not touched by this task); a clean re-run immediately after showed 309/309 passing with zero failures. Not investigated further — out of this task's scope (no file this task modified is involved), and not reproducible on a second run.

## Self-Check: PASSED

- `scripts/build_cloud_workflows.py`, `scripts/deploy_n8n_workflows.py`, `CLAUDE.md` — all FOUND, all edits confirmed present via grep.
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` — FOUND, rebuilt, baked literals confirmed (2x `ALLOW_WEB_RESEARCH = true`, 2x `ANTHROPIC_RESEARCH_MODEL = "claude-haiku-4-5"`).
- `tests/fixtures/companies_jscode_frozen.json` — FOUND, bound-of-4 confirmed against pre-Task-2b state.
- Commits `982503f`, `43c27c5`, `4d87fb3` — all FOUND in `git log --oneline`.
- `603 passed` (pytest), `309 pass / 0 fail` (node --test, re-run) — both suites reconfirmed green after all edits.
- Live read-back: judge escalation x2 `true`, research x2 `true`, both models present and correct, caps unchanged, write-safety flags `"false"`x2 — confirmed above.
