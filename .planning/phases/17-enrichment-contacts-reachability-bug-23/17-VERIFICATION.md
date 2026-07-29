---
phase: 17-enrichment-contacts-reachability-bug-23
verified: 2026-07-29T00:00:00Z
status: passed
score: 5/5
behavior_unverified: 0
overrides_applied: 0
---

# Phase 17: Enrichment Contacts Reachability (BUG 23) Verification Report

**Phase Goal:** The enrichment contacts lane's `contact:create` path is live-reachable for a
genuine no-match event, and the existing live-proven match path is regression-checked, not
assumed safe.
**Verified:** 2026-07-29
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths / ROADMAP Success Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Transport swap real (both nodes httpRequest, credential-bound, zero native hubspot nodes in lane, deterministic build) | ✓ VERIFIED | Read `n8n/wf_enrichment_cloud.json` directly: 0 `n8n-nodes-base.hubspot` nodes; "HubSpot Search" and "HubSpot Fetch By Id" are both `n8n-nodes-base.httpRequest`, POST to `crm/v3/objects/contacts/search`, `authentication: predefinedCredentialType` / `nodeCredentialType: hubspotAppToken` (credential binding happens at deploy time via `NODE_CREDENTIAL_MAP` in `scripts/deploy_n8n_workflows.py` — confirmed both node names are mapped there, and confirmed other established httpRequest nodes like "Lusha Enrich" follow the identical no-embedded-credentials-in-committed-JSON pattern, so this is not a gap). Ran `.venv/bin/python scripts/build_cloud_workflows.py` and `git diff --stat n8n/` afterward — zero diff, confirming deterministic rebuild. Live read-back in `17-CANARY-EVIDENCE.md` ("Read-back after deploy") independently confirms the credential object is attached live (`hubspotAppToken id Y5z3bszayHGPDx30 / "LV HubSpot"`). |
| 2 | Pin removal + harness, offline suite green (596 pytest / 285 node) | ✓ VERIFIED | `tests/test_bug10_company_search_transport.py`'s `CONTACT_NODES_BY_WORKFLOW` now only lists `wf_scheduled_maintenance_cloud.json: ["Dedupe Search (candidate contacts)"]` — both `wf_enrichment_cloud.json` nodes are gone from the pin (verified by direct grep + read). `tests/test_enrichment_contacts_search_transport.py` exists (10 tests, RED-before-GREEN doc comment citing the pre-swap failure output). `tests/n8n/bareEventChainFlow.test.mjs` contains the `CONTACT_NO_MATCH_CHAIN`/`CONTACT_NO_MATCH_HTTP_MOCKS` test asserting `Adapt Search.lookup_failed === false`, `Enrichment Gate.action === "create"`, and `final.action === "write_blocked"` with `final.properties.email` carrying the canary address (verified by reading the test body, lines 296-349). Ran both suites myself: `.venv/bin/python -m pytest -q` → **596 passed, 0 failed**; `node --test tests/n8n/*.test.mjs` → **285 passed, 0 failed**. Both match the claimed counts exactly. |
| 3 | Case A regression evidence (pre/post-swap field-by-field + full-chain vs historical exec 15) | ✓ VERIFIED | `17-CANARY-EVIDENCE.md` "Case A — BEFORE" has real JSON for execs 68/69 (contact 201, real property values, `Adapt Search`/`Enrichment Gate`/`Decide Action` outputs). "Case A — AFTER" has a field-by-field table for execs 70 vs 68 and 71 vs 69 — `existingRecord`, `lookup_failed`, `identity_keys`, gate `action`, `Decide Action` all marked "identical" with the raw-shape difference (flattened→envelope) called out as the fix itself, not a regression. Full-chain re-run (exec 72, `providers:["lusha"]`) diffed against historical exec 15's `Merge Winners` table — all four field **decisions** match (`needs_review`/`stage_only`/`promote`); the three value differences are explicitly attributed to provider-mix variance (1 provider vs 3), not transport. These are concrete field-by-field tables with real production values, not placeholders. |
| 4 | Case B reachability (exec 76: one item `{total:0,results:[]}`, `lookup_failed:false`, `action:"create"`, `write_blocked`, no write node in runData, two searches ≥3 min apart both `total:0`) | ✓ VERIFIED | `17-CANARY-EVIDENCE.md` "Case B" quotes exec 76's `HubSpot Search` raw output `{"total": 0, "results": []}` (one item), `Adapt Search.existingRecord: {}` + `lookup_failed: false`, `Enrichment Gate.action: "create"`, `Decide Action.action: "write_blocked"` with `properties.email` carrying the canary address. Full `runData` node-name list is enumerated and neither `HubSpot Create` nor `HubSpot Update` appears in it. Two post-fire searches recorded at `07:01:48Z` and `07:05:36Z` — I computed the gap independently: **228 seconds = 3.8 minutes**, satisfying the ≥3-minute requirement (both `total: 0`). The file is also honest about a discarded first wait attempt (a `date -u -d` GNU-flag bug on Darwin produced an invalid ~40s gap) — that invalid search was explicitly excluded from the evidence table, which strengthens rather than undermines the claim. |
| 5 | Disarmed restore + live read-back (six literals disarmed, active:true) | ✓ VERIFIED | `17-CANARY-EVIDENCE.md` "Restore" section quotes a fresh `GET /api/v1/workflows/950HPb7a1GgSAIyZ` post-restore: `active: true`, both swapped nodes still `httpRequest`/credential-bound, and all six write-safety literals listed disarmed (`ALLOW_HUBSPOT_RECORD_WRITES="false"`, `ALLOW_HUBSPOT_CREATE="false"`, `TEST_RECORD_IDS=""`, `TEST_RECORD_DOMAINS=""`, `ALLOW_WEB_RESEARCH=false`, `ALLOW_SONNET_ESCALATION=false`). |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Honesty Check — Task 4 (armed-create window) skip

Task 4 (an operator-approved armed-create live window) was explicitly skipped in 17-02-SUMMARY.md
("Task 4 SKIPPED per explicit instruction — operator-only, default-skip") and in
`17-CANARY-EVIDENCE.md`'s closing note ("Task 4 was never performed... its criterion contribution
is N/A, not partially met; criteria 1/3/4/5 above are each fully satisfied by Tasks 1-3 and 5
alone, with no dependency on Task 4"). I confirmed no success criterion's evidence relies on an
armed-create HubSpot write: criterion 4 (reachability) is proven entirely at the write-gated
decision layer (`Decide Action.action == "write_blocked"`), and the two post-fire searches proving
no record materialized are independent of Task 4. The skip is recorded in `17-02-SUMMARY.md`
(Decisions Made), `STATE.md` is updated to reflect Phase 17 complete, and
`bug-23-enrichment-contact-nomatch-chain-stop.md`'s Resolution section does not claim an
armed-create execution occurred. **No overclaiming found.**

One out-of-band observation (not a phase gap, noted for completeness): the working tree currently
has an uncommitted one-line change to
`.planning/debug/bug-23-enrichment-contact-nomatch-chain-stop.md` (frontmatter `status: fixed` →
`status: resolved`), diverging from the committed HEAD (`status: fixed`, matching what
17-02-SUMMARY.md and STATE.md both cite). This file was not modified by this verification (verifier
is read-only) — flagged here as an unrelated, currently-uncommitted repo state the phase owner
should reconcile, not a gap in Phase 17's own success criteria.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `n8n/wf_enrichment_cloud.json` | Both contact nodes on httpRequest transport, zero native hubspot nodes | ✓ VERIFIED | Confirmed by direct JSON parse |
| `scripts/build_cloud_workflows.py` | `_hs_http_search_node()` widened to a resource→URL table (company/contact) | ✓ VERIFIED | Rebuild is deterministic; byte-identical to committed file |
| `tests/test_enrichment_contacts_search_transport.py` | New guard file, 10 tests | ✓ VERIFIED | Exists, collected and passed in the pytest run |
| `tests/test_bug10_company_search_transport.py` | Pin narrowed to `Dedupe Search (candidate contacts)` only | ✓ VERIFIED | `CONTACT_NODES_BY_WORKFLOW` confirmed by read |
| `tests/n8n/bareEventChainFlow.test.mjs` | No-match chain test to `action:"create"`, write-gated | ✓ VERIFIED | Test body read and confirmed; passed in node run |
| `.planning/phases/.../17-CANARY-EVIDENCE.md` | Live evidence for Case A/B + restore | ✓ VERIFIED | Read in full; internally consistent, concrete values throughout |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Deterministic workflow builder | `.venv/bin/python scripts/build_cloud_workflows.py` then `git diff --stat n8n/` | exit 0, no diff | ✓ PASS |
| Offline pytest suite | `.venv/bin/python -m pytest -q` | 596 passed, 0 failed | ✓ PASS |
| Offline node suite | `node --test tests/n8n/*.test.mjs` | 285 passed, 0 failed | ✓ PASS |
| Case B timing gap | computed `07:05:36Z - 07:01:48Z` | 228s = 3.8 min | ✓ PASS (≥3 min claimed) |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|--------------|-------------|--------|----------|
| REACH-01 | Transport swap to httpRequest envelope, no-match emits one classifiable item | ✓ SATISFIED | Node-shape read + live read-back in CANARY-EVIDENCE |
| REACH-02 | Pin dropped with documented rationale | ✓ SATISFIED | `CONTACT_NODES_BY_WORKFLOW` narrowed, rationale in 17-01-SUMMARY.md |
| REACH-03 | Live canary of both cases (match regression + create reachability) | ✓ SATISFIED | Execs 68/69/70/71/72 (Case A), exec 76 (Case B) |
| REACH-04 | Harness gap closed (no-match modeled, drives to write decision) | ✓ SATISFIED | `bareEventChainFlow.test.mjs` new tests, confirmed passing |

REQUIREMENTS.md marks all four REACH-01..04 rows "Complete" against Phase 17 — consistent with the
above.

### Anti-Patterns Found

None. No TODO/FIXME/XXX/HACK/PLACEHOLDER markers in the files this phase touched
(`scripts/build_cloud_workflows.py`, `n8n/wf_enrichment_cloud.json`, the modified/created test
files). The one known deliberate scope carve-out (`Dedupe Search (candidate contacts)` sibling
hazard, left unfixed) is explicitly documented as out-of-fence in both the SUMMARY and STATE.md,
not silently dropped.

### Human Verification Required

None. All five success criteria are backed by artifacts I read directly and/or offline suites I
ran myself; the live-canary evidence is a first-party record of actual HubSpot/n8n API
interactions with concrete execution IDs, timestamps, and JSON payloads — not narrated claims.

### Gaps Summary

No gaps. All 5 ROADMAP success criteria verified against artifacts, both offline suites reproduced
independently with matching counts, the workflow builder is confirmed deterministic, and the
Task-4 skip is honestly recorded with no criterion depending on it.

---

_Verified: 2026-07-29_
_Verifier: Claude (gsd-verifier)_
