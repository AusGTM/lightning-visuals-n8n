---
phase: "62"
slug: "suggest-the-contacts-nobody-named"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-02"
---

# Phase 62 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (plugin + root) and `node:test` (n8n JS) |
| **Config file** | existing — no Wave 0 install needed |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~10s plugin · ~17s root · ~4s node · ~31s full |

**Two hard constraints on every command written into a plan:**
1. Python MUST be `.venv/bin/python -m pytest` — the system python lacks the dependencies.
2. Node MUST use the **glob** form `node --test tests/n8n/*.test.mjs` — the directory form is
   broken on node 24.

**Green baseline at phase start** (measured 2026-09-02, post Phase 60 + code-review fixes):
root **3852 passed / 154 skipped**, plugin **2182 passed / 5 skipped**, node **848 pass / 0 fail**.
A plan's verify step must not reduce these.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests -q`
- **After every plan wave:** full suite (both python suites + node)
- **Before `/gsd-verify-work`:** full suite green
- **Max feedback latency:** ~10 seconds (plugin suite alone)

---

## Per-Task Verification Map

*Populated by the planner. One row per task; every task needs either an `<automated>` command or
a named Wave 0 dependency.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 62-01-T1 | 01 | 1 | SUGGEST-01, SUGGEST-04 | T-62-01 | Row keys asserted a subset of `canonical_props()` — page-read text cannot widen the dispatch header | unit (tracer, end-to-end offline) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py -q` | ❌ new | ⬜ pending |
| 62-01-T2 | 01 | 1 | SUGGEST-01 | T-62-02, T-62-03 | `filter_candidates` host/budget guard called unmodified; per-company fetch bound reset | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py operator-claude-plugin/tests/test_extraction_contract.py -q` | ❌ new / ✅ exists | ⬜ pending |
| 62-01-T3 | 01 | 1 | SUGGEST-04 | T-62-01 | Emailless suggestion held by `hold_emailless`, never a silent write | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py -q && .venv/bin/python -m pytest operator-claude-plugin/tests -q` | ❌ new | ⬜ pending |
| 62-02-T1 | 02 | 2 | SUGGEST-03 (amended) | T-62-06, T-62-07, T-62-09 | Read-only, credential- and portal-guarded sweep; only title strings leave the portal | contract assertion | `.venv/bin/python -c "…VOCAB_SEED_OK…"` (see plan) | ❌ new | ⬜ pending |
| 62-02-T2 | 02 | 2 | SUGGEST-02, SUGGEST-03 (amended) | T-62-08 | An un-evidenced list cannot render as portal-derived | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_role_vocabulary.py operator-claude-plugin/tests/test_suggest_contacts.py -q` | ❌ new | ⬜ pending |
| 62-02-T3 | 02 | 2 | SUGGEST-03 (amended) | — | Documentation cannot claim a close that did not happen | doc assertion | `grep -q "D-62-07" … && test 0 -eq $(grep -c …)` (see plan) | ✅ exists | ⬜ pending |
| 62-03-T1 | 03 | 1 | SUGGEST-05 | T-62-12 | Unmeasured stage-1 rate renders unmeasured, never $0 | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_cost_guard_suggestion.py operator-claude-plugin/tests/test_cost_guard.py -q` | ❌ new / ✅ exists | ⬜ pending |
| 62-03-T2 | 03 | 1 | SUGGEST-05 | T-62-14 | One-way consent change confirmed by the operator before it is built | manual (`checkpoint:decision`, blocking) | none — human-check | n/a | ⬜ pending |
| 62-03-T3 | 03 | 1 | SUGGEST-05 | T-62-11, T-62-13 | Round weight reaches `ceiling_verdict`; CR-01 key collision cannot recur | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_suggestion.py operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_write_grant_surface.py -q` | ❌ new / ✅ exists | ⬜ pending |
| 62-04-T1 | 04 | 1 | SUGGEST-04 | T-62-16, T-62-17 | Source map cannot leak onto CSV uploads; send-shaped set stays at two (D-33) | node + unit | `node --test tests/n8n/*.test.mjs && .venv/bin/python -m pytest operator-claude-plugin/tests/test_retry_reuses_dispatch.py operator-claude-plugin/tests/test_dispatch_multipart.py -q` | ✅ exists / ❌ new | ⬜ pending |
| 62-04-T2 | 04 | 1 | SUGGEST-01 | T-62-18, T-62-19 | Unread contact count stamped `null`, never a missing key; read-field only, no write | node | `node --test tests/n8n/*.test.mjs && grep -c "num_associated_contacts" n8n/wf_enrichment_cloud.json` | ❌ new | ⬜ pending |
| 62-05-T1 | 05 | 3 | SUGGEST-01, -02, -04, -05 | T-62-21, T-62-22 | No fetch without an operator-approved, in-conversation URL; no escalation past a refusal | manifest contract | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_plugin_manifest.py -q` | ✅ exists | ⬜ pending |
| 62-05-T2 | 05 | 3 | SUGGEST-01, SUGGEST-04 | T-62-22, T-62-24 | Held row never reaches the dispatch set; documented sequence covered, ratchet not loosened | composition | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts_composition.py operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` | ❌ new / ✅ exists | ⬜ pending |
| 62-05-T3 | 05 | 3 | SUGGEST-01, SUGGEST-05 | T-62-23 | The allowance actually reaches the grant a real session opens; cap above the priced cap refused | unit + release check | `.venv/bin/python -m pytest operator-claude-plugin/tests -q && .venv/bin/python -c "…version 0.36.0…"` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — no framework install, no new conftest.

Two existing guards this phase MUST keep green rather than add to:
- `tests/n8n/columnMapIdentityParity.test.mjs` — pins `required_identity` between
  `config/column_mapping.yaml` and `n8n/code/columnMap.js`. Suggested rows resolve through this
  contract (D-62-09); do not loosen it to make a row fit.
- `operator-claude-plugin/tests/test_extraction_contract.py` — already pins that `url_fallback.py`
  is named **only** in the "nothing usable" region and never in the tool-error region, because
  *"escalating past a refusal turns a fence into a suggestion"*. Stage-1 discovery must not
  violate this.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real sitemap yields a usable people page on a real racing-club site | SUGGEST-01 | `url_fallback.py` is pure string-building with no I/O by construction; whether a given site's sitemap actually lists a team/board page can only be established against a live site. The unit tests can prove the ladder and the guard, never the coverage. | Run a suggestion sitting against 2–3 real companies already in HubSpot that have a `website`. Record: did the sitemap resolve, did a people page appear in it, how many of the 5-fetch budget were spent, and were any people named. |
| Stage 1 → stage 2 handoff on a real discovered person | SUGGEST-01, SUGGEST-04 | Requires a real page fetch (plugin-side `web_fetch`) followed by a real Lusha credit spend. Neither can run in the stub-transport suite. | With a grant open, take one discovered `firstname + lastname + company` through enrichment and confirm the row resolves on identity group 2 and lands as a proposal, not a silent write. |
| The priced ceiling is not exceeded in a real sitting | SUGGEST-05 | The ceiling is enforced in code and unit-testable, but "the operator saw a number and the round stayed under it" is an end-to-end property of a live sitting. | Note the quoted ceiling before the round, and the actual fetches + credits after. Actuals must land at or under. |

**Why this phase has an unusually high manual share:** the discovery half is an operator-attended
sitting by decision (D-62-01 rev 3), and its quality question — *does a real site's sitemap lead
to its people?* — is inherently a live-coverage question, not a logic question. The logic (ladder
order, host-binding, budget enforcement, role matching, row synthesis, ceiling arithmetic) is all
automatable and must be automated.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
