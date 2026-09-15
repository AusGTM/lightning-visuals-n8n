# Stress-test runbook — end to end (end-client session)

Assets: `tests/stress-tests/uat-stress-mixed-batch-2026-09-13.csv` (contacts, 48 rows,
gitignored), `tests/stress-tests/uat-stress-companies-2026-09-14.csv` (companies, 36 rows),
`README.md` (row maps + expected outcomes), `scripts/uat_reset.py` (reset). Everything the
operator does in the session is said to Claude in plain words; the `!` lines are the only
terminal steps and every one of them runs from the repo root.

Rules that hold throughout: nothing writes to HubSpot without a write grant you open by
name for that batch; every send disarms itself; never paste a Webhook Trigger runData block
into anything (it carries the webhook secret); every "verified" claim is a re-read of the
record, never a 200.

---

## T-1 day — pre-flight (operator alone, ~20 min)

1. **Plugin version.** Restart Claude Code, then `claude plugin list` → `operator-claude-plugin` 0.49.1 or later.
2. **Config.** Say *"Is the plugin configured?"* → expect *already set up*. `allow_write_grants` must be `true` in `operator.local.json` (admin key). Leave `enrichment_providers` at the full waterfall; the session overrides per batch.
3. **Backend level and disarmed.**
   ```
   ! set -a; . ./.env; set +a; python3 scripts/verify_live_write_safety.py
   ```
   Expect `disarmed PASS` on every declaring node in all five workflows. If anything reads armed, STOP — disarm + bounce before the session (`scripts/bounce_n8n_workflows.py` exits 1 while armed).
4. **Status baseline.** Say *"What's the backend doing?"* Record: all five workflows on, nothing running, Lusha and ZoomInfo credits, the latest execution id. Write these on the session sheet — they are the deltas you report at the end.
5. **Leftovers.** Confirm the Phase 72 UAT contact `352522004980` is gone (restorable-delete if not). Row 2 of the contacts CSV (Busteed) is designed to create-or-match; either is a pass.
6. **Snapshot — mandatory, before any company is created.**
   ```
   ! set -a; . ./.env; set +a; python3 scripts/uat_reset.py --snapshot --companies-csv tests/stress-tests/uat-stress-companies-2026-09-14.csv
   ```
   Expect roughly 6 of 32 domains reported *protected* (ATC, MRC, BRC, Perth Racing, Racing Victoria, and HRNSW only if filed under `hrnsw.com.au`). The snapshot file lands next to the CSV and is gitignored. Without it the reset refuses to run.
7. **Budget.** Whole session ≈ 60–90 n8n executions of the 2,500/month plan; provider spend is bounded to Stage D and Stage C sends. Have the client confirm both figures before you start.

---

## Session (~90 min with the client)

### Stage A — contacts, shape only, no provider spend (~15 min)

Say: *"Load `tests/stress-tests/uat-stress-mixed-batch-2026-09-13.csv` into HubSpot, no providers."*

Preview must show:
- 48 rows, 14 headers mapped, `UAT Marker` unresolved and dropped, `Mobile` → Mobile Phone.
- Rows 35–36 refused (malformed email); rows 37–38 collapsed onto row 3 (case-insensitive).
- Row 39 (name only) and rows 31–34 (LinkedIn only) queued for review; rows 41–42 (org not in portal) held; row 40 (gmail) held.
- Cost line: 0 provider credits, $0 model spend.

Approve. Claude asks for the write grant (name the batch, worst-case spend shown, one yes). Autonomy is on: it states the price, pauses seven seconds, arms **that send only**, sends in chunks, disarms, and reports per record.

Verify by re-read (Claude does it; spot-check two in the HubSpot UI):
- Contact `1251` (Telfer): phone unchanged (`+61 2 9663 8400`), job title unchanged — SAFE-01.
- Any dense create (rows 3–14): Mobile Phone populated, LinkedIn URL in BOTH `lv_linkedin_url` and HubSpot's own LinkedIn field, city/state/country, seniority, persona; company association present.
- Row 43: `(08) 9277 0777` and `0421 555 210` normalised to `+61 …`.
- Held list names rows 31–34, 39–42 by person with a reason each.

Record: run id, execution id range, created / updated / held / refused counts.

### Stage B — companies batch (~25 min, provider + model spend)

Say: *"Enrich or create these companies"* and give `tests/stress-tests/uat-stress-companies-2026-09-14.csv`.

Domain table (one row per company) must show: rows 31–32 normalised (`vrc.com.au`, `thevalley.com.au`); row 33 deduped; row 34 (no website) proposed-or-research with its cost line; row 35 (LinkedIn page) **refused**, not proposed; row 36 (`gmail.com`) refused. Answer the table with one yes; strike domain research if the client does not want it costed.

Cost guard: ~30 companies × full waterfall (Lusha 2 credits/company; ZoomInfo ~1; Anthropic ≈ $0.07/record). Grant → dispatch at 2 companies per POST (~15 executions) → watch until settled.

Verify:
- Rows 1–6 **matched, not recreated** — HRNSW must match by name against `www.harnessmediacentre.com.au`. If a second HRNSW appears, that is a finding, stop and record it.
- Created companies carry `lv_org_type`, region, produces-content, and a tier: Daktronics and NYRA → `lv_anti_icp_flag` true, Tier D; Tabcorp → deduction only, no veto; Sky Racing → no veto.
- Wagga Wagga Rowing Club created (fictitious, will not enrich).
- Conflicting-provider companies land in `needs_review` with the field and sources named, never a silently promoted value (§15.0).

Record: execution range, created / matched / needs-review counts, per-tier tally.

### Stage C — suggest-contacts (~20 min, fetch budget + send cost)

Right after Stage B settles Claude offers *"Who's at these companies?"* for every created company with nobody named. Accept for the whole set, keep the default cap of 2 per company, take the offered role list.

Expect: crawl of each site's about/board/team pages; proposals with the source page beside each person; anyone found on an industry site **held**; own-site / LinkedIn proposals ready. Sites that refuse (robots, block) shut the search fallback for that company — the report says so per company. Wagga (no site) fails cleanly.

Send the ready proposals: same grant discipline as Stage A. Verify two created people by re-read: associated to the right company, email domain equals the company domain (or held with `email domain … does not match`).

Record: companies crawled / sites refused / proposals ready / held / sent.

### Stage D — enrich-before-ingest, providers on (~15 min, real spend — optional)

Say: *"Enrich these contacts before uploading them"* with the contacts CSV again. Purpose: rows 41–42 now associate to Wagga (created in B); held rows from A get a second, enriched pass; rows 1–2 (real people) exercise the waterfall — Busteed's email reveal is the known-good case (Lusha up to 7 credits).

Two yeses without a grant (before spend, before write), one with. Verify rows 41–42 landed with the association; fictitious rows report NOT_FOUND at 0 Lusha credits.

Skip this stage if the client declines provider spend; nothing later depends on it.

### Stage E — review queue (~10 min)

Say *"What needs review?"* Work three items: approve one (Claude shows the exact property write, your yes arms that one record, then it re-reads and confirms), reject one with a reason (record stays queued), leave one. Confirm the approved write by re-read.

### Stage F — status and sweep (~5 min)

*"What's the backend doing?"* — execution delta since baseline, nothing running long, nothing armed. *"Run the backend sweep"* — preview of the next unattended fire; expect silence-means-healthy or a named condition.

---

## Close-out (operator, ~15 min)

1. **Disarmed read-back.**
   ```
   ! set -a; . ./.env; set +a; python3 scripts/verify_live_write_safety.py
   ```
   Every node `disarmed`. If not: disarm, `python3 scripts/bounce_n8n_workflows.py`, re-read.
2. **Execution delta.** Latest execution id minus baseline; compare with the ~60–90 estimate. A number wildly above it is a finding, not a rounding error (2026-09-10 runaway precedent).
3. **Reset — dry run first, read every line, then execute.**
   ```
   ! set -a; . ./.env; set +a; python3 scripts/uat_reset.py --companies-csv tests/stress-tests/uat-stress-companies-2026-09-14.csv
   ! set -a; . ./.env; set +a; ALLOW_UAT_RESET=true python3 scripts/uat_reset.py --companies-csv tests/stress-tests/uat-stress-companies-2026-09-14.csv --execute
   ```
   The plan must NOT list `1251`, any snapshot-protected company, or any contact predating the snapshot. Every DELETE prints `204`; the JSON report lands next to the CSV. Deletes are restorable from HubSpot's recycle bin (HubSpot retains deleted records for a limited period; restore before the session report is filed if anything was wrong).
4. **Post-reset check.** Say *"What's the backend doing?"* once more; HubSpot search *email contains uat.* returns nothing; `1251` intact.
5. **Report.** Copy `.planning/phases/72-enrichment-extras-land-in-hubspot/72-UAT.md`'s shape: per stage the run id, execution range, counts, and a findings table (`F-S1..`) with severity. Never a runData block.

---

## Stop conditions (any time)

| Signal | Action |
| --- | --- |
| Executions climbing with no send in flight (>10 in a minute) | `POST /workflows/950HPb7a1GgSAIyZ/deactivate` on the n8n REST API (CLAUDE.md §13.0.3 — deactivate drains over ~30 s, not instantly); then disarm + bounce; record the id range |
| Any `ALLOW_*` flag reads armed after a send has finished | disarm, bounce, re-read before anything else |
| A HubSpot PATCH to an empty id / a `405` in a run | stop sends; that is the legacy-execution-order symptom — check `settings.executionOrder` is `v1` on the live body |
| Provider credits dropping faster than the cost guard stated | stop; compare the guard's figure with the provider dashboard before continuing |
| A second HRNSW / any duplicate company | stop Stage B; record; the dedupe rule is the finding |
| Client asks to keep any created record | exclude it from the reset plan by passing a later `--since`, or delete the rest by hand from the dry-run list |
