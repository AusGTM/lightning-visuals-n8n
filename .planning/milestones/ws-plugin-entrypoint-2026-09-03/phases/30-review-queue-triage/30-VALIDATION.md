---
phase: 30
slug: review-queue-triage
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-31
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `node --test` (FILE form) for n8n module and node-flow tests; `pytest` for builder/deploy/architecture guards and for the plugin's own suite |
| **Config file** | none dedicated — plugin suite is governed by `operator-claude-plugin/tests/conftest.py`'s autouse network guard |
| **Quick run command** | `node --test tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/reviewLoop.test.mjs` (backend tasks) / `.venv/bin/python -m pytest operator-claude-plugin/tests -q` (client tasks) |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/reviewQueueEndpoint.test.mjs tests/n8n/reviewHumanProvenance.test.mjs tests/n8n/reviewWriteFlagSeparation.test.mjs tests/n8n/reviewLoop.test.mjs` |
| **Estimated runtime** | ~90 seconds full, ~5 seconds quick |

Directory-form `node --test tests/n8n/` is broken on this repo's Node build; always pass explicit
file paths. Always use `.venv/bin/python`; the system interpreter lacks this repo's dependencies.

---

## Sampling Rate

- **After every task commit:** Run the matching quick command above
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | REVIEW-03 | T-30-01 / T-30-02 / T-30-03 | Review arming is a distinct gate action; arming it without an allowlist is refused | unit | `.venv/bin/python -m pytest tests/test_cloud_write_path.py tests/test_deploy_flag_overlay.py tests/test_deploy_write_safety_overlay.py tests/test_write_gate_coverage.py tests/test_contact_create_overlay.py -q` | ✅ | ⬜ pending |
| 30-01-02 | 01 | 1 | REVIEW-03 | T-30-02 | The overlayable set stays pinned and cost caps/model names stay unreachable | unit | `.venv/bin/python -m pytest tests/test_enabled_build_invariants.py tests/test_builder_flag_parity.py -q` | ✅ | ⬜ pending |
| 30-01-03 | 01 | 1 | REVIEW-03 | T-30-01 | Arming dispatch grants nothing to review, proved on committed jsCode | unit | `node --test tests/n8n/reviewWriteFlagSeparation.test.mjs` | ❌ W0 | ⬜ pending |
| 30-02-01 | 02 | 2 | REVIEW-05 | T-30-07 / T-30-10 | A rejection writes exactly one property and clears no flag | unit | `node --test tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/reviewLoop.test.mjs` | ❌ W0 | ⬜ pending |
| 30-02-02 | 02 | 2 | REVIEW-03 | T-30-05 / T-30-06 / T-30-08 | Endpoint takes no caller-supplied field or value; PATCH sits behind a review-action gate; artifact committed inactive and disarmed | unit | `.venv/bin/python -m pytest tests/test_architecture_guard.py tests/test_write_gate_coverage.py tests/test_deploy_credential_binding.py tests/test_node_name_uniqueness.py tests/test_hubspot_node_auth.py tests/test_row_carry.py tests/test_deploy_n8n_workflows.py tests/test_schedules_inactive.py -q` | ✅ | ⬜ pending |
| 30-02-03 | 02 | 2 | REVIEW-03, REVIEW-04 | T-30-05 / T-30-06 / T-30-10a | Unarmed request previews and never reaches the gate; injected keys change nothing; the five-key response contract holds on both branches with `verified_properties` from the independent refetch | unit | `node --test tests/n8n/reviewDecisionEndpoint.test.mjs` | ❌ W0 | ⬜ pending |
| 30-03-01 | 03 | 3 | REVIEW-02, REVIEW-04 | T-30-11 / T-30-12 / T-30-13 / T-30-14 | Protected classes never reach the patch; stale writes nothing; human provenance merged additively | unit | `node --test tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/reviewHumanProvenance.test.mjs tests/n8n/reviewLoop.test.mjs tests/n8n/mergeCompanies.test.mjs` | ❌ W0 | ⬜ pending |
| 30-03-02 | 03 | 3 | REVIEW-02 | T-30-15 | Contacts PATCH is gated identically; the 15-minute backstop is untouched | unit | `node --test tests/n8n/reviewDecisionEndpoint.test.mjs && .venv/bin/python -m pytest tests/test_write_gate_coverage.py tests/test_deploy_credential_binding.py tests/test_node_name_uniqueness.py tests/test_hubspot_node_auth.py tests/test_row_carry.py tests/test_architecture_guard.py -q` | ✅ | ⬜ pending |
| 30-04-01 | 04 | 4 | REVIEW-01 | T-30-17 / T-30-19 | Queue request accepts only object type and a clamped limit | unit | `.venv/bin/python -m pytest tests/test_architecture_guard.py tests/test_write_gate_coverage.py tests/test_deploy_credential_binding.py tests/test_node_name_uniqueness.py tests/test_hubspot_node_auth.py tests/test_deploy_n8n_workflows.py -q` | ✅ | ⬜ pending |
| 30-04-02 | 04 | 4 | REVIEW-01 | T-30-16 | No write node is reachable from the queue webhook; stored strings pass through intact | unit | `node --test tests/n8n/reviewQueueEndpoint.test.mjs` | ❌ W0 | ⬜ pending |
| 30-05-01 | 05 | 5 | REVIEW-01, REVIEW-02 | T-30-20 / T-30-20a / T-30-21 | Secret never rendered; policy lookup is display-only; `review` is its own capability row; transport stays read-shaped so `_EXPECTED_SEND_SHAPED` is untouched | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_queue.py operator-claude-plugin/tests/test_status_unknown.py operator-claude-plugin/tests/test_retry_reuses_dispatch.py operator-claude-plugin/tests/test_transport_guard.py -q` | ❌ W0 | ⬜ pending |
| 30-05-02 | 05 | 5 | REVIEW-01 | T-30-22 / T-30-23 | Protected fields labelled before a decision; resolved-source disclosure present | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_queue.py -q` | ❌ W0 | ⬜ pending |
| 30-06-01 | 06 | 6 | REVIEW-03, REVIEW-04, REVIEW-05 | T-30-24 / T-30-24a / T-30-24b / T-30-25 / T-30-26 | `ALLOW_REVIEW_SUBMIT` unset refuses with an empty call log and never gates an un-doing path; unarmed submit makes no mutating call; verified decided against the independent refetch, not a status code | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py operator-claude-plugin/tests/test_retry_reuses_dispatch.py operator-claude-plugin/tests/test_transport_guard.py -q` | ❌ W0 | ⬜ pending |
| 30-06-02 | 06 | 6 | REVIEW-03, REVIEW-05 | T-30-27 | Separate arming phrase stated; rejection wording says the record stays queued | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | ✅ | ⬜ pending |
| 30-06-03 | 06 | 6 | REVIEW-03 | T-30-27 | Docs name both endpoints and the two arms, with no secret value | unit | `grep -q 'hubspot/review/queue' operator-claude-plugin/README.md && grep -q 'hubspot/review/decision' operator-claude-plugin/README.md && grep -qi 'review' operator-claude-plugin/CHANGELOG.md && .venv/bin/python -m pytest operator-claude-plugin/tests -q` | ✅ | ⬜ pending |
| 30-07-01 | 07 | 7 | REVIEW-03 | T-30-29 | Arm/disarm runbook documented with its mandatory allowlist | unit | `grep -q 'hubspot/review/decision' n8n/README.md && grep -q 'hubspot/review/queue' n8n/README.md && grep -q 'ENABLE_BAKED_FLAGS' n8n/README.md` | ✅ | ⬜ pending |
| 30-07-02 | 07 | 7 | REVIEW-02, REVIEW-03, REVIEW-04, REVIEW-05 | T-30-28 / T-30-29 / T-30-30 / T-30-31 | One allowlisted record; disarm confirmed by read-back | manual (blocking human) | n/a — see Manual-Only Verifications | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/n8n/reviewWriteFlagSeparation.test.mjs` — gate-separation guard (30-01 Task 3 creates it)
- [ ] `tests/n8n/reviewDecisionEndpoint.test.mjs` — module + endpoint flow tests (30-02 Task 1 creates it, 30-03 extends)
- [ ] `tests/n8n/reviewHumanProvenance.test.mjs` — provenance additivity and entry shape (30-03 Task 1)
- [ ] `tests/n8n/reviewQueueEndpoint.test.mjs` — read-only reachability and payload pass-through (30-04 Task 2)
- [ ] `operator-claude-plugin/tests/test_review_queue.py` and `test_review_decision.py` (30-05, 30-06)

**`operator-claude-plugin/tests/conftest.py` needs NO Wave 0 work (D-21).** An earlier draft listed a
programmable stub payload as missing; `_as_response` (`:101`) and `stub_post_transport_factory`
(`:142`) already provide it, and once D-17's bare-module transport is used the correct fixture is
`stub_module_transport_factory` (`:238`, shipped by 28-01). The autouse network guard already exists
and must stay intact. `conftest.py` is unmodified by this phase.

No framework install is needed: `node --test` and the repo's `.venv` pytest already run this suite.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| An armed review decision lands in HubSpot on exactly one allowlisted record, and both gates are closed afterwards | REVIEW-02, REVIEW-03, REVIEW-04, REVIEW-05 | Agent tooling in this repo is blocked from arming writes, and no automated verification in this phase may perform a live HubSpot write | 30-07 Task 2's `checkpoint:human-verify`, steps 1-10 **including 6b**: snapshot, armed deploy with a single-record allowlist, activate, unarmed preview, the `ALLOW_REVIEW_SUBMIT`-unset refusal (6b, the only live proof the plugin-side gate holds independently of the conversation arm — D-16), reject, approve, disarmed redeploy with read-back confirmation and the variable unset, compare snapshot |
| The rendered queue is intelligible to a non-technical operator | REVIEW-01 | Legibility is a judgment a test cannot make; the automated tests cover structure and disclosures only | 30-07 Task 2 step 5 — the human confirms the flagged record's conflict reads as plain language and any protected field is labelled |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are the phase's one blocking human checkpoint
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
