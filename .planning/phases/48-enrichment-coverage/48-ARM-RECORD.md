# Phase 48 Plan 05 -- Arm Record (D-06's one declared armed write window)

Durable pre-arm record for plan 48-05 Task 1, appended to by Task 3. Single home for the
whole window rather than living only in a summary written after the fact.

## Write-time population re-derivation (Task 1, 2026-08-13)

Re-derived live via `derive_population()` / `reconcile_population()` -- the exact
`lv_icp_fit_score HAS_PROPERTY AND lv_org_type NOT_HAS_PROPERTY` filter -- **at write time,
not reused from plan 01's evidence or CONTEXT.md's 2026-08-12 snapshot.**

```json
{
  "expected": ["15008671672", "17317381378", "17317850381", "20538284384", "20943964946"],
  "derived":  ["15008671672", "17317381378", "17317850381", "20538284384", "20943964946"],
  "missing": [],
  "unexpected": [],
  "drift": false
}
```

**Matches plan 01's derivation and CONTEXT.md's 2026-08-12 snapshot exactly** -- same 5
ids, same order, zero drift. Every one of the 5 records' live `lv_org_type` reads `null`
(never_attempted) as of this read, confirmed in `48-BEFORE.json`.

## The five exact dry-run PATCH payloads (Task 1, `--dry-run`, no write, no arm)

Printed verbatim by `scripts/enrich_coverage_companies.py`'s dry-run CLI path
(`decide_org_type` + `build_coverage_patch`) against the current `ORG_TYPE_DECISIONS`
table (Racing NSW corrected to `governing_body_league` by plan 48-07):

```
PATCH[15008671672]: {
  "lv_org_type": "governing_body_league",
  "lv_org_type_verified_at": "<stamped at write time>"
}
PATCH[17317381378]: {
  "lv_org_type": "unknown",
  "lv_org_type_verified_at": "<stamped at write time>",
  "lv_enrichment_review_reason": "Web searches for 'Editix edetrix.com.au', 'Editix broadcast streaming live', and 'edetrix.com.au OR Editix Australia media' returned no results for a company matching this identity (matched=false, confidence=5, every data field null). Near-hits were EditiX (an XML editor), Editrix (an AI book-editing tool) and EditShare (media software) -- none matching the company name+domain. Identity is unresolvable, not merely unresearched."
}
PATCH[17317850381]: {
  "lv_org_type": "broadcaster",
  "lv_org_type_verified_at": "<stamped at write time>"
}
PATCH[20538284384]: {
  "lv_org_type": "individual_club_team",
  "lv_org_type_verified_at": "<stamped at write time>"
}
PATCH[20943964946]: {
  "lv_org_type": "content_producer",
  "lv_org_type_verified_at": "<stamped at write time>"
}
```

None of the five contains a `country_region` key or any of the four forbidden derived
scoring fields (`lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`)
-- confirmed by `test_marker_no_patch_contains_country_region_key` and the module-level
`assert FORBIDDEN_PROPS.isdisjoint(props)` inside `build_coverage_patch` itself.

## Pre-arm baseline: both surfaces confirmed disarmed (Task 1, independent read)

```
workflow_id: 950HPb7a1GgSAIyZ  ("LV Enrichment (Cloud template)")
active: True
ALLOW_HUBSPOT_RECORD_WRITES: "false"
ALLOW_HUBSPOT_CREATE:        "false"
TEST_RECORD_IDS:              ""
TEST_RECORD_DOMAINS:          ""
```

## Both operator arming commands, ready to paste

**Amendment (D-48-01, 2026-08-13, Phase 48 only):** these two commands, and the disarm
below, are executed by **Claude**, not the operator, for this phase only -- delegated in
`48-CONTEXT.md`'s D-48-01. They are still recorded here verbatim, in the per-shell form
the plan requires, so the actual invocation used at run time matches this record.

**Surface 1 -- the driver's own two-key gate** (guards the direct `lv_org_type` PATCH
leg), set in the SAME shell as the run command in Task 3:

```
DRY_RUN=false ALLOW_ENRICH_COVERAGE=true .venv/bin/python -c \
  "from dotenv import load_dotenv; \
   load_dotenv('/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.env'); \
   import sys; sys.path.insert(0, '.'); \
   import scripts.enrich_coverage_companies as m; \
   result = m.run_coverage_window(armed=True); \
   import json; print(json.dumps(result, indent=2, default=str))"
```

**Surface 2 -- the n8n-side allowlist** (guards `Decide Company Action` ->
`HubSpot Company Update`), armed BEFORE the command above, for exactly the five ids:

```
ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py \
  --ids 15008671672,17317381378,17317850381,20538284384,20943964946
```

**Disarm** (ungated by design, run unconditionally at the end of the window -- also
performed inside `run_coverage_window`'s own `finally`, as a second, redundant close):

```
.venv/bin/python scripts/june_run_arm.py --disarm
```

---

## Task 3 -- the armed window, run 2026-08-13 (D-06's one declared window, spent)

**Arm (call 1, Claude-executed under D-48-01).** `june_run_arm.arm('15008671672,17317381378,17317850381,20538284384,20943964946')`:

```json
{
  "outcome": "armed",
  "workflow_id": "950HPb7a1GgSAIyZ",
  "prior": {"ALLOW_HUBSPOT_RECORD_WRITES": "false", "ALLOW_HUBSPOT_CREATE": "false", "TEST_RECORD_IDS": "", "TEST_RECORD_DOMAINS": ""},
  "observed": {"ALLOW_HUBSPOT_RECORD_WRITES": "true", "TEST_RECORD_IDS": "15008671672,17317381378,17317850381,20538284384,20943964946", "TEST_RECORD_DOMAINS": ""}
}
```

**Window (call 2, its own shell: `DRY_RUN=false ALLOW_ENRICH_COVERAGE=true`).**
`run_coverage_window(armed=True)`'s first act, `assert_allowlist_exact`, read the
allowlist back independently (a fresh `n8n_read.get_workflow` GET, not this arm call's
own `observed` echo) and confirmed it non-empty, exactly the 5 ids,
`ALLOW_HUBSPOT_RECORD_WRITES == "true"`, `TEST_RECORD_DOMAINS` empty -- it did not raise,
so the window proceeded to its first PATCH.

**Per-record outcomes (in `COVERAGE_COMPANY_ID_ORDER`, exactly 1 PATCH + 1 recompute POST
each, 0 timeouts, 0 retries):**

| id | name | written `lv_org_type` | execution | nodes | dur (s) | `HubSpot Company Update` ran | node-level errors | before -> after score/tier | veto after |
|---|---|---|---|---|---|---|---|---|---|
| `15008671672` | Racing NSW | `governing_body_league` | `11866` | 111 | 3.092 | yes | none | 40/B -> 80/A | false |
| `17317381378` | Editix | `unknown` (+ D-03 reason) | `11867` | 111 | 1.528 | yes | none | 0/Unscored -> 0/Unscored | false |
| `17317850381` | Jam TV | `broadcaster` | `11868` | 111 | 2.246 | yes | none | 20/D -> 40/D | **true, "Non-ANZ geography" -- unchanged** |
| `20538284384` | Waikato Racing Club | `individual_club_team` | `11869` | 111 | 2.340 | yes | none | 30/C -> 45/B | false |
| `20943964946` | The Rumble | `content_producer` | `11870` | 111 | 1.254 | yes | none | 40/B -> 60/B | false |

**Node count 111** on every execution matches plan 48-04's post-bounce baseline (109 + the
2 D-04 gate nodes) -- the running instance did not drift between 48-04 and this window.
**21 nodes ran** on every execution (the 20-node disarmed recompute-lane shape plus
`HubSpot Company Update`, Trap 6's own armed figure) and every run ended at
`Respond to Webhook` with a real `Decide Company Action` output -- the healthy shape, not
the died-early shape (which stops at `Normalize + Score Company` with 0 items out). Durations
(1.25s-3.09s) sit slightly below Phase 47.5's own recompute-lane precedent (2.6s-3.425s) but
show the same ending shape (`Decide Company Action` ran and produced a real decision,
`HubSpot Company Update` ran) -- judged by that shape, per Trap 6's own guidance, not by the
raw number alone. `execution_errors.harvest_errors()` (Trap 1: judges `runData`, never
top-level `status`) found zero findings on every one of the 5 executions.

**Jam TV's veto, confirmed from the read-back, not merely from the write landing:**
`lv_anti_icp_flag: "true"`, `lv_anti_icp_reason: "Non-ANZ geography"` -- unchanged before
and after. The `broadcaster` write added org-type base points (score 20 -> 40) but the veto
is geographic (region `Other`) and org-type has no path to clear it, exactly as predicted.

**Editix**, confirmed `coverage_state() == "attempted_unresolved"` from the after-read (not
`never_attempted`) -- the D-03 marker's whole purpose.

**Waikato's `lv_is_gambling_operator` boolean** (never written by this driver, pre-existing
on the record) changed nothing in the score: `graduated_deductions` has been `{}` since
Phase 46 D-03. Its score moved 30 -> 45 (Tier C -> B) purely from `individual_club_team`'s
+15 org-type base points landing on a previously-blank org-type input.

**Racing NSW's override reached the live record correctly.** The n8n recompute lane reads
the record's own `lv_org_type` field (which this window PATCHed to
`governing_body_league`, plan 48-07's operator-reviewed override) -- never the
`ORG_TYPE_DECISIONS["override_of"]` table entry, which exists only in this repo's
decision record. `Decide Company Action`'s output and the read-back both show a score
(80) consistent with `governing_body_league` (+40 org-type, not `regulator`'s -20),
confirming the override -- not the model's original returned value -- is what the live
chain scored.

**No PATCH by this driver contained a derived-scoring-field key or a `country_region` key**
-- confirmed programmatically over every `patch_properties` dict this run actually sent:
`{lv_org_type, lv_org_type_verified_at}` for four records, plus
`lv_enrichment_review_reason` for Editix only. Every difference between `48-BEFORE.json`
and `48-AFTER.json`'s `lv_icp_fit_score` / `lv_icp_tier` / `lv_anti_icp_flag` /
`lv_anti_icp_reason` values came from `Decide Company Action` settling after this driver's
input-only write.

**Execution census.** `pre_window_last_execution_id` (captured before this window's first
POST) was `11865` -- plan 48-04's own proof execution, confirming continuity, no
unaccounted executions between plans. `post_window_execution_ids` (newest 10, captured
after disarm) shows exactly 5 new ids (`11866`-`11870`) ahead of `11865` -- 5 n8n
executions this window, matching D-06's declaration and `48-COST-ESTIMATE.md`'s
projection of 6 for the whole phase (1 already spent by 48-04's proof, 5 spent here).
0 provider credits, 0 Anthropic calls (Racing NSW's one paid call was plan 48-03's, not
this window's).

**Disarm (unconditional, inside `run_coverage_window`'s own `finally`).**

```json
{"outcome": "disarmed", "workflow_id": "950HPb7a1GgSAIyZ",
 "observed": {"ALLOW_HUBSPOT_RECORD_WRITES": "false", "ALLOW_HUBSPOT_CREATE": "false",
              "TEST_RECORD_IDS": "", "TEST_RECORD_DOMAINS": ""}}
```

**Independent re-read after disarm** -- a FRESH `n8n_read.get_workflow` GET, never a
re-read of the disarm call's own echoed/verified response (Trap 3):

```json
{"flags": {"ALLOW_HUBSPOT_RECORD_WRITES": "false", "ALLOW_HUBSPOT_CREATE": "false",
           "TEST_RECORD_IDS": "", "TEST_RECORD_DOMAINS": ""},
 "active": true}
```

Both reads agree: all four dispatch flags disarmed, workflow still active. **1 window
opened, 1 window closed** -- matching D-06's declaration exactly, no excess to disclose.

**Driver-side arm key.** `DRY_RUN=false ALLOW_ENRICH_COVERAGE=true` was set only in the
single shell invocation that ran `run_coverage_window` above -- never written to `.env`,
never exported into a longer-lived shell. That shell's exit is this surface's own closure;
nothing further to disarm on this side.

**A third, fully independent check** -- a wholly separate process invocation, run minutes
after the window closed and outside `run_coverage_window` entirely -- confirms the same
result again: `active: true`, all four dispatch flags read `"false"` / `""`. Three
independent reads (the function's own post-disarm re-read, this later separate check, and
this document) now all agree the window is closed.
