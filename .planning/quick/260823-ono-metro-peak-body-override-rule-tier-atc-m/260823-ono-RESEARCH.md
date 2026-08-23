# Quick Task 260823-ono: Metro peak-body override rule — Research

**Researched:** 2026-08-23
**Domain:** HubSpot `calculation_equation` grammar + repo scoring-oracle parity
**Confidence:** HIGH on grammar/integration surface, MEDIUM on the one open question (enum readability) — which has a pre-authorized fallback and a cheap probe.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Override lives in HubSpot, not a repo yaml (a repo list is not operator-editable) — **REJECTED alternative**.
- Create `lv_named_account_priority` (companies, enumeration) with options `core_racing`,
  `non_racing_best_fit`, `producer_secondary`, `low_priority`, `unknown`.
- Only `core_racing` acts: **score floor 60**, `max(base, 60)`. Floor only, **no cap** — an earned base ≥ 70 stays Tier A.
- Override branch coalesces inputs so Perth Racing (all blank) scores 60; **non-override branch keeps `org_type_score` unguarded** so blank still means "never scored" for everyone else.
- Live write sequence: property create → formula push (`apply_fit_score_formula.py`, archive is source of truth) → PATCH the 5 ids → **poll** `lv_icp_tier_derived` → confirm 5 × B.
- Operator approval gate before each live write surface.
- Python oracle mirrors the rule; parity stays green; other records unchanged.

### Claude's Discretion
- Exact formula text; floor in `lv_icp_fit_score` (preferred) vs `lv_icp_tier_derived`.
- Spike shape for "can `calculation_equation` read an enumeration"; **numeric mirror fallback if not, surfaced to the operator before building**.
- Adding the property to fetch lists / `check_schema_drift.py` expectations.

### Deferred / out of scope
- Perth Racing's real inputs (Phase 52 backfill owns them).
- Scoring effects for the other four enum values.

---

## Headline finding — the enum question is *not* settled, and the repo's negative is probably an artifact

The repo carries a locked conclusion (D-20, 50-CONTEXT.md, live-proven 2026-08-14) that
`calculation_equation` **reads only numeric properties**:

> "enumerations are rejected outright at property-create ("Sub-expression output type: String is
> not compatible with input type: BigDecimal") — as are string and boolean literal comparisons.
> So every input the veto is built from (`lv_anti_icp_flag`, `lv_produces_content`,
> `lv_is_hardware_vendor`, `lv_org_type`, `lv_country_region_normalized`) is unreadable"
> [VERIFIED: .planning/phases/50-derived-tier-property/50-CONTEXT.md:176-183, read this session]

**But every rejected attempt used a *bare identifier*.** HubSpot's API docs state the required
syntax explicitly:

> "all identifiers will be interpreted as **number** property variables"; string properties
> "must be wrapped in the `string` function"; booleans "must be wrapped in the `bool` function"
> [CITED: developers.hubspot.com/docs/guides/api/crm/properties]

That is exactly the error the repo saw: a bare `lv_org_type` is parsed as a *number* variable, so
comparing it to `'hardware_vendor'` yields "String is not compatible with BigDecimal". Three
corroborating facts, all from repo primary sources read this session:

1. `string` and `bool` **are in the portal's own 400-body token list** —
   `… format_phone_number, …, validate_when, if, (, NOW, DECIMAL, scientific number literal,
   string literal, true, false, e, TARGET, IDENTIFIER, bool, string, timestamp, +, >, …`
   [VERIFIED: .planning/milestones/v0.7-phases/41-validation-data-import-end-to-end-proof/41-FORMULA-SPIKE.md:138-151]
2. This portal already runs a `string()`-wrapped statement-form formula in production:
   `if is_present(string(name)) then string(name) else string(domain)` — HubSpot's stock
   `hs_task_label` [VERIFIED: .planning/phases/50-derived-tier-property/50-RESEARCH.md:239]
3. The Phase 50 spike's Round 1 rejections are all bare/unwrapped:
   `if lv_anti_icp_flag then …` and `coalesce(lv_anti_icp_flag, false)`
   [VERIFIED: .planning/TIER-DERIVATION-SPIKE-2026-08-13.md:67-68] — `bool(...)` was never tried.

**What this means for the plan:** do not accept the mirror property as forced. A created property
is **irreversible** (DELETE is a soft archive; the internal name is never reusable —
[VERIFIED: 50-NULL-PROBE.json `archived_listing_finding.calculated_property_reappears: true`]),
so spending one on an untested premise is the expensive mistake here. Run the probe below first;
it costs two disposable properties and zero population writes.

### The probe (Task 1 of the plan) — uses `lv_org_type`, no new property needed

`lv_org_type` is an existing enum with both populated and blank records, so all three questions
can be answered before `lv_named_account_priority` exists. Harness already in repo:
`scripts/check_tier_null_propagation.py::_create_calculated_property` / `_archive_and_confirm_gone`
(POST/GET/DELETE `crm/v3/properties/companies`, disposable naming, teardown assertions)
[VERIFIED: scripts/check_tier_null_propagation.py:144-192].

| # | Question | Probe formula (disposable, `type: string`) | Read on |
|---|----------|--------------------------------------------|---------|
| P1 | Does the wrapper **parse**? | `if string(lv_org_type) equals 'individual_club_team' then 'HIT' else 'MISS'` | create returns 200 vs 400 |
| P2 | Does it read the **value**? (parse ≠ readable — the booleancheckbox parsed and still read null) | same property | ATC `9605284724` → must poll to `HIT` |
| P3 | Does a **null enum in the condition** blank the whole result? | same property | any never-enriched company → must poll to `MISS`, **not blank** |

**The probe is a live write surface.** A disposable calculated-property create is a property
create — it takes the **same operator approval gate** CONTEXT requires for property create /
formula push / record PATCH, and the same two-key + portal gate as step 1 below. Sequence it as
**step 0** of the write discipline table, not as a free read.

**Do not repeat Phase 50's mistake.** D-20 concluded "unreadable" from a single syntax variant.
A 400 on P1 means *that variant* failed, nothing more. On any 400: read the token list the API
returns **at the failing parse position** (it is positional — that is the whole value of the
41-spike finding) and exhaust the variants before falling back:
`equals` vs `=` (both in the token list; `equals` is only live-proven against a *number*),
single vs double quotes (HubSpot canonicalizes `"`→`'` but the submitted form may still matter),
`string(x) equals 'v'` vs `contains(string(x), 'v')`. Only after the variants are exhausted is
Formula B forced.

**D-22 is mandatory on all three:** poll to a populated value or a fixed ≥3 min ceiling. Values
backfill ~70–130s after create; a single immediate read-back is no evidence and is precisely the
race that produced the wrong D-04 conclusion [VERIFIED: 50-CONTEXT.md:207-213].

- **P1+P2+P3 all pass →** ship the single-property design (Formula A). No mirror, no drift risk.
- **Any fail →** CONTEXT's pre-authorized fallback: add `lv_named_account_priority_num`
  (number, `1` for core_racing, blank/0 otherwise) and ship Formula B. **Surface to the operator
  before building** — CONTEXT requires it, and it changes the operator's job from "set one
  dropdown" to "set two fields in sync".
- If P3 alone fails, the cheap repair is `is_present`-guarding the condition rather than a new
  property: `if is_present(string(lv_named_account_priority)) and string(...) equals 'core_racing'`
  (`is_present` and `and` are both in the token list). Probe that variant before escalating.

**Recommend against** a HubSpot Automation flow syncing enum → num: Phase 50 deleted WF1 outright
because a flow reference (even a disabled one) blocks property archival with
`CANNOT_DELETE_PROPERTY_IN_USE`, and flow-written values carry the staleness bug class the phase
existed to retire [VERIFIED: scripts/check_schema_drift.py:100-118, D-24 comment block].

---

## Formula drafts

Live formula today [VERIFIED: config/hubspot_flows/lv_icp_fit_score-property.after.json,
`calculationFormula`, read this session]:

```
org_type_score + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0)
```

`max` **exists and is two-arity**: "max(arg1, arg2) — Get the maximum of two numbers"
[CITED: knowledge.hubspot.com/properties/create-calculation-properties]; also present in the
portal's own token list [VERIFIED: 41-FORMULA-SPIKE.md:139].

**Formula A — enum readable (preferred, pending probe):**

```
if string(lv_named_account_priority) equals 'core_racing' then max(coalesce(org_type_score, 0) + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0), 60) else org_type_score + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0)
```

**Formula B — numeric mirror fallback** (swap only the condition; identical proven idiom to the
live tier veto guard `coalesce(lv_anti_icp_flag_num, 0) = 1`):

```
if coalesce(lv_named_account_priority_num, 0) equals 1 then max(…same then-branch…, 60) else …same else-branch…
```

Why this shape holds:
- **Perth (all inputs blank)** takes the then-branch, every term coalesced → `max(0, 60)` = **60**.
- **Never-enriched non-named records** take the else-branch, hit the unguarded `org_type_score`,
  and blank — the "never scored" sentinel survives. D-21 proved null does **not** propagate from an
  *untaken* branch (the earlier "it does" verdict was the read-immediately race)
  [VERIFIED: 50-CONTEXT.md:214-221]. P3 above re-confirms this for a null *condition*, which D-21
  did not cover.
- **No cap:** an earned base ≥ 70 passes through `max` untouched → still Tier A.
- **Fallback if `max` misbehaves:** statement-form `if <coalesced base> < 60 then 60 else <coalesced base>` (base text repeated). Function-form `if(a,b,c)` is a confirmed 400 — statement form only.

### Formula-text canonicalization trap (will silently break the push if ignored)

HubSpot rewrites submitted formula text on create/update: `=` → `equals`, `"` → `'`, and inserts
line breaks after branches. Proven by the two artifacts diverging — yaml declares
`coalesce(lv_anti_icp_flag_num, 0) = 1 then "D"`, the live GET echoes
`coalesce(lv_anti_icp_flag_num, 0) equals 1 then 'D'` with `\n` between branches
[VERIFIED: config/hubspot_properties.yaml:426 vs config/hubspot_flows/lv_icp_tier_derived-property.after.json `calculationFormula`; documented at tests/test_tier_formula_pin.py:20-27].

`apply_fit_score_formula.py` verifies by **exact string equality** of the independent re-read
(`back == want`) [VERIFIED: scripts/apply_fit_score_formula.py:174-179]. Today's fit-score formula
is pure arithmetic so it round-trips unchanged; a conditional one will not. **Plan sequence must
be:** push once → GET the canonicalized text → write *that* into
`lv_icp_fit_score-property.after.json` → re-run the script and confirm "in sync — nothing to do".
Otherwise the script reports `verified by re-read: False` forever and every future drift-repair run
re-PATCHes.

---

## Property creation

Existing tool, no new code: declare in `config/hubspot_properties.yaml` under
`companies.properties`, then run `scripts/sync_hubspot_properties.py`, which derives "missing"
from a fresh GET, POSTs one property at a time, and compares options by value set
[VERIFIED: scripts/sync_hubspot_properties.py:20-33, 68-69, 129].

Two-key write gate: `DRY_RUN=false` **AND** `ALLOW_HUBSPOT_PROPERTY_WRITES=true`, plus the portal
guard `HUBSPOT_PORTAL_ID == 22617666` [VERIFIED: scripts/sync_hubspot_properties.py:11-14, 48, 58-60].

```yaml
  - name: lv_named_account_priority
    label: Named Account Priority
    type: enumeration
    fieldType: select
    groupName: companyinformation
    options:
      - {label: Core Racing, value: core_racing, displayOrder: 0}
      - {label: Non-Racing Best Fit, value: non_racing_best_fit, displayOrder: 1}
      - {label: Producer Secondary, value: producer_secondary, displayOrder: 2}
      - {label: Low Priority, value: low_priority, displayOrder: 3}
      - {label: Unknown, value: unknown, displayOrder: 4}
```

`groupName: companyinformation` matches every existing `lv_icp_*` and `*_score` property
[VERIFIED: config/hubspot_properties.yaml:411-446; both `*-property.after.json` archives].
Property names must be lowercase [ASSUMED — memory `hubspot-property-api-gotchas`, not re-verified
this session; the payload above is already lowercase so it is moot].

---

## Repo-side integration (what must change, and what must not)

| Surface | Change needed | Why |
|---|---|---|
| `config/hubspot_properties.yaml` | Declare the new property (+ mirror, if B) | `check_schema_drift.py::classify_property` returns **`missing_from_yaml`** for a live property with no yaml entry, and that is in `_FAILURE_STATUSES` [VERIFIED: scripts/check_schema_drift.py:167, 202-215] |
| `scripts/check_schema_drift.py:138` | **No edit.** `lv_named_account_priority` is already in `D04_COMPANY_PROPERTY_SCOPE` as a design-only name with no live-creation evidence; today it classifies `documented_gap`, and after creation + yaml declaration it becomes `in_sync` [VERIFIED: scripts/check_schema_drift.py:122-140, 224-225] | Scope list is already right; only the yaml side was missing |
| `tests/test_flow_rubric_conformance.py:459-476` | **Must be updated in the same commit.** `test_fit_score_formula_leaves_org_type_score_unguarded_as_the_sentinel` asserts the substring `coalesce(org_type_score` is **absent** from the archived formula. Formula A/B coalesce it inside the override branch → this test goes red [VERIFIED: tests/test_flow_rubric_conformance.py:459-476] | Restate the sentinel invariant as *branch-scoped*: unguarded in the else/default branch, coalesced only inside the `core_racing` branch. The other two fit-score tests (all five components named; the four nullables guarded) keep passing unchanged |
| `src/icp_scoring.py::compute_icp_score` | Add the floor; **guard the tier downgrade** (see trap below) | Oracle parity |
| `scripts/build_cloud_workflows.py` — `Decide Company Action` (`ENRICH_DECIDE_CO_CLOUD`) | Mirror the same rule in JS **in the same commit** (Phase 46 parity rule, restated in-code: "Must stay byte-identical to the JS port") [VERIFIED: src/icp_scoring.py:135-142]; add `lv_named_account_priority` to the company fetch list at line ~1794 or the node cannot read it | Two engines, one commit |
| n8n write path | **No change.** Approach C removed the canonical write of `lv_icp_fit_score` / `lv_icp_tier` / `lv_anti_icp_flag` in Phase 15 — `mergeCompanies.js`'s `DEFAULT_COMPANY_POLICY` has no `score_output` entries, so the node structurally cannot emit them [VERIFIED: scripts/build_cloud_workflows.py:2800-2803; src/merge_policy.py:346-351] | No fit-score write parity issue exists |
| `scripts/backfill_dry_run.py::predict_tier` (~line 741) | Only if a floored score can reach it — it takes `(score, anti_icp_flag)` and replicates the 4-branch ladder; it needs no edit if the floor is applied to `score` upstream in `compute_icp_score` [VERIFIED: scripts/backfill_dry_run.py:741-756] | Keep the floor in one place |
| `docs/OPERATOR-RESCORE.md` | Add the "how to add a 6th named account" procedure (and, under Formula B, the two-fields-in-sync warning) | Operator-facing surface |

### The oracle-tier trap (highest-value catch — Perth Racing)

`compute_icp_score` downgrades tier *after* the ladder when inputs are missing:

```python
confidence = 85
if org_type == "unknown" or produces_content is None:
    confidence = 55
    if not anti_icp_flag:
        tier = "Needs Review" if score >= 15 else "Unscored"
```
[VERIFIED: src/icp_scoring.py:166-174, quoted verbatim]

Perth Racing has **all inputs blank** → `org_type == "unknown"` → with a floored score of 60 the
oracle returns tier **"Needs Review"** while HubSpot's ladder returns **"B"**. That is a parity
defect on the exact record the task exists for. The floor must therefore suppress this downgrade
the same way a fired veto already does (`if not anti_icp_flag`) — i.e. `if not anti_icp_flag and
not named_account_floor_applied`. Note "Needs Review" is a Python-only sixth label the live ladder
has no branch for (PARITY-01, an accepted divergence) — which is exactly why
`predict_tier()` was written to bypass `.tier` [VERIFIED: scripts/backfill_dry_run.py:738-741].

### `check_tier_derived_parity.py` is inoperative — do not plan around it

CONTEXT names it as the D-07 gate to re-run. It compares `lv_icp_tier` against
`lv_icp_tier_derived` [VERIFIED: scripts/check_tier_derived_parity.py:100-104, 126-137], but
`lv_icp_tier` was **archived in Phase 50 Plan 05** (D-24) [VERIFIED: .planning/STATE.md:22-27].
A GET now returns nothing for it, so `classify_row` would mark every non-known-stuck record a
`defect`. **Verify this before relying on it**; if confirmed, substitute:
- `check_tier_derived_parity.py --census` (the D-19 before/after tier distribution), and
- an oracle-vs-live comparison via `compute_icp_score` + `predict_tier` over the scored population.

Whichever comparison ships, **`lv_named_account_priority` (and `_num` under Formula B) must be
added to its `FETCH_PROPS`** — `check_tier_derived_parity.py:100-104` does not list it, so the
oracle would score all five named accounts *without* the floor and report five defects against a
correct portal.

**Formula B only — mandatory drift control.** D-20's precedent when a numeric mirror was forced
required a check that the source value and its mirror always agree. Under Formula B the plan owes
the equivalent over the 5 records: assert `lv_named_account_priority == 'core_racing'` ⟺
`lv_named_account_priority_num == 1`, plus the operator-doc note that both fields must be set
together.

Also pre-register the **denominator change**: the scored population is selected by
`HAS_PROPERTY(lv_icp_fit_score)` [VERIFIED: scripts/check_tier_derived_parity.py:31-33], and Perth
goes blank → 60, so it *joins* the population. Expect N → N+1, not "N unchanged".

---

## Write discipline (three distinct gates, in order)

| Step | Gate | Source |
|---|---|---|
| 0. Enum-readability probe (disposable properties) | Same as step 1 — it *is* a property create. Operator approval + `DRY_RUN=false` + `ALLOW_HUBSPOT_PROPERTY_WRITES=true` + portal guard; teardown asserted (`_archive_and_confirm_gone`) | scripts/check_tier_null_propagation.py:181-192 |
| 1. Property create | `DRY_RUN=false` + `ALLOW_HUBSPOT_PROPERTY_WRITES=true` + portal `22617666` | scripts/sync_hubspot_properties.py:11-14, 48 |
| 2. Formula push | `ALLOW_FORMULA_WRITE=true` (exact `"true"`), archive-first, portal-guarded, verified by independent re-read | scripts/apply_fit_score_formula.py:141-179 |
| 3. Record PATCH (5 ids) | W1 window idiom: `DRY_RUN=false` + `ALLOW_SCORE_BACKFILL=true`, explicit id allowlist, chunked batch PATCH, no n8n arming anywhere in the path | scripts/rescore_population.py:17-35, 179-183 |
| 4. Verify | Poll (D-22), never a single immediate read | 50-CONTEXT.md:222-225 |

Target ids: `9605284724` (ATC), `9604614548` (MRC), `18756544344` (SSR), `9605284723` (BRC),
`9604794662` (Perth Racing).

`.env` is Read/Bash permission-blocked — every live invocation goes through the documented
`load_dotenv()` + `runpy` one-liner [VERIFIED: scripts/check_tier_derived_parity.py:35-40].

---

## Pitfalls

1. **Same-value PATCH is a no-op** — no property-change event. Setting the enum to a value it
   already holds fires nothing. Irrelevant on first write (all five are blank now), but it means a
   *correction* must go through a real value change [ASSUMED — memory
   `hubspot-same-value-patch-is-a-noop`; not re-verified this session].
2. **Backfill latency 70–130s** — poll, never read-immediately. This has already produced one wrong
   locked decision in this repo (D-04 → reversed by D-21).
3. **Property creation is irreversible** — soft archive only, name never reusable. Sequence the
   create as late as possible and only after the probe settles A vs B.
4. **Formula canonicalization** — see the trap above; the archive must hold the *server-echoed*
   text or `apply_fit_score_formula.py` never verifies.
5. **Formula rollback is clean**, property rollback is not: reverting = pushing the previous
   archived formula string. Capture the current formula verbatim before step 2.
6. **Blast radius of a bad formula is all ~712 companies**, not five. Add one control read on a
   never-enriched company (expect: still blank) and one on a Tier A record (expect: unchanged) to
   the verification set.
7. `lv_icp_tier_derived` is labelled "ICP Tier" in the portal (D-15 fallback) — the property whose
   internal name reads `_derived` is the one operators see as the tier. Don't reintroduce
   `lv_icp_tier` in any fetch list.

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | `string(<enum>)` makes an enumeration readable in `calculation_equation` on this portal | Headline finding | Formula A 400s at create → fall back to Formula B (mirror property). Probe P1 settles it for free. |
| A2 | A null enum in the `if` condition falls through to `else` rather than blanking the result | Formula drafts | All never-enriched companies' scores blank. Probe P3 settles it; `is_present` guard is the cheap repair. |
| A3 | `lv_icp_tier` is archived, so `check_tier_derived_parity.py`'s default mode is inoperative | Integration | Plan schedules a gate that returns all-defects. One GET confirms. |
| A4 | Same-value PATCH no-op still holds | Pitfalls | Only affects re-corrections, not this task's first write. |
| A5 | The five ids' current baselines (ATC/SSR/BRC 55 B, MRC 35 C, Perth blank) are still accurate | Predictions | Predictions drift; re-read all five immediately before the write and re-register. |

---

## Sources

**Primary (HIGH):** `41-FORMULA-SPIKE.md` (portal 400-body token list, verbatim);
`50-CONTEXT.md` D-20/D-21/D-22 amendments; `50-NULL-PROBE.json`; `TIER-DERIVATION-SPIKE-2026-08-13.md`;
`config/hubspot_flows/lv_icp_fit_score-property.after.json`, `…lv_icp_tier_derived-property.after.json`;
`scripts/{apply_fit_score_formula,sync_hubspot_properties,check_schema_drift,check_tier_derived_parity,check_tier_null_propagation,backfill_dry_run,rescore_population}.py`;
`src/icp_scoring.py`; `tests/{test_flow_rubric_conformance,test_tier_formula_pin}.py`;
`config/hubspot_properties.yaml`.

**Secondary (MEDIUM):** developers.hubspot.com/docs/guides/api/crm/properties (calculation
property types; `string()`/`bool()` wrapper requirement); knowledge.hubspot.com/properties/create-calculation-properties (`max` arity, operators). Note the KB page documents the **UI** equation
editor, which describes function-form `if(a,b,c)` — a confirmed 400 on the API. Where KB and the
portal's own 400 body disagree, the 400 body wins.
