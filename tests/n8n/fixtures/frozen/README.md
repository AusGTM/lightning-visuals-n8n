# Frozen workflow fixtures — the graphs the 2026-09-10 UAT actually ran

These are **byte-identical copies** of the committed cloud workflows as of 2026-09-10,
taken by `tests/n8n/walkerEngineFidelity.test.mjs` (Phase 70 plan 70-09, gaps G-70-2 and
G-70-3) so that the two live-execution reproductions keep meaning what they meant when
they were written.

| File | The executions it serves |
|---|---|
| `wf_contact_ingest_cloud.2026-09-10.json` | `12200` (Gate 1, disarmed), `12203` (Gate 70-05-A, the first armed mixed-verdict batch), `12207`/`12208` (Gate 3 ingest sends) |
| `wf_enrichment_cloud.2026-09-10.json` | `12204`/`12205` (Gate 3 `enrichment_2x2`), `12206` (Gate 3 `enrichment_single_lane`) |
| `wf_enrichment_cloud.gap-closure.2026-09-10.json` | `12316` (Phase 70 Plan 14, gap G-70-5, D-70-26(b)) — the 291-node gap-closure body, taken BEFORE plan 70-13 deleted the scale-up lane (which shrank it to 287), because 12316 is a child of the runaway self-dispatch loop and only the pre-70-13 body is the graph that execution actually ran |
| `exec_12316.runData.json` | `12316` — a runData excerpt for the eleven nodes `walkerEngineFidelity.test.mjs`'s D-70-26(b) case reasons about, each carrying the engine's recorded `source` beside the `declared_producers` read from the frozen connections |

The full runData account of each is in
`.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-UAT.md`.

## Why these can never be regenerated (D-70-28, gap-closure round 3, plan 70-16)

Every file above carries `settings: {}` — no `executionOrder` — because that is exactly
what the live n8n body ran on when each execution happened: `settings.executionOrder` was
ABSENT on every live body throughout Phase 70 until D-70-28's flip to `"v1"`. These are
RECORDINGS of the LEGACY engine, frozen at the moment they were observed. D-70-28 rules
that every workflow `scripts/build_cloud_workflows.py` generates from here on runs on
`"v1"` — so regenerating one of these fixtures from the current builder would no longer
produce the settings-`{}` body the named execution actually ran on; it would silently stop
being a recording and start being a fabrication. That is the reason "Refresh policy: none"
below is not merely a convention but a consequence of D-70-28: there is no builder output
these fixtures could ever be refreshed FROM again.

The walker (`tests/n8n/lib/walkWorkflow.mjs`) reflects the same fact structurally, not just
in prose (D-70-30): it refuses to walk any graph whose settings are not `"v1"` unless the
caller passes the documented `allowLegacy` escape, and `tests/n8n/walkerEngineFidelity
.test.mjs` — the suite that loads these fixtures — is the ONLY caller in this repo that
passes it, precisely because these three fixtures are the only graphs left that legitimately
need it.

## The rule

**These files are never regenerated and never hand-edited.** Wave 2 of phase 70 changes
the live graph under `n8n/`; if these reproductions pointed at `n8n/` they would silently
stop being reproductions of the runs they name — a test that "passes" against a graph the
engine never executed proves nothing about the engine.

An armed case mutates an **in-memory** copy of one of these files (the same jsCode literal
rewrite `n8n_arming.set_write_safety` performs, as `tests/n8n/writeGateShape.test.mjs`
already does). Nothing here is ever written back to disk, and nothing here is deployable.

Refresh policy: none. If a later phase needs a frozen graph for a *different* execution,
it adds a new dated file beside these and names the executions it serves.
