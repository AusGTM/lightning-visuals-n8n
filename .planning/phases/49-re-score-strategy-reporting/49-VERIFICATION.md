---
phase: 49-re-score-strategy-reporting
verified: 2026-08-19T00:00:00Z
status: passed
score: 4/4 success criteria substantively met; 1 gap closed since last verification, 1 new gap found this pass
overrides_applied: 0
re_verification: yes
re_verification_details:
  previous_status: passed_with_gaps
  previous_status_note: >
    Non-standard value; the frontmatter key has since been renamed to `status:` and
    tooling (`query verification.status`) does not recognise `passed_with_gaps`. This
    report replaces it with a standard value.
  previous_score: "4/4 success criteria substantively met; 1 disclosed gap"
  gaps_closed:
    - "docs/OPERATOR-RESCORE.md now carries a genuine AS-BUILT AMENDMENT block (added
       2026-08-13, extended 2026-08-14) that names the stale-tier failure class, its two
       root causes, the 4 affected company ids, cross-references WINDOWS.md ids 9-12 and
       TIER-DERIVATION-SPIKE-2026-08-13.md by name, and records that Phase 50 shipped the
       structural fix (lv_icp_tier_derived) on 2026-08-14. This genuinely closes the gap
       the prior report identified."
  gaps_remaining: []
  regressions:
    - "docs/OPERATOR-RESCORE.md's ## Acceptance section still names
       scripts/run_scoring_parity.py's live population sweep as 'the proof that a
       re-score landed' -- unedited by either amendment. That script's overall
       match = score_match AND tier_match AND flag_match reads the archived,
       now-permanently-frozen lv_icp_tier property (tests/scoring_fixtures.py's
       FIT_SCORE_PROPS explicitly names it, and Phase 50 itself proved -- see
       50-TIER-PARITY-EVIDENCE.md's 2026-08-14 amendment -- that a named archived
       property still returns its last live value rather than erroring or reading
       null). Phase 50 deleted WF1 (4625147345), the only mechanism the documented
       procedure ever used to write lv_icp_tier, and archived the property. No step in
       OPERATOR-RESCORE.md's procedure writes it any longer. run_scoring_parity.py also
       carries no allowance for the known-stuck ids (unlike its Phase-50-built sibling
       scripts/check_tier_derived_parity.py, which does). Net effect: for the historical
       4-5 stuck records the sweep is red today exactly as before (expected, disclosed),
       but for ANY future rubric change that alters a company's tier, the sweep will now
       show that company red forever -- indistinguishable, to an operator following this
       runbook, from the 'rescore not finished' case the Acceptance section still tells
       them to fix by re-running the rescore. The runbook's named acceptance gate has
       decayed since Phase 49 sealed; this is not a Phase 49 execution defect, but it now
       makes RESCORE-01's 'operator can trust before invoking it' bar unmet for any
       future invocation until the doc is repointed at check_tier_derived_parity.py (or
       an equivalent lv_icp_tier_derived-based check)."
gaps:
  - truth: "A future rubric-triggered full-population re-score has a defined,
            budget-bounded procedure the operator can trust before invoking it"
    status: partial
    reason: >
      The procedure's own named acceptance gate (docs/OPERATOR-RESCORE.md's
      ## Acceptance section, pointing at scripts/run_scoring_parity.py) checks a
      HubSpot property (lv_icp_tier) that Phase 50 permanently stopped writing
      (WF1 deleted, property archived, 2026-08-14). Nothing in the documented
      procedure -- including its own Phase-50-update amendment paragraph -- updates
      the Acceptance section to point at a gate that still means something for a
      NEW rubric change. A future operator who runs this runbook exactly as written,
      then checks acceptance exactly as instructed, will see a red sweep on any
      company whose tier changed under the new rubric, and the runbook tells them
      to "finish the re-score" -- advice that cannot fix this, because nothing in
      the finishable procedure ever writes lv_icp_tier again.
    artifacts:
      - path: "docs/OPERATOR-RESCORE.md"
        issue: "## Acceptance section (unedited by either AS-BUILT AMENDMENT) still
                names scripts/run_scoring_parity.py's lv_icp_tier-based sweep as the
                sole proof a re-score landed, with no caveat that this check is now
                permanently defeated for any record whose tier changes going forward"
    missing:
      - "A dated amendment to the ## Acceptance section (or a new AS-BUILT AMENDMENT
         block) repointing the acceptance proof at scripts/check_tier_derived_parity.py
         (or an equivalent comparison against lv_icp_tier_derived), which Phase 50 built,
         proved PASS post-archive (population=66 match=61 expected_mismatch=5 defect=0),
         and already carries the KNOWN_STUCK allowance run_scoring_parity.py lacks"
deferred: []
human_verification: []
gap_closure_2026_08_19:
  - gap: "docs/OPERATOR-RESCORE.md's ## Acceptance section still named scripts/run_scoring_parity.py's sweep as the proof a re-score landed, but that sweep's pass condition ANDs in tier_match (line 313, used at 315), which reads the lv_icp_tier property Phase 50 archived on 2026-08-14."
    severity: "Real. An archived HubSpot property returns its frozen last value rather than erroring or nulling, so the sweep runs, prints a verdict, and silently compares dead data. After any FUTURE rubric change every newly-tier-changed company reads red permanently and indistinguishably from 'the re-score has not finished' -- the exact misdiagnosis the 2026-08-13 amendment was written to prevent, relocated into another clause of the same document."
    closed_by: "A second AS-BUILT AMENDMENT block dated 2026-08-19 (Phase 50 follow-up), appended at the top per the document's own convention with the original prose left intact. It repoints the acceptance gate at scripts/check_tier_derived_parity.py / lv_icp_tier_derived, cites Phase 50's live proof (population=66 match=61 expected_mismatch=5 defect=0), and carries two cautions: poll rather than single-read (calculated properties backfill ~70-130s, a mistake this project already made once and had to reverse), and a red result still means what it always meant -- only the property being read has changed. The AMENDMENT-block convention section was updated from 'One amendment' to 'Two amendments'."
    verified: "scripts/run_scoring_parity.py:313/315 read directly to confirm tier_match is genuinely in the pass condition before writing the correction."

---

# Phase 49: Re-score Strategy & Reporting Verification Report (RE-VERIFICATION)

**Phase Goal:** A future rubric-triggered full-population re-score has a defined,
budget-bounded procedure the operator can trust before invoking it, and the milestone's net
effect on the target list is visible in plain language. Phase 46 DID change three weights
(commit `caae5d6`), so the full-population re-score was owed, not merely proven.

**Verified:** 2026-08-19
**Status:** gaps_found
**Re-verification:** Yes — replaces the 2026-08-13 report (`status: passed_with_gaps`, a
non-standard value the tooling does not recognise)

## What changed since 2026-08-13

1. **The prior gap is closed.** `docs/OPERATOR-RESCORE.md` now carries a genuine AS-BUILT
   AMENDMENT block, dated 2026-08-13 and extended 2026-08-14, that: names the exact line it
   corrects (the Acceptance section's "finish the re-score" instruction), explains the two
   distinct causes of a red sweep (not-yet-written vs. permanently value-identical), names
   all four affected company ids, cross-references `WINDOWS.md` ids 9-12 and
   `TIER-DERIVATION-SPIKE-2026-08-13.md` by name, and records that Phase 50 shipped the
   structural fix (`lv_icp_tier_derived`, WF1 deleted, `lv_icp_tier` archived) on
   2026-08-14. This is a real, substantive fix — verified against the doc's own
   `## AMENDMENT-block convention` section, which it follows correctly (dated block,
   original prose left in place below it, plain statement of what it corrects).
2. **Offline test suites re-run green with expected growth**, not stale figures:
   `.venv/bin/python -m pytest -q -m "not live"` → 2821 passed / 154 skipped (was
   2719/128); `node --test tests/n8n/*.test.mjs` → 683 pass/0 fail (was 676) —
   consistent with Phase 50 adding tests, not a regression.
3. **`tests/test_rubric_change_guard.py`** (a Phase 49 deliverable explicitly reused by
   Phase 50 per this task's framing) re-run in isolation: 6/6 pass.
4. **A new regression was found in this pass** (not present, or not yet possible, at
   2026-08-13 verification time): `docs/OPERATOR-RESCORE.md`'s `## Acceptance` section
   still names `scripts/run_scoring_parity.py` as the sole proof a re-score landed. That
   script's pass/fail is `score_match AND tier_match AND flag_match`, and `tier_match`
   reads `lv_icp_tier` — a property Phase 50 archived on 2026-08-14 after deleting the
   only workflow (`4625147345`/WF1) that ever wrote it. See "New Regression Found" below.
5. **`WINDOWS.md` ids 9-12 (and 14, added by Phase 50) remain literally `open`** in the
   ledger's status column. This is checked and judged correct, not stale — see "Ledger
   honesty check" below.

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can see, before any future rubric change, exactly which records would be re-scored, chunk size, and write window | ✓ VERIFIED (unchanged) | `docs/OPERATOR-RESCORE.md` still states population=66, chunk_size=100, chunks=1, window=W1, arm_keys, cost — figures unmodified since 2026-08-13, unaffected by Phase 50. |
| 2 | Because no `lv_icp_scoring_version` exists, plan explicitly re-scores the entire 66-company population and states cost up front | ✓ VERIFIED (unchanged) | Same as prior verification; `49-PLAN-OUTPUT.json` unedited since sealing (confirmed by `git log --since` on the evidence path — no touches after 2026-08-13T08:00Z). |
| 3 | If Phase 46 changed a weight, the full-population re-score executed under this defined procedure | ⚠ MET WITH DISCLOSED, PARTIALLY-DISCHARGED, PARTIALLY-NEW GAP | The historical execution (66/66, W1, canary-then-remainder, exact-set gate) is unchanged, still evidenced by `49-W1-ARM-RECORD.md`. The 4-stuck-record disclosure gap from the prior verification is now genuinely closed by the amendment block. **New finding this pass:** the runbook's *named acceptance mechanism itself* (`run_scoring_parity.py`) has been silently defeated for all future invocations by Phase 50's later, deliberate deletion of WF1 and archival of `lv_icp_tier` — see Gap below. |
| 4 | Operator receives a plain-language before/after tier-distribution comparison covering the whole milestone's re-scoring activity | ✓ VERIFIED (unchanged) | `49-RESCORE-REPORT.md` unedited since sealing; published Artifact and operator approval both predate this window and are unaffected by Phase 50. |

**Score:** 3/4 truths cleanly VERIFIED and unchanged; 1/4 (#3) carries a gap that shifted in
kind rather than closed — the specific issue the prior report flagged is fixed, but a new,
more consequential issue in the same acceptance-gate machinery was found this pass.

### New Regression Found — Acceptance gate decay (not a Phase 49 execution defect)

**Chain verified end to end, read-only:**

1. `docs/OPERATOR-RESCORE.md:241-245` (`## Acceptance`, unedited by either amendment):
   *"The proof that a re-score landed is `scripts/run_scoring_parity.py`'s live
   population sweep exiting green... if it is red, the rubric and the live records still
   disagree, and the fix is to finish the re-score, not to loosen the comparison."*
2. `scripts/run_scoring_parity.py:311-313`: `match = score_match and tier_match and
   flag_match`, where `tier_match = str(live_triple["lv_icp_tier"]) ==
   expected_triple["lv_icp_tier"]` and `live_triple["lv_icp_tier"] =
   props.get("lv_icp_tier")`. No allowance list for known-stuck ids exists in this
   script.
3. `tests/scoring_fixtures.py`'s `FIT_SCORE_PROPS` explicitly names `lv_icp_tier` in the
   properties list this script fetches.
4. `.planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md` (D-24, live,
   2026-08-14): WF1 (`4625147345`) — the only workflow that ever wrote `lv_icp_tier` —
   was DELETEd (`204`, independently re-read `404`), and `lv_icp_tier` was then archived
   (`DELETE /crm/v3/properties/companies/lv_icp_tier` → `204`).
5. `.planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md`'s **AMENDMENT
   2026-08-14** section: `check_tier_derived_parity.py` was re-run live post-archive,
   *expecting* `lv_icp_tier` to read null on every record — that expectation was wrong.
   **An archived property's last value is still returned when explicitly named in
   `properties=`.** Re-run result: `population=66 match=61 expected_mismatch=5 defect=0`
   — byte-identical to the pre-archive run.

**What this means, stated precisely (not overclaimed):** `run_scoring_parity.py` will not
error and will not read null — it will keep returning `lv_icp_tier`'s frozen, last-written
value indefinitely. No step in the documented procedure (the weight branch, the veto
branch, or any scheduled job named in this doc) writes to `lv_icp_tier` any longer, because
its one writer no longer exists. I have not verified whether a PATCH *could* still succeed
against the archived property (untested, no write attempted per this task's read-only
constraint) — only that nothing in the documented procedure attempts one.

**Consequence:** for the 4-5 historically-stuck records, the sweep is red today exactly as
it was on 2026-08-13 — expected, and now correctly disclosed by the amendment block. But
for **any future rubric change that alters a company's expected tier**, that company's row
will *also* now read `tier_match = False` forever, with no mechanism to ever correct it,
and no marker distinguishing it from "the rescore just hasn't been finished yet." The
Acceptance section's own prescribed remedy — "finish the re-score" — cannot fix this
class, for the identical structural reason the original amendment already explains for the
4 historical records, but the amendment's fix does not extend to the section that still
names this gate as authoritative.

A working successor already exists and was proved live by Phase 50:
`scripts/check_tier_derived_parity.py`, which compares against `lv_icp_tier_derived`
(the calculated, no-workflow-dependency replacement) and carries an explicit
`KNOWN_STUCK_TRANSITIONS` allowance for exactly the ids this class produces. The runbook
does not point to it anywhere in its `## Acceptance` section — the one mention of
`lv_icp_tier_derived` in the whole document is inside the amendment block, describing that
it shipped, not directing the operator to check against it.

**This is scored as a gap in this phase, not a Phase 49 execution failure.** Phase 49 did
what its own goal required at the time it sealed; Phase 50's later, deliberate,
well-evidenced schema change is what broke the acceptance gate, and Phase 50's own
verification did not flag it as an open item on Phase 49's runbook (checked: no mention of
`run_scoring_parity.py` needing an update anywhere in Phase 50's plans/summaries/
verification). It is real, current, undischarged debt on a Phase-49-owned artifact, so it
belongs in this report.

### Ledger honesty check — WINDOWS.md ids 9-12 (and 14)

Checked per this task's explicit instruction not to mark anything closed the ledger still
shows open. `.planning/WINDOWS.md` (`open_count: 9`, header) shows ids 9, 10, 11, 12, and
14 all with `status: open` — unchanged since Phase 49 sealed. This is judged **correct, not
stale**: `lv_icp_tier`'s literal value for these five records is permanently wrong now
(frozen at its last pre-archive value) and will never self-correct — there is no future
event that flips its status to fixed. `REQUIREMENTS.md`'s TIER-01 row already states this
distinction correctly: the *mechanism-level* problem is resolved (the derived property
gives the right answer with no dependency on the broken event), but the *raw property* stays
wrong forever, by design, and the ledger's `open` status honestly reflects that. Nothing here
should be marked closed. The re-verification instruction's framing — "discharged-by-a-later-
phase rather than debt-outstanding" — applies to the *practical* consequence (an operator
now reads the correct tier via `lv_icp_tier_derived`), not to the ledger row itself, which
correctly continues to describe `lv_icp_tier`'s literal, permanent defect.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/OPERATOR-RESCORE.md` | Budget-bounded operator runbook, both branches | ⚠ VERIFIED, with 1 new gap | Prior gap (missing amendment) genuinely closed. New gap: `## Acceptance` section names a now-decayed proof mechanism (see above); not repointed by either amendment. |
| `scripts/rescore_population.py` | Driver: exact-set gate, `--plan`, canary/execute, `--snapshot` | ✓ VERIFIED (unchanged) | Unedited since Phase 49 sealed per `git log --since`; exact-set gate still present. |
| `49-P2-SNAPSHOT.json` / `49-P3-SNAPSHOT.json` | Before/after population census | ✓ VERIFIED (unchanged) | Byte-identical to 2026-08-13 (confirmed unedited via git log on the file paths). |
| `49-PARITY-VERDICT.json` | Genuine, unedited acceptance-sweep result | ✓ VERIFIED (unchanged, now historical) | Unedited since sealing. Its 4 `real_finding` entries remain the accurate historical record; the sweep it captured is now permanently unrepeatable in its original form (WF1 gone), which is disclosed above, not hidden. |
| `49-RESCORE-REPORT.md` | Plain-language milestone report | ✓ VERIFIED (unchanged) | Unedited since sealing. |
| `49-RUN-REPORT.md` | Cost/window actuals vs. declared | ✓ VERIFIED (unchanged) | Unedited since sealing. |
| `49-REVIEW.md` | Code review, 1 Critical + 4 Warnings | ✓ VERIFIED (unchanged) | Unedited since sealing; fixes on `master` per prior verification, unaffected by Phase 50. |
| `tests/test_rubric_change_guard.py` | Reused by Phase 50 | ✓ VERIFIED, RUNS GREEN | 6/6 pass, run fresh this pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `docs/OPERATOR-RESCORE.md` figures | `49-PLAN-OUTPUT.json` | direct citation | WIRED (unchanged) | Figures unedited, still match. |
| `49-RESCORE-REPORT.md` P1/P2/P3 table | source JSON snapshots | direct citation | WIRED (unchanged) | Unedited. |
| `WINDOWS.md` ids 9-12/14 | `50-TIER-PARITY-EVIDENCE.md` KNOWN_STUCK | company-id match, mechanism-level | WIRED | All 4 (+1) ids map to `check_tier_derived_parity.py`'s `KNOWN_STUCK_TRANSITIONS`, verified by cross-reference of ids and root-cause text between `WINDOWS.md`, the amendment block, and `50-TIER-PARITY-EVIDENCE.md`. |
| `docs/OPERATOR-RESCORE.md` `## Acceptance` | a live, meaningful acceptance gate | named script → live property | **NOT WIRED** | `run_scoring_parity.py` → `lv_icp_tier` (archived, frozen, no writer in the documented procedure). The document never repoints this link at `check_tier_derived_parity.py` → `lv_icp_tier_derived`, the gate Phase 50 proved live. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Offline pytest suite green, fresh | `.venv/bin/python -m pytest -q -m "not live"` | `2821 passed, 154 skipped` | ✓ PASS (grew from 2719/128 — Phase 50 additions, not regression) |
| Offline node suite green, fresh | `node --test tests/n8n/*.test.mjs` | `tests 683, pass 683, fail 0` | ✓ PASS (grew from 676) |
| `test_rubric_change_guard.py` alone, fresh | `.venv/bin/python -m pytest -q tests/test_rubric_change_guard.py` | `6 passed` | ✓ PASS |
| `run_scoring_parity.py` tier check reads an archived property | static trace, corroborated by Phase 50's own live re-run | `props.get("lv_icp_tier")` fetched by name in `FIT_SCORE_PROPS`; feeds `tier_match` in the overall `match` | ✓ CONFIRMED (not independently re-executed live this pass — Phase 50's own 2026-08-14 amendment already re-ran the equivalent check live and is cited as evidence rather than re-run, per this task's read-only-and-no-redundant-live-calls constraint) |
| Evidence artifacts unedited since 2026-08-13 verification | `git log --oneline --since=2026-08-13T09:00:00 -- <each evidence path>` | no commits after the prior verification timestamp touch any cited JSON/MD evidence file | ✓ PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| RESCORE-01 | Defined, budget-bounded re-score procedure the operator can trust before invoking it | ⚠ PARTIALLY SATISFIED | Plan/cost mechanics (`--plan` mode, `49-PLAN-OUTPUT.json`) remain solid and unaffected. The "can trust" bar is now unmet for the acceptance step specifically: the doc's named acceptance gate no longer means what it says for any future tier-changing rescore. |
| RESCORE-02 | Whole-population re-score executed | ✓ SATISFIED (historical, unchanged) | 66/66 re-scored, W1 window; unaffected by Phase 50. |
| RESCORE-03 | Plain-language before/after tier comparison | ✓ SATISFIED (unchanged) | `49-RESCORE-REPORT.md`, published, operator-approved; unaffected by Phase 50. |

### Anti-Patterns Found

None new. No TBD/FIXME/XXX/TODO/HACK/placeholder markers in the touched files this pass
(`docs/OPERATOR-RESCORE.md`, `scripts/run_scoring_parity.py`).

### Human Verification Required

None. The new finding resolves entirely on documentary and code evidence — no runtime or
visual behavior needs a human to confirm it. The remediation (repointing the Acceptance
section) is a documentation fix a future plan can execute without new live probing, since
Phase 50 already proved the successor gate live.

### Gaps Summary

Two things are true at once, and both matter: (1) the specific gap the 2026-08-13 report
flagged — a missing AS-BUILT AMENDMENT disclosing the same-value-PATCH stale-tier failure
class — is genuinely closed, well-cross-referenced, and consistent with the document's own
house convention; (2) a new, more consequential gap has opened in the same acceptance-gate
machinery since then, caused by Phase 50's later, deliberate, well-evidenced deletion of
WF1 and archival of `lv_icp_tier`. The runbook's `## Acceptance` section still tells a
future operator that `scripts/run_scoring_parity.py`'s sweep is "the proof that a re-score
landed" and that a red sweep means "finish the re-score" — advice that is no longer
actionable for any company whose tier changes under a future rubric edit, because nothing
in the documented procedure writes `lv_icp_tier` anymore. Phase 50 already built and
live-proved the correct successor gate (`scripts/check_tier_derived_parity.py` against
`lv_icp_tier_derived`, with the known-stuck allowance `run_scoring_parity.py` lacks); the
runbook simply never got repointed at it. This blocks a clean `passed` verdict — the
phase's central "operator can trust before invoking it" promise is not currently true for
its acceptance step — but it does not indicate Phase 49 executed incorrectly, and the fix
is a short, well-evidenced documentation amendment, not new engineering.

---

*Verified: 2026-08-19*
*Verifier: Claude (gsd-verifier, re-verification)*
