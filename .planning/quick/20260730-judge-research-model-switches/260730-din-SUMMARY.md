---
type: quick
slug: 260730-din
subsystem: enrichment-pipeline
tags: [n8n, judge, research, anthropic-model, config-flags, deploy]

key-files:
  created: []
  modified:
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

key-decisions:
  - "ALLOW_JUDGE_ESCALATION default flips false->true and is DELETED from _OVERLAY_FLAG_SPEC entirely (not renamed) — a default-true flag has no meaningful overlay entry; emergency-off path is edit CONFIG_FLAG_DEFAULTS + rebuild + disarmed redeploy."
  - "Both new model switches (ANTHROPIC_RESEARCH_MODEL, ANTHROPIC_JUDGE_MODEL) default claude-sonnet-5 — behavior-preserving split, no Haiku default introduced."
  - "n8n/code/judge.js's two comment mentions of the old escalation flag name were renamed (zero executable-line changes) because inline() concatenates the file verbatim into 6 compiled node bodies, making the comments occurrences inside n8n/*.json under SC-1's zero-occurrence scope."
  - "Frozen fixture re-baseline bounded and proved via a scratchpad diff script BEFORE writing: exactly 8 of 14 {variant,node} pairs differ (Build Research Request, Judge Gate, Build Judge Request, Apply Judge Verdict x2 variants); Apply Judge Verdict's diff confirmed comment-text only. Fixture committed in isolation."
  - "MAX_JUDGE_VALIDATIONS_PER_RUN bakes as a bare numeric literal (const MAX_JUDGE_VALIDATIONS_PER_RUN = 50;), not a quoted string — matches the pre-existing MAX_WEB_RESEARCH_PER_RUN convention (_flag_const bakes digit-string defaults unquoted). The PLAN.md verify snippet's quoted-string literal was a typo; corrected in this task's actual verification."

duration: ~50min
completed: 2026-07-30
status: complete
---

# Quick 260730-din: Split research/judge model switches, arm judge by default — Summary

**Renamed `ANTHROPIC_SONNET_MODEL` into two independent model levers, flipped judge escalation to armed-by-default (cap raised 10->50), rebuilt both n8n artifacts, re-baselined the frozen fixture under a proven bound, and redeployed disarmed with a live content-probe read-back.**

## Performance

- **Tasks:** 3/3 complete
- **Files modified:** 21 (source, tests, artifacts, docs) + STATE.md note (left uncommitted per orchestrator convention)
- **Suites:** 601 pytest / 309 node — both fully green, zero regressions

## Accomplishments

- **Model split:** `ANTHROPIC_SONNET_MODEL` -> `ANTHROPIC_RESEARCH_MODEL` (Build Research Request nodes) + `ANTHROPIC_JUDGE_MODEL` (Build Judge Request nodes), both defaulting `claude-sonnet-5` — zero behavior change, independent levers going forward.
- **Judge armed by default:** `ALLOW_SONNET_ESCALATION` -> `ALLOW_JUDGE_ESCALATION`, default flipped `false` -> `true`; `MAX_SONNET_VALIDATIONS_PER_RUN` -> `MAX_JUDGE_VALIDATIONS_PER_RUN`, default raised `10` -> `50`. The escalation flag is DELETED from `scripts/deploy_n8n_workflows.py`'s `_OVERLAY_FLAG_SPEC` (not renamed) since a default-true flag has no meaningful overlay entry, and pinned as permanently non-overlayable in both `_OVERLAY_FLAG_SPEC`-adjacent tests.
- **`n8n/code/judge.js`:** renamed the two comment-only mentions of the escalation flag (inlined verbatim into 6 compiled node bodies by `inline()`); zero executable-line changes, confirmed via `git diff` showing only 2 comment lines touched.
- **Both n8n artifacts rebuilt:** `n8n/wf_enrichment_cloud.json` / `n8n/wf_enrichment_local_live.json` now bake `const ALLOW_JUDGE_ESCALATION = true;` (x2 each), `const MAX_JUDGE_VALIDATIONS_PER_RUN = 50;`, and both split model consts resolving `claude-sonnet-5`.
- **New arm-by-default invariant:** `tests/test_enabled_build_invariants.py::test_committed_build_judge_escalation_is_always_true` — the guarantee this whole task exists to deliver, previously uncovered.
- **Frozen fixture re-baselined under a proven bound:** a session-scratchpad script (never committed — this repo deliberately has no generator script for `tests/fixtures/companies_jscode_frozen.json`) built fresh output, diffed it against the pre-rename fixture, and PROVED the diff was exactly 8/14 `{variant,node}` pairs across exactly the 4 predicted node names before writing anything. Committed in its own isolated commit.
- **Coverage-regression trap avoided:** `test_enable_baked_flags_raises_on_numeric_literal_variant` used the escalation flag as its subject before this rename; since that flag left `_OVERLAY_FLAG_SPEC` entirely, using it would raise the "not overlayable" error before ever reaching the numeric-literal drift-detection branch. Swapped the subject to `ALLOW_WEB_RESEARCH` (still overlayable) so that code path keeps a passing test.
- **Live redeploy, disarmed, content-probe verified:** all three workflows redeployed via the exact in-process dotenv wrapper (200 x3, zero shell-sourcing of `.env`). Read-back against the live `LV Enrichment` workflow confirms judge escalation `true` (x2), cap `50`, both split models resolving `claude-sonnet-5`, zero occurrences of any old flag/model name, and every `ALLOW_HUBSPOT_*` write-safety flag still `"false"` with the test-record allowlist still empty. Zero HubSpot API calls were made at any point in this task.

## Task Commits

1. **Task 1: rename at source + rebuild artifacts** — `aac1f9f` (feat)
2. **Task 2a: test churn (rename, flip literals, new invariant)** — `7bd952b` (test)
3. **Task 2b: frozen fixture re-baseline (isolated)** — `19da368` (test)
4. **Task 3: disarmed redeploy + live read-back** — no code commit (live deploy action + a `.planning/STATE.md` Session Continuity note, left uncommitted for the orchestrator's docs commit per the harness's `commit_docs` convention)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `CONFIG_FLAG_DEFAULTS` now 7 keys; 4 node-factory call sites renamed (Build Research Request, Judge Gate, Build Judge Request); comment sweep.
- `scripts/deploy_n8n_workflows.py` — `_OVERLAY_FLAG_SPEC` escalation entry deleted; module + function docstrings updated to reflect judge escalation is armed at build time.
- `src/validator_sonnet.py`, `src/web_research.py` — Python-lane env-var reads renamed (`validator_sonnet.py` also drops the stale `-latest` model suffix per CONTEXT decision).
- `n8n/code/judge.js` — 2 comment-only renames, zero logic change.
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` — rebuilt from renamed source.
- `.env.example`, `CLAUDE.md` — 3 old-line replacements / 11 mentions renamed respectively, new defaults stated.
- 12 test files — renamed, flipped literals to match new defaults, one net-new invariant test, zero weakened assertions.
- `tests/fixtures/companies_jscode_frozen.json` — 8/14 pairs re-baselined, isolated commit.
- `.planning/STATE.md` — one Session Continuity line added (uncommitted, per convention).

## Deviations from Plan

### Auto-fixed / corrected issues (non-blocking, documented per Rule 1/2)

**1. [Doc-inaccuracy] `MAX_JUDGE_VALIDATIONS_PER_RUN` bakes unquoted, not as a quoted string**
- **Found during:** Task 1 verification.
- **Issue:** PLAN.md's Task 1 verify snippet asserted `grep -q 'const MAX_JUDGE_VALIDATIONS_PER_RUN = "50";'` (quoted). The actual baked literal is `const MAX_JUDGE_VALIDATIONS_PER_RUN = 50;` (bare number) — `_flag_const()` bakes any digit-string default as a bare JS number, matching the pre-existing `MAX_WEB_RESEARCH_PER_RUN` convention. This is correct/expected behavior, not a bug; the plan's verify text had a typo.
- **Fix:** Verified against the actual (correct) unquoted form instead; documented here for traceability. No code change needed.
- **Files affected:** none (verification-only).

**2. Live n8n API response envelope embeds a duplicate node copy under `activeVersion`**
- **Found during:** Task 3 live read-back.
- **Issue:** PLAN.md's Task 3 verify snippet did `raw = json.dumps(doc)` over the FULL workflow-fetch response and expected `raw.count('const ALLOW_JUDGE_ESCALATION = true;') == 2`. The live n8n API additionally returns an `activeVersion` key containing a full duplicate `nodes`/`connections` copy (version-history metadata), which doubles every literal count when the whole envelope is serialized (4, not 2).
- **Fix:** Probed `doc['nodes']` (and each node's `parameters.jsCode`) directly instead of the whole envelope — the actual executable content n8n runs — confirming exactly 2 declarations there, and separately confirmed the `activeVersion` duplicate is consistent (4 = 2x2, no drift between the two copies). Not a deploy defect.
- **Files affected:** none (verification-only, no source change).

None of the above required touching `scripts/`, `src/`, `n8n/`, or `tests/` beyond what the plan already specified.

## Live Verification Detail (Task 3)

```
Workflows to create: []
Workflows to update: ['LV Contact Ingest (Cloud template)', 'LV Enrichment (Cloud template)', 'LV Scheduled Maintenance (Cloud)']
updated workflow LV Contact Ingest (Cloud template) (200)
updated workflow LV Enrichment (Cloud template) (200)
updated workflow LV Scheduled Maintenance (Cloud) (200)
```

Read-back against `LV Enrichment (Cloud template)` (`950HPb7a1GgSAIyZ`):
- `const ALLOW_JUDGE_ESCALATION = true;` x2 (companies Judge Gate + Contact Judge Gate)
- `const MAX_JUDGE_VALIDATIONS_PER_RUN = 50;` present
- `ANTHROPIC_RESEARCH_MODEL` and `ANTHROPIC_JUDGE_MODEL` both present, both resolving `claude-sonnet-5`
- Zero occurrences of `ALLOW_SONNET_ESCALATION` / `MAX_SONNET_VALIDATIONS_PER_RUN` / `ANTHROPIC_SONNET_MODEL`
- `ALLOW_HUBSPOT_RECORD_WRITES = "false"`, `ALLOW_HUBSPOT_CREATE = "false"` — unchanged
- `TEST_RECORD_IDS = ""`, `TEST_RECORD_DOMAINS = ""` — allowlist unchanged, still empty
- Zero HubSpot API calls made at any point in this task.

## Operator Action Required — Live `.env` (agent cannot touch this dotfile)

The agent never reads or writes `.env` (permission-blocked). `.env.example` is already
updated in this task's commits; the LIVE `.env` needs the same 3-line rename applied by
the operator. Run this in the session with `!` once the code has landed (verbatim from
the original spec's Task 4, **not run by the agent**):

```
! sed -i '' -e 's/^ANTHROPIC_SONNET_MODEL=.*/ANTHROPIC_RESEARCH_MODEL=claude-sonnet-5\nANTHROPIC_JUDGE_MODEL=claude-sonnet-5/' -e 's/^ALLOW_SONNET_ESCALATION=.*/ALLOW_JUDGE_ESCALATION=true/' -e 's/^MAX_SONNET_VALIDATIONS_PER_RUN=.*/MAX_JUDGE_VALIDATIONS_PER_RUN=50/' .env
```

Then verify (prints variable names only — never secret values):

```
! grep -E '^(ANTHROPIC_(RESEARCH|JUDGE)_MODEL|ALLOW_JUDGE_ESCALATION|MAX_JUDGE_VALIDATIONS_PER_RUN)=' .env
```

## Self-Check: PASSED

- `scripts/build_cloud_workflows.py`, `scripts/deploy_n8n_workflows.py`, `src/validator_sonnet.py`, `src/web_research.py`, `n8n/code/judge.js` — all FOUND, all edits confirmed present via grep.
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` — FOUND, rebuilt, baked literals confirmed.
- `tests/fixtures/companies_jscode_frozen.json` — FOUND, bound-of-8 confirmed against `HEAD~1` (pre-Task-2b).
- Commits `aac1f9f`, `7bd952b`, `19da368` — all FOUND in `git log --oneline`.
- `601 passed` (pytest), `309 pass / 0 fail` (node --test) — both suites reconfirmed green after all edits.
- Live read-back: `LIVE_OK` printed with judge escalation x2 `true`, cap `50`, both models present, zero old names, write-safety flags `"false"`x2 — confirmed above.
