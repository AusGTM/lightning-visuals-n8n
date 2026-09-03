---
phase: "53"
slug: "operator-openable-write-grant"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity
threats_open: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 53 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03.** Phase 53 shipped without a SECURITY.md because the
> `verify:post` secure-phase hook was skipped — `workflow.security_enforcement` was absent from
> `.planning/config.json` and therefore **defaulted to enabled**. The key is now set explicitly.
> All four plans carry plan-time `<threat_model>` blocks (`register_authored_at_plan_time: true`),
> so this is a verification pass, not retroactive-STRIDE.

---

## Trust Boundaries

Consolidated across all four plans.

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator conversation → grant object | The grant is a value Claude holds and hands back; **the settings key, not the object, is authority** | a JSON-shaped grant dict, never persisted |
| `operator.local.json` → authority decision | The admin's key is re-read fresh on every arm | one JSON boolean |
| plugin → n8n workflow content | The arm rewrites write-safety declarations in a live workflow | write-safety flag values, record allowlists |
| headless cron environment → arm authority | `ALLOW_N8N_ARM` is unchanged for `scheduled_arm.py` | a shell environment variable |
| previous session's leftover state → this session's grant | A session that died armed leaves a live allowlist; guardrail A is the only check | live write-safety read (flags, allowlists) |
| send outcome → grant state | The disarm verdict decides whether the run may continue | disarm success/failure verdict |
| rate table and balances → the operator's yes | The envelope is what consent is given against | provider balances, Anthropic cost estimate, execution projection |
| grant → dispatch arm (`authorize_send`) | The one bridge; must not widen the allowlist | workflow id, boolean armed decision — **never a record list** |
| skill prose → operator behaviour | Skills are the operator's instructions | N/A (documentation, not data) |
| operator walk → the claim that G-2 is closed | No automated test can prove Claude-Desktop reachability | a real HubSpot write, real provider credits |

---

## Threat Register

28 threats across four plans. Every mitigation was verified by reading the cited source **at its
current location** — the plans' line numbers have drifted as phases 54, 57, 60, 61 and 62 extended
the same files — and by running the pinned suites.

### 53-01 — End-to-end grant authority (interactive path)

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-53-01 | Elevation of Privilege | forged grant dict | high | mitigate | `n8n_arming.py:237-247` — with a grant present, authority is `config_gate.write_grants_enabled(config)` **re-read from config**, never a property of the grant. Refuses naming the key and file when absent. `test_write_grant.py::test_a_grant_presented_against_a_config_without_the_key_refuses` passes. | closed |
| T-53-02 | Elevation of Privilege | settings key parsed loosely | high | mitigate | `config_gate.py:107-120` — `write_grants_enabled` uses `is True` identity comparison, with an explicit comment that `bool` is an `int` subclass. Sixteen near-miss values pinned refusing across `test_every_near_miss_settings_value_refuses_the_arm`/`_the_plan`; mutation-verified — replacing `is True` with `bool()` reddens 16 tests. | closed |
| T-53-03 | Tampering | headless path widened by accident | high | mitigate | `arm_for_dispatch(..., grant=None)` keyword-default at `n8n_arming.py:313`; `scheduled_arm.py` unedited and `test_scheduled_arm.py` passes unchanged (re-run during this audit). | closed |
| T-53-04 | Denial of Service | disarm made harder | **critical** | mitigate | `n8n_arming.py:478-514` — `disarm()` reads no config, no grant and no env var, confirmed by direct read of current source. `test_control_arming.py:133::test_the_disarm_is_NOT_gated_on_the_kill_switch` present and passing. The escape hatch cannot be gated shut. | closed |
| T-53-05 | Repudiation | a gate test passing while its claim is false | medium | mitigate | `test_control_arming.py:89-119` — test renamed to `test_the_probe_and_the_arm_gates_HEADLESS_branch_use_the_same_comparison`; docstring records the three-way split, D-53-01 and the date. Verified by direct read. | closed |
| T-53-06 | Information Disclosure | a config value echoed in a refusal string | medium | mitigate | `test_write_grant.py::test_no_configured_value_reaches_any_refusal_string` present and passing. | closed |
| T-53-SC | Tampering | npm/pip/cargo installs | low | accept | `operator-claude-plugin/requirements.txt` last touched by `460c048` (Phase 23) — unchanged through 53 and every later phase, verified via `git log`. | closed (accepted) |

### 53-02 — Envelope, lifetime, and the two guardrails

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-53-07 | Elevation of Privilege | opening a grant over an already-armed backend | high | mitigate | `write_grant.py:1766-1881` — `guardrail_a()` / `read_live_write_state()` is `plan_grant`'s **mandatory** preflight; refuses on any enabled flag, an unreadable workflow, or disagreeing nodes. `test_write_grant_guardrails.py:186::test_an_open_over_a_live_armed_backend_refuses_and_names_what_it_found` passing. | closed |
| T-53-08 | Denial of Service | unbounded run over unknown disarm state | high | mitigate | `write_grant.py:1630,1919` — two **consecutive** disarm failures, or a live pre-flight, close the grant; one failure alone does not. `test_one_failure_then_a_verified_disarm_leaves_the_grant_open_and_disarms_nothing_extra` passing. | closed |
| T-53-08b | Elevation of Privilege | grant closed while writes are still live | **critical** | mitigate | `write_grant.py:1882` — `_close_with_disarm` calls the **ungated** `n8n_arming.disarm`, carries its verdict, and closes either way. `test_write_grant_guardrails.py:465::test_the_grant_closes_even_when_the_closing_disarm_itself_fails` passing. | closed |
| T-53-09 | Spoofing | an unreadable balance read as headroom | medium | mitigate | `envelope()` reuses `cost_guard.compare`'s tri-state unchanged; `test_an_unreadable_provider_balance_reads_unconfirmed_never_as_headroom` passing. | closed |
| T-53-10 | Repudiation | a ceiling figure read as a guard | medium | mitigate | `write_grant.py:590-677` — `_envelope_block` states disclosure-not-constraint in the operator-facing text; `test_the_block_says_the_ceiling_discloses_rather_than_constrains` passing. | closed |
| T-53-11 | Tampering | a revocation that does not bite | high | mitigate | `check_before_send` refuses the **next** send; `dispatch_plan` has no grant hook, so a running dispatch finishes. Tested and documented rather than claimed away: `test_write_grant.py:2328::test_a_revocation_midway_does_not_stop_a_running_dispatch` and `:2412::test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against` both passing. See AR-53-05. | closed |
| T-53-12 | Elevation of Privilege | a guardrail switched off | high | mitigate | Neither guardrail reads an env var or a config toggle; `preflight=None` runs guardrail A by default and a non-callable raises `TypeError`. `test_neither_guardrail_reads_an_environment_variable_or_a_disabling_config_key` passing. | closed |
| T-53-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed by this plan. | closed (accepted) |

### 53-03 — Operator-reachable surface

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-53-13 | Elevation of Privilege | the example config shipping enabled | high | mitigate | Verified live: `operator.local.example.json`'s `allow_write_grants` reads `False` (a JSON boolean). `test_the_shipped_example_does_not_enable_write_grants` passing. | closed |
| T-53-14 | Spoofing | the settings key mistaken for a capability | medium | mitigate | Verified live by Python import: `allow_write_grants` is absent from both `config_gate.CAPABILITY_KEYS` and `_CAPABILITY_DESCRIPTIONS`. `test_the_settings_key_is_not_a_capability_row` passing. | closed |
| T-53-15 | Elevation of Privilege | a grant opened without an explicit yes | **critical** | mitigate | `open_grant`'s `confirmation` parameter has **no default** (omitting it is a `TypeError`); only the exact string `yes` proceeds, pinned behaviourally against `control_actions.execute_action` through one shared near-miss list. Tests passing. | closed |
| T-53-16 | Tampering | the bridge widening the allowlist to the grant's whole set | high | mitigate | `write_grant.py:1417` — `authorize_send` returns a workflow id and a bool, **never a record list**. `test_the_armed_allowlist_is_the_SENDS_records_never_the_grants_whole_set` passing. | closed |
| T-53-17 | Denial of Service | an existing operator's file reading as broken | medium | mitigate | Overall status stays derived from capability readiness only. `test_a_file_without_the_key_reports_not_enabled_and_keeps_its_status` passing. | closed |
| T-53-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed by this plan. | closed (accepted) |

### 53-04 — Skills, docs, release, and the operator walk

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-53-18 | Tampering | a traded protection lost without a record | high | mitigate | D-53-05 recorded in `test_enrich_before_ingest_skill_contract.py`'s ordering pin (date, author, and the trade in prose) as one deliberate edit; diff read-back confirms **no test function or assert was deleted** — 13 removed lines, all prose. | closed |
| T-53-18b | Elevation of Privilege | the collapse widening WHAT is covered, not just WHEN | **critical** | mitigate | The scope check lives inside `arm_for_dispatch` (verified live under 53-01). `test_the_skill_never_widens_a_window_to_the_grants_whole_record_set` and `test_the_grant_branch_shows_the_window_scoped_to_this_sends_records` both passing. | closed |
| T-53-19 | Spoofing | a skill claiming the safety went away with the question | medium | mitigate | Each lane skill states what a grant does **not** remove — `README.md:598`, `backend-control/SKILL.md:95-107`, both verified live. Pinned by the skill-contract tests. | closed |
| T-53-20 | Repudiation | shipped work an operator never receives | medium | mitigate | Version bump (0.15.0) plus CHANGELOG cut in commit `7ceca30`, with an automated consistency check. The plugin has since progressed through further releases (0.36.0/0.37.0 verified live), confirming the release path stayed live. | closed |
| T-53-21 | Elevation of Privilege | a live write during the walk | high | mitigate | The checkpoint was `gate="blocking"` with `autonomous: false`. Discharged and independently verified: `53-VERIFICATION.md` (2026-09-02) records walk run 3 (2026-08-29) carrying a real batch through grant-open → arm → dispatch → HubSpot write → disarm; one real create landed on a record the operator chose (`josh@seriesfutsal.com` → `348695309760`), confirmed by an independent post-walk read, and `verify_live_write_safety.py --expectation disarmed` returned PASS. | closed |
| T-53-22 | Information Disclosure | the admin's settings value quoted back in chat | medium | mitigate | `init_check` reports enabled/not-enabled, never the raw value (the T-27-12 convention). The `test_no_configured_value_reaches_any_refusal_string` class of tests passing. | closed |
| T-53-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed by this plan. | closed (accepted) |

*Status: closed · closed (accepted) · open*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-53-01 | T-53-SC (53-01) | No package installed by 53-01; `operator-claude-plugin/requirements.txt` unmodified since `460c048` (Phase 23). | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-53-02 | T-53-SC (53-02) | No package installed by 53-02. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-53-03 | T-53-SC (53-03) | No package installed by 53-03. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-53-04 | T-53-SC (53-04) | No package installed by 53-04. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

**Residual, cross-referenced rather than double-counted (AR-53-05 / T-53-11).** GRANT-05's
revocation bites at the **send** boundary, not the chunk boundary: a running `dispatch_plan`
completes its remaining chunks after a revoke. This is an operator-accepted design limitation
re-scoped 2026-08-25. Its disposition in the register is `mitigate`-by-disclosure-and-test, not
`accept`, so it is listed here as a residual for visibility only and is **not** counted in the
accepted total.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 28 | 28 (24 mitigation-verified, 4 accepted) | 0 | `gsd-security-auditor`, L1 grep-and-read depth per `asvs_level: 1` |

**Audit depth, stated honestly.** `asvs_level: 1` — each mitigation was checked by reading the
cited file at its **current** line (plan-time line numbers have drifted) and by re-running the
pinned suites, which are green. This is not an L2 boundary-placement review or an L3 end-to-end
trace. Deeper means `security_asvs_level: 2` and a re-run.

**Worth recording about the method.** Two of this phase's strongest controls are not assertions
but *mutation* evidence: T-53-02's `is True` identity comparison was confirmed load-bearing by
observing that replacing it with `bool()` reddens 16 tests, and T-53-18's prose-only diff was
confirmed by read-back to have deleted no test function or assert. A control that has been shown
to fail when removed is worth more than one that merely passes.

---

## Bookkeeping Finding (not a security gap)

`53-04-SUMMARY.md`'s frontmatter still reads `status: blocked-on-checkpoint`, with coverage item
G8 (the operator walk) marked `OUTSTANDING`. That checkpoint **was** discharged and independently
verified — `53-VERIFICATION.md` (2026-09-02) and `53-WALK-RECORD-2.md` both record walk run 3 on
2026-08-29. This audit relied on the verification record rather than the stale summary.

Left as-is rather than edited here, because a security audit is the wrong instrument for
reconciling a summary's frontmatter, and this is the same record-lag class already logged against
phases 54, 28 and 57-05. Flagged so a future reader of `53-04-SUMMARY.md` alone is not misled.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03
