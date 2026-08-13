---
phase: 49-re-score-strategy-reporting
plan: 06
subsystem: crm-scoring
tags: [hubspot, n8n, icp-scoring, veto-remediation, web-research, claude-sonnet-5]

requires:
  - phase: 47.5-veto-recompute-path
    provides: "the D-18 recompute POST lane, IF Company Recompute routing, and the unresolved D->non-D transition gap this plan closes"
  - phase: 48-enrichment-coverage
    provides: "the org-type/coverage enrichment pass that confirmed Jam TV's veto is geographic, not org-type"
provides:
  - "Entain 10024564084's non-ANZ and no-content vetoes both cleared live, on committed registry-grade evidence"
  - "The live D -> non-D tier transition proven as a causal transition (not two nearby reads), closing the gap 47.5-A-LIVE-PROOF.md left open"
  - "A live-derived, dated portal-wide non-ANZ veto census (1) and VETO-03 blank-region bar (0)"
affects: [49-rescore-report, milestone-v0.9-close]

actuals:
  tokens: 10230
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "domain-allowlist arming is only valid for records that do not exist yet; an existing record must be armed by --ids and dispatched via a bare (no-domain) event so it routes through the fetch-by-id lane, not the domain-EQ search lane"

key-files:
  created:
    - .planning/phases/49-re-score-strategy-reporting/49-ENTAIN-EVIDENCE.json
    - .planning/phases/49-re-score-strategy-reporting/49-W2-RECORD.md
    - .planning/phases/49-re-score-strategy-reporting/49-W2-WINDOW-RAW.json
  modified: []

key-decisions:
  - "Operator authorised W2 (open-w2) after both of Entain's veto claims cleared config/field_policy.yaml's bar (D-14's override)."
  - "First arm attempt used --domains www.entaingroup.com; n8n's domain-EQ search strips 'www.' before matching and the stored domain carries it, so it matched 0 rows (recompute_refused, zero writes). Re-armed by --ids 10024564084 and dispatched a bare event instead, which routes via fetch-by-id -- the correct mechanism for a record that already exists (Rule 1 auto-fix, disclosed)."
  - "The transition assertion is 'tier != D', never a named tier, per D-15 -- Entain landed at Unscored (-20), below the C floor, which the pre-flight arithmetic in 49-ENTAIN-EVIDENCE.json predicted from its 1.2B+ revenue band."

patterns-established:
  - "A recompute POST for an existing record should default to the bare (fetch-by-id) lane rather than the domain-allowlist lane, unless the record does not exist yet -- the domain lane's own normalization can silently refuse a real record whose stored domain carries a prefix the search strips."

requirements-completed: [RESCORE-03]

coverage:
  - id: D1
    description: "Entain's two veto inputs (region, produces_content) re-examined against the config bar with registry-grade evidence, committed whichever way it falls"
    requirement: RESCORE-03
    verification:
      - kind: other
        ref: ".venv/bin/python -c \"import json,pathlib; d=json.loads(pathlib.Path('.planning/phases/49-re-score-strategy-reporting/49-ENTAIN-EVIDENCE.json').read_text()); assert all(k in d for k in ('preflight','cost_estimate','research','bar','verdict'))\""
        status: pass
    human_judgment: false
  - id: D2
    description: "W2 window: veto inputs written, D-18 recompute clears the veto live, D -> non-D tier transition captured with independent t0/t1 reads and node-level proof, both arming surfaces disarmed and independently re-verified"
    requirement: RESCORE-03
    verification:
      - kind: other
        ref: "live n8n executions 11872 (refused, 0 writes) and 11873 (success, HubSpot Company Update PATCHed exactly lv_anti_icp_flag/lv_anti_icp_reason) -- see 49-W2-RECORD.md sections 4-8"
        status: pass
      - kind: other
        ref: "scripts/verify_live_write_safety.py --expectation disarmed --json -> {\"ok\": true, \"reasons\": []}"
        status: pass
    human_judgment: false
  - id: D3
    description: "Jam TV retained-veto assertion and portal-wide non-ANZ/VETO-03 census re-derived live and dated"
    requirement: RESCORE-03
    verification:
      - kind: other
        ref: "live HubSpot search: non-ANZ veto census = 1 (Jam TV only, Entain cleared); VETO-03 bar (non-ANZ veto + blank region) = 0"
        status: pass
    human_judgment: false

duration: ~30min (this continuation)
completed: 2026-08-13
status: complete
---

# Phase 49 Plan 06: Entain Veto Re-examination and W2 Transition Proof Summary

**Entain's two hard-veto inputs cleared live on registry-grade evidence (AUSTRAC Federal Court filing + Mediaweek racing-channel coverage), the D-18 recompute lane cleared the veto end to end, and the live D -> non-D tier transition is proven as a causal chain for the first time in this project's history — closing a gap 47.5-A-LIVE-PROOF.md explicitly left open.**

## Performance

- **Duration:** ~30 min (this continuation; Task 1 was committed in an earlier session)
- **Tasks:** 3/3 (Task 1: research + evidence; Task 2: checkpoint, resolved `open-w2`; Task 3: W2 window + census)
- **Files created:** 3 (`49-ENTAIN-EVIDENCE.json`, `49-W2-RECORD.md`, `49-W2-WINDOW-RAW.json`)

## Accomplishments

- Re-examined both of Entain `10024564084`'s veto inputs (region, `lv_produces_content`) through `src/web_research.py`'s live path against the D-V6 bright line; both cleared `config/field_policy.yaml`'s bar (confidence 95 vs. required 85/75, evidence URLs independently re-fetched and verified by `curl`).
- Operator authorised W2; both inputs PATCHed directly (`lv_country_region_normalized = ANZ`, `lv_produces_content = true` — inputs only, D-07 held).
- The D-18 recompute POST cleared the hard veto live: `Decide Company Action` -> `HubSpot Company Update` PATCHed exactly `lv_anti_icp_flag` and `lv_anti_icp_reason`, nothing else.
- Captured the D -> non-D tier transition as a transition, not two nearby reads: independent t0 read (`D`), a confirmed input PATCH, node-level proof the recompute lane's `existingRecord` picked up the new inputs, and an independent t1 read after settle (`Unscored`). Asserted `tier != "D"`, never a hard-coded `B`/`C`.
- Both arming surfaces (n8n `ALLOW_HUBSPOT_RECORD_WRITES` + allowlist) independently confirmed disarmed twice — the arm script's own re-read and a full `verify_live_write_safety.py` scan.
- Jam TV's retained geographic veto reconfirmed by plain read; portal-wide non-ANZ veto census re-derived live (1, down from 2 — Entain cleared) and the VETO-03 blank-region bar re-confirmed at 0.

## Task Commits

1. **Task 49-06-01: Re-examine Entain's two veto inputs against the config bar** — `0694ede` (docs) — prior session
2. **Task 49-06-02: Authorise or decline the conditional W2 window** — checkpoint, no commit (resolved `open-w2` by operator)
3. **Task 49-06-03: Run W2 with transition instrumentation, and re-confirm the veto census** — `79a7932` (docs)

**Plan metadata:** (this commit)

## Files Created/Modified

- `.planning/phases/49-re-score-strategy-reporting/49-ENTAIN-EVIDENCE.json` — Task 1's committed research evidence (pre-flight reads, cost estimate, both research calls, independent URL re-verification, per-claim bar verdicts)
- `.planning/phases/49-re-score-strategy-reporting/49-W2-RECORD.md` — the full W2 ceremony: authorisation, pre-window state, both arm attempts (the failed domain-routed one and the corrected id-routed one), node-level transition proof, disarm + independent re-verification, cost accounting, and the D-16 census leg
- `.planning/phases/49-re-score-strategy-reporting/49-W2-WINDOW-RAW.json` — the raw JSON captured by the driver script at each step of the window, underlying `49-W2-RECORD.md`'s narrative (not in the plan's declared `files_modified`, added as supporting evidence — same convention as `47.5-AFTER.json`/`47.5-B-BEFORE.json`)

## Decisions Made

- **W2 opened.** Both veto claims cleared the config bar; operator selected `open-w2` under the `D-49-01` waiver.
- **Arm-by-id, not arm-by-domain, for an existing record.** Discovered live: n8n's domain-EQ search normalizes away a `www.` prefix the stored `domain` property carries, so a domain allowlist can silently fail to match a record that plainly exists. Switched to `--ids` + a bare (no-domain) event, which routes through the fetch-by-id lane instead — no domain match required. Documented as a reusable pattern for any future recompute against an existing record.
- **Transition assertion stayed `tier != "D"`.** Entain's `1.2B+` revenue band drives a `-50` deduction that lands the cleared record at `Unscored` (`-20`), not `B` or `C` — exactly the outcome the pre-flight arithmetic in `49-ENTAIN-EVIDENCE.json` predicted and the operator was told to expect before authorising.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] First W2 arm attempt (`--domains www.entaingroup.com`) could not reach the veto write**
- **Found during:** Task 3, first recompute POST attempt
- **Issue:** n8n's `Adapt Company Search` node strips the `www.` prefix before its domain-EQ search (`identity_keys.domain: "entaingroup.com"`); Entain's live `domain` property is stored as `"www.entaingroup.com"` verbatim, so the search matched 0 rows. `Decide Company Action` returned `action: "recompute_refused"` (execution `11872`) — zero HubSpot writes, no clobber, but the veto was not cleared.
- **Fix:** Disarmed the failed attempt (independently re-read as closed), re-armed with `scripts/june_run_arm.py --ids 10024564084` (the correct mechanism for a record that already exists — a domain allowlist exists specifically for records that do not exist yet), and re-sent the D-18 POST as a bare event (no `domain` key), routing through `IF Company Bare Event` -> `HubSpot Company Fetch By Id` — no domain match required. Succeeded (execution `11873`).
- **Files modified:** none (no source code changed — this was a driver-invocation correction, not a code fix)
- **Verification:** `HubSpot Company Update` node in execution `11873`'s `runData` confirms the PATCH landed with exactly `lv_anti_icp_flag`/`lv_anti_icp_reason`; independent t1 read confirms `lv_anti_icp_flag: "false"`, `lv_icp_tier: "Unscored"`.
- **Committed in:** `79a7932` (Task 3 commit; full detail in `49-W2-RECORD.md` section 4)

---

**Total deviations:** 1 auto-fixed (1 Rule-1 bug in the arming/dispatch invocation, not in any repo source file)
**Impact on plan:** No scope creep; no code changed. Consumed one extra n8n execution (`11872`), disclosed in the cost accounting (2 of the declared ~1–2, 0 provider credits, 0 further Anthropic calls) rather than absorbed silently. The correction is documented as a reusable pattern for future existing-record recomputes.

Carried forward from Task 1 (already disclosed and committed in `0694ede`, restated here for a single point of reference): Task 1 made 2 Anthropic web-research calls against a declared 1. The first call used `src/web_research.py`'s default `RESEARCH_SYSTEM` prompt (no D-V6 framing) and returned a headquarters-based "Isle of Man" region answer — unusable for the veto re-examination. A second call with an explicit D-V6-framed system-prompt addendum produced the verdict-controlling result. Classified Rule 1 (the first call's framing was a bug relative to the task's own instruction); both calls are recorded in `49-ENTAIN-EVIDENCE.json`.

## Issues Encountered

None beyond the arming-mechanism deviation above — no test failures, no credential gaps, no permission refusals.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- This was the third and final consecutive phase (47.5, 48, 49) this carried-forward item was assigned to by name — it is fully discharged, not re-deferred.
- `49-RESCORE-REPORT.md` (a later plan in this phase) can now cite Entain as a resolved D -> Unscored transition with full evidence, rather than as an open item.
- The portal-wide non-ANZ veto census (1: Jam TV only) and VETO-03 bar (0) are current as of 2026-08-13 and available for the phase's final report.
- The domain-vs-id arming pattern discovered here is worth folding into `docs/OPERATOR-VETO-REFRESH.md` or an equivalent runbook if a future phase runs more single-record recomputes against existing companies — no action taken this plan, as it was out of this plan's declared scope.

---
*Phase: 49-re-score-strategy-reporting*
*Completed: 2026-08-13*

## Self-Check: PASSED

- FOUND: `.planning/phases/49-re-score-strategy-reporting/49-ENTAIN-EVIDENCE.json`
- FOUND: `.planning/phases/49-re-score-strategy-reporting/49-W2-RECORD.md`
- FOUND: `.planning/phases/49-re-score-strategy-reporting/49-W2-WINDOW-RAW.json`
- FOUND: `.planning/phases/49-re-score-strategy-reporting/49-06-SUMMARY.md`
- FOUND commit: `0694ede`
- FOUND commit: `79a7932`
