# Phase 48 — Ex-Ante Cost Estimate (COVER-02)

**Written:** 2026-08-12, before any live Anthropic research call, HubSpot write, or n8n
execution attributable to this phase.
**Scope:** the 5-id coverage population in `COVERAGE_COMPANY_ID_ORDER`
(`scripts/enrich_coverage_companies.py`) — Racing NSW, Editix, Jam TV, Waikato Racing
Club, The Rumble.

COVER-02's bar is literal: an estimate written **before** the run, actuals reported
**after**, against the 2,500/month n8n allowance and the current Lusha balance, and a run
projected over either budget **refused, not truncated**. This document is the "before"
half. Plan 06's run report fills the Actuals table below with the same row labels.

This document's projected figures are produced by, and must agree with,
`estimate_phase48_cost()` in `scripts/enrich_coverage_companies.py` (Plan 01). The numbers
below were read directly from a live call to that function, not hand-derived separately —
the two can never silently drift apart. **`estimate_phase48_cost()` is a different function
from Phase 47's `estimate_cost()`** — Phase 47 charged one `n8n_executions` per id on the
assumption every id's research ran through a D-18 webhook POST; Phase 48's research is a
direct standalone-Python Anthropic call (zero n8n executions) and its only n8n executions
are the D-09 recompute POSTs plus one disarmed proof-of-deploy execution (plan 48-04)
declared here rather than discovered afterwards. Reusing `estimate_cost()` against this
phase's ids would misreport both figures — see 48-RESEARCH.md § "Cost estimation
mechanics".

---

## Projected Cost

| Row | Projected | Source |
|-----|-----------|--------|
| Web-research calls | **1** | Racing NSW `15008671672` only — the one record with no captured Phase 47 evidence (D-01). Direct standalone-Python `src/web_research.py::claude_web_research` call using the native `web_search` server tool, enum-constrained per plan 48-03 Task 3. The other 4 records are resolved offline from `47-RESEARCH-RESULTS.json` — zero new calls. |
| n8n executions | **6** | 5 D-09 recompute POSTs (`POST {N8N_URL}/webhook/hubspot/enrichment/event`, `recompute:true`), one per record actually written, plus **1** disarmed proof-of-deploy execution plan 48-04 spends to prove the running instance reloaded the D-04 gate — budgeted here rather than discovered afterwards. Against the **2,500/month** n8n Cloud plan allowance. |
| Anthropic dollars (order-of-magnitude) | **~$0.0686** | Phase 20 canary figure (`ANTHROPIC_PER_RECORD_ESTIMATE_USD`), the same measured $0.0686/record floor `47-COST-ESTIMATE.md` used, multiplied by exactly 1 web-research call. Same caveat as Phase 47's document: this figure is measured on the n8n Haiku-plus-Sonnet chain, not the standalone `claude-sonnet-5` + native `web_search` path this call actually uses, and excludes native `web_search`'s per-search billing — treat as a bounded floor, not a precise number. |
| Provider credits (ZoomInfo / Apollo / Lusha) | **0** | D-01 routes Racing NSW's classification through Claude web research only, not the provider waterfall — providers do not return `lv_org_type` at all. No ZoomInfo, Apollo, or Lusha call is made; the Lusha balance is untouched by this phase. |

### Live projection, read directly from `estimate_phase48_cost()`

```
$ .venv/bin/python -c "
from dotenv import load_dotenv
load_dotenv('/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.env')
import scripts.enrich_coverage_companies as m
research_ids = ['15008671672']
written_ids = list(m.COVERAGE_COMPANY_ID_ORDER)
estimate = m.estimate_phase48_cost(research_ids, written_ids, proof_executions=1)
import json
print(json.dumps(estimate, indent=2))
"
{
  "web_research_calls": 1,
  "n8n_executions": 6,
  "n8n_budget_month": 2500,
  "lusha_credits": 0,
  "lusha_credits_note": "D-01: offline mapping + at most one direct research call, no provider waterfall -- zero Lusha credits drawn.",
  "anthropic_estimate_usd": 0.0686
}
```

`n8n_executions: 6` = `len(written_ids)` (5, one recompute POST per record this phase
writes) `+ proof_executions` (1, plan 48-04's disarmed deploy-proof execution). Both
components are declared here, ex-ante, per D-06 — neither is a surprise discovered in the
run report.

---

## Current Lusha balance (live read, COVER-02's literal wording)

COVER-02 requires the estimate to be stated "against ... the current Lusha balance" even
though this phase draws zero credits — the zero-credit projection above does not excuse a
live read. Read via `scripts/check_provider_credits.py` (read-only usage endpoints only,
never the enrichment/match/person/company data endpoint):

```
$ .venv/bin/python -c "
from dotenv import load_dotenv
load_dotenv('/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.env')
import runpy
runpy.run_path('scripts/check_provider_credits.py', run_name='__main__')
"
lusha: credits=3925 status=200
apollo: credits=None status=200
zoominfo: credits=9397 status=200
```

**Read at:** 2026-08-12T13:14:02Z

| Provider | Remaining | Notes |
|---|---|---|
| Lusha | **3925** | Live `credits.remaining` read, HTTP 200. This is the balance the operator confirms at the checkpoint; it will read the same number after the run (zero draw). |
| Apollo | `None` | Known account-level degradation — this account's key returns HTTP 200 but the body carries no top-level `remaining` field, so the extractor degrades to `None` rather than failing the estimate (per CLAUDE.md's documented Apollo condition). Not attempted this session as a re-derivation of the failure mode, only observed consistent with it. |
| ZoomInfo | **9397** | Live `usageRemaining` read via the JSON:API `Accept: vnd.api+json` header, HTTP 200. |

None of the three is touched by this phase's write leg (D-01: web research only, no
provider waterfall) — these are read-only observations satisfying COVER-02's wording, not
inputs to the projected cost above.

---

## The D-06 window declaration (stated explicitly, per plan requirement)

**1 operator deploy+bounce, 1 armed write window, record cap 5.**

- **1 deploy+bounce** (plan 48-04): `scripts/deploy_n8n_workflows.py` with `DRY_RUN=false`
  **and** `ALLOW_N8N_DEPLOY=true` in one invocation, operator-run, to land D-04's `IF
  Research Errored` gate (built and offline-tested in plan 48-02, not yet running
  anywhere) into the live instance, plus the bounce (deactivate → reactivate) to prove it
  reloaded.
- **1 armed write window** (plan 48-05): at most 5 records, `lv_org_type` /
  `lv_org_type_verified_at` / (for Editix only) `lv_enrichment_review_reason`, followed by
  the 5 D-09 recompute POSTs this document already budgets as n8n executions.
- **Record cap 5**: the entire coverage population re-derived live in plan 48-01
  (`48-POPULATION.json`, drift: false against this document's `COVERAGE_COMPANY_ID_ORDER`).

**Exceeding this declaration is a disclosure obligation in the run report, not a silent
event** — the same discipline Phase 47.5 corrected Phase 47's five-window overrun with (D-06).

---

## Refusal rule (COVER-02's literal bar)

`refuse_if_over_budget(estimate, ids)` (imported unmodified from
`scripts/remediate_veto_companies.py`, fed this phase's `estimate_phase48_cost()` dict
rather than Phase 47's `estimate_cost()` dict) raises **`BudgetRefused`** when the projected
`n8n_executions` exceeds `n8n_budget_month` (2,500), and returns `ids` **unmodified** — never
truncated — when the projection stays within budget. Proven by test, not merely asserted in
prose:

- `tests/test_enrich_coverage_companies.py::test_tracer_refuse_if_over_budget_raises_and_never_returns_a_shorter_list`
  — constructs a synthetic estimate, forces `n8n_budget_month` below the projected
  executions, asserts `BudgetRefused` is raised.
- `tests/test_enrich_coverage_companies.py::test_budget_within_budget_returns_ids_unmodified_same_length_and_order`
  — asserts the live-shaped estimate (1 research call, 6 n8n executions) returns the
  5-id list completely unmodified, same length and order as the input.

At `n8n_executions: 6` against a `n8n_budget_month` of 2,500, this refusal path will not
fire in practice — but the code path exists, is exercised by both tests above, and is the
same imported function (never a phase-local re-implementation) that would fire if the
projection ever exceeded budget.

---

## Actuals (filled by plan 48-06's run report)

| Row | Projected | Actual |
|-----|-----------|--------|
| Web-research calls | 1 | *(pending 48-06)* |
| Anthropic dollars | ~$0.0686 (floor, unmeasured components excluded) | *(pending 48-06)* |
| n8n executions | 6 (5 recompute + 1 deploy-proof) | *(pending 48-06)* |
| Provider credits | 0 | *(pending 48-06)* |
| Lusha balance | 3925 (read 2026-08-12T13:14:02Z) | *(pending 48-06 — expected unchanged)* |
