# 47-04 Summary — the armed window

**Completed:** 2026-08-12 · **Result:** goal met, with two disclosed misses against the plan's
own `must_haves`.

## What happened

All 17 pinned companies were written. **16 false non-ANZ vetoes cleared. Jam TV
`17317850381` correctly retained its veto** (D-23 — it is the Italian broadcaster
`jamtv.it`; Phase 46 mislabelled it `false_veto` only because its region was blank).

| Bar | Result |
|---|---|
| VETO-01 | 16 cleared + 1 correctly retained; per-id table in `47-RUN-REPORT.md` |
| VETO-02 | Both surfaces disarmed, proven by independent re-read, quoted verbatim |
| VETO-03 | **Operator-confirmed zero** ("no Non-ANZ geography companies with Unknown region"), 2026-08-12 |
| Portal-wide census | non-ANZ veto + blank region: **17 → 0** |
| Tiers after | B×9, C×5, Unscored×2, D×1 |
| Cost | 18 n8n executions (of 2,500/mo), 0 provider credits, 0 research calls (ran `--from-cache`) |
| Tests | pytest 1248 passed / 123 skipped; `node --test` 658 pass / 0 fail |

## Two misses, stated plainly

1. **must_have #1 — "ONE armed window" — was NOT met.** There were **five** arm/disarm
   cycles across six run attempts, and D-01's touch-once broke for two records
   (`9604732797` twice in window 1; `18047161864` in windows 4 and 5). Every cycle armed the
   identical 17-id allowlist and every disarm was independently re-read, so blast radius
   never widened — but one window is a stated requirement and it was missed. Full ledger:
   `47-RUN-REPORT.md` § "Window accounting".
2. **Two named checks were relaxed** — the D-20 re-stamp (dropped; it cannot converge) and
   the oracle-tier settle assertion (recorded, not asserted; that is Phase 49's parity
   scope). Both were put to the operator and both are recorded as relaxations rather than
   quietly satisfied. `settle_veto`, the actual veto bar, stayed hard throughout.

## Why five windows: the plan did not survive contact

Six assertions in `47-04-PLAN.md` were unsatisfiable by the deployed system. Each was found
only by running against it, five were approved by the operator before use, and one (#4) was
a mechanical call I made and disclosed.

1. `settle_tier` ran before the webhook POST, but WF1 pins `lv_icp_tier` to `D` while the
   stale flag reads `true`, and only the webhook clears it — unsatisfiable for exactly the
   records this phase targets.
2. **D-23 near-miss.** `_normalize_region('Italy')` returns `None`, and the deployed
   `_regionKey("")` maps blank to `"unknown"`, not `"non_anz"` — so the run **as planned
   would have cleared Jam TV's correct veto**, turning a disqualified Italian broadcaster
   into a live prospect. Nothing downstream would have caught it: `settle_veto`, the Task 2
   automated verify and the VETO-03 search all pass on a cleared flag. Only the pre-arm read
   caught it. `region="Other"` is now written and the veto asserted to persist.
3. Live tier cannot match the oracle's — n8n resolves `lv_org_type` downstream of it.
4. Webhook `timeout=30` is shorter than the research lane; n8n completed writes the client
   had already given up on.
5. The D-20 re-stamp cannot converge — n8n writes its own `*_verified_at` after ours.
6. `Company Gate` skips records whose inputs are complete, so `Decide` never recomputes
   their veto. → **Phase 47.5**.

## Findings raised

- **Phase 47.5 — Veto Recompute Path** (scoped, registered in ROADMAP): a record with
  complete inputs cannot have its veto recomputed by any on-demand trigger. Compounds
  forward — Phase 48 completes 18 more records. `tests/…::test_veto_clear_after_correction`,
  red since Phase 40-07, fails for exactly this reason and is its acceptance test.
- **D-V6 re-examination work-list** — after this window exactly 4 companies portal-wide
  carry a non-ANZ veto, all with populated regions. Jam TV is correct; Ironman (**score 70**,
  Tier A material, suppressed on a Tampa HQ), Gravity Media and Entain were set under the old
  HQ reading. Todo committed.
- **Hardware veto is near-unreachable** — it keys off `lv_is_hardware_vendor`, which exactly
  1 of 66 companies has set, not off `lv_org_type`. Simtech LED (researched
  `hardware_vendor`) landed Tier B; Supertech landed D. Todo committed.
- **Research-lane row-loss proven fixed live** — 17 webhook runs, no `merge: null`, no lost
  rows. Project memory updated from "never run live".

## Stale assertions corrected

- `veto_remediation_report.classify()` gained `correct_non_anz` — without it `--mode after`
  **refused on the correct end state**. Exemption keyed by id, pinned by two tests.
- `remediate_veto_companies.py`'s org-type gate comment claimed free text `400`s the batch;
  it does not — HubSpot accepts it and it scores `0` silently. Silent-zero makes the gate
  *more* necessary, so the wrong reason was a live risk of someone removing it.
- `46-SIMULATION-REPORT.md`'s Jam TV `false_veto` label corrected — Phase 49 reads that file
  and would have re-targeted a correct veto.
- `tests/fixtures/companies_jscode_frozen.json` checked and deliberately **not** re-baselined
  (it holds research inputs, not expected CRM state). The research claim that no test
  references the 17 ids by literal value was wrong — ten appear.

## Artifacts

```
47-AFTER.json          17-row after-snapshot
47-RUN-LOG.json        per-record write/settle log
47-RUN-REPORT.md       § Plan 04 — actuals, window accounting, D-20, gate defect, Rule 1
47-COST-ESTIMATE.md    Actuals table filled
47-armed-driver.py     the corrected-order driver actually used
```

Commits `196b2d3` → `f289adc`.

## Not closed here

COVER-01 / COVER-02 remain open for Phase 48 per D-02 — four records ended with no
`lv_org_type` (Editix, Jam TV, Waikato, The Rumble).
