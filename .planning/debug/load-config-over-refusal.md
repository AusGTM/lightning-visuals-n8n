---
status: resolved
created: 2026-08-04
updated: 2026-08-04
resolved: 2026-08-04
trigger: "fix the load_config over-refusal now"
found_by: "Operator UAT session 1, steps 1.1/1.2, 2026-08-04, live on the installed 0.6.0 plugin"
severity: major
requirement: "PLUGIN-03 — a dead provider credential does not present as total failure"
todo: .planning/todos/pending/2026-08-04-load-config-over-refuses-status.md
---

# load_config() over-refuses: a blank webhook_secret takes down the whole status read

## Symptoms

**Expected behavior.** With `webhook_secret` blank but `n8n_url` and `n8n_api_key` set, asking
the backend-status question still answers: the workflow and execution half comes from the n8n API
key, and only the backend-supplied half (provider balances, HubSpot queue counts, credential
health) reports itself unavailable. This is stated in three places — `config_gate.CAPABILITY_KEYS`
(`"status": ("n8n_url", "n8n_api_key")`), `config_gate`'s own comment ("Losing that secret costs
only the backend-supplied half … the workflow and execution half still answers"), and
`skills/backend-status/SKILL.md` step 1 ("A missing `webhook_secret` does **not** stop it").

**Actual behavior.** The entire status read refuses. No workflow half, no execution half, nothing.

**Error message** (verbatim, from the operator's session and reproduced against the real CLI):

```
'webhook_secret' is not configured. Copy config/operator.local.example.json to
config/operator.local.json and fill it in once — the n8n_url and webhook_secret values come
from your n8n admin.
```

**Timeline.** Present since the status surface was built (Phase 27); never worked. Not a
regression — the operator-facing path was never walked with one key missing until UAT
2026-08-04. Both UAT 1.1 (upload refuses — correct) and 1.2 (status refuses — wrong) were run in
the same session; only 1.2 is the defect.

**Reproduction.** Deterministic, no live backend needed:

1. Blank `webhook_secret` in the plugin's `config/operator.local.json` (keep `n8n_url` and
   `n8n_api_key`).
2. Run `python3 scripts/status.py` from the plugin root.
3. Observe `{"ok": false, "error": "'webhook_secret' is not configured. …"}` instead of a report.

Confirmed twice: once by the orchestrator against a throwaway copy of the plugin
(`scratchpad/plugcopy`), once live in Claude Desktop by the operator.

## Suspected cause (starting hypothesis, not yet confirmed by the debugger)

`config_gate.load_config()` enforces the union of every capability's keys rather than the
universal minimum:

```python
if not cfg.get("webhook_secret"):
    raise ConfigError(f"'webhook_secret' is not configured. {_SETUP_HINT}")
```

Both status entrypoints open with it — `status.py:222` and `render_text.py:229` — so the
per-capability check (`require_capability(cfg, "status")`) is never reached. The capability
matrix the module is built around is therefore dead for any caller whose missing key is
`n8n_url` or `webhook_secret`.

**Corollary already observed (UAT 1.1):** `require_capability()`'s "Everything else still works:
…" clause is unreachable for the same reason — only a missing `n8n_api_key` can ever reach it. The
1.1 refusal was correct but never told the operator what still worked.

## Why the test suite did not catch it

`tests/test_status_unknown.py::test_a_missing_webhook_secret_still_reports_the_workflow_half`
pins the degradation correctly — but it calls `status.full_report(cfg)` with a hand-built dict and
never crosses `load_config()`. The function layer degrades; the CLI layer the operator reaches
refuses first. **Sixth instance of verification-one-layer-from-the-claim in this milestone**
(cf. stored-vs-running reload gap, the cron host probe). Any fix must be pinned at the entrypoint
layer, not only the function beneath it.

## Constraints the fix must respect

- **Do not remove a guard while loosening the gate.** `dispatch.dispatch()` and
  `enrichment.dispatch_enrichment()` have NO `require_capability()` call of their own — they rely
  entirely on `load_config()` refusing for `webhook_secret`. Loosening `load_config()` without
  adding explicit guards there would let a secret-less config reach a transmit path and
  `KeyError` on `config["webhook_secret"]`, or worse, send with an empty secret header.
  `review_queue.fetch_queue()`, `review_decision`, and `control_actions` already guard at the
  library layer — that is the pattern to copy.
- Committed n8n artifacts stay disarmed; this is a client-only change, no backend edit.
- Plugin suite baseline: 903 passed / 5 skipped. Root suite: 1784 pytest / 550 node.
- Milestone v0.6 is SEALED (2026-08-04). This fix lands after the seal and must not silently
  change any sealed requirement's evidence.

## Current Focus

reasoning_checkpoint:
  hypothesis: "`config_gate.load_config()` unconditionally raises for a blank `webhook_secret`
    (config_gate.py:89-90, pre-fix), before any caller-specific capability check runs. Every
    status entrypoint (status.py, render_text.py, render_dashboard.py) calls `load_config()`
    first in its `__main__` block, so the raise fires before `full_report()`/`status_report()`
    ever reach their own `require_capability(config, \"status\")` call — which does NOT list
    `webhook_secret` and would have degraded correctly. The over-refusal is a check placed at
    the wrong layer (global minimum vs. per-capability), not missing logic."
  confirming_evidence:
    - "Live repro against a throwaway copy of the plugin (scratchpad/plugcopy): blank
      webhook_secret, valid n8n_url/n8n_api_key -> `python3 status.py` returned
      `{\"ok\": false, \"error\": \"'webhook_secret' is not configured. ...\"}` pre-fix."
    - "Call-site inventory (Evidence log): status.py:222, render_text.py:229,
      render_dashboard.py:234 all call `config_gate.load_config()` directly in `__main__`,
      and status.py's own `full_report()`/`status_report()` already contain a correct
      `require_capability(config, \"status\")` call that is simply unreachable."
    - "CAPABILITY_KEYS[\"status\"] = (\"n8n_url\", \"n8n_api_key\") — webhook_secret was never
      part of the status capability's own contract, confirming the check in load_config() was
      an accidental universal gate, not a deliberate status requirement."
  falsification_test: "If `load_config()` did NOT enforce webhook_secret and the over-refusal
    still reproduced, the cause would be elsewhere (e.g. inside require_capability itself, or
    a second gate). Reverting only the load_config() check (git stash, keeping regression tests
    in place) reproduced all 6 expected failures and no others — confirming this was the sole
    blocking line."
  fix_rationale: "Move the `webhook_secret` check out of the universal `load_config()` and into
    `require_capability()` calls at each entrypoint/library function that actually needs the
    key — status/control never did, contact-upload/review/enrichment/sweep do. This is a
    relocation, not a loosening: every transmit path that used to be protected only by
    load_config()'s blanket raise now has its own explicit guard (see AND-gate below)."
  blind_spots: "Did not re-verify every one of the 14 load_config() call sites live against a
    real n8n backend — only status.py was reproduced end-to-end live; the rest were verified by
    reading + the full test suite. chunking.py/cost_guard.py/preview.py/preview_enrichment.py
    were confirmed by inspection to never touch webhook_secret directly (cost_guard's
    fetch_balances already degrades internally via backend_status.fetch_backend_status)."
  candidate_causes:
    - "code: a global validation check in config_gate.load_config() enforces a capability-
      specific key for every caller (the confirmed cause)."
    - "config: considered and ruled out — the operator's config file was not malformed;
      n8n_url and n8n_api_key were present and valid. The example config
      (operator.local.example.json) does not push operators toward this state either."
  and_gate: "No — this is a single-cause bug (one wrongly-scoped check in load_config()), not
    an AND of multiple conditions. But fixing it safely required a coupled second change: the
    constraint section already identified that dispatch.dispatch() and
    enrichment.dispatch_enrichment() have NO require_capability() of their own and rely
    entirely on load_config() raising. Loosening load_config() alone (without adding those two
    guards) would have traded one bug (over-refusal) for a worse one (KeyError on
    config[\"webhook_secret\"], or an empty-secret POST) — confirmed live via the revert test:
    without the added guards, dispatch()/dispatch_enrichment() raise KeyError, not ConfigError,
    when webhook_secret is missing."

hypothesis: (as above) — CONFIRMED.
test: reverted only the three source files (config_gate.py, dispatch.py, enrichment.py) via
  `git stash`, keeping the new regression tests in place; ran the plugin suite.
expecting: the 6 new/updated tests fail (bug returns) and only those 6; reapplying the stash
  restores 907 passed / 5 skipped.
next_action: none — fix applied, verified via the 5-signal fix-acceptance guardrail (all pass),
  awaiting human confirmation against the operator's real config before archiving.

## Evidence

- timestamp: 2026-08-04 — `status.py` run against a config with `webhook_secret: ""` returned
  `{"ok": false, "error": "'webhook_secret' is not configured. …"}`. Reproduced live in Claude
  Desktop by the operator in the same state.
- timestamp: 2026-08-04 — call-site inventory: `load_config()` is called by `artifact_store.py:151`
  (catches and continues), `chunking.py:276`, `config_gate.py:138`, `cost_guard.py:264`,
  `dispatch.py:65`, `enrichment.py:260`, `execution_errors.py:142` (already followed by
  `require_capability(_cfg, "status")`), `preview_enrichment.py:334`, `preview.py:212` (reads only
  `column_mapping_path`, swallows all exceptions), `probe_n8n_semantics.py:433` (already guards
  `control`), `render_dashboard.py:234`, `render_text.py:229`, `status.py:222`, `sweep_entry.py:93`.
- timestamp: 2026-08-04 — `CAPABILITY_KEYS` has no row for the enrichment lane; it posts with
  `webhook_secret` and would currently borrow `contact-upload`'s row, whose refusal text says
  "uploading contacts", which is wrong wording for an enrich request. Decide whether to add an
  `enrichment` row (matches D-29's stated principle) or reuse `contact-upload`.
- timestamp: 2026-08-04 — Decided: added a dedicated `enrichment` row to `CAPABILITY_KEYS`
  (`("n8n_url", "webhook_secret")`) rather than reusing `contact-upload`. `skills/enrich-records/
  SKILL.md` states enrichment "posts to a different path from the contact-upload lane"; D-29's
  own principle (separate capability per distinct backend action) applies directly.
- timestamp: 2026-08-04 — Live repro against `scratchpad/plugcopy` (throwaway plugin copy)
  confirmed the fix: blank `webhook_secret`, valid `n8n_url`/`n8n_api_key` -> `status.py` now
  returns `{"ok": true, "workflows": {...}, "backend": {"available": false, "reason":
  "webhook_secret_not_configured", ...}}` instead of the blanket refusal. `dispatch.py` and
  `enrichment.py` against the same config still refuse cleanly by name ("uploading contacts
  needs 'webhook_secret'…" / "enriching records needs 'webhook_secret'…"), each naming what
  still works (status, control).
- timestamp: 2026-08-04 — Fix-acceptance guardrail run (all 5 signals):
  target_test pass (907 passed / 5 skipped, +4 over the 903/5 baseline); mutation_check skipped
  (no Stryker/mutmut configured for this Python codebase); no_op_deletion pass (net +19/-6
  across config_gate.py/dispatch.py/enrichment.py — the one deletion, load_config()'s
  webhook_secret check, is relocated into 3 new require_capability() call sites, justified by
  the reasoning_checkpoint above, not a bare deletion); adjacent_tests pass (full python suite
  1788/6 skip [+4 over 1784/6 baseline], node suite 550/550 unchanged, disarmed-artifact
  gate still 0); revert_and_reconfirm pass (git stash of only the 3 source files, keeping the
  new tests in place, reproduced exactly 6 failures — the driving test plus 5 others tied to
  the same relocation, including proof that dispatch()/dispatch_enrichment() would raise a raw
  KeyError rather than ConfigError without the added guards; git stash pop restored 907/5
  clean).

## Eliminated

(none — the first and only hypothesis investigated was confirmed by evidence)

## Resolution

root_cause: `config_gate.load_config()` enforced `webhook_secret` as a universal, all-caller
  requirement (config_gate.py:89-90) instead of leaving it to each capability's own
  `require_capability()` check. Every status entrypoint calls `load_config()` before it ever
  reaches its own (already-correct) `require_capability(config, "status")` call, so the
  blanket raise fired first and made the per-capability degradation path in status.py
  unreachable for any config missing `webhook_secret`.

fix: (1) `load_config()` now enforces only `n8n_url` — the one key every capability in
  `CAPABILITY_KEYS` needs — and no longer touches `webhook_secret`. (2) Added a
  `config_gate.require_capability(config, "contact-upload")` guard as the first line of
  `dispatch.dispatch()`, and a `config_gate.require_capability(config, "enrichment")` guard as
  the first line of `enrichment.dispatch_enrichment()` (module-level `import config_gate`
  added to enrichment.py) — mirroring `review_queue.fetch_queue()`'s existing library-layer
  guard, so both transmit paths are still protected against a secret-less config even though
  `load_config()` no longer blocks them upstream. (3) Added a new `"enrichment"` row to
  `CAPABILITY_KEYS` / `_CAPABILITY_DESCRIPTIONS` (`("n8n_url", "webhook_secret")`, "enriching
  records") since none existed — it would otherwise have silently borrowed `contact-upload`'s
  wrong-wording refusal text. (4) `dispatch.py`'s `__main__` exception tuple now also catches
  `config_gate.ConfigError` around the `dispatch()` call, since that call can now raise it.

verification:
  target_test:        { result: pass }
  mutation_check:      { result: skipped, reason_if_skipped: "no Stryker/mutmut configured for this Python codebase" }
  no_op_deletion:      { result: pass, deletion_justified_by_rca: true }
  adjacent_tests:      { result: pass, suites_run: ["operator-claude-plugin/tests (907 passed, 5 skipped)", "full python suite (1788 passed, 6 skipped)", "node --test tests/n8n/*.test.mjs (550 pass)", "disarmed-artifact grep gate (0)"] }
  revert_and_reconfirm: { result: pass, bug_returned_on_revert: true, fixed_on_reapply: true }
  guardrail_verdict:   accepted

  oracle_type: derived  # regression tests assert against the documented capability contract
                         # (CAPABILITY_KEYS, config_gate's own comments, SKILL.md step 1), not
                         # against the symptom string alone

files_changed:
  - operator-claude-plugin/scripts/config_gate.py
  - operator-claude-plugin/scripts/dispatch.py
  - operator-claude-plugin/scripts/enrichment.py
  - operator-claude-plugin/tests/test_config_gate.py
  - operator-claude-plugin/tests/test_status_unknown.py
  - operator-claude-plugin/tests/test_dispatch_multipart.py
  - operator-claude-plugin/tests/test_enrichment_envelope.py

## Resolution (2026-08-04)

`load_config()` now enforces only `n8n_url` — the one key every capability needs. Capability-
specific keys are gated by `require_capability()` at the layer that needs them:
`dispatch.dispatch()` gained `"contact-upload"`, `enrichment.dispatch_enrichment()` gained a NEW
`"enrichment"` capability row (same keys as contact-upload, its own row so an enrich request is
refused with "enriching records" rather than "uploading contacts"). `review_queue`,
`review_decision`, `control_actions` and `run_sweep` already guarded themselves and were untouched.

**Independently re-verified by the orchestrator** against a throwaway copy of the REAL operator
config with `webhook_secret` blanked — not by trusting the agent's summary:

| Check | Result |
|---|---|
| `status.py` | `ok: true`, workflow/execution half answered, backend half `reason: webhook_secret_not_configured` |
| `dispatch.py` | clean named refusal, no `KeyError` |
| `enrichment.py` | clean refusal reading "enriching records needs 'webhook_secret'" |
| `sweep_entry.py` | still refuses, notice-shaped, names the key (guard was always its own — `sweep_entry.py:44`) |
| Suites | plugin 907/5 (was 903/5), full python 1788/6 (was 1784/6), node 550 unchanged |

**Bonus fix, unplanned:** `require_capability()`'s "Everything else still works: status, control"
clause is now REACHABLE — it never was, because `load_config()` raised first. That was the UAT 1.1
corollary recorded in this file; it is closed by the same change.

**Deployment note (the trap that nearly cost a false FAIL):** the fix lands in the repo, but the
operator runs the INSTALLED cache at
`~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/0.6.0/`. That copy was
stale at fix time — verifying in Claude Desktop before syncing it would have reproduced the OLD
behaviour and read as "the fix did not work". Same class as the stored-vs-running reload gap and
the stale marketplace clone. Cache synced from the repo (config preserved) as part of this close.
