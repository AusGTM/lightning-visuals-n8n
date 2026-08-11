# 46-ENGINE-INVENTORY.md

Phase 46 Plan 01, Task 1 — the engine-count reconciliation this phase's downstream plans
(04, 05) branch on. Written from source, not from CONTEXT.md/RESEARCH.md's prior claims,
though the finding matches RESEARCH.md's own reconciliation.

## Verdict

**Two engines carry an org-type point table, not three.** CONTEXT.md D-11 and
REQUIREMENTS.md RUBRIC-03 both say "three." This document records what was actually found
by grepping the source, live at commit time, on 2026-08-11.

The n8n leg (`n8n/wf_enrichment_cloud.json`, built by `scripts/build_cloud_workflows.py`
from `n8n/code/mergeCompanies.js`) carries **no** org-type-keyed numeric table anywhere.

## Per-engine evidence

| # | Engine | File path | Verdict | Evidence |
|---|--------|-----------|---------|----------|
| 1 | Python oracle | `src/icp_scoring.py` + `config/icp_scoring.yaml` | **weight table** | `config/icp_scoring.yaml` `base_score.org_type` is a 9-key value-to-points dict (`governing_body_league: 40` ... `unknown: 0`); `src/icp_scoring.py:63` reads it via `cfg["base_score"]["org_type"].get(org_type, 0)`. |
| 2 | HubSpot Automation v4 flow `4626124224` ("Update Score Based on Org Type") | `config/hubspot_flows/4626124224-org-type-score.after.json` | **weight table** | `STATIC_BRANCH` action `1` keyed on `lv_org_type`, 9 `staticBranches` each routing to a `SINGLE_CONNECTION` action that writes `org_type_score` with a literal numeric `staticValue` (e.g. `governing_body_league` → action `2` → `"40"`; `individual_club_team` → action `5` → `"5"`). Confirmed live and authoritative per Phase 40 `PORTAL-FACTS.md`. |
| 3 | n8n JS "port" — `n8n/code/mergeCompanies.js` (source) | `n8n/code/mergeCompanies.js` | **no weight table** | Grep for `individual_club_team`, `governing_body_league`, `regulator`, `org_type_score`, `ORG_TYPE_SCORE`, `base_score`: 0 hits for all six terms. Lines 56-59 read: *"`lv_icp_fit_score` / `lv_icp_tier`: Approach C (Phase 15 criterion 4) — HubSpot owns these derived outputs. Removed from policy so either falls to the default non-promoting policy (`fill_blank_only`) if it ever appears in a candidate, never `score_output`."* `DEFAULT_COMPANY_POLICY` maps `lv_org_type` to `{class: "system_owned", min_confidence: 80, require_evidence_url_for: EVIDENCE_GATED_ORG_TYPES}` — a promotion-gate confidence threshold, not a score. |
| 4 | n8n JS "port" — built workflow | `n8n/wf_enrichment_cloud.json` | **no weight table** | Raw substring counts for the six terms are non-zero (`individual_club_team`: 78, `governing_body_league`: 62, `regulator`: 44 — all zero for `org_type_score`/`ORG_TYPE_SCORE`/`base_score`) because the file embeds `taxonomy.generated.js` (the `ORG_TYPES` enum array and `ORG_TYPE_SYNONYMS` string-to-string map) and a frozen `JUNE_CANDIDATES` fixture blob. A regex requiring each term be immediately (word-boundary) adjacent to a `:`/`=` and a number — the shape of an actual weight-table entry, not mere string presence — finds **zero** matches for any of the nine `base_score.org_type` keys or the three score-name terms. Every hit classified: enum membership (`taxonomy.generated.js`'s `ORG_TYPES` array — which org types exist) or synonym mapping (`ORG_TYPE_SYNONYMS`, e.g. `"club": "individual_club_team"` — a string-to-string normalizer, not a value-to-number table) or `JUNE_CANDIDATES` fixture data (frozen June-snapshot company records, out of scope per CLAUDE.md's "cross-check only, never source of truth" instruction). No `evidence_by_field`/`DEFAULT_COMPANY_POLICY`-adjacent hit maps an org-type value to a number. |
| 5 | n8n JS "port" — build script | `scripts/build_cloud_workflows.py` | **no weight table** | Same six-term grep: 0 raw hits for `individual_club_team`, `governing_body_league`, `regulator`, `org_type_score`, `ORG_TYPE_SCORE`, `base_score`. The same tightened word-boundary-adjacent-to-number regex (applied to all nine `base_score.org_type` keys, not just the three named above) also finds zero matches. |

**Search terms used (minimum set per plan):** `individual_club_team`, `governing_body_league`,
`regulator`, `org_type_score`, `ORG_TYPE_SCORE`, `base_score` — each grepped against all
three n8n-side artifacts (rows 3-5). Full coverage: every key in
`config/icp_scoring.yaml`'s `base_score.org_type` (`governing_body_league`,
`content_producer`, `broadcaster`, `individual_club_team`, `regulator`,
`gambling_operator`, `hardware_vendor`, `other`, `unknown`) was also checked with the same
word-boundary-adjacent-to-number regex against rows 4-5, confirming zero weight-table hits
across the complete key set, not just the six named terms.

## Classification detail — n8n `wf_enrichment_cloud.json`'s 78/62/44 raw hits

None of these are weight-table entries. Sample contexts confirming the classification:

```
'league\",\n  \"content_producer\",\n  \"broadcaster\",\n  \"individual_club_team\",\n  \"regulator\",\n  \"gambling_operator\",\n  \"hardwar'
```
— `taxonomy.generated.js`'s `ORG_TYPES` array (enum membership: which org types exist).

```
'ster\",\n  \"free to air\": \"broadcaster\",\n  \"club\": \"individual_club_team\",\n  \"team\": \"individual_club_team\",\n  \"racing club\"'
```
— `taxonomy.generated.js`'s `ORG_TYPE_SYNONYMS` (string-to-string normalizer input, e.g.
`"club"` → `"individual_club_team"` — no number anywhere in this mapping).

## What this means for downstream plans

1. **Plan 04's D-02 regulator change** collapses from "new engine logic" to a one-line
   `config/icp_scoring.yaml` edit plus the matching HubSpot flow branch edit — no n8n
   change is needed, because there is no n8n weight to change.
2. **Plan 04's D-01/D-03 weight edits** touch exactly two files:
   `config/icp_scoring.yaml` and the archived-then-live-PUT HubSpot flow JSON. The n8n
   build→deploy→bounce pipeline is not part of either plan's edit surface.
3. **RUBRIC-03's parity bar** ("org-type + deduction weights identical in Python oracle
   and HubSpot flow") is satisfiable by keeping exactly these two engines in sync — there
   is no third engine to keep in sync with.

## ROADMAP.md Phase 46 success criterion 4

**Criterion 4 (build → deploy → bounce + running-content read-back) is NOT TRIGGERED by
this phase.** Reason: no org-type (or gambling-deduction) weight reaches the live n8n
workflow at all (rows 3-5 above) — `scripts/build_cloud_workflows.py` has nothing to
regenerate differently as a result of any weight decided in this phase, so there is no
build to deploy and no running content to bounce or read back.

This is a conditional finding, not a permanent one. It would re-activate — i.e. a future
plan genuinely needs to run build → deploy → bounce → running-content read-back — the
moment any of the following changes:

- **Categorical promotion logic** — e.g. `mergeCompanies.js`'s `DEFAULT_COMPANY_POLICY`
  entries for `lv_org_type`/`lv_produces_content`/etc. (confidence thresholds, evidence
  gating), which do live in the n8n leg today.
- **Taxonomy membership** — `config/taxonomy.yaml`'s `org_types.*` list, which drives the
  generated `n8n/code/taxonomy.generated.js` (`ORG_TYPES`, `ORG_TYPE_SYNONYMS`,
  `EVIDENCE_GATED_ORG_TYPES`) via `scripts/gen_taxonomy_js.py`.
- **Evidence gating** — which org types require an evidence URL before promotion
  (`EVIDENCE_GATED_ORG_TYPES`, taxonomy-driven).
- **Merge policy** — any change to `mergeCompanies.js`'s deterministic gate itself (min
  confidence, field class, `_isBlank`/promotion rules).

None of D-01/D-02/D-03 (the three weights this phase decides) touch any of the four
triggers above — they are pure numeric edits to `base_score.org_type` /
`graduated_deductions.gambling_operator` values, which the n8n leg does not encode.

## Permanent guards created by this task

- `tests/test_n8n_org_type_absence.py` — static proof-not-inspection that neither
  `n8n/wf_enrichment_cloud.json` nor `scripts/build_cloud_workflows.py` carries a
  numeric-adjacent org-type key. Goes red if a future change reintroduces the split
  without updating this document.
- `tests/test_flow_rubric_conformance.py::test_org_type_flow_defaultbranch_scores_zero`
  — closes the blank-`lv_org_type` parity gap: flow `4626124224`'s `defaultBranch` (the
  path a blank or unrecognised `lv_org_type` takes — 18 live records) writes
  `org_type_score` `"0"`, matching the oracle's `.get(org_type, 0)` fallback.
