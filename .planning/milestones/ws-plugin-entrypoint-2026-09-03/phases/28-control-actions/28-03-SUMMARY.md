---
phase: 28-control-actions
plan: 03
subsystem: operator-claude-plugin
tags: [arming, write-safety, lifecycle, allowlist, verification, invariant]
requires:
  - n8n_read.read_write_safety (27-01)
  - n8n_control.apply_mutation (28-01)
  - 28-FINDINGS.md Q1 (the four-key PUT filter round-trips cleanly on this instance)
provides:
  - n8n_arming.set_write_safety (bidirectional)
  - n8n_arming.arm_for_dispatch
  - n8n_arming.disarm
  - n8n_arming.armed_window
  - n8n_arming.disarmed_targets
  - n8n_arming.ArmingRefused / DisarmFailed
  - ALLOW_N8N_ARM env gate
affects:
  - 28-05 (operator surface), 28-06 (armed canary)
tech-stack:
  added: []
  patterns:
    - bidirectional literal rewrite where the deploy script can only widen
    - fail-closed re-scan performed BY the shipped reader rather than a copied regex
    - field-level diff narrowing on top of node-level allowlisting
    - record-scoped grant derived from the dispatch batch
key-files:
  created:
    - operator-claude-plugin/scripts/n8n_arming.py
    - operator-claude-plugin/tests/test_control_flag_parity.py
    - operator-claude-plugin/tests/test_control_arming.py
    - operator-claude-plugin/tests/test_control_disarmed_artifacts.py
---

# 28-03 — the arm → dispatch → disarm lifecycle

**Status: COMPLETE.** Plugin suite 656 → 718. Repo 1529 → 1593. Node 506 unchanged. Every
committed artifact still disarmed.

## What was built

`set_write_safety(workflow, targets)` — the one genuinely new thing. `enable_baked_flags()`
searches for the DISABLED literal, so it can arm but can never put a workflow back; this
replaces a declaration whatever literal it currently carries, in either direction.

No reader was written. `n8n_read.read_write_safety` (27-01) is imported and called,
including for the fail-closed re-scan, because a duplicate reader cannot detect a desync it
is itself the cause of. A test asserts no private declaration-reader has crept back in.

`arm_for_dispatch` derives the allowlist from the batch being dispatched, so the grant is
record-scoped as well as operation-scoped: during the window the backend cannot write a
record that was not in the dispatch. An empty allowlist refuses — the deployed
`_writeSafetyAllows()` denies everything on one, so arming the flag alone would report a
successful arming that granted nothing, which reads as success and is therefore worse than
a refusal.

`ALLOW_N8N_ARM` gates arming with `ALLOW_N8N_PROBE`'s exact semantics (the literal string
`true`), checked before any transport exists so a missing gate costs zero HTTP. **The disarm
is deliberately ungated** — a kill switch that blocked disarming would strand an armed
backend, the precise failure this ceremony exists to prevent.

A failed disarm returns its own `disarm_failed` outcome naming the workflow and the observed
literals; `armed_window` runs the disarm on the exception path and surfaces BOTH failures
when the body raised and the disarm failed too, chained so neither is lost.

## Deviations — two plan facts were stale, both from Phase 30 landing after Phase 28 was planned

Exactly the drift §7b of the handoff predicts, and the reason checkers run immediately
before execution rather than at planning time.

1. **"The four overlayable constant names" — there are FIVE.** 30-01 (D-02/D-08e) added
   `ALLOW_HUBSPOT_REVIEW_WRITES` to `_OVERLAY_FLAG_SPEC`. Implementing four would have failed
   the plan's own parity pin, which compares against the live table. Implemented as five.
   **`ALLOW_HUBSPOT_REVIEW_WRITES` is deliberately NOT in `DISPATCH_FLAGS`** — review
   writeback is a separate authority, so arming the dispatch path must not grant it and
   disarming must not silently revoke it. Pinned by a test.
2. **"The three committed cloud workflows" — there are five**, four carrying declarations
   (30-02 added `wf_review_decision_cloud.json`). Every test globs rather than listing.

Counts are asserted where the plan names them (maintenance 4/4, contact ingest 2/3 — both
verified correct against the artifacts) and **derived** everywhere else, so a workflow
gaining or losing a gate fails in a test rather than during an armed window.

## For 28-05 and 28-06

- `armed_window` is the intended entry point; `arm_for_dispatch`/`disarm` are exposed for
  the canary, which needs to hold the window open across a manual step.
- `test_control_disarmed_artifacts.py` is 28-06's closing gate — re-run it after the live
  armed window.
- A failed arm returns `outcome: "failed"` with an `operator_note` saying DO NOT DISPATCH.
  28-05 should surface that sentence rather than composing its own.
