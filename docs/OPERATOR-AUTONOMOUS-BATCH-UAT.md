# Operator UAT — the first live autonomous batch

**Written 2026-09-09.** What 57-05 Task 4 authorised, and nothing more: a **SMALL,
OPERATOR-SUPERVISED** first live batch. The unattended gate (a run nobody watches, or a
scheduled/cron run) stays shut; `ALLOW_N8N_ARM` is not part of this UAT. "Supervised" here
means you watch. Autonomy is ON by default since client `0.41.0`, so the round will not ask
before spending or writing — the seven-second pause is the only stop. Both facts hold at once.

Lane under test: **`enrich-before-ingest`** from a spreadsheet — Phase 61's batch pipeline
(match → enrich → preview → write → held rows → end-of-run report) with Phase 67/68's posture
on top. A second, optional round covers `suggest-contacts` → `suggestion-declines` (Phase 69).

Everything here is read-only for the assistant. Nothing in this session arms, spends, or
writes; every command that could is yours to run.

---

## 0. State as read on 2026-09-09 (read-only, plugin key)

| Fact | Value | Source |
| --- | --- | --- |
| Installed plugin | **`0.40.0`** — no autonomy levels, no pause, no drain skill | `~/.claude/plugins/installed_plugins.json` |
| Marketplace clone | `0.42.0` (fetched 2026-09-08) | `~/.claude/plugins/marketplaces/lightning-visuals-operator` |
| `allow_write_grants` | `true` | `operator.local.json` |
| `autonomy` key | absent → `read_only`, `spend_no_write`, `write` all ON | `config_gate.autonomy_enabled` |
| `n8n_monthly_execution_allowance` | `2500`; sampled spend **70**, remaining **2430** (159 h window, listing exhausted, not the billing quota) | `write_grant.allowance_headroom` |
| `max_records_per_chunk` | `2` | `operator.local.json` |
| Live enrichment `950HPb7a1GgSAIyZ` | active; `ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE` both `"false"`; last execution `12123` (2026-09-03) | `status.describe_workflow` |
| Live contact ingest `AwbBeShdPgV48eiY` | active; both flags `"false"`; last execution `12121` | same |
| Committed vs live JSON | Phase 62 deployed 2026-09-02 (`63-DEPLOY-RECORD.md`). **Phase 66 and quick 260904-5a8/-pav (all 2026-09-04) are committed, NOT deployed** — live `updatedAt` 2026-09-03 | git + n8n API |
| Provider balances | not readable from this session (`.env` is permission-blocked) | — |

Guardrail A (dirty-backend refusal) will pass: both flags read `"false"` at rest.

---

## 1. Preconditions — you run these

### 1a. Update the client

In Claude Desktop, **Update** `operator-claude-plugin` to `0.42.0`. Then:

> `/operator-claude-plugin:initialize`

Expect: setup already complete, nothing changed, settings file at
`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`.
If it reports `0.40.0` anywhere, the update did not land — refresh the clone again and retry.

### 1b. Read provider balances and the deploy diff (zero writes)

```
! set -a; . ./.env; set +a; .venv/bin/python scripts/check_provider_credits.py
! set -a; . ./.env; set +a; .venv/bin/python scripts/deploy_n8n_workflows.py
```

Expected: Lusha and ZoomInfo print a number; **Apollo prints `credits: None`** (the key is
not a master key, so the balance is unreadable — a standing fact). The round will later say
that balance is `unconfirmed` and proceed; that line is itself a UAT check (test 5 below).
The deploy dry-run should name the five `wf_*_cloud.json` for update, zero create, no
`REFUSED` line.

**Read 2026-09-09 (operator ran it):** `lusha: credits=3866 status=200`,
`apollo: credits=None status=200`, `zoominfo: credits=9371 status=200`. Dry-run named all
five for update, zero to create, no `REFUSED` line.

### 1c. Decide the backend version

Two options. Recommended: **A**, because the client is `0.42.0` and its report reads a
field only Phase 66's backend stamps.

- **A — deploy Phase 66 + 5a8/pav disarmed, then bounce.** Same commands `63-DEPLOY-RECORD.md`
  recorded; overlay flags stay `{}` so nothing baked is armed:

  ```
  ! set -a; . ./.env; set +a; DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python scripts/deploy_n8n_workflows.py
  ```

  Then bounce all five (deactivate → activate) and re-read the two write flags — they must
  still be `"false"`. Ask the assistant to re-read them; that is read-only.

- **B — test against the 2026-09-03 backend.** Valid, but expect every row's
  `contactability` in the step-9 report to read `unknown`, the companies gate to chase only
  `lv_org_type`/`lv_produces_content`, and no `lv_linkedin_url` candidate. Record which
  backend ran in the UAT file either way.

### 1d. Build the spreadsheet — 3 or 4 real rows, chunk cap 2 gives two chunks

Headers are the canonical props `contact-upload` reads. Pick real people with **published**
addresses, as the pair walk did; never invent an email. Keep `jobtitle` clear of the
substrings `secret` and `arm` ("Secretary", "Armidale") — the inherited forbidden-name
marker would refuse to persist that person if they are held (tracked todo, 2026-09-08).

```csv
firstname,lastname,company,email,jobtitle,company_id
<first>,<last>,<company already in HubSpot>,<published email>,<title>,
<first>,<last>,<company NOT in HubSpot>,<published email>,<title>,
<first>,<last>,<company already in HubSpot>,,<title>,
```

| Row | Path it exercises | Expected end state |
| --- | --- | --- |
| 1 | company resolves by domain/name → contact created **associated** (§13.0.1) | `written`, HubSpot id, associated |
| 2 | company absent → create is **downgraded to review, never landed** (§13.0.1, Phase 61-06) | `review`, `lv_enrichment_needs_review=true`, not in HubSpot |
| 3 | name+company identity, no email → provider reveal spends credit; if none found → `hold_emailless` holds it | `written` with revealed email, or `held: no usable email` |
| 4 (optional) | a contact already in HubSpot → step 3 proposes the match | `approve` at step 3 → update path |

Save as `uat-batch-2026-09-09.csv` somewhere outside the repo. Name the people so you can
find and hand-delete them in HubSpot afterwards — **HubSpot has no rollback.**

Expected spend for the whole batch: ~2–4 provider credits (Lusha 1/contact, 2/company),
one Anthropic call per unmatched company, roughly 8–15 n8n executions.

---

## 2. The run — say this, watch for that

Open a fresh conversation (a grant lives only in a conversation; nothing carries over).

> `/operator-claude-plugin:enrich-before-ingest`
>
> Enrich and load `<path>/uat-batch-2026-09-09.csv`.

Which asks remain and which vanished, so you can tell a preserved gate from a regression:

| Step | Still asks? | What you should see |
| --- | --- | --- |
| 1 | no | `python3 scripts/config_gate.py` → `"ok": true`, `"target"` = your n8n URL, `"can_send": true`. It names the three touches (unarmed search, provider waterfall, ingest write) and says **all three lanes** are covered by one grant. |
| 2 | no | rows resolved, unarmed HubSpot search; row 2's company reported absent, row 1's resolved by domain or exact name. |
| 3 | **yes — preserved decision point** | the numbered match table. Answer per row: `1. approve`, `4. approve` (if you added row 4), `2. deny` if it proposes a wrong candidate. A bare "approve all" is refused; `approve all 3` is accepted. |
| 4 | no | cost preview: providers from your settings (`zoominfo`, `apollo`, `lusha`), credits and tokens, chunk plan of **2 chunks** at cap 2. |
| 5 | **no — states, pauses, proceeds** | see test 5. |
| 6 | no | the enriched preview, rows marked SEND FIRST / HELD. |
| 7 | no (under the grant) | see test 7. |
| 8 | n/a | only on a broken batch. |
| 9 | no | the end-of-run report block, verbatim. |

The **only** way to stop the round after step 3 is to interrupt inside the pause at step 5,
or to interrupt later, which refuses the **next** send while the chunk in flight finishes
(D-59-06, FLOW-05). Try the second once if you want to see it; it costs one resume.

---

## 3. Tests — record expected / result / evidence

### Test 1 — the client is `0.42.0` and autonomy is ON
- expected: step 1 says the batch will **not** ask before spending or writing (autonomy
  `write` on), names `autonomy.write` in `operator.local.json` as the off switch.
- evidence: quote the sentence.

### Test 2 — Guardrail A sees a clean backend
- expected: no dirty-backend refusal at step 5; both flags were `"false"` before the run.
- evidence: the assistant's pre-run `describe_workflow` read (section 0).

### Test 3 — the match gate is preserved
- expected: step 3 renders one numbered table and waits; nothing spends before your answer.
- evidence: the table, your answer lines, no provider call before it (execution list).

### Test 4 — the chunk plan matches the cap
- expected: 2 chunks for 3–4 rows at `max_records_per_chunk: 2`.
- evidence: the step-4 plan.

### Test 5 — state, pause, open, proceed (D-68-01/03, D-67-09)
- expected, in this order: the grant block (`proposal["envelope"]["block"]`) with the row
  count and the distinct-company figure; `Execution ceiling:` either a number or
  `**unconfirmed**` plus the one-sentence disclosure; Apollo's balance printed
  `unconfirmed`, never read as headroom; a visible pause of about **7 seconds**; then the
  grant opens with **no question**.
- evidence: timestamps of the price line and the next line; the block verbatim.
- failure looks like: a question ("shall I proceed?"), no pause, or a pause under 5 s.

### Test 6 — the interrupt window is real (optional, costs one resume)
- expected: an interrupt inside the pause stops the round **before** `open_grant`; the
  execution list shows no provider call; re-running asks nothing new — it states again.

### Test 7 — the write is armed per send and disarmed after
- expected: each send opens its own record-scoped window; after the run both flags read
  `"false"` again; the ceiling statement names what it bounded.
- evidence: the assistant's post-run `describe_workflow` read; the disarm verdict in the
  step-9 report.

### Test 8 — outcomes per row (§13.0.1)
- row 1 `written` with a HubSpot id and an association; row 2 `review` and absent from
  HubSpot; row 3 `written` with a revealed email **or** held by name with reason
  `no usable email`; row 4 updated, not duplicated.
- evidence: HubSpot ids from the report; a HubSpot search for row 2's email returns nothing.

### Test 9 — the end-of-run report is the whole account (AFTER-01, D-67-11)
- expected: `report["block"]` rendered verbatim; one `run_id` across every leg; written
  records by id; held rows by name and reason; spend vs ceiling with the unreadable
  balance named; disarm verdict; `REPORT INCOMPLETE` banner absent (or present with the
  store it could not read named); `contactability` counts present (backend A) or all
  `unknown` (backend B).
- evidence: the block, saved verbatim into the UAT file.

### Test 10 (optional, second round) — declines survive the round
- `/operator-claude-plugin:suggest-contacts` on one company whose only findable person has
  no public email → the end of round names the backlog → `/operator-claude-plugin:suggestion-declines`
  → `defer` → confirm they reappear; then `export` → open the CSV → `company_id` present.
  No credit needed for the drain itself.

---

## 4. After the run — what the assistant will verify, read-only

None of these arm or write. Say "verify the UAT run `<run_id>`" and the assistant runs:

```
.venv/bin/python - <<'EOF'
import sys, json; sys.path.insert(0, 'operator-claude-plugin/scripts')
import config_gate, status, n8n_read, held_queue, suggestion_declines, written_records
cfg = config_gate.load_config()
for wid in ("950HPb7a1GgSAIyZ", "AwbBeShdPgV48eiY"):
    d = status.describe_workflow(cfg, wid)
    print(wid, {k: v["value"] for k, v in d["write_safety"].items()}, d["last_run"]["execution_id"])
w = n8n_read.executions_in_window(cfg, window_hours=6)
print("executions in window:", w["count_in_window"], "listing_exhausted:", w["listing_exhausted"])
print("written:", json.dumps(written_records.load(path=written_records.written_records_path("<run_id>")), default=str)[:800])
print("held:", held_queue.classify_read(), "declines:", suggestion_declines.classify_read())
EOF
```

Plus a `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` to prove the client
that ran is the client that was tested.

Record the result as `.planning/UAT-autonomous-batch-2026-09-09.md` (GSD UAT shape:
status, tests with expected / result / evidence, `run_id`, execution ids, HubSpot ids, the
step-9 block verbatim, which backend ran). The one open `audit-uat` row (16.9 SC-3, a
companies-lane update reaching HubSpot with 2xx) is **not** discharged by this contacts-lane
run; a company update in the optional second round would discharge it — note the execution
id if it happens.

## 5. Clean-up

Hand-delete the UAT contacts in HubSpot (and the company, if the second round created one).
Note their ids in the UAT file first. Nothing in the client deletes records.
