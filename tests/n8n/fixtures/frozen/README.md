# Frozen workflow fixtures — the graphs the 2026-09-10 UAT actually ran

These are **byte-identical copies** of the committed cloud workflows as of 2026-09-10,
taken by `tests/n8n/walkerEngineFidelity.test.mjs` (Phase 70 plan 70-09, gaps G-70-2 and
G-70-3) so that the two live-execution reproductions keep meaning what they meant when
they were written.

| File | The executions it serves |
|---|---|
| `wf_contact_ingest_cloud.2026-09-10.json` | `12200` (Gate 1, disarmed), `12203` (Gate 70-05-A, the first armed mixed-verdict batch), `12207`/`12208` (Gate 3 ingest sends) |
| `wf_enrichment_cloud.2026-09-10.json` | `12204`/`12205` (Gate 3 `enrichment_2x2`), `12206` (Gate 3 `enrichment_single_lane`) |

The full runData account of each is in
`.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-UAT.md`.

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
