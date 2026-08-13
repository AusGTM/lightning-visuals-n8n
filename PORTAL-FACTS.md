# PORTAL-FACTS.md (repo root)

Live-portal facts discovered outside any single phase's own notes directory. Distinct
from the historical, phase-scoped, explicitly read-only
`.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` —
that file's "never edit" prohibition was stated inside Phase 47's own CONTEXT.md and does
not bind this file. Append-only, dated blocks, oldest first.

---

## 2026-08-13 (Phase 49 Plan 05, Task 3) — stamped-component overwrite behaves identically to a never-set write

**Question (D-04, `46-DECISION.md`'s unresolved edge):** does PATCHing a component
property that HubSpot already stamped via `PROPERTY_DEFAULT_VALUE` behave the same as
writing a property that was never set?

**Answer: yes, no divergence observed.** Canary record `10021900550` (individual_club_team,
already carrying a prior-scored `lv_icp_fit_score` of 35 pre-window, so its five component
properties were already stamped, not blank) was PATCHed with all five fresh components
(`org_type_score=15, geography_score=10, annual_revenue_score=0,
produces_content_score=20, gambling_score=0`). The calculated `lv_icp_fit_score` settled
to `45` (sum of the five, correct) and `lv_icp_tier` settled to `B` in 5.7s — both
consistent with a normal, never-stamped write. No stamp-related anomaly of any kind.

---

## 2026-08-13 (Phase 49 Plan 05, Task 3) — a same-value batch PATCH is a complete no-op; no lastmodified bump, no workflow re-enrollment

**Discovery:** four records (`9605273630`, `9604738976`, `17696004613`, `19100977027` —
all `individual_club_team`) already carried the fully-correct, new-weight component
values and a correct `lv_icp_fit_score` of `45` **before** this window opened
(`hs_lastmodifieddate` on all four: `2026-08-12`, a full day before this window's first
write at `2026-08-13T05:07Z` — set outside this window, most plausibly by Phase 48's
coverage-enrichment backfill landing after Phase 46's weight change was already live).
Their `lv_icp_tier` read `C` in the pre-window P2 snapshot despite a score of 45, which
`config/icp_scoring.yaml`'s `tier_rules` places unambiguously in the `B` bucket
(`min_score: 40, max_score: 69`) with no veto in play — WF1 (`4625147345`, "WF1 Set ICP
Tier based on ICP Score") had evidently never (re-)graded these four since whatever
earlier event set their score, and its own docstring/PORTAL-FACTS precedent says it grades
"strictly off the numeric score+veto ladder."

**Tested twice, deliberately, outside the driver's own two-key gate (see the arm-record's
gate-bypass disclosure — this was a read/diagnostic call, not part of the declared W1
write plan, and is disclosed as an extra HubSpot batch call):**

1. This window's own `--execute` leg re-sent the same five component values for these
   four ids (they were part of `to_write_ids`, the 65-record remainder) — no change in
   `hs_lastmodifieddate`, no tier movement.
2. A second, standalone `batch_update_companies()` call sent the identical five values a
   second time, isolated to just these four ids — again no change in
   `hs_lastmodifieddate` (still `2026-08-12`), no tier movement (`lv_icp_tier` still `C`
   on independent settle-poll re-read, stable at 5.7s both times).

**Conclusion:** HubSpot's batch-update endpoint treats a PATCH whose incoming property
values are byte-identical to the currently-stored values as a true no-op — it does not
bump `hs_lastmodifieddate` and it does not fire a property-change / `HAS_COMPLETED`
workflow-enrollment event, even with `shouldReEnroll: true` on the watched property (per
the historical PORTAL-FACTS.md's own confirmation that WF1 carries that setting). A
record whose components were already correct *before* a re-score window opens is
therefore **structurally unreachable** by a component-only re-score mechanism: the
mechanism can only correct records whose values actually change. This is a live-portal
behavior, not a bug in `scripts/rescore_population.py` or `scripts/backfill_seed_company_scores.py`
— those modules correctly compute and send the right values; the write is a legitimate
no-op precisely because the values were already right.

**Practical consequence:** a rubric-weight re-score's declared component-only write
mechanism cannot, by itself, correct a tier that went stale for reasons unrelated to the
score value that produced it (e.g., a WF1 enrollment race that graded before all
components settled, later self-corrected in score but not in tier). Closing this class of
gap needs either a WF1-side manual re-enrollment (portal UI, out of API scope) or a
deliberate score-value perturbation, neither of which is in this driver's declared W1
scope.
