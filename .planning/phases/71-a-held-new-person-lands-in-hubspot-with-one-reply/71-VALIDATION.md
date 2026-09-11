---
phase: "71"
slug: "a-held-new-person-lands-in-hubspot-with-one-reply"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: true
created: "2026-09-12"
---

# Phase 71 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (plugin suite under `operator-claude-plugin/tests/`, `conftest.py` adds `scripts/` to `sys.path`); node `--test` for `tests/n8n/*.test.mjs` |
| **Config file** | none dedicated beyond `operator-claude-plugin/tests/conftest.py` |
| **Quick run command** | `.venv/bin/python -m pytest -q --tb=short -x -p no:cacheprovider operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_held_queue_facets.py operator-claude-plugin/tests/test_review_triage_facets.py operator-claude-plugin/tests/test_held_facet_render_composition.py` |
| **Full suite command** | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/ && .venv/bin/python -m pytest -q tests/test_todo_triage.py` |
| **Estimated runtime** | quick ~5s (66 tests); plugin suite ~60s (3006 passed, 5 skipped baseline 2026-09-12) |

Always `.venv/bin/python`, never system python. Use `/usr/bin/grep` for counts and pipes.

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-T1 Confirm serialised stable-key shape | 71-01 | 1 | D-71-04 | — | one-way on-disk schema approved by a human before it ships | checkpoint:decision | none (operator answer recorded in 71-01-SUMMARY.md) | n/a | ⬜ pending |
| 01-T2 Tracer: stamp + stable key + save narrowing | 71-01 | 1 | D-71-01, D-71-02, D-71-03, D-71-04 | T-71-01, T-71-02, T-71-03 | key exemption scoped to `identity_keys(entry["row"])`; closed `COMPANY_KNOWN_SOURCES`; atomic 0600 validate-then-write | unit + composition | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_held_queue_facets.py operator-claude-plugin/tests/test_forbidden_marker_parity.py` | ✅ all three exist | ⬜ pending |
| 01-T3 suggestion_declines narrowing + legacy refusal | 71-01 | 1 | D-71-05 | T-71-01, T-71-04 | legacy document degrades whole, never partially trusted; marker-shaped non-identity key still refused | unit (RED-first) | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_held_queue_facets.py operator-claude-plugin/tests/test_suggestion_declines.py operator-claude-plugin/tests/test_suggestion_declines_skill.py operator-claude-plugin/tests/test_forbidden_marker_parity.py` | ✅ all five exist | ⬜ pending |
| 02-T1 rows_to_resume keys on stable key | 71-02 | 2 | D-71-04 | T-71-10 | key miss still re-includes (money-not-a-contact), never silently skips | unit (RED-first) | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_run_manifest.py operator-claude-plugin/tests/test_watch_settle_reporting.py operator-claude-plugin/tests/test_watch_bound_fallback.py` | ✅ all three exist | ⬜ pending |
| 02-T2 enrich-before-ingest collector + stamp + render | 71-02 | 2 | D-71-01, D-71-02, D-71-03 | T-71-07, T-71-08, T-71-09 | no network/config in `confirmed_company_domains`; stamp is evidence not authority; D-10b vocabulary gate | unit + composition (RED-first) | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_preingest_match.py operator-claude-plugin/tests/test_held_facet_render_composition.py operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` | ✅ all four exist | ⬜ pending |
| 02-T3 review-triage cold start + settle under stable key | 71-02 | 2 | D-71-03, D-71-04 | T-71-08, T-71-09, T-71-11 | `record_verb` raises on an unknown key; 2b performs no HubSpot search of its own | composition (RED-first) | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_review_triage_facets.py operator-claude-plugin/tests/test_skill_sequence_coverage.py` then the full plugin suite | ✅ both exist | ⬜ pending |
| 03-T1 Todo triage in/out | 71-03 | 3 | CLAUDE.md §31 rules 1-2 | T-71-16 | `evidence:` carries file:line only, no run id or secret | unit | `.venv/bin/python -m pytest -q tests/test_todo_triage.py` and `.venv/bin/python scripts/todo_triage.py --check` | ✅ exists | ⬜ pending |
| 03-T2 Release 0.48.0 + UAT §1e spec | 71-03 | 3 | D-71-05, D-71-06 | T-71-14, T-71-17 | version + CHANGELOG in ONE commit; no dependency change | unit (greps) + full suite | `/usr/bin/grep -c '"version": "0.48.0"' operator-claude-plugin/.claude-plugin/plugin.json` and `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/` | ✅ both files exist | ⬜ pending |
| 03-T3 D-71-06 live gate | 71-03 | 3 | D-71-06 | T-71-13, T-71-14, T-71-15 | arming per send, disarmed after, bounce after each; every execution id recorded | checkpoint:human-verify (blocking-human) | none — manual by design, see Manual-Only Verifications below | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No Wave 0 scaffold task is needed: every test file this phase extends already exists, and every
`<verify><automated>` in all three plans names a real, currently-runnable command. There is no
`MISSING —` sentinel in any task.

The RED-first cases below are created inside the tasks that own them (all in existing files —
this phase adds no new test file):

- [x] `operator-claude-plugin/tests/test_held_queue.py` (01-T2/01-T3) — the `webhook_secret` key refusal, the Grant-Dewsbury key acceptance, the cross-run `record_verb` invariant, the legacy `row-N` document reading `ANOMALOUS` with `legacy_reason`
- [x] `operator-claude-plugin/tests/test_held_queue_facets.py` (01-T2) — save → load → `stamped_domains` → `classify_facet` asserting `FACET_NEW_PERSON`
- [x] `operator-claude-plugin/tests/test_suggestion_declines.py` (01-T3) — the Grant key acceptance and the `webhook_secret` refusal
- [x] `operator-claude-plugin/tests/test_run_manifest.py` (02-T1) — `rows_to_resume` finds a prior-run held entry by stable key when `row_id` differs
- [x] `operator-claude-plugin/tests/test_preingest_match.py` (02-T2) — `confirmed_company_domains` over both sources, freemail/name-only exclusions, `COMPANY_KNOWN_SOURCES` membership
- [x] `operator-claude-plugin/tests/test_held_facet_render_composition.py` (02-T2) — the step-6 fence driven over a saved-and-reloaded queue
- [x] `operator-claude-plugin/tests/test_review_triage_facets.py` (02-T3) — the cold-start read/render/create/confirm/mark composition

Existing infrastructure (pytest, `conftest.py`) covers framework needs.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A `new_person` row lands live in HubSpot with one `create all N` reply on the batch surface, then `review-triage` cold-start create on a second such row in a fresh sitting | D-71-06 | Live n8n Cloud + HubSpot, per-send arming, human gate (backloaded to end of phase) | `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` §1d; delete `held_queue.json` (D-71-05 wipe) and hand-delete UAT contacts in clean-up; disarm after |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify, or are the two checkpoints (01-T1 decision, 03-T3 blocking-human gate) — no `MISSING —` sentinel anywhere
- [x] Sampling continuity: 7 of 9 tasks carry a runnable `<automated>`; the longest checkpoint-only run is 1
- [x] Wave 0 not required — no MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s (quick command ~5s, 66 tests)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
