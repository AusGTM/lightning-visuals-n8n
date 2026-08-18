---
phase: 50-derived-tier-property
verified: 2026-08-14T00:00:00Z
status: passed
score: 5/5 must-haves verified (all 5 roadmap success criteria hold; 1 accepted open risk disclosed, not counted against the score)
behavior_unverified: 0
overrides_applied: 0
accepted_risks:
  - test: "Search the HubSpot Reports/Dashboards library (not saved views, which are already confirmed migrated) for any report, dashboard widget, or chart that groups by, filters on, or displays lv_icp_tier."
    expected: "Either no such report/dashboard exists, or every one found is repointed to lv_icp_tier_derived."
    disposition: "ACCEPTED BY OPERATOR 2026-08-19 — reviewed twice (at the retirement decision gate and again at seal) and knowingly accepted rather than closed. Recovery if a report does break: lv_icp_tier and its data persist under ?archived=true, so a broken report can be repointed to lv_icp_tier_derived after the fact; the cost is that it breaks visibly first."
    why_human: "HubSpot exposes no public API to enumerate reports or dashboards. This is explicitly disclosed in 50-DEPENDENTS-SWEEP.md and 50-RETIREMENT-RECORD.md as UNCONFIRMED, not resolved — the operator's prior attestation covered saved views only and the operator chose to proceed and accept this risk. It cannot be closed by any script in this repo; it can only be resolved by a human opening the HubSpot UI."
---

# Phase 50: Derived Tier Property Verification Report

**Phase Goal:** `lv_icp_tier` stops depending on a HubSpot property-change event to be correct.
**Verified:** 2026-08-14 (independent live HubSpot re-checks performed during this verification, in addition to reading committed evidence artifacts)
**Status:** human_needed
**Re-verification:** No — initial verification

## Verification method

This phase deviated substantially from its original plan set under four dated, operator-directed
amendment blocks (D-20…D-24) recorded in `50-CONTEXT.md`. Per the task instructions, this
verification checks the codebase and live portal against the **amended** contract, not the
original D-01…D-19 decisions alone. Where a claim in a SUMMARY/evidence file was independently
checkable, it was independently re-checked live against HubSpot with fresh API calls made
directly from this verification session (not just re-reading committed JSON snapshots) — see
"Independent live checks" below. Where a claim rests only on operator attestation (no API to
verify it), that is flagged explicitly rather than accepted as machine-checked.

## Goal Achievement

### Observable Truths (mapped to ROADMAP.md's 5 success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A derived tier property reproduces WF1's live ladder exactly over the scored population, verified against real records | ✓ VERIFIED | `50-TIER-PARITY-EVIDENCE.md`: population=66, match=61, expected_mismatch=5, defect=0. Independently re-run live by this verifier via `scripts/check_tier_derived_parity.py`'s underlying reads (see below) — 5 individually re-fetched records matched the artifact byte-for-byte. The formula shipped live (`coalesce(lv_anti_icp_flag_num,0)=1→D`, else score bounds A/B/C/Unscored, uncoalesced on score) was fetched directly from HubSpot in this session and matches `config/hubspot_flows/lv_icp_tier_derived-property.after.json` exactly. Regression guard `tests/test_tier_formula_pin.py` (14 tests, offline, pins the live formula's parsed meaning against `config/icp_scoring.yaml`) passes. |
| 2 | The 4 (now 5, D-23) stuck records read the tier their score implies, with no event, no enrolment, no workflow run | ✓ VERIFIED | Independently fetched live from HubSpot in this session: `9605273630`→derived B (was stuck C), `9604738976`→B, `17696004613`→B, `19100977027`→B, `14752488879`→derived C (was stuck Unscored). Each record's `hs_lastmodifieddate` is `2026-08-13T22:14:5x`, predating every Phase 50 write window (2026-08-13T23:xx onward) — independently confirming none of these 5 records was ever PATCHed by this phase, satisfying "no record write" literally, not just by narrative. |
| 3 | The runtime null question is answered against live records and the resulting semantics are a recorded choice | ✓ VERIFIED (correction-of-record, not a first-time finding) | D-04's original probe (`50-NULL-PROBE.json`, kept unaltered as historical record per D-21) misread a race as null-propagation. D-21 reversed it after polling; D-22 made polling mandatory going forward. The shipped, live formula is uncoalesced on `lv_icp_fit_score` (0 `coalesce(lv_icp_fit_score...)` occurrences; confirmed directly against the live-fetched formula text in this session) — `test_shipped_ladder_is_uncoalesced_on_score` pins this offline. The choice and its correction are both recorded in `50-CONTEXT.md` and `REQUIREMENTS.md`'s TIER-02 row, not silently absorbed. |
| 4 | Portal-side dependents are enumerated before cutover, and the disposition of the old enum and of WF1 is decided | ⚠️ split verdict — machine-checkable half VERIFIED, human-only half open (see Human Verification) | `50-DEPENDENTS-SWEEP.md`: scripted Lists+Flows API sweep re-run three times (pre-migration, post-migration, pre-cutover), byte-identical each time — 0 lists, 10 flows, 5 findings, all on WF1's own action definitions. WF1 was deleted (D-24) and `lv_icp_tier` archived — both independently confirmed live in this session (`GET /automation/v4/flows/4625147345`→404; `GET /crm/v3/properties/companies/lv_icp_tier`→404 live, 200 under `?archived=true`, `archivedAt: 2026-08-14T02:17:57.731Z`, matching the committed snapshot exactly). Saved views: operator-attested migrated (2026-08-14), not independently machine-verifiable (no API) — recorded as attestation, not proof. **Reports/dashboards: explicitly disclosed as UNCONFIRMED** by the phase's own artifacts (`50-DEPENDENTS-SWEEP.md`, `50-RETIREMENT-RECORD.md`) — this is an accepted, disclosed open risk the operator chose to proceed past, not a closed truth. It is routed to human verification below rather than silently counted as passed. |
| 5 | No company record is silently re-tiered outside a deliberately armed, capped write window | ✓ VERIFIED | D-16 declared zero company-write windows; two deviations were authorised and both are disclosed with evidence: (a) `50-06`'s 6-record `lv_anti_icp_flag_num` backfill, (b) a 1-record armed recompute on Melbourne Racing Club `9604614548`. Independently re-fetched live in this session: `9604614548`'s `hs_lastmodifieddate` is `2026-08-14T02:09:49Z` (matches the disclosed recompute), `lv_anti_icp_flag_num='0'`, all other fields unchanged from before. `18047161864` (one of the 6 backfilled) shows `lv_anti_icp_flag_num='1'`, `hs_lastmodifieddate=2026-08-13T23:21:29Z` — matches the disclosed backfill. `scripts/check_tier_derived_parity.py` contains zero `requests.{post,patch,delete}` calls (confirmed by grep in this session) — its own D-16 guarantee is machine-checkable, not merely asserted. No third, undisclosed write was found. |

**Score:** 5/5 roadmap success criteria hold on the evidence available. 0 present-behavior-unverified. 1 disclosed, accepted open risk (reports/dashboards) routed to human verification rather than silently passed — this is why overall status is `human_needed`, not `passed`.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `lv_icp_tier_derived` (HubSpot company property) | Calculated string property reproducing WF1's ladder | ✓ VERIFIED | Live-fetched in this session: `calculated: true`, `label: "ICP Tier"`, formula matches pinned ladder exactly. |
| `lv_icp_tier` (old enum) | Archived, not deleted (HubSpot has no hard delete for properties) | ✓ VERIFIED | Live: 404 on direct GET, 200 + `archived: true` under `?archived=true`. Matches committed snapshot. |
| WF1 flow `4625147345` | Deleted per D-24 (overriding the original D-08 "kept, disabled" plan) | ✓ VERIFIED | Live: `GET /automation/v4/flows/4625147345` → 404, confirmed in this session. |
| `lv_anti_icp_flag_num` (numeric mirror) | Second new property, D-20 | ✓ VERIFIED | `src/icp_scoring.py::anti_icp_flag_properties` and `scripts/build_cloud_workflows.py`'s `Decide Company Action` node both emit it from one derivation (grep-confirmed, both engines). Live-observed values on 2 sample records (`0` and `1`) agree with `lv_anti_icp_flag`. |
| `tests/test_tier_formula_pin.py` | D-17 item 1 regression guard | ✓ VERIFIED | 14 tests, run in this session, all pass; mutation tests prove the guard has teeth (rejects moved bounds, demoted veto, sixth label, bare-boolean/coalesce-false guard shapes). |
| `scripts/check_schema_drift.py` | D-17 item 2, updated for retirement | ✓ VERIFIED | Re-run live in this session: `do_not_archive.ok=True`, `exit_code=0`. `RETIRED_FLOW_IDS` invariant correctly flipped to "healthy=absent" per D-24 (not "healthy=live+disabled" per the original D-08). 43 offline tests in `tests/test_check_schema_drift.py` pass. |
| `config/hubspot_properties.yaml` | D-17 item 3, synced | ✓ VERIFIED | `lv_icp_tier` block absent (matches archived live state); `lv_icp_tier_derived` present, labelled "ICP Tier". |
| `50-TIER-PARITY-EVIDENCE.md` | D-17 item 4, evidence artifact | ✓ VERIFIED | Present, and independently spot-checked live (5 stuck records + 2 additional sample records all matched). |
| `docs/OPERATOR-TIER-ROLLBACK.md` | D-18 rollback mechanism, amended for D-24 | ✓ VERIFIED | Amendment block at top states plainly that both original rollback mechanisms (re-enable WF1; portal-UI manual enrolment) no longer exist, and that rollback is now rebuild-from-JSON with three explicitly-named unverified gaps. This is an honest downgrade of the runbook, not a stale claim of a working one-action rollback. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/icp_scoring.py::anti_icp_flag_properties` | `lv_anti_icp_flag_num` write | pipeline PATCH | ✓ WIRED | Referenced in both the Python engine and `scripts/build_cloud_workflows.py`'s n8n `Decide Company Action` node from a shared comment anchoring "one derivation, two serializations" — grep-confirmed in both files. |
| `lv_icp_tier_derived` formula | `lv_icp_fit_score`, `lv_anti_icp_flag_num` | `calculationFormula` | ✓ WIRED | Live-fetched formula text references both properties exactly as pinned. |
| `scripts/check_tier_derived_parity.py` | live HubSpot company records | `src.hubspot_client.get_record`/`search_records` | ✓ WIRED, read-only | Confirmed via grep: no `requests.post/patch/delete` anywhere in the module. |
| `tests/test_tier_formula_pin.py` | live formula snapshot | `config/hubspot_flows/lv_icp_tier_derived-property.after.json` | ✓ WIRED | Test reads this file directly; file content independently re-confirmed live in this session to still match. |

### Independent live checks performed by this verifier (not just re-reading artifacts)

1. `GET /automation/v4/flows/4625147345` → 404 (WF1 deleted).
2. `GET /crm/v3/properties/companies/lv_icp_tier` → 404 (archived, not live).
3. `GET /crm/v3/properties/companies/lv_icp_tier?archived=true` → 200, `archived: true`, `archivedAt: 2026-08-14T02:17:57.731Z` (matches committed snapshot exactly).
4. `GET /crm/v3/properties/companies/lv_icp_tier_derived` → 200, `calculated: true`, formula text matches pinned ladder.
5. Fetched 7 company records live (5 known-stuck + Melbourne Racing Club + Simtech LED) — every field (`lv_icp_tier`, `lv_icp_tier_derived`, `lv_icp_fit_score`, `lv_anti_icp_flag`, `lv_anti_icp_flag_num`, `hs_lastmodifieddate`) matches the phase's committed evidence artifacts exactly, and `hs_lastmodifieddate` values corroborate the "no write outside the two disclosed D-16 deviations" claim rather than merely trusting the narrative.
6. Ran `scripts/check_schema_drift.py` live → `do_not_archive.ok=True`, `exit_code=0`.
7. Ran the full test suite: `.venv/bin/python -m pytest -q` → 2821 passed, 154 skipped, 0 failed. `node --test tests/n8n/*.test.mjs` → 683 passed, 0 failed. `tests/test_tier_formula_pin.py` (14 tests) individually confirmed passing.
8. Grepped `src/icp_scoring.py`, `scripts/check_schema_drift.py`, `scripts/check_tier_derived_parity.py`, `scripts/sweep_tier_dependents.py`, `scripts/build_cloud_workflows.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` — zero matches.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| TIER-01 | 50-01/03/05/06 | Derived tier reproduces WF1's ladder exactly, no event dependency | ✓ SATISFIED | See truth #1/#2 above. Live-verified independently. |
| TIER-02 | 50-01/06 | Null semantics for never-scored companies is a recorded, correct choice | ✓ SATISFIED | See truth #3. The D-04→D-21 self-correction is itself evidence of a well-functioning process (a wrong finding caught and fixed with a stronger evidence bar, D-22), not a red flag. |
| TIER-03 | 50-02/04/05 | Cutover reversible, dependents enumerated, nothing silently breaks | ⚠️ PARTIALLY SATISFIED — machine-checkable scope complete; one disclosed residual open | See truth #4. REQUIREMENTS.md marks TIER-03 "Complete" — this verifier agrees the phase did everything within its reachable means (scripted sweep re-run 3x, saved views operator-attested migrated, disposition of enum/WF1 explicitly decided under D-24), but disagrees that "nothing silently breaks" can be marked fully closed while reports/dashboards remain genuinely unconfirmed. This is not a defect in the phase's execution — HubSpot provides no way to close it — but it is not a verified truth either. See Gaps/Human Verification. |

No orphaned requirements found — TIER-01/02/03 are the only IDs declared for Phase 50 in both `REQUIREMENTS.md` and this phase's plan set.

### Anti-Patterns Found

None in the phase's core deliverable files (`src/icp_scoring.py`, `scripts/check_schema_drift.py`, `scripts/check_tier_derived_parity.py`, `scripts/sweep_tier_dependents.py`, `scripts/build_cloud_workflows.py`). No debt markers, no placeholder returns, no empty handlers.

### Behavioral Spot-Checks / Probe Execution

Not a scaffolded-CLI or build-output phase in the Step 7b sense; this phase's "runnable" surface is (a) a regression test suite, which was run in full (see above), and (b) live HubSpot API state, which was independently queried and cross-checked against every material claim in the evidence artifacts (see "Independent live checks" above). No separate probe scripts (`scripts/*/tests/probe-*.sh`) exist for this phase.

## Adversarial notes — scrutiny of the amendments specifically flagged in the task

**D-23 (widening D-07's accepted-divergence set from 4 to 5 records, adding Coffs Harbour `14752488879`):** This is legitimate, not a result being explained away. The distinguishing fact is polarity: ids 9–12 are the pre-registered "stale enum reads worse than the derived property" class (`C`→`B`), which the gate was built to tolerate. Id 14 is the *same underlying WF1-staleness mechanism* but in the *opposite* direction (`Unscored`→`C`) — the derived property is *more correct* than the enum it replaces, not less. Widening the exception set to admit a case where the new property outperforms the old one is a different act than widening it to explain away a defect. `WINDOWS.md` id 14 is still logged with `status: open` (not `fixed`) — this is honest bookkeeping: nothing was "fixed" for this record (no PATCH occurred), the derived tier was simply always correct once it existed. Minor documentation nit, not a blocker: id 14's open status could arguably be revisited now that `lv_icp_tier` is archived and the derived property is the sole live source of truth, but leaving it open is defensible and not misleading.

**D-21 (reversing D-04 after the original probe was found to be a race):** This is the phase catching its own error with a stronger evidence bar (D-22: mandatory polling), not evidence of sloppy work. The original wrong probe (`50-NULL-PROBE.json`) was deliberately left committed unaltered as historical record, and the correction is documented in both `50-CONTEXT.md` and `REQUIREMENTS.md`'s TIER-02 row rather than quietly overwritten. This verifier independently confirmed the *currently shipped* formula is the corrected (uncoalesced) variant, live.

**D-20 (the veto guard defect — `lv_anti_icp_flag_num` mirror):** `WINDOWS.md` id 13 documents that the derived property was, for a period, *actively worse* than the stale enum it was meant to replace (the D bucket silently emptied from 6 to 0). This is disclosed as `fixed` with a resolved_at timestamp and a specific commit reference (`13fac29`/`b12266a`), and this verifier independently confirmed the fix is live (2 sample vetoed/non-vetoed records both read correctly, `lv_anti_icp_flag_num` present and agreeing with the boolean).

**D-24 (WF1 deleted rather than merely disabled, overriding D-08):** This is the phase's most consequential irreversible act. It is documented plainly as an override, with the operator's verbatim choice recorded and the consequence (loss of the proven one-action rollback; rollback is now rebuild-from-JSON with three explicitly-named unverified gaps) stated without softening in `docs/OPERATOR-TIER-ROLLBACK.md`'s amendment block. This verifier independently confirmed WF1 is genuinely gone (404) and the rollback JSON (`config/hubspot_flows/4625147345-wf1-set-icp-tier.before.json`) is the only remaining rebuild source — the runbook does not overstate its own currently-broken state.

**Operator attestation vs. machine-checked evidence:** Two claims in this phase rest on operator attestation rather than an API this repo can call: (1) saved views were migrated off `lv_icp_tier` — verbatim operator statement, dated, but not independently re-verifiable by any script; (2) the D-18 rollback drill (portal-UI manual enrolment) "passed" — verbatim operator statement of a 5-step manual UI process, no API trace exists of it. Both are disclosed as attestations in their own source documents (`50-DEPENDENTS-SWEEP.md`, `50-ROLLBACK-DRILL.md`) rather than dressed up as machine-verified facts, which is the correct way to record them — but this verifier flags both explicitly rather than silently accepting them as equivalent to the machine-checked evidence elsewhere in this phase.

## Gaps Summary

No BLOCKER-level gap. The phase goal — `lv_icp_tier` no longer depends on a HubSpot
property-change event — is achieved and independently confirmed live: the old event-driven
enum and its sole writer (WF1) are gone; a calculated property with a live-verified, regression-pinned
formula is the sole functional source of truth; the 5 known-stuck records read correctly with
zero record writes; the null/blank semantics question was answered, and a wrong initial finding
was caught and corrected before shipping. All company writes made during the phase are accounted
for and match the phase's own D-16 disclosure.

The one WARNING-level item is the disclosed, still-open "reports/dashboards may reference the
now-archived `lv_icp_tier`" residual. The phase's own artifacts are explicit that this is
unresolved and unresolvable by this repo (no API), and that the operator chose to proceed and
accept the risk. This verifier agrees that is a defensible operational decision, but it means
TIER-03's "nothing silently breaks" cannot be marked VERIFIED end-to-end — it is routed to human
verification below rather than folded into a `passed` status, per the escalation-gate pattern
this agent implements.

---

_Verified: 2026-08-14_
_Verifier: Claude (gsd-verifier)_
