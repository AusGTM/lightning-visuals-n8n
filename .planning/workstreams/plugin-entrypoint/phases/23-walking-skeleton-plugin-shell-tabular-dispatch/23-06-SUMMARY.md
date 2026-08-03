# 23-06 — Plugin install + armed create canary

**Status: IN PROGRESS.** Section A partially observed. **Section B not started — blocked.**
Runbooks: `23-OPERATOR-RUNBOOK.md` (authoritative) · `../../OPERATOR-RUNBOOK.md` §RB-3.

No secret, token, or webhook-URL-with-secret appears in this file.

---

## Setup performed

| Item | State |
|---|---|
| `operator-claude-plugin/config/operator.local.json` | Created from the committed example, populated from `.env`. Confirmed gitignored (`.gitignore:6`). |
| `~/Desktop/lv-canary-23-06.csv` | Created. One row, headers `Email Address,First Name,Last Name,Company`, address `canary-23-06-20260731@australiagtm.com`. Did not previously exist. |

`config_gate.py` returns `{"ok": true, "target": "<n8n host>/webhook/hubspot/contact-upload"}`.

---

## Section A observations

### A1 — `claude plugin validate` · **FAIL then PASS after a fix**

First run failed:

```
❯ author: Invalid input: expected object, received string
✘ Validation failed
```

**Root cause:** `.claude-plugin/plugin.json` carried `"author": "Lightning Visuals"`, a bare
string. The Claude plugin schema requires an object. **This would have failed A2 (the Desktop
plugin-manager install) too** — A1 caught a genuine packaging defect, not a runbook error.

**Why the suite missed it:** `tests/test_plugin_manifest.py` asserted only that the `author`
*key was present* (`{"name","description","version","author"} <= set(data)`), never its type.

**Fix applied** (uncommitted at time of writing, pending operator go-ahead):

- `plugin.json` → `"author": { "name": "Lightning Visuals" }`
- `test_plugin_manifest.py` → added type + non-empty-`name` assertions, so the gap the live
  validator found is now covered by the suite rather than only by a human running A1.

Re-run: `✔ Validation passed`, and **also passes `--strict`**. Plugin suite: **302 passed**.

> One false lead worth recording so it is not re-investigated: an earlier run appeared to
> double the path (`.../operator-claude-plugin/operator-claude-plugin`). That was a persisted
> shell working directory in the harness, not a defect in the command as the runbook writes it.
> `claude plugin validate ./operator-claude-plugin` from the repo root is correct.

### A6 — clean refusal when unconfigured · **PASS (behaviour observed)**

Observed before the config file was created, which is the same state A6 constructs by moving it
aside. `config_gate.py` exited non-zero with:

```json
{"ok": false, "error": "Configuration file not found at <path>. Copy config/operator.local.example.json to config/operator.local.json and fill it in once — the n8n_url and webhook_secret values come from your n8n admin."}
```

Plain language, names what is missing and what to do, **shows no key**, no raw socket or parser
error. PLUGIN-03 / D-06 satisfied at the gate level. **Still to do conversationally** through the
installed plugin, which is what A6 formally asks for.

### Step-4 preview precondition · **verified early**

`preview.py` against the canary CSV returns exactly what Section B Step 4 requires:
`row_count: 1`, `mapping_available: true`, `adaptive: false`, and
`Email Address → email`, `First Name → firstname`, `Last Name → lastname`, `Company → company`,
all four `dropped: false`. (`unmapped_canonical_props` lists `jobtitle`, `linkedin_url`, `phone`
— expected; the canary CSV carries no such columns.)

### Not yet observed

**A2** (Desktop plugin-manager install, no terminal), **A3** (natural-language trigger),
**A4** (`/operator-claude-plugin:contact-upload`, same code path), **A5** (endpoint + disarmed
stated first, before asking for a file), **A7** (decline sends nothing). All five are Claude
Desktop interactions with no command form.

---

## Section B — Step 1 done; Steps 2+ held pending two findings

### Tenant pinned (blocker resolved)

Robert confirmed the `.env` key is his despite the `alexherman.app.n8n.cloud` hostname.
`N8N_EXPECTED_URL` has been appended to `.env` pinning that host, converting
`_instance_ok()` from a `.n8n.cloud` suffix fallback into an exact-match guard. Verified
`N8N_URL == N8N_EXPECTED_URL`. `N8N_API_KEY_2` remains absent — the runbooks' description of
where Alex's key is retained is now stale and should be corrected or dropped.

### Step 1 — disarmed baseline read-back · **VERDICT: disarmed PASS**

```
workflow: 'LV Enrichment (Cloud template)'
node 'Decide Action':          ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS=''
node 'Decide Company Action':  ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS=''
VERDICT: disarmed PASS
```

**A read-only probe across every live workflow confirms the instance is genuinely disarmed** —
all four constants are at their disabled literals in all 8 declaring nodes (maintenance 4,
enrichment 2, contact ingest 2). That part is sound. What follows is about the *proof*, not the
state.

---

### FINDING 1 — the read-back verifier covers 2 of the 8 declaration sites, and none in the lane the canary uses

`scripts/verify_live_write_safety.py:60` hardcodes
`ENRICHMENT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"`, and `:64` hardcodes
`WRITE_DECISION_NODE_NAMES = ("Decide Action", "Decide Company Action")`. It has no
workflow argument. Every read-back in this runbook — Step 1, **Step 3b**, **Step 7** —
inspects only that one workflow's two nodes.

The canary fires at `hubspot/contact-upload` → `LV Contact Ingest (Cloud template)`, whose
write gates are named **`HubSpot Update Write Gate`** and **`HubSpot Create Write Gate`**.
Both the workflow name and the node names are wrong for that lane, so pointing the existing
verifier at contact ingest would not merely miss the gates — it would report *"node not found"*.

Consequences, in severity order:

1. **Step 7 is the safety-critical one.** "disarmed PASS" would be reported while the contact
   lane's own gates were unverified. A backend left armed in the contact lane is precisely the
   failure mode the whole ceremony exists to prevent (`23-OPERATOR-RUNBOOK.md`, Abort path).
2. **Step 3b's "do not fire unless this passes" gate does not cover the lane being fired at.**
3. A contact-lane arming failure would surface as a row in `needs_review`, which the runbook
   instructs recording as *"the 23-01 gate fix did not take effect"* — a **misattribution trap**.

Not patched here, per global safety rule 7 (a failure is recorded, not worked around) — changing
a safety verifier mid-window is its own hazard. Routes to
`/gsd-plan-phase 23 --gaps --ws plugin-entrypoint`. Suggested shape: drop the hardcoded name and
have the verifier report every live workflow/node declaring any `_OVERLAY_FLAG_SPEC` constant,
so coverage cannot silently drift again as lanes are added — the same no-allowlist reasoning
27-04 already applied to `status.describe_all()` (D-07).

### FINDING 2 — the live contact-ingest workflow predates 23-01, so Step 3 would deploy never-live-tested logic already armed

| | Declares `ALLOW_HUBSPOT_CREATE` |
|---|---|
| Committed `n8n/wf_contact_ingest_cloud.json` | `Set Config`, **`Decide Action`**, `HubSpot Update Write Gate`, `HubSpot Create Write Gate` |
| **Live** `LV Contact Ingest (Cloud template)` | `HubSpot Update Write Gate`, `HubSpot Create Write Gate` only |

Live `updatedAt` is **2026-07-30T11:38:19Z**; 23-01 landed 2026-07-31. `Decide Action` exists on
the live workflow but declares none of the four constants. **23-01's create-gate fix is committed
but was never deployed.**

This does not break Section B — Step 3's deploy pushes the committed artifact, so 23-01's fix
would land. But it lands **in the same action that arms writes**, meaning the first time this
backend logic ever runs live is with `ALLOW_HUBSPOT_CREATE` already `"true"`.

**Recommended sequencing change:** insert a disarmed deploy between Step 2 and Step 3 —

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

— then re-run the Step 1 read-back. That proves 23-01 reaches the instance cleanly while
everything is still disabled, and separates "did the fix deploy" from "did arming work". Without
it, a failure at Step 5 has two candidate causes and no way to tell them apart.

Note also the runbook's stated expectation of **"create in 9 nodes"** should be re-derived after
this deploy — the committed artifacts and the live instance currently disagree on the count.

---

## Section B — remaining steps not started

**RESOLVED 2026-07-31 — Robert confirmed the key is his; `N8N_EXPECTED_URL` now pins the tenant.
Original finding retained below for the record.**

**Blocker: the n8n tenant and API key in `.env` cannot be attributed.**

Both runbooks open every deploy section with the same warning: confirm whose key is in
`N8N_API_KEY` before **any** deploy command, because API-created workflows land in the key
owner's project and a wrong key has already cost one full deploy cycle. That check cannot be
satisfied from the repo:

| Observation | Value |
|---|---|
| `N8N_URL` | `https://alexherman.app.n8n.cloud` — Alex's tenant by hostname |
| `N8N_EXPECTED_URL` | **unset** |
| `N8N_API_KEY` | present, ownership **not determinable from the repo** |
| `N8N_API_KEY_2` | **absent** — but both runbooks state Alex's key is retained here |

The last row is the substantive part. The runbooks' stated arrangement is *Robert's key in
`N8N_API_KEY`, Alex's in `N8N_API_KEY_2`*. `N8N_API_KEY_2` does not exist, so the arrangement
the warning assumes is not in place, and the single key present cannot be assumed to be Robert's.

**The existing guard does not catch this.** `scripts/deploy_n8n_workflows.py::_instance_ok()`
pins `N8N_URL == N8N_EXPECTED_URL` only when `N8N_EXPECTED_URL` is set; unset, it falls back to
"host ends with `.n8n.cloud`", which `alexherman.app.n8n.cloud` satisfies. The deploy would
proceed, not refuse.

**Required before Section B Step 2:**

1. Robert confirms which tenant/key `.env` currently holds.
2. `N8N_EXPECTED_URL` is set to that tenant, converting the fallback into an exact-match pin.

Same blocker gates **RB-5 / 28-02**, whose probe refuses unless the two URLs match — there it
surfaces as a refusal rather than a silent wrong-project write.

---

## Pass/fail

**Not yet determined.** A1 passes only after the manifest fix above. A6's behaviour is observed
at the gate. A2–A5 and A7 are unobserved, and Section B has not started.

---

## Section B — armed create canary: PASSED 2026-08-03, after finding two real defects

**The proof:** contact `342770428400` (`canary-23-06-20260731@australiagtm.com`, Canary
Twentythreesix, Australia GTM) created at `2026-08-03T01:52:28.977Z` by execution 1129 —
two seconds after a single plugin-driven dispatch, inside an armed window bounded to
`TEST_RECORD_DOMAINS=australiagtm.com`, closed immediately after with a full-coverage
`disarmed PASS` (5 workflows / 11 nodes). Steps 2b/2c ran earlier the same day as the
milestone-wide disarmed redeploy.

**It took four sends, because the canary found what it exists to find:**

1. **The stored-vs-running reload gap.** `deploy_n8n_workflows.py` PUTs but never
   activates (its own line 25); `armed PASS` verifies STORED content while the RUNNING
   webhook keeps executing pre-arm content. Runs 1122/1123 fired inside an "armed" window
   whose running gates were still disarmed. **The ceremony now bounces
   (deactivate→activate) after every arm AND every disarm** — a PUT-only disarm would
   leave a running instance armed, which is the dangerous direction.
2. **BUG 27.** After the bounce, run 1126 still refused: the create gate derived its
   domain from `identity_keys.domain`/`json.domain` — fields Decide Action never emits —
   and a net-new create has no `hs_object_id`, so `_writeSafetyAllows('create', null,
   null)` denied every create regardless of arming. BUG 16 had fixed the id-half of this
   exact shape for updates; the domain-half survived because nothing live-tested create
   until this canary. Fixed at the splice point (domain from `properties.email`, CREATE
   only — the unscoped version was itself caught by reviewDecisionEndpoint g3 handing
   review gates a domain path 30-02 withheld). Pinned by three two-sided flow tests that
   RUN Decide Action and feed its verbatim output to the gate (`22a3f2a`).
3. Also observed: the plugin's thin-response reporting labels an unconfirmable send
   `not_confirmed` and *guesses* the reason from its own (possibly stale) gate belief —
   both failed sends were narrated as "write gated" on stale evidence. Queued for
   Phase 26 follow-up: the reason field must be marked belief, not observation.

**Run ledger:** 1122, 1123 (pre-bounce, stale running content) · 1126 (bounced, BUG 27)
· 1129 (fixed gate — created). Zero duplicates across four sends — identity resolution
held throughout. Step 8 (delete/mark the canary contact) is the operator's.

**Phase 23 is COMPLETE.** Its walking skeleton has now proven every leg live: install,
conversational trigger, preview, refusal, disarmed default, armed create, and the window
ceremony that opens and provably closes.
