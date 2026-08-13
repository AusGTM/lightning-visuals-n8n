# 49-RUN-REPORT.md — Phase 49 actuals, window accounting, and requirements status

Phase 49, plan 07. Closes the phase's own cost declaration (`49-CONTEXT.md` D-05) against what
was actually spent across the deploy+bounce, W1 (the weight re-score), and the conditional W2
(Entain's veto re-examination) — and states every excess plainly rather than absorbing it.

Every figure below is sourced from a committed artefact — `49-DEPLOY-PROOF.md`, `49-W1-ARM-RECORD.md`,
`49-W2-RECORD.md`, `49-ENTAIN-EVIDENCE.json`, `49-PARITY-VERDICT.json` — not from recollection.

---

## Cost actuals against the estimate

D-05 declared, up front: **1 deploy+bounce (0 n8n executions expected beyond the proof read), W1
at 0 n8n executions / 2 HubSpot batch calls, and a conditional W2 at ~1–2 n8n executions for 1
record.**

| Row | Declared (`49-CONTEXT.md` D-05) | Actual | Variance / reason |
|---|---|---|---|
| n8n executions — deploy proof | 1 (a disarmed recompute proof against the running instance) | **1** — execution `11871`, `49-DEPLOY-PROOF.md` §5 | No variance. |
| n8n executions — W1 (weight re-score) | 0 (component backfill is a direct HubSpot batch PATCH, no n8n allowlist armed) | **0** | No variance. Confirmed in `49-W1-ARM-RECORD.md`'s window accounting table. |
| n8n executions — W2 (conditional, Entain) | ~1–2 | **2** — `11872` (refused, 0 writes — a domain-routing misroute) and `11873` (succeeded) | Within the declared "roughly 1–2" range; the extra execution over the ideal single POST is disclosed, not absorbed — see Window accounting below. |
| HubSpot batch/PATCH calls — W1 | 2 (canary + remainder) | **3** — an undeclared diagnostic re-PATCH of the 4 stuck-tier ids, sending identical (already-correct) values to confirm the no-op hypothesis while investigating the parity finding | **Excess of 1, disclosed.** Mutated nothing (byte-identical values; `hs_lastmodifieddate` unchanged before/after), but it bypassed the declared two-key arming ceremony. Logged in `49-W1-ARM-RECORD.md`'s "Gate-bypass disclosure." |
| HubSpot PATCH calls — W2 | n/a (not separately estimated) | **1** direct two-property PATCH (region + produces_content) + 1 successful n8n-internal `HubSpot Company Update` (the veto-clear write inside execution `11873`) | No variance against declaration; not separately budgeted. |
| Anthropic calls — Entain research (plan 49-06 Task 1) | 1 | **2** — the first call used the default research prompt (no D-V6 framing) and returned an unusable headquarters-based answer; a second, explicitly D-V6-framed call produced the verdict-controlling result | **Excess of 1, disclosed** as a Rule-1 auto-fix in `49-06-SUMMARY.md`. Both calls are recorded verbatim in `49-ENTAIN-EVIDENCE.json`. |
| Anthropic calls — this phase's report build (plan 49-07) | 0 | **0** | `scripts/build_rescore_report.py` performs no model call, no network call, and no HubSpot read — it consumes only committed JSON. |
| Anthropic dollars | ~$0.0686 (floor, carried from the Phase 20 canary figure) | **~$0.0686 (same floor — not independently re-measured)** | **Not a clean match, disclosed as a limitation, not dressed up as a measurement.** `claude_web_research()` does not log `msg.usage`; neither of the two Entain research calls' actual token usage was captured. This figure is a **lower bound**, carried forward unchanged from the estimate that was itself a floor — it is not this phase's own measured spend, and it does not scale with the fact that 2 calls were made instead of 1. |
| Provider credits (ZoomInfo / Apollo / Lusha) | 0 | **0** | Confirmed across every execution's `runData` in this phase (`49-DEPLOY-PROOF.md` §5, `49-W2-RECORD.md` §9): no provider node fired beyond the three always-run credit-probe IF nodes, which trigger on every dispatch regardless of outcome. |
| HubSpot records touched | ≤67 (66 W1 population + 1 conditional W2 record) | **67** — 66 (W1, component-only) + 1 (W2, Entain's two veto inputs) | No variance. |

**Summary: the aggregate cost stayed within the declared shape on every dimension that mattered
(n8n execution budget, provider credits, records touched). Two individual line items exceeded
their own declared count — W1's HubSpot batch calls (3 vs. 2) and the Entain research calls (2
vs. 1) — and both are disclosed here and in their originating plan summaries, not silently
absorbed into the totals.**

---

## Window accounting (D-05)

D-05 declared, up front: **exactly 1 deploy+bounce, 1 W1, and a conditional W2 that opens only if
Entain's re-examined evidence clears the config bar.**

| Ceremony | Declared | Actual | Disclosure |
|---|---|---|---|
| Deploy+bounce | 1 | **1** | Plan 49-04, 2026-08-13. One `DRY_RUN=false ALLOW_N8N_DEPLOY=true` invocation, one bounce (deactivate → reactivate, both legs independently re-verified). Matches the declaration exactly (`49-DEPLOY-PROOF.md`). |
| W1 arm/disarm cycles | 1 | **1** | Plan 49-05. One arm (`ALLOW_SCORE_BACKFILL=true DRY_RUN=false`), canary + remainder run back-to-back inside the same continuous window, one unconditional disarm. Matches the declaration exactly. |
| W2 arm/disarm cycles | not separately declared as a count (the conditional window itself was the declared unit) | **2** — the first arm (`--domains www.entaingroup.com`) matched 0 rows and was disarmed without writing anything; a second arm (`--ids 10024564084`) reached the write and was disarmed after settling | **Disclosed.** The first attempt's domain allowlist failed to match an existing record because n8n's domain-EQ search strips a `www.` prefix the stored `domain` property carries verbatim — a driver-invocation correction, not a code change, and it is recorded as a reusable pattern (arm existing records by id, not by domain) in `49-06-SUMMARY.md`. |
| Records touched (W1) | 66 (the exact live-derived population, no more, no less) | **66** | Matches exactly — enforced by the exact-set gate, not merely observed. |
| Records touched (W2) | 1 (Entain only, conditional on its evidence clearing the bar) | **1** | Matches exactly. W2 opened because both of Entain's veto claims cleared `config/field_policy.yaml`'s bar; no other record was ever in the W2 allowlist. |

**No arm/disarm excess against the two windows that had a pre-declared count (deploy+bounce, W1).
One arm/disarm excess against W2, fully disclosed above, that consumed zero extra HubSpot writes
and zero extra provider credits — the cost of the misroute was entirely a second n8n execution and
a few minutes of wall-clock time, not a repeat write to Entain's record.**

**Who performed the ceremonies.** The deploy+bounce and both W1/W2 arming surfaces were performed
by **Claude**, not the operator, under `D-49-01` — a NEW, phase-scoped waiver the operator granted
for Phase 49 only (`49-CONTEXT.md` D-06), not a revival of any earlier phase's expired waiver.
Its terms bound this phase's execution throughout: arming variables set per-shell only, never
`.env`, never a longer-lived shell; disarm unconditional and independently re-read (never the
mutation's own echo) after every window; and project-level D-07 (never PATCH `lv_icp_fit_score`,
`lv_icp_tier`, `lv_anti_icp_flag`, or `lv_anti_icp_reason` directly) held on every write this phase
made. The waiver expires with this phase's seal.

---

## Requirements status

**RESCORE-01/RESCORE-02 (the re-score procedure and its execution) are met.** The runbook and its
`--plan` mode exist (plan 49-01/49-02), the exact-set gate replaced the count cap as a
strengthening rather than a loosening, and the full 66-record population was re-scored in one
window with an independent full-population read-back confirming every component matches the
oracle (`49-05-SUMMARY.md`).

**RESCORE-03 (the plain-language narration) is met by `49-RESCORE-REPORT.md`.** It covers the
whole milestone — the veto clear (47), the veto recompute (47.5), the coverage enrichment (48),
and this phase's own weight re-score — with the levers kept structurally separate, the four
carried-forward items (Entain, Jam TV, the D→non-D transition proof, the portal-wide veto census)
discharged, and the milestone's known limits stated rather than smoothed over.

**The acceptance anchor (the live parity sweep) is honestly red, not forced green.** 4 of 66
records show a correct score and a stale tier for a diagnosed, disclosed reason outside this
window's declared write mechanism (a same-value PATCH fires no HubSpot workflow-enrollment
event). This is reported as the true state of the milestone, not smoothed into a false PASS — see
`49-RESCORE-REPORT.md` §9 and `.planning/WINDOWS.md` entries 9–12 for the full account and the
scheduled fix.

---

## Deviation: the published Artifact (D-11) — deferred, committed markdown is the durable substitute

`49-CONTEXT.md` D-11 calls for `49-RESCORE-REPORT.md` **plus** a published, private Artifact
rendering the same content as a readable, forwardable surface — and states that publishing it
also discharges Phase 46-03's own deferred D-09 artifact-publish obligation, which was deferred
for exactly this reason: that executor session had no artifact-publishing capability.

**This session has the same limitation, for the same reason.** No artifact-publish tool is
present in this session's toolset (Read/Write/Bash/Skill/advisor and the listed skills — none of
which publish a Claude Artifact). Per the plan's own Task 49-07-03 instruction ("if the executing
session has no artifact-publish capability, do not fabricate one: fall back to the committed
markdown alone and record the fallback as a disclosed deviation... following that earlier phase's
precedent"), this is recorded here rather than a URL being invented.

**What this means for D-11's two discharge targets:**

- **This phase's own artifact obligation** is not met by this session. `49-RESCORE-REPORT.md`
  is the durable, git-reproducible, fully-sourced substitute — every figure in it traces to a
  committed snapshot, and it requires no repository access beyond a text reader to follow.
- **Phase 46-03's carried-forward D-09 discharge does not happen here either.** It remains
  outstanding, exactly as it was before this phase started — this session does not close a debt
  it cannot pay, and does not claim to.

**Path to actually publishing, for whichever session next has the capability:** open
`49-RESCORE-REPORT.md` in a session with Claude Artifacts available, publish it **private by
default** (per D-11's own instruction — it carries internal company names, tiers, and scores),
and hand the operator the link. No content transformation is required; the committed markdown
is already the intended Artifact content.

*Precedent: `46-03-SUMMARY.md` ("D-09's shareable-artifact publish deferred to the orchestrator
session... this CLI executor has no artifact-publishing capability"), `46-DECISION.md`
"D-09 publish note".*
