---
created: 2026-08-04T05:10:00.000Z
title: Enrichment throughput — 82% of every full run is two sequential Anthropic calls
area: n8n
severity: major
files:
  - n8n/wf_enrichment_cloud.json
  - n8n/code/judge.js:103
  - n8n/code/escalation.generated.js:9
  - operator-claude-plugin/skills/enrich-records/SKILL.md:133
---

## Problem

Raised by the operator 2026-08-04: at ~37 s/record, a 1000-record import takes ~10 hours and is
unusable for bulk. Confirmed, and **measured** — no new run, no credits spent: n8n retains
per-node timings, so the split came from execution history.

**Method.** `GET /api/v1/executions/{id}?includeData=true` over all 38 executions of
`LV Enrichment (Cloud template)` (`950HPb7a1GgSAIyZ`), summing `executionTime` per node.

**8 of 38 executions ran the full path** (research + judge). The other 30 are 0.1–8.0 s — the
research gate correctly skips already-resolved records. Means across those 8 full runs:

| Stage | Mean | Share of wall |
|---|---|---|
| `Judge Call` (Sonnet 5) | **16.1 s** | **47%** |
| `Claude Web Research` (Haiku 4.5 + web_search) | **12.1 s** | **35%** |
| Everything else — 3 providers, 3 usage checks, HubSpot fetch + update, ~40 code nodes | ~6 s | 18% |
| **Wall clock** | **34.2 s** | 100% |

Per-run detail (exec: wall / judge / research):
1152: 38.6/18.4/10.4 · 1109: 36.9/16.9/10.8 · 443: 34.6/20.0/10.0 · 442: 32.1/11.0/16.2 ·
337: 36.1/16.7/13.7 · 332: 35.6/18.3/11.6 · 328: 38.9/20.0/13.5 · 18: 20.6/7.3/10.9

**Three findings that change where optimization should go:**

1. **The provider waterfall is not the bottleneck and never was.** All three providers plus their
   credit checks total ~4 s — under 12% of the run. The `Judge Call` alone costs four times the
   entire waterfall. Nobody should spend effort on provider latency.

2. **Summed node time ≈ wall clock** (38.52 s vs 38.59 s on exec 1152), which proves the pipeline
   is **strictly sequential** — there is no internal parallelism at all. The three provider calls
   are independent and could overlap; that only saves ~1.5 s, but it confirms the shape.

3. **The judge gate does not discriminate in practice: 8 of 8 full runs fired the judge.**
   `computeEscalation()` (`judge.js:103`) is designed to fire only on org-type conflict,
   `produces_content === false`, hardware/gambling detection, or a confidence in
   `ESCALATION_CONFIDENCE_BAND`. **Hypothesis, not yet proven:** that band is `[75, 85]` and the
   check is inclusive on both ends (`conf >= lo && conf <= hi`), while claude_web appears to
   return confidence **85** routinely — MRC's stored provenance carries `confidence: 85` on every
   `claude_web` field, and the research fixture uses 88. If research habitually lands on the
   inclusive upper bound, `confidence_band` fires on essentially every record and the gate is
   decorative. **One check settles it:** log `reasons[]` from the gate over a handful of records.
   The node data does not currently expose `confidence` at `Validate Research Output`, so this
   could not be read from history.

## Consequences at scale

1000 fresh records (all `lv_org_type`/`lv_produces_content` blank, so research + judge fire on
every one): ~10.4 h serial, ~$69 Anthropic, ~2000 Lusha credits against a 3930 balance — so a
single bulk run also consumes half the Lusha balance and cannot be repeated twice in a month.

The client sends chunks **one at a time in plan order** (`enrich-records/SKILL.md:133`) and
neither workflow contains a `splitInBatches` node (grep: 0 in both), so 1000 records = 500
sequential requests. The chunk ceiling of 2 is a *symptom*: the webhook is synchronous, so the
response cannot fire until every record finishes, and n8n Cloud dies at the ~100 s Cloudflare
ceiling.

## Solution

TBD — the measurement re-ranks the options, and two of these are architecture decisions for the
operator, not defaults to pick:

1. **Tighten the judge gate** (biggest per-record lever, ~16 s). Prove the `confidence_band`
   hypothesis first. If confirmed, options: make the band exclusive at the top, narrow it, or
   require a *classification* trigger rather than confidence alone. Risk: the judge exists to
   catch anti-ICP and hard-veto errors — a gate that fires less often is a gate that adjudicates
   less, so this trades throughput against exactly the decisions the milestone treats as
   high-risk. Do not narrow it without deciding what may go unadjudicated.
2. **Cheaper judge model for low-risk records** (~10 s). Sonnet 5 → Haiku 4.5 when the only
   trigger is `confidence_band`, keeping Sonnet for conflicts and veto-shaped reasons.
3. **Cap research searches** (~4–6 s). `WEB_RESEARCH_MAX_SEARCHES` is 5; the deployed workflow
   showed no explicit `max_uses` literal, so confirm what is actually in effect.
4. **Concurrency — the dominant lever for bulk, and it needs no per-record change.** 82% of the
   run is waiting on Anthropic I/O, which parallelizes almost perfectly. Either send chunks
   concurrently from the client (small change; bounded by n8n Cloud execution concurrency,
   provider rate limits, and Anthropic rate limits — none of which are established) or move to an
   async webhook (respond 202 with a run id, process in the background, poll `backend-status`,
   which already exists). Async also removes the 100 s ceiling, making chunk size a tuning knob
   instead of a hard bound of 2. That is a phase, not a patch: it touches the sealed enrichment
   lane and the reporting/watch surfaces.
5. **Or do not use the interactive lane for bulk at all.** `enrichment_requested = true` on the
   records is already a queue the scheduled maintenance workflow drains — unattended, no webhook
   ceiling, notices report. Wall clock is unchanged but nobody waits. **Unverified:** the
   poller's batch size and cadence were not checked, and they decide whether this is genuinely
   better or just differently slow.

Realistic combined floor: levers 1–3 take a full run from ~34 s to roughly 12–15 s; lever 4 then
divides by concurrency. 1000 records could plausibly land in tens of minutes rather than hours.
