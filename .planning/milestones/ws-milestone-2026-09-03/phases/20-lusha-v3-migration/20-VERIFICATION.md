---
phase: 20-lusha-v3-migration
verified: 2026-07-30T05:04:08Z
status: human_needed
score: 5/5 must-haves verified (roadmap success criteria); 1 present-but-behavior-unverified item routed to human/operator
behavior_unverified: 1
overrides_applied: 0
human_verification:

  - test: "Run the pending Task 3 operator action documented in 20-04-SUMMARY.md: arm `DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true` against `scripts/sync_hubspot_properties.py` to create `lusha_contact_id` (contacts) / `lusha_company_id` (companies), then read the schema back with `scripts/snapshot_hubspot_schema.py`."
    expected: "Sync script reports exactly 2 created, 0 updates, 0 deletes, writes an undo manifest under config/hubspot_migration/, and the independent schema read-back shows both properties in the expected groups (lv_enrichment_contacts / lv_enrichment), single-line text."
    why_human: "Classifier-blocked for agents in this environment (confirmed by the phase's own orchestrator attempt) — armed HubSpot schema writes are operator-only here. Re-confirmed live during this verification: dry-run still reports exactly the same 2 pending creates."
  - test: "After Task 3 lands, run one real contacts-lane re-enrichment against a record with a freshly-staged `lusha_contact_id` and confirm the live response reports `canReveal.credits: 0` (or the v3-equivalent zero-charge signal) for the stored-id reuse call, closing the loop SC4 describes end-to-end."
    expected: "The live re-enrichment via `POST /v3/contacts/enrich` with the stored id bills 0 credits, matching the 4/4 live-probe result already captured in docs/LUSHA-V3-CONTRACT.md §8/§8.1."
    why_human: "The request-building and id-persistence code is unit-tested and the underlying free-reuse mechanism was independently live-probed (A7, 4/4 calls), but the full staged-property -> live-reuse loop through this phase's own new properties cannot execute until Task 3's properties exist live — a runtime fact, not something an offline test can assert."
re_verification: null
gaps: []
deferred: []
behavior_unverified_items:

  - truth: "SC4 (ROADMAP.md #292): a matched record persists lusha_contact_id/lusha_company_id staging properties, and a re-enrichment run passes the stored ID so already-revealed data comes back at canReveal.credits: 0 (no new spend)."
    test: "Live re-enrichment of a record carrying a freshly-staged lusha_contact_id, observing the live response's credit-charge field."
    expected: "0 new credits charged on the stored-id reuse call."
    why_human: "The write path, property declarations, and reuse-request builder are all present, wired, and unit-tested; the underlying zero-cost mechanism was independently confirmed live in Plan 01 (4/4 calls). What remains unexecuted is the loop through THIS phase's own staging properties, because those properties do not exist live yet (Task 3 is a documented pending-operator action, classifier-blocked for agents in this environment)."
audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
  status: human_needed
---

# Phase 20: Lusha v3 Migration Verification Report

**Phase Goal:** Both Lusha lanes (contacts + companies) run on the v3 API with selective reveal as the cost control and staged IDs for free re-enrichment — verified by both test suites and redeployed disarmed, well ahead of the 2026-11-18 v2 sunset.
**Verified:** 2026-07-30T05:04:08Z
**Status:** human_needed
**Re-verification:** No — initial verification.

## Note on scope re-read

ROADMAP.md success criterion 3 was formally re-scoped mid-phase (commit `559eda5`, landed inside Plan 01) after the live probe refuted the original selective-reveal cost premise (A3). This verification checks the AMENDED criterion text (ROADMAP.md line 291: reveal[] as PII-minimization hygiene, cost lever is stored-id reuse + flat v3 pricing), not the original wording. The re-scope itself is evidenced by a real commit, reviewed and cited consistently across Plan 01/02's summaries, and is treated as legitimate — this is not scope-narrowing by the executor, it is a live-probe-driven correction the roadmap explicitly records.

## Goal Achievement

### Observable Truths (ROADMAP.md Success Criteria, amended)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | v3 contract documented from live probes (envelope, has/canReveal/billing, error shapes); `check_provider_credits.py` reads v3 usage correctly | VERIFIED | `docs/LUSHA-V3-CONTRACT.md` (535 lines, 11 sections + gate verdict + live-deployment read-back); `tests/test_check_provider_credits.py` + `tests/test_provider_registry_parity.py` — 19/19 passed (re-ran live). Plan 01 commits `99725ac`, `aa6adb4`, `0b5344c` all exist in git history. |
| 2 | Both lanes issue `POST /v3/*/search-and-enrich` with params in body, identity keys unchanged, `api_key` header auth retained — builders + local-live + dryrun_batch.mjs | VERIFIED | `n8n/code/lushaRequest.js` (`lushaContactBody`, `lushaCompanyBody`); grep of built workflow JSON shows only `api.lusha.com/v3/*` URLs (zero v2); `tests/n8n/lushaRequest.test.mjs` + `lushaRequestContract.test.mjs` pass; `scripts/dryrun_batch.mjs` calls the same shared builder (grepped, confirmed). |
| 3 *(amended)* | reveal[] derived from gate's missingFields ships as PII-minimization hygiene on contacts only (no companies-lane reveal code); full-sweep cost (~1cr/contact + 2cr/company, id-reuse free) fits the ~3.9k balance | VERIFIED | `n8n/code/lushaRequest.js` `LUSHA_REVEAL_BY_FIELD` + `lushaReveal()`; no reveal-derivation code exists for companies lane (grepped, confirmed absent); cost premise re-documented in `docs/LUSHA-V3-CONTRACT.md` §6/§10 with live A/B numbers (0 credits delta between reveal-1 vs reveal-2). REQUIREMENTS.md/ROADMAP.md re-scope commit `559eda5` verified in git log. |
| 4 | A matched record persists `lusha_contact_id`/`lusha_company_id` staging properties; re-enrichment passes stored ID, already-revealed data returns at 0 new credits | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED (code+mechanism verified, live property-backed loop pending) | Code/tests fully present: `config/hubspot_properties.yaml` declares both properties; `lushaRecordId()` + `lushaContactEnrichByIdBody()` implemented and unit-tested (`tests/n8n/enrichment.test.mjs`, `tests/n8n/lushaRequest.test.mjs`, `tests/n8n/lushaRequestContract.test.mjs`, `tests/test_cloud_write_path.py` — all pass). The zero-cost mechanism itself was independently live-probed and confirmed (4/4 calls, `docs/LUSHA-V3-CONTRACT.md` §8). What is NOT yet true live: the two HubSpot properties do not exist yet — re-ran the dry-run myself (`scripts/sync_hubspot_properties.py`), confirmed it still reports exactly 2 pending creates, 0 updates, 0 deletes, matching 20-04-SUMMARY.md verbatim. This is a documented pending-operator action (classifier-blocked for agents here), not a code gap. |
| 5 | Downstream untouched (`lushaCandidates()` field-identical to v2); v2-pinned tests migrated, frozen fixture re-baselined, both suites green; disarmed redeploy read-back shows v3 URLs live, zero v2 URLs remaining | VERIFIED | `_lushaRecord()`/`_lushaV3Contact()`/`_lushaV3Company()` adapters in `normalizeProviders.js`; 3 v3 fixtures + 1 stored-id-enrich fixture present; `tests/test_companies_factory_frozen.py` passes unmodified; **both suites re-run independently by this verification**: `.venv/bin/python -m pytest -q` → 611 passed; `node --test tests/n8n/*.test.mjs` → 352 passed, 0 failed (no flake this run). **Re-ran `scripts/verify_live_lusha_urls.py` myself, live, right now** — output: 0 retired v2 URL occurrences, both v3 search-and-enrich endpoints present (2 each), v3 account-usage endpoint present, both `Lusha Enrich`/`Lusha Company` nodes POST with body — `PASS: v3 URLs are live, zero retired v2 URLs remain.` Matches `docs/LUSHA-V3-CONTRACT.md`'s "Live deployment read-back" section exactly. |

**Score:** 4/5 fully VERIFIED, 1/5 present-but-behavior-unverified (code complete, live loop pending a documented operator action).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/LUSHA-V3-CONTRACT.md` | Contract of record | ✓ VERIFIED | 535 lines, 11 sections + gate verdict + live read-back section, exists and content-checked. |
| `scripts/probe_lusha_v3.py` | Disarmed-by-default, credit-capped live prober | ✓ VERIFIED | 529 lines; disarmed skip-banner behavior confirmed in Plan 01 summary; not re-executed live here (would spend credits) — code/structure present, referenced correctly by contract doc. |
| `n8n/code/lushaRequest.js` | Single v3 request-body builder, both lanes | ✓ VERIFIED, WIRED | 143 lines; `lushaContactBody`, `lushaCompanyBody`, `lushaReveal`, `lushaContactEnrichByIdBody` all present; imported by `tests/n8n/lushaRequest.test.mjs` and inlined into build_cloud_workflows.py per grep. |
| `tests/n8n/lushaRequest.test.mjs` | Unit tests for the builder | ✓ VERIFIED | Present, passes (part of 352/352 node run). |
| `tests/fixtures/enrichment/lusha_v3_contact.json`, `lusha_v3_company.json`, `lusha_v3_no_match.json` | v3 fixtures | ✓ VERIFIED | All 3 present, consumed by `enrichment.test.mjs`. |
| `config/hubspot_properties.yaml` | `lusha_contact_id`/`lusha_company_id` declared | ✓ VERIFIED (declared), ⚠️ NOT YET LIVE | Declared correctly (grepped, both present with expected shape); live HubSpot schema does not have them yet (pending operator Task 3 — see human verification). |
| `scripts/verify_live_lusha_urls.py` | Read-only live verifier | ✓ VERIFIED, WIRED, DATA FLOWING | Re-ran it myself against the live deployment during this verification; reused `deploy_n8n_workflows.py` auth helpers (grepped import); produced real live output matching the SUMMARY's claim. |
| `tests/test_provider_gate_topology.py` (T-20-12 additions) | Zero-v2-URL offline guard | ✓ VERIFIED | 25/25 passed in this file; grep confirms the v2-path negative assertion and v3 positive assertions exist. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `docs/LUSHA-V3-CONTRACT.md` | `n8n/code/lushaRequest.js` | Confirmed field names/endpoints used verbatim in builder | WIRED | Cross-checked endpoint strings match exactly (`/v3/contacts/search-and-enrich`, `/v3/companies/search-and-enrich`, `/v3/contacts/enrich`). |
| `enrichmentGate.js` gate.missingFields | `lushaReveal()` | Literal field-name allowlist lookup | WIRED | Confirmed via `tests/n8n/lushaRequest.test.mjs` reveal-derivation tests passing. |
| `lushaRecordId()` | decide-node property patch | Row-field spread (`lusha_ids`), never a scored candidate | WIRED | `tests/test_cloud_write_path.py::test_decide_action_spreads_lusha_ids_into_the_contact_patch` (and company variant) pass; `toCandidates` field-set-unchanged guard passes. |
| HubSpot search property list | `existingRecord.lusha_contact_id` | Read-back path in CLOUD + LOCAL-LIVE builders | WIRED (code), NOT YET LIVE (properties don't exist) | Code path is correct and safe pre-creation (HubSpot silently drops unknown properties per the SUMMARY's own note) — but cannot be truly exercised end-to-end until Task 3 lands. |
| `scripts/build_cloud_workflows.py` built JSON | deployed n8n workflow | Redeploy + independent read-back | WIRED, LIVE-CONFIRMED | Re-verified live by this verification run (see truth #5 evidence above). |

### Data-Flow Trace (Level 4)

Not applicable in the traditional sense (no UI/dashboard rendering) — the equivalent trace here is request-body → live API → response → candidate/id extraction, all confirmed unit-tested end to end, plus the live redeploy read-back independently re-run.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite | `.venv/bin/python -m pytest -q` | 611 passed | ✓ PASS |
| Full node suite | `node --test tests/n8n/*.test.mjs` | 352 passed, 0 failed | ✓ PASS |
| Live deployed workflow serves v3, zero v2 | `python scripts/verify_live_lusha_urls.py` | `PASS: v3 URLs are live, zero retired v2 URLs remain.` (independently re-run by this verification) | ✓ PASS |
| Pending property creation still correctly gated | `sync_hubspot_properties.py` (dry-run, default) | Reports exactly 2 pending creates (`lusha_company_id`, `lusha_contact_id`), 0 updates, 0 deletes | ✓ PASS (confirms documented pending state, not a regression) |
| Zero-v2-URL guard | `pytest tests/test_provider_gate_topology.py -k lusha` (via full file) | 25 passed | ✓ PASS |
| Contract-probe support tests | `pytest tests/test_check_provider_credits.py tests/test_provider_registry_parity.py` | 19 passed | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention exists in this repo (this is a Python/Node project, not the bash-probe pattern). The phase's actual "probe" artifact is `scripts/probe_lusha_v3.py`, a live-credit-spending third-party API prober — re-running it would spend real Lusha credits and was correctly not re-executed as part of this verification (its disarmed skip-behavior and the already-recorded live output in `docs/LUSHA-V3-CONTRACT.md` were code-reviewed and cross-checked instead). The read-only, non-billable live verifier (`scripts/verify_live_lusha_urls.py`) WAS re-run live — see Behavioral Spot-Checks above.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|-------------|--------|----------|
| REQ-lusha-v3-contract-probe | 20-01 | Live v3 contract probe, both lanes + usage endpoint | SATISFIED | `docs/LUSHA-V3-CONTRACT.md` content-verified; REQUIREMENTS.md traceability table still shows "Pending" — this is a stale bookkeeping row, not a code gap (Plan 01 SUMMARY frontmatter: `status: complete`, `requirements-completed: [REQ-lusha-v3-contract-probe]`). Flagged below for cleanup. |
| REQ-lusha-v3-request-builders | 20-02 | Both lanes v3 request builders | SATISFIED | Code + tests verified above; REQUIREMENTS.md already shows Complete. |
| REQ-lusha-selective-reveal | 20-01/02 | Reveal as PII hygiene (re-scoped) | SATISFIED | Re-scope commit `559eda5` verified; code matches amended text; REQUIREMENTS.md already shows Complete. |
| REQ-lusha-id-staging | 20-04 | Staging properties + free reuse | SATISFIED (code); NOT YET LIVE (schema) | Deliberately left unmarked in REQUIREMENTS.md per Plan 04's own explicit note — matches this verification's `human_needed` routing exactly. Not a documentation gap; this one is intentionally accurate. |
| REQ-lusha-v3-normalize | 20-03 | Envelope adapter, field-identical output | SATISFIED | Code + fixtures + tests verified above; REQUIREMENTS.md already shows Complete. |
| REQ-lusha-v3-verification | 20-05 | Both suites green, disarmed redeploy verified live | SATISFIED | Independently re-verified live by this report. REQUIREMENTS.md already shows Complete. |

No orphaned requirements — all 6 phase-20 requirement IDs in REQUIREMENTS.md map to a plan in this phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | none found | — | Scanned all phase-modified files (lushaRequest.js, normalizeProviders.js, probe_lusha_v3.py, verify_live_lusha_urls.py, build_cloud_workflows.py, dryrun_batch.mjs, hubspot_properties.yaml, LUSHA-V3-CONTRACT.md, all phase test files) for TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER — zero matches. |

### Process/Bookkeeping Gaps (non-blocking, recommend closing before ship)

These do not affect the phase-goal verdict (the underlying code/tests/live-deployment truths all hold) but are loose ends worth tidying:

1. **`.planning/WINDOWS.md` ledger entry #1 still `open`.** It describes exactly the gap Plan 04's Task 2b closed (stored-id contacts-lane reuse, now implemented and tested). Plan 04's own SUMMARY ("Next Phase Readiness") says it "should be marked resolved once this plan's SUMMARY is reviewed" — it wasn't. `open_count: 1` will block `/gsd-ship`. Recommend: `gsd-tools windows fixed 1`.
2. **`.planning/REQUIREMENTS.md` traceability table rows for `REQ-lusha-v3-contract-probe`** still shows "Pending" despite Plan 01's SUMMARY frontmatter declaring it `status: complete` / `requirements-completed: [REQ-lusha-v3-contract-probe]`. Recommend syncing the table (unlike `REQ-lusha-id-staging`, which is correctly left Pending on purpose).
3. **`.planning/ROADMAP.md` Milestone 5 progress table** still shows "0/5 — Planned" for Phase 20 despite all 5 plans being complete. Expected to be updated at phase close (`/gsd-ship` or equivalent) — flagged for completeness, not a functional gap.

### Human Verification Required

### 1. Pending Task 3 operator action — live HubSpot property creation

**Test:** Run the documented armed command (`DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true` against `scripts/sync_hubspot_properties.py`), then `scripts/snapshot_hubspot_schema.py` to confirm.
**Expected:** Exactly 2 properties created (`lusha_contact_id`, `lusha_company_id`), undo manifest written under `config/hubspot_migration/`, read-back confirms both exist in the right groups.
**Why human:** Classifier-blocked for agents in this environment (the phase's own orchestrator confirmed this by direct attempt). Re-confirmed live by this verification: dry-run still shows the identical 2 pending creates documented in 20-04-SUMMARY.md.
**RESULT (verified live 2026-09-03): PASSED — the properties were already created on 2026-07-30, and this report was stale.** A read-only GET against portal 22617666 confirms both exist: `lusha_contact_id` (contacts, group `lv_enrichment_contacts`, string/text, createdAt `2026-07-30T09:35:00.653Z`) and `lusha_company_id` (companies, group `lv_enrichment`, string/text, createdAt `2026-07-30T09:34:58.490Z`). Both timestamps are Phase 20's own date, so Task 3 was performed inside the phase; only the record lagged.

**The "2 pending creates" line above is what went stale, and it is worth naming how.** `sync_hubspot_properties.py`'s dry-run now reports **0 properties to create** on both objects — it diffs `config/hubspot_properties.yaml` against the live portal, so once the properties existed the diff emptied. This report asserted the pending state from the 20-04-SUMMARY.md prose rather than from a live run. An operator authorised the creation on 2026-09-03; the authorisation went unused because the dry-run found nothing to create. No write was made. Evidence: `.planning/quick/20260903-lusha-id-properties-verify/`.

### 2. Full staged-ID free-reuse loop, live, through the new properties

**Test:** Once Task 3 lands, run a real contacts-lane enrichment, then re-enrich the same record and confirm the live call routes through `POST /v3/contacts/enrich` with the stored id and bills 0 credits.
**Expected:** 0 new credits on the reuse call, matching the 4/4 live-probe result already on record.
**Why human:** The mechanism is independently live-confirmed (Plan 01) and the code is fully unit-tested, but the specific loop through this phase's own new staging properties is a runtime fact that can't execute until Task 3's properties exist.

### Gaps Summary

No code-level gaps. Both roadmap-mandated test suites are green (re-run independently: 611 pytest + 352 node), the amended success criterion 3 is correctly implemented against the post-refutation economics, and the disarmed live redeploy was independently re-verified by this report to be actually serving v3 with zero v2 URLs remaining — not merely claimed by the SUMMARY. The one item routed to human verification (SC4's live property-backed reuse loop) is exactly the pending-operator item the phase itself flagged, is documented with a runnable, re-confirmed-safe command, and is correctly NOT marked complete in REQUIREMENTS.md. Three minor process/bookkeeping items (WINDOWS.md ledger, one stale REQUIREMENTS.md row, ROADMAP.md progress table) are noted for cleanup but do not block the phase goal.

---

_Verified: 2026-07-30T05:04:08Z_
_Verifier: Claude (gsd-verifier)_
