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
| Committed vs live JSON | **Level as of 2026-09-10 (Phase 70 Gate 10)** — the v1 bodies (30/69/287/55/43 nodes, `settings.executionOrder: "v1"`) deployed disarmed and bounced on all five (see 1c); Gates 11 and 12 passed on them. Re-read live before every batch — this row is a moment, not a standing fact | git + n8n API |
| Provider balances | not readable from this session (`.env` is permission-blocked) | — |

Guardrail A (dirty-backend refusal) will pass: both flags read `"false"` at rest.

**Re-read 2026-09-11 (read-only, plugin key, before the first supervised batch):**

| Fact | Value |
| --- | --- |
| Installed plugin | **`0.44.0`** (`installed_plugins.json`, lastUpdated 2026-09-10T17:20Z) — one behind |
| Marketplace clone | `0.45.0` at `65c9198` — Update in Claude Code, then restart, before 1a |
| `x-enrichment-secret` | rotated 2026-09-11, operator-confirmed (STATE.md, commit `e6594548`) |
| Live enrichment `950HPb7a1GgSAIyZ` | active; both write flags `"false"`; last execution `12356` (Gate 11, 2026-09-10) |
| Live contact ingest `AwbBeShdPgV48eiY` | active; both flags `"false"`; last execution `12363` (Gate 12 armed write, 2026-09-10) |
| Committed vs live JSON | level (Phase 70 Gates 10–12, commit `ec102a4`); no n8n JSON changed since |
| Executions, last 24 h | 15 listed, listing exhausted |
| `config_gate.py` | `"ok": true`, `"can_send": true` |
| Pending todos | 5, all triaged (§31) |

Section 1a's `0.42.0` target is stale: the current target is **`0.45.0`**.

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

**Read 2026-09-11 (operator ran it, plugin still `0.44.0` at this point):**
`lusha: credits=3860 status=200`, `apollo: credits=None status=200`,
`zoominfo: credits=9367 status=200`. Delta since 09-09: Lusha -6, ZoomInfo -4 (Gate 11/12
spend). Dry-run named all five for update, zero to create, no `REFUSED` line. The
"update" listing is expected on every dry-run — the diff always shows credentials/webhookId
noise — and is not evidence of a committed-vs-live gap (level per Gate 10).

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

  **Done 2026-09-09 (operator ran both):** five PUTs at 200; bounce table all active,
  live nodes 17/29/123/26/39 equal committed, write flags `['false']` on the four that carry
  them, `OK`. Independent read-back via the plugin key: `Build Response` carries
  `contactability`, `Company Gate` carries `lv_revenue_band`, `Enrichment Gate` carries
  `lv_linkedin_url`, `HubSpot Company Search` carries `num_associated_contacts`,
  `Merge Contacts` carries `sourceByField`, `SJ-2 Search (stale refresh)` keeps its narrow
  `REQUIRED`. Backend A is what the UAT runs against.

- **B — test against the 2026-09-03 backend.** Valid, but expect every row's
  `contactability` in the step-9 report to read `unknown`, the companies gate to chase only
  `lv_org_type`/`lv_produces_content`, and no `lv_linkedin_url` candidate. Record which
  backend ran in the UAT file either way.

### 1d. Build the spreadsheet — a MIXED batch by default: 4 real rows, 2 identity lanes x 2 actions

**Mixed lanes and mixed actions are the default shape of this batch, not a variation on it**
(Phase 70, D-70-17). The offline acceptance tests
(`tests/n8n/enrichmentMixedBatch.test.mjs`, `tests/n8n/ingestMixedBatch.test.mjs`) assert
exactly this shape, so a UAT batch that is all one lane proves something narrower than what
was tested. The two identity lanes on the ingest lane are the two company-resolution keys
CLAUDE.md §13.0.1 names — resolution by email DOMAIN and by exact company NAME — and the two
actions are update (the contact already exists) and the create path (it does not).

The chunk cap of 2 splits 4 rows into two chunks, which is the point: a mixed batch that
spans chunks is where a row can be dropped or double-reported, and where the ack-only
response contract (D-70-07 — the wire carries no rows; outcomes are read from runData) is
actually exercised.

**Also send ONE single-lane batch, separately.** The 2x2 shape exercises every lane by
construction and therefore cannot catch a convergence Merge waiting on an input that never
fires — the common real shape, and the failure mode the whole Phase 70 design rests on not
happening. Send 2 rows that all take the SAME path (both companies already in HubSpot,
resolving by domain, both contacts existing → both updates, review path empty). Record
whether the execution SETTLED or is stuck `running`. A stuck execution is a finding to
report, never something to work around. This is the same observation Gate 1 and Gate 3 in
`.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md`
ask for.

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
| 4 | a contact already in HubSpot, its company resolving by exact NAME (not domain) → step 3 proposes the match | `approve` at step 3 → update path, `company_match: "name"` |

Rows 1+3 are the domain lane, rows 2+4 the name lane; rows 1+4 are updates, rows 2+3 the
create path — 2 identity lanes x 2 actions, which is the D-70-17 shape.

**Every row must come back exactly once, matched by its own identity (its email), never by
position.** No duplicate, no missing row. That is the single assertion this batch exists to
make live, and it is the same one the two offline acceptance tests make.

**Built 2026-09-11 (assistant, read-only HubSpot probes + published web pages; nothing armed,
nothing written).** Files: `~/Desktop/uat-2026-09-11/uat-batch-2026-09-11.csv` (mixed, 4 rows)
and `~/Desktop/uat-2026-09-11/uat-single-lane-2026-09-11.csv` (2 rows). All six rows pass
`extraction.has_identity`; every `jobtitle` passes `held_queue._first_forbidden` and
`run_manifest._looks_forbidden`.

| Row | Person / title | Company (id, domain) | Email | Lane / action | Pre-registered outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | John Miller, CEO — contact **3601** | Sunshine Coast Turf Club (`9680907342`, `sctc.com.au`) | `john@sctc.com.au` | domain / update | `written`, id 3601, associated (already associated; PUT idempotent) |
| 2 | Katie Poggioli, Secretary (title inferred from the mailbox; page gives none) | Atherton Turf Club — **absent** by name, token and domain | `secretary@athertonturfclub.com.au` (Racing Queensland club page, Cloudflare-decoded) | domain miss + name miss / create | `review`, `lv_enrichment_needs_review=true`, NOT in HubSpot afterwards — that absence is the evidence |
| 3 | Jimmy Busteed, General Manager of Hospitality & Sales (ATC "our team" page) — **absent** | Australian Turf Club (`9605284724`, `australianturfclub.com.au`) | blank | name / create | `hold_emailless` holds it client-side UNLESS the reveal lands an `@australianturfclub.com.au` address, then `written` + associated. Freemail → `email_domain_freemail`; other domain → `email_domain_mismatch`. Only row that can CREATE — the one hand-delete |
| 4 | Craig Sheppard, Racing Content Producer \| Editor \| Social Media — contact **3501**, no email on record | Ipswich Turf Club (`9604726291`, `ipswichturfclub.com.au`) | blank | name / update (step 3 proposes 3501, `auto: false`, you approve) | as row 3: held unless the reveal lands `@ipswichturfclub.com.au`; a held row 4 means the name-lane UPDATE path was **not reached** this run — record as "path not reached", not a failure |

Reading of this section's row-1 contradiction ("contact created" vs "rows 1+4 are updates"):
row 1 is an UPDATE, as Gate 12's 7101 was. Creates are rows 2 (refused to review) and 3.
Both blank-email rows are held by `extraction.hold_emailless` until the enrich pass
reveals an email — that is the shipped design ("the deployed ingest lane resolves a contact
by email only"), verified offline on these exact rows.

Single-lane batch (both domain-lane updates, TWO companies — the doc's plural, and it keeps
the batch clear of the open Associate Carry Merge condition, which needs 2+ permitted rows on
ONE association lane): Grant Dewsbury, contact **7101**, Darwin Turf Club (`9605267534`);
Nathan Exelby, contact **37400807974**, Ipswich Turf Club (`9604726291`). The one thing this
batch answers: did the execution SETTLE.

Dropped candidates, each with the probe that dropped it: David Hines 22901 / RWWA — an
unattributed `sourceType: API` write at 2026-09-11T00:51Z on both records (operator did not
claim it; offer him back if it was theirs); Tony Fenlon 6851 "CEO, Rockhampton Jockey Club" —
the club's own site (2025-11-07) names David Aldred CEO, record stale; Jack Penfold, David
Aldred, Chris Chaffe, Nathan Exelby, John Miller — all already present (18701, 20801,
133443465640, 37400807974, 3601), which is why the last two became UPDATE rows instead.
Fallback for row 2 if ever needed: Kent Alley, Gordonvale Turf Club,
`info@gordonvaleturfclub.com.au` — company and contact both absent as of 2026-09-11.

Side observation, not a test: ATC (`9605284724`) reports `num_associated_contacts` 4 while 10
contacts carry `@australianturfclub.com.au` addresses — six unassociated ATC people.

**Corrected after the run (2026-09-11, run `a254d1e…`, executions 12365-12376, 0 writes):**
the pre-registered outcomes for rows 2 and 3 above were written against `contact-upload`'s
behaviour. `enrich-before-ingest` holds EVERY create `no_match` (D-70-11) and hands every
matched row to `enrich-records` by id, so on this lane rows 1 and 4 are never ingested and
rows 2 and 3 are never sent — the ingest send was 0 rows by construction, and batch 2 sent
nothing at all. The D-70-17 mixed shape needs `contact-upload`. Record:
`.planning/UAT-autonomous-batch-2026-09-09.md`.

**Second round, `contact-upload`, built 2026-09-11 after plugin 0.46.0 installed** (the lane
that actually creates — see the correction above). Files:
`~/Desktop/uat-2026-09-11/uat-contact-upload-mixed-2026-09-11.csv` (4 rows, chunk cap 2 → 2
chunks) and `~/Desktop/uat-2026-09-11/uat-contact-upload-single-lane-2026-09-11.csv` (2 rows).
All six pass `has_identity`, `_first_forbidden`, and `hold_emailless` (6 sendable, 0 held).

| Row | Person | Company (id, domain) | Email | Lane / action | Pre-registered outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | John Miller, CEO — contact 3601 | Sunshine Coast Turf Club (`9680907342`, `sctc.com.au`) | `john@sctc.com.au` | domain / update | `update`, `association: associated` (idempotent) |
| 2 | Jimmy Busteed, GM Hospitality & Sales — ABSENT | Australian Turf Club (`9605284724`, `australianturfclub.com.au`) | `jbusteed@australianturfclub.com.au` (revealed by run a254d1e…) | domain / create | `create`, new id, associated to 9605284724 — the ONE hand-delete |
| 3 | Katie Poggioli, Secretary — ABSENT | Atherton Turf Club — ABSENT | `secretary@athertonturfclub.com.au` | domain miss + name miss / create | downgraded to `review` at `Decide Action` (§13.0.1), `lv_enrichment_needs_review=true`, NOT in HubSpot |
| 4 | Katie Devine — contact 1801, freemail | Australian Turf Club (name match, unique) | `katiedevine@optusnet.com.au` (AU ISP → resolves no domain) | name / update | `update`, `company_match: name`. **Pre-registered:** rows 2 and 4 share ATC's association lane — the open Associate Carry Merge condition (2+ permitted rows on one lane + Associate returns nothing) may show row 4 `not_confirmed` while HubSpot shows it associated; log that as the KNOWN condition, not a new finding |

Single-lane (both domain / update, two companies; answers "did the execution settle"):
Nathan Exelby 37400807974 (Ipswich Turf Club `9604726291`), Chris Chaffe 133443465640 (Darwin
Turf Club `9605267534`, `cchaffe@darwinturfclub.org.au`). **Grant Dewsbury 7101 deliberately
dropped**: `held_queue._first_forbidden` matches the `grant` marker on his name (pending todo
`2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token`) — a held row of his
would be refused and dropped silently. Craig Sheppard 3501 dropped too: the ingest lane's
identity is email-only, a name-only row can never reach an update there.

Save as `uat-batch-2026-09-09.csv` somewhere outside the repo. Name the people so you can
find and hand-delete them in HubSpot afterwards — **HubSpot has no rollback.**

Expected spend for the whole batch: ~2–4 provider credits (Lusha 1/contact, 2/company),
one Anthropic call per unmatched company, roughly 8–15 n8n executions.

**Corrected 2026-09-13:** Lusha 1/contact was this section's planning estimate at the time it
was written (2026-09-09); it is not the measured rate. A rich first-time reveal was observed on
2026-09-11 billing up to 7 credits per contact (execution `12372`), not a flat 1 — see
`docs/LUSHA-V3-CONTRACT.md` §7.1 and the `_enrichment_providers_cost_note` in
`operator-claude-plugin/config/operator.local.example.json`. Treat any "~2–4 provider credits"
total in this section as a floor, not a ceiling.

### 1e. The D-71-06 gate's CSV — a row that actually gets HELD and reads `new_person`

**Why a THIRD CSV is needed at all.** §1d's second round sends Jimmy Busteed through
`contact-upload` with his email ALREADY REVEALED — that is a straight `create` with no
`no_match` hold anywhere in the path, so it exercises none of Phase 71 (71-RESEARCH.md
§ Seam Map 10). The D-71-06 gate needs a row that actually gets HELD on a `no_match` verdict
and is then read back as `new_person` from the stamp Phase 71 built. It runs through
**`enrich-before-ingest`, not `contact-upload`.**

| Row | Person / company | Email column | What it exercises | Expected |
| --- | --- | --- | --- | --- |
| A | Jimmy Busteed, ABSENT from HubSpot, Australian Turf Club (`9605284724`, `australianturfclub.com.au`) | **BLANK** | the waterfall reveals `jbusteed@australianturfclub.com.au`; `confidence.assess` holds him `no_match`; the entry is stamped and reads `new_person` — the whole phase's headline case | held, then step 6 names him under "new person"; `create all N` lands him, associated to `9605284724` |
| B | the stamp's source — one real contact already in HubSpot at a genuine `@australianturfclub.com.au` address | filled (their real, on-file email) | matches at step 2; that domain enters `confirmed_company_domains` under `step2_match` — this is what makes row A read `new_person` instead of `needs_company` | matched normally, no hold |
| C | Grant Dewsbury, contact `7101`, Darwin Turf Club (`9605267534`) | filled | §1d dropped him because the forbidden-name marker refused his name; his persisting here is this fold's own live proof | matches/updates normally — the point is that he is IN the CSV and is NOT silently dropped |
| D | a second ABSENT person at a company HubSpot already holds, email BLANK | **BLANK** | reserved for the cold-start half — do NOT include in the batch-surface `create all N` reply; leave it held | held as `new_person`; created from a FRESH `review-triage` sitting, not this conversation |

**Row B's source — default (c), zero credit; fallback (a).** Default: pick any one of the
roughly ten contacts ATC already carries at `@australianturfclub.com.au` (RESEARCH § Seam
Map 4) and put them in the CSV with their real, on-file email — this contact MATCHES at step
2, so their domain enters `confirmed_company_domains` under `step2_match` and spends zero
extra credit. Fallback (a), only if no such contact is convenient at gate time: add an ATC
COMPANY row to the CSV instead, so step 2's company-row confirm table supplies the domain
under `step2_company_row` — this option spends one company-enrichment credit where (c) spends
none. **Record which option supplied the stamp in `71-UAT.md`.**

**Keep §1d's `jobtitle` warning in force**: no `secret`/`arm` substrings ("Secretary",
"Armidale") in any row's `jobtitle` — the forbidden-marker scan on row payloads is otherwise
unrelated to this phase's fix and would still refuse to persist a held row carrying one. Note
the change this phase DOES make: as of `0.48.0`, the `grant`/`token` markers no longer refuse
a person's or company's own NAME (that is what lets row C persist) — they still refuse an
actual grant token or secret VALUE wherever one appears.

**Clean-up, part of the gate, not an afterthought:**
- Hand-delete every contact created in HubSpot. HubSpot has no rollback.
- Delete `held_queue.json` from the plugin's durable state directory —
  **this deletion IS the D-71-05 wipe.** It is a manual step by design, not code: no
  migration or lazy-rekey path exists for a pre-Phase-71 file, by the same ruling that makes
  `load()` refuse one outright rather than silently reading it as empty.
- Delete any driver script written during the session (operator scripts ruling, §2 below).

No arming instruction belongs in this subsection — the D-71-06 gate task owns every send.

---

## 2. The run — say this, watch for that

Open a fresh conversation (a grant lives only in a conversation; nothing carries over).

**Scripts (operator ruling 2026-09-09):** your Claude may write a driver or probe script when a
SKILL.md step cannot do the job — ladder down, not around. Two conditions: the script goes
through the same durable bookkeeping the skill's fences use (`run_state`, `held_queue`,
`written_records`, `run_report`), so the end-of-run row-accounting line stays true; and every
such script is deleted at the end of the session (scratchpad only, never the repo root or the
plugin cache). Note in the UAT record which script ran and which step it replaced.

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

---

## 6. Phase 72 gate (D-72-17) — enrichment extras land on a real created contact

**Written 2026-09-12, plan 72-07.** This is the phase's one end-of-phase live gate (operator
ruling 2026-09-09, backloaded per `backload-human-gates-to-end-of-phase`): everything through
plan 06 is code, tests and a walker proof. Nothing has been deployed, bounced, or armed for
this phase yet. Run the seven steps below in order. Nothing may be armed before step 3, and
nothing may be left armed after it.

### Step 1 — verify the three overflow-slot properties exist (NOT create — D-72-23 amendment)

`lv_phone_2` (contacts), `lv_mobilephone_2` (contacts) and `lv_phone_2` (companies) were
**already created live** in plan 05 (`config/hubspot_migration/undo-manifest-481a5c99-ec62-4f59-940a-7387f5e2a7ad.json`),
under an execution-time operator ruling (D-72-23) that moved property creation out of this
gate. This step is therefore a **verify-exists** step, not a creation step — run the sync tool
in its default dry-run mode and confirm it reports **zero pending creations** for these three:

```
! set -a; . ./.env; set +a; .venv/bin/python scripts/sync_hubspot_properties.py
```

If it reports any of the three as pending, do NOT proceed — that means the live portal has
drifted from the undo manifest. Only then, to actually create whatever is missing, run it
armed under its existing two-key gate:

```
! set -a; . ./.env; set +a; DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true .venv/bin/python scripts/sync_hubspot_properties.py
```

Read all three properties back (a plain GET, no write) and confirm `lv_phone_2` exists on both
contacts and companies, and `lv_mobilephone_2` exists on contacts.

### Step 2 — regenerate, deploy, bounce every changed workflow, DISARMED

D-72-21 supersedes D-72-18's ingest-only deploy scope: `mergeContacts.js` and
`mergeCompanies.js` are inlined by `scripts/build_cloud_workflows.py` into
`wf_enrichment_cloud`, `wf_review_decision_cloud`, `wf_scheduled_maintenance_cloud` and
`wf_contact_ingest_cloud` alike, so this phase's recency/overflow/geo changes cannot leave any
of those four diff-clean. The shared engines make a diff-clean non-ingest body impossible.

```
! .venv/bin/python scripts/build_cloud_workflows.py
! set -a; . ./.env; set +a; DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python scripts/deploy_n8n_workflows.py
```

Then bounce (deactivate → activate) every cloud workflow the deploy touched. Read back, for
each: the node count matches the committed JSON, `settings.executionOrder` reads `"v1"`, and
both write-safety flags (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`) read `"false"`.
A workflow whose regenerated JSON is byte-identical to what is already live is not
redeployed — confirm which ones actually changed from the deploy script's own dry-run diff
before running the armed form.

### Step 3 — one armed, single-record window: an absent person at a company HubSpot holds

Reference record (the same one this phase's charter todo names, `72-CONTEXT.md`'s
`<specifics>`): **Jimmy Busteed, Australian Turf Club (`9605284724`,
`australianturfclub.com.au`)** — his held row from the D-71-06 gate carried `mobilephone
+61 419 212 580` and `lv_linkedin_url http://www.linkedin.com/in/jimmybusteed`, both of which
F71-5 recorded as paid-for and dropped. If Busteed already exists in HubSpot from an earlier
gate, substitute a different absent person at a company HubSpot already holds, following
§1d's row-2/row-3 pattern above.

Run `/operator-claude-plugin:enrich-before-ingest` against a one-row CSV naming that person
(blank email — let the waterfall reveal it). At the numbered match table, answer
`create all 1`. This opens exactly ONE armed, record-scoped write window for exactly one send.
`ALLOW_N8N_ARM` must read `true` only for the duration of that window — the arming is
per-record and operator-directed, never unattended or scheduled (see `n8n-legacy-execution-order-empty-item-push`
project memory: the bounce script itself exits 1 while any workflow is armed, which is the
mechanical backstop against leaving one open).

After the send completes, disarm and confirm — read back `ALLOW_HUBSPOT_RECORD_WRITES` and
`ALLOW_HUBSPOT_CREATE` on every workflow touched: **both must read `"false"` again.** Do not
proceed to step 4 until this reads clean.

### Step 4 — re-read the created contact

Read the new contact back from HubSpot (a plain GET) and assert:

- `mobilephone` is populated with the revealed/researched number.
- `hs_linkedin_url` AND `lv_linkedin_url` are both populated with the same LinkedIn URL
  (D-72-04's dual write).
- The geo fields the waterfall found (`city`/`state`/`country`, and `hs_state_code` if the
  provider supplied a code) are populated.
- The contact is associated with `9605284724` (or the substitute company's id).

### Step 5 — one UPDATE row proving non-clobber

Run one more row through the same lane against a contact that already holds a non-blank
`phone` value, with a CSV row supplying a *different* phone number. Confirm the existing
`phone` value was **NOT** overwritten (fill_blank_only, `protect_if_current_present`). Also
check the `firstname`/`lastname`/`company` consequence plan 01 recorded: a CSV correcting a
misspelled name or company on this same UPDATE row should **not** apply, now that the lane
gates every candidate against the contact's real existing properties instead of merging
against `{}`.

### Step 6 — record how `hs_additional_emails` behaved, if at all

Plan 05's live probe found `hs_additional_emails` is a writable `enumeration`, not the
assumed string, so the second-email write was never built — a second email should land in
`lv_contact_enrichment_provenance` only, never on `hs_additional_emails` itself. Confirm this directly
against the created/updated contact: `hs_additional_emails` should be unchanged from
whatever it held before this gate (if anything), and the second email (if the waterfall found
one) should be visible only inside the provenance JSON blob.

### Step 7 — clean up

Hand-delete the contact created in step 3 from HubSpot — **HubSpot has no rollback.** Note its
id in the UAT record before deleting it. Do not hand-delete the UPDATE-path contact from
step 5 (it pre-existed this gate). Delete any scratch script written to drive this gate, per
the operator scripts ruling in §2 above.

### Arm/disarm summary (read before running step 3)

| Flag | Purpose | Rule |
| --- | --- | --- |
| `ALLOW_HUBSPOT_PROPERTY_WRITES` | schema-level property creation (step 1 only) | two-key gate with `DRY_RUN=false`; never used for step 3's record write |
| `ALLOW_N8N_DEPLOY` | deploy regenerated workflow JSON (step 2) | disarmed deploy only in this gate — no record write happens at deploy time |
| `ALLOW_N8N_ARM` | arms exactly one record-scoped send window (step 3) | operator-directed only, per-send, bounded to the one row being sent; the bounce script exits 1 while any workflow is armed, which is the mechanical proof nothing was left open |

Nothing may be armed before step 3. Nothing may be left armed after it — step 3's own
disarm-and-confirm is the gate, not an afterthought.

### Run outcome, 2026-09-13 (plan 72-08 Task 2) — read before running this gate again

The gate ran live. Full record: `.planning/phases/72-enrichment-extras-land-in-hubspot/72-UAT.md`
Task 2. Three things worth knowing before a repeat run:

- **Confirm the plugin's portal before any MCP pre-check.** This session's HubSpot MCP
  connector pointed at a different portal (`443043042`) than the plugin's own target
  (`22617666`); the MCP pre-check had to be discarded and every read/write redone through the
  plugin. Check which portal the MCP connector is pointed at before trusting its output.
- **A phone-value comparison must tolerate bidi wrapping.** HubSpot rendered an existing
  `phone` value wrapped in U+202D…U+202C bidi marks; a byte-for-byte string comparison across
  a copy/paste will report a false mismatch unless those marks are stripped first.
- **Step 4's "both `hs_linkedin_url` and `lv_linkedin_url`" assertion currently fails on
  create** — `lv_linkedin_url` does not land on the ingest CREATE path (F72-1, a real code
  defect, gap-closure pending). It DOES land on the UPDATE/enrich-records path. Do not read a
  repeat failure of this specific assertion on a fresh CREATE as a new finding until F72-1 is
  closed.
- **Step 6 is a no-op if the waterfall finds no second email**, which is what happened for
  both rows in this run — record NOT OBSERVED, not a pass, when that happens again.

### Run outcome, 2026-09-13 (plan 72-12 Task 2/3) — F72-1 closed on a repeat run

The gap-closure fix (plan 72-09) was regenerated, deployed and bounced disarmed across the
four changed cloud workflows, then step 3 was repeated: one armed CREATE against a fresh
absent Jimmy Busteed row (contact `352522004980`, n8n execution `12414`). Step 4's assertion
now **passes**: both `hs_linkedin_url` and `lv_linkedin_url` landed as the identical full URL
`http://www.linkedin.com/in/jimmybusteed`, provenance source `waterfall`/confidence 85 (not
`csv`). Full record: `.planning/phases/72-enrichment-extras-land-in-hubspot/72-UAT.md` Test 3.
**F72-1 is closed** — the "gap-closure pending" note above no longer describes the deployed
behavior on the CREATE path; a future run of this gate should expect the assertion to pass.
