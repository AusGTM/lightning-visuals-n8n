---
task: "Metro peak-body named-account override — lv_named_account_score_floor=60 floors lv_icp_fit_score for ATC, MRC, SSR, BRC, Perth Racing"
quick_id: 260823-ono
date: 2026-08-23
revised: 2026-08-23
revision: "post-CP1 halt-b — enum unreadable in calculation_equation; retargeted to a single NUMBER property per the CONTEXT amendment (operator Option 1)"
status: planned
autonomous: false
write_surfaces:
  - "0. SPENT — disposable enum-readability probe properties (CP1, 5 disposables created+archived, none leaked; verdict halt-b)"
  - "0b. disposable number-floor formula probe: 1 number + 1 calculated property, 3 record values on the disposable only (CP1b, ALLOW_FLOOR_PROBE=true + DRY_RUN=false)"
  - "1. property create lv_named_account_score_floor (CP2, ALLOW_HUBSPOT_PROPERTY_WRITES=true + DRY_RUN=false)"
  - "2. formula push on lv_icp_fit_score (CP2, ALLOW_FORMULA_WRITE=true)"
  - "3. PATCH lv_named_account_score_floor=60 on 5 company ids (CP3, ALLOW_NAMED_ACCOUNT_WRITE=true + DRY_RUN=false)"
must_haves:
  truths:
    - "CP1b proves live, before any production formula push, that a NULL floor does not alter or blank scoring: (a) null floor on a scored record computes that record's existing live lv_icp_fit_score, (b) null floor on a never-enriched record stays BLANK, (c) floor=60 on all-blank inputs computes 60, (d) floor=60 on a base-80 record computes 80 (no cap), (e) floor=60 on a base-55 record computes 60"
    - "All 5 named ids carry lv_named_account_score_floor=60, confirmed by independent per-record re-read (never the PATCH response body)"
    - "All 5 poll to lv_icp_fit_score >= 60 and lv_icp_tier_derived == 'B' (D-22 poll: reads >=90s apart, stability only accepted after >=180s elapsed, never a single immediate read, never a two-agreeing-stale-reads stop)"
    - "Polled actuals match the predictions artifact written BEFORE the PATCH, record for record; any mismatch is logged as a defect, not narrated away"
    - "Blast-radius controls hold: the never-enriched control company's lv_icp_fit_score is still blank, and the Tier A control is unchanged in score and tier"
    - "check_tier_derived_parity.py reports defect=0; the only new divergences are the two pre-registered ones (MRC, Perth), registered before any live write; population N -> N+1 (Perth joins via HAS_PROPERTY(lv_icp_fit_score))"
    - "Oracle mirrors the rule: src/icp_scoring.py reads lv_named_account_score_floor, floors at max(base, floor) when floor > 0, applies no cap, and does not downgrade a floored record to 'Needs Review' on blank inputs"
    - "No enumeration property is created: lv_named_account_priority stays roadmap-only, its yaml declaration reverted, and CLAUDE.md §5.2 records that calculation formulas cannot read enumerations on this portal (D-20 reconfirmed live 2026-08-23)"
    - "Suites green: .venv/bin/python -m pytest, node --test tests/n8n/*.test.mjs, check_schema_drift.py exit 0 with lv_named_account_score_floor == in_sync (post-create)"
    - "Zero n8n changes, zero n8n executions, zero provider credits, zero Anthropic calls"
    - "Every disposable created by either probe is confirmed gone by an independent re-read; zero leaked properties across CP1 + CP1b"
  artifacts:
    - .planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-PREDICTIONS.json
    - .planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-PROBE-VERDICT.json
    - .planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-FLOOR-PROBE-VERDICT.json
    - scripts/probe_number_floor_in_formula.py
    - scripts/set_named_account_score_floor.py
    - config/hubspot_properties.yaml
    - config/hubspot_flows/lv_icp_fit_score-property.after.json
    - src/icp_scoring.py
    - scripts/check_schema_drift.py
    - tests/test_flow_rubric_conformance.py
    - tests/test_icp_named_account_floor.py
    - scripts/check_tier_derived_parity.py
    - CLAUDE.md
    - CHANGELOG.md
    - docs/OPERATOR-RESCORE.md
    - .planning/WINDOWS.md
  key_links:
    - "lv_named_account_score_floor (number) -> lv_icp_fit_score calculationFormula floor branch -> lv_icp_tier_derived ladder -> tier B"
    - "CP1b FLOOR-PROBE-VERDICT all_pass -> authorises CP2; anything less halts before the production formula push"
    - "server-echoed canonicalized formula -> config/hubspot_flows/lv_icp_fit_score-property.after.json -> apply_fit_score_formula.py prints 'in sync — nothing to do'"
    - "lv_named_account_score_floor -> tests/scoring_fixtures.py::FIT_SCORE_PROPS -> src/icp_scoring.py floor (the oracle's only live read path for the floor)"
    - "config/hubspot_properties.yaml declaration -> check_schema_drift.py D04_COMPANY_PROPERTY_SCOPE -> fabricated_entry (Task 1b..CP2 window) -> in_sync"
---

# Quick 260823-ono: Metro peak-body named-account override

Five AU metro racing peak bodies tier as high B via an operator-editable HubSpot **number**
property. A floor value of `60` on `lv_named_account_score_floor` floors `lv_icp_fit_score` at 60
in the calculated-property formula. Floor only, no cap. Blank = no override. Live this task.

Target ids: `9605284724` ATC, `9604614548` MRC, `18756544344` SSR, `9605284723` BRC,
`9604794662` Perth Racing.

## REVISION 2026-08-23 — enum is dead, number ships

CP1 ran armed and returned **`halt-b`**: `string(<enum>)` parses in a `calculation_equation` but
never reads the value. All 5 variants of `scripts/probe_enum_in_formula.py` created cleanly (HTTP
201) and computed `null` on ATC, which has `lv_org_type` set. The `is_present`-guarded variant is
the informative one: the never-enriched control computed `MISS` at 90.8s while ATC stayed `null` at
the same mark — so a NULL enum falls through to `else` correctly (P3 true) but a **SET** enum blanks
the whole formula (P2 false on all 5). Phase 50 D-20 stands; RESEARCH's false-negative theory is
refuted live. All 5 disposables confirmed gone, zero leaked. Evidence:
`260823-ono-PROBE-VERDICT.json`.

Operator decision (CONTEXT amendment, LOCKED): **Option 1 — single NUMBER property, no enum, no
mirror.** `lv_named_account_score_floor`; operator types `60` on a record; blank = no override. The
enumeration is NOT created (a second irreversible property with zero scoring effect). Its yaml
declaration is reverted; CLAUDE.md §5.2 keeps it as roadmap only.

Operator also mandated a **live proof before the production formula push** that a null floor does
not alter or blank scoring — that is CP1b below, and only an all-pass authorises CP2.

## The formula (FORMULA-F) — written once, referenced by name everywhere else

```
if coalesce(lv_named_account_score_floor, 0) > 0 then max(coalesce(org_type_score, 0) + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0), coalesce(lv_named_account_score_floor, 0)) else org_type_score + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0)
```

`>`, `max` (two-arity) and `coalesce` are all in this portal's own 400-body token list
(41-FORMULA-SPIKE.md). Statement-form `if/then/else` only — function-form `if(a,b,c)` is a confirmed
400.

**Deviation from the CONTEXT amendment's literal text, disclosed:** the amendment writes the
then-branch as `max(<branch-coalesced base>, lv_named_account_score_floor)`; FORMULA-F wraps that
second argument in `coalesce(..., 0)` too. Semantically identical (the branch is only taken when the
coalesced floor is > 0) and strictly safer — it removes the last unguarded null reference from the
formula, which is the exact failure class D-21 and CP1 both bit on.

**Fallback if `max` misbehaves under CP1b:** statement-form nesting, base text repeated —
`if coalesce(<floor>, 0) > 0 then (if <coalesced base> < <coalesced floor> then <coalesced floor>
else <coalesced base>) else <bare base>`. CP1b is where that is discovered, not CP2.

CP1b's probe carries FORMULA-F **verbatim, with one substitution only**: every occurrence of
`lv_named_account_score_floor` becomes the disposable number property's name. The `*_score`
component references stay real, so the probe computes real bases on real records.

## Scope disclosures (read before executing)

**No n8n change, no rebuild, no deploy.** This is the CONTEXT locked decision ("No recompute
POST, no n8n change"), and it is structurally correct, not just permitted: the `Decide Company
Action` node computes **no score and no tier** — Approach C removed the canonical
`lv_icp_fit_score`/`lv_icp_tier` write in Phase 15 (`scripts/build_cloud_workflows.py:2800-2803`;
`mergeCompanies.js` `DEFAULT_COMPANY_POLICY` has no `score_output` entries). The Phase 46 parity
rule binds the two **scoring** engines only where a shared predicate exists — restated verbatim in
WINDOWS.md id 19: "that rule binds the two SCORING engines (src/icp_scoring.py <-> Decide Company
Action)"; the veto predicate is the shared surface, and the floor is not a veto predicate. Adding
the floor to the n8n company fetch list would fetch a field nothing on that lane reads, against
v1.0's binding "zero n8n changes/executions" constraint. **This is a deliberate deviation from the
orchestrator's "JS scoring predicate + fetch list in build_cloud_workflows.py change" framing** —
the locked decision and the code both say there is nothing to mirror. Disclosed, not silent.
Unchanged by the enum→number retarget: the reasoning never depended on the property's type.

**A disposable-property record PATCH triggers no n8n execution.** The portal's webhook
subscriptions are `company.propertyChange.lv_enrichment_requested` only (CLAUDE.md §20.2). Writing
`zz_probe_floor_<uuid8>` or `lv_named_account_score_floor` on a company fires nothing.

**RESEARCH A3 is wrong — `check_tier_derived_parity.py` is NOT inoperative.** Task 1 re-confirmed
it live on the baseline run: `population=66 match=61 expected_mismatch=5 defect=0` (recorded in
`260823-ono-PREDICTIONS.json`). Keep default mode + `--census`.

**Do NOT use `run_scoring_parity.py` as the post-write gate** — WINDOWS.md id 18: its `tier_match`
is ANDed into the pass condition and reads the archived, frozen `lv_icp_tier`, so MRC and Perth
would false-fail it by construction.

**Schema-drift trajectory, restated for the number property.** Reverting the enum declaration
returns `lv_named_account_priority` to `documented_gap` (its pre-task state). Declaring
`lv_named_account_score_floor` makes **that** name the expected-red `fabricated_entry` (a
`_FAILURE_STATUSES` member) between Task 1b's commit and CP2's create, closing to `in_sync` after.
`check_schema_drift.py:138`'s `D04_COMPANY_PROPERTY_SCOPE` gets the name swapped in the same commit.

**`.env` is Read/Bash permission-blocked.** Every armed invocation is run by the operator at a
checkpoint using the documented `load_dotenv()` + `runpy` one-liner. The agent runs unarmed
dry-runs and read-only calls only.

**Env write-gate keys.** `ALLOW_FLOOR_PROBE` is new and required for CP1b's probe — a new write
surface gets its own key (repo idiom). The setter **keeps** `ALLOW_NAMED_ACCOUNT_WRITE`: the write
surface it gates is unchanged (a PATCH on the same 5 company ids); only the script's filename and
the payload's key changed. Minting a second key for the same surface would leave a dead key in
`.env`, which is Read-blocked and therefore not cheaply cleanable.

---

## Task 1 — DONE (commit `d0c1d6c`), superseded in part by Task 1b

Committed 2026-08-23: predictions artifact (live baselines for all 5 targets + 2 controls, N=66 /
N+1=67, verbatim rollback formula string), `scripts/probe_enum_in_formula.py`,
`scripts/set_named_account_priority.py`, the enum declaration in `config/hubspot_properties.yaml`,
the enum-keyed oracle floor in `src/icp_scoring.py`, `tests/test_icp_named_account_floor.py`, the
branch-scoped sentinel restatement in `tests/test_flow_rubric_conformance.py`, `FIT_SCORE_PROPS`,
the MRC/Perth pre-registrations in `scripts/check_tier_derived_parity.py`, and WINDOWS ids 20-22.

**Still valid, do not redo:** the predictions artifact's baselines, controls, N/N+1, and rollback
string (all live-read, none affected by the mechanism change); the branch-scoped sentinel test; the
MRC/Perth parity pre-registrations (the divergence class is identical — an archived, frozen
`lv_icp_tier` against a correctly-floored `lv_icp_tier_derived`; only the *mechanism* named in the
prose changed); `probe_enum_in_formula.py` and `260823-ono-PROBE-VERDICT.json`, which are the
evidence for `halt-b` and are left **untouched** — deleting the tool would orphan the verdict.

**Superseded:** everything keyed to the enum. Task 1b retargets it.

---

## Task 1b — Retarget enum → number (offline + read-only)

**files:** `config/hubspot_properties.yaml`, `src/icp_scoring.py`,
`tests/test_icp_named_account_floor.py`, `tests/scoring_fixtures.py`,
`scripts/check_schema_drift.py`, `scripts/set_named_account_score_floor.py` (git mv from
`set_named_account_priority.py`), `scripts/probe_number_floor_in_formula.py` (new),
`scripts/check_tier_derived_parity.py`, `tests/test_tier_derived_tools.py`,
`tests/test_hubspot_properties_config.py`, `CLAUDE.md`, `.planning/WINDOWS.md`,
`.planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-PREDICTIONS.json`

**action:**

1. **`config/hubspot_properties.yaml`** — delete the `lv_named_account_priority` enumeration entry
   added by Task 1 (revert to its pre-task absence), and declare in its place:
   `name: lv_named_account_score_floor`, `label: Named Account Score Floor`, `type: number`,
   `fieldType: number`, `groupName: companyinformation`, `options: []` — the same shape as the five
   `*_score` entries directly above it. Company property count stays 34.
2. **`src/icp_scoring.py`** — retarget the floor block from the enum to the number. Read
   `floor_raw = get_signal(record, candidate_patch, "lv_named_account_score_floor", None)` and
   parse it **defensively**: HubSpot returns numbers as strings, so `None`, `""` and any
   non-numeric value mean "no floor" (never raise), while `"60"` and `60` both mean `60.0`. Apply
   when `floor > 0`: `score = max(score, int(floor))`, append the breakdown entry naming the signal,
   its parsed value and the points delta (append even when the delta is 0 — the override must be
   visible whether or not it bit). Keep both pinned semantics, restated for the new mechanism in
   the code comment: (a) **no cap** — an earned base >= 70 passes through untouched; (b) the
   "missing inputs" downgrade block is guarded on **whether a floor is set** (`floor > 0`), not on
   whether the floor raised the score — the live ladder has no "Needs Review" branch at all
   (PARITY-01), so guarding on the override maximises parity, and Perth (all inputs blank) is the
   exact record this task exists for. A fired veto still forces tier D, floored score or not. Update
   the comment's mechanism prose and cite the CONTEXT amendment, not the superseded enum decision.
3. **`tests/test_icp_named_account_floor.py`** — retarget every case to the number, and add the
   three cases the string-typed input introduces:
   - 35 -> 60/"B"; base 75 + floor 60 stays 75/"A" (no cap); all-blank inputs + floor 60 = 60/"B"
     **not** "Needs Review"; veto fired + floor 60 = floored score with tier "D"; a record without
     the floor is byte-identical to today's result; breakdown carries the override entry.
   - floor `""` (blank string, the shape HubSpot returns for an unset number) -> byte-identical to
     no-floor.
   - floor `"60"` (string) -> parses and floors exactly as the int `60`.
   - floor `0` and floor `"0"` -> no effect, no floor applied (0 is not an override).
4. **`tests/scoring_fixtures.py`** — swap `lv_named_account_priority` for
   `lv_named_account_score_floor` in `FIT_SCORE_PROPS` (this is the oracle's only live read path for
   the floor; without it `expected_for()` scores the five named accounts without it). Requesting an
   unknown property name in a HubSpot GET is a documented no-op, so this is safe before the create.
5. **`scripts/check_schema_drift.py:138`** — swap the name in `D04_COMPANY_PROPERTY_SCOPE`
   (`lv_named_account_priority` -> `lv_named_account_score_floor`). Any test pinning that scope
   set's membership must move with it in the same commit; the full pytest run catches it.
6. **`git mv scripts/set_named_account_priority.py scripts/set_named_account_score_floor.py`**, then
   retarget: `FLOOR_PROP = "lv_named_account_score_floor"`, `FLOOR_VALUE = 60`, payload
   `{"lv_named_account_score_floor": 60}`, and the payload-scope assert becomes "every PATCH body's
   key set is exactly `{"lv_named_account_score_floor"}`". `NAMED_ACCOUNTS` (the five ids, the
   operator's "add a 6th" surface) is unchanged. Keep all three modes, both env keys
   (`DRY_RUN=false` + `ALLOW_NAMED_ACCOUNT_WRITE=true`), the portal guard, the independent
   per-record re-read after each PATCH, and the `--plan` drift refusal covering both the 5 targets
   and the 2 controls. `--verify`'s poll adopts Task 1b step 7's corrected poll shape.
7. **`scripts/probe_number_floor_in_formula.py`** — new, the CP1b probe. Same discipline as CP1's:
   disposable names, teardown in `finally`, teardown confirmed by independent re-read, D-22 polls,
   verdict JSON, `--plan` default that makes zero HTTP calls, portal guard `22617666`, two-key gate
   `DRY_RUN=false` **and** `ALLOW_FLOOR_PROBE=true`. Specifics:
   - **Reuse** `scripts/check_tier_null_propagation.py`'s `_create_numeric_property`,
     `_get_property_live`, `_archive_and_confirm_gone`. Do **not** reuse its
     `_create_calculated_property` and do **not** mutate it — it hardcodes `type: "string"` and the
     tier probe depends on that. Write a local `_create_calculated_number_property` mirroring it
     with `type: "number"`, matching the live `lv_icp_fit_score` shape exactly.
   - Create one disposable number property `zz_probe_floor_<uuid8>` and one disposable calculated
     property `zz_probe_fitscore_<uuid8>` carrying FORMULA-F with `lv_named_account_score_floor`
     substituted by the disposable number's name (both occurrences; the `*_score` component
     references stay real). If the create 400s, print the body verbatim — the token list is
     positional — and fall back to the nested-`if` form named above, recording which one shipped.
   - **Poll shape — CORRECTED, do not copy `poll_d22` from `probe_enum_in_formula.py`.** That
     function returns as soon as two consecutive reads agree, which is wrong when polling for a
     *transition*: backfill is 70-130s, so reads at 0s and 90s can both return the stale
     pre-write value, agree, and stop — reporting the old value as "stable" and false-failing
     (c)/(d)/(e). Replacement rule: poll until `value == expected` **or** the 300s ceiling; a
     stability stop is only accepted once elapsed >= 180s. Reads are >= 90s apart. Poll all target
     ids in one loop per tick (one read cycle across the ids, then one wait) rather than serially —
     serial 90s waits per record is what made CP1 a 20-minute run. Record every read with its
     elapsed time in the verdict either way.
   - **No-change checks never exit early on a match.** (b) expects blank and *starts* blank; (d)
     expects 80 and already reads 80 from the else-branch before the floor is written — so a
     poll-to-expected rule would exit them at t=0, which is the single-immediate-read D-22 forbids
     and proves nothing about whether the portal has recomputed yet. (b) and (d) pass only once
     their phase's **transition** checks have landed — (a) reaching the record's live base for
     phase 1, (c) and (e) reaching 60 for phase 2 — or at the ceiling. The batched per-tick loop
     makes this free: the sibling transitions are the timestamp evidence that the portal recomputed.
     Any non-blank read on (b) at any tick is an immediate FAIL, not something to poll past.
   - **Checks, run in two phases. Every comparison is self-calibrating against the record's own
     live production `lv_icp_fit_score`, compared as floats (HubSpot returns `"55"`, not `55`) —
     never against a hard-coded 55/80, which would false-fail if a base has drifted since Task 1.**

     Phase 1, no floor written anywhere:
     | id | record | floor | expected disposable calc |
     |----|--------|-------|--------------------------|
     | (a) | ATC `9605284724` | unset | `== float(live lv_icp_fit_score)`, and not blank |
     | (b) | never-enriched `9604773165` | unset, **never written** | blank (`None` or `""`), production also blank |

     Phase 2, floor 60 written on exactly three records:
     | id | record | floor | expected disposable calc |
     |----|--------|-------|--------------------------|
     | (c) | Perth `9604794662` | 60 | `60`, with production still blank |
     | (d) | Tier A control `9605284722` | 60 | `== float(live lv_icp_fit_score)` (80) and `> 60` — proves no cap |
     | (e) | ATC `9605284724` | 60 | `60`, and `!= float(live lv_icp_fit_score)` (55) — proves the floor bit |

   - **The never-enriched control `9604773165` is READ-ONLY. It is never written a floor value** —
     writing one destroys check (b), which is the operator's headline question. Exactly three
     records are written: ATC, Perth, Tier A control.
   - Every record write asserts its payload key set is exactly `{<disposable number name>}`. No
     production property is ever in a PATCH body in this script.
   - `finally:` clear the disposable number's value on the three written ids (PATCH `""`), then
     archive the **calculated** property first and the **number** property second — HubSpot refuses
     to archive a property a live calculation still depends on (observed live 2026-08-13,
     `check_tier_null_propagation.py::_teardown`) — then confirm both gone by independent GET.
     Record any leak by name.
   - Write `260823-ono-FLOOR-PROBE-VERDICT.json`: per-check `expected`/`observed`/`pass`, all reads
     with elapsed, the formula text actually shipped, the disposable names, teardown status,
     `leaked_properties`, and a single top-level `all_pass` boolean. Exit 0 only when `all_pass` and
     nothing leaked. Reuse the `_assert_no_secrets` serializer guard verbatim.
8. **Text-truth sweep — every place the enum is named as the live mechanism.** `.planning/WINDOWS.md`
   ids 20 and 21 (descriptions **and** waive `reason` strings) and id 22 (description, including its
   `PAYLOAD_INPUT_PROPS` sentence) name `lv_named_account_priority=core_racing`; direct-edit them to
   `lv_named_account_score_floor=60`. Same for the comments in `scripts/check_tier_derived_parity.py`
   (~lines 37, 93), `tests/test_tier_derived_tools.py` (~lines 166, 275) and
   `tests/test_hubspot_properties_config.py:154`. The ledger ids, the pinned id sets and the
   property count all stay as they are — only the mechanism prose moves.

   **`CLAUDE.md` §5.2 — record the finding HERE, not at Task 3.** The evidence exists now, and if
   the plan halts at CP1b the repo would otherwise carry an unexplained enum revert with nothing
   saying why. `lv_named_account_priority` stays in the "documented but never created" list,
   annotated: *"calculation formulas cannot read enumerations on this portal — D-20 reconfirmed
   live 2026-08-23 (quick 260823-ono CP1: `string(<enum>)` parses but computes null once the enum
   has a value; 5 variants, evidence in 260823-ono-PROBE-VERDICT.json). Any operator-facing
   vocabulary that must drive a formula has to be a number."* This is the only CLAUDE.md edit in
   Task 1b — §4.0's as-built line and §10's rubric entry are Task 3's, because they assert live
   state that does not exist until CP2/CP3.
9. **`260823-ono-PREDICTIONS.json`** — rename the per-target baseline key
   `lv_named_account_priority` to `lv_named_account_score_floor` (value stays `null`) and add a
   one-line `retarget_note` recording that CP1 returned `halt-b` and the input field changed from
   an enumeration to a number. **Predicted scores and tiers are unchanged** — ATC/SSR/BRC 55->60 B,
   MRC 35->60 B, Perth blank->60 B — as are the baselines, controls, N/N+1 and the rollback string.
10. **`config/hubspot_flows/lv_icp_fit_score-property.after.json` is NOT touched here.** Task 2
    settles the archive text after CP1b proves the formula live. Committing an unproven formula into
    the source-of-truth archive is exactly the move CP1b exists to prevent.
11. Commit. One commit, all of the above together — the oracle change, the yaml swap and the drift
    scope must not be separable.

**verify:**
- `.venv/bin/python -m pytest tests/test_icp_named_account_floor.py tests/test_flow_rubric_conformance.py tests/test_hubspot_properties_config.py tests/test_tier_derived_tools.py tests/test_check_schema_drift.py tests/test_backfill_dry_run.py -q` green, then the full `.venv/bin/python -m pytest` green.
- `node --test tests/n8n/*.test.mjs` green (glob form — the directory form is broken on node 24).
- `.venv/bin/python scripts/probe_number_floor_in_formula.py` (unarmed) prints FORMULA-F with the
  disposable substitution and the (a)-(e) check table, and makes zero HTTP calls;
  `.venv/bin/python scripts/set_named_account_score_floor.py --plan` prints exactly 5 single-key
  payloads whose only key is `lv_named_account_score_floor`, and zero writes.
- `check_schema_drift.py` (read-only) reports **exactly one** failure status and it is
  `fabricated_entry` on `lv_named_account_score_floor` — any second failure is a defect, and
  `lv_named_account_priority` must NOT appear among them (it is back to `documented_gap`). This red
  is expected and closes at CP2.
- `rg -n "lv_named_account_priority" --glob '!*PROBE-VERDICT.json' --glob '!*CONTEXT.md' --glob '!*RESEARCH.md' --glob '!CLAUDE.md'` returns only intentional roadmap/history references — no
  remaining live-mechanism claim.
- `git status` clean after the commit; `git show --stat HEAD` contains no `n8n/` file and shows the
  rename as a rename.

**done:** The rule, tooling, tests and ledger all describe the number-floor design. Predictions
remain immutable in their numbers. No production HubSpot write has occurred.

---

## Checkpoint 1 — DONE, verdict `halt-b`

Ran armed 2026-08-23. All 5 enum-readability variants parsed (201) and none read the enum's value.
`is_present`-guarded variant: never-enriched control -> `MISS` at 90.8s, ATC (enum SET) -> `null` at
90.9s. P1 true, P2 false, P3 true. 5 disposables created, 5 confirmed gone, 0 leaked. Evidence:
`260823-ono-PROBE-VERDICT.json`. Operator chose Option 1 (single number property) — see the CONTEXT
amendment. **No numeric 0/1 mirror was built** — the operator rejected the mirror design outright,
so there is no two-fields-in-sync drift check owed.

---

## Checkpoint 1b — `checkpoint:human-verify`, gate: blocking

**what will be built:** Write surface 0b. One disposable number property, one disposable calculated
property carrying FORMULA-F, and a floor value of 60 written on **three** production records —
**only ever on the disposable number property**, never on a production property. The never-enriched
control is read-only. Everything is cleared and archived by the probe's own `finally`. No production
property is created and no production property's value changes.

**why this gate exists:** the operator's mandated question — *if the floor is null, does it still
contribute to scoring?* CP1 proved this portal will happily accept a formula that parses and then
silently blanks. FORMULA-F governs all ~712 companies the moment it is pushed; a blanking bug found
at CP2 is found on the whole population. Found here, it costs two disposables.

**operator command:**
```
ALLOW_FLOOR_PROBE=true DRY_RUN=false .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy; \
   runpy.run_path('scripts/probe_number_floor_in_formula.py', run_name='__main__')"
```
Expect **~10-15 minutes**: two poll phases, reads >=90s apart, and a stability stop that is not
accepted before 180s elapsed. Paste the full output including the verdict JSON path.

**pass condition:** `all_pass: true` — every one of (a), (b), (c), (d), (e) passed and
`leaked_properties` is empty.

**options:**
- `proceed` — all five checks pass. FORMULA-F (or the recorded nested-`if` fallback, if `max`
  400'd) is authorised for CP2.
- `halt-blank` — (a) or (b) failed: a null floor alters or blanks scoring. **The plan HALTS.** The
  formula is wrong in a way that would damage the population; report the observed values and
  re-plan the formula shape. Do not push anything.
- `halt-floor` — (c), (d) or (e) failed: the floor does not compute as specified (no floor, or a
  cap, or the wrong value). **The plan HALTS**; same treatment.
- `halt-leak` — any disposable was not confirmed gone. Stop and clean up manually before anything
  else; a leaked disposable calculated property referencing a leaked disposable number is the one
  state that needs the archive-dependent-first order run by hand.
- `abort` — stop; the probe's `finally` has already cleared values and archived both disposables.

**resume-signal:** Reply `proceed`, `halt-blank`, `halt-floor`, `halt-leak`, or `abort`.

---

## Task 2 — Settle the formula text (between CP1b and CP2)

**files:** `config/hubspot_flows/lv_icp_fit_score-property.after.json`

**action:** Write the formula **exactly as CP1b proved it** into the archive's
`calculationFormula` — FORMULA-F verbatim with the real `lv_named_account_score_floor` name
restored in place of the disposable, or the nested-`if` fallback if that is what the verdict records
as shipped. Take the text from `260823-ono-FLOOR-PROBE-VERDICT.json`'s recorded formula field, not
from this plan document, and perform only the property-name substitution. The archive is the source
of truth; the push script only ships it. Re-confirm the verbatim pre-change live formula is still
recorded in the predictions JSON as the rollback string. Then dry-run both CP2 commands unarmed:
`scripts/sync_hubspot_properties.py` (expect: exactly one missing property named, and it is
`lv_named_account_score_floor`) and `scripts/apply_fit_score_formula.py` (expect: `archived:`/`live:`
lines diverging plus the `DRY RUN (set ALLOW_FORMULA_WRITE=true to apply)` PATCH payload). Commit.

**verify:** `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` green against the
new archive text (the branch-scoped sentinel test passes on the *submitted* form); the two unarmed
dry-runs print exactly the two expected shapes and make zero writes; `git show --stat HEAD` shows
only the archive JSON.

**done:** Archive holds the CP1b-proven formula; both CP2 commands are proven to be one-property and
one-PATCH respectively before they are armed.

---

## Checkpoint 2 — `checkpoint:human-verify`, gate: blocking

**precondition:** CP1b returned `proceed` (`all_pass: true`). Do not run these commands otherwise.

**what will be built:** Write surfaces 1 and 2, in this order — the create MUST precede the push,
because the formula references a property that does not exist yet. Two commands, two distinct env
keys, one gate.

**how to run:**

1. **Property create** (surface 1) — a `number` property, `lv_named_account_score_floor`:
```
DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy; \
   runpy.run_path('scripts/sync_hubspot_properties.py', run_name='__main__')"
```
   Expect: exactly ONE property created (`lv_named_account_score_floor`), 200/201. If it reports
   more than one missing property — in particular if it names `lv_named_account_priority` — STOP and
   report: the yaml revert did not land.

2. **Formula push** (surface 2):
```
ALLOW_FORMULA_WRITE=true .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy; \
   runpy.run_path('scripts/apply_fit_score_formula.py', run_name='__main__')"
```

**EXPECTED, NOT A FAILURE — read this before reacting to the output.** A *successful* push will
print `PATCH 200` followed by `verified by re-read: False` and a `!! live is now: ...` line, and
the script will exit 1. HubSpot canonicalizes conditional formula text on write (`=` -> `equals`,
`"` -> `'`, newlines inserted between branches) and the script verifies by exact string equality.
This is the known canonicalization trap. **Paste the whole `!! live is now:` line verbatim** —
Task 3 folds that echoed text into the archive and re-runs the script to
`in sync — nothing to do`. A `PATCH 400` (not 200) IS a failure: paste the body, it lists the
valid tokens at the failing parse position.

**blast radius:** the formula governs all ~712 companies. At this point no record carries a floor,
so every record takes the else-branch and nothing should change — which is precisely what CP1b's
check (a) and (b) proved on live records before this push. **CP3's unarmed preflight is the second
check, and it proves it again before any record is touched** — it refuses to arm if either control
record has moved. Do not skip it.

**rollback:** push the verbatim pre-change formula string recorded in `260823-ono-PREDICTIONS.json`.
Formula rollback is clean; property creation is not (soft archive only).

**resume-signal:** Paste both command outputs, then reply `pushed` or describe the failure.

---

## Checkpoint 3 — `checkpoint:human-verify`, gate: blocking

**what will be built:** Write surface 3 — PATCH `lv_named_account_score_floor=60` on exactly the 5
named ids. Zero n8n executions, zero provider credits, zero Anthropic calls.

**preflight (unarmed, run this first):**
```
.venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy; \
   runpy.run_path('scripts/set_named_account_score_floor.py', run_name='__main__')"
```
Expect: 5 single-key payloads (`{"lv_named_account_score_floor": 60}`) plus a drift check against
`260823-ono-PREDICTIONS.json` covering both the 5 target ids and the two control records. It
**refuses** if any of them has moved since Task 1 — including a never-enriched control that is no
longer blank or a Tier A control whose score or tier changed, which would mean the formula push
damaged the population. **Wait at least 3 minutes after the CP2 push before running this**: the
formula's effect on any record backfills ~70-130s later, so a preflight run immediately after the
push reads pre-formula values and proves nothing. Do not arm if the preflight refuses.

**armed run:**
```
DRY_RUN=false ALLOW_NAMED_ACCOUNT_WRITE=true .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
   sys.argv = ['set_named_account_score_floor.py', '--execute']; \
   runpy.run_path('scripts/set_named_account_score_floor.py', run_name='__main__')"
```
Expect 5 PATCH 200s, each confirmed by an independent per-record re-read of the floor value. Scores
and tiers will NOT be correct immediately — they backfill ~70-130s later and Task 3 polls for them.

**resume-signal:** Paste both outputs, then reply `patched` or describe the failure.

---

## Task 3 — Post-write verification, archive re-sync, docs, ledger

**files:** `config/hubspot_flows/lv_icp_fit_score-property.after.json`, `CLAUDE.md`,
`CHANGELOG.md`, `docs/OPERATOR-RESCORE.md`, `.planning/WINDOWS.md`,
`.planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-PREDICTIONS.json`

**action:**

1. **Archive re-sync from the server echo (do this first, it closes CP2's expected red).** GET
   `crm/v3/properties/companies/lv_icp_fit_score`, take `calculationFormula` verbatim, write it
   into the archive, and re-run `apply_fit_score_formula.py` **unarmed** — it must print
   `in sync — nothing to do`. If it does not, the archive text is still wrong and every future
   drift-repair run would re-PATCH. Re-run `tests/test_flow_rubric_conformance.py` against the
   echoed text (this is the second half of the newline/quote-tolerance requirement).
2. **Blast-radius controls, before trusting anything else:** read the never-enriched control
   (expect `lv_icp_fit_score` still blank — the else-branch sentinel survives, as CP1b check (b)
   predicted) and the Tier A control (expect score and `lv_icp_tier_derived` unchanged). A blanked
   control is a stop-and-roll-back signal, not a rounding difference.
3. **Poll and compare:**
```
.venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
   sys.argv = ['set_named_account_score_floor.py', '--verify']; \
   runpy.run_path('scripts/set_named_account_score_floor.py', run_name='__main__')"
```
   Reads >=90s apart, stability accepted only after >=180s elapsed, 300s ceiling. Diff against the
   predictions JSON and append the actuals to it. **Any mismatch is a defect** — record it in
   WINDOWS.md and report it; do not narrate it as expected.
4. **Parity + census:** run `check_tier_derived_parity.py` (default) and `--census`. Require
   `defect=0`; the pre-registered MRC and Perth rows must classify as `expected_mismatch` (they
   were registered in Task 1, before the write — not widened after seeing the result); population
   must be N+1 with Perth newly present. Do **not** substitute `run_scoring_parity.py`
   (WINDOWS.md id 18).
5. **Schema drift:** re-run `check_schema_drift.py`; `lv_named_account_score_floor` must now be
   `in_sync` and the overall exit code 0.
6. **Docs.**
   - `CLAUDE.md` §4.0: add a dated as-built line for `lv_named_account_score_floor` — it now exists,
     it is a number, `60` on a record floors that record's `lv_icp_fit_score` at 60.
   - `CLAUDE.md` §5.2: already annotated in Task 1b — verify the note is still present and
     accurate, do not duplicate it.
   - `CLAUDE.md` §10: add the floor rule to the rubric section — floor 60 on
     `lv_named_account_score_floor`, no cap, veto still wins, the floor lives in the HubSpot
     calculated property and is mirrored in `src/icp_scoring.py` only — **not** in n8n, with the
     Approach C reason.
   - `CHANGELOG.md` `[Unreleased] / Added`: one entry in the repo's existing prose style, naming the
     five accounts, the number property, the floor, **both** probe results (CP1 halt-b and CP1b
     all-pass), and the disclosed n8n non-change.
   - `docs/OPERATOR-RESCORE.md`: an "add a 6th named account" procedure pointing at
     `scripts/set_named_account_score_floor.py` (edit `NAMED_ACCOUNTS`, run `--plan`, arm
     `--execute`, then `--verify`), plus the "set the number to 60 in HubSpot, blank it to remove
     the override" manual path, the same-value-PATCH-is-a-no-op warning for corrections, and the
     70-130s backfill wait.
7. Commit. Report the final actuals table (id, name, before score/tier, after score/tier) in the
   response.

**verify:**
- `apply_fit_score_formula.py` unarmed prints `in sync — nothing to do`.
- `--verify` exits 0 with all 5 at score >= 60 and `lv_icp_tier_derived == "B"`, matching predictions.
- Never-enriched control still blank; Tier A control unchanged.
- `check_tier_derived_parity.py`: `defect=0`, MRC + Perth `expected_mismatch`, population N+1.
- `check_schema_drift.py` exit 0, `lv_named_account_score_floor` `in_sync`.
- `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` both green.
- `git log --stat` for this task shows zero `n8n/` files touched.

**done:** Five records live at Tier B with score >= 60, proven by polled reads against
pre-registered predictions; archive matches the server echo; parity, drift and both suites green;
docs and ledger updated.

---

## Output

SUMMARY at
`.planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-SUMMARY.md`
with `status: complete` frontmatter. Must surface verbatim: **CP1's `halt-b` verdict and what it
proved** (enums are unreadable in a `calculation_equation` on this portal — the reusable finding),
the CP1b (a)-(e) results table, the server-echoed canonical formula, the before/after actuals table,
and the exact tally of live writes spent, by surface (expect **5 surfaces**: surface 0 = 5 CP1
probe properties created + archived; surface 0b = 2 CP1b disposables created + archived and 3
disposable-only record values written + cleared; surface 1 = 1 property created; surface 2 = 1
formula PATCH; surface 3 = 5 record PATCHes), with the count of properties **leaked** stated
explicitly as 0. Plus the three WINDOWS.md ledger ids recorded (20, 21, 22).
