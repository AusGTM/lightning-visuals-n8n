---
phase: 37
slug: enrich-before-ingest
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-05
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `37-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`operator-claude-plugin/tests/` + repo `tests/`) + Node built-in `node:test` (`tests/n8n/*.test.mjs`) |
| **Config file** | none — repo convention; autouse fixtures live in `tests/conftest.py` |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` · `node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~120 seconds for all suites |

**Baselines, corrected for Phase 36** (37-CONTEXT.md §11's numbers are stale — they predate it):

| Suite | 37-CONTEXT.md §11 says | Actual current baseline |
|---|---|---|
| `.venv/bin/python -m pytest -q` | 1933 / 6 | **1960 passed / 6 skipped** |
| `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | 1052 / 5 | **1052 / 5** (unchanged — Phase 36 was backend-only) |
| `node --test tests/n8n/*.test.mjs` | 553 | **609** |
| `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | 0 | **0** |

Command forms are exact. System python lacks the deps; the `node --test` directory form is broken on
node 24 — FILE glob only.

**The autouse `no_network` guard means no test may perform a real request.** Use
`stub_post_transport_factory` (attribute-shaped) / `stub_module_transport_factory` (module-shaped)
from `tests/conftest.py`.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest <touched_test_file> -q` and/or
  `node --test tests/n8n/<touched>.test.mjs`
- **After every plan wave:** `.venv/bin/python -m pytest -q` + `node --test tests/n8n/*.test.mjs`
- **Before `/gsd-verify-work`:** all suites green
- **Max feedback latency:** 30 seconds (targeted run)

---

## Proof layers

This phase's central discipline (37-CONTEXT.md §9.1): **pin behaviour at the layer the operator
reaches.** Pure logic may be direct-imported; anything the operator experiences is pinned as a CLI
subprocess against an isolated plugin root.

| Layer | What it covers | Harness |
|---|---|---|
| **Direct import** | `classify_matches`, `apply_match_decisions`, `merge_enriched`, `build_rows_spec`, `rows_from_table`, `hold_emailless`, and `write_dispatch_csv`'s new raise | plain pytest, no fixture beyond autouse `no_network` |
| **Direct import + stub transport** | `fetch_matches`, `match_batch` — network stubbing needs in-process fixture control a subprocess cannot give | `stub_post_transport_factory` |
| **CLI subprocess** | `config_gate`'s new `match` row; `preview_enrichment`'s rows-spec branch and file-path `__main__`; `chunking`'s new `rows` branch | `tests/test_config_gate.py::_run_cli`, `_run_header_cli` in `tests/test_header_suggest.py` |
| **Skill-contract** | the two-arming-phrases pin (§6.3) and heading-index ordering (§8.7) | new pytest over `skills/enrich-before-ingest/SKILL.md`, same character-index idiom 36-04 used for `_writeSafetyAllows` call ordering |
| **Backstop — live** | the 9-directors end-to-end walk; the release checklist | operator walk; no automated file |

---

## Per-Task Verification Map

Task IDs filled by the planner; the DoD → proof mapping below is the contract each task must satisfy.

| §8 DoD | Behavior | Layer | Test file | Status |
|---|---|---|---|---|
| 1 | 9-directors walks end to end; every row reaching HubSpot carries an email | **backstop/live** | manual UAT walk | ⬜ pending |
| 2 | Incomplete rows named and held; `write_dispatch_csv` raises; file not created | direct import | `tests/test_extraction_*.py` (new cases + the §10 flipped test) | ⬜ pending |
| 3 | A failed match chunk yields `unchecked`, never `unmatched` | direct import | new `test_preingest_match.py` | ⬜ pending |
| 4 | `apply_match_decisions` refuses an unproposed row or a not-own candidate; nothing applied on refusal | direct import | new `test_preingest_match.py` | ⬜ pending |
| 5 | `merge_enriched` joins by id, refuses duplicate id, ignores unknown id | direct import | new `test_preingest_merge.py` | ⬜ pending |
| 6 | Rows envelope pinned byte-identical py↔js | py↔js pair | `tests/n8n/rowsEnvelopeContract.test.mjs` + `operator-claude-plugin/tests/test_rows_envelope_contract.py` | ⬜ pending |
| 7 | Two arming phrases, no combined one; ingest-arm section after enriched-preview by heading index | skill-contract | new test over `skills/enrich-before-ingest/SKILL.md` | ⬜ pending |
| 8 | Suites green; version bumped in the same commit as the CHANGELOG cut; merged to master; clone refreshed | **backstop/live** | manual release checklist | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `operator-claude-plugin/tests/test_preingest_match.py` — `classify_matches` tiering,
      `match_batch`'s skip-a-failing-chunk contract, `apply_match_decisions`' two refusal branches
- [ ] `operator-claude-plugin/tests/test_preingest_merge.py` — `merge_enriched` join-by-`row_id`,
      duplicate-id refusal, unknown-id ignore
- [ ] `tests/n8n/rowsEnvelopeContract.test.mjs` + `operator-claude-plugin/tests/test_rows_envelope_contract.py`
      — the py↔js pair, mirroring `listEnvelopeContract.test.mjs` + `test_list_envelope_contract.py`.
      **This is the D-19 flat-vs-nested class that shipped once and killed the list lane while both
      suites stayed green** — it is the highest-value test in the phase.
- [ ] Skill-contract test over `skills/enrich-before-ingest/SKILL.md`
- [ ] `tests/test_retry_reuses_dispatch.py` — allowlist `fetch_matches` AND close the module-shaped
      hole. **Two keeper tests stop the allowlist being a rubber stamp:** the match POST passes no
      `files=`/`data=`, and its `json=` body keys are AST-pinned to `{email, firstname, lastname,
      company}` — deliberately not phone/jobtitle/linkedin_url.
- [ ] The §10 deliberate flip: the emailless-row round-trip case in the extraction tests currently
      asserts the row is written; it now asserts the refusal. Record it in the SUMMARY, do not silence it.

*Framework fully present — no install needed.*

---

## Manual-Only Verifications

| Behavior | DoD | Why Manual | Instructions |
|---|---|---|---|
| 9-directors end-to-end walk: extract → match → confirm → enrich → enriched preview → ingest | 1 | Needs the live tenant, a real HubSpot sandbox, and Phase 36 deployed + bounced | Operator walk. **Blocked until Phase 36's disarmed deploy lands.** |
| Release: version bumped in the same commit as the CHANGELOG cut → push → **merge to master** → refresh the marketplace clone | 8 | Master is the branch the marketplace reads; `0.9.0` shipped with a correct bump sitting on a feature branch and the Update button stayed grey | Operator-run |

---

## Open decision affecting one task only

**Match request ceiling.** Phase 36 shipped an unconditional `events.length > 2` refusal in
`Parse HubSpot Event` (`scripts/build_cloud_workflows.py:3414-3425`), checked *before* `mode` is read —
so a match/propose call is capped at 2 rows. 37-CONTEXT.md §4.2 instructs shipping a larger measured
`max_rows_per_match_request`, and §12 lists match inheriting the waterfall's 2 under **rejected**.
Awaiting the operator's ruling. Isolate this to one task so either resolution is a small change:

- **If the ceiling stays 2:** ship `max_rows_per_match_request: 2` with a provenance note pointing at
  the shared guard (not an independent measurement) plus a cross-repo pin like
  `test_chunk_ceiling_contract.py`.
- **If the guard becomes mode-aware:** that edit lives in Phase 36's builder, not here; this phase's
  config key then carries the measured value 37-CONTEXT.md §4.2 asks for.

Either way the key stays separate from `max_records_per_chunk` — a match refusal must not print
waterfall wording.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
