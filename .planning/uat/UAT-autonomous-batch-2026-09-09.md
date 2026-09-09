---
status: in_progress
lane: enrich-before-ingest (supervised first live batch, 57-05 Task 4)
run_id: 377a913c1c9d49129663c6c8740f436d
client: 0.42.0
backend: Phase 66 + 5a8/pav, deployed disarmed and bounced 2026-09-09 (level with master)
started: 2026-09-08T23:22:18Z
updated: 2026-09-09
source: docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md
---

## Reconstructed read-only from the plugin key and the durable stores

| Execution | Workflow | Started (UTC) | What |
|---|---|---|---|
| 12140 | enrichment | 23:22:18 | propose, row-3 — no email, no candidates, `contactability: none` |
| 12141 | enrichment | 23:22:59 | propose, row-1 + row-2 — first pass, no email found (`gap_flag`) |
| 12142, 12143 | backend status | 23:23–23:24 | reads |
| 12144 | enrichment | 23:25:27 | propose, row-1 + row-2 — `ceo@turfclubtas.com` (complete), `admin@devonportracingclub.net.au` (email_only) |
| 12145 | contact ingest | 23:43:14 | Natalie Waters → **create `351336543679`, associated to company `20686065409` by domain** |
| 12146 | backend status | 23:44:04 | read |
| 12147 | contact ingest | 23:44:26 | Barry Milton → `Decide Action: review` — "no company in HubSpot matched name \"Devonport Racing Club\"" — **not created** (correct, §13.0.1) |
| 12148–12151 | review decision | 23:46–23:47 | review-queue reads (contacts 0, companies 17) |

Stores: `held_queue.json` row-1/row-2 `no_match` (match gate, both later resolved);
`run_manifest` both `confidence_held`; `run_state` dispatched row-1, row-2; `run_audit`:
ceiling `ok` (projected 12 of 2427 remaining), balances lusha 3866 / zoominfo 9371 / apollo
`unknown` (unrecognized_response_shape), disarm `disarmed` on `AwbBeShdPgV48eiY` with every
flag `"false"`. Both workflows' write flags read `"false"` after the run.

## Tests

### 2. Guardrail A clean backend — **pass** (flags false before and after, disarm recorded)
### 7. Armed per send, disarmed after — **pass** (`run_audit.disarm`, post-run `describe_workflow`)
### 8. Outcomes per row
- row 1 (company in HubSpot) → written, associated — **pass** (`351336543679`, operator to eyeball in HubSpot)
- row 2 (company absent) → review, never landed — **pass on the backend**, **fail on the client**: recorded as `outcome: "failed", reason: null` in `written_records`, the reason never reached the operator (todo 2026-09-09-ingest-review-branch…)
- row 3 (no email) → present in 12140, absent from `run_state` — **unverified**: transcript needed
### 5. State / pause / open — **unverified**: transcript needed (price block, Apollo `unconfirmed`, ~7 s pause, no question)
### 1, 3, 4, 6, 9 — **unverified**: transcript needed

## Open questions for the operator
1. Barry's email: the spreadsheet/held_queue row carries `admin@devonportracingclub.net.au`; the ingest sent `Devraclb@bigpond.net.au`. Where did the Bigpond address come from — a step-3 `email:` correction, the step-6 preview, or a provider?
2. Row 3: who, and what did the round say about them?
3. The step-9 report block, verbatim.

## Findings
- F1 (major, backend): review branch responds `{"queue":"needs_review"}` only → client reads FAILED, reason lost. Todo filed.
- F2 (minor, client): durable dir never prunes (362 `run_state` files). Todo filed.
- F3 (observation): the operator's Claude attributed the hold to the email verifier; the backend's reason was "company absent". Consequence of F1, not a separate defect.


## Round B (mixed), 2026-09-09 ~03:00Z — run `2bc3617b094b4c939d57f38ff6704e3f`

Run through a driver script the operator's Claude wrote in its scratchpad, NOT through the
SKILL.md sequence (second occurrence; see F4). Match split by email presence to work around
F5. Observed:
- Natalie auto-matched `351336543679` (tier high), set aside — correct, no duplicate.
- Waterfall found Greg `gregoryp@wyongraceclub.com.au` + LinkedIn + persona; Barry LinkedIn
  + state; Nardine seniority only, no email.
- `confidence.assess` held all three unmatched rows `no_match` (D-61-03: tier `none` is never
  confident) → `SENDABLE=0`, nothing ingested. By design: a NEW person is created only via the
  end-of-run approval pass. The operator declined the approve prompt.
- Preview said SEND for Greg/Barry while the gate held them → todo
  `2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md` (F7).
- Report rendered (F3 path works) but `REPORT INCOMPLETE`: per-record `None -> failed` for
  row-2/row-4 from enrichment legs that wrote nothing → todo
  `2026-09-09-written-records-labels-propose-and-enrich-legs-failed.md` (F8).
- Held rows section lists row-1..row-4 `confidence_held` including Natalie: the global
  `held_queue` backlog from run `377a913c` is not run-attributed (a stated report gap).
- Balances: lusha readable, apollo unreadable (known), **zoominfo unreadable
  (`provider_error`)** this run though readable at 23:44Z and at grant time — intermittent,
  observe (F9).
- F1 (review branch response) NOT exercised: no ingest send happened. Round A result not yet
  reported.

## F4 closed with direct evidence, 2026-09-09

The 2026-09-08 session's own scratchpad (`…/043ec56e…/scratchpad/drv_enrich.py`, plus
`drv_preview.py`, `drv_ingest_natalie.py`, `drv_ingest_barry.py`) shows the round was driven by
scripts, not the SKILL.md. `drv_enrich.py:11` hard-codes `enrich_rows=[all_rows['row-1'],
all_rows['row-2']]` — row-3 was left out by the driver before `run_state.start_run` ran; and
`:39` passes `async_ack=True`, which is the source of the bogus `written_records` entry
`392753a` later stopped. Not a repo defect. Under the operator's 2026-09-09 ruling (scripts
allowed when required, bookkeeping through the same stores, cleanup at session end) the
report's row-accounting line is the right guard: it now names any row the batch knew about
and the run did not.

## Round B rerun after the F5 deploy, 2026-09-09 ~05:20Z — run `c2bf9c3f78b146309efecaf7419098f1` (+ solo `80b44c4f…`)

Driver-scripted again (allowed under the 2026-09-09 ruling). Greg + Barry only.
- **F5 verified live** (12173, 12179): per-run identity correct at `Normalize + Score`.
- **F1 proven live** (12184, Barry solo): body carries `action: "review"` + the real reason.
- **Greg was NOT updated.** Execution 12181: `HubSpot Update Write Gate` emitted 0 items,
  `HubSpot Update` never ran. The gate reads `identity_keys.domain || domain`; the ingest
  item carries `company_domain` only (F11). The response still said `update` (F12) and the
  client recorded `write_attempted`; the operator's Claude reported "Landed — updated". Wrong.
- 2-row ingest body carried ONE item: webhook `responseData` default `firstEntryJson` (F10).
- Spend: 2 rows enriched (waterfall), ~4 credits. No HubSpot write landed this round.
- Barry: review, correct (§13.0.1). Nardine excluded. Natalie untouched.
