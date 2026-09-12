---
phase: "72"
slug: "enrichment-extras-land-in-hubspot"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
threats_open_below_threshold: 1
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: "2026-09-13"
---

# Phase 72 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register consolidated from the `<threat_model>` blocks of all twelve plans (`72-01`..`72-12`);
> ids that recur across plans (`T-72-01`, `T-72-03`, `T-72-07`, `T-72-09`, `T-72-SC`) appear once
> with every plan that carried them. No SUMMARY carried a `## Threat Flags` section. ASVS L1
> grep-depth verification, 2026-09-13; evidence column names the artifact checked.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator spreadsheet → plugin CSV parse | untrusted header names and cell values enter here | contact PII, arbitrary column names |
| provider / waterfall response → merge candidate | untrusted third-party property names and values compete with CRM data | phones, emails, LinkedIn URLs, geo, seniority, firmographics |
| plugin dispatch CSV → n8n webhook | `write_dispatch_csv`'s STRUCT-01 allowlist is the input-validation control | canonical contact rows + `source_by_field` |
| merged row → `held_queue.json` on disk | the only persistent client-side write | seven added PII fields per held row |
| HubSpot property history → merge gate | a timestamp decides whether a non-blank CRM value is overwritten | `propertiesWithHistory` `versions[].timestamp` |
| company candidate → ICP scoring inputs | `lv_country_region_normalized` drives a hard veto and a tier | region / ISO codes |
| repo config / probe → HubSpot schema API | `config/hubspot_properties.yaml` describes writes to the live portal; probe is read-only | property definitions |
| local committed JSON → n8n Cloud instance | a PUT replaces the body of a running, credential-bound workflow | workflow bodies incl. write-safety constants |
| armed n8n workflow → HubSpot CRM write | the only place this phase changes what lands on a real record | contact / company property values |
| operator paste-back → project documentation | live evidence becomes the repo's record of truth | execution ids, property values, flags |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status | Evidence (L1, 2026-09-13) |
|-----------|----------|-----------|----------|-------------|------------|--------|---------------------------|
| T-72-01 (plans 01/02/05/06) | Tampering | widened `MERGE_CONTACTS` candidate set, `_2` slots, new company targets vs `config/field_policy.yaml` | high | mitigate | every reachable key carries an explicit `class` + `min_confidence`; no default fallthrough | closed | `config/field_policy.yaml`: `mobilephone`, `hs_linkedin_url`, `lv_linkedin_url`, `lv_phone_2`, `lv_mobilephone_2` entries present (6), 34 `min_confidence` lines; `tests/n8n/fieldProducerMatrix.test.mjs` |
| T-72-02 (plan 04) | Tampering / Repudiation | recency gate clock inputs | critical | mitigate | only `opts.now` and HubSpot `propertiesWithHistory` timestamps; CSV candidates carry no observation time; provider-sourcing decided by `opts.sourceByField` name, never a row time | closed | `n8n/code/mergeContacts.js` `historyByField`/`sourceByField` (9 refs); `tests/n8n/mergeRecencyGate.test.mjs` |
| T-72-03 (plans 05/08) | Elevation of Privilege | HubSpot property creation | critical | mitigate | only via `scripts/sync_hubspot_properties.py` two-key gate (`DRY_RUN=false` AND `ALLOW_HUBSPOT_PROPERTY_WRITES=true`), never `ALLOW_N8N_ARM` | closed | `scripts/sync_hubspot_properties.py`: `ALLOW_HUBSPOT_PROPERTY_WRITES` (4), `DRY_RUN` (4); undo manifest `config/hubspot_migration/undo-manifest-481a5c99-….json` |
| T-72-04 (plan 03) | Information Disclosure | `held_queue.json` gains seven PII fields | medium | mitigate | closed `ROW_FIELD_ALLOWLIST`; forbidden-name scan; D-71-05 wipe | closed | `operator-claude-plugin/scripts/held_queue.py` `ROW_FIELD_ALLOWLIST` (8 refs) |
| T-72-05 (plan 01) | Tampering | `ADAPT_SEARCH_RESULTS` `existingRecord` stamp | high | mitigate | value-match on the row's own normalized email, never index; zero hits / `lookup_failed` → `{}` | closed | `scripts/build_cloud_workflows.py` `existingRecord` (132 refs), normalized-email match (19); `tests/n8n/ingestTracerFlow.test.mjs` |
| T-72-06 (plan 01) | Denial of Service | regenerated `n8n/wf_*.json` self-dispatch | high | mitigate | `assert_no_self_dispatch` refuses generation on any `executeWorkflow` node in the enrichment build | closed | `scripts/build_cloud_workflows.py` `assert_no_self_dispatch` (4); `n8n/wf_enrichment_cloud.json` has 0 `n8n-nodes-base.executeWorkflow` nodes |
| T-72-07 / T-72-17 (plans 01/02/04/06) | Elevation of Privilege | write-safety constants in regenerated bodies | critical | mitigate | every body ships disarmed; walker tests arm in-memory copies only | closed | all `n8n/wf_*_cloud.json`: 0 `ALLOW_* = "true"` literals, 46 `"false"`; live read-back 2026-09-13 all `false` (72-UAT.md Test 3) |
| T-72-08 / T-72-16 (plans 01/04) | Information Disclosure | frozen walker fixtures | medium | mitigate | redact Webhook Trigger `headers` before freezing | closed | `tests/n8n/fixtures/`: every `x-enrichment-secret` value is `<redacted>` (10 occurrences, 0 real); 72-UAT.md carries 0 secret strings |
| T-72-09 (plans 02/06) | Tampering | `ENRICH_GATE` / `ENRICH_CO_GATE` `REQUIRED` chase lists | high | mitigate | write-only keys never enter `REQUIRED` (12 contacts / 13 companies) | closed | `tests/n8n/widenedKeyParity.test.mjs` (REQUIRED pinned), green at HEAD |
| T-72-10 (plan 02) | Spoofing | `required_identity.any_of` | medium | accept | surface unchanged | closed (accepted) | `tests/n8n/columnMapIdentityParity.test.mjs` green unmodified |
| T-72-11 (plan 03) | Tampering | `PROVIDER_KEY_ALIASES` before the allowlist | high | mitigate | closed one-entry dict, key rename only | closed | `operator-claude-plugin/scripts/preingest.py:791` `PROVIDER_KEY_ALIASES = {"lv_linkedin_url": "linkedin_url"}` |
| T-72-12 (plan 03) | Tampering | D-72-05 provider-wins on CREATE | high | mitigate | creates only, never `IDENTITY_FIELDS`, only allowed keys, every replacement recorded in `conflicts` | closed | `preingest.py` `IDENTITY_FIELDS` (4), `conflicts` (13) |
| T-72-13 (plan 03) | Repudiation | merge report as only record of a CSV loser | medium | accept | report produced on every merging run | closed (accepted) | 72-03-SUMMARY.md decision D-72-20 |
| T-72-14 (plan 04) | Tampering | generalized `_isSystemCorrectable` | high | mitigate | all four §17.2.1 conjuncts incl. strict `rowConflicted === false` | closed | `mergeContacts.js` (2) and `mergeCompanies.js` (2) `rowConflicted === false` |
| T-72-15 / T-72-28 (plans 04/08) | Denial of Service | new ingest-lane HTTP hop and its Merges; deploying untested Merge topology | high | mitigate | D-70-23 sentinel gate; walker `starvedWithData` assertion; disarmed deploy before any armed send; live read-back of a created record | closed | `starvedWithData` asserted in 15 test files; disarmed deploy + read-back recorded 72-UAT.md Tests 2/3 (execs 12398–12406, 12411–12415) |
| T-72-18 (plan 05) | Tampering | runner-up selection | medium | mitigate | second element of the same trust-rank sort, deduped on normalized value | closed | `_overflowSlot`/`rankedByField` in both JS engines (9/8), `route_overflow` in `src/merge_policy.py` (3) |
| T-72-19 (plan 05) | Information Disclosure | `72-PORTAL-PROBE.json` | low | accept | metadata only, no record data, no token | closed (accepted) | file holds names/types/`readOnlyValue` only |
| T-72-20 (plan 05) | Repudiation | provenance under the wrong key | medium | mitigate | contacts engine writes `lv_contact_enrichment_provenance` | closed | `n8n/code/mergeContacts.js` (3 refs); live read-back Test 3 |
| T-72-21 (plan 06) | Tampering | contact geo reaching `lv_country_region_normalized` | critical | mitigate | D-72-16 forbids the path; guard test | closed | D-72-16 guard tests in 2 files under `tests/`; material-conflict machinery untouched |
| T-72-22 (plan 06) | Tampering | derived ISO codes | medium | mitigate | D-72-15: codes only from provider code-shaped values, no name→code table | closed | D-72-15 refs in `n8n/code`/`tests/n8n` (6) |
| T-72-23 (plan 07) | Tampering | gate spec arm/disarm instructions | high | mitigate | spec names `ALLOW_N8N_ARM`, bounce exits 1 while armed, post-send disarm confirmation | closed | `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md`: `ALLOW_N8N_ARM` (3), "exits 1" (2) |
| T-72-24 (plan 07) | Repudiation | stale CLAUDE.md | medium | mitigate | §17.2.2 as-built delta | closed | CLAUDE.md §17.2.2 present, amended through 2026-09-13 |
| T-72-25 (plan 07) | Elevation of Privilege | property-creation step in the gate spec | critical | mitigate | two-key gate named, never `ALLOW_N8N_ARM` | closed | same as T-72-03 |
| T-72-26 (plan 07) | Information Disclosure | CHANGELOG and gate spec content | low | accept | no token / portal id / record data | closed (accepted) | reviewed 2026-09-13 docs sweep |
| T-72-27 / T-72-12-01 (plans 08/12) | Elevation of Privilege / Tampering | the armed window; live HubSpot data during it | critical | mitigate | one record-scoped window per gate, closed same sitting, every `ALLOW_*` read back `false`, zero post-disarm executions | closed | 72-UAT.md Tests 2 and 3: flags `false` read back, zero executions after final disarm (execs 12402/12406, 12414) |
| T-72-29 (plan 08) | Repudiation | trusting the send's 200 | high | mitigate | every assertion from a re-read of the record | closed | 72-UAT.md read-back basis (9 refs) |
| T-72-30 (plan 08) | Information Disclosure | live test record left on the portal | medium | mitigate | created id recorded; hand-deletion is a confirmed checklist item | **open — below `high` threshold (non-blocking)** | Test 2 contact `352455353810` deleted (72-UAT.md line 197, operator-reported 204). Test 3 contact `352522004980`: DELETE command handed to operator 2026-09-13, **no 204 reported** (72-UAT.md Test 3 row (e)). Closes when the operator confirms the 204 or re-runs the delete. |
| T-72-09-01 (plan 09) | Tampering | `MERGE_CONTACTS` confidence derivation | high | mitigate | 85 only for a non-`csv` `source_by_field` provider; csv/80 default untouched | closed | `scripts/build_cloud_workflows.py` `CANDIDATE_ALIASES` (4 refs); `tests/n8n/ingestWidenedFieldsFlow.test.mjs` pre-alias fixture |
| T-72-09-02 (plan 09) | Elevation of Privilege | `CANDIDATE_ALIASES` write-target expansion | medium | mitigate | closed literal, one entry, two already-promotable targets, not request-derived | closed | same |
| T-72-09-03 (plan 09) | Repudiation | provenance source for `lv_linkedin_url` | low | accept | more accurate provenance; recorded | closed (accepted) | 72-UAT.md Test 3: source `waterfall`/85 |
| T-72-10-01 (plan 10) | Tampering | local-live existing-record fetch narrower than merge set | critical | mitigate | `HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR` widened to every `protect_if_current_present` field | closed | `build_cloud_workflows.py` `lv_phone_2` (11), `n8n/wf_enrichment_local_live.json` (5); `fieldProducerMatrix.test.mjs` |
| T-72-10-02 (plan 10) | Information Disclosure | widened `/search` property list | low | accept | same token/scopes, values stay in-execution | closed (accepted) | — |
| T-72-10-03 (plan 10) | Denial of Service | provider spend from a widened chase list | medium | mitigate | `REQUIRED` not widened | closed | `tests/n8n/widenedKeyParity.test.mjs` green |
| T-72-11-01 (plan 11) | Tampering | overflow dedup predicate (3 engines) | medium | mitigate | case folded in both JS engines, matching Python | closed | `toLowerCase` in both engines (2/2); mixed-case `EXT 12`/`ext 12` fixture in `overflowSlots.test.mjs` (4) |
| T-72-11-02 (plan 11) | Repudiation | frozen `companies_jscode_frozen.json` re-baseline | medium | mitigate | node-scoped diff review recorded; halts if any node other than `Merge Company` changed | closed | 72-11-SUMMARY.md (Merge Company diff review, 4 refs) |
| T-72-11-03 (plan 11) | Information Disclosure | provenance tail for deduped candidates | low | accept | only removes a duplicate | closed (accepted) | — |
| T-72-12-02 (plan 12) | Denial of Service | redeploy of a running workflow | high | mitigate | deploy + bounce disarmed first; node counts / `executionOrder` / flags read back before arming | closed | 72-UAT.md Test 3: 78/287/55/43/30, `v1`, all flags `false` |
| T-72-12-03 (plan 12) | Repudiation | UAT/CLAUDE.md transcription | medium | mitigate | only pasted values transcribed; gaps recorded honestly | closed | 72-UAT.md Test 3 row (e) records the unconfirmed deletion as a gap (2026-09-13 correction, commit 71907b15) |
| T-72-12-04 (plan 12) | Information Disclosure | pasted execution runData | medium | mitigate | enumerated fields only, never raw Webhook Trigger runData | closed | 72-UAT.md contains 0 `x-enrichment-secret` strings |
| T-72-SC (plans 09–12) | Tampering | npm/pip/cargo installs | high | accept | no package added | closed (accepted) | `git diff --stat 1a328347..HEAD -- requirements.txt operator-claude-plugin/requirements.txt package.json` empty |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (`high`) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-72-01 | T-72-10 | identity surface unchanged; parity test green unmodified | planner (72-02 PLAN) | 2026-09-12 |
| R-72-02 | T-72-13 | a discarded CSV value is recoverable from the run report; persisting it would change the D-71-04/05 schema | planner (72-03 PLAN), D-72-20 | 2026-09-12 |
| R-72-03 | T-72-19 | probe artifact carries property metadata only | planner (72-05 PLAN) | 2026-09-12 |
| R-72-04 | T-72-26 | docs describe already-documented names/behaviour; no token, portal id or record data | planner (72-07 PLAN) | 2026-09-12 |
| R-72-05 | T-72-09-03 | aliasing makes provenance more accurate; recorded in SUMMARY and 72-UAT.md | planner (72-09 PLAN) | 2026-09-13 |
| R-72-06 | T-72-10-02 | widened `/search` list uses the same token and scopes; values stay inside the execution | planner (72-10 PLAN) | 2026-09-13 |
| R-72-07 | T-72-11-03 | case folding only removes a duplicate provenance entry | planner (72-11 PLAN) | 2026-09-13 |
| R-72-08 | T-72-SC | no dependency added by any plan in the phase | planner (72-09..12 PLANs) | 2026-09-13 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-13 | 41 | 40 | 1 (T-72-30, medium — below `high` threshold, non-blocking) | secure-phase orchestrator, ASVS L1 grep-depth (short-circuit: `threats_open: 0`, register authored at plan time) |

**Residual for the operator:** confirm the restorable DELETE of UAT contact `352522004980`
returned `204`, or re-run it, then flip T-72-30 to closed. Command (credentials from `.env`):

```
! set -a; . ./.env; set +a; curl -s -o /dev/null -w '%{http_code}\n' -X DELETE -H "Authorization: Bearer $HUBSPOT_PRIVATE_APP_TOKEN" https://api.hubapi.com/crm/v3/objects/contacts/352522004980
```

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (one medium-severity item open below the `high` block threshold)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-13
