---
phase: 29-notices-unattended-sweep
plan: 03
subsystem: operator-claude-plugin
tags: [sweep, tracer, notices, read-only-guard, D-15, D-13, D-14]
requires:
  - n8n_read.recent_executions / summarize_execution / stuck_threshold_minutes (27-01)
  - backend_status.fetch_backend_status (27-02)
  - error_table.translate (27-04)
  - conftest executions fixtures (29-02)
  - 29-HOST-PROBE.md (29-01 — the amended host and the A5 delivery shape)
provides:
  - sweep_read.gather / nothing_was_readable
  - sweep_conditions.check_stuck / evaluate
  - sweep_notify.render
  - sweep_entry.run_sweep
  - config_gate capability row "sweep" (n8n_url + n8n_api_key + webhook_secret)
  - tests/test_sweep_tracer.py, tests/test_sweep_read_only.py
affects:
  - 29-04 (bounded watch), 29-05 (more conditions), 29-06 (skill + cron template + live gate)
tech-stack:
  added: []
  patterns:
    - exactly one I/O module; conditions and notices are pure functions over fetched data
    - allowlist import-graph guard with one named POST exception, proven to bite
    - a sweep that cannot run notices; only successful reads may be silent
key-files:
  created:
    - operator-claude-plugin/scripts/sweep_read.py
    - operator-claude-plugin/scripts/sweep_conditions.py
    - operator-claude-plugin/scripts/sweep_notify.py
    - operator-claude-plugin/scripts/sweep_entry.py
    - operator-claude-plugin/tests/test_sweep_tracer.py
    - operator-claude-plugin/tests/test_sweep_read_only.py
  modified:
    - operator-claude-plugin/scripts/config_gate.py (sweep row)
    - operator-claude-plugin/tests/test_status_unknown.py (capability set + loop)
---

# 29-03 — the tracer: a stuck run gets noticed, and the guard that keeps the sweep read-only

**Status: COMPLETE.** Plugin 795 → 811, repo 1670 → 1686, node 506 unchanged.

## Task 1 — the slice

Four flat modules; `sweep_read` is the only one that performs I/O, and it never names a
write verb — the one POST (`backend_status.fetch_backend_status`, D-13) happens inside
Phase 27's own function, whose default supplies the transport.

The stuck condition **consumes** Phase 27's tri-state verdict (`stuck` /
`stuck_threshold_minutes` off `summarize_execution`) — no second definition, no
`is_stuck()` (D-14). All three states travel end to end: True fires `stuck_execution`,
False is silent, and None fires its own `stuck_age_unreadable` notice — in flight with an
unreadable age is not fine.

D-15 is enforced at the entrypoint: a config missing a sweep key returns an
admin-attributed notice naming the missing **keys** (never values) instead of raising —
because with nobody watching, an escaped exception is indistinguishable from a healthy
backend. Same rule one layer down: a gather in which *every* read failed returns the
`sweep_blind` notice. A half-dead gather (executions readable, backend 404 — today's
actual live state) stays quiet about only the unreadable half, pinned by a test.

The `sweep` capability row requires all three keys, deliberately unlike `status`: a sweep
that can only read half the conditions stays quiet about the other half, and quiet is a
claim. The no-`webhook_secret` neighbour test kept its `{status, control}` assertion
untouched — the key list predicted that, which is the check the plan asked for.

Attribution goes through `error_table.translate` (imported, not mirrored); a stuck-run
cause is unmatched, so the admin guardrail applies by construction. Headlines are one
line for A5's banner budget; no notice instructs the operator to run anything.

## Task 2 — the guard, proven to bite

`test_sweep_read_only.py`: the transitive first-party closure of `sweep_entry` must equal
(not merely fit inside) the eight-module allowlist — subset catches new imports, equality
catches stale allowlist fat. Independently, the only write-verb site in the closure is
`("backend_status", "post")`, and the compensating AST assertion holds that POST bodyless:
`json=` the empty dict literal, no `files=`, no `data=` (mirroring
`test_retry_reuses_dispatch.py`'s convention — one decision, applied twice).

It bites, three ways, all against synthetic modules in `tmp_path`: an import outside the
allowlist, a `requests.put`, and the status POST mutated to carry a body. No production
file is edited to prove the guard works.

## Open Question 4 (29-RESEARCH.md) — n8n read-only scoped API keys

**Not available on this tenant's plan.** n8n's API-key scoping is an Enterprise feature;
Cloud-plan keys are full-access. Recorded so nobody later promises a defense-in-depth
story the platform does not support: **this client-side guard is the only layer.**

## For 29-05 / 29-06

- Add conditions by extending `sweep_conditions.evaluate` — pure functions over
  `gather`'s dict; the backend half's `available: False` must degrade, never fire.
- The 404 caveat stands (see 29-05's plan header): quota/credential/review conditions
  cannot be live-verified until `wf_backend_status_cloud.json` is deployed (disarmed).
- 29-06's skill/template names capabilities bounded by the same allowlist this guard
  declares — reference it, do not re-declare it.
