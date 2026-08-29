# Handover — remaining backlog

**Written:** 2026-08-29, at the end of a long session
**Repo state:** clean tree, `HEAD = ff300a8`, **10 commits unpushed**
**Plugin:** repo `0.28.3` · marketplace clone `0.28.0` · installed cache lags further behind

Read `.planning/HANDOFF-2026-08-29-ultrareview.md` first if you have no context on the project —
it carries purpose, the operator/admin constraint, and the architecture map. This file is only
*what is left*.

---

## What just happened, in three lines

Phase 59 shipped (18/18 after gap closure). The Phase 53 operator walk was run three times;
**GRANT-01 is now ticked** — a batch went ingest → enrich → HubSpot write under one grant, and
contact `348695309760` exists. Five composition defects were found and fixed, and a guard now
exists so a sixth cannot hide.

**The through-line for whoever picks this up:** every one of those five defects had every unit
correct and individually tested, and the documented sequence joining them tested nowhere. None
were found by the test suite. Assume that is still true of anything not explicitly listed as
covered below.

---

## P1 — Do these first

### 1. Push, then bring the operator's installed plugin up to date

10 commits are unpushed and the marketplace clone is at `0.28.0` while the repo is at `0.28.3`.
Everything below that involves the operator depends on this.

```
git push origin master
# then refresh the marketplace clone + reinstall so the operator's plugin is >= 0.28.3
```

Note: `origin/master` was moved once during this session by a push that did **not** originate
from the session doing the work. If that recurs, find out who.

### 2. The operator-chair walk — **ATTEMPTED 2026-08-30, FAILED, now BLOCKED on Phase 61**

**Walk run 4 halted before the grant was ever opened** (`53-WALK-RECORD-3.md`). Both prereqs
below were met — pushed, and the installed plugin updated to 0.28.6 — so **limitation 2 is
closed**. But given only a LinkedIn URL, the plugin demanded a company and the operator ended the
run. Steps 3–7 were never exercised, so **limitation 1 stands: the grant surface has still never
been driven from the operator's chair, and G-2 is still undisproven.**

The cause (FINDING D) is a front-end contract demanding a field the backend does not need —
`resolveIdentity.js:76-78` makes `linkedin_url` a strong match key and `lushaRequest.js:79-91`
accepts a Lusha v3 body with `linkedinUrl` alone. **Phase 61 owns the fix and is the immediate
next phase. Do not re-walk before it lands — the walk will halt in the same place.**

Original text follows.

### 2 (original). The operator-chair walk — GRANT-01's remaining half

GRANT-01 is ticked and the tick is honest, but **two limitations were recorded, not waived**:

- All three walks ran from **Claude Code with a terminal**, not the operator's chair. The
  composition is proven; the operator's own constraint set is not. **G-2 — the original client
  blocker, "the operator cannot do this unaided" — has still never been disproven by an actual
  operator.**
- All three ran the **repo**, not the installed plugin.

Item 1 above unblocks this. The walk script is `59-CONTEXT.md` § specifics; the two prior records
are `53-WALK-RECORD.md` and `53-WALK-RECORD-2.md`. Expect it to cost ~4 n8n executions, ~2
provider credits, ~$0.07, and one HubSpot write.

**This is the single highest-value open item.** It is the only thing that closes the loop the
whole v1.1 milestone exists for.

---

## P2 — The composition backlog the new guard made visible

`operator-claude-plugin/tests/test_skill_sequence_coverage.py` inventories every documented
`SKILL.md` call sequence and fails on a new one that no composition test claims. It **passes
today** because 5 sequences are grandfathered — that is a ratchet, not a clean bill of health.

`MAX_GRANDFATHERED = 5`. It can only shrink without a deliberate constant bump. Each entry names
the specific undriven join; full text is in the registry in that file.

| # | Skill | The join nothing drives | Priority |
|---|---|---|---|
| 1 | `contact-upload` | `authorize_* → armed_window → dispatch.dispatch` — the window is opened in tests but `dispatch.dispatch` is never driven inside it | **highest** |
| 4 | `enrich-before-ingest` | same chain, other skill | **highest** |
| 3 | `enrich-before-ingest` | `resolve_providers`/`authorize_*`/`armed_window` never feed `dispatch_plan → merge_enriched`. Its apparent neighbour asserts SKILL.md *wording*, not execution — correctly ruled not coverage | high |
| 7 | `enrich-records` | same shape as #3 | high |
| 2 | `enrich-before-ingest` | `chunk_ceiling(cfg, key='max_rows_per_match_request')`'s real return never flows into `plan_chunks` in a test that also drives `match_batch → classify_matches`; those always use a literal ceiling | medium |

**#1 and #4 are defect F2's exact shape** (`walk-write-path-defects` in the knowledge base), whose
one still-open dimension is recorded as a live operator walk. Closing them in tests and doing P1.2
attack the same risk from both ends.

---

## P3 — Deferred design work, each with a recorded reason

### `row_id` carried alongside rows, not inside them
Deferred during the bug_002 fix (operator ruling, 2026-08-29). `strip_row_id` fixed the instance;
the *class* is still live because a plugin-internal join key shares a dict with HubSpot
properties. Touches `build_rows_spec`, `merge_enriched`, `classify_matches`, `chunking`, and every
lane that joins by `row_id` — a hot path, wants its own plan. Reasoning is in
`extraction.strip_row_id`'s docstring so it cannot be re-litigated from scratch.

### A stub harness that RUNS each documented sequence
The guard shipped is an *inventory* test — it proves a sequence is claimed, not that it executes.
The stronger option (a per-lane stub harness that actually runs each skill's sequence) was
considered and deferred as the natural follow-up if the inventory test proves its worth. It would
have caught all five defects by execution rather than inspection.

### The other two guard shapes
A typed pipeline object making seam mismatches construction-time errors was rejected for this task
(wide refactor, only covers type-shaped seams). Recorded in
`.planning/HANDOFF-2026-08-29-ultrareview.md` § 8.

---

## P4 — Unstarted phases, in the sequence the operator set

- **Phase 55 — Async run: submit, poll, resume.** Owns the `max_records_per_chunk: 2` ceiling and
  the ~100s synchronous response window. A 40-record batch is currently 20 sequential chunks each
  holding a connection open — supervised, not unattended, and directly against the operator's
  stated priority. Still spike-first: n8n Cloud's execution model decides what is possible.
- **Phase 56 — The unattended pair pipeline.** One grant carries ingest → enrich → create →
  associate as one flow. Today ingest and enrich are separate dispatches.
- **Phase 57 — Ceilings, refusal-before-start, post-run proof.** D-53-02 is explicit that the
  grant's computed ceiling is *disclosure, not constraint* — the protective load falls entirely
  here.
- **Phase 60 — Review-lane authority.** The last lane still shaped like G-2: approving one flagged
  contact needs a plugin kill switch **plus** an admin-run arm-deploy. Three options recorded in
  the roadmap, none pre-decided. **Not an option:** deleting `ALLOW_REVIEW_SUBMIT` with no
  replacement.
- **Phase 52 — Staged canary (v1.0).** Deferred 2026-08-25, gated behind 59 and 55. On resume,
  re-derive Phase 51's population and credit sizing first (the dry-run artifacts drift with every
  enrichment run) and resolve the deferred FILL-04 third-disposition question.

---

## P5 — ALL CLOSED 2026-08-29

All three items are resolved, and **none of the three was a code defect**. Two were wrong
observations recorded as bugs; the third was debris kept for a reason that turned out to be
false. The value of working P5 was disproving it, not fixing it — worth remembering about how
this section was compiled.

Closed alongside it, from the same run: the two Phase 48 code-review WARNINGs (WR-01, WR-02),
which WERE real — plus the whole bare-`assert` defect class they belonged to. See
"Phase 48 warnings and the bare-assert class" below.

| Item | Detail |
|---|---|
| ~~Grant `expires_at: None`~~ | **CLOSED 2026-08-29 — not a defect** (debug session `grant-fields-return-none`). There is no wall-clock expiry field by design: GRANT-03 scopes a grant to a named batch, "not a duration", and a timestamp `expires_at` was **proposed and declined by the operator on 2026-08-25** (D-53-03, `operator-claude-plugin/scripts/write_grant.py:682-688`). "Expiring" in the design language means GRANT-04's five event-triggered closes, which ARE implemented and tested. `expires_at: None` was the result of reading a field that was never defined. Operator ruling 2026-08-29: accept as designed; the roadmap phrasing was clarified so it no longer reads as promising a timestamp. |
| ~~`close_grant` returns `close_reason: None`~~ | **CLOSED 2026-08-29 — not a defect, the observation named the wrong field** (debug session `grant-fields-return-none`). The real field is `closed_reason` (with the "d"): initialized at `write_grant.py:571`, set at `:592` after validating against the enforced vocabulary, and pinned green by a test parametrized over all five GRANT-04 reasons — including the exact `session_end` value the walk used. `close_reason` without the "d" appears **only** in planning prose and in no `.py` file anywhere in this repo's history. The walk record is left as written: it records what was observed at the time, wrong field name included. |
| ~~Legacy `written_records.json`~~ | **CLOSED 2026-08-29 — investigated and deleted as debris** (record: `.planning/debug/resolved/legacy-written-records-file.md`). The "only artifact demonstrating the glob" claim was **wrong**: `test_written_records.py:359` (`test_load_globs_and_finds_a_legacy_pre_change_filename_too`) pins the non-hyphen-anchored glob hermetically in `tmp_path`. Provenance: its `run_id` `2acd52f7…` appears in no walk record or planning doc (both sibling hyphenated files' run_ids DO appear in `53-WALK-RECORD-2.md`), all three entries were `outcome: "not_written"`, and it was saved mid-Phase-59 dev session — development debris, not operator data. It also carried an active cost: `load()` with no path unioned its three phantom entries into every operator-facing read. Content preserved verbatim in the resolution record, so the deletion is reversible. **The glob stays un-anchored** — a real operator may still hold a genuine pre-D-59-09 file. |

---

## Phase 48 warnings and the bare-`assert` class — CLOSED 2026-08-29

Both Phase 48 code-review WARNINGs were real, and fixing one of them exposed a defect class
much larger than either.

**WR-02** — `build_coverage_patch`'s D-07 "never write derived scoring fields" guard was a bare
`assert`. CPython strips `assert` ENTIRELY under `python -O` / `PYTHONOPTIMIZE=1`: the guard did
not weaken, it ceased to exist — and what it guards is a live PATCH to a portal with no
rollback. **WR-01** — `run_coverage_window`'s armed per-record loop special-cased only a client
`Timeout`, so any other exception discarded the whole run's partial audit trail, which is
precisely the record you need when an armed loop dies. Fixed in `ac64353`, one regression test
each, both proven red on the pre-fix code.

**The class.** A sweep of `scripts/` found ~35 bare asserts across 14 files. The largest group
was ~18 **credential-leak** guards (`assert "Authorization" not in text`,
`assert token not in text`, `assert "HUBSPOT_PRIVATE_APP_TOKEN" not in text`) copy-pasted
verbatim across 6 files — under `-O` a serialized artifact could carry the live bearer token,
arguably higher stakes than WR-02 itself. Operator ruling 2026-08-29: fix all safety-critical
classes via one shared helper.

`src/guards.py` now holds four unconditional `ValueError`-raising helpers
(`assert_disjoint`, `assert_keys_equal`, `assert_keys_subset`, `assert_no_secrets`). 14 sites
fixed across 10 scripts in `196b989` / `2f897fc` / `c205503`, each pinned by a
`PYTHONOPTIMIZE=1` subprocess test — the fix is pinned, not merely asserted. Deliberately left
as `assert`, with reasons recorded: `build_cloud_workflows.py` (dev-time config-name checks),
`sync_hubspot_properties.py:209,211` (post-write confirmation, not prevention),
`check_schema_drift.py:363`, `probe_org_type_migration.py:406`.

Full record incl. falsifiability evidence: `.planning/debug/resolved/bare-assert-guard-sweep.md`
and `.planning/debug/resolved/phase48-coverage-warnings.md`.

**Standing rule this establishes:** a safety guard — anything preventing a live write or a
secret leak — must never be a bare `assert`. Use `src/guards.py`.

---

## Standing rules — do not rediscover these

- **Test commands.** `.venv/bin/python -m pytest -q` (root, **3365** passed / 154 skipped —
  was 3328 before the 2026-08-29 session's +37 tests),
  `.venv/bin/python -m pytest operator-claude-plugin/tests -q` (**1725** / 5),
  `node --test tests/n8n/*.test.mjs` (**776** / 0, **glob form only** — the directory form is
  broken on node 24). Never bare `python -m pytest`; system python lacks the deps. Root collection
  includes the plugin tests, so its count moves when plugin tests are added.
- **A green suite is not evidence a documented flow works.** On this repo it never has been.
- **Worktrees break execution.** `workflow.use_worktrees: false` is set because `.venv` is at the
  repo root and gitignored. `dispatch-isolation` re-persists `harness-worktree` on a plain read —
  pass `--force-isolation none` immediately before each executor dispatch, with no intervening
  call.
- **`phase.complete` misfires** on root-`.planning/` phases with a workstream guard error. Seal by
  direct edit; do not pass `--ws`.
- **Release hygiene.** Any commit touching `operator-claude-plugin/` bumps
  `.claude-plugin/plugin.json` **and** adds a `CHANGELOG.md` entry in the **same** commit.
- **Never hand-edit `n8n/wf_enrichment_cloud.json`** (generated, 809KB). Phase 46 parity rule: a
  shared predicate lands in both `src/icp_scoring.py` and `scripts/build_cloud_workflows.py`, one
  commit.
- **Do not "simplify" these** — all operator-confirmed load-bearing, several look like removable
  ceremony: the n8n write-safety gate nodes; `plan_grant`'s empty-record-set refusal; the
  material-conflict judge gate; the non-clobber merge policy; the verbatim no-invention sentence
  in `extraction.md`; per-send armed-window narrowing (each window ⊆ the grant).
- **HubSpot has no rollback** and ~700 live company records are reachable. `348695309760` is a
  real contact created by walk run 3 — leave it.

---

## Where the evidence lives

| For | Read |
|---|---|
| Project purpose, operator constraint, architecture | `.planning/HANDOFF-2026-08-29-ultrareview.md` |
| The five-defect pattern, and what actually found each | `.planning/debug/knowledge-base.md`, last entry (`composition-boundary-blind-spot`) |
| How the system really behaves end to end | `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD.md` and `53-WALK-RECORD-2.md` (three walks; the only end-to-end exercises ever performed) |
| Phase 59 decisions D-59-01..D-59-10 | `.planning/phases/59-frictionless-write-path/59-CONTEXT.md` |
| What 18/18 does and does not mean | `.planning/phases/59-frictionless-write-path/59-VERIFICATION.md` |
| The guard and its census | `operator-claude-plugin/tests/test_skill_sequence_coverage.py`, `.planning/quick/260829-hjm-skill-sequence-composition-guard/` |
| Stale-vs-live spec | `CLAUDE.md` — read its "as-built delta" blocks (§4.0, §10.3.1, §13.0, §13.0.1, §29.1) **before** the tables they correct |

---

## Suggested first move after `/clear`

```
git push origin master          # P1.1 — unblocks everything operator-facing
```

then either `/gsd-quick` the marketplace refresh + operator-chair walk (**P1.2, highest value**),
or `/gsd-plan-phase 55` if you would rather close the throughput gap first. The five grandfathered
sequences (**P2**) are good `/gsd-quick` work in any order, and #1/#4 pair naturally with the
walk.
