# Phase 41 — Canary Evidence (COMPLETE, 5/5 records)

**Date:** 2026-08-08
**Verdict:** all five canary paths exercised and correct. The engine behaves per rubric on
real records.

The canary ran in two sittings: 2 records on 2026-08-07 before the operator disarmed, and
the remaining 3 on 2026-08-08 after a re-arm scoped to exactly those three ids.

---

## Results

| # | Record | Path under test | org_type | content | veto | score | tier | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | Melbourne Racing Club (9604614548) | non-clobber | individual_club_team | *(blank)* | false | 25 | C | **PASS** — no prior canonical value overwritten |
| 2 | Racing NSW (15008671672) | evidence-gated promotion | *(blank)* | **true** | false | *(blank)* | *(blank)* | **PASS** — promotion works; parked for missing org_type |
| 3 | QRIC (16047156820) | D-02 exception list | **regulator** | false | true | *(blank)* | D | **PASS** |
| 4 | Sportsbet (17861423879) | graduated deduction | gambling_operator | false | true | 0 | D | **PASS** — see below |
| 5 | Supertech (15274105699) | hard veto | hardware_vendor | false | true | *(blank)* | D | **PASS** |

---

## The three paths that settle the rubric

### QRIC → `regulator` (D-02 exception list)

June's coarse Perplexity enum had no `regulator` value and bucketed QRIC as a governing
body. The hand-curated exception list corrected it to `regulator`, which is what
`docs/business/icp-scoring.md` says it is ("QRIC is a regulator, not a content buyer").
**The exception list does real work on real data.**

Its veto reason is `No broadcast or streaming content` — correct: a racing integrity
commission produces no broadcast content.

### Sportsbet → gambling is a DEDUCTION, not a veto

This is the subtle one, and the initial automated assertion got it wrong.

`lv_anti_icp_flag` is `true`, which looks like a failure against the rubric's rule that
gambling is a graduated deduction rather than a hard veto. It is not. The veto **reason**
is:

> `No broadcast or streaming content`

Gambling is absent from the reason string. The veto came from the `no_content` rule, which
is a legitimate hard veto and correct for a betting operator. Had gambling been wrongly
promoted to veto status, the reason would name it.

The deduction applied exactly as specified:

| Component | Value |
|---|---|
| `org_type_score` (gambling_operator) | 0 |
| `produces_content_score` | 0 |
| `geography_score` (AU) | +10 |
| `annual_revenue_score` | +10 |
| `gambling_score` | **−20** |
| **`lv_icp_fit_score`** | **0** |

0 + 0 + 10 + 10 − 20 = 0. **Exact.** This is ENGINE-05's gambling component computing
correctly on a real record, and it closes the question Phase 40 could only prove on
fixtures.

**Correction to the check, not the engine:** `finish_canary.py` asserted "Sportsbet: no
veto," which is the wrong predicate. The right one is "gambling did not *cause* the veto"
— verified by reading the reason string. The script exited 1 on that assertion; the
engine is correct and the assertion was naive.

### Supertech → hard veto fires with a compound reason

> `No broadcast or streaming content; Hardware/AV/LED vendor, not sports-media buyer`

Both applicable hard vetoes fired and are named separately, matching
`config/icp_scoring.yaml`'s reason strings. Tier D. This is VETO-01's behaviour confirmed
on a real record rather than a disposable.

---

## Zero provider spend — HOLDS across the whole canary

| Provider | Baseline | After | Delta |
|---|---|---|---|
| Lusha | 3925 | **3925** | 0 |
| ZoomInfo | 9397 | **9397** | 0 |
| Apollo | null | null | n/a (non-master key; zero-spend proven structurally) |

---

## Disarm and queue hygiene

```json
{"outcome": "disarmed",
 "observed": {"ALLOW_HUBSPOT_RECORD_WRITES": "false", "ALLOW_HUBSPOT_CREATE": "false",
              "TEST_RECORD_IDS": "", "TEST_RECORD_DOMAINS": ""}}
```

All five canary records had `lv_enrichment_requested` reset to `false` after processing, so
the 15-minute poller cannot re-pick them and spend Anthropic tokens against a closed gate.

---

## What this establishes for DATA-02

Scores and tiers computed automatically on landing, with **no per-record manual touch**, on
the actual enrichment write path — across five records exercising five distinct rubric
behaviours (non-clobber, evidence-gated promotion, enum exception, graduated deduction,
hard veto). Every outcome matches `config/icp_scoring.yaml`.

**DATA-02's mechanism is proven.** What remains for full closure is scale: the parity sweep
over a landed population, which needs the remaining 61 records released through 41-04's
review gate.

**DATA-01 remains open** — 5 of 66 companies have landed.
