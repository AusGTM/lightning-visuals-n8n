---
created: 2026-08-04T05:10:00.000Z
updated: 2026-09-11
title: Enrichment throughput — the judge fires on nearly every record and costs ~16s of a ~34s run
area: n8n
severity: major
files:

  - n8n/code/judge.js:145
  - n8n/code/escalation.generated.js:9
  - config/escalation_policy.yaml
  - n8n/wf_enrichment_cloud.json

audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
---

## Amendment 2026-09-03 — `resolves_phase: 63` REMOVED; this todo stays OPEN

Phase 63 completed 2026-09-03. Its `close_phase_todos` step retires every pending todo whose
`resolves_phase` matches — which would have closed this one automatically. That would have been
wrong, and this todo's own body is the evidence: the status section immediately below says of
Phase 61 and the confirmed hypothesis, *"Both narrow it; neither closes it."* Phase 63 evaluated
**lever 2 only** and **dropped it** (63-04, see that lever's entry under "What remains open").
Levers 1 and 3 were never attempted.

So the frontmatter key is removed rather than the todo closed: leaving it would have armed the
same automatic closure for any future re-run, silently retiring an open `severity: major` defect
on the strength of a phase that explicitly did not fix it.

The todo is now **unassigned to a phase**. Re-targeting it — or splitting the two surviving levers
apart, since lever 1 is an authorization-shaped trade and lever 3 is a config confirmation — is an
operator decision, not one this closure makes.

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

## Operator ruling 2026-09-11 (resume session)

**Measure first.** No gate change yet. Quick task scope: log `reasons[]` from `Judge Gate`
over a handful of records so `confidence_band`'s share becomes a measured distribution, and
confirm the `max_uses` actually in effect in the deployed workflow against
`WEB_RESEARCH_MAX_SEARCHES=5` (lever 3). Lever 1 (band bounds) is NOT authorised until the
measurement is in hand.

## Measurement 2026-09-11 (quick task 260911-anv) — answers (a), (b), (c)

Ran under this operator ruling. No gate change. `scripts/build_cloud_workflows.py` and
every `n8n/wf_*.json` are byte-unchanged by this task (`git diff --stat -- n8n/
scripts/build_cloud_workflows.py` prints nothing; `Judge Gate`'s built jsCode hashes to
the same `5804fec76c32c600` before and after).

**(a) The reasons array was ALREADY being emitted on every row, escalating or not — no
builder change was needed.** This closure's own "Do this first" line above assumed the
logging did not exist yet; it was wrong, and is corrected here. Evidence, read from the
committed artefacts with no edit:

- `scripts/build_cloud_workflows.py`'s `judge_pass1_block_js` sets
  `judge_reasons: allReasons` unconditionally for the companies target (line ~3343) and
  `judge_reasons: reasons` unconditionally for the contacts target (line ~3464) — both
  BEFORE the escalation/cap decision, not conditioned on it.
- `applyCostCap` (`n8n/code/judge.js:207`) spreads the row (`{ ...row, ... }`) when it
  caps it, so `judge_reasons` survives being capped.
- Pass 3 in `_enrich_judge_gate_js` (`scripts/build_cloud_workflows.py` ~line 3630)
  returns `{ json: row }` for every row leaving the gate, capped or not, escalated or not.
- `tests/n8n/judge.test.mjs:444` already pinned `judge_reasons: []` (an empty array, not
  an absent key) on a non-escalating row through the BUILT `JUDGE_GATE_BODY` — this is not
  a new test in this task; it already existed and is unchanged.
- Live confirmation, no live call needed (already-frozen runData):
  `tests/n8n/fixtures/frozen/exec_12354.runData.json`, node `Contact Judge Gate`, both
  output items carry `"judge_reasons": []`, `"needs_judge": false` (checked directly:
  `run['data']['main'][0][*]['json']['judge_reasons']` on both items is `[]`).

**(b) The web-research search budget in the committed `n8n/wf_enrichment_cloud.json` is
5, baked as a build-time literal — not a runtime env read.** `CONFIG_FLAG_DEFAULTS["WEB_RESEARCH_MAX_SEARCHES"] = "5"`
(`scripts/build_cloud_workflows.py`); `_flag_const(name, cloud=True)` renders it as the
literal JS `const WEB_RESEARCH_MAX_SEARCHES = 5;` in both research-request builder nodes
(`Build Research Request`, `Build Contact Research Request`) rather than a `$env`/`$vars`
lookup — confirmed directly against the committed JSON
(`n8n/wf_enrichment_cloud.json`'s `Build Research Request` and
`Build Contact Research Request` node bodies both contain the literal string
`WEB_RESEARCH_MAX_SEARCHES = 5`). **Mechanism, not just the number:** on a cloud body the
runtime environment variable of the same name is NOT read at all — changing this value
means a `scripts/build_cloud_workflows.py` regenerate plus a deploy, never an env-var
edit on the running instance. It agrees with the todo's lever-3 figure.

Corroborated against live-observed `runData` rather than inferred: `research_request_body.tools[0].max_uses`
reads `5` on every item that carried a `research_request_body` in
`tests/n8n/fixtures/frozen/exec_12354.runData.json` and `exec_12356.runData.json`
(checked across all 15 node-output occurrences of `research_request_body.tools` in each
file — every one is `5`). Committed and live are level as of Gate 10 (CLAUDE.md §13.0.2),
so this is also the value the running instance is serving right now.

**(c) A live sample WAS reachable, and it measured zero judge escalations — not because
the gate is inert, but because this n8n instance's execution retention has rolled
entirely past the last real (provider-enabled) enrichment run.**

`.venv/bin/python scripts/judge_reason_distribution.py --limit 100` reached the API
(GET-only; `.env` credentials via the script's own `load_dotenv()`) and scanned 89
executions of the enrichment workflow (`950HPb7a1GgSAIyZ`), ids `12264`-`12356`:

| Lane | rows_through_gate | rows_research_matched | rows_with_reasons | rows_capped |
|---|---|---|---|---|
| companies | 83 | 0 | 0 | 0 |
| contacts | 93 | 0 | 0 | 0 |
| total | 176 | 0 | 0 | 0 |

Zero `by_reason` entries at all — `confidence_band` included. Widening the list-and-filter
scan to `limit=250` (the same GET, just a larger page) shows this is not a `--limit 100`
artifact: the ENTIRE retained execution history for this workflow on this instance is ids
`12119`-`12356`, 177 executions, split `{"webhook": 42, "integrated": 135}` — and every one
of those falls inside the 2026-09-10 incident/UAT day (CLAUDE.md §13.0.2/§13.0.3): the 135
`integrated`-mode executions are the D-70-24 runaway's self-dispatched fan-out children
(the same figure — 135 — CLAUDE.md's own runaway record cites for executions
`12211`-`12348`), and the `webhook`-mode executions are the Gate 8/11/12 disarmed proof
sends, `mode: "propose"` with `provider_enabled: {lusha: false, apollo: false,
zoominfo: false}` (checked directly on `Contact Judge Gate`'s output for execution
`12354`) — `research_candidate.matched` is `false` on every item because no provider or
research call was ever made in this window, which is exactly why `computeEscalation`'s
RO-1 guard (`if (!researchCandidate || !researchCandidate.matched) return { needsJudge: false, reasons: [] }`)
never fires. The one genuinely ARMED write in this whole story — Gate 12's execution
`12363` — is itself already outside the retained window (max id `12356`).

The plan's own suggested targeted ids from the original 2026-08-04 measurement —
`1152`, `1109`, `443`, `442`, `337`, `332`, `328`, `18` — were tried explicitly via
`--execution-ids` and every one 404s (`HTTPError 404 ... /api/v1/executions/1152`),
confirming the todo's standing note that n8n prunes executions. **There is currently no
execution on this instance, at any id, carrying a real provider-matched judge input** —
this task's own script call is the direct evidence, not an inference from "the sample
might be gone."

**Prior evidence, cited both because the live sample above is zero and because this is
what the record-keeping asks for either way:**
`.planning/milestones/v1.1-phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-REPLAY-VERDICT.json`'s
`reasons_distribution` (extracted 2026-09-02, before this instance's retention rolled
past that window) records 5 escalated judge inputs total, with `confidence_band` present
in all 5 and the SOLE reason in 3 of 5 — the code-read prediction ("`confidence_band`
dominates") holds on that sample. Its limit, restated: it is drawn from `Build Judge
Request`/`Build Contact Judge Request`, which only keeps rows whose `judge_request_body`
is non-null — i.e. already-escalated rows — so it has numerators but never had a
denominator (`rows_research_matched`/`rows_through_gate` are not obtainable from it). This
task's reader was built specifically to supply that missing denominator, and did — the
denominator today is real (176 rows through the gate, 83+93), but the matched-and-eligible
subset it needs to be a share of is 0 in the only window this instance still has. The two
artifacts are not comparable as a before/after on the same population; Phase 63's 5 inputs
remain the only surviving sample of a real escalation-shaped judge distribution.

**Lever 1 (band bounds) remains unauthorised. The `[75, 85]` band is untouched** —
`n8n/code/escalation.generated.js`'s `ESCALATION_CONFIDENCE_BAND = [75, 85]` literal is
unchanged, `test_ro2_judge_gate_cannot_see_size_conflicts` is green, and this task made no
edit to `config/escalation_policy.yaml`, `n8n/code/judge.js`, or any generated file. Lever
3's number is now confirmed rather than assumed, but changing it still requires a
regenerate-plus-deploy this task deliberately did not perform.
