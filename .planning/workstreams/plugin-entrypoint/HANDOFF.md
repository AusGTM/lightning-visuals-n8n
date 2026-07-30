# v0.6 Handoff — Claude Plugin Entrypoint

**Written:** 2026-07-31 · **Milestone:** v0.6 · **Workstream:** `plugin-entrypoint`
**Read this first on a fresh context.** It exists so you do not re-derive facts that were already
established live, and do not trust documentation that has been verified wrong.

---

## 1. Where things stand

All 8 phases (23–30) are **discussed, researched, and planned**: 43 plans on disk. Execution is
mid-flight.

| Phase | Plans | State |
|---|---|---|
| 23 Walking skeleton | 6 | 5 done. **23-06 is a human checkpoint — see §4** |
| 24 Non-tabular adapters | 3 | ✅ **ALL 3 DONE** (24-01, 24-02, 24-03) |
| 25 Enrichment lane & cost guard | 7 | 25-02 done. **25-01 is a human checkpoint — see §4** |
| 26 Outcome reporting & retry | 3 | checker-clean. 26-01 done. **26-02, 26-03 runnable now** |
| 27 Backend status surface | 5 | planned, dependency (25-02) satisfied → **runnable after its checker** |
| 28 Control actions | 6 | planned, chained behind 27 |
| 29 Notices & sweep | 6 | planned, chained behind 27/28 |
| 30 Review-queue triage | 7 | planned, chained behind 28 |

**Test baselines at handoff:** `869 passed, 1 skipped` (pytest) and `378 passed` (node); the plugin's
own suite is `125 passed`. Started the milestone at 709. Any drop is a regression to investigate,
not absorb. Working tree was **clean** and every n8n artifact **disarmed** at handoff.

**Plan-checker status:** 23, 24, 25, 26 all PASSED. **27, 28, 29, 30 have NOT been checked** —
deliberately deferred, because checking plans against a tree where their dependencies don't exist
produces a pass that goes stale. **Run the checker for each of those immediately before executing
it.**

### First thing to do on resume

**Nothing was in flight at handoff** — all executors completed and the tree was clean at commit
`9552c65`. Sanity-check that it still is, then proceed:

```bash
git status --porcelain | grep -v DS_Store | grep -v '^?? .claude/'   # expect empty
.venv/bin/python -m pytest -q | tail -2                              # expect 869 passed, 1 skipped
node --test tests/n8n/*.test.mjs 2>&1 | grep -E '^. (pass|fail) '    # expect pass 378, fail 0
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = \\"true\\"' n8n/*.json              # expect 0 everywhere
```

**Immediately runnable, no human input needed** — a good next batch:
- **26-02** and **26-03** (Phase 26 wave 2, both depend only on 26-01 which is done). Note **26-02
  Task 3 closes amendment #4** by rewording REPORT-02 in REQUIREMENTS.md.
- **Phase 27** — run `gsd-plan-checker` on it first (it has never been checked), then 27-01, whose
  dependency on 25-02's `hubspot/backend-status` endpoint is now satisfied.

A general caution for any future batch: if a SUMMARY is missing while that plan's commits are
present, the agent died mid-plan — re-run it rather than assuming it finished.

---

## 2. Verified facts that CONTRADICT the documentation

**The root `CLAUDE.md` describes an aspirational system. The deployed one differs.** Every item
below was verified against deployed JSON or live probes. Do not "correct" them back.

| Documented | Actually |
|---|---|
| `enrichment_lock_until` property exists | **Does not exist anywhere.** `lv_enrichment_status` is only ever written `needs_review` or `complete` — nothing sets `running`. Stuck-lock is redefined as execution age |
| Flat `<field>_source` / `_verified_at` / `_verified_by_model` metadata convention | **Does not exist.** Real mechanism is one JSON blob per object: `lv_enrichment_provenance` (companies) / `lv_contact_enrichment_provenance` (contacts), entries `{source, confidence, verified_at, validation_status, value, evidence_url?}`, **no `verified_by_model` key** |
| Generic unprefixed review property names | **All `lv_`-prefixed**: `lv_enrichment_needs_review`, `lv_enrichment_review_reason`, `lv_enrichment_review_candidate_json`, `lv_enrichment_review_approved`, `lv_enrichment_reviewed_by`, `lv_enrichment_reviewed_at`, `lv_icp_needs_review` |
| `Decide Action` emits `email` | **It does not.** Returns `{action, outcome, contact_id, hs_object_id, reason, email_status, properties}` |
| Write-safety literal in 2 nodes | **`ALLOW_HUBSPOT_CREATE` in 9 nodes; `ALLOW_HUBSPOT_RECORD_WRITES` in 8** — contact 3/2, enrichment 2/2, maintenance 4/4. **Different subsets.** Never hardcode a node list |
| `POST /api/v1/workflows/{id}/execute` | **Does not exist** — open, unmerged upstream PR #20304 |
| ROADMAP's "reuse `src/file_loader.py`" | Superseded by Phase 23 D-01. `_has_identity` there **does not trim**; the live n8n rule does. Do not copy it |

### Other load-bearing verified facts

- **Auth header is literally `X-Enrichment-Secret`**, shared with the enrichment webhook — not a
  contact-upload-specific name.
- **Multipart field name is `data`**; `Extract From File`'s operation is hardcoded `"csv"`, so
  **XLSX must be converted to CSV bytes client-side**.
- **Canonical props are exactly 7:** `email, firstname, lastname, jobtitle, linkedin_url, phone,
  company`. The backend **silently drops unmapped keys with no report** — "report, don't drop" can
  only be honored client-side.
- **The identity rule lives in `Map Columns.requiredIdentity()`** (trim-then-presence), *not* in
  `Resolve Identity` / `Merge Contacts` (those are CRM dedupe, out of scope).
- **Set Review strips every identifying field** — build ledgers from `Decide Action` output.
- **No webhook returns an execution ID.** Run handles are time-proximity correlation — fallible, say so.
- **Webhook response ceiling is a Cloudflare-enforced ~100s** (524 on breach). The enrichment
  workflow has **no `Split In Batches`** — every record runs the full provider+Haiku+Sonnet chain
  before the response fires.
- **Arming a flag with an EMPTY allowlist grants nothing while reporting success.**
  `_writeSafetyAllows()` starts `if (!allowedDomains.length && !allowedIds.length) return false;`
- **`enable_baked_flags()` cannot disarm** — it only widens disabled→enabled. **Disarming is
  redeploying the committed (disarmed) artifact.**
- **Provider nodes are `onError: continueRegularOutput`** — a 401/429/quota failure does **not** fail
  the n8n execution. Read per-node output, not run status. Same pattern in
  `wf_scheduled_maintenance_cloud.json`'s HubSpot-Search nodes.
- **Both workflows contain a node named `Decide Action`**; enrichment also has
  `Decide Company Action`. Select by **workflow first, then lane**.
- **HubSpot saved views have no public API**; the Lists API needs `crm.lists.read`, unevidenced in
  this repo. Unresolved — 25-01 probes it.
- **Claude Desktop Code-tab file handoff: BOTH legs work** (verified live 2026-07-31). Attachment
  resolves to a real path; `@mention` resolves too but **indexes the workspace only**.
- **Scheduled Claude routines are enabled on this machine** (`coworkScheduledTasksEnabled`,
  `ccdScheduledTasksEnabled`), with a working example at
  `~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md`. Unverified: whether one can invoke
  *this plugin's* skill — that is 29-01's first task.

---

## 3. Accepted requirement amendments (six)

Each was surfaced explicitly and chosen. **None is silent drift. Do not revert them.**

| # | Requirement | Amendment |
|---|---|---|
| 1 | PLUGIN-02 | Operator, not admin, does config setup from the committed example. **Already reworded in REQUIREMENTS.md by 23-05** |
| 2 | Phase 25 criterion 2 | Provider default ships as full waterfall. Mitigated: `Parse HubSpot Event` has no server-side default and fails closed; resolved selection always shown in preview |
| 3 | STATUS-04 + Phase 27 criterion 4 | Stuck-lock redefined as long-running execution. **Already reworded by planner 27** |
| 4 | REPORT-02 | ICP-tier clause removed — HubSpot owns derived ICP outputs (Phase 15 "Approach C": `src/merge_policy.py:347`, `n8n/code/mergeCompanies.js:53`, `config/field_policy.yaml:97`). **Rewording is 26-02 Task 3, not yet executed** |
| 5 | CONTROL-01 + Phase 28 criterion 1 | Off-cycle scheduled-scan execution dropped (no endpoint exists). Operator uses enable/disable + re-timing |
| 6 | Mutation allowlist (CONTROL-03) | Widened by exactly one field: a Schedule Trigger node's `disabled` boolean, because `LV Scheduled Maintenance (Cloud)` has **five** Schedule Triggers so workflow-level on/off can't express per-job control |

---

## 4. The two human checkpoints (the binding constraint)

Agent tooling in this repo is **classifier-blocked from arming writes**. These must be run by a human.

### 23-06 — plugin install + armed create canary
**Runbook written and committed:**
`.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-OPERATOR-RUNBOOK.md`

Section A (install + invoke, 7 read-only observations) gates Section B (the armed window).
Canary CSV prepared at `~/Desktop/lv-canary-23-06.csv` for
`canary-23-06-20260731@australiagtm.com`. **Unblocks nothing downstream** — it is Phase 23's own proof.

### 25-01 — lists-scope probe + chunk-timing measurement  ← HIGHER LEVERAGE
**No runbook written yet.** Two live checkpoints:
1. One live call verifying whether the HubSpot credential carries `crm.lists.read`.
2. Measure real per-record wall-clock time to derive `max_records_per_chunk`.
Plus a decision on whether saved-view resolution is feasible at all — if not, **INGEST-04 scopes
down to lists + record IDs** and that becomes amendment #7.

**Blocks 25-03, 25-04, 25-06, 25-07 — and through them most of the milestone's back half.**
Write it a runbook in the same form as 23-06's when the operator is ready.

---

## 5. Safety invariants — never violate

- **Committed n8n artifacts stay disarmed.** Verify with:
  `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = \\"true\\"' n8n/*.json` → expect 0.
- **No automated verification may arm anything, deploy, activate, or perform a live HubSpot write.**
- The plugin's autouse `no_network` guard blocks `requests` — **including `requests.get`**, which
  routes through the patched `Session.request`. (A planner once reported this as a hole; it was
  verified empirically and is **not**.)
- **A re-send is a send** — retry flows through the same armed dispatch path.
- **The plugin imports nothing from `src/` or repo-root `scripts/`** — enforced by an AST test,
  `operator-claude-plugin/tests/test_no_backend_imports.py`.
- **Plugin tests must not import a package named `scripts`** — from repo root that resolves to the
  *backend's* package. `conftest.py` puts `operator-claude-plugin/scripts` on `sys.path` for flat
  imports. No `__init__.py` under the plugin's `tests/`.

---

## 6. Tooling gotchas that cost time

- **Live scripts need the dotenv wrapper.** A bare `python scripts/foo.py` from a fresh shell
  **silently sees no credentials and skips**:
  ```bash
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/<script>.py', run_name='__main__')" [args]
  ```
- **Test invocation:** `.venv/bin/python -m pytest` (system python lacks the suite's deps) and
  `node --test tests/n8n/<file>.test.mjs` in **FILE form** — the directory form is broken on this
  node version.
- **All GSD tool calls need `--ws plugin-entrypoint`.** Without it they resolve `.planning/ROADMAP.md`
  (doesn't exist post-reorg) and report `phase_found: false`.
- **`check.decision-coverage-plan` is unreliable here** — returns `covered=0` with an *empty*
  uncovered list for some phases. Do not chase it. `gsd-plan-checker` is the real gate.
- **`state.planned-phase` / `state.update-progress` mangle this workstream's STATE.md**
  (it rewrote `milestone_name` to "Progress" once). Hand-edit STATE.md instead.
- Interpreter split: plugin scripts run under the session's `python3` (which has `openpyxl`,
  `requests`, `yaml`); the repo suite needs `.venv/bin/python`.

---

## 7. Dependency graph — what unblocks what

```
23-06 (human) ──> nothing downstream (Phase 23's own proof)

25-01 (human) ──> 25-03, 25-04 ──> 25-06 ──> 25-07
25-02 (DONE)  ──> 25-05 ──────────────────────┘
              └──> 27-01 ──> 27-02..05 ──> 28-01..06 ──> 29-*, 30-*

24-01 (DONE)  ──> 24-02, 24-03
26-01         ──> 26-02, 26-03   (26-03 Task 2 needs dispatch.py — exists)
```

**Runnable without any human input once the in-flight three land:** Phase 27 (after its checker),
then 28, then 29 and 30 — except each phase's own armed checkpoints (28-02, 28-06, 29-01, 30-07).

---

## 8. Working conventions that have been paying off

- **Tell every executor about its concurrent siblings** and which filesystem region each owns.
- **The real shared surfaces are `SKILL.md` and `README.md`, not `conftest.py`.** Learned the hard
  way: 24-03 and 26-01 collided on `operator-claude-plugin/skills/contact-upload/SKILL.md` while
  both were uncommitted in the same working tree. Almost every plan from Phase 24 onward adds a
  step to that one file, because it is the single operator-facing script for the whole plugin.
  **Name it explicitly when briefing concurrent executors**, or serialize any two plans that both
  touch it.
  - The collision resolved cleanly — the 26-01 agent detected it and isolated the sibling's hunks
    with `git add -p` — and content integrity was verified afterward (8 steps, correct order, both
    contributions present). But it left an artifact: **commits `d8bc409` and `347faaf` carry an
    identical message**, and `d8bc409` is **mislabelled** — it says "report step in the skill" but
    actually contains 24-03's extraction hunks. History was not rewritten, since rewriting shared
    history is riskier than a wrong commit message. Do not be confused by it.
- **Verify safety claims independently** rather than trusting agent reports. Two planner claims were
  wrong when checked (the `requests.get` guard "hole"; a node count). One executor claim about
  weakening an architecture guard turned out to be a *strengthening* — it asserts zero write nodes
  rather than skipping the file.
- **Fold research corrections back into the phase CONTEXT.md**, not just the plans. The planner reads
  CONTEXT; leaving a correction only in RESEARCH means it gets re-litigated.
- **A "no" from a probe is a build instruction, not a failure.** 23-02 was written expecting a
  negative result and pre-authorizing a degraded build; the positive result widened the design.
