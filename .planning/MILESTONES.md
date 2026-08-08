# Milestones

## v0.7 HubSpot Scoring Engine Remediation (Shipped: 2026-08-08)

**Phases completed:** 5 phases (39–43), 23 plans

**Key accomplishments:**

- The ICP rubric was implemented twice — correctly in `src/icp_scoring.py` (oracle only, zero
  production callers) and incorrectly as four live HubSpot workflows nobody knew existed until
  the `automation` scope was granted. All ten validated defects (F1–F10) are fixed **in place**
  on the HubSpot-resident path (Phase 39 decision: the lead-scoring tool cannot write
  `lv_icp_fit_score`, so it was rejected despite being available).
- Engine correct end to end: `lv_produces_content` contributes +20, scoring reads the canonical
  `lv_*` inputs the pipeline actually writes (not native `country`/`annualrevenue`), revenue
  decay lands in the rubric-correct band at every boundary, the gambling deduction is
  independent of org type and never sets the veto flag, sub-15 without a veto no longer grades
  D, all three hard vetoes write flag + reason, vetoes clear on correction, and a flag change
  alone moves the tier.
- **Parity harness instead of eyeballing the UI** (`scripts/run_scoring_parity.py`): recomputes
  via the oracle and asserts against live HubSpot, with a false-green guard that fails when zero
  assertions execute. Every F-defect had been invisible in the HubSpot UI.
- 66 web-researched companies landed as a real scoreable population with provenance at **zero
  provider spend**, and scored automatically on the actual write path (A:7 B:18 C:17 D:24).
- Schema reconciled: `config/hubspot_properties.yaml` is a full 32-property live mirror at zero
  drift, with a standing checker (`scripts/check_schema_drift.py`) and a machine-checked
  do-not-archive invariant. Live derivation found zero orphans — Phase 40 left no debris.
- Pipeline hygiene: boolean write sites coerced to strings at two shared choke points, the
  dormant veto site hardened, `lv_icp_score_breakdown` given a producer, and the closed-lost
  reason signal consumed.
- **Post-milestone, same day:** Phase 41 exposed that `lv_icp_fit_score`'s formula blanked
  entirely on any null term, so 63 of 66 records had no score while the sweep still said PASS.
  Spiked the grammar (the API's 400 body enumerates it), applied a null-safe formula live, and
  added a detector for the blank-score condition the harness structurally could not see.

**Closeout:** REQUIREMENTS 16/16; ROADMAP 5/5 phases Complete; suites 2427 pytest / 636 node;
arming grep 0; all n8n write gates disarmed at rest; live parity PASS with 0 real findings;
schema drift exit 0. No milestone git tag (semver-release-tag namespace precedent from
v0.3/v0.4/v0.6).

---

## v0.6 Claude Plugin Entrypoint (Shipped: 2026-08-04)

**Phases completed:** 10 phases (23–32), workstream `plugin-entrypoint`

**Key accomplishments:**

- Shipped `operator-claude-plugin/`: a conversational front door over the n8n backend — tabular + non-tabular ingestion (prose, foreign JSON, URLs, screenshots), enrichment lane with cost guard, per-record outcome reporting with safe retry, backend status surface, allowlisted control actions, notices + unattended sweep, and review-queue triage. 49/49 requirements complete.
- Every dangerous capability behind a uniform `ALLOW_*` gate (exact-string `true`, D-34), session arms separate from env gates, single-record `TEST_RECORD_*` allowlists, and symmetric `--expect-armed` read-backs. Committed workflow artifacts always disarmed; every arm/disarm bounces active workflows (stored-vs-running gap, proven live).
- Phase 31 (inserted): HubSpot enum validate-and-refuse across staging AND both review paths — preview and submit return identical explicit refusals; `not_allowlisted` distinct from workflow error (BUGS 28/29/30 closed on live evidence).
- Phase 32 (inserted): LLM-free unattended sweep trigger — deterministic sh wrapper under real cron, zero credentials, loud on its own failure; NOTICE-03 sealed by RB-8 re-run (`claude -p` under cron fails silently — never reintroduce).
- Armed canaries RB-3/7/8/9 all passed with single-record blast radius. RB-9 close (2026-08-04) demonstrated REVIEW-04 live: a human approve stamped `source: human` / `human_approved` / timestamp / reason with the superseded machine source readable, and the D-31 probe recorded the decision endpoint withholding a `manual_protected` field (backstop path explicitly not proven).

**Closeout:** REQUIREMENTS 49/49 complete; STATE 10/10 phases; closing gates 1784 pytest / 550 node / armed-literal grep 0 / live tenant disarmed PASS. Carried opens (tracked in HANDOFF/todos): sweep lookback time-window + workflow-name notices, Phase 26 thin-response reason, versioned-cache config orphan, RB-3 canary contact cleanup. No milestone git tag (semver-release-tag namespace precedent from v0.3/v0.4).

---

## v0.4 Reachability & Verification Debt (Shipped: 2026-07-29)

**Phases completed:** 3 phases, 6 plans, 17 tasks

**Key accomplishments:**

- BUG 23 fixed: enrichment `contact:create` made structurally reachable — contacts-lane `HubSpot Search`/`HubSpot Fetch By Id` swapped to the credential-bound httpRequest envelope, byte-identical pins retired with rationale, dual live canary proved match-path regression AND create-path reachability (write-gated), deployment restored disarmed.
- Added `_industryText` to `normalizeProviders.js` so ZoomInfo's and Lusha's company mappers emit the NAICS entry's human-readable name (or nothing) instead of a bare numeric code, closing the gap where a code could win the industry waterfall purely on source trust.
- Wired `lv_sponsorship_reliant` (companies research fold) and `lv_persona_group` (contacts winners loop) into their merge calls via one array entry and one dot-access if-block, closing both Phase-15-carried-forward copy-loop gaps at the wiring level; both fields still have no producer.
- Both Phase-18 verification gaps closed end-to-end: the research prompt now actually asks for `lv_sponsorship_reliant` and a new provider-mapper producer actually emits `lv_persona_group` — both proven live-reachable through compiled node bodies fed by recorded fixtures, not hand-constructed test rows.
- Reconstructed and re-executed all six v0.3 `/gsd-verify-work` re-runs against current code — surfacing BUG 26 (live n8n Cloud deployment had drifted behind git) along the way. Same-day operator runbook closed everything: Step-0 redeploy (BUG 26 resolved), armed `company:update` canary (execution 108, write proven on the allowlisted record only, disarm read back). Final ledger: **6/6 passed, zero residual operator debt**.

**Closeout:** verified — all 3 phases `verification_status: passed`; pre-close artifact audit all-clear; v4 requirements 8/8 complete. No `v0.4-MILESTONE-AUDIT.md` was run (accepted: the phase-level verifier chain + 6/6 ledger covered the same ground). No git tag created — repo tag namespace uses semver release tags (`v0.4.0`/`v0.5.0`); a `v0.4` milestone tag would collide confusingly (same precedent as the untagged v0.3 close). Legacy v1/v2 requirement sections in the archived REQUIREMENTS.md carry historical unchecked rows from already-archived milestones, not v0.4 gaps.

---
