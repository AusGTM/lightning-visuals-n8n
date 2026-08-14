# D-18 rollback drill — portal-UI manual enrolment, proven live

**Date checked:** 2026-08-14
**Portal:** `22617666`
**WF1 state at drill time:** `4625147345` ("WF1 Set ICP Tier based on ICP Score") — **on**,
confirmed by the operator immediately before enrolling (step 1 of the instructions in
`50-04-PLAN.md` Task 50-04-02). WF1 remains on after this drill; nothing in this drill or this
plan switches it off.

## Subject

| Field | Value |
|---|---|
| Company id | `9604614548` |
| Company name | Melbourne Racing Club |
| Row in `50-TIER-PARITY-EVIDENCE.md` | `match` (`lv_icp_tier` = `C`, `lv_icp_tier_derived` = `C`, score 35, veto false) |
| One of the 4 stuck ids named in `50-04-PLAN.md`'s prohibitions (D-07's original expected-mismatch set)? | No |

Selected per the plan's constraint: any confirmed `match` row, excluding the 4 stuck records
listed in `50-04-PLAN.md`'s `<prohibitions>` and `50-CONTEXT.md`'s D-07 — running WF1 on any of
those would violate this phase's own "no event, no enrolment, no workflow run" success criterion
for that set and would contaminate D-07's pre-registered expected-mismatch class.

## What was done

1. Operator confirmed WF1 `4625147345` was on.
2. Operator read the subject's `lv_icp_tier` before enrolling: **`C`**.
3. Operator manually enrolled the subject into WF1 (portal UI — companies index page /
   inside-workflow enrolment; there is no API for this, RESEARCH Q1).
4. Operator confirmed, in WF1's execution history, that the enrolment **completed** for this
   record.
5. Operator re-read the subject's `lv_icp_tier` after: **`C`** — unchanged.

**Operator attestation (verbatim, 2026-08-14):** "The operator ran the portal drill. It PASSED."
— with the five numbered answers above, confirming WF1 on, tier before `C`, enrolment done,
execution history confirmed, tier after `C`.

## What this proves

Portal-UI manual enrolment is a **real, available mechanism** for forcing a HubSpot-native record
into WF1 with no property-change event as a prerequisite. That is the crux of D-18: re-enabling
WF1 alone re-grades nothing, because a value-identical record fires no event; manual enrolment
bypasses the event requirement entirely, and this drill shows HubSpot's portal accepts and
completes that enrolment on demand.

It also confirms the mechanism's precondition in practice, not just on paper: it requires WF1 to
be **on** at the moment of enrolment, which is exactly why this drill had to run before Plan 05's
WF1-off task — proving it afterwards would have been impossible (see `docs/OPERATOR-TIER-ROLLBACK.md`
Step 2).

## What this does NOT prove — stated explicitly, not implied

- **The subject's tier was already correct before the drill (`C` -> `C`).** The drill demonstrates
  that manual enrolment *runs and completes*. It does **not** independently re-demonstrate that
  WF1 *re-grades a stale record* — WF1's grading logic itself was never in doubt and is not what
  this drill tests.
- **Coffs Harbour Racing Club `14752488879` was deliberately NOT used**, even though it is the
  genuinely stale record this mechanism exists to fix. Enrolling it would flip its `lv_icp_tier`
  from `Unscored` to `C`, which would break the `Unscored -> C` transition that **D-23**
  (`50-CONTEXT.md`, `scripts/check_tier_derived_parity.py::KNOWN_STUCK_IDS`) pinned as one of the
  5 accepted-divergence records, turning D-07's now-GREEN parity gate back to RED. Using the
  stronger subject would have been a more convincing proof of re-grading, at the direct cost of
  invalidating a separate, already-settled gate this same phase depends on. That trade was
  rejected.

## Company writes

**Zero.** Manual enrolment is a workflow action; the subject's `lv_icp_tier` did not change
(value-identical, `C` -> `C`). This drill spends no company-write budget. The phase's one
authorised **D-16** deviation (50-06's 6-record numeric-veto-mirror backfill) remains the only one
spent in Phase 50.

## Disclosure — D-16 framing

Per the plan's acceptance criteria, this is recorded as a WF1-authored, value-identical write
touching the subject company, disclosed here rather than silently absorbed: WF1's own action
sequence wrote `lv_icp_tier = C` over the pre-existing `C`. It is not a repo-script write and it
changed no value, but it is named here in the same spirit as every other write-adjacent action
this phase discloses. It does not count against **D-16**'s zero-company-write-window declaration,
which governs writes made *by this repo's own scripts*, not by HubSpot's own workflow engine
acting through a human-triggered enrolment.
