---
task: Enable web research by default; research model → claude-haiku-4-5
quick_id: 260730-fij
date: 2026-07-30
status: planned
must_haves:
  truths:
    - "Default cloud build bakes `const ALLOW_WEB_RESEARCH = true;` and `ANTHROPIC_RESEARCH_MODEL = \"claude-haiku-4-5\"` (companies + contacts chains)"
    - "ANTHROPIC_JUDGE_MODEL stays claude-sonnet-5; ALLOW_JUDGE_ESCALATION stays true; MAX_JUDGE_VALIDATIONS_PER_RUN stays 50; MAX_WEB_RESEARCH_PER_RUN stays 10 (pacing untouched)"
    - "ALLOW_WEB_RESEARCH deleted from _OVERLAY_FLAG_SPEC (default-true flags are not overlayable) with no dangling references"
    - "Both suites green; frozen fixture regenerated (never hand-patched)"
    - "Live LV Enrichment redeployed DISARMED; read-back shows research true, haiku research model, sonnet judge model; all ALLOW_HUBSPOT_* still \"false\""
  artifacts:
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - n8n/wf_enrichment_cloud.json
    - tests/fixtures/companies_jscode_frozen.json
  key_links:
    - "Precedent: quick task 260730-din did the identical shape for ALLOW_JUDGE_ESCALATION (commits aac1f9f/7bd952b/19da368) — mirror its overlay-deletion, inverted-invariant-test, and fixture-regen patterns"
---

# Quick 260730-fij: Enable web research + Haiku research model

Evidence basis: 35-run Haiku A/B eval (2026-07-30) — judge triggers catch all observed
Haiku errors; judge armed+live since 260730-din. Operator ordered flip.

## Task 1 — Builder + overlay + docs flip

**files:** scripts/build_cloud_workflows.py, scripts/deploy_n8n_workflows.py, .env.example (BLOCKED — emit operator command instead), CLAUDE.md
**action:**
- CONFIG_FLAG_DEFAULTS: `ALLOW_WEB_RESEARCH: "true"`, `ANTHROPIC_RESEARCH_MODEL: "claude-haiku-4-5"`. Nothing else changes.
- deploy_n8n_workflows.py: delete `ALLOW_WEB_RESEARCH` from `_OVERLAY_FLAG_SPEC` (mirror 260730-din's escalation deletion); update docstrings mentioning it as overlayable.
- CLAUDE.md: update the flag-default mentions where they state ALLOW_WEB_RESEARCH=false as the shipped default (kill-switch §21.1 block and env examples) — reflect new defaults, keep historical/narrative text intact.
- .env.example is dotfile-blocked to agents: do NOT edit; surface operator `!` sed in SUMMARY (see Output).
- Rebuild artifacts: `.venv/bin/python scripts/build_cloud_workflows.py`.
**verify:** python import of CONFIG_FLAG_DEFAULTS shows the two new values + 5 unchanged; `git grep -n 'ALLOW_WEB_RESEARCH' scripts/deploy_n8n_workflows.py` → no _OVERLAY_FLAG_SPEC entry; generated wf_enrichment_cloud.json contains `const ALLOW_WEB_RESEARCH = true;` (expect 2: companies+contacts research gates... verify actual count) and `ANTHROPIC_RESEARCH_MODEL = "claude-haiku-4-5"` (2), `ANTHROPIC_JUDGE_MODEL = "claude-sonnet-5"` (2).
**done:** builder + overlay + CLAUDE.md committed atomically with rebuilt n8n/*.json.

## Task 2 — Test churn + fixture re-baseline + suites

**files:** tests/test_deploy_flag_overlay.py, tests/test_enabled_build_invariants.py, tests/test_deploy_write_safety_overlay.py (if it passes ALLOW_WEB_RESEARCH through overlay helpers), tests/n8n/enabledResearchLaneFlow.test.mjs, tests/fixtures/companies_jscode_frozen.json, any other test referencing ALLOW_WEB_RESEARCH as overlay/disabled-default (grep first)
**action:**
- Mirror 260730-din exactly: overlay tests lose their ALLOW_WEB_RESEARCH cases (entry deleted → enable_baked_flags raises for it). The numeric-literal-drift test subject: if it now uses ALLOW_WEB_RESEARCH, move to a still-overlayable flag (ALLOW_HUBSPOT_RECORD_WRITES family).
- test_enabled_build_invariants.py: FLAGS tuple shrinks; ADD inverted invariant `test_committed_build_web_research_is_always_true` beside the existing judge one; keep cap list (MAX_WEB_RESEARCH_PER_RUN still pinned at "10").
- enabledResearchLaneFlow.test.mjs: enabled-fixture for research collapses into default build — update OVERLAY_FLAGS/asserts accordingly.
- Frozen fixture: regenerate via scratchpad script (260730-din procedure), isolated commit; expect changed pairs = research-gate + research-request nodes in both variants (verify exact count from diff, likely 4/14: Research Trigger Gate + Build Research Request × 2 variants — contacts chain nodes also frozen? check FROZEN_NODE_NAMES).
- Run `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` — both green.
**verify:** suites green; fixture diff touches ONLY research-gate/request nodes; `git grep -c 'ALLOW_WEB_RESEARCH' tests/` consistent with new semantics (no test expects false-by-default build).
**done:** two commits — test churn, then fixture re-baseline isolated.

## Task 3 — Disarmed redeploy + read-back + STATE note

**files:** .planning/STATE.md
**action:** Deploy via dotenv wrapper (`.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"`), NO ENABLE_BAKED_FLAGS. Read back deployed LV Enrichment via n8n API using deploy module helpers (_base_url/_n8n_headers), inspect doc['nodes'] only (activeVersion duplicate-envelope gotcha from 260730-din).
**verify:** live nodes contain `ALLOW_WEB_RESEARCH = true`, `ANTHROPIC_RESEARCH_MODEL = "claude-haiku-4-5"`, `ANTHROPIC_JUDGE_MODEL = "claude-sonnet-5"`, `MAX_WEB_RESEARCH_PER_RUN` still 10; every `ALLOW_HUBSPOT_*` still `"false"`; allowlist empty. ZERO HubSpot calls.
**done:** read-back facts recorded in SUMMARY; STATE.md Session Continuity note added (uncommitted for orchestrator docs commit).

## Output

SUMMARY at .planning/quick/260730-fij-enable-web-research-haiku/260730-fij-SUMMARY.md with `status: complete` frontmatter. MUST surface verbatim the operator commands:
```
! sed -i '' -e 's/^ALLOW_WEB_RESEARCH=.*/ALLOW_WEB_RESEARCH=true/' -e 's/^ANTHROPIC_RESEARCH_MODEL=.*/ANTHROPIC_RESEARCH_MODEL=claude-haiku-4-5/' .env .env.example && grep -hE '^(ALLOW_WEB_RESEARCH|ANTHROPIC_RESEARCH_MODEL)=' .env .env.example
```

## Cost note (goes in SUMMARY)

Research lane now LIVE on scheduled runs: Haiku research ≈ $0.07/company-call incl. search fees, paced by MAX_WEB_RESEARCH_PER_RUN=10 per run (≈960/day ceiling at 15-min cadence). Judge escalations (Sonnet) expected on ~15-100% of researched companies per eval; capped 50/run.
