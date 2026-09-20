---
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
reviewed: 2026-09-20T00:00:00Z
depth: standard
files_reviewed: 68
files_reviewed_list:
  - CLAUDE.md
  - config/hubspot_flows/4626722240-geography-score.after.json
  - config/hubspot_flows/4626722240-geography-score.post75.json
  - config/hubspot_flows/4626722240-geography-score.pre75.json
  - config/hubspot_migration/baseline/portal-schema-companies-phase75.json
  - config/hubspot_migration/baseline/portal-schema-contacts-phase75.json
  - config/hubspot_migration/undo-manifest-7ee513f4-644d-4788-8b1f-fcda558fb767.json
  - config/hubspot_properties.yaml
  - config/icp_scoring.yaml
  - docs/OPERATOR-RESCORE.md
  - n8n/code/hubspotEnums.generated.js
  - n8n/code/icpScoring.generated.js
  - n8n/code/normalizeProviders.js
  - n8n/wf_contact_ingest_cloud.json
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_enrichment_local.json
  - n8n/wf_review_decision_cloud.json
  - n8n/wf_scheduled_maintenance_cloud.json
  - scripts/bounce_n8n_workflows.py
  - scripts/build_cloud_workflows.py
  - scripts/check_schema_drift.py
  - scripts/deploy_n8n_workflows.py
  - scripts/gen_geography_flow.py
  - scripts/gen_hubspot_enums_js.py
  - scripts/gen_icp_scoring_js.py
  - scripts/remediate_veto_companies.py
  - scripts/simulate_rubric_weights.py
  - scripts/sync_hubspot_properties.py
  - scripts/veto_remediation_report.py
  - scripts/zoominfo_company_client.py
  - src/icp_scoring.py
  - src/normalizer.py
  - tests/fixtures/companies_jscode_frozen.json
  - tests/n8n/antiIcpFlagMirror.test.mjs
  - tests/n8n/companyRecomputeLaneFlow.test.mjs
  - tests/n8n/companyVersionStaleRecompute.test.mjs
  - tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs
  - tests/n8n/enrichment.test.mjs
  - tests/n8n/fixtures/frozen/exec_12682.runData.json
  - tests/n8n/fixtures/frozen/exec_12683.runData.json
  - tests/n8n/materialConflictNoVetoFlip.test.mjs
  - tests/n8n/regionAliasParity.test.mjs
  - tests/n8n/reviewQueueEndpoint.test.mjs
  - tests/n8n/sj2VersionStaleGate.test.mjs
  - tests/n8n/sjPredicates.test.mjs
  - tests/test_backfill_dry_run.py
  - tests/test_backfill_seed_company_scores.py
  - tests/test_bug10_company_search_transport.py
  - tests/test_check_schema_drift.py
  - tests/test_cloud_companies_branch.py
  - tests/test_cloud_write_path.py
  - tests/test_flow_rubric_conformance.py
  - tests/test_geography_flow_conformance.py
  - tests/test_hubspot_properties_config.py
  - tests/test_icp_named_account_floor.py
  - tests/test_icp_scoring_generated_currency.py
  - tests/test_icp_scoring.py
  - tests/test_loss_reason_report.py
  - tests/test_normalizer.py
  - tests/test_recompute_flag_isolation.py
  - tests/test_remediate_veto_companies.py
  - tests/test_rubric_change_guard.py
  - tests/test_scaffold.py
  - tests/test_scoring_parity.py
  - tests/test_simulate_rubric_weights.py
  - tests/test_sync_hubspot_properties.py
  - tests/test_veto_remediation_report.py
  - tests/test_zoominfo_company_client.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: clean
---

# Phase 75: Code Review Report

**Reviewed:** 2026-09-20
**Depth:** standard
**Files Reviewed:** 68 (reviewed as the `dfef89d9..HEAD` diff per each file, not full bytes)
**Status:** clean

## Summary

Phase 75 makes the geography hard-veto's target-region whitelist config-driven
(`config/icp_scoring.yaml` `regions.home`/`regions.aliases`, replacing three independent
hand-typed `AU/NZ/ANZ` literal sets in `src/icp_scoring.py`, `scripts/build_cloud_workflows.py`'s
`Decide Company Action`, `n8n/code/normalizeProviders.js`, `src/normalizer.py`, and
`scripts/zoominfo_company_client.py`), adds a `lv_icp_scoring_version` staleness mechanism with
a new `ALLOW_HUBSPOT_RECOMPUTE_WRITES` standing write authority, and adds an enum-option-safe
UPDATE path to `scripts/sync_hubspot_properties.py`.

This review traced the diff since `dfef89d9` for every listed file (not full-file re-reads),
cross-checked the Python (`src/icp_scoring.py`) and JS (`ENRICH_DECIDE_CO_CLOUD`'s `_regionKey`)
scoring engines for parity, verified the three-state region rule (`unknown` / `home` / `other`,
never firing the veto on a blank/never-enriched region) is preserved in both engines and in the
JS `Company Gate` version-stale reroute (`!row.lookup_failed` guard), and verified:

- `.venv/bin/python scripts/build_cloud_workflows.py` and `.venv/bin/python
  scripts/gen_geography_flow.py` are both no-ops against the committed tree (`git diff --quiet`
  clean on `n8n/` and the geography flow `.after.json`) — no hand-edited generated artefact.
- `.venv/bin/python -m pytest -q` — 5210 passed, 160 skipped, 0 failed.
- `node --test tests/n8n/*.test.mjs` — 1350 passed, 0 failed (including
  `frozenFixtureSecrets.test.mjs`, which globs the whole `tests/n8n/fixtures/frozen/` directory
  and therefore already covers the two new `exec_12682`/`exec_12683` runData fixtures).
- The new `ALLOW_HUBSPOT_RECOMPUTE_WRITES` flag ships `"false"` in every committed workflow,
  is absent from `operator-claude-plugin/scripts/n8n_arming.py`'s overlay/disarm sets and from
  `scripts/deploy_n8n_workflows.py`'s `--enable-baked-flags` overlay spec (confirmed by grep and
  by the dedicated `tests/test_recompute_flag_isolation.py` suite, all green), and is only read
  live by `scripts/bounce_n8n_workflows.py`, which compares it against the **committed** body
  rather than a hardcoded literal — so a manual operator flip is visible on the next bounce in
  either direction (armed-but-not-committed and committed-but-not-armed both fail the row).
  The flag's authority is confirmed to cover *both* operator-requested (`recompute: true`
  webhook) and version-stale-reroute rows — this reads as deliberate per the phase's own D-75-16
  ruling text ("today the recompute path REWRITES action from skip to enrich"), not scope creep.
- The `lv_country_region_normalized` enum, `hubspotEnums.generated.js`, and
  `n8n/code/icpScoring.generated.js`'s `REGIONS_HOME`/`REGION_ALIASES` all agree with
  `config/icp_scoring.yaml`'s `regions.home`/`regions.aliases` (pinned by
  `tests/n8n/regionAliasParity.test.mjs` and `tests/test_icp_scoring_generated_currency.py`,
  both exercised and green). `UK` is hidden rather than deleted (the sync tool's new `update`
  bucket explicitly refuses to drop a live enum option — verified in
  `scripts/sync_hubspot_properties.py`'s `compute_property_diff` and its test coverage).
- `normalizePhone.js`'s `_iso2()` guard (`/^[A-Z]{2}$/.test(alias || "")`) correctly filters out
  the new non-ISO2 alias `"ANZ"` before it could be handed to `normalizePhone`'s
  `CALLING_CODE` table; the three new alias regions with no `CALLING_CODE` entry (`ZA`, `HK`,
  `AE`) fall through to the pre-existing AU-heuristic fallback exactly as an unmapped region did
  before this phase — not a behavior regression.
- The live-write blast radius claims in `WRITE_SAFETY_DEFAULTS`'s comment and
  `docs/OPERATOR-RESCORE.md` (exactly four properties on a bare recompute row: the veto triple
  plus `lv_icp_scoring_version`) match `ENRICH_DECIDE_CO_CLOUD`'s actual PATCH construction.
- The one applicable pending todo triage (`2026-09-20-other-stamped-records-cannot-be-rescued-
  by-recompute.md`, `2026-09-20-sj2-version-stale-backstop-is-armed-only.md`) is correctly typed
  (`kind: design` / `kind: question`, each with `decision_needed`/`trigger`+`owner`) per CLAUDE.md
  §31 — neither is an untriaged defect.

No BLOCKER or WARNING-level defects were found in this diff. Two Info-level, pre-existing-pattern
observations are recorded below.

## Info

### IN-01: Veto reason string re-hardcoded as a literal in `scripts/simulate_rubric_weights.py`

**File:** `scripts/simulate_rubric_weights.py:105`
**Issue:** `OUTSIDE_HOME_VETO_REASON = "Outside target regions"` is a hand-typed literal
(renamed from the pre-existing `NON_ANZ_VETO_REASON = "Non-ANZ geography"` literal), while the
sibling scripts touched in the same phase (`scripts/remediate_veto_companies.py`,
`scripts/veto_remediation_report.py`) read the reason string from
`config/icp_scoring.yaml["hard_vetoes"]["outside_home_regions"]["reason"]` at runtime instead.
This is not a new defect introduced by Phase 75 — the same script hardcoded the string before
the rename too — but the phase touched this line and could have closed the gap in the same
motion. A future yaml edit to the reason string will silently desync this one script's
`false_veto`-detection heuristic from the two runtime-reading scripts.
**Fix:** Read the reason from `config/icp_scoring.yaml` via `load_yaml(...)["hard_vetoes"]
["outside_home_regions"]["reason"]`, mirroring `_outside_home_reason()` in
`scripts/veto_remediation_report.py`.

### IN-02: `regions.aliases` key `"in"` is a two-letter English word

**File:** `config/icp_scoring.yaml` (regions.aliases)
**Issue:** The alias table maps the exact lowercase string `"in"` to `"IN"` (India). Because
every lookup site lowercases and exact-matches the full country-field value (never a substring
match), this is not exploitable as written — but it's the one alias key in the table that is
also a common English word, and a future caller that ever normalizes a partial/garbled country
string (rather than the whole field) would silently resolve to India. No such caller exists
today.
**Fix:** None required; flagged for awareness only. If it becomes a real risk, prefer requiring
a minimum length or an explicit ISO2 hint for two-character keys equal to common short words.

---

_Reviewed: 2026-09-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
