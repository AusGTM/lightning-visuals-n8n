# Operator Runbook — v0.6 Claude Plugin Entrypoint, all human-gated plans

**Written:** 2026-07-31 · **Workstream:** `plugin-entrypoint` · **Milestone:** v0.6

Nine plans in this milestone cannot be run by agent tooling. Every one of them is here, with its
exact commands and the `.env` loading each needs. This is the consolidated companion to
`phases/23-.../23-OPERATOR-RUNBOOK.md`, which remains the authoritative narrative for 23-06's
ceremony; §RB-3 below carries 23-06's commands so this file is complete on its own.

**Why these are yours:** agent tooling in this repo is classifier-blocked from arming write flags,
deploying, activating workflows, and performing live HubSpot writes. Read-only probes are also here
because several are platform interactions (Claude Desktop, scheduled routines) that no test harness
can drive.

---

## §0 — Command form and `.env` loading

Three forms appear below. Use the one each step names.

### Form 1 — Python scripts (in-process dotenv wrapper)

**None of this repo's scripts call `load_dotenv()` themselves. A bare `python scripts/foo.py` from a
fresh shell silently sees no credentials and skips.** Always:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/<script>.py', run_name='__main__')" [trailing CLI args]
```

- Run from the **repo root** — the relative `scripts/` path and `.env` discovery both assume it.
- `load_dotenv()` defaults to `override=False`: variables already set in the shell win over `.env`.
  `.env`'s own `DRY_RUN=true` **cannot** un-arm a shell-set `DRY_RUN=false`. That is how arming works.
- `.venv/bin/python`, not system python — the suite's deps are only in the venv.

### Form 2 — curl and other non-Python tools (export into the shell)

The wrapper above loads into a Python process only. `curl` needs the variables in the shell:

```bash
set -a; . ./.env; set +a
```

Then `$N8N_URL`, `$N8N_ENRICHMENT_WEBHOOK_SECRET`, `$HUBSPOT_PRIVATE_APP_TOKEN` etc. are available.

- Use a **subshell** (`bash -c '...'`) or close the terminal afterwards if you would rather not leave
  credentials exported for the rest of the session.
- Verify without printing values: `[ -n "$N8N_URL" ] && echo N8N_URL set`. **Never `echo` a secret**,
  never paste one into a summary, a log, or a commit.

### Form 3 — Claude Desktop, Code tab

Several steps are conversational and have no command. They say so explicitly.

### Before ANY deploy command

**Confirm `N8N_EXPECTED_URL` is set.** API-created workflows land in the key owner's n8n project,
and a wrong key silently deploys into the wrong one. This has already cost a full deploy cycle once.

The deploy target is **`https://alexherman.app.n8n.cloud`** — confirmed 2026-07-31 as the correct
tenant. Pin it so the check is mechanical rather than remembered:

```bash
grep -q '^N8N_EXPECTED_URL=' .env || echo 'N8N_EXPECTED_URL=https://alexherman.app.n8n.cloud' >> .env
grep -c '^N8N_EXPECTED_URL=' .env    # expect exactly 1
```

**Why this is not optional.** `scripts/deploy_n8n_workflows.py::_instance_ok()` pins
`N8N_URL == N8N_EXPECTED_URL` **only when `N8N_EXPECTED_URL` is set**. Left unset it falls back to
`host.endswith(".n8n.cloud")`, which *any* n8n Cloud tenant satisfies — so the guard distinguishes
"is an n8n host" from "is not", but never "is the right tenant". Setting the variable converts that
fallback into an exact-match pin. Found during 23-06 Section A, 2026-07-31.

**Superseded wording:** earlier revisions of this runbook and of `23-OPERATOR-RUNBOOK.md` said the
key must be Robert's, with Alex's retained as `N8N_API_KEY_2`. **`N8N_API_KEY_2` does not exist**,
so that arrangement was never in place and the instruction was unfollowable. The tenant pin above
replaces it.

### Variables these steps use

`N8N_URL`, `N8N_API_KEY`, `N8N_EXPECTED_URL`, `N8N_ENRICHMENT_WEBHOOK_SECRET`,
`HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_EXPECTED_PORTAL_ID`, `TEST_COMPANY_IDS`, plus the
run-time switches you set inline: `DRY_RUN`, `ALLOW_N8N_DEPLOY`, `ENABLE_BAKED_FLAGS`.

---

## §0b — Readiness: what you can run today

| § | Plan | Runnable now? | Blocker |
|---|---|---|---|
| RB-1 | **25-01** lists-scope + chunk timing | ⚠ Probe B yes, Probe A **no** | Probe A's script `scripts/check_hubspot_list_scope.py` is built by 25-01 **Task 1**, which is autonomous and not yet run |
| RB-2 | **29-01** scheduled-routine host probe | ✅ **yes** | none — no dependencies, no code needed |
| RB-3 | **23-06** plugin install + armed create canary | ✅ **yes** | none — all scripts exist, canary CSV prepared |
| RB-4 | **27-05** dashboard same-URL check | ❌ | 27-05 Tasks 1–2 not built (27-02/03/04 in flight) |
| RB-5 | **28-02** n8n semantics live gate | ❌ | `scripts/probe_n8n_semantics.py` is built by 28-02 Task 1; **Phase 28 checker not yet run** |
| RB-6 | **28-04** five-triggers decision | ❌ | gated behind 28-02; decision only, no commands |
| RB-7 | **28-06** armed arm→dispatch→disarm canary | ❌ | gated behind 28-05 |
| RB-8 | **29-06** live notice gate | ❌ | gated behind 29-04/05 |
| RB-9 | **30-07** armed review canary | ❌ | gated behind 30-06 |

**Provisional sections.** RB-4 through RB-9 belong to phases whose `gsd-plan-checker` has **not**
run. Plans were written before their dependencies existed, and the checker has already caught one
stale target this milestone (27-01 aimed at the wrong workflow file). **Script names, subcommands
and flags in RB-4…RB-9 may change when their phase is checked.** Re-read the section against its
plan before running it.

**Highest leverage first:** RB-1 (25-01) unblocks 4 plans, RB-2 (29-01) unblocks 4 and has zero
dependencies. RB-3 (23-06) unblocks nothing — it is Phase 23's own proof.

---

## §0c — Global safety rules

These hold in every section below.

1. **Read-back is the proof, not exit code.** A deploy that reports success is not evidence the
   backend is armed or disarmed. Every armed window ends with a read-back that must pass.
2. **`enable_baked_flags()` cannot disarm.** It only widens disabled→enabled. **Disarming is
   redeploying the committed (disarmed) artifact.**
3. **An empty allowlist grants nothing while reporting success.** `_writeSafetyAllows()` opens
   `if (!allowedDomains.length && !allowedIds.length) return false;`. Arming without a
   `TEST_RECORD_IDS` / `TEST_RECORD_DOMAINS` entry is a no-op that looks like a success — and the
   deploy script refuses it outright, which is a **correct outcome to record**, not an obstacle.
4. **The allowlist is a gate, not a selector.** A domain allowlist permits writes to *any* record at
   that domain for the whole window. What bounds the write to one record is the one-row input.
5. **A re-send is a send.** Retry flows through the same armed dispatch path. **One fire per window.**
   If a fire is ambiguous, read the record and the executions list *before* firing again.
6. **Abort path:** anything unexpected while armed — ambiguous response, wrong record touched,
   unexpected execution count — **go straight to disarm + disarmed read-back**. Disarm first,
   diagnose after.
7. **A failure is recorded, not worked around.** Gaps route to `/gsd-plan-phase <n> --gaps --ws plugin-entrypoint`.
8. Never paste `$N8N_ENRICHMENT_WEBHOOK_SECRET`, `$N8N_API_KEY`, `$HUBSPOT_PRIVATE_APP_TOKEN` or any
   other credential into a summary, findings file, log, or commit.

---

# RB-1 · Plan 25-01 — Lists-scope probe, chunk timing, view decision

**Gates 25-03, 25-04, 25-06, 25-07.** Two live probes plus one decision. Neither probe writes to
HubSpot: the deployed `wf_enrichment_cloud.json` is the committed disarmed build, so its
write-safety constants are off and its `TEST_RECORD_*` allowlist is empty.

### Prerequisite — build Task 1 first

`scripts/check_hubspot_list_scope.py` **does not exist yet**. It is Task 1 of this plan and is
autonomous. Ask for 25-01 Task 1 to be built before starting; Probe A cannot run without it.

### Probe A — HubSpot Lists scope (free, read-only)

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/check_hubspot_list_scope.py', run_name='__main__')" "<name of a real company list in the portal>"
```

If the portal has no company list, run it against a deliberately nonsense name — **a 404 answers the
scope question, and a 403 answers it the other way.** Either is a result.

**Record:** the verdict, the HTTP status, and — if granted — the member count and whether a paging
cursor came back.

### Probe B — chunk timing (four timed POSTs)

Load the shell (Form 2), then confirm without printing:

```bash
set -a; . ./.env; set +a
[ -n "$N8N_URL" ] && [ -n "$N8N_ENRICHMENT_WEBHOOK_SECRET" ] && echo "env ok"
```

Pick test company ids from `TEST_COMPANY_IDS` in `.env`. Then:

```bash
# B1 — one record, NO providers (zero provider credits)
curl -o /dev/null -s -w 'B1 %{time_total}\n' -X POST "$N8N_URL/webhook/hubspot/enrichment/event" \
  -H "X-Enrichment-Secret: $N8N_ENRICHMENT_WEBHOOK_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"providers": [], "events": [{"objectId": "<id1>", "objectType": "companies"}]}'

# B2 — three records, no providers
curl -o /dev/null -s -w 'B2 %{time_total}\n' -X POST "$N8N_URL/webhook/hubspot/enrichment/event" \
  -H "X-Enrichment-Secret: $N8N_ENRICHMENT_WEBHOOK_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"providers": [], "events": [{"objectId": "<id1>", "objectType": "companies"}, {"objectId": "<id2>", "objectType": "companies"}, {"objectId": "<id3>", "objectType": "companies"}]}'

# B3 — five records, no providers
curl -o /dev/null -s -w 'B3 %{time_total}\n' -X POST "$N8N_URL/webhook/hubspot/enrichment/event" \
  -H "X-Enrichment-Secret: $N8N_ENRICHMENT_WEBHOOK_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"providers": [], "events": [{"objectId": "<id1>", "objectType": "companies"}, {"objectId": "<id2>", "objectType": "companies"}, {"objectId": "<id3>", "objectType": "companies"}, {"objectId": "<id4>", "objectType": "companies"}, {"objectId": "<id5>", "objectType": "companies"}]}'
```

`"providers": []` resolves server-side to no providers enabled — **zero provider credits.** These
three may still incur Anthropic research/judge spend on the order of a few cents per record.

```bash
# B4 — ONE record, FULL WATERFALL. This one burns real provider credits.
curl -o /dev/null -s -w 'B4 %{time_total}\n' -X POST "$N8N_URL/webhook/hubspot/enrichment/event" \
  -H "X-Enrichment-Secret: $N8N_ENRICHMENT_WEBHOOK_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"providers": ["lusha", "apollo", "zoominfo"], "events": [{"objectId": "<id1>", "objectType": "companies"}]}'
```

**B4 cost:** roughly 2 Lusha credits for a company match plus about 1 ZoomInfo credit, plus a few
cents of Anthropic spend. **B4 is the number the chunk default is actually derived from** — a preview
whose chunk plan was sized on the cheapest path will time out on the expensive one. Skip it only if
you accept a default sized on incomplete data, and say so in the findings.

**Watch for the ~100s Cloud response ceiling.** `wf_enrichment_cloud.json` has **no `Split In
Batches`** — every record runs the full provider+Haiku+Sonnet chain before the response fires. A 524
means you found the ceiling, which is itself the measurement.

**Derive:** `seconds_per_record` = worst case observed; `max_records_per_chunk = max(1, floor(60 / seconds_per_record))`.

### Decision — how a HubSpot "view" input is handled

INGEST-04 says "list, view, or record IDs". Research found **no discoverable public API** for
resolving a saved-view name to record ids. Pick one:

- **`refuse-and-redirect`** *(recommended)* — refuse a view input, point the operator at saving it as
  a list in HubSpot's own UI. INGEST-04 scopes down to lists + record ids. **This becomes accepted
  amendment #7**, applied to REQUIREMENTS.md and ROADMAP criterion 1 by plan 25-07.
- **`discovery-spike`** — budget open-ended discovery against an absence-of-evidence finding. Any
  endpoint found this way is likely internal/undocumented: trades a scope gap for a stability gap.
- **`treat-view-as-list`** — **rejected on its face** (25-RESEARCH.md Pitfall 2): a view name
  colliding with an unrelated list name enriches the wrong record set with no error. Listed only so
  the rejection is visible.

### Where the outcome is written

`phases/25-enrichment-lane-cost-guard/25-BLOCKERS.md`, with three sections:
`## Lists API scope` (verdict, HTTP status, date), `## Chunk timing` (each measured time with its
record count and provider selection, the derived worst-case seconds-per-record, the computed
`max_records_per_chunk`, and **explicitly whether B4 was run**), and `## View resolution` (chosen
option, date, one sentence of rationale, the exact operator-facing refusal sentence if
`refuse-and-redirect`, and which plan implements it — 25-03 backend, 25-04 client).

**No token, secret, or webhook URL-with-secret may appear in that file.**

---

# RB-2 · Plan 29-01 — Can a scheduled routine invoke this plugin's skill?

**Gates 29-03, 29-04 → 29-05 → 29-06 (all of Phase 29). No dependencies — runnable today.**
No commands beyond authoring one file. Nothing is armed and nothing is written.

**Read first:** `29-RESEARCH.md` §"Pattern 2" and §"Pitfall 2" — finding the config flag set to
`true` is **not** this task's answer. The flags (`coworkScheduledTasksEnabled`,
`ccdScheduledTasksEnabled`) are already known enabled; what is unverified is whether a routine can
reach *this plugin's* skill.

**Model to copy:** `~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md` — YAML frontmatter
with `name` and `description`, then a markdown instruction body.

### Task 1 — the host probe

1. Author a throwaway routine at `~/Documents/Claude/Scheduled/lv-sweep-probe/SKILL.md` whose **only**
   job is to invoke this plugin's read-only status capability (Phase 27's status skill, by whatever
   name 23-04/27 registered it) and print what came back.
2. Set the soonest cadence the UI allows. Let it fire once.
3. Record **three** things:
   - **Did it reach the plugin's skill at all?** yes / no / tried-and-errored — quote the error verbatim.
   - **Did real backend data come back**, or only a description of what it *would* have fetched?
     **A routine that narrates instead of calling is a NO.**
   - **Where did the output surface** — macOS notification banner, in-app inbox or badge, both,
     somewhere else — and roughly how much text rendered before truncation. This sets the ceiling
     29-05 formats against.
4. Delete the throwaway routine.

**If the first two answers are NO: stop. Do not work around it.** Report it as a blocked phase.
D-01's host does not exist and the correct next step is D-01b's named fallback (Managed Agents
`deployments`) — a different phase shape needing your decision, not a planner's workaround.

### Task 2 — unprompted mid-conversation report-back (bonus only)

In a Claude Desktop **Code tab** session, start something that takes visibly longer than one turn and
keep talking. Observe whether its completion arrives on its own as a new message without you asking
again.

Record exactly one of: **YES** (describe the mechanism), **NO**, or **INCONCLUSIVE**.
**INCONCLUSIVE is treated as NO** — an unverified capability and an absent one get the same
treatment, because the cost of being wrong is a watch that goes silent, which is what NOTICE-02
forbids. Nothing in 29-04 may be built such that it fails when this is NO.

### Where the outcome is written

`phases/29-notices-unattended-sweep/29-HOST-PROBE.md` (Section 2 is where RB-8 later expects the
notice to surface).

---

# RB-3 · Plan 23-06 — Plugin install + armed create canary

**Gates nothing** — Phase 23's own proof. Full narrative:
`phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-OPERATOR-RUNBOOK.md`. Commands repeated
here for completeness; that file governs on any discrepancy.

**Records touched:** exactly one, which does not exist yet —
`canary-23-06-20260731@australiagtm.com`. CSV prepared at `~/Desktop/lv-canary-23-06.csv`.
**Flags armed:** `ALLOW_HUBSPOT_RECORD_WRITES` **and** `ALLOW_HUBSPOT_CREATE`, allowlisted to
`TEST_RECORD_DOMAINS=australiagtm.com`. Arming `ALLOW_HUBSPOT_CREATE` is a **deliberate departure**
from 22-OPERATOR-RUNBOOK.md, which forbade it — Phase 23's entire goal *is* the create path.

### ⚠ Two defects found walking this runbook on 2026-07-31 — read before Section B

Both were found by the operator mid-window, and both were independently confirmed against the
committed artifacts and the live instance. **Section B is not safe to run as originally written.**

**Defect 1 — the read-back at Steps 1, 3b and 7 does not cover the lane being armed.**
`scripts/verify_live_write_safety.py` hardcodes one workflow (`ENRICHMENT_WORKFLOW_NAME`, line 60)
and two node names (`WRITE_DECISION_NODE_NAMES = ("Decide Action", "Decide Company Action")`, line
64), and takes no workflow argument. Confirmed coverage: **2 of the 9 `ALLOW_HUBSPOT_CREATE` sites
and 2 of the 8 `ALLOW_HUBSPOT_RECORD_WRITES` sites — and zero nodes in
`LV Contact Ingest (Cloud template)`**, whose gates are named `HubSpot Update Write Gate` and
`HubSpot Create Write Gate`. That is the lane this canary fires at.

Consequence: **a `VERDICT: disarmed PASS` at Step 7 is not evidence the contact lane is disarmed.**
Until the verifier is fixed, close the window by *also* confirming the contact lane directly:

```bash
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
import os, re, requests
base = os.getenv('N8N_URL','').rstrip('/'); key = os.getenv('N8N_API_KEY')
r = requests.get(f'{base}/api/v1/workflows', headers={'X-N8N-API-KEY': key}, timeout=30); r.raise_for_status()
for w in r.json()['data']:
    d = requests.get(f\"{base}/api/v1/workflows/{w['id']}\", headers={'X-N8N-API-KEY': key}, timeout=30).json()
    for n in d.get('nodes', []):
        for flag, val in re.findall(r'(ALLOW_HUBSPOT_[A-Z_]+)\s*=\s*\"(true|false)\"', n.get('parameters',{}).get('jsCode','') or ''):
            if val == 'true': print('ARMED:', w['name'], '|', n['name'], '|', flag)
print('scan complete — any ARMED line above means the window is still open')
"
```

Read-only. **Silence is the pass.** Any `ARMED:` line means the backend is still armed regardless of
what the verifier reported.

**Defect 2 — 23-01's create-gate fix is committed but not deployed.** Confirmed live 2026-07-31:
`LV Contact Ingest (Cloud template)` (`updatedAt` 2026-07-30) declares literals in only its two
write gates; the committed artifact also declares `ALLOW_HUBSPOT_CREATE` in `Decide Action`. So
**Step 3 would push 23-01's never-live-tested logic in the same action that arms writes**, leaving
"did the fix deploy" and "did arming work" inseparable if the canary misbehaves.

**Insert this between Step 2 and Step 3** — a disarmed deploy, then a read-back, so the fix lands
and is proven *before* anything is armed:

```bash
# Step 2b — deploy the committed (disarmed) artifacts, arming nothing
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# Step 2c — confirm 23-01's fix is now live AND everything is still disarmed
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
```

Then re-run the Defect-1 scan above and confirm `LV Contact Ingest`'s `Decide Action` now declares
`ALLOW_HUBSPOT_CREATE = "false"` — three CREATE sites in that workflow, not two. Only then proceed
to Step 3.

### Section A — install and invoke (read-only, gates Section B)

```bash
claude plugin validate ./operator-claude-plugin
claude --plugin-dir ./operator-claude-plugin
```

A2 install via the Desktop plugin manager, **no terminal** — this is the step that actually tests
PLUGIN-01. A3 natural-language trigger ("load these contacts into HubSpot") in a fresh session.
A4 `/operator-claude-plugin:contact-upload` in another fresh session — both must enter the same code
path. A5 confirm the **first** thing it says names the endpoint and states dispatch is disarmed,
*before* asking for a file. A6 clean refusal when unconfigured:

```bash
mv operator-claude-plugin/config/operator.local.json operator-claude-plugin/config/operator.local.json.bak
# invoke; confirm plain-language refusal, NO key shown, no raw socket error
mv operator-claude-plugin/config/operator.local.json.bak operator-claude-plugin/config/operator.local.json
```

A7 point it at the canary CSV, preview, then **decline** — confirm nothing was sent and it says so.

### Section B — the armed window

**Step 0.** In HubSpot, search `canary-23-06-20260731@australiagtm.com`. **It must not exist** — a
pre-existing contact turns a create test into an update test.

```bash
# Step 1 — disarmed baseline read-back → expect VERDICT: disarmed PASS
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed

# Step 2 — dry-run the deploy (arms nothing, shows the diff)
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# Step 3 — ARM
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,ALLOW_HUBSPOT_CREATE,TEST_RECORD_DOMAINS=australiagtm.com" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# Step 3b — ARMED read-back (required, distinct step) → expect VERDICT: armed PASS
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation armed --allowlist australiagtm.com
```

`ENABLE_BAKED_FLAGS` syntax: bare boolean kill switches take **no** `=value`;
`TEST_RECORD_DOMAINS=australiagtm.com` supplies the allowlist. Multiple values within one flag
separate with `|`, not `,` (`,` already separates entries in `ENABLE_BAKED_FLAGS` itself). A name
outside `_OVERLAYABLE_FLAGS` **raises** rather than silently enabling nothing. `VALUE` is rendered
with `json.dumps`, so it always lands as a quoted JS string literal and can never inject JS.

**Expected rewrite counts: create in 9 nodes, record-writes in 8** (contact ingest 3/2, enrichment
2/2, maintenance 4/4 — the two flags are declared in *different* subsets). A count of 0 for either
means the script refused and deployed nothing.

**If Step 3b does not pass, DO NOT FIRE.** Return to Step 3.

**Step 4 — fire exactly once, through the plugin** (Form 3, Desktop Code tab): point it at
`~/Desktop/lv-canary-23-06.csv`; confirm the preview shows 1 row and labels `Email Address → email`,
`First Name → firstname`, `Last Name → lastname`, `Company → company`; approve; arm the conversation
with the plugin's arming phrase; let it dispatch. **One dispatch. A second fire is a new window, not
a retry.**

<details><summary>curl equivalent — diagnosis only, if the plugin path fails</summary>

```bash
set -a; . ./.env; set +a
curl -sS -X POST "$N8N_URL/webhook/hubspot/contact-upload" \
  -H "X-Enrichment-Secret: $N8N_ENRICHMENT_WEBHOOK_SECRET" \
  -F "data=@$HOME/Desktop/lv-canary-23-06.csv;type=text/csv"
```

Using this **instead of** the plugin means Task 2 did not pass — it proves the backend, not the
client. Record it as a Section A failure and a Section B partial.
</details>

```bash
# Step 5 — read back the run, capture the execution id
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" list

# Step 6 — DISARM (a plain deploy pushes the committed, disarmed literals)
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# Step 7 — disarmed read-back → expect VERDICT: disarmed PASS
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
```

Then in HubSpot confirm a contact was **CREATED**. **A row landing in the review queue instead means
the 23-01 gate fix did not take effect** — record that as a 23-01 failure with the execution id; do
not retry and do not adjust the plugin to compensate. Also record the raw webhook response verbatim
(Phase 26 needs it) **without asserting it is a complete per-record ledger**.

**The window is not closed until Step 7 passes.** Step 8: delete or mark the canary contact.

### Where the outcome is written

`23-06-SUMMARY.md` and `operator-claude-plugin/CHANGELOG.md`.

---

# RB-4 · Plan 27-05 — Dashboard publishes to the same URL *(provisional)*

**Blocked:** 27-05 Tasks 1–2 must be built first. **Gates nothing.** Read-only throughout — nothing
here turns a workflow on or off, starts a run, or changes a record.

Entirely Form 3 (Desktop Code tab). No shell commands, except restoring config in step 6.

1. Ask for backend status. Confirm it arrives as **conversational text with no dashboard** — text is
   the default.
2. Ask for the dashboard. Confirm it publishes, carries the **same** workflows, counts and states as
   the text answer, and shows a fetch-time stamp.
3. Same conversation, ask for a refresh. **URL unchanged, stamp moved forward.**
4. **Brand-new conversation**, ask for the dashboard again. Confirm it lands on the **same URL** as
   step 2, not a second one. *This is the cross-session behaviour the stored identifier exists for
   and the only step that proves it.*
5. Confirm a provider whose balance the backend could not read shows as **unknown** — not a zero
   balance, not a healthy provider.
6. Set the expiry key in `operator-claude-plugin/config/operator.local.json` to **0** days, open the
   skill again, confirm the state file was removed and the next dashboard request mints a fresh
   identifier. **Restore the config afterwards.**
7. Confirm none of the above turned a workflow on or off, started a run, or changed a record.

**Resume signal:** "approved", or which step's behaviour differed.

---

# RB-5 · Plan 28-02 — n8n semantics live gate *(provisional)*

**Blocked:** `scripts/probe_n8n_semantics.py` is built by 28-02 Task 1, and **Phase 28's checker has
not run.** Subcommand names and the enabling env var below may change. **Gates 28-03, 28-04 → 28-05 → 28-06.**

**Precondition:** `N8N_URL` and `N8N_API_KEY` present, and `N8N_URL` matching `N8N_EXPECTED_URL` (or
a genuine `.n8n.cloud` host) — **the probe refuses otherwise and makes no call.**

`roundtrip` performs a **real PUT** (a genuine no-op: GET→PUT→GET changing nothing), which is why a
human runs it. Neither subcommand can touch a write-safety constant — the module has no code path
that writes one, asserted by a grep criterion in the plan.

### Task 2 — no-op round-trip (D-20) and execute-endpoint check (A2)

Get the live workflow id first:

```bash
set -a; . ./.env; set +a
curl -sS "$N8N_URL/api/v1/workflows" -H "X-N8N-API-KEY: $N8N_API_KEY" \
  | python3 -c "import sys,json; [print(w['id'], '|', w['name'], '| active:', w.get('active')) for w in json.load(sys.stdin)['data']]"
```

**Recommended target: `LV Scheduled Maintenance (Cloud)`** — its `settings` object is `{}` in the
committed JSON, so if any workflow round-trips cleanly it is this one.

```bash
# no-op round-trip — expect verdict "verified", settings and connections identical before/after
<PROBE_ENABLE_VAR>=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/probe_n8n_semantics.py', run_name='__main__')" roundtrip --workflow-id <ID>

# execute-endpoint check — expect 404 or 405, confirming D-05a
<PROBE_ENABLE_VAR>=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/probe_n8n_semantics.py', run_name='__main__')" execute_probe --workflow-id <ID>
```

- **A schema rejection naming additional properties means the four-key filter is wrong** and 28-01
  needs a fix before anything else in Phase 28 proceeds.
- **A `settings` mismatch** means research Open Question 3's community report applies to this
  instance — record exactly which nested key changed.
- Record the execute-endpoint status code **and response body verbatim**. `POST /workflows/{id}/execute`
  is expected not to exist (open, unmerged upstream PR #20304).
- Confirm the workflow's `active` state is unchanged from before — `roundtrip` restores the prior
  active state and this is the cheapest place to see that working for real.

### Task 3 — is the deactivate→PUT→activate bracket effective? (D-18 / A1)

**Precondition: Task 2's `roundtrip` returned `verified`.** A PUT that cannot round-trip cleanly
makes the reload observation meaningless.

1. Confirm `LV Scheduled Maintenance (Cloud)` is currently **active**. If inactive, the reload
   question does not apply — activation is itself the load event by n8n's documented model. Record
   the question as **unanswerable on this instance** rather than answered, and skip to step 5.
2. **Recommended target trigger: `Review Trigger (15 min)`** — its downstream write gate is disarmed
   so extra fires perform reads only, and its committed interval is `minutes`/15 so a short-interval
   change is a small delta. **Confirm the choice against current provider-credit headroom first.**

```bash
<PROBE_ENABLE_VAR>=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/probe_n8n_semantics.py', run_name='__main__')" cadence_reload --workflow-id <ID> --node "Review Trigger (15 min)"
```

3. Watch reported execution start times over the bounded polling window. **New spacing** → the
   bracket makes a Schedule Trigger change effective on a running instance; A1 answered and 28-03 can
   rely on it. **Old spacing for the whole window** → the bracket is insufficient and 28-03 needs a
   different mechanism, which is exactly what this probe exists to find out before an armed window
   depends on it.
4. **Confirm the restore.** The probe reports a separate verdict for putting the captured interval
   back; it **must** read `verified`. If it does not, restore by hand from the committed JSON's
   interval for that node **and say so plainly** — a probe that leaves a schedule changed is the
   failure mode D-05c warned about and is not to be quietly tidied.

This is deliberately **not** the cadence-as-one-shot-fire workaround D-05c rejected: nothing is made
to fire in place of a manual trigger, and it is a one-time human-supervised diagnostic, never an
operator-facing verb.

### Where the outcome is written

`phases/28-control-actions/28-FINDINGS.md` — for each of the three questions: what was run, what was
observed **verbatim**, and the resulting confidence. **State plainly where an answer is partial.**

---

# RB-6 · Plan 28-04 — Five triggers, one workflow: the per-job disable decision *(provisional)*

**Blocked** behind 28-02. **No commands — a decision.** Gates 28-05 → 28-06.

CONTROL-03 asks for "enable or disable a scheduled job", but `LV Scheduled Maintenance (Cloud)`
carries **five** Schedule Trigger nodes in one workflow. Workflow `active` state is workflow-wide —
deactivating it to disable one job stops all five, including the review poller and the stuck-lock
sweep. 28-CONTEXT.md's Deferred section says widening the mutation allowlist is a new requirement,
not a planning decision. That sentence is why this is yours.

- **`widen-by-one-field`** — permit the `disabled` boolean on an already-allowlisted Schedule Trigger
  node. CONTROL-03 satisfied as written; one boolean on a node the allowlist already names; trivially
  reversible; 28-03's field-level diff guard applies unchanged so the permitted difference stays
  exactly two fields on one node. Cost: it *is* a widening — CONTROL-05's allowlist wording needs
  updating to name it. **This is already recorded as accepted amendment #6 in HANDOFF.md §3.**
- **`refuse-per-job`** — workflow-level on/off and re-timing only. Allowlist stays exactly as
  REQUIREMENTS.md and ROADMAP describe it. Cost: CONTROL-03 only partly satisfied, requiring a
  REQUIREMENTS.md amendment recording the narrowing.

Either way the structural diff still refuses every other node, every connection and every settings
change, and read-back verification is unchanged.

**Note the tension:** HANDOFF.md §3 already lists `widen-by-one-field` as accepted amendment #6. If
you now choose `refuse-per-job`, amendment #6 must be **revoked in HANDOFF.md**, not left standing
alongside the opposite decision.

---

# RB-7 · Plan 28-06 — Armed arm→dispatch→disarm canary *(provisional)*

**Blocked** behind 28-05. Phase 28 exit gate. **This is the only point in Phase 28 where a real
write-safety constant is set to its enabled literal on the live instance**, bounded by a
`TEST_RECORD_*` allowlist to a single record. Every automated test behind it ran against a stubbed
transport.

**Precondition:** `N8N_URL`, `N8N_API_KEY` and the plugin's operator config all present, and a
disposable HubSpot test record whose id or email domain will be the **entire** content of the arming
allowlist.

1. **Pick the lane.** Prefer the enrichment lane with a single HubSpot object id in the record
   allowlist if Phase 25's enrichment dispatch is built; otherwise the contact lane with a single
   disposable email domain. **Note which was used.**
2. **Record the flag state BEFORE**, read through Phase 27's status surface — **not** from local
   config (D-04). Every declaration in the target workflow must read disabled.
3. Run the action **conversationally through the skill**, as an operator would. Confirm that before
   any confirmation is given, the consequence names what live writes permit **and** names the single
   record the grant is bounded to. **Decline once**, and confirm nothing was sent — the decline path
   is as important as the accept path and cheaper to test here than anywhere else.
4. Run again and confirm. Watch three things: **arm read-back verified**, **dispatch landing**,
   **disarm read-back verified**. **Note the wall-clock duration of the armed window** — the ~100s
   n8n Cloud webhook response ceiling bounds how long an arm→dispatch→disarm cycle can hold the flag
   open, and this measurement says whether that bound is comfortable or tight.
5. Confirm the write happened in HubSpot **for the allowlisted record**, and that **no other record
   was touched.** The record allowlist is the phase's strongest safety property and this is the only
   place it can be observed working.
6. **Confirm the plugin's API-side arm wrote the SAME literal shape the deploy script's overlay
   writes.** Fetch the workflow and compare the declaration text against `_OVERLAY_FLAG_SPEC`'s
   enabled literal. A cosmetic difference means two conventions exist and Phase 27's reader will
   eventually disagree with Phase 28's writer.
7. **Read the flag state AFTER through Phase 27's status surface** — every declaration must read
   disabled. Then the belt-and-braces close-out this repo's armed windows always end with:

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
```

Then re-read through the status surface once more.

### Where the outcome is written

`phases/28-control-actions/28-CANARY-LOG.md`: the lane, the allowlist content, the before state, each
verdict, the armed-window duration, the HubSpot outcome, the literal-shape comparison, the after
state. **Record any step that did not behave as described, verbatim.**

---

# RB-8 · Plan 29-06 — Live notice gate *(provisional)*

**Blocked** behind 29-04/05. Phase 29 exit gate. Read-only — no arming, no writes.

**Read first:** `SCHEDULED-ROUTINE-TEMPLATE.md` (Task 1's output), and `29-HOST-PROBE.md` Section 2
from RB-2, so a notice arriving somewhere *else* is recognised as a finding rather than missed.

1. **Install:** copy `SCHEDULED-ROUTINE-TEMPLATE.md` to `~/Documents/Claude/Scheduled/<name>/SKILL.md`
   and enable it.
2. **Silence check FIRST.** Backend healthy, let it fire at least once. Confirm **nothing** arrives.
   **A heartbeat, an all-clear, or an empty report all FAIL this check** — NOTICE-04 requires silence,
   and a sweep that speaks when healthy is one the operator learns to ignore.
3. **Notice check.** Make one condition genuinely true. **Cheapest safe lever: set the review-backlog
   threshold below the current real backlog count**, so the condition fires on real data without
   changing anything in the backend. **Do NOT manufacture a condition by breaking a credential or
   arming the backend** — the sweep is being tested, not the backend's failure modes.
4. Let it fire. Confirm the notice: arrives **in the place 29-01 recorded**; is legible at the
   observed length ceiling; states the cause in plain language; states whether the operator or an
   admin can act; and **contains no instruction to run a command or open a terminal.**
5. **Restore the threshold** to its documented default.
6. Confirm from n8n's execution history and the provider credit balances that the sweep's firings
   performed **no write** and consumed **no provider credits.** The import-graph guard proves no code
   path exists; this proves none was taken.

```bash
set -a; . ./.env; set +a
curl -sS "$N8N_URL/api/v1/executions?limit=20" -H "X-N8N-API-KEY: $N8N_API_KEY" \
  | python3 -c "import sys,json; [print(e['id'], e.get('workflowId'), e.get('startedAt'), e.get('status')) for e in json.load(sys.stdin)['data']]"
```

Record all six results in `29-06-SUMMARY.md`, **including anything that surfaced differently from what
29-01 predicted.**

---

# RB-9 · Plan 30-07 — Armed review canary *(provisional)*

**Blocked** behind 30-06. Phase 30 exit gate. One record is the **entire blast radius.**

1. Choose **ONE** HubSpot test company currently flagged for review and holding a stored review
   candidate. Note its record id.

```bash
# 2 — capture the before state
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/canary_record_snapshot.py', run_name='__main__')" snapshot --label 30-07-review-canary --company-id <RECORD_ID>

# 3 — deploy ARMED for review writes only, one record in the allowlist
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_REVIEW_WRITES,TEST_RECORD_IDS=<RECORD_ID>" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

**Confirm a non-zero rewrite count for the flag.** Zero means it refused and deployed nothing.

4. **Activate** the review-decision workflow in n8n Cloud.
5. From a Claude session with the plugin installed: open the review queue, confirm the chosen record
   appears with its conflict rendered in plain language and any protected field labelled.
6. **Without arming review writeback in the conversation**, take a decision to the point of the
   exact-write display. Confirm the plugin shows the property write **and states nothing was sent.**
7. Arm review writeback for the conversation and **REJECT** with a short reason. Confirm the plugin
   reports verified. In HubSpot confirm the review reason holds your text **and the record is STILL
   in the queue** — needs-review flag and stored candidate unchanged.
8. **APPROVE** the same record with a short reason. Confirm: verified; the candidate's values are now
   on the record; review flags cleared; the provenance blob has an entry per applied field naming a
   **human** source, `human_approved` status, timestamp and your reason — **with the previously
   recorded machine source still readable in that entry**, and **provenance entries for untouched
   fields intact.**

```bash
# 9 — redeploy DISARMED, then deactivate in n8n Cloud
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed

# 10 — compare against the step-2 snapshot
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/canary_record_snapshot.py', run_name='__main__')" compare --snapshot <PATH_FROM_STEP_2>
```

Then read the deployed workflow back from the n8n API and confirm the review-write constant is in its
**disabled** form on the live instance. **A deploy that reports success is not evidence; the read-back
is.**

**If any step writes to a record other than the chosen one, STOP and report it — that is a gate
failure, not a variance.**

Record in `30-07-SUMMARY.md`: the record id, both outcomes, the observed property changes, and the
confirmed disarmed state.

---

## Resume signals — what to reply with

| § | Plan | Reply with |
|---|---|---|
| RB-1 | 25-01 | Probe A verdict + HTTP status; the four `time_total` values; whether B4 (full waterfall) was run; the view decision |
| RB-2 | 29-01 | The three Task-1 observations (or "blocked" + verbatim error); Task 2 as YES/NO/INCONCLUSIVE |
| RB-3 | 23-06 | A1–A7 observed; the armed and disarmed verdicts; whether HubSpot shows a **created** contact; raw webhook response; execution id |
| RB-4 | 27-05 | "approved", or which step's behaviour differed |
| RB-5 | 28-02 | "approved" + roundtrip verdict + settings/connections comparison + execute-endpoint status code; then execution spacing + restore verdict + 28-FINDINGS.md written |
| RB-6 | 28-04 | `widen-by-one-field` or `refuse-per-job` |
| RB-7 | 28-06 | "approved" + both read-back verdicts + armed-window duration + only-allowlisted-record confirmation + disarmed-after-redeploy confirmation |
| RB-8 | 29-06 | The six results |
| RB-9 | 30-07 | "approved" + the record id + the confirmed disarmed read-back |
