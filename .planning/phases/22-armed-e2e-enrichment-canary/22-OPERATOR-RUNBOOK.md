# Operator Runbook — the consolidated armed window (Phase 20-22)

This runbook closes every armed operator action this milestone has accumulated across
three phases, in the one order they must happen. It extends the ceremony
`19-OPERATOR-RUNBOOK.md` (`.planning/milestones/v0.4-phases/19-verification-debt-closure/19-OPERATOR-RUNBOOK.md`)
already proved for a single `company:update` canary — arm, fire once, read back, restore
disarmed, read the deployment back — and reuses the exact deploy-time overlay mechanism it
used (`_OVERLAY_FLAG_SPEC` / `enable_baked_flags()`, `scripts/deploy_n8n_workflows.py`).

Everything in this document is either read-only or explicitly the one operator-only
armed action a section performs. Armed HubSpot schema writes, armed HubSpot record
writes, and armed n8n deploys are all classifier-blocked for agents in this environment
(confirmed twice: Phase 20 Plan 04's own attempt, and again in Phase 21) — this whole
window is yours to run.

## Scope

- **Companies/properties touched:** the Lusha id staging properties (`lusha_contact_id`
  on contacts, `lusha_company_id` on companies — Section A), one disposable probe
  property that never collides with a real field (Section B), and `lv_org_type` itself,
  the phase's one true one-way door (Section C).
- **Records touched:** the standing test fixtures used throughout this project —
  company `9604614548` (Melbourne Racing Club) and contact `201` — plus the probe's own
  disposable property on that same test company (Section B never touches a second
  company). The canary (Section D) arms exactly ONE allowlisted record.
- **Write flag armed for the canary:** `ALLOW_HUBSPOT_RECORD_WRITES` only, allowlisted to
  `TEST_RECORD_IDS=9604614548`. `ALLOW_HUBSPOT_CREATE` stays untouched throughout this
  entire runbook — nothing in this milestone's success criteria needs a `company:create`
  or `contact:create` path, and arming an unneeded write-enabling flag widens risk (a
  wrong record could be *created* as well as updated) for no verification value. Do not
  add it to any `ENABLE_BAKED_FLAGS` invocation below.
- **Two sittings, not one.** Sections A and B are prerequisites this session can close
  today; Section B's probe ladder produces the verdict block Phase 21 Plan 04's rollback
  runbook and migration script are built FROM — that build is agent work that happens
  between the two sittings (the "agent interlude" below), not something this document
  can run ahead of. Sections C and D are the second sitting, run back to back once the
  interlude is done.

## Command form

Every live command in this document runs through the same in-process `python-dotenv`
wrapper `19-OPERATOR-RUNBOOK.md` established, from the repo root:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/<script>.py', run_name='__main__')" [trailing CLI args]
```

- `load_dotenv()` defaults to `override=False`: any variable already set in the shell
  (`DRY_RUN=false`, `ALLOW_N8N_DEPLOY=true`, `ALLOW_HUBSPOT_PROPERTY_WRITES=true`,
  `ENABLE_BAKED_FLAGS=...`) WINS over `.env`. `.env` only fills in what the shell didn't
  set — the credentials. `.env`'s own `DRY_RUN=true` cannot un-arm a shell-set
  `DRY_RUN=false`.
- Run every command from the repo root — the relative `scripts/` path and `.env`
  discovery both assume it.
- Trailing arguments after the closing quote of the `-c "..."` string become that
  script's own `sys.argv[1:]`, so its `argparse` parser sees them normally (the same
  form `20-01-PLAN.md`'s live Lusha probe command used with `--out`). Use this to pass
  `--label`, `compare --snapshot PATH`, `--allowlist`, and so on to the scripts below.
  None of these scripts call `load_dotenv()` themselves, so always use the wrapper — a
  bare `python scripts/foo.py` from a fresh shell silently sees no credentials and skips.
- **Confirm whose key is in `.env`'s `N8N_API_KEY` before ANY deploy command below.**
  API-created workflows land in the key owner's n8n project. It must be Robert's key
  (Alex's key is retained separately as `N8N_API_KEY_2`) — a wrong key silently deploys
  into the wrong project (this has already cost a full deploy cycle once, per
  `19-OPERATOR-RUNBOOK.md`'s precedent).

---

# SITTING 1 — Prerequisites (Sections A and B)

## Section A — Lusha id staging properties (Phase 20 Plan 04)

Source: `20-04-SUMMARY.md`, "Pending Operator Actions". These two properties
(`lusha_contact_id`, `lusha_company_id`) are read by the already-shipped stored-id-reuse
code the moment they exist live — no code change is pending, only the schema create.

**A1 — dry run.** Confirm the diff is still exactly 2 creates, 0 updates, 0 deletes:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/sync_hubspot_properties.py', run_name='__main__')"
```

Expected output:

```
DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_WRITES=true to create.

=== companies ===
Groups to create: []
Properties to create (1): ['lusha_company_id']

=== contacts ===
Groups to create: []
Properties to create (1): ['lusha_contact_id']
```

If this differs (a different count, an update, a delete), STOP — the live schema has
drifted since Phase 20 was planned; do not arm against an unexpected diff.

**A2 — arm.** Both keys in the same invocation:

```bash
DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/sync_hubspot_properties.py', run_name='__main__')"
```

Confirm the script printed 2 created and wrote an undo manifest under
`config/hubspot_migration/` — note the manifest filename (the rollback path for this
section).

**A3 — read-back (distinct step).** Independently confirm the schema, not the script's
own exit code:

```bash
.venv/bin/python scripts/snapshot_hubspot_schema.py
```

Confirm `lusha_contact_id` exists on contacts and `lusha_company_id` exists on
companies, both single-line text, in the expected groups (`lv_enrichment_contacts` /
`lv_enrichment`), both lowercase as created.

No record write happens in this section — do not set any record-write or create flag
here.

## Section B — org-type probe ladder (Phase 21 Plan 03)

Source: `21-03-PLAN.md` Task 3. **Phase 21 Plan 04 cannot be built until this section's
verdict block exists** — the rollback runbook and the migration script are written FROM
these verdicts, not from research assumption. This is the one section whose output the
agent needs back before anything downstream can be built.

**B1 — review before arming.** From the repo root:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/probe_org_type_migration.py', run_name='__main__')"
```

This is the dry run (the default) — it prints all 9 steps with every URL, method and
body and makes zero calls. Read it. Confirm the only property name it will create,
patch or archive is the double-underscored probe constant
(`lv__phase21_org_type_probe`), and that the only record it touches is the designated
test company.

**B2 — confirm the allowlist.** Confirm the environment names a test company that is in
`TEST_COMPANY_IDS` — the script refuses otherwise. Do not point it at a real account.

**B3 — arm.** Both keys in the same invocation:

```bash
DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/probe_org_type_migration.py', run_name='__main__')"
```

**B4 — verdict block (paste back verbatim).** Read the `=== VERDICT ===` block the
script prints and paste it back to the agent session verbatim — every line matters, in
particular the reverse-PATCH line, which decides whether Section C's migration has a
cheap rollback or an expensive one.

**B5 — residue check (independent read-back).** Confirm the script's own final
residual-state line reports nothing left behind, THEN independently confirm:

```bash
.venv/bin/python scripts/snapshot_hubspot_schema.py --label post-probe
```

Check the probe property name does not appear in the companies snapshot. If it does,
say so before proceeding — that residue must be removed before Section C or D runs.

**B6 — inventory check.** Confirm the committed inventory artifact's out-of-vocabulary
count (`config/hubspot_migration/org_type_inventory-*.json`, from Plan 03 Task 2). If
non-zero, decide now how those records are remediated (map to a canonical key, or to the
default) — Section C's migration will refuse to run live while any remain.

**End of Sitting 1.** Paste B4's verdict block and B5/B6's findings back to the agent.

---

## [Agent interlude — not run by the operator]

Between Sitting 1 and Sitting 2, the agent builds Phase 21 Plan 04's Task 1
(`docs/ORG-TYPE-ENUM-MIGRATION.md`, the rollback runbook, authored from Section B4's
verdict — never before it exists) and Task 2 (`scripts/migrate_org_type_enum.py`, the
gated migration script, structurally refusing to arm without that runbook's four
markers and a clean inventory). Both are `type="auto"` work with offline-tested gates —
no armed action happens during the interlude. Phase 21 closes its own Plan 04 the same
way this phase closes Plan 04: with an operator checkpoint. This runbook's Section C
below IS that checkpoint, folded into the same sitting as Section D so the whole
milestone's remaining armed debt closes in one session instead of three.

---

# SITTING 2 — Section C (migration) then Section D (canary)

**Decision recorded (Task 2 of this plan, resolved by the orchestrator — not re-opened
here): `migrate-first`.** The `lv_org_type` text-to-enumeration conversion runs to
completion in this sitting, BEFORE the canary in Section D fires. Rationale: the
canary's second success criterion requires proving writes succeed against the migrated
enum, not merely against the old free-text property — a canary fired before the
migration would pass mechanically without testing anything new about the schema. The
alternative (defer the migration past this canary, mark that half of criterion 2
deferred) was rejected because Sections A/B/the interlude have already produced
everything the migration needs (verdict, runbook, gated script) — deferring at this
point would trade a settled, evidence-backed conversion for an open gap with no
remaining reason to leave it open. Section C therefore runs to completion, in its own
right, before Section D's Step 0 begins.

## Section C — org-type enum migration (Phase 21 Plan 04)

Source: `21-04-PLAN.md` Task 4. Do not run any part of this section until the interlude
above has produced `docs/ORG-TYPE-ENUM-MIGRATION.md` and `scripts/migrate_org_type_enum.py`
— read the rollback document in full before arming anything; it is what a rollback reads,
not this runbook.

**C1 — pre-migration baseline.**

```bash
.venv/bin/python scripts/snapshot_hubspot_schema.py --label pre-orgtype-enum
```

Confirm the companies snapshot shows `lv_org_type` as type `string`, fieldType `text`,
with an empty options list. This file is the rollback's diff target.

**C2 — re-run the inventory** so the migration's pre-flight gate reads a current
artifact (it may have gone stale since Plan 03):

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/inventory_org_type_values.py', run_name='__main__')"
```

Confirm the out-of-vocabulary count is zero. If it is not, stop and remediate those
records first — the migration will refuse anyway.

**C3 — review the dry run.**

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/migrate_org_type_enum.py', run_name='__main__')"
```

Confirm the printed body's option values are exactly the nine taxonomy keys, all
lowercase, and that the target property named is the real `lv_org_type` property (this
is the one script in this whole runbook that legitimately names it).

**C4 — arm.** Both keys in the same invocation, and answer the script's typed
confirmation:

```bash
DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/migrate_org_type_enum.py', run_name='__main__')"
```

Note the manifest filename it prints — that is the rollback's input.

**C5 — independent read-back (distinct step, not the script's exit code).**

```bash
.venv/bin/python scripts/snapshot_hubspot_schema.py --label post-orgtype-enum
```

Diff this against C1's `pre-orgtype-enum` snapshot. The ONLY difference should be
`lv_org_type`'s type, fieldType and options. Anything else changing is a finding —
report it before proceeding to Section D.

**C6 — value-count diff.** Re-run the inventory and diff its value counts against the
pre-migration artifact (Plan 03's committed one):

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/inventory_org_type_values.py', run_name='__main__')"
```

Every in-vocabulary value's count should be unchanged.

**C7 — enforcement smoke test**, on the designated test company only: write a canonical
`lv_org_type` value directly and confirm it succeeds, then write a deliberately invalid
value and confirm HubSpot rejects it (a 400, not a silent store). Restore the test
company's original `lv_org_type` value afterwards. This is the direct evidence for "the
enumeration actually enforces, it doesn't just decorate" — Section D's canary depends on
this being true, not merely dry-run-reviewed.

Paste back to the agent: the C5 diff (or "only type/fieldType/options changed"), the
manifest filename, the C6 value-count comparison, and the two C7 smoke-write results.

**If any gate in Section C refuses** (runbook markers missing, inventory non-zero,
portal mismatch): STOP. Do not proceed to Section D. A migration that cannot arm is not
a migration that ran, and Section D's second success criterion has no evidence to stand
on until Section C actually lands.

---

## Section D — the armed canary (this phase, Phase 22 Plan 04)

Section D fires only after Section C has completed and been independently read back.

### Step 0 — disarmed redeploy + three read-backs

Redeploy the current committed build with NO write-enabling overlay at all — a plain
disarmed redeploy that also closes any deployment-drift gap (this repo has found the
live deployment behind git at least once in every phase to date — Phase 19's BUG 26 —
which is why this step is never optional):

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

Then run all three read-backs. **All three must pass before anything is armed:**

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_lusha_urls.py', run_name='__main__')"
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_no_native_search.py', run_name='__main__')"
```

Expect `VERDICT: disarmed PASS` from the first, zero v2 Lusha URLs from the second, and
zero native search nodes from the third. If any fails, STOP — the deployment is not
current, and a canary against a stale artifact proves the wrong thing.

### Step 1 — pre-canary snapshot and the research-gate branch

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/canary_record_snapshot.py', run_name='__main__')" snapshot --label pre-canary
```

Keep the printed artifact path (under
`.planning/phases/22-armed-e2e-enrichment-canary/snapshots/`) — Step 5 compares against
it. Read the `research_gate_will_fire` line.

**Branch explicitly:**

- **If `research_gate_will_fire: true`** — proceed to Step 2. (This was the live-observed
  state as of 22-01's own pre-canary read on company `9604614548`: `lv_org_type` and
  `lv_produces_content` were both still blank, so the gate fired. If time has passed
  since 22-01 and something else populated those fields, this snapshot is the fresh
  source of truth — trust it, not the 22-01 finding.)
- **If `research_gate_will_fire: false`** — proceeding would let the canary pass
  mechanically without ever exercising the Haiku-research-then-Sonnet-judge chain the
  first success criterion names. Proceeding without one of the two branches below is
  **not a third option** — it is a run whose first success criterion cannot be claimed.
  Note also: several org-type values are evidence-gated (fire research even when
  populated) per the gate's own predicate — trust the tool's `research_gate_will_fire`
  verdict, not intuition about whether the field "looks filled in." Take ONE of:

  - **Branch 1 — blank the governing fields on the allowlisted company, then
    re-snapshot.** Direct operator PATCH (bypassing the pipeline; this is a manual
    HubSpot UI or `hs_client.patch_record` action against `9604614548`'s
    `lv_org_type`/`lv_produces_content` fields, blanking both), then re-run:
    ```bash
    .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/canary_record_snapshot.py', run_name='__main__')" snapshot --label pre-canary
    ```
    Confirm `research_gate_will_fire: true` on the re-snapshot before proceeding.
  - **Branch 2 — pick a different allowlisted company whose fields are still blank.**
    Add its id to `TEST_COMPANY_IDS` if not already present, then:
    ```bash
    .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/canary_record_snapshot.py', run_name='__main__')" snapshot --label pre-canary --target-id <other-allowlisted-company-id>
    ```
    Every subsequent step in Section D that names `9604614548` uses this id instead, and
    Step 3's `TEST_RECORD_IDS` overlay value uses this id instead.

### Step 2 — credit baseline

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" credits --label pre-canary
```

Keep the printed snapshot path — Step 6 diffs against it.

### Step 3 — arm

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=9604614548" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

Syntax notes (`_OVERLAY_FLAG_SPEC`/`_requested_overlay_flags()`,
`scripts/deploy_n8n_workflows.py`):

- `ALLOW_HUBSPOT_RECORD_WRITES` is a bare boolean kill switch — write it with no
  `=value`. It rewrites the baked `"false"` literal to `"true"`.
- `TEST_RECORD_IDS=9604614548` supplies the allowlist value. The script REFUSES to arm
  any write-enabling flag unless the SAME `ENABLE_BAKED_FLAGS` invocation also supplies a
  non-empty `TEST_RECORD_IDS` and/or `TEST_RECORD_DOMAINS` — enforced code, not
  convention (`_requested_overlay_flags()`'s "refusing to enable HubSpot writes without
  an allowlist" `ValueError`).
- A hypothetical multi-record window would separate ids with `|`, not `,`
  (`TEST_RECORD_IDS=id1|id2`) — `,` already separates entries within
  `ENABLE_BAKED_FLAGS` itself. Not needed for this single-record canary.
- `ALLOW_HUBSPOT_CREATE` is deliberately NOT included, per the Scope section above. Do
  not add it.

The deploy's own printed output confirms the rewrite count before any write happens — a
count of 0 for either flag means the script REFUSES and deploys nothing.

**Step 3b — armed read-back (distinct step, required before firing).** The deploy
command's own exit code is NOT this proof:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation armed --allowlist 9604614548
```

Confirm `VERDICT: armed PASS` before proceeding to Step 4. If it fails, do not fire —
return to Step 3.

### Step 4 — fire exactly once

```bash
curl -sS -X POST "$N8N_URL/webhook/hubspot/enrichment/event" \
  -H "Content-Type: application/json" \
  -H "X-Enrichment-Secret: $N8N_ENRICHMENT_WEBHOOK_SECRET" \
  -d '[{"objectId": 9604614548, "objectType": "company", "subscriptionType": "company.propertyChange", "propertyName": "enrichment_requested", "propertyValue": "true", "occurredAt": 1783316400000}]'
```

(`$N8N_URL` is the base URL, no trailing slash, e.g. `https://<subdomain>.n8n.cloud`; the
webhook path is fixed at `/webhook/hubspot/enrichment/event` per the deployed `Webhook
Trigger` node. `$N8N_ENRICHMENT_WEBHOOK_SECRET` is the same secret provisioned into the
webhook's Header Auth credential — never logged, never pasted into the ledger.)

Exactly ONE event is sent. **A second fire is a new window, not a retry** — if this POST
fails or times out ambiguously, read the record and the executions list before firing
again; do not fire twice to "make sure."

Capture the execution id:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" list
```

Note the most recent execution id for the company lane — this is what Steps 5 and 6 read.

### Step 5 — read back the run

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/canary_record_snapshot.py', run_name='__main__')" compare --snapshot <Step 1's pre-canary snapshot path>
```

Prints the target's field diff and the neighbour verdict (`neighbors_changed`). **A
non-zero neighbour count is an immediate abort to Step 7** — capture the diff before
doing anything else; this is the one outcome this phase exists to rule out.

Then confirm the complete chain actually ran, not just that a write landed:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" extract --execution-id <Step 4's execution id>
```

Confirm `Claude Web Research` and `Judge Call` both show `status=ran` with populated
usage counters. A write landing is not, by itself, evidence the research+judge lanes
executed.

### Step 6 — the ledger

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" credits --label post-canary --settle
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" report --before <Step 2's pre-canary credits snapshot path> --after <this step's post-canary credits snapshot path> --execution-id <Step 4's execution id> --record-count 1
```

Transcribe the report's three printed blocks (Provider credits / Anthropic usage per
call / Totals) into `22-LEDGER.md`'s Cost Table, and the Step 0/3b/5/7b pass/fail
outcomes into its Criterion Ledger — flip every `not-yet-observed` cell to the real
observed value.

### Step 7 — disarm

Redeploy the SAME committed build with the overlay removed ENTIRELY — not an empty
overlay, no `ENABLE_BAKED_FLAGS` at all:

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

**Step 7b — disarmed read-back (distinct step, this run's closing gate):**

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
```

Confirm `VERDICT: disarmed PASS`. The window is not closed until this passes.

---

## Pass / fail condition

- **Pass:** Step 0's three read-backs all passed before arming; Step 1 resolved
  `research_gate_will_fire: true` (directly or via a branch); Step 3b's armed read-back
  passed before firing; exactly one event fired; Step 5's neighbour count is zero and
  the research+judge nodes show `status=ran`; the ledger (Step 6) recorded a per-record
  figure; Step 7b's disarmed read-back passed.
- **Fail:** any of Step 0's read-backs failed; the research gate would not fire and
  neither branch was taken; Step 3b failed but firing proceeded anyway; the neighbour
  count is non-zero; the research/judge nodes never ran; or Step 7b shows writes still
  armed.

## Abort path

If anything goes wrong at any point after Step 3 (armed): **disarm first, always,
before diagnosing anything.** Run Step 7 (disarm) and Step 7b (disarmed read-back)
immediately. Only once Step 7b passes, capture evidence of what went wrong (the Step 5
diff, the execution's `runData`, the Step 3b/7b verdict lines) and report it. A window
left armed while being debugged is a worse failure than the original problem.

## Where the outcome is written

The window's outcome — every criterion row and every cost-table row — is written into
`22-LEDGER.md`, this phase's canonical evidence document. Each row names the roadmap
criterion it corresponds to and the exact command whose output is its evidence; nothing
in this runbook substitutes for filling that document in.
