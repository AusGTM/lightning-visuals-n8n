# Phase 49 Plan 05 — W1 Arm Record

Durable pre-arm record for plan 49-05, appended to by Task 3 once W1 is authorised and run.
Single home for the whole window rather than living only in a summary written after the fact
(precedent: `.planning/phases/48-enrichment-coverage/48-ARM-RECORD.md`).

## Task 1 — Pre-flight (2026-08-13, disarmed, read-only)

### Precondition check (before any driver invocation)

Ran through the absolute-path dotenv wrapper, printed presence/values only (no token text):

```
HUBSPOT_PRIVATE_APP_TOKEN set: True
HUBSPOT_PORTAL_ID: 22617666
DRY_RUN: 'true'
ALLOW_SCORE_BACKFILL: None
```

Portal matches `22617666`. `DRY_RUN` defaults to `'true'` and `ALLOW_SCORE_BACKFILL` is unset
in `.env` — **no arming variable lives in the environment prior to this window.** Both driver
invocations below (`--snapshot`, `--plan`) ran with these same unarmed values; neither call
sets `DRY_RUN`/`ALLOW_SCORE_BACKFILL` in its own shell.

### P2 snapshot (report point 2 — after 47/47.5/48, before W1)

`scripts/rescore_population.py --snapshot --out .../49-P2-SNAPSHOT.json`, committed at
`.planning/phases/49-re-score-strategy-reporting/49-P2-SNAPSHOT.json`.

- **derived_at:** `2026-08-13T05:00:24.071224+00:00`
- **population_count:** 66
- **tier_distribution:** `A:9 B:27 C:21 D:7 Unscored:2` (sums to 66)

### Live population re-derivation vs. the 49-02 capture

Ran `scripts/rescore_population.py --plan` fresh (not committed as a new file — the plan
capture already committed in 49-02's `49-PLAN-OUTPUT.json` remains the cited artifact; this
run is a live re-derivation check only):

- **Fresh derivation:** `derived_at 2026-08-13T05:00:30.310867+00:00`, 66 ids,
  `chunks=1 chunk_size=100 max_records=100`, `arms_n8n_allowlist=False`,
  `cost={records:66, hubspot_batch_calls:1, n8n_executions:0, anthropic_calls:0,
  provider_credits:0, branch:weight}`.
- **49-02 capture:** `.planning/phases/49-re-score-strategy-reporting/49-PLAN-OUTPUT.json`,
  `derived_at 2026-08-13T04:01:11.038812+00:00`, 66 ids.
- **Comparison:** `fresh_ids == old_ids` — **exact match, symmetric difference is the empty
  set.** ~59 minutes apart, same 66-id population both times. The live derivation confirms
  the committed 49-02 capture rather than superseding it; no drift to record.

### Pre-window parity sweep (BEFORE state)

`scripts/run_scoring_parity.py` (no `--write-breakdown`), disarmed (no `DRY_RUN`/
`ALLOW_SCORE_BACKFILL` set — the sweep makes no writes regardless, it is read-only by
construction, but recorded here for completeness):

- **Exit code:** 1 (FAIL)
- **assertions_executed:** 67 (non-zero — not a false-green empty run)
- **real_findings count:** 31
- **verdict (verbatim):** `FAIL: 31 of 66 sampled companies diverge from the oracle or could
  not be checked (not the documented Needs Review divergence).`

The sweep is genuinely RED going in, confirmed by a live run in this session rather than
asserted from commit history. The report JSON this run produced (written by the script's own
default `PARITY_REPORT_DIR`, which resolves to the archived `40-scoring-engine-remediation-notes`
phase directory — a pre-existing script default predating that directory's archival, not a
Phase 49 artifact) was inspected for these figures and then discarded rather than committed:
it is a transient BEFORE-state read, not one of this plan's declared artifacts
(`49-P2-SNAPSHOT.json`, `49-P3-SNAPSHOT.json`, `49-W1-ARM-RECORD.md`, `49-PARITY-VERDICT.json`).
Task 3's own sweep run is the one whose report is committed, to `49-PARITY-VERDICT.json`.

**Note for the continuation agent:** 31 real findings pre-window is fewer than the 66-record
population and does not by itself need reconciling against the Phase 46 forecast below — some
`individual_club_team` records may already carry live scores that happen to match the new-weight
oracle (e.g. touched by an unrelated write since Phase 46) even though the bulk re-score has not
run. Task 3 explains the post-window count, not this one.

### Phase 46 forecast (pre-registered, quoted verbatim from `46-SIMULATION-REPORT.md`)

> Rows that change tier: 14 of 66
> Rows unchanged: 52
>
> | lv_org_type | changed | unchanged |
> |---|---|---|
> | individual_club_team | 14 | 10 |
> (all other org types: 0 changed)

Tier distribution forecast (`46-SIMULATION-REPORT.md`'s "Oracle — proposed rubric" row):
`A:7 B:31 C:2 D:7 Unscored:17 Needs Review:2` (this is the Oracle scenario, not the Live
scenario — it does not net against P2's Live-read `A:9 B:27 C:21 D:7 Unscored:2` one-for-one,
because Oracle assumes today's *current* inputs recomputed under the *proposed* rubric, while
P2 is HubSpot's own live-stored tier as of the read. The two P2/P3 points in this plan are both
Live reads, matching each other's basis; the Oracle row is cited here only as the pre-registered
prediction of *movement shape* — 14 rows, all `individual_club_team`, C→B — to compare Task 3's
observed movement against.)

Vetoed records (QRIC, both gambling-flagged records): scores predicted to move, tiers predicted
to hold, per D-02/46-02's live simulation.

### PORTAL-FACTS.md — path resolution (noted here for the continuation agent)

The plan's `files_modified` cites `PORTAL-FACTS.md` unqualified — every other path in this
plan's frontmatter is repo-root-relative, so this resolves to a **new file at repo root**,
distinct from the historical, phase-scoped, explicitly read-only
`.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md`. That
"never edit" prohibition was stated inside Phase 47's own CONTEXT.md and does not bind this
phase or this new file. No root-level `PORTAL-FACTS.md` exists yet as of this task; Task 3
creates it when it records the stamped-component finding.

---

*Continued in Task 3 (canary, remainder, settle, disarm, P3, parity verdict) once the
checkpoint at Task 49-05-02 is answered.*
