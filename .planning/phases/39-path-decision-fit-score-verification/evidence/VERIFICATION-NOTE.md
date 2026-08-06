# Verification Note: Company Fit-Score Availability on Sales Hub Pro (D-02 Attestation)

## Header

- **Verification date:** 2026-08-06
- **Portal ID:** 22617666
- **Portal host:** `app-ap1.hubspot.com`
- **Region:** ap1
- **Git SHA at time of verification:** `9b39b2860ff3604a4ebb80a47f0953bb9f5e2f1b`
- **Who performed the portal walkthrough:** the orchestrator, driving the operator's already-logged-in
  Chrome session, at the operator's explicit in-session delegation. This is a deviation from
  CONTEXT.md D-01's "the operator drives it" instruction — the operator overrode that instruction
  live and asked the orchestrator to perform the click-path directly. The resulting portal state and
  screenshots are authentic (not simulated, not mocked); only the identity of who clicked differs from
  the plan's original assignment. See `39-02-SUMMARY.md` Deviations for the full record.

## Verdict

**Verdict: Company fit-score scoring on Sales Hub Pro (portal 22617666) is AVAILABLE** — confirmed by
`evidence/portal_walkthrough_2026-08-06-3-leadscoring-entry.png` and
`evidence/portal_walkthrough_2026-08-06-4-company-fit-selector.png`.

## API evidence (supporting/negative only)

| Probe | Endpoint | HTTP status | Finding | Evidence file |
|---|---|---|---|---|
| Account info | `GET /account-info/v3/details` | 200 | `has_tier_field: false` — the response carries only portal identity and locale (`portalId`, `accountType`, `timeZone`, `companyCurrency`, `uiDomain`, `dataHostingLocation`); no hub-tier or entitlement field exists in this schema, as RESEARCH.md predicted. | `evidence/account_info_response.json` |
| Company properties list | `GET /crm/v3/properties/companies` | 200 | 270 total properties; `calculation_score_properties_found: []` — zero score properties present. | `evidence/properties_probe_response.json` |

**Neither API result establishes availability, positively or negatively.** The account-info schema is
documented to carry portal identity and locale only — it has never exposed hub tier or product
entitlement, on this portal or any other, so `has_tier_field: false` is expected and carries no signal.
The company-properties listing only contains a `calculation_score`-typed property *after* the operator
builds a scoring model in the portal UI; HubSpot does not pre-provision an empty scoring property to
signal availability. An empty list at probe time is therefore inconclusive by construction, not
tier-negative evidence. Anyone re-reading this note must not mistake either API result — individually or
together — for a negative verdict on availability. (RESEARCH.md "Common Pitfalls" Pitfall 1.)

## Portal evidence (authoritative)

Outcome shape observed: **the builder rendered** (not an upsell/paywall screen, not an absent entry
point).

Walkthrough, in order:

1. Settings → Account & Billing → Products & Add-ons — the full subscription list on this portal shows
   **Sales Hub Professional (3 Sales Seats)** plus 2 Granted Core Seats, and no other Hub product.
   (`evidence/portal_walkthrough_2026-08-06-1-billing-overview.png`,
   `evidence/portal_walkthrough_2026-08-06-2-products-addons.png`)
2. The Lead Scoring app rendered at `app-ap1.hubspot.com/lead-scoring/22617666`.
   (`evidence/portal_walkthrough_2026-08-06-3-leadscoring-entry.png`)
3. "Choose who you'd like to score" offered three objects: Contacts (**locked** — Marketing Hub gate,
   consistent with HANDOVER §8), **Companies (unlocked, selectable)**, and Deals.
4. For Companies, the score-type selector offered **Company combined score, Company engagement score,
   and Company fit score** — the company + fit combination specifically confirmed available on this
   Sales Hub Professional portal, not just company scoring in general.
   (`evidence/portal_walkthrough_2026-08-06-4-company-fit-selector.png`)

No score was created in the portal during this walkthrough; the builder was backed out of without
saving, so no scoring model or `calculation_score` property exists on this portal as of this note.

## Gate status

This resolves the availability half of the D-05 gate: **available**, on evidence, per the portal
walkthrough above.

**This verdict does NOT drive the path decision.** Per an operator decision made mid-execution of this
plan (2026-08-06, superseding CONTEXT.md D-05's lead-scoring-tool preference), the path is
**fix-the-four-workflow-chain-in-place**, locked on a hard architectural requirement: the score must
land in the existing `lv_icp_fit_score` property (tier in `lv_icp_tier`) and reuse the existing scoring
architecture. The lead-scoring tool auto-generates its own `hubspotDefined`, HubSpot-managed score
property and cannot be configured to write to `lv_icp_fit_score` — so despite the AVAILABLE verdict
recorded above, the tool is not adopted.

Consequently the D-04 recalc-latency gate (built in plan 39-03, reserved for a live run in 39-04) is
**moot for the path decision**: it measures the lead-scoring tool's recalculation behavior, and that
tool is not the chosen path regardless of what the measurement would show. The availability verdict in
this note stands on its own as accurate, re-checkable evidence — it is simply not the fact that decided
the path. The formal decision record, citing this note, lands in `39-DECISION.md` (plan 39-04).

Custom equation properties remain rejected per D-06/HANDOVER §5 (not RevOps-editable, formula-fragile) —
unaffected by this operator override.

## Re-check procedure

**API probe (re-runnable):**

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/probe_scoring_tool_availability.py', run_name='__main__')"
```

Requires `HUBSPOT_PRIVATE_APP_TOKEN` and `HUBSPOT_PORTAL_ID=22617666` in `.env`; the script refuses any
other portal ID and performs GET-only reads. Re-running will overwrite
`evidence/account_info_response.json` and `evidence/properties_probe_response.json` with fresh
timestamps — diff against the versions in this commit to detect API schema drift.

**Portal click-path (manual, in-browser, signed into portal 22617666 on `app-ap1.hubspot.com`):**

1. Settings → Account & Billing → Products & Add-ons — confirm the subscription list.
2. Navigate to the lead scoring tool (`app-ap1.hubspot.com/lead-scoring/22617666`).
3. "Choose who you'd like to score" → select Companies.
4. Confirm the score-type selector lists "Company fit score" as a selectable option.
5. Back out without saving (no scoring model should be created by a re-check).

## Assumptions carried

Two RESEARCH.md assumptions were **not relied upon** for this verdict:

- **A1** (third-party "real-time" recalculation claims are marketing copy, not a documented SLA) — not
  relied upon; this note makes no latency claim. The latency question is D-04/D-03 scope, not D-01/D-02.
- **A2** (the properties-create failure — `POST /crm/v3/properties/companies` against a
  `calculation_score` field — is believed portal-agnostic but was not reproduced live) — not relied
  upon; this note's availability verdict rests entirely on the portal walkthrough in the "Portal
  evidence" section above, not on any API create-attempt result.
