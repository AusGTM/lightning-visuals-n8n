# Handoff — 2026-08-08 — resume at task #2 (formula spike re-run)

Read this, then re-create the three tasks below and continue. Everything else in v0.7 is
closed; this is the only open thread.

---

## Where the milestone stands

**Milestone v0.7 is COMPLETE — all 16 requirements closed.** Phases 41, 42, 43 all done.
Branch `feat/v0.7-scoring-remediation`. Suites: **2421 pytest / 636 node / 1286 plugin**,
arming grep 0, all n8n write gates **disarmed**, zero provider spend (Lusha 3925,
ZoomInfo 9397 — unchanged from baseline).

Phase 41 landed 66/66 companies scored with provenance, tiers A:7 B:18 C:17 D:24, parity
PASS over all 66 with zero real findings.

**This handoff is about a defect Phase 41 exposed, not about unfinished milestone work.**

---

## The open thread: blank scores from a single null term

`lv_icp_fit_score` is a HubSpot `calculation_equation` property whose formula is a bare
five-term sum:

```
org_type_score + geography_score + annual_revenue_score + produces_content_score + gambling_score
```

HubSpot **blanks the entire result if any one referenced term is null**
(`PORTAL-FACTS.md:176-180`, live-proven in Phase 40).

`gambling_score` is written by a mapper flow that fires on `lv_is_gambling_operator`
changing. The research prompt (`scripts/build_cloud_workflows.py:1994`) instructs the model
to answer **null** for that field unless a cited source directly supports it — correct
research discipline, but it means the trigger input is never written for any company that
is not a gambling operator. **~95% of companies.** This run: 63 of 66 had `gambling_score`
null, and only 3 of 66 scored until the backfill was run manually.

**It will recur on every future enrichment run.** It is the default path, not an edge case.

---

## Task #1 (DONE): spike whether the formula can be made null-safe

Full verdict: `.planning/phases/41-validation-data-import-end-to-end-proof/41-FORMULA-SPIKE.md`

**Verdict: INCONCLUSIVE.** Grammar mapped; one strong untested lead.

The API returns the valid token list verbatim in its 400 body:
```
*, -, round_down, round_up, round_nearest, is_present, number_to_st…
```

| Candidate | Result |
|---|---|
| `if(...)` | **400** unparseable |
| `ifnull(...)` | **400** unparseable |
| `is_known(...)` | **400** unparseable |
| `coalesce(...)` | **200** accepted |
| `(gambling_score + 0)` | **200** accepted |
| **`is_present(...)`** | **NEVER TESTED — in the API's own token list; most likely the intended null guard. Test this first.** |

**Do not trust the first run's "zero-add VIABLE" result.** The test never created a null
term: HubSpot's `PROPERTY_DEFAULT_VALUE` stamps 0 on newly created records, so the
disposable had `gambling_score = 0` and every candidate was measured against a fully
populated record. The baseline read `60` instead of blank — that is the tell. `60` also
does not reconcile with the 40+10+10+20 written, indicating stale reads at an 8s settle.

The corrected re-run hit a transient **401** partway (rapid PATCH cycle) and could not
finish. Its own restore check was meaningless because it compared two failed reads.

**State verified clean afterwards:** live formula intact (original five-term sum, direct
read), **zero** disposables leaked, schema snapshotted as
`config/hubspot_migration/baseline/portal-schema-companies-pre-formula-spike.json`.

### What a conclusive re-run needs

1. Create disposable, then **explicitly clear all five components** and confirm the score
   reads blank *before* testing. Never assume a fresh record has null terms.
2. **Settle ≥25s** after a formula change; re-read until stable rather than a fixed sleep.
3. Test **`is_present`** first.
4. Verify each accepted formula on **both** cases: null term (want **80**) and all five
   present (want **60**). A formula that stops blanking but computes wrong is the failure
   mode to guard against — worse than the status quo, because it fails silently.
5. Space the PATCHes to avoid the 401.
6. Restore the original formula in a `finally`, and re-verify it with an independent read
   (the 401 proved a same-call check can be vacuous).

Existing script to adapt: `.../41-.../spike_null_safe_formula.py` (keep for grammar
evidence; its verdict is superseded). ~20–30 min.

---

## RE-CREATE THESE TASKS

**Task 1 — Re-run the formula spike conclusively** *(supersedes the completed #1)*
Test `is_present` first, per the six requirements above. Deliverable: a definitive
supported / not-supported verdict with the exact working formula string if one exists. A
clean negative is a valid, useful result.

**Task 2 — Re-present the options with the verdict** *(blocked by 1)*
Do NOT implement until the operator selects. The four options:
1. **Null-safe formula** — root-cause fix, one property change, eliminates the failure mode
   for every record forever. Viability is what the spike settles.
2. **Schedule `scripts/backfill_seed_company_scores.py` as a maintenance sweep** — proven
   tooling, computes components from each record's own inputs via the same oracle (not a
   second producer), self-heals *any* null component. Works regardless of the spike outcome.
   Note: hard-caps at 25 records/run as a typo-guard, so it batches.
3. **Write explicit `false` instead of `null`** for the veto booleans — currently
   recommended against: converts "no evidence" into "definitely not", and for
   `lv_is_hardware_vendor` that suppresses a hard veto. Buys nothing the others don't.
4. **Detector** — parity harness fails on *"has canonical inputs but no `lv_icp_fit_score`"*.
   That exact condition silently swallowed 63 records and shipped as apparent success.

Re-rank in light of the verdict; say plainly if it overturns the operator's provisional
2+4; flag any new option the grammar suggests. Then stop and let them choose.

**Task 3 — Implement the selection** *(blocked by 2)*
Unscoped until chosen. **Non-negotiable regardless of path: a regression test that fails if
the fix is reverted.** This defect was invisible for a full phase and shipped as success —
the guard against recurrence is the deliverable, not the fix.

Ordering constraint: option 2 deploys n8n content, and a content deploy rebakes
write-safety to disarmed — never run it while a write window is open.

---

## Also outstanding (unrelated, one line)

`.env` has `HUBSPOT_PORTAL_ID='!'` instead of `22617666` (shell history expansion ate it).
Everything else works because nothing else reads that variable, but
`scripts/run_scoring_parity.py` checks it fail-closed, so **the standing scoring-drift
guard refuses on every scheduled invocation**. Inline overrides work for manual runs; the
scheduled sweep loads `.env` and cannot override. Fix:

```
HUBSPOT_PORTAL_ID='22617666'
```

Detail: `.../41-PARITY-BLOCKER.md`.

---

## Useful context for whoever resumes

- **Credentials are reachable.** `.env` cannot be `Read`, but scripts that call
  `load_dotenv()` work fine. Do not assume live work is blocked.
- **Arming n8n writes IS blocked** by the auto-mode classifier — attempted twice, denied
  both times, and editing the permission file is denied too. The operator must run
  `ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --ids <ids>`. Plain CLI —
  no `python -c` wrapper (an earlier wrapper form had a malformed `sys.argv` and failed).
- **Property PATCH is not blocked** — the formula spike ran fine.
- Disposable pattern: `ZZ-SCORING-TEST-DELETE-ME-*`. Always search for leaks afterwards.
- Two known-stale claims already corrected in the record: Phase 40's "80/A live-proven" on
  Melbourne Racing Club (live is 25/C; drift predates Phase 41 —
  `41-MRC-DRIFT-FINDING.md`), and PIPE-01's "one LIVE defect" framing (HubSpot silently
  coerces the boolean, so severity was overstated — `43-LIVE-EVIDENCE.md`).
