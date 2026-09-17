---
phase: "73"
slug: "ga-fix-list-from-stress-attempt-2"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
created: "2026-09-18"
verified: "2026-09-18"
register_authored_at_plan_time: true
---

# Phase 73 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> First audit (State B): register built from the seven `<threat_model>` blocks in
> `73-01-PLAN.md` … `73-07-PLAN.md` (30 threats). No `## Threat Flags` section exists in any
> SUMMARY. Auditor: `gsd-security-auditor` (opus), read-only, 2026-09-18. No implementation
> file was modified by the audit.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator plugin → n8n webhook | multipart POST with CSV rows, run_id, request-level flags | contact/company PII, shared webhook secret (header) |
| n8n → HubSpot | search / PATCH / POST / association PUT behind write gates | CRM records, private-app token (credential store) |
| n8n → providers (Apollo, Lusha, ZoomInfo, Anthropic) | enrichment / research / credit probes | company identity, provider API keys (credential store) |
| n8n executions API → repo fixtures | `scripts/freeze_execution_rundata.py` GETs runData into `tests/n8n/fixtures/frozen/` | Webhook Trigger headers (secret) — redacted wholesale before write |
| operator terminal → repo artefacts | `!` env-loading commands, gate records, UAT notes | credential VALUES never recorded; outcomes only |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-73-01-01 | Information Disclosure | `scripts/freeze_execution_rundata.py` → committed fixture | high | mitigate | `_redact_headers()` (`:80-100`) replaces the whole `headers` object; `exec_12434`/`exec_12449` carry 0 `x-enrichment-secret` hits | closed |
| T-73-01-02 | Information Disclosure | freeze script credential handling | medium | mitigate | env read at `:73-77`, names-only print at `:176-182`; `executions_client.py` exposes GET transports only | closed |
| T-73-01-03 | Repudiation | run report under-counting outcomes | medium | mitigate | `test_run_report_enrich_account.py:103-175` — 36 events bucketed, 18 markers counted, `joined + unjoinable == 35`, `unjoinable_seen is True` | closed |
| T-73-01-04 | Tampering | cross-run manifest bleed | medium | mitigate | `test_run_manifest.py:898` run-B read does not return run-A verdicts | closed |
| T-73-02-01 | Tampering | `reviewApply()` serialization | medium | mitigate | enum check (`reviewApply.js:92`) strictly before join (`:115`); refusal path all-or-nothing, empty `canonicalPatch` (test in `reviewLoop.test.mjs`) | closed |
| T-73-02-02 | Denial of Service | ingest search nodes vs HubSpot search cap | medium | mitigate | 3 search nodes at `batchInterval: 400, batchSize: 1` in generated JSON, pinned by `ingestSearchThrottle.test.mjs:23-42` — see audit note 2 | closed |
| T-73-02-03 | Elevation of Privilege | review-approve write path | low | accept | serialization-only change; all 5 committed cloud bodies `ALLOW_HUBSPOT_*="false"`; regeneration zero diff | closed (accepted, AR-73-01) |
| T-73-03-01 | Tampering | freemail domain accepted as a company identity | high | mitigate | one authoritative set in `companyLink.js:25`, pulled verbatim by the builder (`build_cloud_workflows.py:4679`), mirrored in Python (`test_people_and_url_normalisation.py:118`); backend holds `action: "review"` (`companyFreemailRefusal.test.mjs:47-56`) | closed |
| T-73-03-02 | Tampering | duplicate company from a match narrower than the stored form | high | mitigate | `operator: "IN"` over `domain_variants` on all 3 search sites; `companyDomainVariants.test.mjs:92` www.-stored record resolves from a bare request | closed |
| T-73-03-03 | Denial of Service | empty `values` list 400s the search | medium | mitigate | `["no-company-domain.invalid"]` sentinel (`build_cloud_workflows.py:640`); `companyDomainVariants.test.mjs:63,85` | closed |
| T-73-03-04 | Repudiation | name-only refusal reason without a remedy | medium | mitigate | `companyNameOnlyOutcome.test.mjs:81-83, 98-101` — outcome + missing domain + remedy asserted per reason | closed |
| T-73-03-05 | Tampering | IN search returns two companies | medium | accept | D-73-20 `bareHit || merged.results[0]` (`build_cloud_workflows.py:3343-3344`), both ids named in the reason | closed (accepted, AR-73-02) |
| T-73-04-01 | Denial of Service | duplicated row aborting a batch at the write node | high | mitigate | `csv_dedupe.py` at the input boundary; `test_csv_dedupe.py:310` only the deduped file reaches the wire; write-node containment under T-73-06-* | closed |
| T-73-04-02 | Tampering | over-eager collapse dropping a distinct person | high | mitigate | exact/casefold/trim only (`csv_dedupe.py:25`); `test_csv_dedupe.py:124, 242` distinct + identity-less rows never collapsed, no fuzzy matching | closed |
| T-73-04-03 | Repudiation | row disappearing with no record | medium | mitigate | `{row, duplicate_of, identity_key, outcome: "duplicate_in_csv"}` (`csv_dedupe.py:38,75-78`), rendered by `preview.py:144`; `test_csv_dedupe.py:269` | closed |
| T-73-04-04 | Tampering | field merge rewriting the surviving row | medium | mitigate | `test_csv_dedupe.py:45-68` loser-only value asserted absent from the survivor | closed |
| T-73-05-01 | Information Disclosure | provider credential handling on the status lane | medium | mitigate | `wf_backend_status_cloud.json` unchanged at 30 nodes; all probes credential-typed, no `$env` inlining; 0 credential-shaped strings in tests/fixtures | closed |
| T-73-05-02 | Repudiation | unreadable balance reported as zero or free | high | mitigate | `test_cost_guard.py:271,285` unknown ≠ insufficient ≠ zero; `backendStatusCredits.test.mjs:81` `apollo.credits === null` | closed |
| T-73-05-03 | Tampering | under-stated cost → overspend | high | mitigate | `git diff a662ec7c..HEAD -- cost_guard.py` empty (no rate lowered); `test_write_grant.py:756-768` contact-upload figures equal the preview's on all 3 fields | closed |
| T-73-05-04 | Spoofing | third-party error body parsed as a balance | medium | mitigate | `backendStatusCredits.test.mjs:29,81,98-100` Apollo 403 → unknown, never a number, never `ok`/`not_configured` | closed |
| T-73-06-01 | Information Disclosure | `Build Create Failure Row` parsing an n8n HTTP error object | high | mitigate | `_createFailureReason()` reads message/description/statusCode only + fixed fallback; `ingestCreateErrorLane.test.mjs:98,129` synthetic `Authorization: Bearer …` never reaches the row | closed |
| T-73-06-02 | Tampering | positional pairing mis-associating after a mid-batch rejection | high | mitigate | identity-ladder join in `pairCreateOutcome.js:57-66,107-134`; `create_outcome: "refused"` on uncomputable key or collision | closed |
| T-73-06-03 | Elevation of Privilege | new lane output as a second write path | high | mitigate | `HubSpot Create` fed only by `HubSpot Create Write Gate IF[out0]`; error out1 → carry merge → pair → failure row → response merge (reporting only); `HubSpot Associate Company` fed only by `Build Association Request`; `writeGateShape.test.mjs` unchanged across the phase, 29/29 | closed |
| T-73-06-04 | Tampering | rejected write presenting as success | high | mitigate | `HubSpot Create` = `continueErrorOutput` (distinct output), `HubSpot Update` = no `onError`; `ingestCarryMerge.test.mjs:193-206` pins exactly 2 output branches; `ingestCreateErrorLane.test.mjs:133-138` rejected row never `create`/`associated` — see audit note 1 | closed |
| T-73-06-05 | Denial of Service | starved or double-firing Merge on a healthy batch | high | mitigate | `Create Carry Merge` 3 inputs, one producer each; `Ingest Merge Response` input 5 ← `Build Create Failure Row` alone; `ingestCreateErrorLane.test.mjs:141-181` `starvedWithData(trace) == []`, no row lost, failure-row node runs once | closed |
| T-73-07-01 | Elevation of Privilege | deploying an armed body | high | mitigate | all 5 committed bodies `ALLOW_HUBSPOT_{RECORD_WRITES,CREATE,REVIEW_WRITES}="false"`; `bounce_n8n_workflows.py:57-70,96` exits 1 unless every flag reads `"false"`; `deploy_n8n_workflows.py:489` plain deploy never arms; `73-UAT.md:42,229` operator read-back | closed |
| T-73-07-02 | Tampering | deploying a body not what the builder produces | high | mitigate | auditor re-ran `scripts/build_cloud_workflows.py`: `git diff -- n8n/` empty | closed |
| T-73-07-03 | Tampering | stored PUT that never reloads | high | mitigate | `bounce_n8n_workflows.py:58-66,82` compares live node count + `executionOrder == "v1"` per workflow, non-zero exit on mismatch; `73-UAT.md:25,229` | closed |
| T-73-07-04 | Repudiation | green attempt 3 read as live proof of the create-error lane | medium | mitigate | `73-UAT.md:125-126` lane recorded "NOT exercised … offline-proven only, never tagged observed-live"; CLAUDE.md §13.0.1 `[documented]` per D-73-19 | closed |
| T-73-07-05 | Information Disclosure | credential echoed into the gate record | medium | mitigate | `73-07-PLAN.md:204,210,216,224` credential commands in `!` env-loading form; 0 credential values in PLAN/SUMMARY/UAT | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-73-01 | T-73-02-03 | F-E1 changes only the serialization of an already-approved value; the review write gate, allowlist and disarmed flags are untouched and regeneration is zero-diff on them | planner (73-02 `<threat_model>`), confirmed by audit | 2026-09-18 |
| AR-73-02 | T-73-03-05 | D-73-20: when the IN search returns two companies the lane takes `results[0]` preferring the bare-domain hit and names both ids in the reason — the same tolerance the lane already has for exact-name collisions; the choice is auditable, never silent | operator ruling D-73-20 (73-CONTEXT.md), confirmed by audit | 2026-09-18 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-18 | 30 | 30 (28 mitigated + 2 accepted) | 0 | gsd-security-auditor (opus), orchestrated by Claude Fable 5.1 |

### Audit notes (register-text inaccuracies — recorded, not blocking, no todo per CLAUDE.md §31)

1. **T-73-06-04's third clause misdescribes its own guard.** No grep asserts "regular-continue
   appears nowhere in the generated ingest body", and such a grep could not pass:
   `wf_contact_ingest_cloud.json` legitimately carries `continueRegularOutput` on 5 READ nodes
   (`Verify Emails (batch)`, `HubSpot Search by Email`, `HubSpot Contact History`,
   `HubSpot Company Search by Domain`, `HubSpot Company Search by Name`). The real invariant is
   the BUG 11 rule — WRITE nodes never get it — and it holds (`HubSpot Create` =
   `continueErrorOutput`, `HubSpot Update` = no `onError` key). Residual: no test pins the
   ingest `HubSpot Create.onError === "continueErrorOutput"` literal;
   `tests/test_write_node_transport.py` covers the enrichment lane only. A structural pin
   mirroring that file for the ingest lane is the natural follow-up when that lane is next touched.
2. **T-73-02-02's "unthrottled fourth node" claim is weaker than stated.**
   `ingestSearchThrottle.test.mjs:25` filters on `parameters.options.batching.batch`, so it
   derives the THROTTLED set, not the SEARCH set — a fourth search node added without
   throttling leaves the count at 3 and passes. The 400 ms interval itself is pinned correctly.
3. **T-73-01-01 scope.** Pre-phase fixtures `exec_12354`–`12358` carry the header NAME (older
   key-by-key scrub, values redacted, pinned by `v1RuntimeRecordings.test.mjs`); phase-73
   fixtures carry neither name nor value. No secret value in any committed fixture; no header
   value was printed during the audit.

Test evidence at audit time (commit `759d023b`): 345 plugin pytest across the 6 cited files;
46 node tests across the 8 cited files; `writeGateShape` 29/29, `ingestCarryMerge` 3/3,
`test_write_node_transport` 9/9. Full suite the same day: py 4993 passed / 154 skipped,
node 1218 / 0.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-18
