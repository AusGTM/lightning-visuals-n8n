# Judge lever 2 — evaluated and dropped (2026-09-02)

**Lever:** cheaper-model routing for the `confidence_band`-only class (D-63-05). When a companies
row's `judge_reasons` is exactly `["confidence_band"]`, adjudicate with a cheaper model
(`claude-haiku-4-5`) instead of the primary judge model (`claude-sonnet-5`).

**Verdict: DROP.** Both configured drop reasons fired simultaneously:

- `material_disagreement`
- `insufficient_corpus`

## What was evaluated

`.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-REPLAY-VERDICT.json`
(committed 2026-09-02T06:13:38Z) is the artifact this record is based on. It was produced by
`scripts/replay_judge_models.py --replay` over real stored n8n judge inputs — an offline replay,
per D-63-06, using zero Lusha credits, zero HubSpot writes, and zero new n8n executions.

**Corpus.** 91 n8n executions scanned (`11973`–`12069`), 5 judge inputs found in total, split
`companies: 5, contacts: 0`. Of those 5, exactly **3** carried `judge_reasons` matching the
`confidence_band`-only class this lever is about — below the fixed minimum corpus size of **10**
set in `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-CONTEXT.md` /
Plan 63-03, before this data was seen. That shortfall alone is `insufficient_corpus`.

**Models compared.** `claude-sonnet-5` (model_a, today's production judge) vs
`claude-haiku-4-5` (model_b, the proposed cheaper model).

**Comparison counts** across the 3 confidence_band-only inputs: `agree: 0`, `immaterial: 2`,
`material: 1`, `both_unparseable: 0`.

**The material disagreement, in full** — input `11975:0`, lane `companies`:

| | `decision` | `chosen_value` |
|---|---|---|
| `claude-sonnet-5` | `accept_research` | `governing_body_league` |
| `claude-haiku-4-5` | `accept` | `governing_body_league` |

Both models agreed on the resulting `chosen_value`, but diverged on `decision`
(`accept_research` vs `accept`) — the field the replay's materiality rule treats as
load-bearing, since it distinguishes "accepted straight" from "accepted after further
research," a distinction downstream consumers of the judge's verdict rely on. That divergence on
a single reason class (`confidence_band` alone — no veto-shaped or conflict reason present) is
exactly the class this lever proposed handing to the cheaper model unconditionally, which is why
one disagreement inside a 3-row corpus is enough to trigger `material_disagreement` on its own,
independent of the corpus-size shortfall.

## What would change the answer

- **For `insufficient_corpus`:** more retained n8n executions carrying judge inputs on the
  `confidence_band`-only class. The current corpus is bounded by execution retention on this n8n
  Cloud instance and by how few executions in the scanned window reached the judge at all (5 of
  91) — not by anything this repo controls directly. A later replay over a wider execution window,
  once more confidence_band-only judge calls have accumulated, could clear the minimum of 10.
- **For `material_disagreement`:** a narrower record class than "`confidence_band` is the only
  reason" — one where the two models are shown to agree consistently on `decision`, not just on
  `chosen_value`. The disagreement observed here does not indict the model choice broadly; it
  indicts unconditional routing of every confidence_band-only row.

## What was NOT touched

`scripts/build_cloud_workflows.py` was never opened for this change. No `n8n/wf_*.json` was
regenerated for this reason. `n8n/code/escalation.generated.js` and `n8n/code/taxonomy.generated.js`
were not regenerated. Nothing about this lever was committed before the verdict in
`63-JUDGE-REPLAY-VERDICT.json` was read — that ordering is the entire design of D-63-06 (adequacy
established by evidence gathered before the ship/drop decision, not after). Because nothing was
committed, there is nothing to revert: a DROP here means the codebase is exactly as it was before
Plan 63-04 began, not a reverted state.

## Disposition

- **Lever 1** (narrowing the escalation band) remains deferred — an authorization trade needing
  its own phase, per `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-CONTEXT.md`
  Deferred section. Not affected by this record.
- **Lever 2** (this lever) — evaluated against real evidence, dropped. Will not be re-proposed as
  unexplored; any future attempt starts from this record and needs either a wider corpus or a
  narrower target class, per "What would change the answer" above.
- **Lever 3** (capping research searches) remains deferred — the effective `max_uses` in the
  deployed workflow is unconfirmed, per the same Deferred section. Not affected by this record.

The ~16s-per-record judge cost measured in
`.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md` stands unchanged. This
record does not close that todo — it amends the todo's lever-2 entry to reflect that it was tried
and rejected, not left unexplored.
