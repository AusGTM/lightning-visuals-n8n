---
phase: "47"
slug: "veto-remediation"
status: verified
# threats_open counts OPEN threats at or above block_on (high). T-47-08 was medium → never counted.
# 2026-09-03, AFTER the audit: T-47-08 CLOSED by operator grant — the ordering bug is fixed and two
# further live-discovered corrections folded back. See "Resolution" under its section.
threats_open: 0
threats_open_below_threshold: 0
unregistered_surface_found: 2
asvs_level: 1
created: "2026-09-03"
---

# Phase 47 — Security

> Retroactive secure-phase run, 2026-09-03. All four plans carry plan-time `<threat_model>` blocks
> — a verification pass, not retroactive-STRIDE. 26 threats. Scope is **47-veto-remediation only**;
> the sibling `47.5-veto-recompute-path` has its own register and its own SECURITY.md.
>
> **Archival drift, not a missing mitigation:** COVER-01/02 and VETO-01/02/03 are no longer in
> `.planning/REQUIREMENTS.md` because the v0.9 milestone was archived. They survive intact in
> `.planning/milestones/v0.9-REQUIREMENTS.md`, including Plan 02's `Phase 47 + 48` traceability
> split and Plan 04's ticks.

---

## The open threat: T-47-08 — the declared mitigation is not the code that ran

**A shape distinct from the rest of this audit round.** Elsewhere the register had gone stale
(a mitigation citing an artifact never built) or been invalidated (an acceptance whose premise a
later change destroyed). Here the cited mitigation **exists and is correct**, and a *different
code path* performed the live production writes.

**What the register cites.** `verify_post_run` plus a "re-stamp once, raise if it diverges again"
loop. Both are genuinely present, in `scripts/remediate_veto_companies.py:1058-1072`, inside
`main()`.

**What actually ran.** `main()` was never executed for the production writes. Its armed sequence
calls `settle_tier` *before* the D-18 webhook POST, which is structurally unsatisfiable for this
phase's exact target population — WF1 pins `lv_icp_tier` to `D` while `lv_anti_icp_flag` still
reads `true`, and only the webhook clears it. This was discovered by running `main()` live against
`9604732797` and watching it fail. The writes were then performed by
`.planning/phases/47-veto-remediation/47-armed-driver.py`: a hand-written driver, never added to
`scripts/`, never covered by `tests/test_remediate_veto_companies.py`, which reorders the sequence
and — per its own comment block at `:199-217` — records a live operator decision to **drop** the
re-stamp mechanism for metadata divergence: *"Operator chose: do not re-stamp; record who
diverged."*

So a clobbered **input** field still stops the run, but a clobbered **metadata timestamp** — which
fired on **12 of 17** records, always `lv_produces_content_verified_at` — is now tolerated
silently and permanently, not "re-stamped once inside the armed window" as the register states.

**Two compounding facts, both verified at HEAD:**

1. **The ordering bug was never fixed.** `git log -S"settle_tier(rec" -- scripts/remediate_veto_companies.py`
   shows only the original 47-01 commit touched that line. Worse, the module's own docstring
   (`:33-38`) **still instructs an operator to invoke `main()` directly for an armed run** —
   following the documented procedure today would reproduce the exact failure this phase spent a
   live session diagnosing.
2. **One of the six live corrections *was* folded back.** The webhook timeout fix (30s → 300s) made
   it into `main()`, with a comment at `:636-641` saying so. The ordering fix and the re-stamp
   downgrade did not. So the fold-back path existed and was used selectively — this is not a case
   of nobody knowing how.

**Severity is `medium`**, below `block_on: high`, so `threats_open` is 0 and nothing is gated. But
it is deliberately not a clean CLOSED: the register's evidence citation was not what protected the
live run, and `main()` as it stands would not reproduce that run's outcome if invoked as its own
docstring documents.

**Two ways to close it:** fix `main()`'s ordering and reconcile the docstring so the documented
path is the one that works; or amend the register to cite `47-armed-driver.py` and record the
re-stamp downgrade as the operator decision it was. Either is an operator call, not this audit's.

### Resolution — 2026-09-03, first option taken by operator grant

The operator granted the fix, transcribed verbatim:

> execute the following, grant is authorised: … **T-47-08** · `scripts/remediate_veto_companies.py`
> … **I'd fix the code — the docstring describes the correct sequence.**

**The bug outlived its own mechanism, and that is why it was still live.** The finding above
explains it via WF1 pinning `lv_icp_tier` to `D`. Phase 50 deleted WF1 and archived `lv_icp_tier`,
and `settle_tier` now polls `lv_icp_tier_derived` — so a reader could reasonably conclude the
ordering no longer matters. It does. `lv_icp_tier_derived`'s `calculation_equation` names
`lv_anti_icp_flag_num` in its opening `if` clause (`50-06-PLAN.md:384`), and that numeric mirror is
written by the n8n `Decide Company Action` node. Same dependency on the webhook, new
serialization. Verified before changing anything, not assumed.

**Three of the driver's live corrections folded back**, into a new `run_armed_record()` extracted
from `main()`'s inline loop:

1. **Correction 1 — ordering.** `inputs+metadata → components → webhook POST → settle_veto →
   settle tier → verify`, the sequence `47-armed-driver.py:11` records as proven live.
2. **Correction 3 — the tier is settled, not asserted** (`settle_tier_stable`). The old call
   asserted the local oracle's pre-webhook tier, which n8n's research lane can legitimately move
   after our patch; the settled tier is now recorded against its oracle counterpart instead. The
   veto assertion stays hard — the veto is this phase's actual bar.
3. **Correction 5 — a diverged metadata stamp is recorded, never re-stamped.** The re-stamp cannot
   converge and fired on 12 of 17 records. The partition is preserved exactly: a clobbered **input**
   field still raises, because it could reinstate the very veto this phase removes.

**Scope of the grant, stated plainly.** Its letter is correction 1. Corrections 3 and 5 are folded
back because without them the documented path *still fails* — a reordered-but-asserting
`settle_tier` cannot converge when the research lane moves the score, and the re-stamp loop raises
on a divergence that always recurs. This closure's own wording is "so the documented path is the
one that works." Both are **operator decisions already on record** — `47-armed-driver.py`'s
"Correction 3 (operator-approved, live-discovered)" and this section's own quoted "Operator chose:
do not re-stamp; record who diverged" — and were **transcribed, never composed** by this
resolution.

**Deliberately not folded back**, so their absence is not read as oversight: the driver's D-23
one-record region override for Jam TV (`17317850381`) with its paired veto-persists branch, and the
Simtech LED gate-skip blank-then-restore of `lv_org_type`. Both were single-record decisions for a
population already remediated, and CLAUDE.md §13.0 prohibits the gate-skip workaround outright.

**The coverage gap that let this survive is closed.** The audit's own diagnosis was that every
individual guard was tested but "the orchestration that sequences them" was not.
`run_armed_record()` takes injectable legs (the precedent is `run_coverage_window` in
`scripts/enrich_coverage_companies.py`), and five tests in
`tests/test_remediate_veto_companies.py` now pin the order, the no-re-stamp rule, the input-clobber
raise, the record-don't-assert tier, and the default tier settler. The ordering test was
perturbation-proved: restoring the pre-fix sequence turns it RED, restoring the fix turns it GREEN.

`settle_tier`'s own docstring was corrected in the same commit — it still claimed a "pure-HubSpot
chain … → WF1 → `lv_icp_tier`" while polling the derived property, the same record-vs-code shape
this audit round exists to catch.

**This partially remediates unregistered surface 1** below: the orchestration that performed the
live writes now lives in `scripts/` under test, rather than only in a throwaway driver. It does
**not** register that surface or surface 2 — neither was in the grant.

---

## Unregistered surface (no threat ID covers these)

No summary in this phase carries a `## Threat Flags` section, so the executor did not self-report
either of these:

1. **`47-armed-driver.py` itself** — a second write-orchestrator that performed nearly all of the
   phase's live production writes, outside the test suite's coverage. The individual guards it
   reuses all still fire inside it (`FORBIDDEN_PROPS` assertions, `_writes_allowed()`,
   `_run_property_existence_guard`, `verify_post_run` — all confirmed present), so the primitives
   held. What was never offline-verified is the **orchestration that sequences them**.
2. **The Simtech LED "gate-skip unstick"** (`47-armed-driver.py:109-144`) — a live, in-window,
   temporary blank-then-restore of `lv_org_type` on a real production record, used to force a
   downstream recompute around the defect Phase 47.5 later fixed properly. Disclosed and reverted,
   and it used tested primitives — but temporarily nulling a real input field on a production CRM
   record is a **write shape the STRIDE register never anticipated**, and no threat ID covers it.

Neither blocks. Both are named here rather than folded into an adjacent "closed".

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| script → HubSpot CRM v3 | Production CRM records; a malformed or over-broad payload mutates real sales data | scoring inputs, component scores, metadata stamps |
| script → n8n Cloud webhook | Shared-secret endpoint that triggers a workflow with **its own** write authority | property-change event, company id |
| shell env → script | Arming flags, HubSpot token, Anthropic key and webhook secret all arrive ambient | per-shell arming vars, credentials |
| Anthropic `web_search` → script | Untrusted web content summarised into values written to the CRM | org type, content signals, evidence URLs |
| planning docs → later execution | Cost/coverage documents authorize and bound the live write; a wrong figure is acted on without re-derivation | projected cost, requirement scope |
| operator shell → production CRM / n8n Cloud | An armed window with live write authority over 17 real companies | write-authorization state, record ids |
| n8n Decide node → production CRM | The workflow writes the derived veto fields for records in its allowlist | `lv_anti_icp_flag`, `lv_anti_icp_reason` |
| HubSpot portal UI → operator judgement | VETO-03's proof is a human reading a filtered view, deliberately script-free | none — human-verified count |

---

## Threat Register

### 47-01 — The remediation script (write legs, guards)

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-47-01 | Tampering | `build_*_patch` payload construction | high | mitigate | `remediate_veto_companies.py:377,443,468,480` — `assert_disjoint(props, FORBIDDEN_PROPS, …)` in **all four** builders. `FORBIDDEN_PROPS` (`:122`) has since gained `lv_icp_tier_derived` via a later phase (`0e351e1`) — **additive, not weakened**. `pytest -k never_write` → 6 passed. | closed |
| T-47-02 | Elevation of Privilege | `main()`'s write branch | high | mitigate | `_writes_allowed()` (`:263-266`) is `(not DRY_RUN) AND ALLOW_VETO_REMEDIATION`, called at `:1035` before any write branch. Two independent keys. | closed |
| T-47-03 | Tampering | id selection | high | mitigate | `resolve_pinned_ids` (`:216-235`) raises `PinRefused` for any id outside `PINNED_COMPANY_IDS`, **naming** the offending id and distinguishing the three excluded ids by name. `assert_disjoint(PINNED_COMPANY_IDS, EXCLUDED_COMPANY_IDS, …)` runs at **import time** (`:107-110`) via `src/guards.assert_disjoint` — not a bare `assert`, so it survives `python -O`. | closed |
| T-47-04 | Information Disclosure | webhook POST and HubSpot client | high | mitigate | `post_webhook_event` (`:627-660`) places the secret only in the `X-Enrichment-Secret` header dict, never printing it. **Every** `print(` in the file was grepped — none references `config`, `header`, `secret` or `token`. | closed |
| T-47-05 | Denial of Service | record cap | medium | mitigate | `HARD_CEILING_RECORDS = DEFAULT_MAX_RECORDS = 17` (`:178-179`); `_resolved_max_records()` clamps via `min(...)`; `refuse_if_over_budget` (`:709-718`) **raises and returns `ids` unmodified rather than truncating** — a silent truncation would have been the dangerous failure. | closed |
| T-47-06 | Spoofing | Anthropic `web_search` results | medium | mitigate | `build_input_patch` (`:345-372`) — `_classify_org_type` requires an enum-exact match; evidence-gated org types require `_has_field_evidence`; `produces_content` requires `isinstance(..., bool)` **and** evidence for both true and false. Hardened live in Plan 03. | closed |
| T-47-07 | Repudiation | post-run state | medium | mitigate | `47-RUN-REPORT.md` carries per-record before/after with source metadata and `_verified_at`/`_verified_by_model` stamps; `verify_post_run` present (`:723-737`). | closed |
| **T-47-08** | **Tampering** | **n8n re-research lane overwriting stamps** | **medium** | **mitigate — amended to the code that actually runs** | **Amended 2026-09-03 by operator grant. The declared re-stamp loop is GONE, not repaired: it cannot converge (n8n's research lane always writes its own `lv_*_verified_at` after ours) and it fired on 12 of 17 records. The mitigation is now record-who-diverged, per the transcribed operator decision — `run_armed_record` (`scripts/remediate_veto_companies.py`) records diverged stamps in its returned entry and prints them, while still RAISING on a clobbered INPUT field, which could reinstate the veto this phase removes. The ordering bug that forced `47-armed-driver.py` to exist is fixed in the same commit, so `main()` is once again the path its own docstring documents. Tests: `test_armed_leg_records_a_diverged_metadata_stamp_and_never_re_stamps_it`, `test_armed_leg_still_stops_the_run_when_an_input_field_is_clobbered`, plus the ordering test, perturbation-proved. See "Resolution" above.** | **closed** |
| T-47-01-SC | Tampering | package installs | low | accept | `git show --stat` on all five Plan-01 commits: no dependency-manifest diff. | closed (accepted) |

### 47-02 — Traceability, cost estimate, coverage matrix

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-47-09 | Repudiation | `47-COST-ESTIMATE.md` | medium | mitigate | Every figure sourced (Phase 20 canary, `estimate_cost()` quoted directly); unmeasured `web_search` per-search billing **explicitly labelled unmeasured** rather than silently estimated. | closed |
| T-47-10 | Tampering | `.planning/REQUIREMENTS.md` | medium | mitigate | The amendment landed as scoped edits (`2736bb4`) and survives in the archived `v0.9-REQUIREMENTS.md` with the `Phase 47 + 48` split and its "neither phase closes alone" footnote intact. | closed |
| T-47-11 | Information Disclosure | the four Plan-02 documents | low | mitigate | All grepped for `pat-na1`/`sk-ant`/bearer-shaped strings — none found. | closed |
| T-47-02-SC | Tampering | package installs | low | accept | `2736bb4`/`917e454`/`a9d183f` are docs-only diffs. | closed (accepted) |

### 47-03 — Before-snapshot, property guard, live research, dry-run

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-47-12 | Spoofing | live-vs-mock research path | high | mitigate | `47-RESEARCH-RESULTS.json` has 17 entries, and 47-03-SUMMARY D3 records **zero** evidence-URL intersection with the mock fixture — proving live research actually ran rather than a fixture being replayed. | closed |
| T-47-13 | Tampering | an unknown property name in the batch payload | high | mitigate | `_run_property_existence_guard` (`:753`) is wired into `main()` at `:1002` and refuses **before** any write branch. The live run found **19 of 21** D-09 stamp names absent (D-21) — exactly the silent-ignore trap CLAUDE.md §4.0 warns about — then narrowed and re-verified at zero missing. | closed |
| T-47-14 | Spoofing | web-sourced org-type/content claims | medium | mitigate | Evidence-URL gating in `build_input_patch`, plus a pre-arm table in `47-RUN-REPORT.md` exposing every classification before arming. That table caught two live defects (free-text org_type, over-broad `lv_is_gambling_operator`) before any payload was trusted. | closed |
| T-47-15 | Information Disclosure | the committed dry-run artifact | medium | mitigate | `47-DRYRUN.md` grepped — payloads only, no secret-shaped string. | closed |
| T-47-16 | Denial of Service | unbounded research spend | medium | mitigate | `refuse_if_over_budget` runs before the first paid call (D8: cost printed before any `RESEARCHED:` line); `WEB_RESEARCH_MAX_SEARCHES` still present at `src/web_research.py:128`; the pinned set bounds records to 17. | closed |
| T-47-03-SC | Tampering | package installs | low | accept | No dependency file touched in the commit range. | closed (accepted) |

### 47-04 — The armed window

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-47-17 | Elevation of Privilege | the armed window staying open | high | mitigate | `47-RUN-REPORT.md` §VETO-02 quotes the disarm verbatim with `n8n_arming.disarm`'s independent re-read matching `OVERLAY_DISABLED_LITERALS` — and §"Window accounting" shows this held across **all five** arm/disarm cycles, each independently re-read, not just the final one. | closed |
| T-47-18 | Tampering | n8n allowlist scope | high | mitigate | The armed command used `TEST_RECORD_IDS` = exactly the 17 pinned ids on each of the five cycles; the post-run disarm re-read shows `TEST_RECORD_IDS: ""`. | closed |
| T-47-19 | Repudiation | claiming the window closed | high | mitigate | Both disarm outcomes quoted verbatim including re-read values (`:407-434`). | closed |
| T-47-20 | Information Disclosure | secrets in the run log/report | medium | mitigate | `47-RUN-LOG.json`, `47-AFTER.json`, `47-BEFORE.json` grepped — no secret-shaped string. | closed |
| T-47-21 | Tampering | weakening a red test to close the phase | medium | mitigate | `test_veto_clear_after_correction`'s logic is unmodified at HEAD (still `@live`-gated with real assertions), and no commit in this phase touches `scripts/run_scoring_parity.py`. | closed |
| T-47-22 | Denial of Service | a partial write leaving records mid-state | medium | mitigate | §"Window accounting" shows every one of the five aborts surfaced **loudly**, each with a named record and cause; `47-RUN-LOG.json` records exactly which records were attempted. Five aborts that were all loud is better evidence than one clean run. | closed |
| T-47-04-SC | Tampering | package installs | low | accept | Commit range `196b2d3`..`f289adc` touches no dependency file. | closed (accepted) |

*Status: closed · closed (accepted) · open — below `high` threshold (non-blocking)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-47-01 | T-47-01-SC | No package-manager install in Plan 01; `anthropic`, `requests`, `pydantic`, `PyYAML` already present. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-47-02 | T-47-02-SC | Plan 02 is documentation-only — no dependency file touched by any of its three commits. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-47-03 | T-47-03-SC | Plan 03 adds no dependency. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-47-04 | T-47-04-SC | Plan 04's live-run commits touch no dependency file. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open (blocking) | Open (below threshold) | Unregistered | Run By |
|------------|---------------|--------|-----------------|------------------------|--------------|--------|
| 2026-09-03 | 26 | 25 (21 mitigation-verified, 4 accepted) | 0 | 1 (T-47-08, `medium`) | 2 | `gsd-security-auditor`, `asvs_level: 1` |
| 2026-09-03 (later, post-audit) | 26 | 26 (22 mitigation-verified, 4 accepted) | 0 | 0 | 2 (unchanged) | operator-granted fold-back; T-47-08's mitigation amended to the code that runs |

**The most valuable thing this phase's own record already did:** it *disclosed* the `main()`
failure and the driver substitution in `47-04-SUMMARY.md` and `47-RUN-REPORT.md` rather than hiding
them. T-47-08 is open not because the phase concealed anything, but because the **threat register
was never updated to match what the disclosure said**. The honesty was in the summary; the register
kept pointing at the code that did not run.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (no open threat at or above `high`)
- [x] **T-47-08 CLOSED 2026-09-03 by operator grant** — `main()`'s ordering fixed, two further
      live-discovered corrections folded back, `settle_tier`'s stale docstring corrected, and the
      orchestration put under test for the first time
- [ ] **Two unregistered surfaces named, no threat IDs assigned** — still open; surface 1 is
      partially remediated (the orchestration now lives in `scripts/` under test), but neither was
      in the 2026-09-03 grant and neither is registered
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03. T-47-08 outstanding at that verification; **closed later the
same day** by the operator-granted fold-back recorded under "Resolution".
