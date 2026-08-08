# Phase 41 — Interim Run Report

**Status: INCOMPLETE.** This is the honest interim record, not the closure report 41-04
Task 3 specifies. That task's precondition (`parity-report-final.json` exists) is unmet
because the full 66-record run never happened, and its closure action (mark DATA-01 and
DATA-02 complete) would be false. **DATA-01 and DATA-02 remain open.**

**Date:** 2026-08-08

---

## Provenance of the source dataset

The operator explicitly asked this trail be validated rather than assumed, so it is
recorded here in full.

| Fact | Value |
|---|---|
| Physical location | `../ausgtm-lightningvisuals-data/data/enriched_companies.json` (sibling repo, outside this git root) |
| Committed snapshot | `config/june_candidates_source.json`, sha256-pinned |
| Producer | `../icp-analysis/enrich.mjs` |
| Method | Perplexity `sonar`, live web research |
| Date produced | 2026-06-29 |
| Records | 66, keyed by HubSpot company ID |
| Confidence split | 49 high / 16 medium / 1 low |

The "66 web-researched companies (49 high-confidence)" claim in ROADMAP.md and
REQUIREMENTS.md is **accurate**. All 66 are pre-existing CRM companies, so Phase 41 is
enrich-in-place, not net-new creation.

---

## Resolution outcomes

| Outcome | Count |
|---|---|
| Resolved live | **66** |
| Re-matched by name/domain | 0 |
| Ambiguous | 0 |
| Unmatched / skipped | 0 |

Zero June-to-now drift. Evidence: `41-id-resolution.json`.

---

## What actually ran

The operator armed the window for all 66 IDs (`41-arm-evidence.json`: outcome `armed`,
66 record IDs, 0 domains, create still disarmed). Five canary records were queued per
D-10's ramp. The operator then ran `--disarm` while the canary was still in flight, so
**2 of 5 canary records processed and 61 records were never queued at all.**

### Canary results

| ID | Record | Path under test | org_type | produces_content | revenue_band | score | tier | status |
|---|---|---|---|---|---|---|---|---|
| 9604614548 | Melbourne Racing Club | non-clobber | individual_club_team | *(blank)* | 50-500M | 25 | C | needs_review |
| 15008671672 | Racing NSW | evidence-gated promotion | *(blank)* | **true** | 5-50M | *(blank)* | *(blank)* | needs_review |
| 16047156820 | QRIC | exception list → regulator | — | — | — | — | — | **never processed** |
| 17861423879 | Sportsbet | graduated deduction, no veto | — | — | — | — | — | **never processed** |
| 15274105699 | Supertech Electronics | hard veto fires | — | — | — | — | — | **never processed** |

**3 of the 5 distinct code paths the canary exists to exercise were never tested.**

---

## Findings

### The promotion path works — MRC's blank is pre-existing

Racing NSW promoted `lv_produces_content = true`. That settles the question raised in
`41-MRC-DRIFT-FINDING.md`: the evidence-gated promotion path functions. MRC's blank
`lv_produces_content` predates this run (it was already blank in
`41-canary-readback-before.json`) and is not a canary failure.

### The F1 native firmographic fold works

Both processed records gained a `lv_revenue_band` derived from their own `annualrevenue`
where the waterfall supplied none — MRC to `50-500M` (from $206,078,000), Racing NSW to
`5-50M`. MRC's `annual_revenue_score` moved 0 → 10 and its score 15 → 25 as a direct
result. This is F1's option-(a) resolution working on real data.

### No clobbering occurred

MRC was the deliberate non-clobber test case — the only canary record carrying prior
canonical state. No previously-set canonical value was overwritten or cleared.

### Racing NSW has no score, and that is expected

`lv_org_type` is blank, so the calculated `lv_icp_fit_score` has a null term and produces
no value. This is the parked-record shape 41-02 anticipated when it scoped the parity
sample to *landed* records — a fully parked record would otherwise register as a
structural parity FAIL that says nothing about the engine.

### Parked to review — 2 of 2 processed records

Both processed records sit at `needs_review`. Per D-12 this is accept-and-report: review
routing is the system working, not a defect. The operator triages via the existing flow.

### No derivable revenue band

Not assessable at this sample size. `41-01-SUMMARY.md` records that 6 of 66 have blank
`annualrevenue` and would score up to 10 points low, potentially one tier below true
position — F1's documented option-(c) residue. Neither processed record was in that set.

### Non-ANZ hard veto

Not exercised. No processed record was non-ANZ.

---

## Zero provider spend — HOLDS

| Provider | Baseline (pre-run) | Notes |
|---|---|---|
| Lusha | 3925 | |
| ZoomInfo | 9397 | |
| Apollo | null | Non-master key; balance endpoint returns nothing. Known, expected. |

Structural assertion (`tests/test_zero_provider_spend.py`, 10 tests): the SJ-3 dispatch
event carries no `providers` key, and an absent key resolves to zero enabled providers —
so zero spend is structural for this vehicle rather than a setting that could be
misconfigured. Apollo's zero-spend rests on that structural proof, not on a balance
comparison.

---

## Disarm evidence

```json
{"outcome": "disarmed", "workflow_id": "950HPb7a1GgSAIyZ",
 "observed": {"ALLOW_HUBSPOT_RECORD_WRITES": "false", "ALLOW_HUBSPOT_CREATE": "false",
              "TEST_RECORD_IDS": "", "TEST_RECORD_DOMAINS": ""}}
```

All four write-safety flags false/empty. Re-verified live before the Phase 43 deploy.

**Queue hygiene:** all five canary records had `lv_enrichment_requested` reset to `false`
after the disarm. Left set, the 15-minute poller would have re-picked them, spent
Anthropic tokens, and written nothing against the closed gate.

---

## Verdicts

### DATA-01 — **NOT MET**

The 66 companies did not land. Two records received partial input writes with provenance
stamped. Zero provider spend held. The mechanism is proven; the population is not
imported.

### DATA-02 — **PARTIALLY EVIDENCED, NOT CLOSED**

Melbourne Racing Club scored automatically on landing — `lv_icp_fit_score` and
`lv_icp_tier` computed with no per-record manual touch, on the actual enrichment write
path rather than a hand-constructed fixture. That is genuine, real-record evidence for the
requirement's core claim.

It is **one record**, not a population, and the parity sweep over a landed population never
ran. One record demonstrates the chain can fire; it does not establish that it fires
correctly across the range of inputs the rubric distinguishes — which is precisely what the
three unprocessed canary paths were chosen to test.

---

## To finish Phase 41

1. Re-arm the window (operator action).
2. Re-queue the three unprocessed canary records (16047156820, 17861423879, 15274105699).
3. Confirm QRIC lands `regulator`, Sportsbet takes the graduated deduction without a veto,
   and Supertech trips the hard veto.
4. Then release the remaining 61 through 41-04's review gate.
5. Run the parity sweep over the landed population and disarm.

Steps 2–5 are mechanical once step 1 is done. Step 3 is the substantive gate: it is what
turns one record's success into evidence about the engine.
