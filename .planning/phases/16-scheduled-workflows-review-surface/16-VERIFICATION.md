---
phase: 16-scheduled-workflows-review-surface
verified: 2026-07-23T07:00:00Z
status: human_needed
score: 9/9 must-haves verified (structurally, offline)
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Run the operator runbook: provision_n8n_credentials.py, deploy_n8n_workflows.py (with N8N_URL/N8N_API_KEY/ALLOW_N8N_DEPLOY=true), activate 'LV Enrichment (Cloud template)' and 'LV Scheduled Maintenance (Cloud)' on a real n8n Cloud instance, and live-create the two SJ-3 HubSpot properties."
    expected: "Both workflows appear active on n8n Cloud with every node credential-bound (no unbound-node import errors); the phase goal's literal 'the pipeline runs live on n8n Cloud, the background reconciliation layer runs on schedule' becomes true, not just deployable."
    why_human: "Requires a live n8n Cloud subscription, live HubSpot portal writes, and live provider credentials — none of which exist in this offline environment. Cannot be proven by grep/test."
  - test: "Flip lv_enrichment_review_approved=true on one real needs_review company record and watch the live 'Apply Review' branch fire."
    expected: "reviewApply's computed canonicalPatch+clearPatch actually reach the HubSpot company record — but the built 'Review Apply Update' node ships with updateFields:{} (a documented placeholder, same convention as the pre-existing webhook-branch Update nodes); an operator must map {...canonicalPatch, ...clearPatch} onto the node's custom-properties UI before this works live."
    why_human: "The dynamic per-record patch is not baked into the builder's JSON output by design (values vary per record); wiring it is an operator/deploy-time step this repo cannot execute or grep-prove offline."
  - test: "Send a real HubSpot company-object webhook event (objectId/objectType/subscriptionType only, no email/domain/firstname) through the deployed Cloud webhook and confirm identity resolves and enrichment proceeds end to end."
    expected: "The event resolves to the correct company and the companies branch runs providers/research/judge/merge against it."
    why_human: "Documented limitation (16-01-SUMMARY Deviation 3, MINIMUM-scope shim): Build Identity/Build Company Identity still read direct body fields (email/domain) rather than fetching the record by objectId. A genuine HubSpot event carries none of those fields, so this path is unproven against a real event shape without a live webhook call and a follow-up fetch-by-id node the plan explicitly scoped out."
---

# Phase 16: Scheduled Workflows & Review Surface — Verification Report

**Phase Goal:** "The pipeline runs live on n8n Cloud, the background reconciliation layer runs
on schedule, and needs-review records reach a human who can approve them — held to
`docs/SYSTEM-CONTRACT.md`."
**Verified:** 2026-07-23
**Status:** human_needed (all 9 ROADMAP success criteria and every named review finding are
structurally VERIFIED offline; the goal's literal "runs live" clause requires a live n8n Cloud
operator action that cannot be proven in this repo — see Human Verification below)
**Re-verification:** No — initial verification

## Environment / Reproduction

- `.venv/bin/python -m pytest -q` → **266 passed** (matches SUMMARY claim exactly).
- `node --test tests/n8n/*.test.mjs` → **147 passed** (matches SUMMARY claim exactly).
- `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet n8n/` → **clean** (builder rebuild is byte-identical; no drift between committed JSON and freshly-generated JSON).
- Frozen files (`mergeCompanies.js`, `judge.js`, `enrichmentGate.js`, `webResearch.js`, `dedupeSweep.js`) are byte-identical to the pre-Phase-16 commit (`eb0adab`) — `git diff --stat eb0adab -- <files>` returns nothing.
- All 9 phase-16-01/16-02 task commit hashes verified present in `git log` (34e6dcf, d87b8bb, a444fc7, a8c4d5a, 601c787, 1b436e1, 48212ce, 9a7fd4a, 595026b).

## Per-Criterion Verdicts (ROADMAP's 9 Phase-16 Success Criteria)

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Schedule-triggered n8n workflows for SJ-1 (hourly input-gap), SJ-2 (monthly stale refresh), SJ-3 (15-min requested poller), keyed on pipeline-owned inputs only, never `lv_icp_tier`/`lv_icp_scored_at` | ✓ VERIFIED | `build_scheduled_maintenance_cloud()` in `scripts/build_cloud_workflows.py` emits all three scheduleTrigger branches into `n8n/wf_scheduled_maintenance_cloud.json`. `tests/n8n/sjPredicates.test.mjs` (12 tests, all pass) asserts SJ-1's 3 OR'd single-filter groups, SJ-2's epoch-ms cutoff + 2 LT filters, SJ-3's single AND'd group — and an explicit negative test (`DERIVED_ICP_OUTPUT_RE`) asserts no SJ filter block anywhere references `lv_icp_tier|lv_icp_fit_score|lv_icp_scored_at`. |
| 2 | `build_cloud_workflows.py` emits scheduleTrigger nodes; `dedupeSweep.js` wired into an active scheduled workflow (CLAUDE.md §13.4) | ✓ VERIFIED | `n8n/wf_scheduled_maintenance_cloud.json` is in the `ACTIVE` deployable-set list in `tests/test_architecture_guard.py` (line 24) and `test_top_level_is_exactly_the_deployable_set` passes. `tests/n8n/dedupeSweepWiring.test.mjs` (5 tests, all pass) proves the Dedupe Sweep node exists, references no HubSpot URL (classify-only), and feeds a downstream HubSpot write node. `dedupeSweep.js` itself is git-unchanged. |
| 3 | The §22.2 review loop closes: flag → decision JSON → RevOps approve → apply → clear, on the 9 review properties | ✓ VERIFIED (structurally) | `n8n/code/reviewApply.js` (75 lines) implements refetch compare-and-set, fail-closed malformed-JSON handling, and a structural Approach-C guard (imports `DEFAULT_COMPANY_POLICY` from `mergeCompanies.js` as the field allowlist — `lv_icp_fit_score`/`lv_icp_tier` are absent from that policy object, so they cannot appear in `canonicalPatch` by construction). `tests/n8n/reviewLoop.test.mjs` (7 tests) proves the producer-consumer contract, the negative Approach-C case, the non-clobber compare-and-set, and the fail-closed cases. All 9 review properties (`lv_enrichment_needs_review`, `_review_reason`, `_review_candidate_json`, `_review_approved`, `_reviewed_by`, `_reviewed_at`, `lv_icp_needs_review` ×2 objects) confirmed present in `config/hubspot_properties.yaml` (from Phase 15, unchanged). **Caveat:** the built "Review Apply Update" node ships with `updateFields: {}` — the computed patch is not baked into the JSON (documented as a deliberate placeholder matching the pre-existing webhook-branch Update-node convention); wiring the dynamic patch onto the node is an operator/deploy-time step, not disproven but not live-provable here. See Human Verification. |
| 4 | SJ-1..SJ-3 acceptance tests authored with this phase's plan | ✓ VERIFIED | `tests/n8n/sjPredicates.test.mjs` created this phase, 12 tests, all pass — covers SJ-1/2/3 filter shapes, terminal dispatch, and the Approach-C negative check. |
| 5 | `$env`→credentials + build-time constants; 6 secrets bound to credentials, 6 flags baked; local-replica and Cloud builders share one single-source, must not diverge without a parity story | ✓ VERIFIED | `tests/test_architecture_guard.py::test_no_env_or_vars_in_cloud_workflows` passes — zero `$env`/`$vars` word-boundary matches in `wf_enrichment_cloud.json` (independently confirmed: also zero in `wf_scheduled_maintenance_cloud.json`, though only the enrichment workflow is asserted by name). `CONFIG_FLAG_DEFAULTS` (6 keys) and `SECRET_ENV_NAMES` (6 names) are the single module-level source both `build_enrichment_local_live()` and `build_enrichment_cloud()` read; `tests/test_builder_flag_parity.py` (6 tests) asserts both builders reference the identical 6-flag/6-secret sets. `WRITE_SAFETY_DEFAULTS` (Cloud-write-only) has zero key overlap with `CONFIG_FLAG_DEFAULTS` — confirmed by direct import (`set(CONFIG_FLAG_DEFAULTS) & set(WRITE_SAFETY_DEFAULTS) == set()`), correctly excluded from the parity set. |
| 6 | Credential-provisioning script: two-key gated, ~5 credential objects for 6 secrets, create-if-missing, no-creds skip path, never in offline suite | ✓ VERIFIED | `scripts/provision_n8n_credentials.py` — `_has_n8n()` skip-to-exit-0, `_writes_allowed()` two-key gate (`DRY_RUN=false AND ALLOW_N8N_DEPLOY=true`), `CREDENTIAL_MANIFEST` (6 entries: HubSpot, Lusha, Apollo, Anthropic, ZoomInfo [holds both client_id+secret], + a 7th "LV Enrichment Webhook" credential for Task 6's shared secret — 6 secret env vars total across 6 credential objects), schema introspection via `GET /api/v1/credentials/schema/{type}` wrapped in try/except, create-if-missing only (no PUT), writes `.n8n_credential_ids.json` (gitignored, confirmed in `.gitignore`), never prints a secret value (grep confirms no f-string interpolation of any secret env var). `tests/test_deploy_n8n_workflows.py`'s hermetic fixture monkeypatches `requests.get/post/put` to raise on any call — proves the offline suite makes zero live HTTP calls. |
| 7 | Deploy script over the guarded deployable set — dry-run diff (create-vs-update), `X-N8N-API-KEY`, idempotent | ✓ VERIFIED | `scripts/deploy_n8n_workflows.py::compute_workflow_diff` matches by workflow `name` against a fresh `GET /api/v1/workflows` every run (never local state — idempotent); `_writes_allowed()` two-key gate; `_instance_ok()` wrong-instance guard does NOT fail open (requires `N8N_EXPECTED_URL` set-and-equal, or `N8N_URL` host ends `.n8n.cloud` — refuses with zero HTTP calls otherwise, confirmed by `tests/test_deploy_n8n_workflows.py::test_instance_ok_refuses_non_cloud_host_when_expected_unset_no_fail_open`). Credential binding (`bind_credentials`) resolves via `NODE_CREDENTIAL_MAP` (node-name→credential-name, correctly disambiguating Lusha/Apollo/Anthropic which share the `httpHeaderAuth` type) + the provisioned name→id map, and **fails closed** (raises `ValueError`, no unbound node emitted) when a mapped credential name is absent — this was the #1 cross-AI HIGH finding and is directly fixed. |
| 8 | Cloud-template companies-branch port — `build_enrichment_cloud()` gains the full ICP pipeline | ✓ VERIFIED | `tests/test_cloud_companies_branch.py` (8 tests, all pass): every company-branch node BFS-reachable from Webhook Trigger; `Emit Company Targets` (the hard-coded Harvey-Norman/Racing-NSW fixture emitter — sol's HIGH finding) is confirmed **absent** from the built Cloud workflow; the company canonical patch never contains a derived ICP output field; `ENRICH_DECIDE_CO_CLOUD` is confirmed as the review-loop producer (writes `lv_enrichment_needs_review`/`_review_reason`/`_review_candidate_json` and holds those fields' canonical writes on any `needs_review` decision — reviewed and matches kimi's HIGH finding fix exactly); HubSpot Create/Update are native credential-bound nodes; the ZoomInfo company Mint node is credential-bound Basic Auth. |
| 9 | RT-5 research caching by domain, 180-day TTL keyed on `_verified_at` properties | ✓ VERIFIED | `n8n/code/enrichmentGate.js` (frozen, unmodified) already implemented the 180-day staleness logic; `tests/n8n/enrichmentGate.test.mjs` (4 tests) is its **first-ever direct unit test** — fresh (~10 days, both required fields + both verified_at) → skip; stale (200 days) → enrich; never-verified → enrich; a missing-required-field fixture → enrich for "missing" not "stale" (the exact fixture-bug fix kimi's review flagged). SJ-2's epoch-ms cutoff (`Date.now() - 180 * 86400000`) matches the 180-day constant, and its Adapt step (`ENRICH_ADAPT_SJ2_SEARCH`, of the `ENRICH_ADAPT_CO_SEARCH` shape) feeds the reused Company Gate a populated `existingRecord` rather than a raw search row — confirmed by `sjPredicates.test.mjs`'s "SJ-2: an Adapt step ... feeds Company Gate with a populated existingRecord, not raw rows" test. |

**Score: 9/9 ROADMAP success criteria structurally VERIFIED offline.**

## Cross-AI Review Finding Landing Check (16-REVIEWS.md)

All findings named in the verification brief were traced to source and confirmed landed:

| Finding | Status | Evidence |
|---------|--------|----------|
| Approach C: no write path for `lv_icp_fit_score`/`lv_icp_tier`; SJ predicates never key on derived outputs; negative test exists | ✓ LANDED | `mergeCompanies.js` `DEFAULT_COMPANY_POLICY` has no entries for either field (comment explains removal is deliberate, Phase 15). `sjPredicates.test.mjs` has an explicit negative test (`DERIVED_ICP_OUTPUT_RE`) over all SJ-prefixed nodes. `test_cloud_companies_branch.py::test_company_canonical_patch_never_contains_a_derived_icp_output_field` covers the webhook producer side too. |
| Credential-ID binding (deploy) | ✓ LANDED | `bind_credentials()` + `NODE_CREDENTIAL_MAP` + fail-closed `ValueError` on unresolvable id, exactly as specified (see Criterion 7 above). |
| Review loop closes end-to-end (producer↔consumer) | ✓ LANDED | `ENRICH_DECIDE_CO_CLOUD` (producer, `build_cloud_workflows.py:1977`) ↔ `n8n/code/reviewApply.js` (consumer) — `reviewLoop.test.mjs`'s "producer-consumer contract" test builds the candidate JSON in the exact shape the producer emits and proves it round-trips. Malformed-JSON fail-closed and all-or-nothing compare-and-set both proven. |
| Webhook hardened (auth, event parse, real HubSpot nodes, fail-closed, write-safety gate) | ✓ LANDED (with one documented, non-blocking scope carve-out) | Native Header Auth on Webhook Trigger (not a Code node — a documented, arguably-safer deviation); `Parse HubSpot Event` + `Route By Object Type` upstream of Build Identity; both HubSpot Search nodes carry real `filterGroups` + request `hs_object_id`; Adapt steps distinguish `lookup_failed` from confirmed-absent and the decide nodes override `create`→`skip` on that flag (never duplicate-creates on a transient failure); `WRITE_SAFETY_DEFAULTS` (`ALLOW_HUBSPOT_RECORD_WRITES` default false + create switch + empty-allowlist-denies-everything) gates every write, confirmed disjoint from the parity-guarded flag set. The one documented carve-out: Build Identity/Build Company Identity still read direct body fields rather than fetch-by-id, an explicitly plan-permitted minimum-scope shim (see Human Verification item 3). |
| SJ-3 prerequisite properties exist | ✓ LANDED | `lv_enrichment_requested` (bool, true/false options) and `lv_enrichment_status` (enum, all 6 values incl. `skipped`) confirmed on both `lv_enrichment` (companies) and `lv_enrichment_contacts` (contacts) groups in `config/hubspot_properties.yaml`. |
| dedupeSweepWired into `wf_scheduled_maintenance_cloud.json`, frozen file unmodified, workflow in ACTIVE set | ✓ LANDED | Confirmed above (Criterion 2); `test_top_level_is_exactly_the_deployable_set` passes. |
| Criterion-5 parity: `CONFIG_FLAG_DEFAULTS`+`SECRET_ENV_NAMES` single-source + `test_builder_flag_parity.py` | ✓ LANDED | Confirmed above (Criterion 5). |
| Offline discipline: zero live network/HubSpot/n8n writes in the suite; live deploy/provision/activation is Manual-Only runbook | ✓ LANDED | `tests/test_deploy_n8n_workflows.py`'s `hermetic` fixture monkeypatches `requests.get/post/put` to raise-on-call — any accidental live call would fail the test suite itself, not just go unnoticed. Both plans' `<verification>` sections explicitly scope live deploy/provision/activation to a "Manual-Only (operator runbook, non-gating)" section. |
| Frozen files unmodified: `mergeCompanies.js`, `judge.js`, `enrichmentGate.js`, `webResearch.js` | ✓ LANDED | `git diff --stat eb0adab -- n8n/code/mergeCompanies.js n8n/code/judge.js n8n/code/enrichmentGate.js n8n/code/webResearch.js n8n/code/dedupeSweep.js` returns nothing — byte-identical to the commit immediately preceding Phase 16's start. |

## Required Artifacts

| Artifact | Expected | Status |
|----------|----------|--------|
| `scripts/deploy_n8n_workflows.py` | diff + bind_credentials + two-key gate + no-fail-open instance guard | ✓ VERIFIED |
| `scripts/provision_n8n_credentials.py` | 6-secret manifest, schema introspection, create-if-missing, name→id map | ✓ VERIFIED |
| `build_enrichment_cloud()` companies branch + `ENRICH_DECIDE_CO_CLOUD` | full port, review-loop producer, no fixture emitter | ✓ VERIFIED |
| `CONFIG_FLAG_DEFAULTS`/`SECRET_ENV_NAMES`/`WRITE_SAFETY_DEFAULTS` | shared single-source + Cloud-only write gate, disjoint | ✓ VERIFIED |
| `config/hubspot_properties.yaml`: `lv_enrichment_requested`/`lv_enrichment_status` | both objects, correct option shapes | ✓ VERIFIED |
| `build_scheduled_maintenance_cloud()` + `n8n/wf_scheduled_maintenance_cloud.json` | SJ-1/2/3 + dedupe + review-loop branches | ✓ VERIFIED |
| `n8n/code/reviewApply.js` | refetch compare-and-set, fail-closed, structural Approach-C guard | ✓ VERIFIED |
| `tests/test_deploy_n8n_workflows.py`, `test_cloud_companies_branch.py`, `test_cloud_write_path.py`, `test_builder_flag_parity.py`, `test_architecture_guard.py::test_no_env_or_vars_in_cloud_workflows`, `test_hubspot_properties_config.py` | offline, zero live calls | ✓ VERIFIED (all pass) |
| `tests/n8n/sjPredicates.test.mjs`, `enrichmentGate.test.mjs`, `dedupeSweepWiring.test.mjs`, `reviewLoop.test.mjs` | offline, zero live calls | ✓ VERIFIED (all pass, 24 tests total) |

## Requirements Coverage

`phase_req_ids` is null for Phase 16 in `.planning/REQUIREMENTS.md` (grep confirms no `Phase 16` row) — per the task brief, the requirement set is the 9 ROADMAP success criteria above, all satisfied.

## Anti-Patterns Found

- No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` debt markers in any file this phase created or modified (checked all 12 new/modified source+test files).
- No secret-value printing in either new script (grep confirms no f-string interpolation of `HUBSPOT_PRIVATE_APP_TOKEN`/`*_API_KEY`/`ZOOMINFO_CLIENT_SECRET` into a printed line).
- `n8n/wf_enrichment_local.json`/`n8n/wf_enrichment_local_live.json` (docker-replica fixture workflows) are picked up by `deploy_n8n_workflows.py`'s `glob("wf_*.json")` alongside the two genuinely Cloud-intended workflows — sol's LOW finding ("deploying every top-level wf_*.json would import local fixture workflows") is technically still present. Low severity: these workflows legitimately keep `$env`/`$vars` expressions (by AR-4 design) and would import as unbound/broken nodes on Cloud if a live deploy were run unfiltered — an operator following the runbook literally would need to notice and exclude them. Not a security or correctness issue for the *offline* proof, but worth a follow-up filter (e.g. `wf_*_cloud.json`/`wf_scheduled_maintenance_cloud.json` explicitly) before the first live deploy is actually run.

## Human Verification Required

See frontmatter `human_verification` — three items, all converging on the same root cause:
**the phase goal's literal "runs live on n8n Cloud" clause has not been executed against a real
n8n Cloud instance.** Every one of the 9 ROADMAP success criteria (which are the actual
specified deliverable contract per the task brief) is satisfied — the tooling, workflows, and
tests exist and are proven offline. What remains is exclusively the live operator runbook both
plans explicitly scope out as "Manual-Only, non-gating" and STATE.md itself documents this
precedent from Phase 15 ("tooling offline-proven, live operator runbook pending").

This is not a code gap; it is a live-environment gap that cannot be resolved by further code
changes in this repository. The verification therefore routes to `human_needed` rather than
`gaps_found` — no artifact is missing, stubbed, or unwired; the remaining work is executing the
already-built and already-tested deploy/provision scripts against a real n8n Cloud + HubSpot
portal.

## Gaps Summary

No blocking gaps. All 9 ROADMAP success criteria and every named cross-AI review finding are
structurally verified against the actual codebase (not SUMMARY claims): 266 pytest + 147 node
tests green, builder rebuild byte-identical, frozen files byte-identical to pre-phase state, all
9 task commits present in git history. The single open item is live execution on a real n8n
Cloud instance — explicitly out of this phase's automated scope by both plans' own design, and
consistent with the same "tooling proven / live pending" split used for Phase 15.

---
*Verified: 2026-07-23*
*Verifier: Claude (gsd-verifier)*
