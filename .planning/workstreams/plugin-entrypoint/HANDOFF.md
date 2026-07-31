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
| 23 Walking skeleton | 6 | 5 done. **23-06 operator window IN PROGRESS — Section A partial, Section B blocked on two live findings, see §4** |
| 24 Non-tabular adapters | 3 | ✅ **COMPLETE** |
| 25 Enrichment lane & cost guard | 7 | ✅ **ALL 7 BUILT** — all four success criteria met. 25-01's Probe A ran live (**lists GRANTED**); **Probe B / B4 still outstanding**, so the chunk ceiling of 2 stays **PROVISIONAL** everywhere it appears |
| 26 Outcome reporting & retry | 3 | ✅ **COMPLETE** — amendment #4 closed, REQUIREMENTS.md reworded |
| 27 Backend status surface | 5 | ✅ **CODE-COMPLETE** — 27-01…05 all built. Only **27-05 Task 3** (dashboard same-URL, operator-run) outstanding |
| 28 Control actions | 6 | **checked twice** (5 blockers → repaired → 1 more → repaired). **28-01 DONE.** 28-02 is a human gate; 28-03/04 chain behind it; **28-05 serialized** behind the operator's `test_plugin_manifest.py` fix |
| 29 Notices & sweep | 6 | checker run + repaired (3 blockers). **29-02 DONE.** 29-03/04 need 29-01 (human) |
| 30 Review-queue triage | 7 | checker run + repaired (4 blockers). **30-01…30-06 ALL DONE.** Only **30-07** (armed canary, human) remains |

**34 of 43 plans built. Phases 24, 25, 26, 27 COMPLETE; 30 complete bar its canary.**

> ## ⚠ What is left, and why — read before concluding "nothing is runnable"
>
> **"Autonomous work is exhausted" was claimed twice on 2026-07-31 and was WRONG both times.**
> Check before believing it. Two things make plans look blocked when they are not:
>
> 1. **A plan marked `autonomous: false` can still have an autonomous Task 1.** 25-01 and 28-02 are
>    human *gates*, but each builds a probe script first, and those Task 1s were runnable all along.
>    Building them is what unblocked the operator.
> 2. **An operator result can unblock a plan silently.** 25-03's precondition was literally "a
>    granted verdict in `25-BLOCKERS.md`" — the moment Probe A returned granted, three plans became
>    runnable with no other change.
>
> **The inverse trap:** 28-03/28-04 *appear* runnable because 28-02 has a SUMMARY (written by its
> Task-1 executor), but they need `28-FINDINGS.md`, which is 28-02's **human** Task 3 output and does
> not exist. **Resolve dependencies against the artifact a plan actually reads, not against SUMMARY
> presence.**
>
> **Genuinely blocked right now:** 28-03/04/05/06 (need 28-02's live probe), 29-03/04/05/06 (need
> 29-01's host probe), 30-07 (armed canary). **Highest-leverage gates: 29-01 and 28-02**, four plans
> each.
>
> ✅ **`verify_live_write_safety.py` is FIXED** (plan 23-07). It now discovers rather than names —
> 8 workflows / 11 declaring nodes, up from 2 — a zero-discovery scan fails, and `--expect-armed`
> is symmetric. Both armed windows are unblocked on that axis.

**Test baselines — CURRENT:** `1529 passed, 1 skipped` (pytest), `506 passed` (node), plugin suite
`654 passed`. Milestone started at 709 pytest / 400 node; the handoff before this one read 919/400.
**Node includes 4 Apollo sentinel tests** merged from `fix/apollo-zero-revenue-band` — not a
regression signal. Any drop is a regression to investigate, not absorb.

**Known flake — ✅ FIXED.** The intermittent **1 ms timestamp mismatch** in
`tests/n8n/mergeContacts.test.mjs` (`lv_jobtitle_verified_at`) came from a strip helper anchored on
`"verified_at":`, which normalizes the bare provenance key but **never the prefixed canonical-patch
key**. The same narrow pattern was inlined **four times** (1× mergeContacts, 3× mergeCompanies), so
all four carried it. Now one shared `tests/n8n/verifiedAtStrip.mjs`, matching any key ending in
`verified_at` and normalizing only the value. Verified deterministically (stamps 1 ms apart: old
pattern DIFFERS, new EQUAL; a real value change still fails) rather than by re-running until green.
Sibling of `a0790cc`, same class: **a wall clock read twice and compared for equality.**
Every n8n artifact is **disarmed** (`grep -c` → 0) and REQUIREMENTS.md coverage is intact at **49/49**.

**Branch:** work is on **`feat/v0.6-plugin-entrypoint`**, not `master`. `master` is at `3e8dd1d`
(= `origin/master`, a GitHub merge that pulled the v0.6 line in along with the Apollo fix). The
v0.6 branch is a clean descendant of `origin/master`. **`worktree-claude-plugin-entrypoint` and its
worktree at `.claude/worktrees/claude-plugin-entrypoint` are GONE** (removed 2026-07-31, verified
first: zero unmerged commits, zero uncommitted or untracked files, and `git branch -d` — the merged-
only delete — accepted it). It was 109 commits behind master, so anyone resuming there would have
been missing the entire milestone. `fix/apollo-zero-revenue-band` is also fully merged and safe to
delete; left in place.

**Plan-checker status: all 8 phases have now been checked.** 23–26 passed earlier. 27 passed after
one blocker. 28 took two rounds (5 blockers, then 1 that the repair itself introduced into the one
file it had not edited — see §7b). 29 and 30 were checked 2026-07-31 immediately before execution.

**Uncommitted, and not yours:** an operator is mid-23-06 holding `STATE.md`,
`operator-claude-plugin/.claude-plugin/plugin.json`,
`operator-claude-plugin/tests/test_plugin_manifest.py`, and an untracked `23-06-SUMMARY.md`. Do not
stage, commit, or edit any of them. **`test_plugin_manifest.py` is why 28-05 is serialized.**

### First thing to do on resume

**No executor is in flight.** But the tree is **not** clean and that is expected — an operator holds
four uncommitted 23-06 files (listed in §1). Sanity-check, then proceed:

```bash
git rev-parse --abbrev-ref HEAD                                      # expect feat/v0.6-plugin-entrypoint
git status --porcelain | grep -v DS_Store | grep -v '^?? .claude/'   # expect ONLY the operator's 4 files
.venv/bin/python -m pytest -q | tail -2                              # expect 1529 passed, 1 skipped
node --test tests/n8n/*.test.mjs 2>&1 | grep -E '^. (pass|fail) '    # expect pass 506, fail 0
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = \\"true\\"' n8n/*.json              # expect 0 everywhere
```

**General caution:** if a SUMMARY is missing while that plan's commits are present, the agent died
mid-plan — re-run it rather than assuming it finished. This has happened twice (26-01, 26-02); both
times the code was committed and only the summary was orphaned, so check before re-running.

**Next batch, in order:**
1. **Re-check what is runnable** using the trap notes above — do not assume. As of this writing every
   remaining plan is a human gate or chained behind one, but that has been wrong twice today.
2. **28-03, 28-04** the moment 28-02's live probe produces `28-FINDINGS.md`; then 28-05 — but 28-05
   is **serialized** behind the operator committing `test_plugin_manifest.py`, by operator decision.
3. **29-03, 29-04** once 29-01's host probe answers; then 29-05, then 29-06.

**A contract held in two places needs a test that reads both.** Phase 25 shipped this bug twice in
one day — the list envelope (client flat, backend nested: the whole list lane refused every request
while both suites stayed green) and the chunk ceiling (two copies of `2`). Both are now pinned by
paired tests (`13006fa`, `1196c57`). Per-component testing cannot see either.

**Do not re-run the phase checkers.** All 8 phases are checked. Re-checking is warranted only after
a repair pass — which is itself a real source of drift, see §7b.

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
- **The deploy tenant is `https://alexherman.app.n8n.cloud`** — confirmed correct 2026-07-31.
  **`N8N_EXPECTED_URL` must be set to it**, because
  `scripts/deploy_n8n_workflows.py::_instance_ok()` pins `N8N_URL == N8N_EXPECTED_URL` **only when
  that variable is set**; unset, it falls back to `host.endswith(".n8n.cloud")`, which any n8n Cloud
  tenant satisfies. The guard separates "is an n8n host" from "is not" — never "is the right
  tenant". **Both runbooks' old instruction (key must be Robert's, Alex's in `N8N_API_KEY_2`) was
  unfollowable: `N8N_API_KEY_2` does not exist.** Corrected in both; it blocked 23-06 Section B.
- **The plugin manifest's `author` must be an object, not a string** — `claude plugin validate`
  rejects `"author": "Lightning Visuals"` with `expected object, received string`, and the Desktop
  plugin-manager install would have failed the same way. `test_plugin_manifest.py` asserted only
  that the key was *present*, never its type. Found live by 23-06 A1, 2026-07-31.
- **Scheduled Claude routines are enabled on this machine** (`coworkScheduledTasksEnabled`,
  `ccdScheduledTasksEnabled`), with a working example at
  `~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md`. Unverified: whether one can invoke
  *this plugin's* skill — that is 29-01's first task.

---

## 3. Accepted requirement amendments (seven)

Each was surfaced explicitly and chosen. **None is silent drift. Do not revert them.**

| # | Requirement | Amendment |
|---|---|---|
| 1 | PLUGIN-02 | Operator, not admin, does config setup from the committed example. **Already reworded in REQUIREMENTS.md by 23-05** |
| 2 | Phase 25 criterion 2 | Provider default ships as full waterfall. Mitigated: `Parse HubSpot Event` has no server-side default and fails closed; resolved selection always shown in preview |
| 3 | STATUS-04 + Phase 27 criterion 4 | Stuck-lock redefined as long-running execution. **Already reworded by planner 27** |
| 4 | REPORT-02 | ICP-tier clause removed — HubSpot owns derived ICP outputs (Phase 15 "Approach C": `src/merge_policy.py:347`, `n8n/code/mergeCompanies.js:53`, `config/field_policy.yaml:97`). **Rewording is 26-02 Task 3, not yet executed** |
| 5 | CONTROL-01 + Phase 28 criterion 1 | Off-cycle scheduled-scan execution dropped (no endpoint exists). Operator uses enable/disable + re-timing |
| 6 | Mutation allowlist (CONTROL-03) | Widened by exactly one field: a Schedule Trigger node's `disabled` boolean, because `LV Scheduled Maintenance (Cloud)` has **five** Schedule Triggers so workflow-level on/off can't express per-job control |
| 7 | INGEST-04 + ROADMAP criterion 1 | **Saved views refused**, scope is **lists + record IDs**. Applied by 25-07. Lists were **denied (403)** on first probe and are now **GRANTED** — `crm.lists.read` was added to the `ausgtm-lightningvisuals-data` static-auth app and **reinstalled** (`hs project install-app`; uploading a scope does not grant it, and rotating the token never would). Had the 403 stood, this would have been the *large* amendment dropping lists too. Refusal sentence lives once, as `enrichment.VIEW_REFUSAL` |

---

## 4. The two human checkpoints (the binding constraint)

Agent tooling in this repo is **classifier-blocked from arming writes**. These must be run by a human.

**A consolidated runbook now covers ALL human-gated plans in one file:**
`.planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md` — every command with its `.env`
loading form, a readiness table, and uniform gating rules. The per-phase runbooks remain
authoritative for their own ceremony. **Eight gates remain, not nine: RB-6 (28-04) was withdrawn**
because D-25 had already settled that decision and the plan was asking the operator to re-decide it.

### 23-06 — plugin install + armed create canary  ← IN PROGRESS, and it found two real defects

Walking it surfaced **three** confirmed defects. **Two are now FIXED by plan 23-07; one remains.**

1. ✅ **FIXED — the read-back did not cover the lane the canary fires at.**
   `verify_live_write_safety.py` hardcoded the enrichment workflow and two `Decide*` node names,
   taking no workflow argument, so it inspected **2 of 11 declaring nodes** and **none in
   `LV Contact Ingest`**. 23-07 replaced naming with **discovery**: verified live, it now scans
   **8 workflows / 11 declaring nodes**. A zero-discovery scan **fails** rather than passing quietly.
2. ✅ **FIXED — `--expectation armed` rejected a correctly armed window.** It required
   `RECORD_WRITES` armed and *every* other boolean disabled ("canary scope is record writes only"),
   with no way to permit `CREATE` — so Step 3b failed on a backend armed exactly as Step 3 intended.
   23-07 added **`--expect-armed FLAG,FLAG`**, symmetric: named flags must be enabled, **everything
   else is still asserted disabled**. Verified: arming an unnamed flag is caught, in the contact lane.
   Omitting the flag keeps Phase 22's stricter meaning, so the completed Phase 22 runbook still works.
3. ⏳ **STILL OPEN — 23-01's create-gate fix is committed but not deployed.** Live contact ingest
   declares literals in only its two write gates. Step 3 would push never-live-tested logic in the
   same action that arms writes. Runbook inserts Steps 2b/2c: a disarmed deploy plus read-back first.

**Declaration counts move — never memorise them.** They were 9/8 in the morning and
**CREATE 11 / RECORD_WRITES 10 / REVIEW_WRITES 10 across 11 nodes** by the afternoon, because 30-01
added a constant to 8 nodes and 30-02 added a whole workflow. Both runbooks now **derive** the
expected rewrite count at deploy time; a stale figure makes a *correct* deploy look like a misfire.
**`STATE.md`'s stale 2-of-8 claim is now corrected** (2026-07-31): FINDING 1 struck through and
marked resolved by 23-07, FINDING 2's memorised count replaced with the derive-at-deploy-time rule,
and Session Continuity brought forward from "27-05 is next" to the real state. **The file is still
operator-held and left UNSTAGED** — it carries the operator's own uncommitted 23-06 hunks, which are
not ours to commit. Whoever owns those hunks commits the whole file.

Also found by A1: **the plugin manifest's `author` must be an object, not a string** —
`claude plugin validate` rejects the bare string, and the Desktop install would have failed the same
way. `test_plugin_manifest.py` asserted the key was *present*, never its type.

**Runbook written and committed:**
`.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-OPERATOR-RUNBOOK.md`

Section A (install + invoke, 7 read-only observations) gates Section B (the armed window).
Canary CSV prepared at `~/Desktop/lv-canary-23-06.csv` for
`canary-23-06-20260731@australiagtm.com`. **Unblocks nothing downstream** — it is Phase 23's own proof.

### 25-01 — mostly DONE. Probe A ran, the decision is made, only Probe B remains.
- **Probe A (lists scope): DONE, GRANTED.** First run returned **403**; `crm.lists.read` was added
  to `ausgtm-lightningvisuals-data`'s `requiredScopes` and **reinstalled** via `hs project
  install-app` — uploading a scope does not grant it, and rotating the token never would. Re-probe:
  `granted / 200`, list id 15 (`New Targets.xlsx`, contacts, 102 members). Token did not rotate.
- **Task 3 (view resolution): DECIDED — `refuse-and-redirect`, amendment #7.** Applied by 25-07.
- **Probe B (chunk timing): STILL OUTSTANDING.** 29-02 measured **36.1 s/record** free from
  execution history, deriving a ceiling of **2** — but every measured run was single-record,
  company-lane, and **none was a full waterfall**. **B4 is the only source for the expensive path**,
  and until it runs the ceiling stays labelled PROVISIONAL in every artifact carrying it.

**No longer blocks anything** — 25-03/04/06/07 are all built. Everything is in `OPERATOR-RUNBOOK.md`
§RB-1, including a verdict table (**200 and 404 both mean granted; 403 is the denial**).

**One free live check to run alongside B4:** a single POST naming `New Targets.xlsx` should return
the **oversize refusal** (102 members vs a ceiling of 2) — not a 200, not a hang. Zero writes, zero
credits, and it exercises the one path 25-03 built but could not test live.

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

## 7b. Why the 28/29/30 checkers are deferred — this is not laziness

**Run each phase's `gsd-plan-checker` immediately before executing that phase, never earlier.**

All 43 plans were written in one batch, so a plan for a later phase necessarily *guessed* at
artifacts its dependencies had not built yet. A checker run at planning time has nothing to compare
against; only after the dependency exists can the mismatch be seen.

**This already happened once and was caught exactly this way.** Phase 27's checker found that
`27-01` targeted `build_enrichment_cloud()` / `n8n/wf_enrichment_cloud.json` — a guess made before
Phase 25 executed. 25-02 had instead built the status endpoint as its own file per D-14, precisely
so a responder would not sit on the enrichment workflow's branch and corrupt real enrichment
responses. Unfixed, an executor would have added HubSpot search nodes to the enrichment workflow and
silently violated D-14. Fixed in commit `5b138a1`.

**Expect the same class of finding in 28, 29 and 30.** Phase 28 is the highest risk: it is the only
phase that mutates production, and its read-back verification depends on the status-endpoint shape
27-01 is changing. Treat a checker blocker there as expected work, not an anomaly.

## 8. Working conventions that have been paying off

- **Tell every executor about its concurrent siblings** and which filesystem region each owns.
- **A CONTRACT HELD IN TWO PLACES NEEDS A TEST THAT READS BOTH.** This produced three real bugs on
  2026-07-31, none visible to per-component testing:
  - **The list envelope.** Client emitted flat `{"list": "<name>", "objectType": ...}`; backend reads
    `isPlainObject(body.list)` then `.name`/`.objectType`. A string is non-null, so it **passed** the
    `IF List Input` gate and was then refused by **every** request — the whole list lane dead while
    both suites stayed green. Fixed `13006fa`; one literal now pinned from both sides.
  - **The chunk ceiling**, declared in the backend builder and the client config with nothing forcing
    agreement. Pinned `1196c57`.
  - **The runbook's memorised rewrite counts** — 9/8 in the morning, 11/10/10 by afternoon. Both
    runbooks now **derive** them at deploy time; a stale count makes a *correct* deploy look like a
    misfire.
  **Never write the same number or shape in two files without a test that fails when they diverge.**
- **`<phase>-CONTEXT.md` is a shared surface too**, added the hard way: 25-05's commit swept 25-04's
  staged hunk there. Name it alongside `SKILL.md`/`README.md` when briefing concurrent executors.
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
