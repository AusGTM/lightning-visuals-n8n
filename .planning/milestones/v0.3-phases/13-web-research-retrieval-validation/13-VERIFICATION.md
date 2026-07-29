---
phase: 13-web-research-retrieval-validation
verified: 2026-07-21T04:08:20Z
status: passed
score: 7/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification: No — initial verification
---

# Phase 13: Web Research Retrieval & Validation Verification Report

**Phase Goal:** `lv_org_type` and `lv_produces_content` resolve from citable web sources
(Anthropic native `web_search_20250305`), or not at all — via a vocabulary-safe,
per-field-evidenced validation layer that feeds the existing evidence-gated
`mergeCompanies` unchanged.

**Verified:** 2026-07-21T04:08:20Z
**Status:** passed
**Re-verification:** No — initial verification

All 11 requested checks were run directly against the codebase (not read from
SUMMARY.md). One deliberate-break guard (Task 4's failure-skip proof) was
independently re-executed and restored byte-identical, per instructions.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 7 former-xfail acceptance tests pass unmarked; full suite green | ✓ VERIFIED | `.venv/bin/pytest -q` → `139 passed, 1 warning` (pre-existing httpx deprecation), 0 xfailed/xpassed/failed. `grep -n "xfail" tests/test_web_research_spec.py` shows only the now-unused `unbuilt` marker definition (line 23) — none of the 7 target `def` lines (`test_oc1_evidence_is_keyed_per_field`, `test_oc2_oc3_output_values_are_canonical`, `test_oc4_malformed_output_does_not_raise`, `test_ts1_ts2_thin_evidence_yields_null_not_false`, `test_ts3_false_requires_evidence_url`, `test_at2_off_vocabulary_from_model_becomes_unknown`, `test_er1_entity_resolution_present`) carry a decorator. |
| 2 | TS-2/TS-3 semantics correct: gate is evidence-presence, not confidence | ✓ VERIFIED | `src/taxonomy.py:132`: `if produces_content is False and not evidence_by_field.get("lv_produces_content"): produces_content = None`. No confidence variable referenced anywhere in the function. Mirrored in `n8n/code/webResearch.js:30`. Test bodies (`test_ts1_ts2_...`, `test_ts3_...`) confirmed to assert exactly this by direct read, not just marker removal. |
| 3 | AT-2 off-vocabulary → "unknown" + needs_review, via Phase-12 normalizers, no second hand-rolled vocabulary | ✓ VERIFIED | `validate_research_output` calls `normalize_org_type_result` (Phase-12 function, `src/taxonomy.py:77`); JS twin `require("./taxonomy")` → `normalizeOrgTypeResult`. `grep -rn "governing_body_league" n8n/code/*.js \| grep -v taxonomy.generated.js` → only hit is an explanatory comment in `taxonomy.js`, not a literal list. `test_at2` confirms `lv_org_type == "unknown"` and `needs_review is True` for an off-vocab value. |
| 4 | JS/Python parity: 51 node tests pass, driven by shared fixture | ✓ VERIFIED | `node --test tests/n8n/*.test.mjs` → `pass 51, fail 0`, including `webResearch: GENUINE parity vs Python src.taxonomy ...` and the 4 `webResearchFailure`/`researchCandidateFromHttpItem` tests. `tests/n8n/parity.test.mjs:340` reads `tests/fixtures/research_validation_cases.json` via `pyResearch(...)`, the single shared case table. |
| 5 | mergeCompanies.js byte-identical across Phase 13 | ✓ VERIFIED (see note) | `git diff acca773..HEAD -- n8n/code/mergeCompanies.js` (acca773 = the Phase-13 plan commit, the correct pre-phase baseline) is empty. **Note:** the reference commit given in the task instructions, `360d7bc`, is actually the commit immediately *before* Phase 12 started, not the pre-Phase-13 baseline; diffing from `360d7bc` surfaces Phase 12's legitimate, already-verified `TX-4` change (commit `7b1e5ec`, evidence-gated org-type list now sourced from generated taxonomy). That change predates Phase 13 and is out of this phase's scope. Confirmed empty from the actual pre-Phase-13 commits (`acca773` and `e0d1d5d`). |
| 6 | Workflow containment: only wf_enrichment_local_live.json changed; only Merge Company's jsCode changed; contacts branch untouched | ✓ VERIFIED | Node-diff script (Python, comparing `git show acca773:<file>` vs working tree) over all 5 workflow JSONs: `wf_contact_ingest_cloud.json`, `wf_contact_ingest_local.json`, `wf_enrichment_cloud.json`, `wf_enrichment_local.json` → `changed=[] added=[]` (byte-identical). `wf_enrichment_local_live.json` → `changed=['Merge Company']`, `added=['Research Trigger Gate','IF Research Needed','Build Research Request','Claude Web Research','Validate Research Output']`. Contacts branch is untouched by construction (no contact-branch node appears in any changed/added list). |
| 7 | Rebuild determinism | ✓ VERIFIED | `.venv/bin/python scripts/build_cloud_workflows.py` run fresh, then `git diff --exit-code n8n/` → exit 0 (clean). |
| 8 | Failure-skip proof re-run with a live deliberate break | ✓ VERIFIED | `tests/n8n/webResearchFailure.test.mjs` covers all three named failure shapes (n8n execution-error item, empty/missing `content`, Anthropic HTTP error body) plus a malformed-text control case and a "good response still matches" control. I independently stripped the guard + try/catch from `researchCandidateFromHttpItem` in `n8n/code/webResearch.js` (removed the `!item \|\| item.error \|\| !Array.isArray(item.content)` short-circuit and the surrounding try/catch, forcing an unconditional `extractFinalJson`/`toProviderResult` call). Re-ran the test: 3 of 4 tests genuinely failed with named `SyntaxError`s pointing at the exact broken line, confirming the guard is load-bearing, not a no-op. Restored via `cp` from a scratch backup (md5 confirmed identical: `f938b960cb4577422f963554de59d82a` before/after); `git diff --exit-code n8n/code/webResearch.js` → clean; full re-run of `node --test tests/n8n/*.test.mjs` → 51 passed. |
| 9 | Smoke script exits 0 with no credentials; read-only; exit-2 keyed to evidenced false only | ✓ VERIFIED | `env -u HUBSPOT_PRIVATE_APP_TOKEN -u ANTHROPIC_API_KEY .venv/bin/python scripts/smoke_closed_won_research.py` → prints `skipped (no credentials): ...`, exit 0. `grep -rn "smoke_closed_won_research" tests/` → no matches (never imported by pytest). Read of the full script: HubSpot calls are `hs.search_records` (POST `/crm/v3/objects/deals/search` — a read/search endpoint), `_deal_company_ids` (GET associations v4), `hs.get_record` (GET company) — zero PATCH/PUT/DELETE or object-creation POST anywhere. Exit-2 branch (`return 2`) fires only when `evidenced_false` is non-empty, populated only when `pc is False` post-`validate_research_output` — and per TS-2 (checked above), an unevidenced False is coerced to `None` before this point, so a bare `False` reaching this branch is necessarily evidenced. **Not run with credentials, per instructions.** |
| 10 | AR guards green; api.anthropic.com only research host | ✓ VERIFIED | `.venv/bin/pytest tests/test_architecture_guard.py -q` → `17 passed`. `ALLOWED_HOSTS` in that test includes `"api.anthropic.com", # Haiku / Sonnet / web_search`; the new HTTP node in `scripts/build_cloud_workflows.py:1668` targets exactly `https://api.anthropic.com/v1/messages` — no new host introduced. |
| 11 | No unresolved debt markers in phase-touched files | ✓ VERIFIED | Grepped all 11 phase-touched files for `TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER` (plus lowercase placeholder-language variants). Only hits: (a) the pre-existing, unrelated `unbuilt` xfail marker *definition* (not applied to any of the 7 target tests) in `tests/test_web_research_spec.py`; (b) 24 `XXX` matches in `n8n/wf_enrichment_local_live.json` that are digit-placeholder patterns in phone-normalization comments (`0XXXXXXXXX`, `61XXXXXXXXX` — describing AU phone-number shapes, not debt markers) inlined from `normalizePhone.js`, pre-existing and untouched by this phase. No genuine debt markers found. |

**Score:** 7/7 must-haves verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/schemas.py` | additive `ProviderResult.evidence_by_field` | ✓ VERIFIED | `ProviderEvidence`/`ProviderResult` local-imported and used correctly in `to_provider_result` |
| `src/taxonomy.py` | `validate_research_output`, `to_provider_result` | ✓ VERIFIED | Both present, read directly, semantics match spec (OC-1..4/TS-1..3/AT-2/ER-1) |
| `n8n/code/webResearch.js` | JS twin + `researchCandidateFromHttpItem`/`extractFinalJson` | ✓ VERIFIED | All four exports present; parity-proven; failure-path proven by deliberate break |
| `tests/fixtures/research_validation_cases.json` | shared Python/JS case table | ✓ VERIFIED | Read by both `tests/test_web_research_spec.py` fixtures and `tests/n8n/parity.test.mjs` |
| `scripts/build_cloud_workflows.py` | new node bodies + wiring | ✓ VERIFIED | Rebuild deterministic; node-diff confirms exact wiring described in plan |
| `n8n/wf_enrichment_local_live.json` | regenerated with 5 new nodes | ✓ VERIFIED | Node-diff confirms 5 additions, 1 modification (Merge Company), rest byte-identical |
| `tests/n8n/webResearchFailure.test.mjs` | offline failure-path proof | ✓ VERIFIED | 4 tests, guard independently re-broken and confirmed load-bearing |
| `scripts/smoke_closed_won_research.py` | non-gating live smoke, read-only | ✓ VERIFIED | Exit-0 skip path run; read confirms read-only HubSpot access; not run with credentials |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `config/taxonomy.yaml` | `src/taxonomy.py` normalizers | `normalize_org_type_result`/`normalize_content_types` | WIRED | Confirmed by direct code read |
| `src/taxonomy.py` normalizers | `validate_research_output`/`to_provider_result` | function calls | WIRED | Confirmed at `src/taxonomy.py:127-129` |
| `n8n/code/taxonomy.js` | `n8n/code/webResearch.js` | `require("./taxonomy")` | WIRED | Confirmed at `webResearch.js:7` |
| `webResearch.js` "Validate Research Output" node | `ENRICH_MERGE_CO` research merge call | `row.research_candidate` | WIRED | Confirmed via node-diff (Merge Company jsCode changed) and `webResearchFailure.test.mjs`'s `foldResearchIntoMerge` mirror of the D6 fold |
| `ENRICH_MERGE_CO` research merge | `mergeCompanies.js` (unchanged) | second `mergeCompanies()` call | WIRED | `mergeCompanies.js` confirmed byte-identical across the phase; fold logic lives in the wrapper only |
| "Research Trigger Gate" | "IF Research Needed" → "Claude Web Research" HTTP node | gate-then-HTTP topology | WIRED | Node-diff confirms all 5 nodes added in the expected chain; `api.anthropic.com` confirmed the only new/existing research host |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| REQ-web-retrieval | RT-1..4, OC-1..4, ER-1 | ✓ SATISFIED | Tasks 1 & 3; tests pass, code read confirms semantics |
| REQ-evidence-by-field | TS-1/2/3, AT-2 | ✓ SATISFIED | Task 1; `src/taxonomy.py:132` gate confirmed evidence-keyed, not confidence-keyed |
| REQ-tristate-content | JS/Python parity (NM-6 pattern) | ✓ SATISFIED | Task 2; `node --test` 51/51 |

### Anti-Patterns Found

None. (24 `XXX` matches in the built workflow JSON are digit-placeholder phone-format comments, not debt markers; the one `xfail` marker definition remaining in the test file is unused by the target tests.)

### Human Verification Required

None. All must-haves were verified programmatically, including a live re-execution of the
deliberate-break guard (Task 4a) and direct code reads of the evidence-gate semantics
(Task 2's TS-2/TS-3 requirement), rather than relying on test-pass counts alone.

### Gaps Summary

No gaps. One clerical discrepancy is noted (not a gap): the task instructions' reference
commit `360d7bc` for the mergeCompanies.js byte-identical check is the pre-Phase-12 baseline,
not pre-Phase-13. Using the correct pre-Phase-13 baseline (`acca773`, the Phase 13 plan
commit, or `e0d1d5d`, the Phase 12 verification commit — both give the same empty diff)
confirms `mergeCompanies.js` is untouched by Phase 13, as the plan's D6 decision requires.

---

_Verified: 2026-07-21T04:08:20Z_
_Verifier: Claude (gsd-verifier)_
