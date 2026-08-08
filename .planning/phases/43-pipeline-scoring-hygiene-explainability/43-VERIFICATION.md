---
phase: 43-pipeline-scoring-hygiene-explainability
verified: 2026-08-08T00:00:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 43: Pipeline Scoring Hygiene & Explainability Verification Report

**Phase Goal:** Close the pipeline-side residue of the 2026-08-06 scoring audit — the one
LIVE defect (`lv_enrichment_needs_review` written as a boolean HubSpot filters can never
match), the shared latent veto site, a producer for the score breakdown, and first
consumption of the closed-lost feedback signal.

**Verified:** 2026-08-08
**Status:** passed
**Re-verification:** No — initial verification

This verification independently re-derived every live claim rather than trusting
SUMMARY.md/LIVE-EVIDENCE.md prose: read the actual coercion sites in
`n8n/code/reviewApply.js`, `n8n/code/mergeCompanies.js`, `scripts/build_cloud_workflows.py`;
ran the full offline suites myself; fetched the 5 deployed n8n Cloud workflows directly via
the n8n API (read-only GET, no mutation) and regex-scanned their stored JSON for
bare-boolean vs. string-coerced `lv_*_needs_review` writes; diffed the phase's commit range
against the pre-existing dead-path test; and re-ran `build_cloud_workflows.py` to confirm
builder idempotence. All read-only, no portal mutation, no deploy, no arming.

## Goal Achievement

### Observable Truths (Success Criteria SC1–SC5)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | Every writer of `lv_enrichment_needs_review` emits the string "true"/"false"; a structural test pins it; an EQ-filter fixture proves the filter matches | ✓ VERIFIED | 6 write sites fixed at their shared choke points (`n8n/code/reviewApply.js:94-95`, `scripts/build_cloud_workflows.py:2796` needs-review branch, `:1366`/`:2843` finalization-loop coercion branches, `n8n/code/mergeCompanies.js:249` promote-branch). Row-specific tests (not counts) in `tests/test_cloud_companies_branch.py` — 23/23 pass, independently re-run. Live EQ-filter proof in `43-LIVE-EVIDENCE.md` Task 1: direct poll reproduction confirmed the disposable company appeared in the `AWAITING_REVIEW_GROUPS[0]` filtered search after ~20s (the pytest module's own no-poll second test flakes on HubSpot search-index lag — disclosed honestly as WINDOWS.md #6, open, not swept under the rug). |
| SC2 | `mergeCompanies.js` veto-class fields carry non-zero `min_confidence` + string coercion at the single shared fix site; dead-path test proves hardening without resurrecting the path | ✓ VERIFIED | `min_confidence: 80` on `lv_anti_icp_flag`/`lv_anti_icp_reason` (lines 68-69) was already landed by Phase 40 D-04 and correctly treated as verify-only this phase (not re-implemented). Coercion added at the one shared promote-branch assignment (`n8n/code/mergeCompanies.js:249`, `typeof value === "boolean" ? ... : value`), proven via a static regex test, never by driving the dead path. `test_company_canonical_patch_never_contains_a_derived_icp_output_field` (the dead-path proof) diffed byte-identical across the phase's full commit range (`f7edd13^..HEAD`) — confirmed independently via `git diff`, zero hunks touching that function. |
| SC3 | The parity harness writes `lv_icp_score_breakdown` (rubric-versioned, property-limit truncated) for every record it checks | ✓ VERIFIED | `serialize_breakdown()` (`scripts/run_scoring_parity.py:70`) adds `total` on every path (confirmed absent from `src/icp_scoring.py`'s source `breakdown` dict — grep shows no `"total"` key ever assigned) via `json.dumps()` at each shed stage, never a byte slice — always valid JSON. `--write-breakdown` is `action="store_true", default=False` (genuinely opt-in per D-01); a raising-stub guard test (`test_write_breakdown_default_off_never_calls_write_fn`) proves the default path cannot write. Live round-trip proven against pipeline-computed truth (disposable company settled through the real n8n pipeline): breakdown `total: 80` == live `lv_icp_fit_score: '80'`, 371 bytes (0.6% of the 60k limit), `version: "lv-icp-v0.1"` stamped. Coverage confined to compared records only (D-03) — a company whose fetch raised gets no write (test-proven). |
| SC4 | A loss-reason report aggregates `lv_closed_lost_reason` against the rubric version; consumption only | ✓ VERIFIED | `scripts/build_loss_reason_report.py` — no `patch_record`/`create_record`/`delete_record` call anywhere (grep 0); `src/hubspot_client.py` unchanged. `docs/reports/2026-08-07-loss-reason-report.md` exists, stamps `lv-icp-v0.1`, reports 59 closed-lost deals examined, both `lv_closed_lost_reason` and native `closed_lost_reason` at 0% filled — honestly reported as the expected first-run outcome (not fabricated, not a failure exit code). `test_empty_dataset_renders_zero_counts_and_exits_success` confirms exit 0 over zero rows. Plugin skill (`operator-claude-plugin/skills/loss-reason-report/SKILL.md`) shells out via subprocess, never imports backend code, passes `test_no_backend_imports.py`. |
| SC5 | Suites green above baselines; arming grep 0; no n8n JSON hand-edits — builder only | ✓ VERIFIED | Re-ran myself: `.venv/bin/python -m pytest -q` → 2421 passed, 121 skipped (matches SUMMARY's claim, above the 2398 baseline). `node --test tests/n8n/*.test.mjs` → 636 passed, 0 failed. `operator-claude-plugin/tests/ -q` → 1286 passed, 5 skipped. `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → 0 for all 8 files. Re-ran `scripts/build_cloud_workflows.py` myself and confirmed `git diff --exit-code n8n/` is clean (zero diff) — builder is idempotent, no hand-edits present in the tree. |

**Score:** 5/5 must-haves verified (0 present-but-behavior-unverified)

### Live Deployment Verification (independent, read-only)

Fetched all 5 deployed n8n Cloud workflows directly via `GET /api/v1/workflows` and
`GET /api/v1/workflows/{id}` (no PUT/PATCH/DELETE issued) and regex-scanned stored JSON:

| Workflow | id | active | bare-boolean `needs_review` writes | string-coerced writes | Notes |
|---|---|---|---|---|---|
| LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | true | 0 | 2 | `june_2026` marker present; matches 43-05's claimed 2 |
| LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | true | 0 | 4 | |
| LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | **false** | 0 | 1 | Deployed (43-05's 5-workflow dry run) but not bounced (43-05 bounced only 2 by name); inactive, so no stale-code risk on this workflow — the one review-flag consumer inlined via `reviewApply.js`'s shared `clearPatch` fix. |
| LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | true | — | — | Not a `lv_*_needs_review` writer, out of this check's scope |
| LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | true | — | — | Not a `lv_*_needs_review` writer, out of this check's scope |

Live `ALLOW_HUBSPOT_RECORD_WRITES` on both bounced workflows: `"false"` — write gates
confirmed disarmed live, independently of the repo grep. Zero bare-boolean writes found in
any deployed workflow's stored content — the coercion fix is genuinely live, not merely
committed.

**Note on `LV Review Decision (Cloud)`:** it received the same 43-05 deploy (its stored
content already carries the string-coerced form) but was not one of the 2 workflows 43-05
explicitly bounced. Because it is currently `active: false`, there is no running instance
executing stale pre-fix code — this is not a live-defect gap. If it is ever activated
without a bounce first, the standing stored-vs-running rule (a bare PUT never reloads a
running workflow) would apply. Recorded here as an operator note, not a blocker.

### PIPE-01 Severity Framing — Honestly Downgraded, Not Smoothed Over

43-04's live investigation found that HubSpot silently coerces a bare-boolean PATCH on
`lv_enrichment_needs_review` to the string `'true'` — this is disconfirming evidence
against the audit's original "LIVE defect: unfixed records are invisible to the review
queue" framing for *this specific property*. This is recorded plainly, not smoothed:

- `43-LIVE-EVIDENCE.md` Task 1 states it explicitly under "Severity framing change": *"HubSpot's own coercion already makes a bare-boolean write filterable... the fix is a correctness/consistency improvement and a defense against non-coercing properties, not a fix for an observed 'invisible record' defect on this specific property."*
- `43-04-SUMMARY.md`'s headline sentence leads with the disconfirmation: *"found one disconfirming result (silent boolean coercion softens PIPE-01's severity framing)... recorded honestly rather than smoothed over."*
- `.planning/REQUIREMENTS.md`'s PIPE-01 entry still carries the pre-phase parenthetical `(LIVE defect: shallow-spread-with-no-coercion.)` — this is stale historical wording from before the phase ran, not a re-smoothing after the fact; the downgrade lives in the summaries/evidence where the disconfirmation was actually discovered, which is where honesty is required. Not treated as a gap.

The fix's real value — closing the coercion class everywhere before it reaches a
non-coercing property, plus proving the EQ filter genuinely matches the corrected write —
stands independently of the softened severity framing.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `n8n/code/reviewApply.js` | Quoted-string `clearPatch` booleans | ✓ VERIFIED | Lines 94-95: `"false"` literals confirmed |
| `n8n/code/mergeCompanies.js` | min_confidence 80 + promote-branch coercion | ✓ VERIFIED | Lines 68-69 (min_confidence), line 249 (coercion) |
| `scripts/build_cloud_workflows.py` | needs-review + 2 finalization-loop coercion branches | ✓ VERIFIED | Lines 1366, 2796, 2843 |
| `scripts/run_scoring_parity.py` | `serialize_breakdown`, `--write-breakdown` | ✓ VERIFIED | Lines 63-133 (serializer), 367-378 (CLI flag) |
| `scripts/build_loss_reason_report.py` | Consumption-only aggregator | ✓ VERIFIED | No write helpers; empty-dataset-correct |
| `operator-claude-plugin/skills/loss-reason-report/SKILL.md` | Plugin skill, shells out | ✓ VERIFIED | Present; `plugin.json` bumped 0.11.1→0.12.0 |
| `docs/reports/2026-08-07-loss-reason-report.md` | First real report | ✓ VERIFIED | Present, correct empty-dataset content |
| `tests/test_review_flag_eq_filter.py` | Live-gated EQ-filter proof | ✓ VERIFIED (with caveat) | Authored and executed; second test flakes on index lag (WINDOWS #6, open) — filter match proven via direct poll reproduction instead |
| `n8n/wf_*.json` (8 files) | Builder-generated, no hand-edits | ✓ VERIFIED | Re-generated by this verifier; zero diff |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `reviewApply.js` clearPatch | `wf_scheduled_maintenance_cloud.json` "Apply Review" + `wf_review_decision_cloud.json` "Build Review Decision" | Shared JS module inlined at build time | ✓ WIRED — both consumers checked, both carry the quoted form |
| `mergeCompanies.js` promote branch | `ENRICH_MERGE_CO` node in enrichment workflows | Same inlining mechanism | ✓ WIRED |
| `run_scoring_parity.py --write-breakdown` | `lv_icp_score_breakdown` HubSpot property | `patch_record` via injectable `write_fn` | ✓ WIRED — live round trip confirmed |
| `build_loss_reason_report.py` | Deal search + company join | `search_records`/Associations v4 | ✓ WIRED — live run confirmed (59 deals examined) |
| Deployed n8n Cloud workflows | Repo `n8n/*.json` | `deploy_n8n_workflows.py` PUT + bounce | ✓ WIRED — independently confirmed via live GET, content matches repo exactly for the 2 bounced + 1 deployed-but-inactive workflows |

### Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| PIPE-01 | ✓ SATISFIED | 6-site coercion sweep, live-deployed, live EQ-filter match proven, severity honestly downgraded |
| PIPE-02 | ✓ SATISFIED | min_confidence verify-only (already 80), coercion added, dead-path test untouched (git-diff-confirmed) |
| PIPE-03 | ✓ SATISFIED | Opt-in write mode, valid-JSON truncation, live round trip against pipeline-computed truth |
| PIPE-04 | ✓ SATISFIED | Live report over empty dataset, honest counts, consumption-only, plugin skill shipped |

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX` markers in any file this phase touched (checked directly).
No stub returns, no hardcoded-empty data flowing to output.

### Human Verification Required

None. All must-haves resolved to VERIFIED via direct code inspection, offline test
execution, and independent live-portal reads.

### Warnings (non-blocking)

1. **Flaky EQ-filter fixture** (`tests/test_review_flag_eq_filter.py`, WINDOWS.md #6, open) — the second test lacks a poll for HubSpot's ~20s search-index lag on brand-new records and will fail on a fresh disposable company. The underlying filter-match claim (SC1) is still proven — via the direct poll reproduction recorded in `43-LIVE-EVIDENCE.md` — but the test-as-authored is not self-sufficient proof on a bare re-run. Tracked, not silently dropped.
2. **`LV Review Decision (Cloud)` deployed-but-unbounced** — content is correct and the workflow is inactive, so there is no live-defect exposure today. Flag for the operator: if this workflow is ever activated, bounce it first per the standing stored-vs-running rule.
3. **Canary score drift** (Melbourne Racing Club, `9604614548`): recorded 80/A at Phase 40's close, now reads 25/C; only 1 of 712 portal companies carries any live score. Discovered as a side effect of 43-04's Task 2, explicitly flagged by that plan as out of its investigation scope. Carried forward here for operator visibility, not a Phase 43 gap.
4. **`REQUIREMENTS.md`'s PIPE-01 parenthetical** retains pre-phase "(LIVE defect...)" wording — stale historical framing, not a re-smoothing; the actual severity downgrade is recorded where it was discovered (43-04-SUMMARY.md, 43-LIVE-EVIDENCE.md). Cosmetic only.

### Gaps Summary

None. All 5 roadmap success criteria verified against actual code and independently
re-checked live deployment state. No FAILED must-haves.

---

*Verified: 2026-08-08*
*Verifier: Claude (gsd-verifier)*
