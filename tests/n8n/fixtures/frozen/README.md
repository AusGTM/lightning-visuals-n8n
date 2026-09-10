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
| `exec_12354.runData.json`, `exec_12355.runData.json`, `exec_12356.runData.json` | `12354`/`12355` (Gate 11 `enrichment_2x2`, 2 chunks), `12356` (Gate 11 `enrichment_single_lane`) — FULL runData recordings of the enrichment lane's first runs under `executionOrder: "v1"`, 2026-09-10 ~13:55Z, disarmed |
| `exec_12357.runData.json`, `exec_12358.runData.json` | `12357` (Gate 11 `ingest_2x2`), `12358` (Gate 11 `ingest_single_lane`) — the same, for the contact-ingest lane |
| `wf_enrichment_cloud.v1.2026-09-10.json` | `12354`/`12355`/`12356` (quick task 260911-0tz, `walkerEngineFidelityV1.test.mjs`) — a byte copy of the COMMITTED `n8n/wf_enrichment_cloud.json` at commit `ec102a4` (287 nodes, `settings.executionOrder: "v1"`, verified identical to the committed file at freeze time via `git diff ec102a4 -- n8n/wf_enrichment_cloud.json`), added so these three v1 executions can be WALKED rather than only read as runData. Unlike the three legacy fixtures above, this copy IS v1 and so needs no `allowLegacy` — it is the opposite case from them, not a fourth member of their set. sha256 `77a4e8c0137580c1b1d827586a2d600d1fbf2942e883596caeb58f77318eab7d` — asserted by `walkerEngineFidelityV1.test.mjs`'s own MN-06 digest test (quick task 260911-1z5), so a future regeneration of `n8n/wf_enrichment_cloud.json` that silently diverges from this copy goes RED there rather than continuing to pass against a non-reproduction. |

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

## The v1 recordings (Gate 11, 2026-09-10) — `exec_1235{4..8}.runData.json`

These five are the OPPOSITE kind of recording from the three legacy fixtures above: each
carries `settings.executionOrder: "v1"` because that is what the live body ran on (Gate 10
deployed the committed v1 bundle earlier the same day; the Gate 11 driver read `v1` back on
all five workflows before sending). They are full runData, not excerpts — nothing owned them
at freeze time, so nothing was cut. `workflowData` is dropped: the graph that ran is the
committed `n8n/wf_enrichment_cloud.json` (287 nodes) / `n8n/wf_contact_ingest_cloud.json`
(69 nodes) at commit `ec102a4`, node names verified identical at freeze time, and each file's
`graph` header records the `workflowVersionId` n8n stamped on the execution. The committed
JSON regenerates; these do not. If a test ever needs to WALK one of these executions, add a
dated graph copy beside this file first (`wf_enrichment_cloud.v1.2026-09-10.json`) rather
than pointing at `n8n/`.

Reader: `tests/n8n/v1RuntimeRecordings.test.mjs` — assertions over the recorded runData only,
no walk. It pins the two NEW v1 observations these recordings established (both in CLAUDE.md
§13.0.3, `[observed live]`):

- **A Merge can fire twice under v1.** `Decide Company Action Merge` (append, 2 declared
  inputs, 6 producer edges) ran twice on 12354/12355/12356 — run 0 with 2 marker items (both
  inputs from `Companies Absent Sentinel Gate`), run 1 with 1 marker item (input 0 from
  `Recompute Not Requested Sentinel Gate`, input 1 `null` — the v1 end-of-run drain firing on
  a single arrived input). `Decide Company Action` therefore ran twice, 0 items each.
- **A node that RAN and emitted zero items is NOT a delivery under v1.** `Merge Company` ran
  with 0 items into that same Merge's input 1 and never appears in any run's `source`. This is
  the question `walkWorkflow.mjs` D-70-30 rule (c) left UNOBSERVED; it is now observed, and the
  walker's rule (c) model (legacy: zero-item output delivers) is known NOT to match v1. The
  walker is deliberately unchanged by the freeze — see
  `.planning/todos/pending/2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md`.

`allowLegacy` does not apply to these five: they are not walked, and they are v1.

## Redaction rule for every recording frozen from a live execution

The Webhook Trigger's runData item carries the caller's request headers verbatim — including
`x-enrichment-secret` (CLAUDE.md §18.1) and the caller's IP. Redact `x-enrichment-secret`,
`x-real-ip`, `x-forwarded-for` and `cf-connecting-ip` to `<redacted>` BEFORE committing, and
say so in the file's `redaction` header. `tests/n8n/v1RuntimeRecordings.test.mjs` refuses an
unredacted secret in the five v1 recordings; extend that check when a new recording is added.
