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

### 2. The operator-chair walk — GRANT-01's remaining half

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

## P5 — Small, verified, unfixed

| Item | Detail |
|---|---|
| Grant `expires_at: None` | The design language is "bounded, **expiring** and revocable". Bounded and revocable are demonstrated; expiring is not. Observed walk run 2. |
| `close_grant` returns `close_reason: None` | State correctly becomes `closed` and the reason vocabulary is enforced, but the returned field reads `None`. Cosmetic; possibly a differently-named field. Not chased. |
| Legacy `written_records.json` | Mtime 07:09 on 2026-08-29 suggests it may itself be test debris rather than a genuine pre-change operator file. Kept deliberately — it is the only artifact demonstrating why `load()`'s glob is not hyphen-anchored. Decide and either document or delete. |

---

## Standing rules — do not rediscover these

- **Test commands.** `.venv/bin/python -m pytest -q` (root, **3328** passed / 154 skipped),
  `.venv/bin/python -m pytest operator-claude-plugin/tests -q` (**1721** / 5),
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
