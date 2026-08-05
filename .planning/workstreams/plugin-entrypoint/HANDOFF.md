# v0.6 Handoff — Claude Plugin Entrypoint

**Written:** 2026-08-04 (supersedes both 2026-08-03 handoffs) · **Milestone:** v0.6 · **Workstream:** `plugin-entrypoint`
**Read this first on a fresh context.** Everything below was verified live; do not re-derive or
"correct" it. The evidence trail is git history `3f575ec..94d32d5` plus the FINDINGS/SUMMARY files
named per phase.

---

## 1. Where things stand

**Branch `feat/v0.6-plugin-entrypoint`, fully pushed to `origin/master` (fast-forward), tree clean.**
Suites: **1784 pytest / 6 skipped (root, includes plugin) · 550 node · 903 plugin-standalone** — via
`.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` (FILE form). Committed
`n8n/*.json` disarmed (grep → 0). Live tenant verified **disarmed PASS** (5 workflows / 12 declaring
nodes). Crontab empty. No gate variable set anywhere.

| Phase | State |
|---|---|
| 23–27 | ✅ COMPLETE incl. their canaries (unchanged from prior handoff) |
| 28 | ✅ **COMPLETE incl. RB-7 armed canary** — arm→dispatch→disarm verified, execution 1152, 54.37 s window, one record. CONTROL-01…07 sealed |
| 29 | ✅ **COMPLETE via Phase 32** — NOTICE-01/02/04/05 complete; NOTICE-03 sealed by the LLM-free trigger |
| 30 | ✅ **COMPLETE — RB-9 close 2026-08-04 (armed window #2)**. Valid-enum approve landed on `9604614548`: REVIEW-04 demonstrated (provenance `source: human`, `human_approved`, timestamp, operator reason, `superseded_source: waterfall` readable; `reviewed_by`/`reviewed_at` stamped). REVIEW-02 sealed via the D-31 endpoint probe (`domain` withheld on preview AND submit, unchanged on re-read; backstop path NOT probed — still allowlists by key). Evidence: 30-07-SUMMARY.md "RB-9 CLOSE" section |
| 31 | ✅ **COMPLETE incl. live canary re-run** — BUGS 28/29/30 closed; enum refusal observed against the real legacy candidate |
| 32 | ✅ **COMPLETE incl. RB-8 re-run** — LLM-free sweep trigger proven under real cron (silence AND loud-failure), zero credits |

**Milestone SEALED 2026-08-04.** All three remaining items done in the RB-9 close: the REVIEW-04
approve landed (human provenance stamped, machine source readable), the D-31 endpoint probe was
recorded as observed (endpoint withholds `manual_protected`; backstop path explicitly NOT proven),
REVIEW-02/04 flipped, STATE reconciled 10/10, MILESTONES.md carries the v0.6 entry. Closing gates
at seal: 1784 pytest / 550 node / armed-literal grep 0 / live disarmed PASS.

**Open todos (`.planning/todos/pending/`):** `sweep-lookback-has-no-time-window` (major — fixed
100-row lookback re-notifies a fixed failure until displaced, no acknowledgement; same todo carries
the id→name notice-naming gap). Plus two older known opens: Phase 26's thin-response reason field is
belief-not-observation; the versioned-cache config orphan on version bump.

## 2. The four big live findings of 2026-08-03 (evening) — never un-learn

1. **`claude -p` under cron cannot authenticate, and fails SILENTLY.** Expired token with empty
   `refresh_token` + `node` off cron's PATH. The interactive host probe (29-01) missed it because it
   inherited a live session's credentials — *verification one layer away from the claim*, same class
   as the stored-vs-running reload gap. Fix shipped in Phase 32: the sweep trigger is now
   `skills/backend-sweep/lv-sweep-run.sh`, deterministic sh, **no LLM anywhere in the unattended
   path** (`sweep_entry.py` under `env -i` with zero credentials emits identical JSON). A trigger
   that cannot run now exits non-zero AND banners. D-01 amended in `29-HOST-PROBE.md`.
2. **HubSpot enums vs provider free-text (BUG 28 family, all FIXED).** `industry` is an enumeration
   (148 options); providers speak NAICS-ish labels; the approve PATCH 400'd and the preview lied
   (`applied`). Phase 31: generated enum module (`hubspotEnums.generated.js` from the schema
   snapshot, `gen_hubspot_enums_js.py`), staging validate-and-refuse (exact case-insensitive
   label→value match ONLY — full mapping layer explicitly rejected), shared-path refusal in
   `reviewDecision.js` covering dry_run AND apply, explicit `not_allowlisted` body on gate drops
   (BUG 30). Proven live: armed approve of the legacy candidate → explicit `refused` naming
   value/property/closest-labels, zero n8n errors.
3. **The backend-status array-unwrap bug is DEAD** (was "KNOWN OPEN" for a whole session). The
   webhook answers `[{...}]`; the client now unwraps single-element lists, pinned both shapes
   (29-05). Queue counts and balances read real values through the plugin.
4. **Arming invariant AMENDED, not eroded.** Arming is operator-directed only, on a second explicit
   instruction after the agent names the invariant, bounded by a single-record `TEST_RECORD_*`
   allowlist, with a symmetric `--expect-armed` read-back. Unattended/scheduled/inferred/unbounded
   arming stays absolutely blocked. Precedent: RB-9 step 3. Disarm is never gated.

## 3. Standing operational facts (hard-won, still true)

- **Stored vs running:** every deploy (armed OR disarmed) needs a deactivate→activate bounce of
  active workflows; `verify_live_write_safety.py` reads STORED content. `n8n_control.apply_mutation`
  brackets correctly on its own.
- **Armed-window arithmetic:** dispatch ~38.6 s (B4 37.44 s), arm+disarm overhead ≈15.8 s. At chunk
  ceiling 2: ≈93 s vs the ~100 s webhook ceiling — tight, budget accordingly.
- **`ALLOW_*` gates:** literal `true` only, must PREFIX the command (each `!` line is its own shell;
  an export dies with its line; the refusal reads "it reads None").
- **Plugin install traps (RB-7 step 0 has the full write-up):** reinstall never refreshes the
  marketplace clone (fetch `--depth=1` + `reset --hard FETCH_HEAD` it yourself); a same-version
  reinstall DELETES `config/operator.local.json` (back it up; a good copy also lives gitignored at
  `operator-claude-plugin/config/operator.local.json` in the repo); `plugin.json`'s `0.1.0` is
  hand-written — **verify by content, never by version**. Cache-refresh shortcut that preserves
  config: `rsync -a --exclude='config/operator.local.json' <clone>/operator-claude-plugin/ <cache>/0.1.0/`.
  ⚠ Cache last synced at `ebae5ad`; commits after it are docs-only EXCEPT the plugin
  `CHANGELOG.md` gate note (`94d32d5`) — cosmetically stale in the cache, refresh before the next
  operator session.
- **Parallel executors share one working tree:** a bare `git commit` sweeps another process's staged
  files (happened: `dfd1178`). **Always commit explicit paths.** Disjoint file ownership per
  executor worked well twice.
- **RB-9 endpoint facts:** queue row id arrives as `hs_object_id`; a fail-closed allowlist drop now
  answers `not_allowlisted` (no longer conflated with a workflow error); read verdicts from
  `verify_decision`, never HTTP. Rejects bypass `ALLOW_REVIEW_SUBMIT` by design (undoing); rejects
  stamp NO reviewed_by/at (D-30 one-key) — part of why REVIEW-04 is open.
- **Sweep facts:** conditions honest on live data (Apollo `unreadable` ≠ out of credits; credential
  `unknown` ≠ broken — both observed silent). Healthy = exactly one stamped log line, nothing else.
  n8n executions API has NO workflow-name field — notices say "an unnamed workflow" until the
  lookback todo lands the id→name read.
- **Test-record registry:** company `9604614548` (Melbourne Racing Club) — resolved state, `industry`
  = `SPORTS`, review flags clear, reject reason retained as audit; the pipeline-produced legacy
  candidate is reproducible verbatim from `.planning/phases/22-armed-e2e-enrichment-canary/snapshots/`.
  Contact `342770428400` — RB-3's created canary; operator delete/mark still outstanding.
- **Tooling:** `.env` is agent-blocked (dotenv wrapper loads it inside python runs; hand the
  operator `!` lines for anything needing it directly). `--ws plugin-entrypoint` on every gsd-tools
  call. Hand-edit STATE.md, never `state.update-progress`. rtk wrapper breaks `npx`. GSD phase
  planning for NEW phases: register in ROADMAP (hand-edit both the list and a `### Phase N` detail
  block) → CONTEXT.md via PRD-express from a todo → planner (opus) → checker (sonnet) → executors
  (sonnet) — this flow ran cleanly twice (31, 32).

## 4. Why REVIEW-04 is genuinely undemonstrated (do not round up)

The requirement: every decision stamps human source + timestamp + reason. Observed: a **reject**
writes exactly one key (`lv_enrichment_review_reason`) and stamps neither `reviewed_by` nor
`reviewed_at`; the only **approve** ever attempted was first blocked by BUG 28, then (correctly)
refused by Phase 31's fix. So no decision on this system has ever written a human provenance entry.
The near-miss to avoid repeating: this was briefly marked Complete during the seal and caught only
by re-reading the requirement text against the canary logs. The seal is where overclaims become
permanent.

## 5. Safety invariants

- Committed artifacts disarmed (`grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → 0);
  closing gate `operator-claude-plugin/tests/test_control_disarmed_artifacts.py` (note the path —
  older docs say `tests/`).
- A window is not closed until the disarm read-back passes AND the bounce has run — stored and
  running both. Close order for review windows: deactivate `LV Review Decision` FIRST, then
  disarmed redeploy, then bounce actives, then read back.
- Arming per §2.4. Disarm paths never gated. The sweep is read-only by import-graph proof
  (`test_sweep_read_only.py`), and its trigger contains no credential that can expire.
- Tenant pin `N8N_EXPECTED_URL=https://alexherman.app.n8n.cloud`; portal 22617666.

## 6. Resume point

**v0.6 sealed 2026-08-04. Since then: Phase 33 (0.7.x), Phase 34 (0.9.0), Phase 35 (0.10.0) all
COMPLETE. UAT session 2 is 7/7 PASS.**

**NEXT: Phase 36, then Phase 37 — they are two halves of one capability and 37 depends on 36.**

Self-contained handovers, each assuming no prior context — read the one you are starting:
- `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-CONTEXT.md` (backend)
- `.planning/workstreams/plugin-entrypoint/phases/37-enrich-before-ingest/37-CONTEXT.md` (client)

**In one line:** a contact row with names + company but **no email dead-ends completely and
silently** — the ingest lane resolves identity by email only, so the row becomes `ambiguous` →
`review` → a bare Set node, leaving **no HubSpot record and no object id**, which means it cannot be
enriched later either. Measured live on 9 GCTC directors. The operator's decision: enrich-first
becomes the DEFAULT, a contact must be as complete as possible BEFORE ingest, and a row still
missing an email is held back rather than sent to evaporate.

**Phase 36 (backend)** adds an explicit `mode:"propose"` to `hubspot/enrichment/event` (returns the
merged properties, never enters the write path) plus a `lastname + company CONTAINS_TOKEN` match
lane. It also fixes two verified live bugs found while exploring: mixed-lane row duplication (both
adapters read `$('Build Identity').all()`), and the ingest lane manufacturing a batch-wide
`lookup_failed` from an emailless row, which demotes sibling rows' `create` to `review`.

**Phase 37 (client)** adds `preingest.py`, the ingest gate at `write_dispatch_csv` (raises — and it
fixes the existing extraction lane, which accepts emailless rows today), rows-chunking, the enriched
preview, and a new `enrich-before-ingest` skill. Two arming phrases stay, structurally uncollapsible.

Run `/gsd-plan-phase 36 --ws plugin-entrypoint` then `/gsd-execute-phase 36 --ws plugin-entrypoint`,
and only then the same pair for 37.

Current live state: plugin **0.10.0** on master, marketplace clone refreshed; backend deployed and
bounced with the widened alias table live; suites **1052 plugin / 1933 python / 553 node**; disarmed
gate 0; tenant disarmed (4 active, LV Review Decision inactive); tree clean and pushed.

Other open work, none absorbed into 36/37: the sweep's versioned crontab path (**major** — three
version bumps shipped in two days, each leaving it stale), the enrichment throughput levers
(measured, awaiting a decision), the sweep lookback window, UAT 1.1 needing a re-walk on 0.6.2's
changed behaviour, and two findings logged during Phase 35 — `web_fetch`'s summarising model does not
return stable casing (so "verbatim" is not reliably verbatim), and a login wall lands in the
nothing-usable branch so the URL ladder fires on it (harmless, capped, same-host).
