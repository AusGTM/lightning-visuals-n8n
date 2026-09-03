---
phase: "60"
slug: "review-lane-authority"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity
threats_open: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 60 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03.** All four plans carry plan-time `<threat_model>` blocks
> (`register_authored_at_plan_time: true`), so this is a verification pass, not retroactive-STRIDE.
>
> **Phase 60 is not complete** — `60-VERIFICATION.md` is `human_needed` and `60-UAT.md` has two
> pending items, all four needing an armed HubSpot write window. That does **not** hold this
> register open: every mitigation below is a deterministic client-side control, exercised by
> stub-transport tests re-run live during this audit. What the armed run adds is *corroboration*,
> tracked in its own section below so it is not lost.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| conversation → plugin client | An operator's "yes" becomes an authority object; nothing in the conversation may fabricate one that arms a backend whose admin never enabled write grants | a grant object (lanes, record ids/domains, workflow ids) |
| plugin client → n8n management API | A PUT rewrites `const` literals inside a deployed workflow; the diff must reach nothing but declaration lines | write-safety flag literals, record allowlist strings |
| n8n workflow → HubSpot | `_writeSafetyAllows("review", …)` is the last gate before a PATCH; this phase changes its **inputs**, never the function | record id, decision word, HubSpot property patch |
| a previous session → this session's grant open | State this process did not create — a backend left armed by a session that died mid-window | live write-safety flag state read back from n8n |
| batch window → the individual decisions inside it | The window is grant-wide; each decision must still be record-scoped | per-decision record id vs. the grant's allowlist |
| operator free text → durable disk | A review reason is the operator's own words; the artifact must never persist an arming-, grant- or secret-shaped value (Phase 23 D-11) | review reason text — deliberately never persisted, fixed at `None` |
| bookkeeping → the live write | A durable-state failure must never stop or reverse a HubSpot write already in flight (D-59-10) | append-chunk success/failure signal |
| documentation → operator behaviour | A gate table that overstates or understates what is required trains the operator wrong | gate-table prose, skill instructions |
| generator → deployed workflow JSON | The JSON is a build artifact; a hand-edit silently diverges from source and survives until the next regeneration erases it | generated `jsCode`/message text |
| repo → installed plugin copy | An unbumped version string means none of this phase reaches the operator at all | plugin version string |

---

## Threat Register

23 threats across four plans.

### 60-01 — Review-lane authority tracer

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-60-01 | Elevation of Privilege | `n8n_arming.arm_for_review` targets dict | high | mitigate | `n8n_arming.py:379-392` — the `AUTHORITY_REVIEW` branch builds `targets = {"ALLOW_HUBSPOT_REVIEW_WRITES": True, "TEST_RECORD_IDS": …, "TEST_RECORD_DOMAINS": …}`, **never either dispatch boolean**. `REVIEW_FLAGS` and `DISPATCH_FLAGS` are separate tuples at `:184-192`, with a comment stating `DISPATCH_FLAGS` must never gain `ALLOW_HUBSPOT_REVIEW_WRITES`. Independently re-read by the orchestrator. `test_the_review_arm_never_sets_dispatch_write_flags_in_the_recorded_put_body` and `tests/n8n/reviewWriteFlagSeparation.test.mjs` (4/4) green. | closed |
| T-60-02 | Elevation of Privilege | `submit_decision` gate 1 | high | mitigate | `review_decision.py:301-313` — gate 1 is `write_grant.authorize_send(grant, lane=REVIEW_LANE, …)`; `write_grant.py:1268-1330`'s `covers` is the **sole** scope implementation, no second scope function found anywhere. `test_a_review_grant_over_record_a_refuses_a_decision_on_record_b` passing. | closed |
| T-60-03 | Spoofing | a hand-built grant-shaped dict | high | mitigate | `write_grant.py:1295-1296` — `covers` refuses any object whose `kind != KIND`; `n8n_arming.py:237-256` — `_arm_gate` re-reads `config_gate.write_grants_enabled(config)` from config on **every** arm, never cached. Unchanged by this phase. | closed |
| T-60-04 | Denial of Service | the retired kill switch | medium | accept | `ALLOW_REVIEW_SUBMIT`, `submit_enabled()` and `_ENV_REFUSAL` confirmed absent (`grep -c` = 0 for all three; no `import os` in `review_decision.py`). Accepted per D-60-04 — see AR-60-02. | closed (accepted) |
| T-60-05 | Tampering | the arming PUT's blast radius | medium | mitigate | `n8n_arming.py:411,413` and `:284-310` — `_declaring_nodes(workflow, flags)` and `_assert_only_declaration_lines_changed(…, flags)` are threaded the **review** flag set inside `arm_for_dispatch`'s `_mutate` closure. `_writeSafetyAllows("review", …)` confirmed unmodified in `scripts/build_cloud_workflows.py:1202-1208` (pre-existing Phase 30 code). | closed |
| T-60-18 | Repudiation | `disarm` reporting a clean verdict over a degraded verify | high | mitigate | `n8n_arming.py:519-533` — an unreadable pre-read (`not isinstance(original, dict)`) returns `DISARM_FAILED` **before any mutation**, naming `ALLOW_HUBSPOT_REVIEW_WRITES` as unverified. Independently re-read by the orchestrator. `test_disarm_refuses_before_mutating_when_the_pre_read_is_unreadable` passing. | closed |
| T-60-19 | Elevation of Privilege | `disarm`'s node allowlist disagreeing with its targets | medium | mitigate | `n8n_arming.py:535-538` — `derived_flags` (from `read_write_safety` over `OVERLAYABLE_FLAGS`) feeds **both** `disarmed_targets(*derived_flags)` and `_declaring_nodes(original, derived_flags)`: one list, not two. `test_disarm_rewrites_a_node_declaring_only_the_review_constant` passing. | closed |
| T-60-A-SC | Tampering | npm/pip/cargo installs | high | mitigate | `git show --stat` on `8a9dac0`, `7cc5780`, `4cb68e2` — none touches `requirements.txt`, `package.json` or `package-lock.json`. | closed |

### 60-02 — Guardrail widening + batch window

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-60-06 | Tampering / Repudiation | `guardrail_a` blind to `ALLOW_HUBSPOT_REVIEW_WRITES` | high | mitigate | `write_grant.py:1749-1750` — `WRITE_ENABLING_FLAGS` widened to three, review flag appended last; `:1798,1824-1827,1862` — `read_live_write_state`/`guardrail_a` iterate `sorted(n8n_arming.OVERLAYABLE_FLAGS)`, the same list feeding both the render and the fault check. `test_a_stuck_open_review_flag_refuses_the_open_and_names_it` passing. | closed |
| T-60-07 | Elevation of Privilege | the batch window's grant-wide allowlist | high | mitigate | `write_grant.py:1480-1536` — `authorize_review_batch` returns the grant's own record lists, **and every individual decision is still routed through** `authorize_send(lane=REVIEW_LANE, record_ids=[one])` inside `submit_decision`. The window is grant-wide; the decisions are not. `test_a_decision_outside_the_grants_records_refuses_but_the_window_still_disarms` passing. | closed |
| T-60-08 | Denial of Service | `preflight_before_send` on the review lane mid-batch | medium | mitigate | `write_grant.py:1954-1956` — `enabling_flags` excludes `ALLOW_HUBSPOT_REVIEW_WRITES` **only**, derived from `WRITE_ENABLING_FLAGS`, and **only** when `lane == REVIEW_LANE`; a live dispatch flag still trips it. Both `test_a_review_lane_preflight_does_not_trip_over_its_own_batch_arm` and `test_a_review_lane_preflight_still_closes_on_a_live_dispatch_flag` passing — the pair is what makes this a narrowing rather than a hole. | closed |
| T-60-09 | Repudiation | a crashed or revoked batch leaving the review flag live | high | mitigate | `n8n_arming.py:606-618` — `armed_window.__exit__` always calls `disarm` and never swallows the body's exception. `test_an_exception_mid_batch_propagates_and_the_window_still_disarms` and `test_a_mid_batch_revocation_refuses_the_next_decision_but_the_window_still_disarms` passing. | closed |
| T-60-B-SC | Tampering | npm/pip/cargo installs | low | accept | `56d1143`, `b3c2337` touch no dependency manifest. | closed (accepted) |

### 60-03 — Written-records vocabulary

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-60-10 | Information Disclosure | the review entry's `reason` field | high | mitigate | `written_records.py:365-372,393-401` — `classify_review_item`'s entry fixes `reason`, `row_id` and `association` to `None`, then re-runs the same `_looks_forbidden` sweep (`:403-409`) that `classify_item` runs. The operator's free text never reaches disk. Full module suite 375/375. | closed |
| T-60-11 | Denial of Service | `append_chunk` raising into a live decision | high | mitigate | `review_decision.py:329-336` — `try/except Exception` (not `OSError`-only) wraps the `append_chunk` call, matching `append_chunk`'s own `OSError`-swallow / `WrittenRecordsError`-propagate split. Both `test_append_chunk_raising_oserror_still_returns_the_writes_own_outcome` and the `WrittenRecordsError` variant passing. Bookkeeping cannot reverse a landed write (D-59-10). | closed |
| T-60-12 | Repudiation | a review write missing from the run's artifact | medium | mitigate | `review_decision.py:322-336` — the append happens immediately after `_post_decision` returns, keyed by the caller's own `run_id` via `written_records.written_records_path(run_id)` (`written_records.py:231-241`). `test_three_decisions_under_one_run_id_produce_three_entries_in_one_file` passing. | closed |
| T-60-13 | Tampering | a review outcome word leaking into downstream readers | medium | mitigate | `written_records.py:153-156,193-201` — all seven `REVIEW_OUTCOME_TO_OUTCOME` values are members of the eight-word `ALL_OUTCOMES` set. `test_every_review_outcome_to_outcome_value_is_in_all_outcomes` plus a source-level `set(…) <= ALL_OUTCOMES` assertion both passing. | closed |
| T-60-C-SC | Tampering | npm/pip/cargo installs | low | accept | `ec993d2`, `dddc373` touch no dependency manifest. | closed (accepted) |

### 60-04 — Operator-facing truth and the release

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-60-14 | Repudiation | a hand-edited `wf_review_decision_cloud.json` | high | mitigate | Independently re-verified by regeneration rather than by inspection: `.venv/bin/python scripts/build_cloud_workflows.py` re-run leaves `git status --porcelain n8n/` empty — generator output is byte-identical to the committed JSON. (Orchestrator confirmed the tree was clean afterwards.) The message correction is present at `n8n/code/reviewDecision.js:228-234`; `not_allowlisted` literal count unchanged; `test_review_outcome_parity.py` 7/7. | closed |
| T-60-15 | Spoofing | a gate table implying an authority that no longer exists | medium | mitigate | `README.md:598` and `USAGE.md` rows name the grant and `allow_write_grants`; `grep -c 'ALLOW_REVIEW_SUBMIT'` = 0 in both. | closed |
| T-60-16 | Elevation of Privilege | three-lane grants in the dispatch skills | high | mitigate | `enrich-records/SKILL.md` and `enrich-before-ingest/SKILL.md` both name `"review"` and cite D-60-02; `write_grant.py:683-691`'s `_consequence()` names every lane individually in a per-lane sentence loop. **Carried sub-finding — see below.** | closed |
| T-60-17 | Repudiation | shipping code an operator never receives | medium | mitigate | `git show --stat f3fa305` — `plugin.json` (version bump) and `CHANGELOG.md` (`## [0.35.0]`) are modified in the **same** commit, matching the release checklist. This is the failure mode recorded in memory as "a bumped version stays invisible without the CHANGELOG cut". | closed |
| T-60-D-SC | Tampering | npm/pip/cargo installs | low | accept | `9d514a7`, `f4dd82d`, `f3fa305` touch no dependency manifest. | closed (accepted) |

*Status: closed · closed (accepted) · open*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

### Carried sub-finding on T-60-16 (does not hold the threat open)

`write_grant.py`'s `>1-lane` trailing sentence still hardcodes *"enables enrichment"* for a `lanes`
combination that could omit enrichment. This is the pre-triaged **non-blocking WR-01** finding
already recorded in `60-VERIFICATION.md` — an incompletely-executed plan instruction, not a new
discovery.

It does not affect the per-lane naming this threat's mitigation actually rests on (`_consequence()`
names each lane in its own sentence), and no shipped skill opens a review+contacts-only grant
today, so the wrong sentence is currently unreachable. Recorded here so it does not get lost:
should a review+contacts-only grant ever become reachable, the sentence would misdescribe the
authority being granted, which is exactly the class T-60-15 exists to prevent.

*Reported by the auditor; the orchestrator confirmed the pre-triage in `60-VERIFICATION.md` but did
not independently re-derive the code path.*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-60-01 | T-60-B-SC | No package installed by 60-02 (`56d1143`, `b3c2337`), verified by commit diff. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-60-02 | T-60-04 | Retiring `ALLOW_REVIEW_SUBMIT` removes an out-of-band admin stop. The admin's `allow_write_grants` settings key — re-checked on **every** arm at `n8n_arming.py:237-256` — replaces it, and `n8n_arming.disarm` stays deliberately ungated so nothing can strand an armed backend. A kill switch on *disarm* would be worse than no kill switch at all. | D-60-04, re-confirmed this audit | 2026-09-03 |
| AR-60-03 | T-60-C-SC | No package installed by 60-03 (`ec993d2`, `dddc373`), verified by commit diff. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-60-04 | T-60-D-SC | No package installed by 60-04 (`9d514a7`, `f4dd82d`, `f3fa305`), verified by commit diff. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

---

## Awaiting Armed Run — corroboration, not closure

`60-VERIFICATION.md` is `human_needed` and `60-UAT.md` holds two `[pending]` items. **Neither gates
any threat in this register.** Every mitigation above is a deterministic client-side control fully
exercised by stub-transport tests, and the disarm path fails loud (`DISARM_FAILED`) rather than
passing silently on a live divergence. Recorded so the distinction is not lost:

1. **Live approve-and-refetch** — open a grant on one real flagged record, approve through
   review-triage, confirm via `verify_decision`'s post-PATCH refetch. Corroborates T-60-01,
   T-60-05 and T-60-07: that the arm/scope mechanics produce a **landed, verified** write on a real
   backend, not merely a correctly-shaped PUT/POST against a stub.
2. **`verify_live_write_safety.py --expectation disarmed`** after any armed review batch.
   Corroborates T-60-06, T-60-09 and T-60-18: that a real deployed workflow actually reads back
   disarmed once the guaranteed-disarm path has run — not merely that the path was called.

This is the honest shape of the limit: the code-level control is verified, the live behaviour is
not yet observed, and the two are not the same claim.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 23 | 23 (19 mitigation-verified, 4 accepted) | 0 | `gsd-security-auditor`, L1 grep-and-read depth per `asvs_level: 1` |

**Audit depth, stated honestly.** `asvs_level: 1`. Mitigations were checked by reading the cited
file and line and by re-running the named tests live; T-60-14 was checked by **regenerating** the
workflow JSON and observing an empty diff, which is stronger than reading it. This is not an L2
boundary-placement review or an L3 end-to-end trace, and it is not a substitute for the armed run
above. Deeper means `security_asvs_level: 2` and a re-run.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03
