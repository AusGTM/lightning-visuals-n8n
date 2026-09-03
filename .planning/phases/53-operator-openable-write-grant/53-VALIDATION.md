---
phase: "53"
slug: "operator-openable-write-grant"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: false
wave_0_complete: true
created: "2026-09-03"
---

# Phase 53 — Validation Strategy

> Reconstructed from artifacts (State B) on 2026-09-03, **after** the phase closed, as part of a
> cross-phase sweep. Phase 53 ran without a VALIDATION.md because `workflow.nyquist_validation`
> was absent from `.planning/config.json` and therefore defaulted to **enabled** — the
> `verify:post` nyquist hook was active and silently skipped for ~60 phases. The key is now set
> explicitly to `true`. This file closes the gap for 53; it does not reopen the phase.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) — this phase is entirely operator-plugin Python; no n8n code nodes changed |
| **Config file** | none — tests are discovered by convention |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_write_grant_guardrails.py operator-claude-plugin/tests/test_write_grant_surface.py operator-claude-plugin/tests/test_control_arming.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` and `node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | quick ~1s · full python ~20s · node ~4s |

**Two invocation traps, both load-bearing:** use `.venv/bin/python`, never bare `python3` — the
system interpreter lacks this project's dependencies. And use the **glob** form
`node --test tests/n8n/*.test.mjs`; the directory form is broken on node 24.

**Path note:** this phase's implementation lives at `operator-claude-plugin/scripts/write_grant.py`
(not `src/`). Every line citation below uses that path.

---

## Sampling Rate

- **After every task commit:** the quick run command above (~1s)
- **After every plan wave:** full suite
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** ~1s for the quick set

At this validation pass the suites read **3982 passed / 154 skipped** (pytest) and
**862 pass / 0 fail** (node). The phase-53 grant cluster is **261 passed** (independently re-run by
this record's author: 261 passed in 0.67s); the other 13 files named across 53's `<verify>` blocks
run **406 passed** together.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 53-01 T1 | 01 | 1 | GRANT authority — `config_gate.WRITE_GRANT_SETTINGS_KEY` / `write_grants_enabled` is the ONE identity comparison against JSON `true`; `_arm_gate` three-way split, no-grant branch unchanged on `ALLOW_N8N_ARM` | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_control_arming.py operator-claude-plugin/tests/test_scheduled_arm.py operator-claude-plugin/tests/test_control_flag_parity.py -q` | ✅ | ✅ green |
| 53-01 T2 | 01 | 1 | GRANT-03 scope enforced **in `arm_for_dispatch` itself**, before any transport is constructed — not only in a helper a lane skill is supposed to call | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_chunking.py -q` | ✅ | ✅ green — `test_a_record_outside_the_grant_is_refused_before_any_transport_call` (`:210`) and the domain twin (`:227`) call the un-bypassable path directly |
| 53-01 T3 | 01 | 1 | Near-miss settings values (`"true"`, `1`, truthy non-boolean) all refuse the arm | unit (parametrised) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k near_miss -q` | ✅ | ✅ green (`test_every_near_miss_settings_value_refuses_the_arm`, `:1039`) |
| 53-02 T1 | 02 | 2 | GRANT-02 envelope — four figures plus a rendered block built only from `cost_guard` + `chunking`, no second cost model; each figure labelled measured / projected / unconfigured | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_cost_guard.py operator-claude-plugin/tests/test_preview_enrichment.py -q` | ✅ | ✅ green — **see drift note D1: the ceiling is now binding, and the test says so** |
| 53-02 T2 | 02 | 2 | GRANT-04 close vocabulary — exactly five reasons pinned **by name** (not by `len()`); `close_grant` RAISES on free text | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -q` | ✅ | ✅ green (`GRANT_04_REASONS` set-equality at `:2230`; `test_close_grant_refuses_a_free_text_reason` at `:2254`) |
| 53-02 T3 | 02 | 2 | Guardrails A (offers, never acts) and B (acts, closing its own window) — the documented asymmetry, the two-failure bound, close-either-way on a failed closing disarm | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_guardrails.py operator-claude-plugin/tests/test_write_grant.py -q` | ✅ | ✅ green (35 tests, including `test_the_refusal_offers_a_disarm_and_does_not_perform_one`, `test_the_grant_closes_even_when_the_closing_disarm_itself_fails`, `test_nothing_a_guardrail_writes_reaches_disk`) |
| 53-03 T1 | 03 | 3 | D-53-01 — admin-set switches reported in their OWN `settings` section, never as capability rows, and never moving overall status; a READY file predating the key still reads READY | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_init_check.py operator-claude-plugin/tests/test_config_gate.py operator-claude-plugin/tests/test_plugin_manifest.py -q` | ✅ | ✅ green |
| 53-03 T2 | 03 | 3 | GRANT-05 — `revoke_grant` reachable by name, idempotent **and** reason-preserving; bites at the *next send* | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_surface.py operator-claude-plugin/tests/test_control_surface.py operator-claude-plugin/tests/test_control_arming.py -q` | ✅ | ✅ green (`test_revoking_a_grant_a_guardrail_closed_does_not_overwrite_its_close_reason`, `:147`) |
| 53-03 T3 | 03 | 3 | Must-not-lose invariants — the armed allowlist is the **send's** records, never the grant's whole set; a granted arm still goes THROUGH `apply_mutation`; the shared dispatch loop stays grant-unaware; nothing reaches disk or env | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_surface.py operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_write_grant_guardrails.py operator-claude-plugin/tests/test_control_pipeline.py -q` | ✅ | ✅ green (`test_the_armed_allowlist_is_the_SENDS_records_never_the_grants_whole_set` `:279`; `test_a_granted_arm_still_goes_THROUGH_apply_mutation_never_around_it` `:360` — a behavioural pin with a monkeypatched recorder, not a grep) |
| 53-04 T1 | 04 | 4 | The grant conditional lives inside **each** lane skill's own numbered arming step, with that lane's REAL dispatch; the D-53-05 trade recorded in the pin it replaced | unit (doc-contract) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_enrich_skill_contract.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py operator-claude-plugin/tests/test_plugin_manifest.py operator-claude-plugin/tests/test_status_skill.py operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` | ✅ | ✅ green — **contact-upload is covered too**, parametrised in `test_write_grant.py` (`:2588`/`:2683`/`:2709`) and in `test_skill_sequence_coverage.py`; **see drift note D2** |
| 53-04 T2 | 04 | 4 | T-53-20 mitigation — version bump and CHANGELOG cut in one commit, checked automatically | inline | the `<automated>` `python -c` release-consistency one-liner in `53-04-PLAN.md` | n/a (inline) | ✅ green → `release consistency ok 0.37.0` (version-agnostic; still passes at 0.37.0, ten releases past the 0.15.0 this phase cut) |
| 53 headline | — | — | **GRANT-01** — an operator-opened, bounded, revocable session grant carrying a batch through ingest → enrichment → HubSpot write, asked once, no terminal, no loss of record scoping | manual (operator walk) | none — see Manual-Only | n/a | ✅ passed live, walk run 3, 2026-08-29 (`53-VERIFICATION.md`) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**No test file named in any 53 PLAN is absent at HEAD.** All 14 were checked individually. Phase 53
has no analogue of 63's `tests/test_judge_model_routing.py` — there was no DROP branch, so the
absent-file question does not arise here in either of its two forms.

---

## Wave 0 Requirements

None. Every requirement was met by extending pytest suites that already existed
(`test_control_arming.py`, `test_control_surface.py`, `test_init_check.py`,
`test_enrich_*_skill_contract.py`); the four files this phase **created**
(`test_write_grant.py`, `_guardrails`, `_surface`, and 53-03's surface file) needed no new
framework, fixture infrastructure or runner. `wave_0_complete: true` by vacuity.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A grant opened by an operator carries a real batch through ingest → enrichment → a **real HubSpot write**, asked once, with record scoping never widened, and a verified disarm afterwards | GRANT-01 (the phase's headline claim) | `53-04-PLAN.md` states it directly: *"The walk cannot be automated and is the phase's only evidence for its headline claim."* A grant that carries a real batch to a real HubSpot write cannot be certified by reading source — the write must land in the portal. It costs real money (walk run 3: 4 n8n executions, ~1 Lusha and ~1.08 ZoomInfo credit, ~$0.07 Anthropic, 1 HubSpot write) and is not idempotent, so it can never be a suite test. | Follow `53-WALK-BRIEF-OPERATOR.md` steps 1–7. Confirm the write **independently of the response body**: re-run an unarmed match on the created contact and require `auto_matched: 1` where the pre-walk probe returned `unmatched: 1`. Then `verify_live_write_safety.py --expectation disarmed` must print `VERDICT: disarmed PASS`. Record: `53-WALK-RECORD-2.md` § "WALK RUN 3". |
| The same flow with **no terminal access** — the operator's own chair against an *installed* plugin build | GRANT-01's "no terminal" clause | Only reachable from Claude Desktop against a marketplace-installed plugin; by construction there is no process a test runner could drive. | Walk run 4 (2026-08-30, `53-WALK-RECORD-3.md`) did this from the operator's chair against installed 0.28.6 and **discharged the installed-plugin half**. It then FAILED at FINDING D — upstream of the grant, before step 3, so it exercised none of this phase's properties; its cause was closed by Phase 61-03 (`linkedin_url` as a third identity group, pinned by `tests/n8n/columnMapIdentityParity.test.mjs`). **The terminal-access half was never re-walked to a completed write and remains a recorded, undischarged caveat.** To discharge: re-run the walk brief end-to-end from Claude Desktop on a current build. |

---

## Why `nyquist_compliant` is false

The phase's headline requirement, GRANT-01, is evidenced by a live operator walk and by nothing in
either suite — and correctly so: a grant carrying a real batch to a real HubSpot write cannot be
certified by reading source, and an in-suite fake of it would prove the wrong thing. Its supporting
mechanics (authority, scope, envelope, close vocabulary, revocation, both guardrails, the operator
surface, the skill contracts) are **exhaustively** suite-covered — 261 tests in the grant cluster
alone, including negative and non-bypassable-path assertions — but the end-to-end claim is not.

Separately, one clause of GRANT-01 — "no terminal" — is **not fully discharged even manually**: run
3 had terminal access, and run 4 (no terminal) failed upstream before the grant opened. That is a
recorded standing caveat in `53-VERIFICATION.md`, not a suite gap, and it is the second reason this
flag stays false.

Setting `nyquist_compliant: true` would claim every requirement has suite verification. It does
not, and should not.

---

## Drift notes — cited artifacts that have moved since Phase 53 closed

Verified at HEAD on 2026-09-03. **All three drifts are already annotated in the implementation and
pinned by current tests; no map row above describes retired behaviour as current.**

- **D1 — D-53-02 SUPERSEDED by D-57-00.** 53-02 recorded the envelope's computed ceiling as
  *disclosure, not constraint*. Phase 57 (RUN-05) made it a **binding preflight refusal and a
  pre-send mid-run stop**. At HEAD `operator-claude-plugin/scripts/write_grant.py:135` carries an
  explicit `D-57-00 SUPERSEDES D-53-02` block (re-read independently by this record's author), and
  `_CEILING_CONSTRAINT` reads *"a batch that would exceed it is refused, not merely disclosed."*
  Pinned by `test_write_grant.py:1408`, whose docstring names the supersession. The 53-02 T1 row
  above is green against **current** semantics.
- **D2 — D-53-05's pre-emptive disclosure RETIRED by 59-03.** The sentence `_consequence()`
  rendered at the yes (*the HubSpot write is authorized before the enriched preview exists*) is no
  longer operator-facing; a pointer to the post-run written-records artifact replaced it (D-59-07,
  `write_grant.py:91-100`). **The D-53-05 trade itself is unchanged** — one grant still spans both
  lanes, scoping still record-bound. Pinned positively at
  `test_enrich_before_ingest_skill_contract.py:257`/`:263` and, importantly, **negatively** at
  `:271` — the retired warning must never reappear.
- **D3 — a third drift, NOT named in the sweep brief: 53-01's "review deliberately excluded" is
  REVERSED.** Phase 60 (D-60-01 / D-60-05) made `review` a third grantable lane — confirmed at
  HEAD by this record's author: `write_grant.py:83` `REVIEW_LANE = "review"`, `:89` mapping it to
  `REVIEW_WORKFLOW_NAME`, with the reversal recorded in a comment at `:105`. The exclusion had cost
  two manual admin round trips per flagged record. Guarded by
  `test_write_grant.py::test_the_review_lane_is_grantable_with_flag_separation_intact` (`:660`) and
  by the review-batch block in `test_write_grant_guardrails.py` (`:614`–`:867`). **Read
  53-01-SUMMARY's `provides` list as history, not as inventory.**

---

## Record-lag noted (not a gap)

**RESOLVED 2026-09-03 by operator grant — the frontmatter now reads `status: complete` with G8 `DISCHARGED`; the finding below is kept as the record of what was wrong.** `53-04-SUMMARY.md` frontmatter still reads `status: blocked-on-checkpoint` with **G8 OUTSTANDING**.
The checkpoint **was** discharged — `53-VERIFICATION.md` (`status: passed`, `gaps: []`,
`verification_basis: operator_walk`), `53-WALK-RECORD-2.md` § "WALK RUN 3", walk run 3 on
2026-08-29, and the phase marked complete in `ROADMAP.md` the same day. This is known record-lag,
already flagged in `53-SECURITY.md`. Recorded here so a later reader does not mistake a stale
frontmatter line for an open item; **no action taken — the phase is complete and is not reopened.**

---

## Validation Audit 2026-09-03

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 0 |
| Reclassified manual-only | 2 |
| Escalated | 0 |

**Both gaps are the two Manual-Only rows** (GRANT-01 end-to-end, and its "no terminal" clause).
Neither is suite-fillable and neither was filled — see "Why `nyquist_compliant` is false". No guard
test was written by this pass, deliberately: an in-suite simulation of a live HubSpot write would
prove the wrong thing, which is the failure mode the `sweep-trigger-llm-free` record exists to
warn about.

**No suite-fillable gap was found, and that conclusion was reached adversarially rather than by
deference.** Every command in every 53 `<verify>` block was executed at HEAD, not read. All 14
named test files were confirmed present individually. The four properties most likely to be
verified by a weaker proxy than the requirement demands were each checked for the strong form, and
each had it:

- scope is asserted against `arm_for_dispatch` **directly** — the un-bypassable path — not only
  through the `authorize_send` bridge;
- `apply_mutation` routing is pinned with a monkeypatched recorder, not a grep that would pass on
  a call never made;
- `GRANT_04_REASONS` is pinned by **set equality on names**, not by a `len()` that would prove
  nothing;
- the retired D-53-05 warning carries a **negative** assertion against its return, not merely a
  positive one on its replacement.

**One optional guard is named but NOT filed as a Phase 53 obligation,** because it guards Phase
60's widening rather than 53's contract: nothing currently asserts that *adding a key to `LANES`
does not by itself make that lane grantable*. If wanted, it would be
`operator-claude-plugin/tests/test_write_grant.py::test_a_lane_added_to_LANES_is_not_grantable_without_its_own_authority_check`
— monkeypatch a synthetic key into `write_grant.LANES` and assert `plan_grant` either refuses it or
routes it through the same settings-key/flag-separation check the review lane goes through,
asserting *the mechanism is per-lane* rather than the current membership or a lane count. Proving
it is a real guard rather than a tautology would mean temporarily deleting the flag-separation
branch, confirming the test reddens with its intended message, then restoring and confirming green.

**Nothing was written by the audit pass itself** — it ran read-only alongside two sibling auditors,
and no implementation file was modified.

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify or a recorded manual-only justification
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none needed — existing infrastructure sufficed)
- [x] No watch-mode flags
- [x] Feedback latency < 5s for the quick set (~1s measured)
- [x] Every cited decision re-verified at HEAD; three drifts recorded (D1–D3)
- [ ] `nyquist_compliant: true` — deliberately NOT set; see "Why `nyquist_compliant` is false"

**Approval:** approved 2026-09-03 (partial — 2 manual-only by nature)
