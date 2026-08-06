# Phase 39 Decision Record: Scoring Engine Path (DECIDE-01)

## Verdict

**Path: fix-the-four-workflow-chain-in-place.** The ICP rubric continues to score inside
HubSpot's four existing property-change workflows (created 2026-08-04), remediated to close
defects F1–F10. The score lands in the existing `lv_icp_fit_score` company property, the grade
in `lv_icp_tier`, and nothing in the write target changes.

**Decision date:** 2026-08-06. **Portal:** 22617666 (`app-ap1.hubspot.com`, Sales Hub
Professional).

## How the verdict was reached

**Availability gate (D-05 half 1): AVAILABLE.** Company fit-score is confirmed selectable in
HubSpot's native lead-scoring builder on this Sales Hub Professional portal — see
`evidence/VERIFICATION-NOTE.md` (Portal Evidence section) and the four
`evidence/portal_walkthrough_2026-08-06-{1..4}-*.png` screenshots, specifically screenshot 4
(`portal_walkthrough_2026-08-06-4-company-fit-selector.png`), which shows "Company fit score"
offered as a selectable score type. The two live API probes
(`evidence/account_info_response.json`, `evidence/properties_probe_response.json`) contributed
supporting evidence only, and per VERIFICATION-NOTE.md are explicitly inconclusive by
construction — neither establishes availability positively or negatively. Availability was
resolved from the portal walkthrough alone, never from API evidence (per the plan's
prohibition and D-01).

**Recalculation gate (D-05 half 2): NOT MEASURED — moot.** D-04's armed latency probe
(`scripts/probe_scoring_recalc_latency.py`, built in plan 39-03) measures the lead-scoring
tool's recalculation behavior. Because the operator override below closes the lead-scoring-tool
path regardless of what that measurement would show, running the probe live would not change
the verdict, so it was not run. `evidence/recalc_latency_probe.json` does not exist. This is not
an availability-gate failure invoking D-06's pre-committed fallback — it is a third path,
explained below, that supersedes the D-05/D-06 gate sequence entirely on an operator hard
requirement discovered mid-phase. The probe script itself remains shipped, unit-tested, and
disarmed (plan 39-03) as a reusable asset — see 39-03-SUMMARY.md.

## Latency measurement

None recorded. No `recalc_latency_probe.json` exists for this decision. Had the probe run, it
would have measured only the **per-record event-driven rescore** (HANDOVER §10.1's ~4–25 s
mapper latency, ~2 s calculated-sum, ~3 s tier), not the criteria-edit bulk recalculation — see
`classify_latency_band` in `scripts/probe_scoring_recalc_latency.py` for the band boundaries
that would have applied (a: ≤600 s, b: 600–3600 s, c: manual-only or no-fire). This measurement
is not needed for the chosen path: HANDOVER §10.1 already demonstrates the four-workflow chain
fires end-to-end within ~30 s on property-change events, live-validated on disposable
`ZZ-SCORING-TEST-DELETE-ME-*` companies, which is the same class of evidence the probe would
have produced for the other mechanism.

## Rationale

Cite `HANDOVER-2026-08-06-icp-scoring.md` §5 for the full mechanism comparison
(lead-scoring tool vs custom equation properties vs workflow chain) — not re-derived here per
D-07. §5 decision 1 (session-original) preferred the lead-scoring tool rebuild specifically
because it is RevOps-editable and auto-generates a grade property; that preference is
**superseded** by the operator override below, which was made on a constraint §5 did not
originally weigh: reuse of the existing property surface.

**The deciding factor is an operator hard requirement (2026-08-06), not the availability
verdict.** The lead-scoring tool auto-generates its own `hubspotDefined`, HubSpot-managed score
property — it cannot be configured to write to `lv_icp_fit_score` or `lv_icp_tier`. The operator
requires the score to keep landing in those existing properties and to reuse the existing
scoring architecture. This is decisive independent of the AVAILABLE verdict: even though company
fit-score is confirmed available on this portal (see above), adopting it would mean abandoning
`lv_icp_fit_score`/`lv_icp_tier` as the properties of record, which the operator has ruled out.
The path decision is therefore **not availability-driven** — it would have been the same verdict
had the availability gate failed.

§5 decision 2 carries forward unchanged on either path: **hard vetoes stay pipeline-owned.**
n8n keeps writing `lv_anti_icp_flag` and `lv_anti_icp_reason`; HubSpot (whichever mechanism)
scores only additive/graduated points; Tier D is a view filter on the flag. Phase 40 must not
rediscover this constraint — it is fixed regardless of path, and it directly shapes how
VETO-01–03 get satisfied on the chosen path (see "What this shapes downstream" below).

## Rejected alternatives

**Custom equation properties** — rejected twice, unaffected by the operator override.
HANDOVER §5 rejects them on the merits: viable technically (string output, `if()` conditionals,
70-open-paren ceiling) but not RevOps-editable and formula-fragile. D-06 separately pre-commits
against them as *any* fallback: "Custom equation properties stay rejected." **D-06 supersedes
ROADMAP Phase 39 success criterion 3**, which still names equation properties as the fallback
for an unavailable lead-scoring tool — that wording is stale; the pre-committed (and, as it
turns out, actual) fallback is fix-in-place.

**Legacy `calculation_score` HubSpot Score mechanism** — recorded as **unavailable**, not
rejected. It stopped updating 2025-08-31 and was removed from this portal 2026-01-10
(HANDOVER §5); it is not a live option on any path.

**Lead-scoring tool rebuild** — the path §5 decision 1 and D-05 originally preferred, and the
one this phase spent most of its evidence-gathering verifying as AVAILABLE. Not chosen, for the
architecture-reuse reason stated above, not because it failed either D-05 gate.

## What this shapes downstream

**Phase 40** — remediation targets the F1–F10 defect inventory in
`HANDOVER-2026-08-06-icp-scoring.md` §10.2 inside the four existing HubSpot workflows (flow IDs
4626124224, 4626722240, 4626722237, 4625147345), not a lead-scoring-tool build. VETO-01–03 are
satisfied by fixing the workflow+pipeline interplay per §5 decision 2: n8n continues to own
`lv_anti_icp_flag`/`lv_anti_icp_reason` writes; the workflow-side fix is making the veto
symmetric (F4–F6) and making tier recompute on flag change, not just score change (F7).

**Phase 41** — DATA-02's "imported companies score automatically on landing" assumption is
supported, not put at risk. HANDOVER §10.1 already shows the four-workflow chain fires on
property-change events within ~30 s live-validated end to end; the D-04 recalc-latency concern
that motivated Task 1/Task 2 of this plan applied only to the lead-scoring tool's undocumented
recalc cadence, which is no longer the mechanism in play.

**Phase 42** — the retirement set is whatever the lead-scoring-tool path would have produced had
it been chosen: none, since no lead-scoring model was ever created or saved in this portal
(VERIFICATION-NOTE.md: "the builder was backed out of without saving"). Phase 42's cleanup scope
is therefore the pre-existing superseded-artifact list from `REQ-retire-calc-placeholder`
(the `1 + 1` calculated-property placeholder and its `*_score` orphans), unaffected by this
decision.

## Assumptions carried into the verdict

- **A-BOUNDARY / A-PRECISION** (39-01-PLAN.md) — the band-edge constants (600 s / 3600 s) and
  the 5-second-poll-quantized upper-bound measurement contract in
  `scripts/probe_scoring_recalc_latency.py`'s `classify_latency_band`. Not exercised for this
  verdict since the probe never ran; would matter only if a future re-check revives the
  lead-scoring-tool path and needs to re-measure its recalc cadence.
- **RESEARCH.md A1** (third-party "real-time" recalculation claims for the lead-scoring tool are
  marketing copy, not documented SLA) — not relied upon; this decision makes no lead-scoring-tool
  latency claim at all.
- **RESEARCH.md A2** (the `POST /crm/v3/properties/companies` create failure against a
  `calculation_score` field is portal-agnostic) — not relied upon; irrelevant to the chosen path.

## Re-check procedure

If HubSpot changes packaging or the architecture-reuse constraint is later relaxed:

1. Re-run the availability probe: `scripts/probe_scoring_tool_availability.py` (API, supporting
   evidence only) plus the portal click-path in `evidence/VERIFICATION-NOTE.md`'s Re-check
   Procedure section (Settings → Account & Billing → Products & Add-ons → lead scoring tool →
   Companies → confirm "Company fit score" is offered).
2. If a lead-scoring-tool path is reconsidered, arm and run
   `scripts/probe_scoring_recalc_latency.py` per its module docstring (requires a human-built
   trivial criterion in the portal first — no API creates that property type) to measure its
   recalc cadence before re-deciding.
3. Re-verify HANDOVER §10.1's ~30 s workflow-chain latency by re-running the disposable-company
   validation pattern (`ZZ-SCORING-TEST-DELETE-ME-*`, create/exercise/delete) against the four
   flow IDs listed above.

## Process note: Tasks 1 and 2 of this plan did not run

Per operator instruction, this plan's Task 1 (armed latency probe run) and Task 2 (band-c
review checkpoint) were skipped as moot rather than executed, and are recorded here as a
documented deviation rather than silently dropped:

- **Task 1** would have built a trivial lead-scoring criterion in-portal and run the armed
  `scripts/probe_scoring_recalc_latency.py` to resolve the D-04 recalc gate. It did not run
  because the mechanism it measures (the lead-scoring tool) is not the chosen path regardless of
  the result — established in `evidence/VERIFICATION-NOTE.md`'s Gate Status section before this
  plan started. No trivial criterion was built in-portal for this plan; the portal carries no
  scoring-related leftovers from this plan's execution.
- **Task 2** (the band-c operator-decision checkpoint) is conditioned entirely on a band letter
  from Task 1's probe output. With no probe run, there is no band to evaluate, so the checkpoint
  never had grounds to fire. This is distinct from D-04 outcome (a) or (b) auto-proceeding
  silently — no auto-proceed happened either, because the gate the checkpoint gates on was never
  reached.

Both skips trace to the same root cause: the operator's mid-phase architecture-reuse requirement
(recorded first in `39-02-SUMMARY.md` Deviations and `evidence/VERIFICATION-NOTE.md` Gate
Status) closed the lead-scoring-tool path before this plan's Tasks 1–2 became relevant, making
the D-04/D-05 gate sequence moot for reaching a verdict. The full details of that override are
in the two evidence artifacts referenced above; the "Consequently" paragraph at the end of
`VERIFICATION-NOTE.md`'s Gate Status section is the operative statement.

## Evidence index

| File | Description |
|---|---|
| `evidence/VERIFICATION-NOTE.md` | Dated D-02 attestation: availability verdict AVAILABLE, API-vs-portal evidence framing, gate status recording the operator override, re-check procedure. |
| `evidence/account_info_response.json` | Raw `GET /account-info/v3/details` response — no hub-tier field exists in this schema; inconclusive by design. |
| `evidence/properties_probe_response.json` | Raw `GET /crm/v3/properties/companies` response — 270 properties, 0 `calculation_score`-typed; inconclusive by design (HubSpot only creates this property type after a human builds a scoring model in-portal). |
| `evidence/portal_walkthrough_2026-08-06-1-billing-overview.png` | Settings → Account & Billing overview showing Sales Hub Professional (3 seats) + 2 Granted Core seats, no other Hub product. |
| `evidence/portal_walkthrough_2026-08-06-2-products-addons.png` | Products & Add-ons subscription list, same billing confirmation. |
| `evidence/portal_walkthrough_2026-08-06-3-leadscoring-entry.png` | Lead Scoring app rendered at `app-ap1.hubspot.com/lead-scoring/22617666` — builder present, not an upsell screen. |
| `evidence/portal_walkthrough_2026-08-06-4-company-fit-selector.png` | The decisive screenshot: score-type selector for Companies offering Company combined score, Company engagement score, and **Company fit score** as selectable options. |

`evidence/recalc_latency_probe.json` does not exist for this decision — see "Latency
measurement" above.
