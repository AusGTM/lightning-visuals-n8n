# Quick Task 260823-ono: Metro peak-body named-account override rule (ATC, MRC, SSR, BRC, Perth Racing → high B) - Context

**Gathered:** 2026-08-23
**Status:** Ready for planning

<domain>
## Task Boundary

Narrow override rule so the five Australian metro racing peak bodies — Australian Turf Club
(9605284724), Melbourne Racing Club (9604614548), Southside Racing (18756544344), Brisbane Racing
Club (9605284723), Perth Racing (9604794662) — tier as high B in HubSpot ICP scoring. They govern
and own tracks for smaller child clubs and influence broadcasting via partner connections, which
the `individual_club_team` org type (15 pts) under-weights.

Baseline (live read 2026-08-23): ATC/SSR/BRC score 55 tier B; MRC 35 tier C; Perth Racing
unscored (all inputs blank). All `individual_club_team`, no vetoes.

</domain>

<decisions>
## Implementation Decisions

### Override mechanism — HubSpot-native, operator-editable
- The scoring engine already lives in HubSpot: `lv_icp_fit_score` is a calculated property
  (`org_type_score + coalesce(geography_score,0) + coalesce(annual_revenue_score,0) +
  coalesce(produces_content_score,0) + coalesce(gambling_score,0)`), `lv_icp_tier_derived` is
  calculated from it. Pipeline writes only the component `*_score` numbers + `lv_anti_icp_flag_num`.
- Override = edit the `lv_icp_fit_score` calculation formula to read a new enumeration property
  `lv_named_account_priority` (spec'd in CLAUDE.md §5.2, never created). No recompute POST, no n8n
  change — HubSpot recalculates on property change (~70–130s backfill).
- A repo-only yaml named-account list was explicitly REJECTED: a HubSpot-only operator could not
  edit it.

### Enum + floor
- Create `lv_named_account_priority` (companies, enumeration) with the spec'd options:
  `core_racing`, `non_racing_best_fit`, `producer_secondary`, `low_priority`, `unknown`.
- Only `core_racing` has effect in this task: score floor 60 — `max(base, 60)`.
- Floor only, NO cap: an earned base ≥ 70 stays Tier A.
- Other enum values: no scoring effect yet.

### Perth Racing (blank inputs)
- Override forces 60 / Tier B even when `org_type_score` is null (the "never scored" sentinel).
  Formula must coalesce inputs inside the `core_racing` branch only; the non-override branch keeps
  `org_type_score` unguarded so blank still means "never scored" for everyone else.
- Perth's inputs are NOT hand-filled in this task; Phase 52 backfill owns that.

### Live write, this task
- Create property → push formula (`scripts/apply_fit_score_formula.py`, `ALLOW_FORMULA_WRITE=true`
  gate, archive `config/hubspot_flows/lv_icp_fit_score-property.after.json` is source of truth) →
  PATCH `lv_named_account_priority=core_racing` on the 5 ids → poll `lv_icp_tier_derived`
  (never a single immediate read) → confirm 5 × B, scores ≥ 60.
- Operator approval gate before each live write surface (property create, formula push, record PATCH).
- Python oracle `src/icp_scoring.py` mirrors the rule so `scripts/check_tier_derived_parity.py`
  (D-07 gate) stays green; re-run it after the write and confirm the other 61+ records unchanged.

### Claude's Discretion
- Exact formula text (statement-form if / coalesce grammar per memory `hubspot-calculation-formula-grammar`).
- Whether the floor lives in `lv_icp_fit_score` (preferred — score itself reflects override) vs
  `lv_icp_tier_derived`.
- Spike shape for "can calculation_equation read an enumeration property" — booleans are known
  unreadable (always null); enum unverified; a bad formula 400 lists valid tokens. If enum proves
  unreadable, fall back to a numeric mirror property (e.g. `lv_named_account_priority_num`) written
  alongside, and surface that to the operator before building.
- Add property to fetch lists / `check_schema_drift.py` expectations as needed.

</decisions>

<specifics>
## Specific Ideas

- Expected post-write: ATC 55→60 B, SSR 55→60 B, BRC 55→60 B, MRC 35→60 B, Perth blank→60 B.
- Record predictions before any write; compare polled actuals against them; any mismatch = defect.

</specifics>

<canonical_refs>
## Canonical References

- CLAUDE.md §5.2 (`lv_named_account_priority` spec), §10 rubric, §13.0 recompute lane (NOT needed here)
- `config/hubspot_flows/lv_icp_fit_score-property.after.json`, `scripts/apply_fit_score_formula.py`
- `scripts/check_tier_derived_parity.py`, `scripts/check_schema_drift.py`
- `.planning/phases/41-validation-data-import-end-to-end-proof/41-FORMULA-SPIKE.md` (null-blanking behaviour)
- memory: hubspot-calculation-formula-grammar, hubspot-calculated-property-runtime-semantics, hubspot-property-api-gotchas

</canonical_refs>

---

## Amendment 2026-08-23 — CP1 outcome and operator decision (supersedes "Enum + floor" above)

**CP1 verdict: `halt-b`.** The armed enum-readability probe (`scripts/probe_enum_in_formula.py`,
verdict in `260823-ono-PROBE-VERDICT.json`) exhausted all 5 variants. Every variant parsed (P1)
but none read the enum's value (P2 false on all 5): on the `is_present`-guarded variant the
never-enriched control computed `MISS` at 90.8s while ATC — which has `lv_org_type` set — stayed
null at the same mark. `string(<enum>)` parses but blanks the formula once the enum has a value.
Phase 50 D-20 stands; RESEARCH's false-negative theory is refuted live. All 5 disposables archived,
none leaked.

**Operator decision: Option 1 — single NUMBER property, no enum, no mirror.**

- Create `lv_named_account_score_floor` (companies, `number`, operator-editable). Operator types
  `60` on a record to floor it; blank = no override.
- `lv_icp_fit_score` formula: when `coalesce(lv_named_account_score_floor, 0) > 0`, score =
  `max(<branch-coalesced base>, lv_named_account_score_floor)`; otherwise the existing formula
  verbatim with `org_type_score` still unguarded (blank = never scored sentinel). No cap.
- Perth Racing (blank inputs) must score 60 when the floor is set — coalesce inputs inside the
  floor branch only.
- The enumeration `lv_named_account_priority` is NOT created in this task (YAGNI — second
  irreversible property with zero scoring effect). Revert its yaml declaration so
  `check_schema_drift.py` returns to green; CLAUDE.md §5.2 keeps it as roadmap only, with a note
  that calculation formulas cannot read enumerations on this portal. Operator may re-raise if the
  label vocabulary is wanted.
- Oracle `src/icp_scoring.py` reads `lv_named_account_score_floor` (number) instead of the enum;
  same floor semantics, same no-"Needs Review"-downgrade-when-floored rule; tests follow.
- `scripts/set_named_account_priority.py` becomes a floor-setter writing
  `{"lv_named_account_score_floor": 60}` on exactly the 5 ids; rename accordingly.

**Operator-mandated live test BEFORE the production formula push — "if the floor is null, does
it still contribute to scoring?"** A new disposable probe (same discipline as CP1: disposable
property names, archive in `finally`, confirm gone) must prove on this portal:
  (a) floor null on a scored record (ATC-like) → calculated value == current base (55), not blank,
      not altered;
  (b) floor null on a never-enriched record → calculated value stays BLANK (sentinel preserved);
  (c) floor = 60 on a record with blank inputs → 60;
  (d) floor = 60 on a record with base > 60 (Tier A control, base 80) → base, not 60 (no cap,
      max semantics);
  (e) floor = 60 on a base-55 record → 60.
The probe uses a disposable NUMBER property as the floor input and a disposable CALCULATED
property carrying the candidate formula, set on the minimum records needed (ATC, the never-
enriched control `9604773165`, the Tier A control `9605284722`, Perth), then clears the
disposable number values and archives both disposables. Record writes touch ONLY the disposable
property. Armed by the operator; this is checkpoint 1b. Only a passing (a)–(e) authorises CP2.

Ordering stays: Task 1 revisions (offline) → CP1b probe → Task 2 settle formula → CP2 create
number property + push formula → CP3 PATCH floor=60 on 5 ids → Task 3 verify/poll/docs.
