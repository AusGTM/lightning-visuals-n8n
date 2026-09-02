---
phase: 24
slug: non-tabular-input-adapters
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `24-RESEARCH.md` §"Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo-wide convention; the plugin carries its own `requirements.txt`) |
| **Config file** | none — pytest runs on defaults; the existing suite already runs this way, so no Wave 0 install |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~10–20 seconds quick; ~60 seconds full |

**Note:** the repo's established invocations are `.venv/bin/python -m pytest <paths> -q` (system
python lacks deps) and `node --test tests/n8n/<file>.test.mjs` in FILE form (the directory form is
broken on the installed node version). Do not substitute a bare `pytest`. Phase 24 adds no n8n-side
JavaScript, so no `node --test` file is new here; the existing ones must stay green.

---

## Sampling Rate

- **After every task commit:** run the quick command, scoped to that task's test file
- **After every plan wave:** run `.venv/bin/python -m pytest operator-claude-plugin/tests -q`
- **Before `/gsd-verify-work`:** full suite green, plus the two live-runtime confirmations below
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 24-01 | 1 | INGEST-01, STRUCT-03 | T-24-01 | canonical set and identity groups derived from `config/column_mapping.yaml`, never retyped; artifact in, CSV out, no API key anywhere | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_handoff.py -q` | ❌ W0 | ⬜ pending |
| 24-01-02 | 24-01 | 1 | STRUCT-02 | T-24-03 | identity presence check trims before testing, matching the deployed `Map Columns` node rather than `_has_identity` | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_identity_preflight.py -q` | ❌ W0 | ⬜ pending |
| 24-01-02 | 24-01 | 1 | INGEST-03 | T-24-01 | a key outside the canonical allowlist is reported before it is removed — the backend cannot report, so the client must | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_identity_preflight.py -q` | ❌ W0 | ⬜ pending |
| 24-01-02 | 24-01 | 1 | INGEST-06 | T-24-04 | missing / unparseable / wrong-shaped / empty artifact each raise a distinct named code; CLI exits non-zero | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_identity_preflight.py -q` | ❌ W0 | ⬜ pending |
| 24-01-03 | 24-01 | 1 | STRUCT-03, STRUCT-04 | T-24-02 | provenance rendered in the preview and structurally absent from the dispatch CSV header | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_provenance_strip.py -q` | ❌ W0 | ⬜ pending |
| 24-02-01 | 24-02 | 2 | INGEST-07 | T-24-05, T-24-06 | overlap collapses on exact identity-key equality only; no similarity threshold exists; merged row keeps both provenance records | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_overlap_dedupe.py -q` | ❌ W0 | ⬜ pending |
| 24-02-02 | 24-02 | 2 | STRUCT-04 | T-24-07 | a record flagged uncertain for a field yet carrying a value for it is rejected; no code path resolves an ambiguity into a value | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_no_invention_structural.py -q` | ❌ W0 | ⬜ pending |
| 24-03-01 | 24-03 | 2 | INGEST-01, INGEST-03 | T-24-13 | the documented artifact schema is pinned to the real validator by parsing the fenced example and running it | unit (static + contract) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py -q` | ❌ W0 | ⬜ pending |
| 24-03-02 | 24-03 | 2 | INGEST-05, INGEST-06 | T-24-09, T-24-10, T-24-12 | fetch-failed and fetched-but-nothing-usable are separately worded; fetch fences stated as tool facts, not policy | unit (static + contract) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py -q` | ❌ W0 | ⬜ pending |
| 24-03-02 | 24-03 | 2 | INGEST-07 | T-24-11 | automated capture excluded as a fact about the adapter; screenshot example artifact validated through the real dedupe path | unit (static + contract) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py -q` | ❌ W0 | ⬜ pending |
| 24-03-03 | 24-03 | 2 | INGEST-01, INGEST-05, INGEST-07 | T-24-11 | one skill, one preview, one dispatch path; every script path the skill names exists | unit (suite regression) | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is **plan 24-01**, whose Task 1 creates the fixtures every later test in this phase reuses.
It extends the existing `operator-claude-plugin/tests/conftest.py` from 23-03 rather than adding a
second conftest.

- [ ] `operator-claude-plugin/tests/conftest.py` — a valid two-record prose extraction artifact
      written to `tmp_path`, plus a factory for malformed and edge-case variants so no later test
      hand-writes JSON
- [ ] `operator-claude-plugin/tests/test_extraction_handoff.py` — the end-to-end slice, covering
      INGEST-01 and STRUCT-03
- [ ] `operator-claude-plugin/tests/test_identity_preflight.py` — STRUCT-02 including the whitespace
      divergence from `src/file_loader.py::_has_identity`, plus INGEST-03's report path and
      INGEST-06's named artifact errors
- [ ] `operator-claude-plugin/tests/test_provenance_strip.py` — STRUCT-01 stays true: the dispatch
      CSV's parsed header set is a subset of the canonical props
- [ ] `operator-claude-plugin/tests/test_overlap_dedupe.py` — INGEST-07's overlap clause (24-02)
- [ ] `operator-claude-plugin/tests/test_no_invention_structural.py` — STRUCT-04's checkable half (24-02)
- [ ] `operator-claude-plugin/tests/test_extraction_contract.py` — the prompt/validator drift pin (24-03)
- [ ] No framework install needed — pytest is already used repo-wide and the plugin's own
      `requirements.txt` (23-03) already covers this phase's dependencies. Phase 24 adds no package.

**Critical Wave 0 constraint:** no test in this phase may perform a live POST or a real network
fetch. The autouse `no_network` fixture from 23-03 blocks `requests` by construction; the additional
constraint here is that no test may invoke `web_fetch` or read an image file — per D-02 Python never
touches image bytes, so a test that reads one is testing something this design does not do.

**Blocking prerequisite (not a Wave 0 gap):** Phase 23 plans 23-04 and 23-05 must have landed before
this phase executes, so `operator-claude-plugin/scripts/preview.py`, `scripts/dispatch.py` and
`skills/contact-upload/SKILL.md` exist. 24-01 Task 1 and 24-03 Task 1 each carry a `<precondition>`
asserting this and halting if it is unmet.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The native `web_fetch` tool is actually available to a running skill in the operator's Claude Desktop surface | INGEST-05 | 24-RESEARCH.md Open Question 1 / assumption A1: the API-level tool contract is documented, but whether the Desktop skill runtime exposes it ambiently or needs an enabling step is not resolvable from docs | In a live session with the plugin installed, paste a public URL and confirm a fetch occurs and reports either retrieved content or an error code. If no fetch happens, the URL adapter is blocked as designed and needs a design change — do not reach for an HTTP client, which would violate D-01/D-02 |
| Images attached in one turn are read natively, and the practical per-turn image ceiling | INGEST-07 | 24-RESEARCH.md Open Question 2 / assumption A2: API-level limits are documented (~20 images before a dimension cap) but the Desktop client's own upload cap is not; and no automated harness can attach an image | Attach a scrolled sequence of screenshots in one turn and confirm rows are extracted with per-image provenance. Note the count at which the client refuses or drops, and adjust the batching ceiling stated in `extraction.md` to the observed number rather than the deduced one |
| An extracted batch actually renders as one preview with provenance, rejects, dropped keys and one ambiguity block | STRUCT-03, STRUCT-04 | The preview is rendered by the skill in conversation (23-CONTEXT D-09), so its readability is human judgment; the underlying structure is unit-tested | Run one extracted batch of each kind through to the preview and confirm the operator can find, for a row they doubt, which input and which span produced it — and that ambiguities arrive as one block, not one interruption per row |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
