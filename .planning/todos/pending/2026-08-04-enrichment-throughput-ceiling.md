---
created: 2026-08-04T05:10:00.000Z
updated: 2026-09-02
resolves_phase: 63
title: Enrichment throughput — the judge fires on nearly every record and costs ~16s of a ~34s run
area: n8n
severity: major
files:
  - n8n/code/judge.js:145
  - n8n/code/escalation.generated.js:9
  - config/escalation_policy.yaml
  - n8n/wf_enrichment_cloud.json
---

## Status (rewritten 2026-09-02)

Two things changed since this was captured on 2026-08-04. Both narrow it; neither closes it.

**1. The dominant bulk lever SHIPPED.** Original lever 4 (concurrency / async) landed in Phase 61
(2026-08-30): `async_ack` takes a run off the ~100s synchronous Cloudflare window, and `scale_up`
fans out via a self-referencing `Execute Workflow` node. Both are present in the deployed
`n8n/wf_enrichment_cloud.json`. The "500 sequential requests, chunk ceiling of 2 as a hard bound"
framing below is **superseded** — chunk size is now a tuning knob, not a ceiling imposed by the
response window.

Read Phase 61's own caveat before assuming this made bulk cheap (CLAUDE.md §13.0.3): the same
2-row batch listed **1** execution inline and **3** with `scale_up: true`. Fan-out is a
*throughput* win, not a cost win, and the billed-vs-listed question is unresolved.

**2. The central hypothesis is now CONFIRMED — by reading the code, no run needed.**

The original said: *"Hypothesis, not yet proven: that band is [75, 85] and the check is inclusive
on both ends, while claude_web appears to return confidence 85 routinely."*

Verified 2026-09-02:

```js
// n8n/code/escalation.generated.js:9
const ESCALATION_CONFIDENCE_BAND = [75, 85];

// n8n/code/judge.js:147
if (typeof conf === "number" && conf >= lo && conf <= hi && _carriesClassification(data)) {
  reasons.push("confidence_band");
}
```

Inclusive at **both** ends, exactly as suspected. With claude_web landing on 85 routinely (MRC's
stored provenance carries `confidence: 85` on every `claude_web` field; the research fixture uses
88), `confidence_band` fires on essentially every record that carries a classification signal —
which is what "8 of 8 full runs fired the judge" measured. **The gate is decorative in practice.**

One caveat against over-reading it: `_carriesClassification(data)` still gates the reason, so a
candidate carrying only a size guess does not trigger it. The gate is not unconditional — it is
just not selective among the records that reach it.

**Also since 2026-08-04, pushing the other way:** gap-closure 58-06 (2026-08-26) *widened* judge
escalation to all material-conflict field groups. The judge now fires on strictly more conditions
than when this was measured, so the 47%-of-wall figure is a floor, not a ceiling.

## What remains open

The per-record levers, worth ~16s of a ~34s run:

1. **Tighten the judge gate.** Now that the band is confirmed inclusive-at-85, the options are
   concrete: make the upper bound exclusive, narrow the band, or require a *classification*
   trigger rather than confidence alone. **This is an authorization-shaped trade, not a perf
   tweak** — the judge exists to catch anti-ICP and hard-veto errors, and 58-06 deliberately
   widened it after an unadjudicated conflict false-vetoed a real AU company (execution `11983`,
   Series Futsal Victoria). Do not narrow it without deciding what may go unadjudicated. Any
   change must respect RO-2 (`test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts`).
2. **Cheaper judge model when `confidence_band` is the ONLY reason** (~10s). **Evaluated and
   dropped, 2026-09-02 (Phase 63, Plan 63-04).** Sonnet 5 → Haiku 4.5, keeping Sonnet for
   conflicts and veto-shaped reasons, was tested by offline replay (D-63-06) of both models over
   real stored n8n judge inputs — zero Lusha credits, zero HubSpot writes, zero new n8n
   executions. Verdict: **DROP**, on both configured drop reasons at once —
   `insufficient_corpus` (3 confidence_band-only judge inputs found against a fixed minimum of
   10) and `material_disagreement` (the one comparable input disagreed on `decision`, `accept`
   vs `accept_research`, despite agreeing on `chosen_value`). Nothing was shipped or reverted —
   `scripts/build_cloud_workflows.py` and every `n8n/wf_*.json` were never touched for this
   change. Full evidence:
   `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-REPLAY-VERDICT.json`
   (the artifact) and
   `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-LEVER-DROP-RECORD.md`
   (the record). This lever is not unexplored — re-attempting it needs either a wider retained
   corpus or a narrower target class than "confidence_band is the only reason," per the record's
   "What would change the answer" section. Lower risk than (1) because it does not reduce *what*
   gets adjudicated, only what adjudicates it — that property is unaffected by the drop.
3. **Cap research searches** (~4–6s). `WEB_RESEARCH_MAX_SEARCHES` is 5; confirm what `max_uses` is
   actually in effect in the deployed workflow.

**Do this first, and it is nearly free:** log `reasons[]` from the gate over a handful of records.
The code read above predicts `confidence_band` dominates; a live sample turns that into a measured
distribution and tells you whether (2) alone captures most of the win. The node data does not
currently expose `confidence` at `Validate Research Output`.

## Original measurement (2026-08-04, unchanged and still the baseline)

Method: `GET /api/v1/executions/{id}?includeData=true` over all 38 executions of
`LV Enrichment (Cloud template)` (`950HPb7a1GgSAIyZ`), summing `executionTime` per node. No new
run, no credits spent. 8 of 38 ran the full path; the other 30 are 0.1–8.0s (the research gate
correctly skips already-resolved records).

| Stage | Mean | Share of wall |
|---|---|---|
| `Judge Call` (Sonnet 5) | **16.1 s** | **47%** |
| `Claude Web Research` (Haiku 4.5 + web_search) | **12.1 s** | **35%** |
| Everything else — 3 providers, 3 usage checks, HubSpot fetch + update, ~40 code nodes | ~6 s | 18% |
| **Wall clock** | **34.2 s** | 100% |

Per-run (exec: wall / judge / research): 1152: 38.6/18.4/10.4 · 1109: 36.9/16.9/10.8 ·
443: 34.6/20.0/10.0 · 442: 32.1/11.0/16.2 · 337: 36.1/16.7/13.7 · 332: 35.6/18.3/11.6 ·
328: 38.9/20.0/13.5 · 18: 20.6/7.3/10.9

**The finding that still re-ranks everything:** the provider waterfall is not the bottleneck and
never was. All three providers plus their credit checks total ~4s — under 12%. The `Judge Call`
alone costs four times the entire waterfall. Nobody should spend effort on provider latency.

Summed node time ≈ wall clock (38.52s vs 38.59s on exec 1152) proved the pipeline strictly
sequential with no internal parallelism. Phase 61 addressed this *between* runs (fan-out), not
*within* one.

## Consequences at scale (recompute against Phase 61 before quoting)

The original figure — 1000 fresh records ≈ 10.4h serial, ~$69 Anthropic, ~2000 Lusha credits
against a 3930 balance — assumed strict serialization. Wall clock now divides by achieved
concurrency, but **the Anthropic and Lusha figures do not change**: they are per-record, and
fan-out spends them faster rather than less. A single bulk run still consumes half the Lusha
balance and cannot be repeated twice in a month. That constraint is untouched by Phase 61 and is
the reason levers 1–3 still matter.
