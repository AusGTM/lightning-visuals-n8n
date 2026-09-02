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
run-time switches you set inline: `DRY_RUN`, `ALLOW_N8N_DEPLOY`, `ENABLE_BAKED_FLAGS`,
`ALLOW_N8N_PROBE` (RB-5), `ALLOW_N8N_ARM` (RB-7).

### Gating is uniform — one rule, everywhere (D-34)

Every dangerous capability in this repo sits behind exactly one `ALLOW_*` environment variable, and
they all behave identically:

- The value must read **exactly `true`**. `1`, `yes`, `TRUE`, `True` and empty all refuse.
- The check runs **before any transport is constructed**, so a missing gate costs zero HTTP calls.
- The refusal names the variable and says an admin sets it.

Current set: `ALLOW_N8N_DEPLOY`, `ALLOW_N8N_PROBE`, `ALLOW_N8N_ARM`, `ALLOW_HUBSPOT_CREATE`,
`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_PROPERTY_WRITES`, `ALLOW_WEB_RESEARCH`,
`ALLOW_JUDGE_ESCALATION`, `ALLOW_LUSHA_PROBE`, `ALLOW_CANONICAL_WRITES`.

**`ALLOW_N8N_ARM` gates arming only — never disarming.** A kill switch that could block a disarm
would strand an armed backend, which is the failure mode this entire ceremony exists to prevent.

---

## §0b — Readiness: what you can run today

**Re-swept 2026-07-31, evening.** Suite now: **1635 pytest / 6 skipped, 506 node / 0 fail,
760 plugin**. Every `n8n/*.json` disarmed (8 files, grep → 0). Remaining plans without a SUMMARY:
28-05, 28-06, 29-01, 29-03…06, 30-07 — all human-gated or chained behind a gate.
*(The 11:00 sweep read 1214/474/414 and 24 of 43 built; kept here so a mid-day snapshot of this
file is not mistaken for drift.)*

| § | Plan | Runnable now? | Blocker |
|---|---|---|---|
| ~~RB-1~~ | ~~**25-01** lists-scope + chunk timing~~ | ✅ **DONE** | Probe A granted 2026-07-31; **B4 ran 2026-08-03: 37.44 s full waterfall, ceiling 2 CONFIRMED**. The oversize-refusal live check found the deployed enrichment workflow predates the committed list lane — folded into the disarmed-redeploy remediation (three reasons now). **Deploy DONE 2026-08-03**: list lane live, refusal verified verbatim, backend-status + review-decision workflows created. Fully closed |
| ~~RB-2~~ | ~~**29-01** scheduled-routine host probe~~ | ✅ **ANSWERED 2026-08-03** | Host AMENDED (D-01) to cron/launchd → `claude -p` headless; Cloud Routines fail twice, harness cron is session-only. Verdicts in `29-HOST-PROBE.md` (§A2 is NO) |
| ~~RB-3~~ | ~~**23-06** install + armed create canary~~ | ✅ **PASSED 2026-08-03** | Contact 342770428400 created by run 1129, window closed with disarmed PASS. Found + fixed live: the stored-vs-running reload gap (ceremonies now bounce) and BUG 27 (create gate read fields Decide Action never emits). **Phase 23 COMPLETE** |
| ~~RB-4~~ | ~~**27-05** dashboard same-URL check~~ | ✅ **APPROVED 2026-08-03** | All steps pass; Phase 27 CLOSED, STATUS-05 checked. Found + fixed live: a session delivering the dashboard as a file attachment instead of publishing the Artifact |
| ~~RB-5~~ | ~~**28-02** n8n semantics live gate~~ | ✅ **DONE 2026-07-31** | Ran live against `1fXPuIabz3RsAHgn`. Round-trip `verified`, execute endpoint `405`, cadence reload confirmed on a running instance. Results in `28-FINDINGS.md`. **28-03 and 28-04 are built and committed as a result.** Nothing left here |
| ~~RB-6~~ | ~~**28-04** five-triggers decision~~ | **withdrawn** | Already decided — D-25 / amendment #6. Checkpoint deleted, plan now autonomous. **Nothing for you to do.** |
| RB-7 | **28-06** armed arm→dispatch→disarm canary | ✅ **YES — this is the next gate** | 28-05 shipped. Lane/workflow/record all resolved and preconditions checked 2026-08-03 — see RB-7's header table. Needs `ALLOW_N8N_ARM=true` in the invoking shell, and a plugin refresh first (cached SKILL.md files are stale) |
| RB-8 | **32-02** live notice gate — wrapper re-run | ✅ YES — this is the exit gate | 32-01 shipped the LLM-free `lv-sweep-run.sh` trigger; this is RB-8's re-run against it, comparable step-by-step to the 2026-08-03 FAIL under `claude -p` |
| RB-9 | **30-07** armed review canary | ❌ | behind 30-05/30-06 (30-01…04 built). Now needs `ALLOW_REVIEW_SUBMIT`; **four changes — read RB-9's header block** |
| RB-10 | **33-04** durable state release gate — real migration | ✅ YES — this is the exit gate | Plugin `0.7.0` committed (33-04). Answers Research Open Question 1 live: does writing into `~/.claude/plugins/data/<id>/` raise a "sensitive location" permission prompt? Not reproduced during research — MEDIUM confidence, settled here by observation |

**Nine gates remain**, not ten — RB-6 is withdrawn. Two are partially done (RB-3's Section A,
RB-4's plan built to its checkpoint).

**What unblocks the most, in order:** **RB-2 (29-01)** releases four plans and is now the single
highest-leverage gate left — RB-5 was run on 2026-07-31 and its four (28-03/04/05/06) are already
moving. **RB-1 (25-01)** drops the PROVISIONAL label off the chunk ceiling everywhere it appears.
**RB-3 and RB-4 unblock nothing** — each is its own phase's proof.

**Provisional sections.** RB-9 belongs to phase 30, whose `gsd-plan-checker` has **not** run.
**Script names, subcommands and flags there may change.** Re-read against the plan before running.
RB-8 now points at plan 32-02, not 29-06 — its provisional marker is dropped below.

RB-5 and RB-7 are **no longer provisional** — Phase 28 was checked twice on 2026-07-31 (5 blockers
then 1, all repaired) and its commands here are current. RB-6 is withdrawn entirely.

That checking caught real staleness both times, which is why it happens immediately before a phase
executes rather than at planning time: 27-01 aimed at the wrong workflow file, and Phase 28's plans
were written against Phase 27's research doc rather than the code Phase 27 shipped.

**Highest leverage first:** RB-1 (25-01) unblocks 4 plans, RB-2 (29-01) unblocks 4 and has zero
dependencies. RB-3 (23-06) and RB-4 (27-05) unblock nothing — each is its own phase's proof.

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

### Probe A — HubSpot Lists scope (free, read-only) · ✅ **script BUILT 2026-07-31, ready to run**

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/check_hubspot_list_scope.py', run_name='__main__')" "<name of a real company list in the portal>"
```

**No company list to hand? A nonsense name answers the question just as well:**

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/check_hubspot_list_scope.py', run_name='__main__')" "no-such-list-20260731"
```

Optional second positional argument is the object-type id — `0-2` companies (default), `0-1` contacts.

**How to read the verdict:**

| Result | Means |
|---|---|
| **200** | granted — plus a follow-up line with `member_count=` and `has_paging_cursor=` |
| **404** | **granted.** The request was authorized; only the *name* missed |
| **403** | **denied** — the credential lacks `crm.lists.read` |
| 401 / 5xx / timeout | neither; exits 2. Not an answer — re-run |

**Run it through the wrapper.** With `HUBSPOT_PRIVATE_APP_TOKEN` unset the script prints
`skipped (no credentials)` and states explicitly that this is **NOT a scope verdict** — verified.
It makes zero HTTP calls in that state, so a bare `python scripts/...` cannot produce a
silent false "denied".

Every run also prints that it settles the **Lists API only** — saved views are a different concept
with no public API, and this probe does not speak to them.

**Record:** the verdict, the HTTP status, and — if granted — the member count and whether a paging
cursor came back.

### ⚡ Probe B is now PARTLY PRE-ANSWERED — read this before spending credits

Plan **29-02 measured enrichment run durations on 2026-07-31**, read-only and free, from
`/api/v1/executions` on the live tenant. Full detail in
`phases/29-notices-unattended-sweep/29-TIMING.md`. What it establishes:

| Measured | Value | Basis |
|---|---|---|
| Max single-run duration | **38.9 s** | n=5, company lane |
| Max seconds-per-record | **36.1 s** | n=2 (only 2 runs carried a recoverable record count) |
| Headroom rate used downstream | **45 s/record** | observed max + ~25% |

**What this implies before you run anything:** at ~36 s/record, a **3-record** POST lands near
**108 s** — already past the ~100 s Cloudflare ceiling — and the full-waterfall case (B4) is
slower still. So the answer is very likely `max_records_per_chunk` of **1 or 2**, and **B3 (five
records) is likely to 524 rather than return a timing.** That is a useful result, not a failure —
but expect it rather than treating it as a fault.

**What it does NOT answer, and why B1–B4 are still worth running:**
- Every measured run is **single-record, company-lane**. Linearity at N>1 is *extrapolated*, and
  the whole point of B2/B3 is to test exactly that.
- None of the measured runs is a **full waterfall**. B4 remains the only source for the expensive
  path, which is the one the chunk default must survive.

**Cheapest sequencing given the above:** run **B1** (confirm ~36 s reproduces), then **B4** (the
number that actually sets the default). Run B2/B3 only if you want the linearity curve — and if B3
524s, record that as the ceiling being found, which is itself the measurement.

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

**Derive** with the method the shipped artifacts use (not the earlier `floor(60/s)` line, which
disagreed with every artifact carrying the number): worst case observed + 25% headroom, against the
~100 s ceiling — `max_records_per_chunk = max(1, floor(100 / (worst_case * 1.25)))`.

> **✅ B4 RAN — 2026-08-03.** One full-waterfall record (lusha+apollo+zoominfo): **37.44 s,
> HTTP 200**. Worst case 37.44 → +25% = 46.8 → floor(100/46.8) = **2, CONFIRMED**. PROVISIONAL is
> stripped from every artifact carrying the ceiling; B2/B3 can only lower per-record time, so they
> cannot move the ceiling and are not required.
>
> **The same-day oversize-refusal check FOUND A DEPLOY GAP instead:** the live enrichment workflow
> answered `[{"object_type":"unsupported","remaining_credits":[]}]` to a list envelope — the exact
> T-25-16 signature of a workflow with NO list-expansion node. **The deployed enrichment workflow
> predates the committed list lane.** The whole list lane (and its oversize refusal) is unreachable
> live until a disarmed redeploy, which the tenant now needs for THREE reasons: this, the
> backend-status 404, and 23-01's undeployed create gate. One deploy fixes all three; re-run the
> refusal check after it.

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
Nothing is armed and nothing is written.

> **✅ The routine is already written — you do not author anything.** It ships at
> `phases/29-notices-unattended-sweep/probe/`, with a README that assumes nothing about whose
> machine it runs on. **Follow that README**, not the "author a routine" wording below, which
> describes work already done.
>
> **The operator is not on the development machine**, so the probe folder covers the install too:
> the plugin now has a marketplace manifest, so
> `/plugin marketplace add <repo>` then `/plugin install operator-claude-plugin@lightning-visuals-operator`
> works on a fresh machine. **Run `/operator-claude-plugin:backend-status` once before scheduling
> anything** — if it does not resolve, the probe returns NO for a trivial reason and the cycle is
> wasted.
>
> **Why this one cannot be automated:** a routine's cadence lives in the app's IndexedDB, not in
> any file — verified, the routines folder holds `SKILL.md` and nothing else. There is no terminal
> path to schedule one or make it fire, and the deliverable is a UI observation (did a banner
> appear, was the output truncated) regardless.

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

### ⚠ One outstanding defect found walking this runbook on 2026-07-31 — read before Section B

Three defects were found by the operator mid-window. **Two of them were in
`scripts/verify_live_write_safety.py` and are FIXED** (plan 23-07): the read-back no longer names one
workflow and two nodes — it discovers every node in every deployed workflow that declares a
write-safety constant — and the armed expectation now takes an explicit `--expect-armed` set, so a
backend armed as Step 3 arms it yields `armed PASS` instead of a guaranteed FAIL. The all-workflow
shell workaround that used to live here is gone: the verifier does that scan itself, and prints its
own coverage line. The third defect below is unrelated and still stands.

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

Step 2c's own report now lists every declaring node it found, grouped by workflow. Read it and
confirm `LV Contact Ingest (Cloud template)`'s `Decide Action` appears with
`ALLOW_HUBSPOT_CREATE='false'` — three CREATE sites in that workflow, not two. Only then proceed to
Step 3.

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
# (covers EVERY declaring node in EVERY deployed workflow — the contact lane included.
#  Read the `coverage:` line: a scan finding zero declaring nodes FAILS, it never passes.)
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed

# Step 2 — dry-run the deploy (arms nothing, shows the diff)
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# Step 3 — ARM
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,ALLOW_HUBSPOT_CREATE,TEST_RECORD_DOMAINS=australiagtm.com" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# Step 3b — ARMED read-back (required, distinct step) → expect VERDICT: armed PASS
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation armed --allowlist australiagtm.com --expect-armed ALLOW_HUBSPOT_RECORD_WRITES,ALLOW_HUBSPOT_CREATE
```

`--expect-armed` names exactly what Step 3 armed. It is **symmetric, not a filter**: every
write-enabling boolean you do *not* name — here `ALLOW_HUBSPOT_REVIEW_WRITES` — is still asserted
disabled in every declaring node of every deployed workflow. Omitting the argument means record
writes alone, which would FAIL this window (create is armed), so a forgotten flag is a stricter
verdict, never a permissive one. An empty allowlist is its own reported finding: `_writeSafetyAllows()`
returns false on empty, so it would grant nothing while every flag read `true`.

`ENABLE_BAKED_FLAGS` syntax: bare boolean kill switches take **no** `=value`;
`TEST_RECORD_DOMAINS=australiagtm.com` supplies the allowlist. Multiple values within one flag
separate with `|`, not `,` (`,` already separates entries in `ENABLE_BAKED_FLAGS` itself). A name
outside `_OVERLAYABLE_FLAGS` **raises** rather than silently enabling nothing. `VALUE` is rendered
with `json.dumps`, so it always lands as a quoted JS string literal and can never inject JS.

**Do not trust a memorised rewrite count — derive it.** The counts grow every time a plan adds a
write gate, and a stale number in a runbook makes a *correct* deploy look like a misfire. **Derive
the expected counts from the committed artifacts immediately before you deploy:**

```bash
python3 -c "
import json, glob, re
from collections import Counter
c = Counter()
for f in sorted(glob.glob('n8n/wf_*.json')):
    for n in json.load(open(f)).get('nodes', []):
        code = n.get('parameters', {}).get('jsCode', '') or ''
        for flag, _ in re.findall(r'(ALLOW_HUBSPOT_[A-Z_]+)\s*=\s*\"(?:true|false)\"', code):
            c[flag] += 1
for k, v in sorted(c.items()): print(f'{k}: {v}')
"
```

**As of 2026-07-31 that prints `CREATE: 11, RECORD_WRITES: 10, REVIEW_WRITES: 10` across 11 distinct
nodes** — up from 9/8 earlier the same day, because 30-01 added the review constant to 8 nodes and
30-02 added a whole review workflow. **The flags sit in different subsets**, so the numbers are not
expected to match each other.

**A count of 0 for a flag you asked to arm means the script refused and deployed nothing.**

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
# This verdict now covers the contact lane's own write gates, so it IS evidence the lane
# this canary fired at is disarmed. No separate all-workflow scan is needed any more.
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

# RB-4 · Plan 27-05 — Dashboard publishes to the same URL

**READY.** 27-05 Tasks 1–2 are built (`27-05-SUMMARY.md` on disk); this is Task 3, the last step in
Phase 27. **Gates nothing.** Read-only throughout — nothing here turns a workflow on or off, starts
a run, or changes a record.

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

# RB-5 · Plan 28-02 — n8n semantics live gate

**READY.** `operator-claude-plugin/scripts/probe_n8n_semantics.py` **exists** (28-02 Task 1, `type="auto"`,
built) and Phase 28's checker **has** run — twice, 2026-07-31. **Gates 28-03, 28-04 → 28-05 → 28-06.**

> **The commands below were corrected 2026-07-31 — the previous ones could not run.** All three named
> `scripts/probe_n8n_semantics.py` (the module lives under `operator-claude-plugin/scripts/`, so the
> paste died on `FileNotFoundError`) and passed `--workflow-id <ID>`, which argparse rejects —
> `workflow_id` is **positional**, and `cadence_reload`'s node name is a **second positional**. The
> dotenv wrapper is also unnecessary here: this module takes credentials from
> `config_gate.load_config()` and **has never read `N8N_URL` from the shell**. Verified by running
> each corrected form with the gate **off** — it refuses and makes no call.

**Precondition:** the plugin's own config supplies the instance URL and key via
`config_gate.load_config()` — **not** shell `N8N_URL`/`N8N_API_KEY`. A missing or mismatched config
makes the probe refuse with `"verdict": "refused"` **before any transport is constructed**. The
`.env` shell vars are still used by the id-listing `curl` in Task 2, which is a separate command.

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
ALLOW_N8N_PROBE=true python3 operator-claude-plugin/scripts/probe_n8n_semantics.py roundtrip <ID>

# execute-endpoint check — expect 404 or 405, confirming D-05a
ALLOW_N8N_PROBE=true python3 operator-claude-plugin/scripts/probe_n8n_semantics.py execute_probe <ID>
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
ALLOW_N8N_PROBE=true python3 operator-claude-plugin/scripts/probe_n8n_semantics.py cadence_reload <ID> "Review Trigger (15 min)"
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

# RB-7 · Plan 28-06 — Armed arm→dispatch→disarm canary

**UNBLOCKED** — 28-05 shipped. Phase 28 exit gate. **This is the only point in Phase 28 where a real
write-safety constant is set to its enabled literal on the live instance**, bounded by a
`TEST_RECORD_*` allowlist to a single record. Every automated test behind it ran against a stubbed
transport.

### What was resolved before you start (2026-08-03, read-only)

The choices this section left open are now made, and the preconditions an agent can check have been
checked. Nothing below was armed, deployed, or written.

| Item | Resolved value | How it was established |
|---|---|---|
| Lane | **enrichment** (step 1's preferred branch — Phase 25's dispatcher shipped) | `enrichment.dispatch_enrichment` present |
| Target workflow | **`950HPb7a1GgSAIyZ`** — `LV Enrichment (Cloud template)`, `active=true` | live `GET /api/v1/workflows` |
| Record allowlist | **`9604614548`** (one HubSpot **company** id) — the same test company Probe B4 and the Phase 22 canary used | 25-BLOCKERS.md B4, 23-07-SUMMARY |
| `allow_create` | **false** — this is an update to an existing company, not a create | — |
| Flag state BEFORE | **all five workflows disarmed**: `ALLOW_HUBSPOT_RECORD_WRITES='false'`, `ALLOW_HUBSPOT_CREATE='false'`, `ALLOW_HUBSPOT_REVIEW_WRITES='false'`, `TEST_RECORD_IDS=''`, `TEST_RECORD_DOMAINS=''` (2n on enrichment, 4n on maintenance, 3n create-nodes on contact ingest) | live read via `n8n_read.read_write_safety` |
| `control` capability | **passes** against the installed `operator.local.json` | `config_gate.require_capability(cfg, "control")` |
| Step 6's expected literal | plugin `_render_literal(True)` → `"true"`; deploy `_OVERLAY_FLAG_SPEC` enabled literal → `"true"`. **Identical by construction** — step 6 confirms it live, it is not expected to differ | source comparison |

**The reload gap does NOT bite here.** `n8n_control.apply_mutation` brackets its PUT with
deactivate → PUT → restore-prior-active, and `LV Enrichment` is active, so the arm's activate is what
forces the running instance to reload the armed content — *before* its verify GET. The disarm goes
through the same bracket. This is the path that was already correct on 2026-08-03; it was
`deploy_n8n_workflows.py` (which never activates) that was not.

**Expect one gap in the surface.** `plan_action(kind="arm_dispatch")` composes the proposal but does
**not** build the dispatch — `execute_action` calls `proposal["dispatch_fn"]`, and neither
`control_actions.py` nor `backend-control/SKILL.md` says who sets it. The plugin session's agent has
to wire it. That is a real finding about the shipped surface; **record it in the canary log** rather
than treating it as a mistake in this section. The wiring, for reference:

```python
import control_actions, enrichment, config_gate
cfg = config_gate.load_config()
envelope = enrichment.build_envelope(
    {"record_ids": ["9604614548"], "object_type": "companies"},
    enrichment.resolve_providers(None, cfg))
proposal = control_actions.plan_action(
    {"kind": "arm_dispatch", "workflow_id": "950HPb7a1GgSAIyZ",
     "record_ids": ["9604614548"], "record_domains": [], "allow_create": False}, cfg)
# show proposal["consequence"] — then, ONLY on an explicit yes:
proposal["dispatch_fn"] = lambda: enrichment.dispatch_enrichment(envelope, True, cfg)
result = control_actions.execute_action(proposal, "yes", cfg)
```

**Cost of one pass:** ~37 s of dispatch (B4's measured full waterfall), ~$0.07 Anthropic, and the
enrichment lane's provider credits for one company (Lusha 2 cr/company).

**Precondition:** the plugin's `operator.local.json` carries the `control` capability's keys
(`n8n_url`, `n8n_api_key`); `N8N_EXPECTED_URL` is set and matches; **`ALLOW_N8N_ARM=true` is set for
the invoking shell**; and a disposable HubSpot test record exists whose id or email domain will be
the **entire** content of the arming allowlist.

The plugin reads credentials from `operator.local.json` only — **never** from `N8N_URL` /
`N8N_API_KEY` shell variables. The deploy-script steps below are the exception: `deploy_n8n_workflows.py`
is a repo script and does read the shell environment.

**`ALLOW_N8N_ARM` must be on the same command line as the arming call.** `_arm_gate()` reads
`os.environ` inside the process that arms, and in this setup **each `!` line is its own shell** — an
`export` on one line is gone by the next. Prefix the invocation instead:
`ALLOW_N8N_ARM=true python3 -c "..."`. An `export` in a previous line produces the refusal
"`ALLOW_N8N_ARM` is not set to exactly 'true' (it reads None)", which reads like a missing variable
rather than a lost shell.

**On `ALLOW_N8N_ARM` (D-34):** it gates arming and **not** disarming, so unsetting it mid-window can
never trap you with an armed backend. Unset it again as soon as the window closes — it is the gate
that still holds if an agent, a test harness, or a scheduled routine reaches the arming module by a
path nobody anticipated.

0. **Refresh the installed plugin first — and read the two traps below, both hit live on
   2026-08-03.** The plugin cache at
   `~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/0.1.0/` must match
   HEAD before the canary runs, or it drives a surface other than the one that is committed.

   **Trap 1 — reinstalling the plugin does NOT refresh the marketplace.** The plugin is copied from
   a *separate* clone at `~/.claude/plugins/marketplaces/lightning-visuals-operator`, and that clone
   never fetches on a plugin reinstall. It sat at `a60e3da` (28-05) for five commits while every
   uninstall/reinstall faithfully re-copied the same stale snapshot. **`plugin.json`'s
   `"version": "0.1.0"` is hand-written and has never been bumped, so the version number cannot tell
   you whether the content is current — verify by content, never by version.** Update the
   marketplace first; the clone is shallow, so a plain `pull` tends to fail where this works:

   ```bash
   git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator fetch --depth=1 origin master \
     && git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator reset --hard FETCH_HEAD
   ```

   **Trap 2 — the reinstall DELETES `config/operator.local.json`.** Not orphans it (that is the
   known version-bump behaviour) — *deletes* it, on a same-version reinstall, leaving only
   `operator.local.example.json`. **Back the file up before every reinstall.** On 2026-08-03 it was
   recoverable only because an equivalent gitignored copy happened to exist at
   `operator-claude-plugin/config/operator.local.json` in the repo checkout; the tuning keys the
   operator had added to the cache copy (`enrichment_providers`, `max_records_per_chunk`,
   `dashboard_artifact_ttl_days`, `hubspot_portal_id`) were not in it and had to be re-supplied.

   Then confirm by content: `skills/backend-control/SKILL.md` opens with the "Where commands run"
   note, `scripts/preview_enrichment.py` no longer contains the word `PROVISIONAL`, and
   `config_gate.require_capability(cfg, "sweep")` resolves instead of raising "unknown capability".
1. **The lane is enrichment** (resolved above): workflow `950HPb7a1GgSAIyZ`, record allowlist
   `9604614548`, `allow_create=false`, no domains. Note it in the log as the lane used.
2. **Record the flag state BEFORE**, read through Phase 27's status surface — **not** from local
   config (D-04). Every declaration in the target workflow must read disabled. The 2026-08-03
   read is in the table above; **re-read it yourself** rather than copying that table — the point of
   the step is a fresh observation.
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

# RB-8 · Plan 32-02 — Live notice gate, the wrapper re-run

Phase 32 exit gate. Read-only throughout — no arming, no deploy, no write to HubSpot or n8n. The
only mutations are machine-local (a temporary crontab line, a temporary interpreter argument),
and both are reverted at the end.

**This is a re-run, not a new gate.** RB-8 was run once already, on 2026-08-03 against the old
`claude -p` cron trigger, and its central claim FAILED: the cron fire produced no sweep and no
notice, **silently** (`29-06-FINDINGS.md`). Phase 32 replaced that trigger with a deterministic
`sh` wrapper (`lv-sweep-run.sh`) that runs `sweep_entry.py` directly — no LLM, no Anthropic
credential, nothing in the path that can expire. This re-run keeps the same six-step spine so the
two runs are comparable line for line. Sealing NOTICE-03 on source review alone would repeat the
exact mistake the first run made — a verification performed one layer away from the claim.

**Read first:** `SWEEP-CRON-TEMPLATE.md` (the shipped install text — follow it verbatim), and
`29-06-FINDINGS.md` (the original run, for the step-by-step comparison).

1. **Install: from the shipped template, verbatim.** Create the venv per Step 1 of
   `SWEEP-CRON-TEMPLATE.md`, then install the crontab (or launchd) line calling `lv-sweep-run.sh`
   with its three positional arguments — plugin root, venv python, log path — exactly as printed
   there. **Install the shipped text exactly; an approximate invocation is the failure class this
   gate exists to catch.** Record whether the crontab was empty beforehand, so the revert in step
   5 is provably clean. A short test cadence (e.g. `*/2` or `*/5`) may be substituted for the
   shipped `0 */4` for the gate window; restoring it is part of step 5.

2. **Silence check — carry forward the reason it was PARTIAL, and ring-fence it.** Let a real
   cron fire land with no session open. Check `~/Library/Logs/lv-backend-sweep.log`.
   - Healthy → exactly one stamped line, no banner.
   - Notices → the count, the full JSON, one banner per headline.
   - **Either outcome PASSES this criterion. Producing nothing at all is the old failure and
     FAILS it.**
   - `recent_executions` reads a **fixed page of 100 executions with no time window**
     (`EXECUTIONS_PAGE_LIMIT`, `n8n_read.py`). Check the live window's id range first: while
     execution **1173** (the pre-Phase-31 review approve that returned HubSpot 400) remains
     inside it, the sweep will keep firing on it and full silence is unobservable. **Record step
     2 as PARTIAL for that reason alone — it is a separate, already-filed defect**
     (`.planning/todos/pending/2026-08-03-sweep-lookback-has-no-time-window`), **not a failure of
     this phase's trigger.** Do not conflate the two, and do not attempt to clear 1173.

3. **Step 2b — the loud-failure proof, and it is a first-class criterion.** Point the crontab
   line's second argument (the interpreter) at one that does NOT have this plugin's
   `requirements.txt` installed — the system `python3` is the measured example — and let one fire
   land. Expected: a banner saying the sweep could not run, a non-zero exit, and a failure line in
   the log. This is the half the 2026-08-03 design never had: a trigger that could not run looked
   exactly like a healthy backend. **Restore the correct venv-python argument immediately after
   observing this** — it is a one-argument change to the crontab line, so do it now rather than
   leaving it to be remembered at step 5.

4. **Notice check and quality — unchanged in intent.** If a real errored execution is present,
   prefer it over any seeded condition, exactly as the first run did. If the backlog is genuinely
   zero and a condition must be manufactured, the 2026-08-03 amendment still stands: the
   prescribed "lower the threshold" lever does not work against a zero backlog — re-seed one real
   review candidate onto test company `9604614548` instead (fixture recoverable from the
   `30-07-review-canary-*` / `31-rb9-rerun-*` snapshots under
   `.planning/phases/22-armed-e2e-enrichment-canary/snapshots/`), and clear it in step 5. Keep the
   two live honesty traps in view while here: Apollo's `unreadable` balance must **never** read as
   out of credits; `credential_health.state: unknown` must **never** fire as broken. Confirm the
   original seven step-4 criteria, plus one new one:
   - arrives in the place 29-01 recorded
   - legible at the observed length ceiling
   - states the cause in plain language
   - states whether the operator or an admin can act
   - contains no instruction to run a command or open a terminal
   - declares its own read-only nature
   - honest about inference (never dresses a guess as a fact)
   - **NEW: arrived with no session open** — evidenced by the log timestamp against a cron fire
     time, not a manual invocation.

5. **Restore.** Three things, not one: the temporary cadence (back to the shipped `0 */4`), the
   interpreter argument (back to the correct venv python — should already be done per step 2b,
   confirm here), and the crontab line itself (removed if the gate was run on a temporary
   schedule). Clear any seeded review candidate from step 4.

6. **No writes, no credits — unchanged.** Confirm from n8n's execution history and the provider
   credit balances that the sweep's firings performed **no write** and consumed **no provider
   credits**, exactly as the first run's step 6 did. `test_sweep_read_only.py` is still the
   structural half — the import-graph guard proves no write path exists; this proves none was
   taken.

```bash
set -a; . ./.env; set +a
curl -sS "$N8N_URL/api/v1/executions?limit=20" -H "X-N8N-API-KEY: $N8N_API_KEY" \
  | python3 -c "import sys,json; [print(e['id'], e.get('workflowId'), e.get('startedAt'), e.get('status')) for e in json.load(sys.stdin)['data']]"
```

Record everything observed — the verbatim log lines, the fire timestamps, whether a banner
appeared for both the notice path and the broken-trigger path, and anything that surfaced
differently from what Phase 32 predicted — in `32-02-FINDINGS.md`. A surprise is the most
valuable thing this gate can produce; report it rather than smoothing it.

---

# RB-9 · Plan 30-07 — Armed review canary

**Blocked** behind 30-06 (30-01…30-04 are built; 30-05 in flight). Phase 30 exit gate. One record is
the **entire blast radius.**

### Resolved before you start (2026-08-03, read-only)

**The canary record is `9604614548` — Melbourne Racing Club, a company.** RB-7's armed enrichment
produced it: the pipeline itself flagged the record `needs_review` and held a real provider-vs-CRM
conflict (`industry`: provider `arts, entertainment, and recreation` against the stored `SPORTS`).
That is a better canary than a manufactured one, and it satisfies step 1 without further setup.
Because it is a **company**, the `TEST_RECORD_IDS`-only rule in point 3 below is satisfied by the id
that is already in hand.

**The review endpoints are currently unreachable, and that is expected.** Both
`hubspot/review/queue` and `hubspot/review/decision` live in `LV Review Decision (Cloud)`, which is
**inactive** — so a queue read returns `http_404` until step 4 activates it. A 404 here is the
workflow being off, not a broken endpoint. Do not debug it.

### ⚠ FIFTH thing, added 2026-08-03 — THE RELOAD GAP APPLIES TO THIS SECTION

`ENABLE_BAKED_FLAGS` overlays every workflow in the deploy set, and
`ALLOW_HUBSPOT_REVIEW_WRITES` is declared in **four**, of which **three are ACTIVE**:

| Workflow | Active | Declaring nodes |
|---|---|---|
| `LV Scheduled Maintenance (Cloud)` | **ACTIVE** | 4 — includes `Review Apply Update Write Gate`, **which hosts the 15-minute approve backstop** |
| `LV Enrichment (Cloud template)` | **ACTIVE** | 2 |
| `LV Contact Ingest (Cloud template)` | **ACTIVE** | 2 |
| `LV Review Decision (Cloud)` | inactive | 2 |

`deploy_n8n_workflows.py` **PUTs but never activates** (its line 25), so after step 3 the three
active workflows keep serving their OLD, disarmed bodies until they are bounced. Two consequences,
both of which will otherwise be misread:

1. **Step 3b will report `armed PASS` while three running instances are still disarmed.** It reads
   STORED content. This is precisely the false confidence that burned RB-3 on 2026-08-03.
2. **Step 8's APPROVE will probably do nothing.** The documented approve flow goes through the
   15-minute backstop in `reviewApply.js`, which lives in `LV Scheduled Maintenance` — active, and
   confirmed running on a 15-minute cadence (ticks observed at 03:30, 03:45, 04:00Z). Its running
   body will still be disarmed, so the approve will look like a broken approve rather than a stale
   reload.

**Therefore: bounce every active workflow immediately after step 3, and again after step 9.** A
deactivate→activate on each is what forces the running instance to reload. Step 4 already does this
for `LV Review Decision` by activating it from cold — that one is fine; the other three are not.

**Step 9's order is also wrong and must be reversed.** As written it redeploys disarmed and *then*
deactivates, which leaves a window where the running review-decision webhook is still armed while
stored content reads disarmed. **Deactivate `LV Review Decision` FIRST, then redeploy disarmed, then
bounce the three active workflows, then run the disarmed read-back.**

### Read before running — four things changed under this section

1. **TWO gates now, at different layers, and both must be open.**
   `ALLOW_HUBSPOT_REVIEW_WRITES` is a **backend baked constant**, compiled into workflow JSON and
   read by `_writeSafetyAllows()` **inside n8n**. `ALLOW_REVIEW_SUBMIT` is a **plugin-side operator
   env var**, read by Python **on your machine before a request exists** (D-34's uniform rule:
   value must read **exactly `true`**; `1`, `yes`, `TRUE` all refuse). Different processes, both
   required. Do not confuse them, and do not set the backend constant expecting the plugin to move.
2. **A new step 6b proves the plugin gate independently.** With `ALLOW_REVIEW_SUBMIT` **unset**,
   attempt the rejection and confirm the plugin refuses naming the variable — this is the only live
   proof the plugin gate holds on its own rather than being masked by the conversation arm. Step 9
   unsets it alongside the disarmed redeploy.
3. **A contact can only be allowlisted by `TEST_RECORD_IDS`.** Domain-only arming **denies silently**
   for contacts. If your canary record is a contact, a `TEST_RECORD_DOMAINS` entry alone will look
   armed and write nothing.
4. **This canary does NOT prove protected-field enforcement (D-31).** `manual_protected` is filtered
   on the review-decision endpoint (`reviewDecision.js`, by class) but **not** on the 15-minute
   backstop (`reviewApply.js`, allowlists by key, leaving `domain` and `annualrevenue` writable) —
   and the backstop is the path the documented approve flow uses. Record what you observed; do not
   write "protected fields are protected" in the log.

### THREE gates, all three must be open — verified against the shipped code 2026-07-31

Any one closed stops the write, and they live in three different places:

| # | Gate | Where it is read | How to open it |
|---|---|---|---|
| 1 | `ALLOW_REVIEW_SUBMIT` | **Python, your machine**, before a request exists | admin exports it in the shell the plugin runs in |
| 2 | The session arm | the conversation, never written to disk | say **"arm review writeback"** |
| 3 | `ALLOW_HUBSPOT_REVIEW_WRITES` + `TEST_RECORD_*` | **inside n8n**, a literal compiled into workflow JSON | deploy with `ENABLE_BAKED_FLAGS` |

**Gate 1 accepts the exact string `true` and nothing else** — tested empirically: `True`, `TRUE`,
`1`, `yes`, `""`, `" true"` and `"true "` all refuse. Same rule as `ALLOW_N8N_PROBE` and
`ALLOW_N8N_ARM` (D-34), deliberately, so one rule covers every gate in this milestone.

**Gate 2 is separate from the contact-dispatch arm in both directions.** Arming the upload does not
arm review writeback, and vice versa.

**Gate 1 gates *submitting* only.** A **reject** — which records a reason and leaves the record
queued — proceeds with it unset, and `preview_decision` is unaffected by it entirely. A kill switch
that blocked the un-doing path would be a trap. Gate 2 still applies to a rejection.

### Two failure modes that look like something else

- **CORRECTED 2026-08-03 (Phase 31 Plan 02, BUG 30).** An un-allowlisted decision now comes back as
  `outcome: not_allowlisted` with a message naming the allowlist, and the client reports it
  `not_written`, never `failed`. **An empty or unreadable body is therefore NOT the allowlist** — it
  means the *workflow itself* errored, and n8n execution history is where the cause is. (Before this
  phase, an allowlist drop returned no body at all and was indistinguishable from a broken endpoint —
  that gap is what misled RB-9's own run, below.)
- **Read the verdict from `verify_decision`, never from an HTTP status.** A mismatch names the
  offending key; an *unreadable* read-back is a different finding and should be reported as such,
  not merged into "failed".
- **CORRECTED 2026-08-03 (Phase 31 Plan 02, BUGS 28/29).** A review approval carrying a value
  HubSpot's enumeration will not accept — e.g. an `industry` candidate that is a raw provider label,
  not one of the 148 accepted options — now comes back as `outcome: refused`, naming the property and
  the offending value, on BOTH the preview and the real submit. Previously it 400'd inside the
  workflow only on a real submit, and the preview claimed `outcome: applied` for a write that was
  guaranteed to fail — this is the defect RB-9 step 8 found live.

### Start with a reject

**Reject is the safest first canary**: one property, the record stays queued, and it needs neither
`ALLOW_REVIEW_SUBMIT` nor an approval's multi-key patch (it still needs gate 2 and the backend
allowlist). Prove the path with a rejection, then do the approval.

1. Choose **ONE** HubSpot test company currently flagged for review and holding a stored review
   candidate. Note its record id. **The RB-9 canary record (`9604614548`) was cleared manually on
   2026-08-03** (its reject stands; `industry` now reads `SPORTS`) — it is no longer `needs_review`
   and cannot be reused as-is. A fresh `needs_review` fixture is needed: one enrichment run against a
   test company holding a conflicting staged value produces one.

```bash
# 2 — capture the before state. The script's own flags: --target-id plus --target-object-type.
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/canary_record_snapshot.py', run_name='__main__')" snapshot --label 30-07-review-canary --target-id <RECORD_ID> --target-object-type companies

# 3 — deploy ARMED for review writes only, one record in the allowlist
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_REVIEW_WRITES,TEST_RECORD_IDS=<RECORD_ID>" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# 3b — ARMED read-back (required before any decision) → expect VERDICT: armed PASS
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation armed --allowlist <RECORD_ID> --expect-armed ALLOW_HUBSPOT_REVIEW_WRITES
```

**Confirm a non-zero rewrite count for the flag.** Zero means it refused and deployed nothing.

Step 3b's read-back covers the review workflow — it discovers every node in every deployed workflow
that declares a write-safety constant, so the flag you just armed is one it can see. `--expect-armed`
is **symmetric**: naming `ALLOW_HUBSPOT_REVIEW_WRITES` asserts it reads enabled *and* asserts
`ALLOW_HUBSPOT_RECORD_WRITES` and `ALLOW_HUBSPOT_CREATE` still read disabled everywhere — a review
window that also armed dispatch is a widened blast radius and fails here. Omitting the argument
means record writes alone and would FAIL this window, so a forgotten flag is the stricter verdict.
**If Step 3b does not pass, do not take a decision.**

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

# RB-10 · Plan 33-04 — Refresh the clone, update, and observe one real migration

**READY.** Phase 33's release gate. Plugin `0.7.0` is committed (`33-04-SUMMARY.md`) but the
marketplace clone has not been refreshed, so nothing has reached the installed copy yet. Config
and the dashboard pointer now resolve from
`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`, and the first
resolution after an update is supposed to migrate them up from the newest previous install —
0600, verified byte-for-byte, source removed only after that verification. This gate is where
that claim meets a real update on a real machine for the first time.

**Two things need a human, not one.** The clone refresh is release-checklist step 4 and the
clone never fetches on its own (§0's standing rule). And Research Open Question 1 is still open:
a closed-as-not-planned upstream issue (anthropics/claude-code#41156) reports that writes into
`~/.claude/plugins/data/<id>/` raise a "sensitive location" permission confirmation at the
Bash-tool layer, even under `bypassPermissions` — **not reproduced during 33-RESEARCH.md,
MEDIUM confidence.** A migration that stops to ask is a terminal step by another name, so this is
observed here, not assumed.

**Do not perform any migration against your real state anywhere but here, and do not shortcut
the backup in Step 0.** This is the one run where an unproven delete path touches a live
`webhook_secret` and `n8n_api_key`.

**Absolute rule, restated because it is the one thing that would invalidate this gate: if a
permission prompt fires in Step 3, that IS the finding.** Do not change a permission setting, do
not edit `settings.json`, and do not add a hook to suppress it. The mitigation already built for
exactly this case is `LV_OPERATOR_CONFIG` (the admin escape hatch in `durable_paths.py`'s
resolution order) plus the untouched legacy fallback — record the prompt verbatim and stop; the
next step is a decision about the chosen storage location, never a workaround around the guard.

### Step 0 — record the before state, and back up the live config

Form 3, plus one Form-1-shaped read:

```bash
ls -la ~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/
ls -la ~/.claude/plugins/data/
```

Note which install directories exist under `cache/.../operator-claude-plugin/` and confirm no
`operator-claude-plugin-lightning-visuals-operator` directory yet exists under `data/`. Copy
`operator.local.json` from the **newest** install directory that holds one to somewhere **outside
`~/.claude/`** as a safety net — this costs nothing and is the one precaution that makes Step 3's
delete path recoverable if `_migrate_once`'s verify-then-delete does not behave as tested.

### Step 1 — push and refresh the clone

Release-checklist step 3 and 4, run here rather than by the executor per this plan's own
constraint (the orchestrator does not push or refresh the clone on its own):

```bash
git push origin master

git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator fetch --depth=1 origin master
git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator reset --hard FETCH_HEAD
```

### Step 2 — update the plugin

Form 3. Open the Claude Desktop plugin manager and confirm the **Update** button is actually
offered for `operator-claude-plugin`. **A greyed-out button here is itself the finding** — it
means the version bump or the clone refresh did not land, not that there is nothing to update.
Trace which of the two before treating this as done.

### Step 3 — trigger one resolution, in a NEW conversation

Form 3. Say `/operator-claude-plugin:initialize`. **Watch for a permission-confirmation dialog
before doing anything else.** Record verbatim: whether one appeared, its exact wording, whether
it blocked the skill from completing, and whether declining or ignoring it left the plugin
working or hanging. This is the live answer to Open Question 1 — see the absolute rule above if
one fires.

### Step 4 — read the outcome

`initialize` should report the settings file at the durable path and say the settings live
outside the install folder — never mentioning migration by name (33-03's own rule for that
branch). Then confirm on disk:

```bash
ls -l ~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json
```

- Mode reads `600`.
- Contents match the Step 0 backup, byte for byte.
- The previous install directory's copy of `operator.local.json` is **gone**.
- The **current** (`0.7.0`) install directory holds no `config/operator.local.json` of its own —
  it should never have had one; a hit here means the sibling scan found the wrong source.

**If the migration did not happen**, record which of the five resolution steps it stopped at
(`durable_paths.py`'s own docstring numbers them 1–5). `initialize` naming a path inside the new
install directory means the sibling scan found nothing to migrate; naming the previous install's
path means the copy-verify-delete sequence itself did not complete.

### Step 5 — the dashboard pointer

Form 3. Ask for backend status, then ask for a dashboard. Note the Artifact URL. **In a
brand-new conversation**, ask for the dashboard again. Same URL confirms STATUS-05 holds across
this update — the guarantee the 0.7.0 CHANGELOG entry names as silently broken since the
plugin's first-ever update, now fixed by the same durable-home mechanism as Step 4.

### Where the outcome is written

`.planning/workstreams/plugin-entrypoint/phases/33-durable-operator-state/33-FINDINGS.md`,
verbatim — including a clean run with no prompt. A "nothing happened, it just worked" result is
still the finding this gate exists to produce; do not skip writing it down because there was
nothing dramatic to report.

---

## Resume signals — what to reply with

| § | Plan | Reply with |
|---|---|---|
| RB-1 | 25-01 | Probe A verdict + HTTP status; the four `time_total` values; whether B4 (full waterfall) was run; the view decision |
| RB-2 | 29-01 | The three Task-1 observations (or "blocked" + verbatim error); Task 2 as YES/NO/INCONCLUSIVE |
| RB-3 | 23-06 | A1–A7 observed; the armed and disarmed verdicts; whether HubSpot shows a **created** contact; raw webhook response; execution id |
| RB-4 | 27-05 | "approved", or which step's behaviour differed |
| RB-5 | 28-02 | "approved" + roundtrip verdict + settings/connections comparison + execute-endpoint status code; then execution spacing + restore verdict + 28-FINDINGS.md written |
| ~~RB-6~~ | ~~28-04~~ | **withdrawn — nothing to reply** |
| RB-7 | 28-06 | "approved" + both read-back verdicts + armed-window duration + only-allowlisted-record confirmation + disarmed-after-redeploy confirmation |
| RB-8 | 32-02 | The verbatim log lines observed, the fire timestamps, whether both banners appeared (notice path AND the deliberately broken-interpreter path), and any divergence from what Phase 32 predicted |
| RB-9 | 30-07 | "approved" + the record id + the confirmed disarmed read-back + the step-6b refusal + whether the record was a company or a contact |
| RB-10 | 33-04 | Whether the Update button was offered; whether a permission prompt fired in Step 3 (verbatim wording if so); the migrated file's mode and byte-for-byte match against the Step 0 backup; whether the dashboard URL matched across the brand-new conversation; or "blocked" + which of the five resolution steps it stopped at |

---

## Changelog — what moved under this runbook since it was written

Kept so a section you read yesterday is not silently different today.

| When | Change |
|---|---|
| 2026-07-31 | **Tenant pinned.** `N8N_EXPECTED_URL` = `https://alexherman.app.n8n.cloud`. Replaces the unfollowable "key must be Robert's, Alex's in `N8N_API_KEY_2`" check — `N8N_API_KEY_2` does not exist |
| 2026-07-31 | **RB-3 gained three confirmed defects**, of which **two are now fixed by plan 23-07** (read-back coverage; Step 3b rejecting a correctly armed backend). The remaining one — 23-01's fix committed but not deployed, with Steps 2b/2c inserted for it — still stands |
| 2026-07-31 | **RB-4 became runnable** — Phase 27 is code-complete |
| 2026-07-31 | **RB-5's probe variable is named** `ALLOW_N8N_PROBE`, and its credential source is settled as `config_gate.load_config()`, not shell `N8N_URL`/`N8N_API_KEY` |
| 2026-07-31 | **RB-6 withdrawn** — the decision it asked for was already made (D-25 / amendment #6) |
| 2026-07-31 | **Gating made uniform (D-34)** — one `ALLOW_*` per dangerous capability, value exactly `true`, checked before any transport. Added `ALLOW_N8N_ARM` (RB-7) and `ALLOW_REVIEW_SUBMIT` (RB-9) |
| 2026-07-31 | **RB-1's Probe B partly pre-measured** — 36.1 s/record measured free from execution history, implying a chunk default of 1–2 and a likely 524 on the five-record probe |
| 2026-07-31 | **RB-9 gained four changes** — two gates at different layers, a new step 6b, contacts allowlistable only by `TEST_RECORD_IDS`, and the D-31 caveat that it does not prove protected-field enforcement |
| 2026-07-31 | **The read-back was fixed (plan 23-07, D-19).** `verify_live_write_safety.py` now scans EVERY deployed workflow and every node declaring a write-safety constant, and takes `--expect-armed FLAG,FLAG`. Two of RB-3's three defects and RB-9's ⚠ paragraph are gone with it; the all-workflow shell workaround is retired. RB-3's undeployed-23-01 finding stands |
| 2026-08-03 | **The stored-vs-running reload gap, found live under RB-3.** `deploy_n8n_workflows.py` PUTs but never activates, and n8n serves a RUNNING workflow's old content until a deactivate→activate bounce — so `verify_live_write_safety.py` (which reads STORED content) can report `armed PASS` while the running webhook is still disarmed. Every arm AND disarm now bounces. `n8n_control.apply_mutation` was already correct; the `ENABLE_BAKED_FLAGS` deploy path was not |
| 2026-08-03 | **RB-7 de-provisionalised and unblocked.** Lane (enrichment), workflow (`950HPb7a1GgSAIyZ`), record (`9604614548`), `allow_create=false`, the live before-state, the `control` capability check and step 6's expected literal are all resolved in its header table. A new step 0 refreshes the installed plugin — the cached `SKILL.md` files are stale — and the `dispatch_fn` wiring gap in the shipped surface is documented there rather than left to be rediscovered mid-window |
| 2026-08-03 | **RB-2 answered** — the sweep host is cron/launchd → `claude -p` headless (D-01 amendment); Cloud Routines and harness cron are both out. `29-HOST-PROBE.md` holds the verdicts |
| 2026-08-03 | **RB-9's diagnostic advice corrected (Phase 31 Plan 02, BUGS 28/29/30 — found live by RB-9 step 8).** An un-allowlisted decision now answers `not_allowlisted` explicitly instead of an empty body, so silence no longer means "check the allowlist" — it means the workflow errored and n8n execution history is where to look. An enum-invalid review candidate (e.g. `industry`) now answers `refused` naming the property and value, on both preview and real submit, instead of 400ing inside the workflow on submit only. Step 2's snapshot command corrected to the script's real flags, `--target-id` and `--target-object-type` |
| 2026-08-04 | **RB-10 added (Phase 33 exit gate).** Plugin `0.7.0` moves the operator's settings and dashboard pointer to a durable home outside the versioned install folder, with a one-time sibling-scan migration on first resolution after an update. RB-10 is the first live update-and-migrate on a real machine, and the live answer to Research Open Question 1 (does the migration write trip a Bash-tool "sensitive location" permission prompt?) — not reproduced during research, MEDIUM confidence, settled by observation here rather than by more reading |

### Standing note — the read-back, after 23-07

`scripts/verify_live_write_safety.py` is the read-back both RB-3 and RB-9 depend on. Since plan 23-07
it **discovers** its own coverage — every node in every deployed workflow that declares a
write-safety constant, so a workflow deployed or renamed later appears with no code edit — and it
takes `--expect-armed FLAG,FLAG` so each window can state exactly what it armed. There is
deliberately **no workflow-narrowing argument**: a scan that can be narrowed can be blind.

Read its `coverage:` line every time. **A scan that discovers zero declaring nodes FAILS** rather
than reporting a disarmed pass, and an **empty allowlist under an armed expectation is its own
finding** — `_writeSafetyAllows()` returns false on empty, so that state grants nothing while every
flag reads `true`. Naming a flag never widens the check: every write-enabling boolean you do not
name is still asserted disabled, everywhere it is declared.
