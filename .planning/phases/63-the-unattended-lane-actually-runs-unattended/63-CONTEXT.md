# Phase 63: The unattended lane actually runs unattended - Context

**Gathered:** 2026-09-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the gap between "the unattended path exists" (Phase 61 shipped it) and "the unattended path
can be left alone with real volume." Two halves, from opposite ends of the same v1.1 goal:

- **63-A — reliability.** The sweep that is supposed to run without anyone watching can silently
  run old code, or silently stop, because its crontab pins a versioned plugin path.
- **63-B — cost per record.** A bulk run costs ~16s per record on a judge gate that does not
  discriminate among the records that reach it.

Neither is worth a phase alone; shipping either without the other still leaves bulk unattended
running unwise. Closes the two todos carrying `resolves_phase: 63`.

**Out of this phase:** disk hygiene on the operator machine, crontab rewriting, any change to
*what* the judge adjudicates, and the first live unattended credit-spending batch (still gated,
still not run).

</domain>

<decisions>
## Implementation Decisions

### 63-A — the sweep launcher

- **D-63-01:** Ship **both** a stable launcher shim and a staleness self-check. The shim installs
  under the durable home (`${CLAUDE_PLUGIN_DATA}` / `~/.claude/plugins/data/<id>/`), resolves the
  newest install at run time and `exec`s its `lv-sweep-run.sh`; the crontab pins the shim, which
  never moves. The self-check lives inside `lv-sweep-run.sh` and compares its own resolved root
  against the newest installed version. The shim fixes the defect going forward; the self-check is
  the **only** mechanism that reaches a crontab already pinned to an old directory, which is the
  actual state of this machine (twelve versioned directories, newest cached `0.33.0` against a
  shipped `0.35.0`). — **Reversibility:** costly — once an operator's crontab pins the shim path,
  changing that path means re-pointing every installed crontab by hand, which is the exact failure
  this phase exists to remove.

- **D-63-02:** On detecting staleness the sweep **runs anyway and notifies loudly** — completes the
  sweep with the old code, then emits the banner plus a log stamp naming both the running and the
  newest version. It does **not** refuse. Rationale: a stale sweep is still doing useful work, and
  refusing would convert a degraded-but-working unattended lane into a dead one — the worse failure
  for a milestone whose whole point is that the lane runs unattended. This is a deliberate
  departure from Phase 32's "a trigger that cannot run must be loud": stale is not cannot-run.

- **D-63-03:** **Do not touch the twelve stale install directories, and do not rewrite any
  crontab.** Signal only. Two reasons: `durable_paths._newest_sibling_holding()` migrates operator
  state (credentials, dashboard pointer) *out of* sibling installs and deletes the sibling copy only
  after a verified read-back — so a directory that looks like dead weight may hold the only copy of
  a credential that has not been migrated yet. And this phase's job is that the lane runs
  unattended, not disk hygiene. The directories stop accumulating once the shim lands.

- **D-63-04:** **Reuse `durable_paths.py`'s existing version ordering** (`_version_key`,
  `_newest_sibling_holding`). Do not write a second version-comparison implementation. That module
  already solved this ordering problem for operator state; the shim needs the same answer for code.

### 63-B — the judge

- **D-63-05:** **Lever 2 only — the cheaper model.** When `confidence_band` is the **only** reason
  in `reasons[]`, adjudicate with Haiku 4.5; any veto-shaped or conflict reason keeps Sonnet 5.
  Explicitly **out of scope: lever 1** (making the `85` upper bound exclusive, or narrowing the
  band). Lever 2 changes *who* adjudicates; lever 1 changes *what gets* adjudicated, and 58-06
  widened this gate deliberately after an unadjudicated conflict false-vetoed a real AU company
  (Series Futsal Victoria, execution `11983`). The authorization surface does not move in this
  phase. — **Reversibility:** reversible — the model is a single build-time constant.

- **D-63-06:** Adequacy is established by **offline replay of both models** over stored judge
  inputs from past executions, compared verdict by verdict on this exact record class. Anthropic
  calls only: **zero Lusha credits, zero HubSpot writes, zero n8n executions**, so it does not
  touch the balance a single bulk run already halves. **If the two models disagree materially on
  this class, the lever is dropped rather than shipped** — the phase is allowed to land 63-A alone.
  Rejected: shipping on a disagreement-trip guard, which would establish adequacy by assertion —
  the exact shape of mitigation-without-evidence that cost Phase 62 a full gap-closure plan (CR-01).

- **D-63-07:** The `reasons[]` distribution the todo asks for is **a by-product, not a separate
  task.** Routing on "`confidence_band` is the only reason" requires branching on `reasons[]`
  content, so the distribution becomes observable as a side effect of implementing D-63-05. Do not
  plan a standalone measurement spike.

### Deployment

- **D-63-08:** **Deploy disarmed, carrying Phase 62's changes too.** Phase 63's judge routing goes
  through `scripts/build_cloud_workflows.py`, which regenerates the whole workflow from current
  source — and the committed JSON is already ahead of the live n8n instance by Phase 62's
  `num_associated_contacts` and `sourceByField`. Deploy and bounce both phases' changes together,
  proven by a **disarmed** execution, matching Phase 61's disarmed-only close. Rationale: the
  throughput fix is worthless undeployed, the divergence must close eventually, and closing it while
  someone is watching beats discovering it during the first unattended batch. Rejected: deploying
  63's change alone, which would require a deliberately reverted build and mean deploying JSON that
  matches no commit. — **Reversibility:** costly — undoing means another deploy+bounce window, and
  the live instance is shared.

- **D-63-09:** **Nothing is armed by this phase.** No live write, no provider credit spent on a
  write path. The first live unattended credit-spending batch remains un-run.

### Claude's Discretion

- The shim's exact filename, location under the durable home, and installation mechanism.
- How the staleness comparison reads the "newest installed version" (reusing D-63-04's helpers).
- The offline replay harness's shape, corpus selection, and agreement-rate threshold — subject to
  D-63-06's rule that a material disagreement drops the lever.
- Whether `WEB_RESEARCH_MAX_SEARCHES` (lever 3) is worth confirming opportunistically while the
  deployed workflow is being read for D-63-08 — but it is **not** a deliverable (see Deferred).

### Folded Todos

Both todos carrying `resolves_phase: 63` are folded in full — they **are** this phase:

1. **`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`** (severity: major, area:
   operator-claude-plugin) — `SWEEP-CRON-TEMPLATE.md:56` hands the admin a crontab line built from
   `[plugin-root]`, so every plugin update orphans it. Re-verified 2026-09-02: all three sketched
   mitigations still absent; twelve versioned directories now on the machine. Addressed by
   D-63-01 … D-63-04.
2. **`2026-08-04-enrichment-throughput-ceiling.md`** (severity: major, area: n8n) — `Judge Call`
   costs 16.1s of a 34.2s wall clock (47%), and the escalation band `[75, 85]` is inclusive at both
   ends while `claude_web` returns 85 routinely, so `confidence_band` fires on essentially every
   record carrying a classification signal. Partially addressed by D-63-05 … D-63-07 (lever 2
   only); levers 1 and 3 deferred below.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The two todos this phase closes
- `.planning/todos/pending/2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` — the 63-A
  defect, its three candidate fixes, and the 2026-09-02 re-verification (twelve directories,
  `0.33.0` cached vs `0.35.0` shipped).
- `.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md` — the 63-B measurement
  (16.1s judge / 12.1s research / 34.2s wall), the confirmed inclusive band, and why levers 1–3
  rank as they do.

### 63-A — the sweep launcher
- `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh` — the wrapper; takes the plugin
  root as `$1` by design. Where D-63-02's self-check lands.
- `operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` §56 — the crontab line that
  pins `[plugin-root]`. Must change to pin the shim.
- `operator-claude-plugin/scripts/durable_paths.py` — `_version_key` (line 44),
  `_newest_sibling_holding` (line 84), `_migrate_once` (line 122), `durable_dir` (line 167). The
  version ordering D-63-04 mandates reusing, and the state-migration hazard behind D-63-03.

### 63-B — the judge
- `n8n/code/judge.js:145-150` — the `confidence_band` trigger, inclusive on both ends; and
  `applyUnadjudicated` below it, the D5 fail-safe that must keep working.
- `n8n/code/escalation.generated.js:9` — `ESCALATION_CONFIDENCE_BAND = [75, 85]`. **Generated —
  do not edit;** regenerate via `.venv/bin/python scripts/gen_escalation_js.py`.
- `config/escalation_policy.yaml` — the single source for the band and the material-conflict field
  groups.
- `scripts/build_cloud_workflows.py:1100` — `"ANTHROPIC_JUDGE_MODEL": "claude-sonnet-5"`, and
  `:2885-2896` where the flag is read. D-63-05's one-constant change point.
- `tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts` — RO-2. Must keep
  passing untouched.

### Project contracts
- `CLAUDE.md` §15.0 — the material-conflict suppression ruling from 58-06 and why the judge was
  widened; the tier table for ALWAYS-judge fields.
- `CLAUDE.md` §13.0.2 — request-level flags, and the 2026-09-02 amendment recording that the
  committed workflow JSON is ahead of the live instance (the fact D-63-08 acts on).
- `CLAUDE.md` §13.0.3 — n8n Cloud platform facts; note the `[documented]` vs `[observed live]`
  tags and that fan-out is a throughput win, not a cost win.
- `.planning/REQUIREMENTS.md` — Out of Scope: "Terminal instructions to the operator are a
  requirement failure." Rules out "document it" as a fix for 63-A.

### Project memory (verified operational facts)
- `sweep-trigger-llm-free` — `claude -p` cannot auth under cron and fails silently; the original
  host probe passed interactively and still failed under real cron. The reason D-63-05's proof
  standard demands a real scheduler tick.
- `n8n-stored-vs-running-content` — a bare PUT never reloads a running workflow; bounce after every
  deploy, and a stored read-back proves nothing about the running instance.
- `n8n-deploy-permission-blocked` — disarmed deploys, activation and API reads pass via the python
  driver; arming writes is the blocked line.
- `n8n-execution-budget` — Starter: 2,500/month, 5 concurrent, FIFO queue.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`durable_paths.py`'s version ordering** — `_version_key` sorts dotted-version directory names
  correctly (`0.10.0` above `0.9.0`) and `_newest_sibling_holding` excludes the current install by
  resolved-path equality, not version-string comparison. D-63-04 mandates reusing both; the shim
  needs exactly the answer this module already computes.
- **`durable_dir()`** — already resolves `${CLAUDE_PLUGIN_DATA}` with a computed fallback. The
  shim's install location follows it rather than inventing a path.
- **`lv-sweep-run.sh`'s banner/stamp helpers** — `banner()` (osascript notification) and `stamp()`
  (timestamped log append) already exist and are the right vehicle for D-63-02's loud notice.

### Established Patterns
- **The sweep path is deliberately LLM-free** — "No LLM in this path, no credential that can
  expire." The shim must preserve this; it is a `/bin/sh` concern, not a Python-with-Anthropic one.
- **Every non-healthy path is loud** — non-zero exit plus a banner. D-63-02 deliberately adds a
  *third* state (ran, but stale) that is loud without being non-zero.
- **`escalation.generated.js` is generated** from `config/escalation_policy.yaml` via
  `scripts/gen_escalation_js.py`. Even though D-63-05 does not change the band, anything touching
  escalation data goes through the YAML and the generator.
- **Never hand-edit `n8n/wf_*.json`** — regenerate with `scripts/build_cloud_workflows.py`.
- **Phase 46 parity rule** — a shared predicate lands in both engines in one commit. The judge
  model choice is n8n-side only (the Python oracle does not adjudicate), so no parity obligation
  applies here — state that explicitly rather than leaving it ambiguous.

### Integration Points
- The shim sits between cron and `lv-sweep-run.sh` — a new, thin `/bin/sh` layer with one job.
- The judge model routing sits inside the node built at `build_cloud_workflows.py:2885-2896`,
  branching on the `reasons[]` array already computed by `judge.js`'s `needsJudge` return.
- The deploy (D-63-08) touches the same five cloud workflows Phase 61 deployed and Phase 62
  regenerated without deploying.

</code_context>

<specifics>
## Specific Ideas

- The self-check's notice should name **both versions** — the one running and the newest installed
  — so the operator can see the size of the drift, not just that drift exists.
- The offline replay should compare **verdict by verdict on the confidence_band-only class
  specifically**, not aggregate agreement across all judge invocations; the whole claim is about
  that one class.
- 63-A's proof needs a **real cron tick with a simulated update**: install the shim, add a newer
  version directory, observe a genuine scheduled fire resolve to the new root. Under a temporarily
  shortened schedule, restored as part of the same task.

</specifics>

<deferred>
## Deferred Ideas

- **Judge lever 1 — narrowing the escalation band** (making `85` exclusive, or tightening
  `[75, 85]`). Deliberately excluded by D-63-05. It is an authorization trade, not a perf tweak:
  it decides that some records currently adjudicated will not be, and 58-06 widened this gate after
  exactly that gap produced a false veto. Needs its own phase with its own decision about what may
  go unadjudicated.
- **Judge lever 3 — capping research searches** (~4–6s). `WEB_RESEARCH_MAX_SEARCHES` is 5 but the
  effective `max_uses` in the deployed workflow is unconfirmed. Not a deliverable here; may be
  confirmed opportunistically while reading the deployed workflow for D-63-08, and recorded for a
  later phase.
- **Auto-repointing a stale crontab.** Rejected in D-63-01: it means the plugin edits the user's
  crontab — machine-level mutation no prior phase has attempted — and a bad rewrite kills the sweep
  entirely rather than leaving it merely stale.
- **Pruning the twelve stale install directories.** Rejected in D-63-03 on the un-migrated-credential
  hazard. If disk reclamation is ever wanted, it needs its own arming discipline and a
  provably-migrated precondition.
- **Re-examining fan-out cost.** Phase 61's own caveat (CLAUDE.md §13.0.3) is that the same 2-row
  batch listed 1 execution inline and 3 with `scale_up: true` — fan-out is a throughput win, not a
  cost win, and the billed-vs-listed question is unresolved. Out of scope here; noted because
  anyone quoting bulk economics will hit it.

</deferred>
