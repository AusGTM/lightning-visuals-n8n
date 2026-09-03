---
phase: "50"
slug: "derived-tier-property"
status: verified
# Found 3 OPEN at high on 2026-09-03. FIXED the same day (see "Resolution" below) —
# the missing guard was wired into all five write paths and pinned by a coverage test.
threats_open: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 50 — Security

> Retroactive secure-phase run, 2026-09-03. All six plans carry plan-time `<threat_model>` blocks.
> **43 threats. The audit found 40 closed and 3 open at `high` — the only blocking count in the
> round, and the only finding that was a genuinely missing code control rather than a documentation
> or authority question. All three were FIXED the same day; see the Resolution below.**

---

## T-50-11, T-50-27, T-50-36 — one root cause, three threat IDs, FIXED

**A control the register asserts, that has never existed on the paths it names.**

All three threats cite the identical mitigation: *"`assert_no_secrets` applied … before it is
written to a committed path."* The guard is real — `src/guards.py:58` — and is genuinely called by
**seven** scripts. **None of them is one of the five these threats name.**

Independently confirmed by the orchestrator, not taken from the audit:

```
$ grep -rln "assert_no_secrets" scripts/ src/
scripts/check_schema_drift.py            scripts/probe_number_floor_in_formula.py
scripts/check_tier_null_propagation.py   scripts/snapshot_hubspot_schema.py
scripts/derive_orphan_candidates.py      scripts/sweep_tier_dependents.py
scripts/probe_enum_in_formula.py         src/guards.py
```

The five write paths the register covers — `check_tier_derived_parity.py`,
`apply_fit_score_formula.py`, `rollback_property_migration.py`, `put_hubspot_flow.py`,
`backfill_anti_icp_flag_num.py` — return **0** matches each. Corroborating this from the other
direction: `src/guards.py`'s own docstring inventories the guard's historical call sites, and none
of the five appears there either. **This is never-present, not a regression.**

**What is and is not at risk.** Every committed artifact was manually scanned during the audit —
`50-TIER-PARITY-EVIDENCE.md`, `50-RETIREMENT-RECORD.md`, `50-MIRROR-SCOPE.md`,
`50-MIRROR-BACKFILL.md` and the refreshed `.after.json` snapshots — grepping for `Authorization:`,
`bearer `, `pat-na1-` and the token env-var pattern. **No live secret was found.** The exposure is
prospective: `check_tier_derived_parity.py` in particular will be re-run by every future phase that
touches tier scoring, and there is nothing standing between a future misconfigured run and a
committed file.

**The fix was small because the canonical implementation already existed** — the guard, its tests
and its call convention were all already in the repo; only the call sites were absent.

### Resolution — 2026-09-03, operator directed the fix rather than an acceptance

`src/guards.py` gained two wrappers that make the guarded path the **shortest** path, so a future
author reaches for it by default rather than reassembling a serialize-check-emit trio:

- `emit_json(obj, **kwargs)` — `json.dumps` → `assert_no_secrets` → `print`. stdout is guarded
  because these scripts' output is routinely captured into a committed run record: a token
  reaching stdout reaches git.
- `write_guarded(path, text)` — `assert_no_secrets` → `write_text`, checking **before** the write
  so a leak raises with nothing on disk rather than leaving a poisoned artifact behind.

All five scripts now route through them — 9 stdout sites and 3 file sites replaced, with **zero**
remaining `print(json.dumps(...))` or bare `.write_text(...)` calls in any of them.

**Pinned so a sixth script cannot repeat it.** `tests/test_guarded_emit_coverage.py` (17 tests)
asserts, per script, that a guarded emitter is imported and that no raw emit call survives — by
**AST walk**, not substring search. It also proves the guard it pins still has teeth, since three
coverage assertions could otherwise pass against a hollowed-out guard.

**Verified behaviourally, not just by import.** With a sentinel token in the environment,
`emit_json` refused with *"serializer leaked the bearer token value"*, and `write_guarded` refused
an `Authorization` header with `file_exists=False` — proving the check precedes the write. Clean
payloads pass through unchanged. Full suite after the fix: **3982 passed / 154 skipped / 0 failed**
(up 17).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| repo scripts → HubSpot Properties/Automation API | A live private-app bearer token crosses here to create, PATCH, **archive or delete** portal schema | live-write payloads, an irreversible archive/delete call |
| repo scripts → HubSpot CRM API | Company-record reads plus the phase's disclosed write deviations | company ids, tier/score/flag values |
| env → per-script two-key write gates | `DRY_RUN` plus a dedicated `ALLOW_*` key decides whether any armed step executes | write authorization state |
| operator decision → irreversible act | `checkpoint:decision` gates precede the archive and the WF1 deletion | authorization to proceed |
| script output → committed git artifacts | Probe/sweep/evidence/snapshot files are committed to the repo | company ids, tier values, workflow ids — unguarded on five write paths until the 2026-09-03 fix; now routed through `src.guards`' checked emitters |
| repo → n8n Cloud API | The deploy PUT and bounce change what production actually runs | workflow definitions, veto-mirror wiring |

---

## Threat Register

### 50-01 — Null probe, formula declaration, tracer

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-50-01 | Information Disclosure | probe snapshots | high | mitigate | `_assert_no_secrets` defined and called at `check_tier_null_propagation.py:82,317` before every write. **This script does have the guard** — which is what makes its absence elsewhere a gap rather than a convention. | closed |
| T-50-02 | Tampering | live-write gate | high | mitigate | Two-key gate: `DRY_RUN=="false"` **and** `ALLOW_TIER_NULL_PROBE=="true"` (`:77-78`). | closed |
| T-50-03 | Tampering | wrong-portal execution | high | mitigate | `_portal_ok()` / `EXPECTED_PORTAL_ID="22617666"` asserted before any call (`:49,70,336-337`). | closed |
| T-50-04 | Denial of Service | disposable-object teardown | medium | mitigate | `finally:` block at `:296` with gone-confirmation re-reads. | closed |
| T-50-05 | Tampering | the veto-guard formula shape | high | mitigate → **corrected in-phase** | The originally-pinned shape `coalesce(lv_anti_icp_flag, 0) = 1` was **live-falsified** by Plan 03: 6 of 6 real vetoed companies derived a normal tier instead of `D`, because `lv_anti_icp_flag` is a `booleancheckbox` and a `calculation_equation` cannot read one. Plan 06 replaced it with the numeric mirror; the shipped formula reads `coalesce(lv_anti_icp_flag_num, 0) = 1` (`config/hubspot_properties.yaml:426`). Closed on the **corrected** control. See note below. | closed (corrected) |
| T-50-06 | Elevation of Privilege | the calculated property becoming writable | low | accept | `fieldType: calculation_equation` (`:423`) — HubSpot makes calculated properties `readOnlyValue` platform-wide. See AR-50-01. | closed (accepted) |
| T-50-SC | Tampering | package installs | low | accept | No dependency change. | closed (accepted) |

### 50-02 — Portal dependent sweep

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-50-07 | Information Disclosure | `50-DEPENDENTS-SWEEP.md` | high | mitigate | `_assert_no_secrets` defined and called at `sweep_tier_dependents.py:68,266`. | closed |
| T-50-08 | Tampering | the sweep mutating what it inspects | high | mitigate | `tests/test_sweep_tier_dependents.py:104-109` **AST-walks the module** and asserts no `requests.post/patch/delete` call site exists — structure, not a string search. | closed |
| T-50-09 | Tampering | wrong-portal execution | high | mitigate | Portal guard confirmed. | closed |
| T-50-10 | Repudiation | an undated manual UI check | medium | mitigate | `render_sweep_markdown` emits an explicit `UNCHECKED` placeholder (`:104,159-161`) rather than a blank that could read as done; operator filled it 2026-08-14. | closed |
| T-50-SC | Tampering | package installs | low | accept | No dependency change. | closed (accepted) |

### 50-03 — D-07 parity gate + D-19 census

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| **T-50-11** | **Information Disclosure** | **`50-TIER-PARITY-EVIDENCE.md`** | **high** | **mitigate — NOT PRESENT** | **`assert_no_secrets` does not exist anywhere in `check_tier_derived_parity.py` (0 matches). The artifact is written by `out_path.write_text(text)` (`:748`) and `_append_or_write` (`:619-628`) with no scrubbing step.** | closed (fixed 2026-09-03) |
| T-50-12 | Tampering | a stale parity capture reused | high | mitigate | The population is re-derived live on every invocation via a `HAS_PROPERTY(lv_icp_fit_score)` search — never read from a cached file. | closed |
| T-50-13 | Repudiation | an unreconstructable gate verdict | medium | mitigate | `render_evidence_markdown` (`:294`) produces the full row-level artifact. | closed |
| T-50-14 | Tampering | silent threshold drift | high | mitigate | `tests/test_tier_formula_pin.py` passes at HEAD and includes parametrized **mutation** cases. | closed |
| T-50-15 | Denial of Service | a defect-free report from an empty population | medium | mitigate | `render_parity_markdown` (`:171-186`) raises `ValueError` on `population_count <= 0` **and** on a row/population mismatch — an empty run cannot render as a clean pass. | closed |
| T-50-SC | Tampering | package installs | low | accept | No dependency change. | closed (accepted) |

### 50-04 — D-18 rollback runbook + live drill

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-50-16 | Tampering | the drill re-tiering a real record | high | mitigate | Subject Melbourne Racing Club `9604614548`, tier `C` before and after — value-identical. | closed |
| T-50-17 | Tampering | the drill contaminating D-07 evidence | high | mitigate | The drill subject is not one of the four `KNOWN_STUCK_IDS`. | closed |
| T-50-18 | Repudiation | a rollback path asserted but never exercised | high | mitigate → **mechanism since destroyed** | Proven live 2026-08-14 **while WF1 existed**. Plan 05's D-24 then deleted WF1 entirely. `docs/OPERATOR-TIER-ROLLBACK.md:5-40` carries a dated amendment stating both mechanisms are **"GONE"** and that rollback is now a from-scratch rebuild. Honestly disclosed in-repo. See note below. | closed (see note) |
| T-50-19 | Information Disclosure | drill and runbook docs | high | mitigate | This claim is narrower than T-50-11/27/36 — it asserts the guard only for the **sweep re-run** (which does have it) plus hand-authored docs. Both grepped: 0 hits for token patterns. | closed |
| T-50-20 | Elevation of Privilege | manual enrolment needing portal permission | low | accept | HubSpot's own permission model. **Moot under D-24** — WF1 was deleted, so the surface is gone. See AR-50-02. | closed (accepted, moot) |
| T-50-SC | Tampering | package installs | low | accept | No dependency change. | closed (accepted) |

### 50-05 — Retirement (WF1 deleted, `lv_icp_tier` archived)

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-50-21 | Tampering | an irreversible archive without authority | high | mitigate | A `checkpoint:decision` precedes the archive task, whose `<precondition>` refuses absent a proceed option; the live archive is additionally gated by `DRY_RUN=false` plus an allow-key. | closed |
| T-50-22 | Denial of Service | portal dependents breaking at archive time | high | mitigate | The pre-cutover sweep enumerated dependents, and D-11 escalation **fired** for a real `CANNOT_DELETE_PROPERTY_IN_USE` blocker, resolved by explicit operator decision (D-24) rather than forced through. **Residual:** reports/dashboards remained structurally unscannable — see AR-50-09. | closed |
| T-50-23 | Tampering | the drift comparator reporting deliberate success as damage | high | mitigate | `RETIRED_FLOW_IDS` in `check_schema_drift.py`, with the invariant flipped to must-be-absent per D-24 — an honest, disclosed divergence from the plan's originally-drafted live-AND-disabled shape, matching the actual deletion. 3 pytest cases pass. | closed |
| T-50-24 | Repudiation | an unreconstructable archive outcome | medium | mitigate | `50-RETIREMENT-RECORD.md` present and non-empty. | closed |
| T-50-25 | Tampering | verifying a mutation from its own response body | high | mitigate | Independent re-read confirmed in `apply_fit_score_formula.py:104-110,158-164` and `rollback_property_migration.py`'s `_get_property_live`. | closed |
| T-50-26 | Tampering | a wrong-portal irreversible call | high | mitigate | Portal guard in `apply_fit_score_formula.py:129-132` and the other two writers. | closed |
| **T-50-27** | **Information Disclosure** | **retirement record, refreshed snapshots** | **high** | **mitigate — NOT PRESENT** | **`assert_no_secrets` absent from `apply_fit_score_formula.py`, `rollback_property_migration.py` and `put_hubspot_flow.py` (0 hits each) — the three scripts performing this phase's irreversible live mutations. Committed artifacts manually scanned clean, but no standing mechanism exists for a future run.** | closed (fixed 2026-09-03) |
| T-50-SC | Tampering | package installs | low | accept | No dependency change. | closed (accepted) |

### 50-06 — Numeric veto mirror + uncoalesced formula correction

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-50-28 | Tampering | a backfill widening beyond authorised scope | high | mitigate | `MAX_BACKFILL_RECORDS=10`, `assert_payload_scope`, and a live re-derived target set (`backfill_anti_icp_flag_num.py:46,48,90-137`). | closed |
| T-50-29 | Tampering | two veto serializations drifting apart | high | mitigate | `flagIsSet` is a **single derivation** (`build_cloud_workflows.py:3423-3426`); `anti_icp_flag_properties()` (`src/icp_scoring.py:56-62`); `tests/n8n/antiIcpFlagMirror.test.mjs` green. The mirror cannot diverge from the boolean it mirrors. | closed |
| T-50-30 | Tampering | the HubSpot-native flow becoming a second writer | high | mitigate | `VETO_PROPERTY_NAMES` includes all three veto properties (`test_flow_rubric_conformance.py:359`); guard test passing. | closed |
| T-50-31 | Denial of Service | the mirror silently archived | high | mitigate | `lv_anti_icp_flag_num` is in `DO_NOT_ARCHIVE_COMPANY_PROPERTIES` (`check_schema_drift.py:78-86`) with an offline pin. The formula's only readable input cannot be archived out from under it. | closed |
| T-50-32 | Repudiation | a verdict from an unsettled calculated read | high | mitigate | `50-MIRROR-BACKFILL.md:96-133` — Simtech LED polled 7× at 10s intervals until it settled at `D`; two others polled repeatedly and held. Matches the standing fact that formula edits backfill on a delay: a single read would have been worthless. | closed |
| T-50-33 | Tampering | a stored-but-not-running n8n deploy | high | mitigate | `ALLOW_N8N_DEPLOY` gate plus bounce-and-execution-id proof (`11879`). | closed |
| T-50-34 | Tampering | verifying from a response body | high | mitigate | Per-record independent re-read by design. | closed |
| T-50-35 | Tampering | wrong-portal execution | high | mitigate | Portal guard, 4 hits. | closed |
| **T-50-36** | **Information Disclosure** | **mirror-backfill artifacts, snapshots** | **high** | **mitigate — NOT PRESENT** | **Same root cause: `assert_no_secrets` absent from `backfill_anti_icp_flag_num.py` and the same three writers. Artifacts manually scanned clean; no standing control.** | closed (fixed 2026-09-03) |
| T-50-37 | Repudiation | a gate passed by redefining the exception list | high | mitigate | `KNOWN_STUCK_IDS` verified unchanged — exactly the four pre-registered ids. The gate could not be passed by widening its own exceptions. | closed |
| T-50-SC | Tampering | package installs | low | accept | No dependency change. | closed (accepted) |

*Status: closed · closed (accepted) · closed (corrected) · **open***

---

## Disposition Notes

**T-50-05 — corrected in-phase, not silently passed.** The register's original formula shape was
proven broken by the phase's own gate run: six of six real vetoed companies derived a workable tier
instead of `D`. That is the repo's standing platform fact in action — a `calculation_equation`
cannot read a `booleancheckbox` or an enumeration. Plan 06's numeric mirror replaced it, and three
further threats (T-50-29/30/31) were added to keep the mirror honest. Closed on the corrected
control, with the falsification recorded rather than the original quietly restated.

**T-50-18 — proven, then its own mechanism was destroyed inside the same phase.** The rollback
drill genuinely proved manual enrolment into WF1 — and Plan 05 then deleted WF1 to unblock the
archive. The runbook carries a dated amendment saying both mechanisms are gone and that rollback is
now a from-scratch rebuild with two further unverified steps. Kept closed because the drill did
prove what it claimed at the time, but **the phase's own rollback proof no longer describes
reality**, and an operator reading only the drill record would be misled.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-50-01 | T-50-06 | Calculated properties are `readOnlyValue` platform-wide in HubSpot; no PATCH path exists for any caller. | plan-time, re-confirmed | 2026-09-03 |
| AR-50-02 | T-50-20 | HubSpot's own permission model gates manual enrolment. **Moot under D-24** — WF1 was deleted, so the surface no longer exists. | plan-time, moot under D-24 | 2026-09-03 |
| AR-50-03 … AR-50-08 | T-50-SC (one per plan) | No plan in this phase installs a package or adds a dependency. | plan-time, re-confirmed | 2026-09-03 |
| AR-50-09 | T-50-22 | Reports and dashboards have no documented public HubSpot API and were left an explicit **UNCONFIRMED** residual by the Plan 02 sweep; the archive proceeded with it open. `50-05-SUMMARY.md` records this as the operator's previously stated accepted risk. **No prior `AR-50-*` entry existed for it** — surfaced by this audit rather than left off the log. | operator, per 50-05-SUMMARY's disclosure | 2026-08-14 (surfaced 2026-09-03) |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open (at/above `high`) | Run By |
|------------|---------------|--------|------------------------|--------|
| 2026-09-03 | 43 | 40 (32 mitigation-verified, 8 accepted) | **3** | `gsd-security-auditor`, `asvs_level: 1` |
| 2026-09-03 (post-fix) | 43 | 43 | 0 | orchestrator — guard wired, coverage test added, behaviour proven |

Suites re-run during the audit: 139 targeted pytest cases across six files, and `node --test
tests/n8n/*.test.mjs` 862/862.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented, including AR-50-09 which had never been logged
- [x] `threats_open: 0` — T-50-11 / T-50-27 / T-50-36 fixed 2026-09-03, not accepted
- [x] Guard wired into all five write paths and pinned by `tests/test_guarded_emit_coverage.py`
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03, after the fix
