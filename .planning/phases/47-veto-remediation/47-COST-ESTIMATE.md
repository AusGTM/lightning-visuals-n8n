# Phase 47 — Ex-Ante Cost Estimate (D-03 / COVER-02)

**Written:** 2026-08-11, before any live HubSpot, n8n, or Anthropic call for this phase.
**Scope:** the 17 pinned records in `PINNED_COMPANY_ID_ORDER`
(`scripts/remediate_veto_companies.py`).

COVER-02's bar is literal: an estimate written **before** the run, actuals reported **after**,
against the 2,500/month n8n allowance and the current Lusha balance, and a run projected over
either budget is **refused, not truncated**. This document is the "before" half. Plan 04's
run report fills the empty Actuals table below with the same row labels.

This document's projected figures are produced by, and must agree with, `estimate_cost()` in
`scripts/remediate_veto_companies.py` (D-03/D-20's cost-projection function, built in Plan 01
Task 3). The numbers below were read directly from a live call to that function against the 17
pinned IDs, not hand-derived separately — the two can never silently drift apart.

---

## Projected Cost

| Row | Projected | Source |
|-----|-----------|--------|
| Web-research calls | **17** | One per pinned record, on the standalone Python `src/web_research.py::claude_web_research` path — a single `ANTHROPIC_RESEARCH_MODEL` (`claude-sonnet-5`) call per record using the native `web_search` server tool at up to `WEB_RESEARCH_MAX_SEARCHES` (default 5) searches, `max_tokens=4096`. |
| Redundant second-pass research calls (D-20) | **~4** | `KNOWN_LIKELY_EVIDENCE_GATED_IDS` in `scripts/remediate_veto_companies.py`: Simtech LED (`18047161864`), Editix (`17317381378`), Jam TV (`17317850381`), The Rumble / Pacific Action Sports (`20943964946`) — the four pinned IDs whose plainly-not-a-club names (D-17) make them the likeliest to land on `hardware_vendor` / `content_producer`. |
| Anthropic dollars (order-of-magnitude) | **~$1.17** (17 × $0.0686) | Phase 20 canary, execution 332, 2026-07-30: $0.0686/record ($0.052 Haiku research + $0.017 Sonnet judge, intro pricing). **This figure is measured on the n8n Haiku-plus-Sonnet chain, NOT the standalone Python `claude-sonnet-5` + native `web_search` path D-08 chose for this phase.** It excludes the native `web_search` server tool's per-search billing entirely — that component is genuinely unmeasured in this repo. Treat $1.17 as a bounded floor, not a precise number; the redundant ~4 second-pass calls are already inside the 17-record base count reported by `estimate_cost()` (it does not add them as extra dollars — see "What this figure does and does not include" below). |
| n8n executions | **at most 17** | One per D-18 webhook POST (`POST {N8N_URL}/webhook/hubspot/enrichment/event`), against the **2,500/month** n8n Cloud plan allowance (project memory `n8n-execution-budget.md`). |
| Provider credits (ZoomInfo / Apollo / Lusha) | **0** | D-08 routes all enrichment through Claude web research, not the provider waterfall. No ZoomInfo, Apollo, or Lusha call is made; the Lusha balance is untouched. |

### What this figure does and does not include

`estimate_cost()`'s `anthropic_estimate_usd` multiplies `web_research_calls` (17) by the
per-record canary figure — it does **not** separately multiply the 4 redundant records by a
second per-record cost, because the canary figure itself was never measured for a second-pass
call shape. The ~4 redundant calls are reported as a **count**, not folded into the dollar
figure, precisely so this document does not manufacture false precision on top of an
already-acknowledged under-estimate. Read the dollar row as "at least ~$1.17, plus an unknown
additional amount for ~4 second-pass calls and for native `web_search` per-search billing on
all 17 calls" — bounded, not precise.

### Live projection, read directly from `estimate_cost()`

```
$ .venv/bin/python -c "
import scripts.remediate_veto_companies as m
print(m.estimate_cost(m.PINNED_COMPANY_ID_ORDER))
"
{'web_research_calls': 17, 'redundant_research_calls': 4, 'n8n_executions': 17,
 'n8n_budget_month': 2500, 'lusha_credits': 0,
 'lusha_credits_note': 'D-08: web research only, no provider waterfall -- zero Lusha
 credits drawn.', 'anthropic_estimate_usd': 1.1662,
 'anthropic_estimate_note': "Derived from the Phase 20 canary figure ($0.0686/record),
 measured on the n8n Haiku-plus-Sonnet path -- NOT this script's single claude-sonnet-5 +
 native web_search call, and excludes that call's per-search billing. An under-estimate,
 not a live-measured figure for this path."}
```

---

## Why the deployed workflow re-fires research on ~4 records (D-20)

The workflow's `Research Trigger Gate` node's `needsResearch()` (`n8n/wf_enrichment_cloud.json`)
fires purely on org-type membership in `EVIDENCE_GATED_ORG_TYPES` (`content_producer`,
`gambling_operator`, `governing_body_league`, `hardware_vendor`) — it does **not** check whether
evidence is already present for that org type. `ALLOW_WEB_RESEARCH` is a build-time literal
(`true`), baked into the compiled JS, not something a per-invocation webhook payload can
override. Suppressing the redundant call would mean editing and redeploying the workflow, which
is a far larger blast radius than accepting ~4 extra Anthropic calls (D-20's explicit trade-off).
This is why the redundant-call row exists in this estimate at all: discovering it in the actuals
after the fact — rather than naming it here, before the run — is exactly what COVER-02 forbids.

`scripts/remediate_veto_companies.py`'s `verify_post_run()` re-checks after the D-18 webhook leg
whether the redundant pass clobbered the D-09 evidence metadata stamps, and re-stamps once inside
the same armed window if it did (Plan 01 Task 3, D-20 consequence (b)).

---

## Refusal rule (COVER-02's literal bar)

`refuse_if_over_budget(estimate, ids)` in `scripts/remediate_veto_companies.py` is the function
that refuses. It raises **`BudgetRefused`** when the projected `n8n_executions` exceeds
`n8n_budget_month` (2,500), and returns `ids` **unmodified** — never truncated — when the
projection stays within budget. There is no n8n usage endpoint (project memory
`n8n-execution-budget.md`), so this is a **static projected count**, not a live balance read;
month-to-date headroom against the 2,500/month allowance is a figure the operator confirms at
the arming checkpoint in Plan 04, not something this script or this document can verify live. A
run projected over budget is **refused outright — no API call is made** — not truncated
part-way through the 17.

---

## Actuals (filled by Plan 04's run report)

| Row | Projected | Actual |
|-----|-----------|--------|
| Web-research calls | 17 | *(Plan 04)* |
| Redundant second-pass research calls | ~4 | *(Plan 04)* |
| Anthropic dollars | ~$1.17 (floor, unmeasured components excluded) | *(Plan 04)* |
| n8n executions | at most 17 | *(Plan 04)* |
| Provider credits | 0 | *(Plan 04)* |
