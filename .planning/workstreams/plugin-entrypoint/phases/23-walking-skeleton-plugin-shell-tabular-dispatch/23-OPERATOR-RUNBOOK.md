# Operator Runbook — Phase 23 walking-skeleton install + armed create canary

This runbook closes plan `23-06`, the only armed operator action in Phase 23. It follows the
ceremony `22-OPERATOR-RUNBOOK.md` established — arm, fire once, read back, restore disarmed, read
the deployment back — and reuses the identical deploy-time overlay mechanism
(`_OVERLAY_FLAG_SPEC` / `enable_baked_flags()`, `scripts/deploy_n8n_workflows.py`).

Armed n8n deploys and armed HubSpot record writes are classifier-blocked for agents in this
environment. **This whole window is yours to run.** Everything else in Phase 23 was automated and
is already committed.

## Scope

- **What this proves:** (1) the plugin installs and is invocable conversationally in the Claude
  Desktop **Code** tab — not hand-run (PLUGIN-01); (2) an armed dispatch now **creates** a contact
  rather than routing it to `needs_review`, which is the end-to-end proof of the `23-01` gate fix
  (DISPATCH-01 + DISPATCH-03).
- **Records touched:** exactly one, and it does not exist yet —
  `canary-23-06-20260731@australiagtm.com`. This is a **create** canary, which is why it differs
  from Phase 22's update canary in the next bullet.
- **Write flags armed:** `ALLOW_HUBSPOT_RECORD_WRITES` **and** `ALLOW_HUBSPOT_CREATE`, allowlisted
  to `TEST_RECORD_DOMAINS=australiagtm.com`.
  **This is a deliberate departure from `22-OPERATOR-RUNBOOK.md`, which forbade
  `ALLOW_HUBSPOT_CREATE`.** Phase 22 had no create path in its success criteria, so arming create
  widened risk for no verification value. Phase 23's entire goal *is* the create path — criterion 3
  is unprovable without it. Do not carry Phase 22's prohibition across.
- **Why a domain allowlist rather than `TEST_RECORD_IDS`:** the record does not exist yet, so it has
  no id to allowlist. Domain allowlisting is inherent to testing creation. Understand what this
  means: the allowlist is a **gate, not a selector** — it permits writes to any record at
  `australiagtm.com` for the duration of the window. The one-row CSV is what bounds the write to
  one record. Do not dispatch anything else while armed.
- **Prerequisite:** plan `23-05` must have landed. Section A installs a plugin whose preview step
  `23-05` builds; running Section A before then verifies an incomplete surface.

## Command form

Every live command runs through the same in-process `python-dotenv` wrapper
`22-OPERATOR-RUNBOOK.md` established, from the repo root:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/<script>.py', run_name='__main__')" [trailing CLI args]
```

- **A bare `python scripts/foo.py` from a fresh shell silently sees no credentials and skips.**
  None of these scripts call `load_dotenv()` themselves. Always use the wrapper.
- `load_dotenv()` defaults to `override=False`: variables already set in the shell
  (`DRY_RUN=false`, `ALLOW_N8N_DEPLOY=true`, `ENABLE_BAKED_FLAGS=...`) **win** over `.env`.
  `.env`'s own `DRY_RUN=true` cannot un-arm a shell-set `DRY_RUN=false`.
- Run everything from the repo root — the relative `scripts/` path and `.env` discovery both
  assume it.
- **Set `N8N_EXPECTED_URL` before ANY deploy command.** API-created workflows land in the key
  owner's n8n project, and a wrong key silently deploys into the wrong one — this has already cost
  a full deploy cycle once. The deploy target is `https://alexherman.app.n8n.cloud`, confirmed
  2026-07-31 as the correct tenant:

  ```bash
  grep -q '^N8N_EXPECTED_URL=' .env || echo 'N8N_EXPECTED_URL=https://alexherman.app.n8n.cloud' >> .env
  ```

  `_instance_ok()` pins `N8N_URL == N8N_EXPECTED_URL` **only when that variable is set**; unset, it
  falls back to `host.endswith(".n8n.cloud")`, which any n8n Cloud tenant satisfies. Setting it
  turns the fallback into an exact-match pin. **Superseded:** this bullet previously said the key
  must be Robert's with Alex's in `N8N_API_KEY_2`. `N8N_API_KEY_2` does not exist, so that check was
  unfollowable — Section B was blocked on it during the 2026-07-31 window.

---

# SECTION A — install and invoke the plugin (23-06 Task 1)

Read-only. Nothing here arms anything or writes to HubSpot. Record each step as observed pass or
observed fail **with what you actually saw** — a step that fails is a gap for
`/gsd-plan-phase 23 --gaps`, not something to work around here.

### A1 — validate the plugin as a developer

```bash
claude plugin validate ./operator-claude-plugin
```

Record the validator's output verbatim. Also load it for a session to confirm it resolves:

```bash
claude --plugin-dir ./operator-claude-plugin
```

### A2 — install the way the operator will

Desktop app's plugin manager, **no terminal**. Confirm it appears installed. This is the step that
actually tests PLUGIN-01 — A1 proves the package is well-formed, not that the operator path works.

### A3 — natural-language trigger

Fresh session. Say something ordinary: *"load these contacts into HubSpot"*. Confirm the skill
triggers **without** the slash command.

### A4 — slash-command trigger

Another fresh session. Invoke `/operator-claude-plugin:contact-upload`. Confirm identical
behaviour. Both must enter the same code path, not two implementations (D-02, D-14b).

### A5 — it states endpoint and arming state up front

Confirm the **first** thing it says names the endpoint it would POST to and states that dispatch is
disarmed — **before** it asks for a file (D-12).

### A6 — it refuses cleanly when unconfigured

```bash
mv operator-claude-plugin/config/operator.local.json operator-claude-plugin/config/operator.local.json.bak
```

Invoke it again. Confirm it refuses in plain language naming what is not configured, **shows no
key**, and produces no raw socket error (PLUGIN-03, D-06). Then restore:

```bash
mv operator-claude-plugin/config/operator.local.json.bak operator-claude-plugin/config/operator.local.json
```

### A7 — declining the preview sends nothing

Point it at `~/Desktop/lv-canary-23-06.csv`, let it preview, then **decline**. Confirm nothing was
sent and that it says so (PREVIEW-04). The backend is still disarmed at this point, so this is
doubly safe — but the plugin must refuse on its own terms, not merely be saved by the backend.

**Gate:** do not proceed to Section B until A1–A7 are recorded. Section B assumes a working,
installed plugin.

---

# SECTION B — the armed create canary (23-06 Task 2)

### Step 0 — confirm the canary does not already exist

In HubSpot, search for `canary-23-06-20260731@australiagtm.com`. **It must not exist.** A
pre-existing contact turns a create test into an update test and the canary proves nothing.

If it does exist (a previous run), pick a new dated address, update the CSV, and note the change in
the ledger.

### Step 1 — disarmed baseline read-back

Prove the starting state rather than assuming it:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
```

Confirm `VERDICT: disarmed PASS`.

### Step 2 — dry-run the deploy

Default is dry-run; this arms nothing and shows the diff:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

### Step 3 — arm

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,ALLOW_HUBSPOT_CREATE,TEST_RECORD_DOMAINS=australiagtm.com" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

Syntax notes (`_OVERLAY_FLAG_SPEC` / `_requested_overlay_flags()`):

- `ALLOW_HUBSPOT_RECORD_WRITES` and `ALLOW_HUBSPOT_CREATE` are bare boolean kill switches — write
  them with **no** `=value`. Each rewrites its baked `"false"` literal to `"true"`.
- `TEST_RECORD_DOMAINS=australiagtm.com` supplies the allowlist value. The script **REFUSES** to arm
  any write-enabling flag unless the SAME invocation also supplies a non-empty `TEST_RECORD_IDS`
  and/or `TEST_RECORD_DOMAINS` — enforced code, not convention. **That refusal is a correct outcome
  to record, not an obstacle to route around.**
- Multiple values would separate with `|`, not `,` — `,` already separates entries within
  `ENABLE_BAKED_FLAGS` itself. Not needed here.
- A name outside `_OVERLAYABLE_FLAGS` raises rather than silently enabling nothing, so a typo
  refuses the deploy instead of no-op'ing.
- `VALUE` is rendered with `json.dumps`, so it always lands as a quoted JS string literal and can
  never inject JS.

The deploy prints its rewrite count before any write happens. **Expect the create flag to rewrite
in 9 nodes and record-writes in 8** (verified 2026-07-31: contact ingest 3/2, enrichment 2/2,
maintenance 4/4 — the two flags are declared in *different* subsets). A count of 0 for either flag
means the script refuses and deploys nothing.

### Step 3b — armed read-back (required, distinct step)

The deploy's exit code is **not** this proof:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation armed --allowlist australiagtm.com
```

Confirm `VERDICT: armed PASS` before firing. If it fails, **do not fire** — return to Step 3.

### Step 4 — fire exactly once, through the plugin

This is the point of the phase: the dispatch goes through the **plugin**, not curl. In a Claude
Desktop Code-tab session:

1. Point the plugin at `~/Desktop/lv-canary-23-06.csv`.
2. Review the preview — confirm it shows 1 row and labels `Email Address → email`,
   `First Name → firstname`, `Last Name → lastname`, `Company → company`.
3. Approve it.
4. Arm the conversation with the plugin's arming phrase.
5. Let it dispatch.

**Exactly ONE dispatch. A second fire is a new window, not a retry** — if it fails or times out
ambiguously, read the record and the executions list before firing again. Do not fire twice to
"make sure."

<details>
<summary>curl equivalent — for diagnosis only, if the plugin path fails</summary>

```bash
curl -sS -X POST "$N8N_URL/webhook/hubspot/contact-upload" \
  -H "X-Enrichment-Secret: $N8N_ENRICHMENT_WEBHOOK_SECRET" \
  -F "data=@$HOME/Desktop/lv-canary-23-06.csv;type=text/csv"
```

Using this instead of the plugin means Task 2 did **not** pass — it proves the backend, not the
client. Record it as a Section A failure and a Section B partial.
</details>

### Step 5 — read back the run

Capture the execution id:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" list
```

Then in HubSpot, confirm a contact was **CREATED** with that email.

**A row landing in the review queue instead means the `23-01` gate fix did not take effect.**
Record that as a failure of 23-01 with the execution id — do not retry, and do not adjust the
plugin to compensate.

Also record the raw webhook response verbatim. Phase 26 needs it for its response-shape work. **Do
not assert it is a complete per-record ledger** — this phase claims only that the POST was accepted.

### Step 6 — disarm

A plain deploy pushes the committed literals, which are disarmed. This works *because*
`enable_baked_flags()` only ever widens disabled→enabled — it cannot disarm, so disarming is
redeploying the committed artifact:

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

### Step 7 — disarmed read-back

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
```

Confirm `VERDICT: disarmed PASS`. **The window is not closed until this passes.**

### Step 8 — clean up the canary

Delete or mark the canary contact per the repo's existing canary cleanup practice.

---

## Pass / fail condition

**PASS** requires all of:

- A1–A7 recorded, with A2 (GUI install), A3 and A4 (both trigger paths, same code path), A5
  (endpoint + disarmed stated up front), A6 (clean refusal, no key shown) and A7 (decline sends
  nothing) all observed passing.
- Step 3b showed `VERDICT: armed PASS`.
- HubSpot shows a contact **created** at `canary-23-06-20260731@australiagtm.com` — not a review row.
- Step 7 showed `VERDICT: disarmed PASS`.

**FAIL** on any of those. A fail is recorded, not worked around. Gaps route to
`/gsd-plan-phase 23 --gaps`.

## Abort path

If anything unexpected happens at any point while armed — ambiguous response, wrong record touched,
unexpected execution count — **go straight to Step 6 and Step 7**. Disarm first, diagnose after. A
backend left armed is the failure mode this whole ceremony exists to prevent, and Phase 28's
`arm → dispatch → disarm` design (D-03) treats a stuck-armed backend as a real, expected hazard.

## Where the outcome is written

- `23-06-SUMMARY.md` — the canary email/domain, the read-back verdicts before and after, whether
  HubSpot shows a created contact, the raw webhook response, and the n8n execution id.
- `operator-claude-plugin/CHANGELOG.md` — that the lane was proven end to end, with the date.

Never paste `$N8N_ENRICHMENT_WEBHOOK_SECRET` or any key into either.
