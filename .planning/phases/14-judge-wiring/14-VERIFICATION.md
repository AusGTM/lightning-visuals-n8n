---
phase: 14-judge-wiring
verified: 2026-07-21T00:00:00Z
status: passed
score: 5/5 roadmap success criteria verified (11/11 must-have truths verified)
behavior_unverified: 0
overrides_applied: 0
---

# Phase 14: Judge Wiring — Verification Report

**Phase Goal:** Conflicts and high-risk classifications get adjudicated on evidence, not
recall.
**Verified:** 2026-07-21
**Status:** PASSED
**Re-verification:** No — initial verification

Every check below was executed directly against the working tree by the verifier (not
read from SUMMARY.md prose). Deliberate-break-and-restore was performed live for RO-2;
the tree was confirmed clean before and after.

---

## Goal Achievement — ROADMAP Success Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Escalation triggers match CLAUDE.md §15 / JG-1 | ✓ VERIFIED | `computeEscalation` in `n8n/code/judge.js:100-133` implements all 5 JG-1 triggers (`org_type_conflict`, `produces_content_false`, `hardware_vendor_detected`, `gambling_operator_detected`, `confidence_band`); thresholds sourced from `config/escalation_policy.yaml` via generated `escalation.generated.js` (`ESCALATION_CONFIDENCE_BAND=[75,85]`, `JUDGE_MIN_CONFIDENCE=80`) — confirmed by direct `node -e` read of the generated file and `.venv/bin/pytest tests/test_judge_spec.py -q` (8 passed). |
| 2 | RO-1 (no retrieval → no judgement) and RO-2 (size conflicts never alone trigger judgement) proven structurally | ✓ VERIFIED | See "RO-2 structural proof" below — re-proven independently by the verifier, including a live deliberate-break-and-restore. |
| 3 | Judge confidence <80 → needs_review, never promotes (JG-3) | ✓ VERIFIED | Double-gated in code: `judgeVerdictFromHttpItem` (judge.js:272-274) rewrites `decision` to `needs_review` when `confidence < JUDGE_MIN_CONFIDENCE`; `applyJudgeVerdict` (judge.js:288-289) independently re-checks `>= JUDGE_MIN_CONFIDENCE` before promoting — a promoted value cannot reach output through either path below 80. |
| 4 | Evidence sufficiency (JG-4) enforced against the 20 real smoke rows, demotes to null never false | ✓ VERIFIED | Fixture-vs-source-doc match confirmed byte-for-byte; heuristic hand-traced against all 20 rows independently by the verifier (see below) — 8 sufficient / 11 insufficient / 1 judge_only, matching plan's acceptance criteria exactly; RWWA fails safe. |
| 5 | Vendor-flag INPUTs (`lv_is_hardware_vendor`/`lv_is_gambling_operator`) reach HubSpot via prompt + merge-fold widening; veto proven offline against unchanged `icp_scoring.py` | ✓ VERIFIED | Confirmed present in the BUILT `wf_enrichment_local_live.json` (Build Research Request node body + Merge Company node's fold whitelist), not just builder source; `git diff e08e8fd..HEAD -- src/icp_scoring.py` empty. |

**Score:** 5/5 roadmap criteria verified. 0 behavior-unverified. 0 overrides applied.

---

## Check-by-check evidence

### 1. Test suites

```
.venv/bin/pytest -q                    -> 147 passed, 0 failed
node --test tests/n8n/*.test.mjs       -> 74 passed, 0 fail
```
Both match the SUMMARY's claimed baseline exactly. **PASS.**

### 2. RO-2 structural proof (re-proven independently, including a live break)

- Read the BUILT `n8n/wf_enrichment_local_live.json` directly (not the builder source):
  `Judge Gate` node's `jsCode` (16,366 chars) contains neither `row.conflicts` nor
  `CONFLICT_WATCH` — confirmed by direct string search.
- BFS over the workflow's `connections` graph (own script, not reusing the plan's test):
  `Judge Gate` **can** reach `Merge Company`; `Merge Company` **cannot** reach `Judge Gate`.
  Ancestry confirmed structurally, not by comment.
- **Live deliberate-break-and-restore performed by the verifier:** injected
  `// deliberate break: const _x = row.conflicts;` immediately after
  `ENRICH_JUDGE_GATE = inline(...)` in `scripts/build_cloud_workflows.py`, rebuilt
  (`.venv/bin/python scripts/build_cloud_workflows.py`), ran
  `.venv/bin/pytest tests/test_judge_spec.py -q -k ro2` → **failed** with
  `AssertionError: RO-2: Judge Gate must not reference the downstream size-disagreement
  array`, exactly as expected. Restored `scripts/build_cloud_workflows.py` from a file
  copy (never `git checkout --`), rebuilt again,
  `git diff --exit-code n8n/ scripts/build_cloud_workflows.py` → clean, and the
  ro2 test passed again (1 passed).

**PASS — RO-1/RO-2 hold and the guard demonstrably fires on regression.**

### 3. JG-4 correctness on real data

- The 20-row fixture (`tests/fixtures/evidence_sufficiency_cases.json`) was diffed by
  hand against `.planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md`
  rows 71-80 (second closed-won run) + 114-123 (closed-lost control): domains, citation
  URLs, and verdicts match exactly, row for row.
- Independently traced the stated rule — `(host stripped of www == domain stripped of
  www, or host is a known video host) AND path not in {"", "/"}` — against all 20 rows by
  hand (not by running the code): **all 20 verdicts matched expected** (8 sufficient / 11
  insufficient / 1 judge_only — matches the Task 2 acceptance criteria exactly). Row 8
  (RWWA, `racingwa.com.au` citation vs `rwwa.com.au` HubSpot domain) fails safe to
  `insufficient` (never a wrong promote, never `false`) exactly as documented — this is a
  host mismatch causing `hostMatches` to be `false`, not a bug in the rule.
- Row 9 (QRIC, `claim: false`) confirmed excluded from the sufficiency loop by
  construction (`applyEvidenceSufficiency` no-ops unless `data.lv_produces_content ===
  true`, judge.js:46).

**PASS.**

### 4. TS-1 inviolable

Grepped every `lv_produces_content` reference in `n8n/code/judge.js` and `src/judge.py`:
- `src/judge.py` never references `lv_produces_content` at all (D4 — only the pure
  sufficiency function, operating on URL/domain strings, is ported).
- `applyEvidenceSufficiency` (judge.js:53) only ever writes `lv_produces_content: null`;
  no code path in this function can write `false`.
- The one `=== false` write-preserving path (`applyUnadjudicated`, judge.js:159) is
  documented as deliberately unchanged (D5 table — an evidenced `false` still flows per
  Phase 13 TS-3), and is a pass-through, not a new write.
- `judgeVerdictFromHttpItem`/`applyJudgeVerdict` can promote a judge-chosen `false` value
  **only** when the model returns confidence ≥80 with a `chosen_field`/`chosen_value`
  pair — this is the judge's designed adjudication path (JG-1's
  `produces_content_false` trigger explicitly routes an evidenced-false candidate to the
  judge, per spec §8 JG-1/JG-5), not a bypass of "insufficient evidence." The JG-4
  deterministic heuristic — the only new path that classifies "insufficient" — never
  writes `false`, confirmed above.
- Test coverage in `tests/n8n/judge.test.mjs` explicitly asserts
  `assert.notEqual(result.data.lv_produces_content, false)` for the Supertech-shaped
  insufficient case.

**PASS.**

### 5. JG-3 in code (not just tests)

Confirmed via direct read of `n8n/code/judge.js`:
- Line 272: `if (!(verdict.confidence >= JUDGE_MIN_CONFIDENCE)) { verdict = {...verdict,
  decision: "needs_review"}; }` inside `judgeVerdictFromHttpItem`.
- Line 288-289: `applyJudgeVerdict`'s `promotes` boolean independently re-checks
  `v.confidence >= JUDGE_MIN_CONFIDENCE` before allowing a promoted value through — a
  second, independent gate, not a duplicate of the same check.
- `JUDGE_MIN_CONFIDENCE = 80` confirmed live in the generated
  `n8n/code/escalation.generated.js` and cross-checked against
  `human_review.use_when.sonnet_confidence_below` in `config/escalation_policy.yaml`.

**PASS.**

### 6. Approach C containment

- `ls n8n/code/icpScoring.js` → does not exist.
- `git diff e08e8fd..HEAD -- src/icp_scoring.py` → empty (byte-identical since before
  this phase).
- The only `anti_icp_flag`/`lv_icp_tier` references in built JS are (a) a **read-only**
  HubSpot properties fetch list in the Fetch Existing Company node, and (b) inert policy
  metadata (`class: "score_output"`/`"veto_output"`) inside `DEFAULT_COMPANY_POLICY` in
  `mergeCompanies.js` — both pre-existing (confirmed via the `mergeCompanies.js`
  byte-identical diff, check 8) and neither computes a score or veto; nothing populates
  `candidateRow.lv_icp_tier`/`lv_anti_icp_flag` anywhere in the codebase.

**PASS.**

### 7. Criterion 5 real deliverable (verified in the BUILT workflow, not builder source)

- `src/web_research.py`'s `RESEARCH_SYSTEM` schema string contains
  `"lv_is_hardware_vendor":<bool|null>,"lv_is_gambling_operator":<bool|null>` plus the
  hard-veto-input sentence (lines 39-40, 51-52); `REQUIRED_FIELDS` lists both (lines
  20-21).
- The **built** `n8n/wf_enrichment_local_live.json`'s `Build Research Request` node body
  contains the identical schema fragment (`'"lv_is_hardware_vendor":<bool|null>,"lv_is_gambling_operator":<bool|null>},'`)
  and the hard-veto-input sentence, confirmed by direct JSON parse + regex search — not
  read from `build_cloud_workflows.py` source alone.
- The built `Merge Company` node body's research-fold whitelist (the `for (const f of
  [...])` loop that reads `rc.data`) includes `lv_is_hardware_vendor` and
  `lv_is_gambling_operator` — confirmed by direct JSON parse of the built file.
- `test_prompt_parity_vendor_flags` exists and passes (part of the 147-passed run).

**PASS.**

### 8. mergeCompanies.js byte-identical

`git diff e08e8fd..HEAD -- n8n/code/mergeCompanies.js` → empty output, exit 0.

**PASS.**

### 9. Rebuild determinism

Ran `.venv/bin/python scripts/build_cloud_workflows.py` twice in sequence;
`git diff --exit-code n8n/` clean after each. Diffed all 5 workflow JSONs' node bodies
against `e08e8fd` (pre-phase): only `wf_enrichment_local_live.json` has any node change;
within it, only `Merge Company`, `Build Research Request`, and `Decide Company Action`
have changed `jsCode` among pre-existing nodes; `Apply Judge Verdict`, `Build Judge
Request`, `IF Needs Judge`, `Judge Call`, `Judge Gate` are additions. All other 4
workflow JSONs (`wf_contact_ingest_cloud/local.json`, `wf_enrichment_cloud.json`,
`wf_enrichment_local.json`) are byte-identical to `e08e8fd`.

**PASS.**

### 10. AR guards

`.venv/bin/pytest tests/test_architecture_guard.py -q` → 17 passed. `api.anthropic.com`
was already in `ALLOWED_HOSTS` (added in Phase 13); `test_architecture_guard.py` itself
is unchanged since `e08e8fd`, and the Judge Call node's host reuses the existing entry —
no new host was added by this phase's AR-2 allowlist.

**PASS.**

### 11. icp_scoring.py bug adjudication — CONFIRMED, see dedicated section below.

### 12. Anti-patterns

Scanned every phase-touched file (13 files) plus the specific new/changed node bodies
inside the built workflow JSON (`Judge Gate`, `IF Needs Judge`, `Build Judge Request`,
`Judge Call`, `Apply Judge Verdict`, `Merge Company`, `Build Research Request`, `Decide
Company Action`) for `TODO`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` — zero matches.

**PASS.**

---

## icp_scoring.py tier-precedence bug — adjudication (per user request, NOT fixed here)

**Confirmed real**, by direct read of `src/icp_scoring.py` and by running the unmodified
module live.

**Exact defect.** Lines 101-110 correctly set `tier = "D"` whenever `anti_icp_flag` fired
(hardware-vendor, gambling, or non-ANZ veto). But lines 115-119 unconditionally
re-execute afterward:

```python
confidence = 85
if org_type == "unknown" or produces_content is None:
    confidence = 55
    tier = "Needs Review" if score >= 15 else "Unscored"   # line 118 — overwrites tier
    recommended_motion = "research_more"                    # also overwrites motion
```

This block never checks whether `anti_icp_flag` is already `True`. When
`lv_produces_content is None` (the JG-4-demoted value) **and** an independent hard veto
has already fired, `tier` gets silently clobbered from `"D"` back to
`"Needs Review"`/`"Unscored"`, and `recommended_motion` is clobbered from
`"disqualify"` back to `"research_more"`.

**Live reproduction** (run directly against the unmodified module, Supertech Electronics
shape — `lv_is_hardware_vendor=True`, `lv_org_type="hardware_vendor"`,
`lv_country_region_normalized="AU"`):

| `lv_produces_content` | `tier` | `anti_icp_flag` | `recommended_motion` |
|---|---|---|---|
| `True` | `"D"` | `True` | `"disqualify"` |
| `None` (JG-4-demoted) | `"Unscored"` | `True` | `"research_more"` |

The veto **signal** (`anti_icp_flag` + `anti_icp_reason`) is independent of
`lv_produces_content` in both branches, as `test_jg5_supertech_hardware_veto_independent_of_jg4`
claims and as this phase's routing relies on. The `tier` **label** — and, newly noted
here, the `recommended_motion` **label** — are not.

**One-line fix** (line 116): change

```python
if org_type == "unknown" or produces_content is None:
```
to
```python
if (org_type == "unknown" or produces_content is None) and not anti_icp_flag:
```

Verified offline by the verifier (simulated the fix in an isolated script, not applied
to the repo): with the guard added, both `True` and `None` branches report `tier="D"`,
`anti_icp_flag=True`. Confirms the fix closes the gap as claimed.

**Blast radius.** Searched every existing test that calls `compute_icp_score` /
`icp_scoring.score` (`tests/test_icp_scoring.py`'s 16 cases, `tests/test_web_research_spec.py`'s
TS-1/TS-4/ER-1/AT-2 cases): **none** combine a fired hard veto
(`lv_is_hardware_vendor=True`, `lv_country_region_normalized` non-ANZ, or
`lv_produces_content=False`) with `lv_produces_content is None` simultaneously in the same
call — confirmed by reading every call site. The blast radius of the one-line fix is
genuinely zero regressions against the current suite, as the SUMMARY claims.

**Verifier's assessment:** the bug report is accurate, not overstated, and not
downplayed. The test that surfaces it (`test_jg5_supertech_hardware_veto_independent_of_jg4`)
is honest — it asserts the actual (buggy) `tier` behavior in the `None` branch rather than
force-asserting `"D"` or silently passing. This is a pre-existing defect (present before
Phase 14 touched this file), out of this phase's Do-Not-touch scope, and does not block
Phase 14's goal — `src/icp_scoring.py` is a dev-oracle-only module (AR-3) with no
production write path in this milestone (Approach C locks `lv_icp_tier` computation out of
the pipeline entirely). It is a legitimate carry-forward decision for the user: whether to
apply the one-line fix now (as a separate, explicit, sign-off gated change) or defer it
until a future phase actually depends on `icp_scoring.py`'s `tier` output for in-pipeline
routing.

**Not fixed here, per the user's explicit instruction** ("Do NOT fix it — this is an
adjudication for the user").

---

## Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| REQ-evidence-before-judgement | ✓ SATISFIED | All 11 must-have truths from PLAN.md frontmatter verified against the codebase (escalation single-source, JG-4 heuristic + parity, RO-1/RO-2 structural exclusion, JG-3 never-promotes-below-80, vendor-flag prompt+fold widening, deterministic rebuild). |

## Anti-Patterns Found

None in phase-touched files or new/changed node bodies.

## Human Verification Required

None. All must-haves were verifiable by direct code/JSON inspection, hand-tracing, and
live deliberate-break-and-restore.

## Gaps Summary

No gaps. One pre-existing, out-of-scope defect in `src/icp_scoring.py` was independently
confirmed (see adjudication section) — it does not block this phase's goal and was
correctly left unfixed per the plan's own Do-Not list and the user's explicit
instruction.

---

_Verified: 2026-07-21_
_Verifier: Claude (gsd-verifier)_
