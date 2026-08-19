# Milestone Context — Direct Backfill & Scoring Coverage

**Gathered:** 2026-08-19 (operator, `/gsd-new-milestone`)

## Goal

Backfill HubSpot company records directly — in-session, not via n8n — with ZoomInfo data and
targeted research, writing the outstanding fields required for scoring and derived tiering.
The operator does not have n8n credits to do this through the pipeline.

## Why this is cheaper than it first appears

HubSpot already derives two of the three steps, verified live 2026-08-19:

| Step | Who | Verified |
|---|---|---|
| `lv_org_type` (enum) → `org_type_score` (number) | **nobody unless we do** | `calculated=False` |
| five `*_score` components → `lv_icp_fit_score` | **HubSpot** | `calculated=True` |
| score + `lv_anti_icp_flag_num` → `lv_icp_tier_derived` | **HubSpot** | `calculated=True` |

n8n never derived the tier — Phase 50 made that HubSpot's own calculation engine. What n8n does
is the **translation**: enum/boolean inputs into the six numeric properties the engine can read.
`calculation_equation` reads only numerics (enums are rejected at create, booleans read null),
which is the same finding that forced `lv_anti_icp_flag_num` into existence.

So this milestone writes the `lv_*` inputs plus six numbers per record, and HubSpot computes
score and tier itself ~70-130s later. **Zero n8n executions, zero n8n credits.** `src/icp_scoring.py`
is already the oracle for those six numbers — held in parity with the n8n node by the Phase 46
rule — so nothing is reimplemented.

## Locked decisions

- **D-01 — Population: never-scored only (~646).** Companies with no `lv_icp_fit_score`, which read
  blank on the derived tier today. Deliberately excludes the 66 already-scored records, so the
  committed D-07 parity evidence and Phase 49's settled tiers are not disturbed.
- **D-02 — Sources: ZoomInfo first, research only for gaps.** ZoomInfo GTM `companies/enrich` by
  domain for firmographics; Claude web research only for fields ZoomInfo cannot answer
  (`lv_org_type`, `lv_produces_content`, hardware/gambling classification).
- **D-03 — Credits sized up front.** Query the ZoomInfo credit balance BEFORE the run and cap the
  population to what the balance actually supports, rather than discovering exhaustion partway.
- **D-04 — Unmatched records: skip and log, never guess.** A record ZoomInfo cannot match is
  written with nothing and logged unenriched. It stays blank-tiered rather than scored on invented
  data, preserving the distinction between "not yet enriched" and "enriched and genuinely low-fit".
  **No whole-record research fallback** — operator: too expensive. Research fills specific gap
  fields on records ZoomInfo DID match; it does not rescue records ZoomInfo missed entirely.
- **D-05 — Pre-registered prediction, per record.** The dry run commits an artifact naming each
  record's expected tier BEFORE any write. `src/icp_scoring.py` yields it for free while computing
  the six numbers, so it costs nothing. Post-write reads are compared against it, making a
  surprising tier unambiguously a defect rather than a story told afterwards.
- **D-06 — Canary: 1 → 5 → 25 → chunked remainder, operator gate at each.** The remainder is
  batched (not one ~615-record write) with a checkpoint between batches, so a late-emerging
  failure — quota exhaustion mid-run, a systematic normalisation error only visible at volume —
  stops after one batch.

## Landmine carried in from prior work

**ZoomInfo GTM returns revenue in THOUSANDS, not dollars.** Raw pass-through puts every company
one band too low and inverts the ICP scoring. Any revenue normalisation must convert before
banding, and a test must pin it.

## Sequence

Plan → dry run on a sample → **operator approval** → canary execution. No writes before approval.
