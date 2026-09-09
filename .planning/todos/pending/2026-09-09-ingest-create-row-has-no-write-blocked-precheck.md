---
created: 2026-09-09
updated: 2026-09-09
title: ingest lane's Decide Action has no write_blocked precheck for CREATE rows (update-only, by design, per F12)
area: n8n-workflows
severity: minor
files:
  - scripts/build_cloud_workflows.py
---

## Context (F12, uat-batch-review-row-reads-failed, 2026-09-09)

F12 fixed the ingest lane's "Decide Action" (`DECIDE_CLOUD`) to pre-compute an UPDATE
row's write-safety verdict itself, so a row the downstream `HubSpot Update Write Gate`
would refuse reports `action: "write_blocked"` (routed through `Set Review`'s edge into
`Build Ingest Response`) instead of a stale pre-block action nothing ever wrote — and,
more importantly, so a batch of ONLY refused update rows still has a path to
`Build Ingest Response` at all (a Code node filtering its input to zero never fires its
own outgoing connection, the same wave-dropping semantics as "IF Company Skip"'s true
lane — a 100%-refused, review-row-less batch previously dead-ended, the F1 shape
recurring for a different reason).

CREATE rows deliberately got no equivalent precheck. `HubSpot Create Write Gate`
derives its own allowlist domain from the row's OWN email (BUG 27, live-canary-proven
on runs 1122/1123/1126) when no `domain`/`identity_keys.domain` resolves — reproducing
that fallback inside Decide Action risked a precheck that disagrees with the real
gate's verdict for a scenario this session had no live evidence for, an unnecessary
regression risk to take on to close what execution 12181 actually showed (an UPDATE).

## What's still open

1. A create-only batch where every row is refused by `HubSpot Create Write Gate` (e.g.
   the allowlist doesn't cover any row's email domain) still dead-ends the same way
   updates used to: no review row, no path to `Build Ingest Response`, silence instead
   of a `write_blocked` report.
2. A create row the gate refuses still reports its pre-block `action: "create"` (never
   `write_blocked`) in the synchronous response, the same misreport F12 fixed for
   updates.

## Fix shape

Mirror F12's approach: give `DECIDE_CLOUD` its own copy of the CREATE gate's exact
domain-derivation fallback (`identity_keys.domain || row.domain || (email domain, if
`properties.email`/`row.email` parses one)`) and extend the `action === "update"`
precheck to `action === "update" || action === "create"`, computing the fallback domain
per-action the same way `_write_gate_js("create")` does. Test against BUG 27's own
scenario (`contactCreateGateFlow.test.mjs`'s `netNewRow()` + email override) as the
regression pin: a precheck that disagrees with the live-canary-proven gate behavior
must fail loudly, not silently ship.
