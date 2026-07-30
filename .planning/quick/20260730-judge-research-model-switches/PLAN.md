# Quick Task Plan — Split model switches (RESEARCH/JUDGE) + arm judge

**Date:** 2026-07-30
**Status:** PLANNED (not executed)
**Driver:** Haiku-vs-Sonnet A/B eval (2026-07-30, n=35 runs): Haiku 96% correct on
lv_org_type/lv_produces_content but confidently-wrong tail (error at c92 inside the
correct-answer band) — no usable confidence frontier (t=95 blocks the error but sends
52% of correct outputs to review). Guard is the EXISTING judge value-triggers
(produces_content_false, vendor flags, org_type_conflict, confidence_band 75–85) —
which requires the judge to actually be ON.

## Objective

1. Split the single `ANTHROPIC_SONNET_MODEL` knob into two independent levers:
   - `ANTHROPIC_RESEARCH_MODEL` — Build Research Request (companies + contacts chains)
   - `ANTHROPIC_JUDGE_MODEL` — Build Judge Request (companies + contacts chains)
   Both default `claude-sonnet-5` (behavior-preserving). Flipping research to
   `claude-haiku-4-5` becomes a later one-line default change / env override —
   deliberately NOT part of this task (operator at medium confidence).
2. Rename `ALLOW_SONNET_ESCALATION` → `ALLOW_JUDGE_ESCALATION`; **default flips
   `false` → `true`** (judge armed by default — precondition for any Haiku swap:
   judge-off leaves the D5 hole where an evidenced `produces_content=false` flows
   unadjudicated, judge.js:162).
3. Rename `MAX_SONNET_VALIDATIONS_PER_RUN` → `MAX_JUDGE_VALIDATIONS_PER_RUN`;
   **default raises `10` → `50`** (capped-out rows fall to applyUnadjudicated — same
   D5 hole; 50 covers a full SJ-3 batch page. Cost ceiling ≈ 50 × ~$0.03 ≈ $1.50/run).

**Explicitly out of scope (operator decision, do not re-add):**
- org_type evidence-gate in `computeEscalation` (the >85-confidence blank-record gap) —
  plausible, not observed; YAGNI until it actually bites.
- Changing either model default to Haiku.
- Any n8n/code/judge.js logic change (comments mentioning ALLOW_SONNET_ESCALATION may
  be renamed for greppability; zero logic edits).

## Touchpoints (surveyed 2026-07-30)

### Task 1 — Builder: scripts/build_cloud_workflows.py
- `CONFIG_FLAG_DEFAULTS` (~L781): remove `ANTHROPIC_SONNET_MODEL`; add
  `ANTHROPIC_RESEARCH_MODEL: "claude-sonnet-5"`, `ANTHROPIC_JUDGE_MODEL:
  "claude-sonnet-5"`; rename escalation flag → `ALLOW_JUDGE_ESCALATION: "true"`;
  rename cap → `MAX_JUDGE_VALIDATIONS_PER_RUN: "50"`. Net flag count 6 → 7.
- Build Research Request (~L2111, `_enrich_build_research_request_js`, BOTH targets):
  `_flag_const("ANTHROPIC_RESEARCH_MODEL", cloud)`; `const model = ANTHROPIC_RESEARCH_MODEL;`
- Judge Trigger Gate (~L2176–2178): renamed flag consts (`allowOn`, `MAX_PER_RUN` reads).
- Build Judge Request (~L2209–2213): `ANTHROPIC_JUDGE_MODEL`.
- Sweep builder comments/docstrings for old names (L2102, L2165, L2202).

### Task 2 — Deploy overlay: scripts/deploy_n8n_workflows.py
- `_OVERLAY_FLAG_SPEC` (~L125): DELETE the `ALLOW_SONNET_ESCALATION` entry. Flag is
  default-true; the overlay mechanism only widens disabled→enabled, so an entry is
  meaningless. Emergency off = edit CONFIG_FLAG_DEFAULTS + rebuild + disarmed redeploy
  (proven path). Update module docstring (~L104) + harness-env docstring (~L378).

### Task 3 — Python oracle parity: src/
- `src/validator_sonnet.py`: `ALLOW_JUDGE_ESCALATION`, `ANTHROPIC_JUDGE_MODEL`
  (defaults: "true" / "claude-sonnet-5" — drop the stale `-latest` suffix while here).
- `src/web_research.py`: `ANTHROPIC_RESEARCH_MODEL`.
- grep src/ + main.py for any other os.getenv of old names.

### Task 4 — Env + config docs
- `.env.example`: replace 3 lines with 4 (two model vars, renamed flag=true, cap=50).
- **Live `.env` (operator step — dotfile is permission-blocked to the agent):** run in
  the session with `!` once the code lands:
  ```
  ! sed -i '' -e 's/^ANTHROPIC_SONNET_MODEL=.*/ANTHROPIC_RESEARCH_MODEL=claude-sonnet-5\nANTHROPIC_JUDGE_MODEL=claude-sonnet-5/' -e 's/^ALLOW_SONNET_ESCALATION=.*/ALLOW_JUDGE_ESCALATION=true/' -e 's/^MAX_SONNET_VALIDATIONS_PER_RUN=.*/MAX_JUDGE_VALIDATIONS_PER_RUN=50/' .env
  ```
  Then verify (prints names only, no secrets):
  `! grep -E '^(ANTHROPIC_(RESEARCH|JUDGE)_MODEL|ALLOW_JUDGE_ESCALATION|MAX_JUDGE_VALIDATIONS_PER_RUN)=' .env`
- `config/escalation_policy.yaml`: section name `sonnet_5:` stays (describes the judge
  role, not the env var) — comment-only touch if any old env names appear.

### Task 5 — Tests (expected churn; rename, don't weaken)
- `tests/test_builder_flag_parity.py` — flag list (7 entries).
- `tests/test_deploy_flag_overlay.py` — remove/convert every ALLOW_SONNET_ESCALATION
  overlay case (entry deleted per Task 2); keep ALLOW_WEB_RESEARCH cases intact.
- `tests/test_enabled_build_invariants.py` — FLAGS tuple (now research-only for overlay),
  cap/model name lists (~L161, L184, L192).
- `tests/test_deploy_write_safety_overlay.py` — parametrize list (~L140).
- env-setters: `test_main.py`, `test_service.py`, `test_e2e_ingest.py`,
  `test_contact_ingest.py` — rename monkeypatch.setenv.
- `tests/n8n/enabledResearchLaneFlow.test.mjs` — OVERLAY_FLAGS + baked-const asserts
  (flag now true in the DEFAULT build; the "enabled overlay" fixture may collapse into
  the default build for the escalation half).
- `tests/n8n/researchRequestSponsorshipContract.test.mjs` — baked model const name.
- `tests/n8n/contactResearchChainRowFlow.test.mjs` — comment + budget fixture.
- `tests/test_companies_factory_frozen.py` (byte-identity) — WILL fail by design;
  regenerate the frozen snapshot per that file's documented procedure. Never hand-patch
  bytes.
- `tests/test_judge_spec.py` currency test — unaffected unless escalation.generated.js
  changes (it does not; thresholds/vocab only).

### Task 6 — Rebuild + verify (local)
- `.venv/bin/python scripts/build_cloud_workflows.py` (regenerates n8n/wf_*.json).
- Full suite: `.venv/bin/python -m pytest` + `node --test tests/n8n/*.test.mjs`
  (dir-form broken on node 24 — glob the files).
- Grep generated `n8n/wf_enrichment_cloud.json`:
  - `const ALLOW_JUDGE_ESCALATION = true;` present; old names ZERO occurrences anywhere
    in n8n/*.json.
  - `ANTHROPIC_RESEARCH_MODEL` in both research request nodes;
    `ANTHROPIC_JUDGE_MODEL` in both judge request nodes;
    `MAX_JUDGE_VALIDATIONS_PER_RUN` = "50".

### Task 7 — Deploy (disarmed) + read-back
- Dotenv-wrapper deploy (Phase 19 runbook form):
  `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"`
- Read back deployed workflow JSON via n8n API (disarmed reads are permitted); assert
  the three Task-6 grep facts against the LIVE copy.
- Write-safety flags stay disarmed ("false") — this deploy touches model/judge flags only.

### Task 8 — Docs
- `CLAUDE.md`: 11 mentions (L895, 910, 923, 1243, 1477–1479, 2135, 2144, 3030, 3037,
  3346) — rename + new defaults + add second model var to §11.2/§21.1 blocks.
- `README.md` / Phase-19 runbook references to ENABLE_BAKED_FLAGS=...ALLOW_SONNET_ESCALATION:
  drop the escalation flag from examples.
- `.planning/STATE.md`: one-line note under Session Continuity.

## Success criteria
1. Old flag/model names: zero occurrences in scripts/, src/, tests/, n8n/*.json,
   .env.example (docs/ archives + .planning/milestones exempt — historical).
2. Both suites green.
3. Live (disarmed) deployment carries: judge armed (true), cap 50, split model consts,
   models still claude-sonnet-5 both.
4. No write-safety flag changed; no HubSpot write occurs at any step.

## Risks / notes
- Judge now live in cloud: real Sonnet judge spend begins on next armed enrichment runs
  (~$0.03/judged company; ≤$1.50/run at cap). ALLOW_WEB_RESEARCH remains false — research
  lane still off until separately enabled, so judge fires only on provider-conflict paths
  until then (research triggers dominate once research is enabled).
- Frozen-bytes test churn is the bulk of the diff — budget most review attention there.
- After this lands, the Haiku experiment is literally:
  `ANTHROPIC_RESEARCH_MODEL=claude-haiku-4-5` default change (or env override in
  local-live) + rebuild + disarmed redeploy. Nothing else moves.

**Est. effort:** ~half day (test churn dominated).
