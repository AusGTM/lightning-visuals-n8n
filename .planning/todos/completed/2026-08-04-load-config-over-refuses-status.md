---
created: 2026-08-04T04:40:00.000Z
title: load_config() enforces every capability's keys, so a blank webhook_secret takes down status
area: operator-claude-plugin
severity: major
files:
  - operator-claude-plugin/scripts/config_gate.py:84
  - operator-claude-plugin/scripts/status.py:222
  - operator-claude-plugin/scripts/render_text.py:229
---

## Problem

Found by UAT session 1 (steps 1.1/1.2), 2026-08-04, live on the 0.6.0 install — and reproduced
against the real CLI beforehand with a throwaway config copy.

`config_gate.load_config()` raises unconditionally when `webhook_secret` is blank or absent:

```python
if not cfg.get("webhook_secret"):
    raise ConfigError(f"'webhook_secret' is not configured. {_SETUP_HINT}")
```

But `CAPABILITY_KEYS["status"]` is `("n8n_url", "n8n_api_key")` — the status capability does not
need that secret, and `config_gate`'s own comment says so explicitly ("Losing that secret costs
only the backend-supplied half of the status answer … the workflow and execution half still
answers"). `skills/backend-status/SKILL.md` step 1 repeats the promise to the operator.

Both status entrypoints open with `load_config()` (`status.py:222`, `render_text.py:229`), so the
whole status read refuses before the capability check is ever consulted. Observed live: a blanked
`webhook_secret` produced

> `webhook_secret` is not configured. Copy config/operator.local.example.json …

for *"what's the backend doing?"* — no workflow half, no execution half, nothing.

**This is over-refusal, which PLUGIN-03 names a defect** ("a dead provider credential does not
present as total failure"). UAT step 1.2 is marked FAIL on this evidence.

**Why the suite did not catch it:** `test_status_unknown.py` pins the degradation correctly —
`test_a_missing_webhook_secret_still_reports_the_workflow_half` asserts
`report["backend"]["reason"] == "webhook_secret_not_configured"` — but it calls
`status.full_report(cfg)` with a hand-built dict, never crossing `load_config()`. The function
layer degrades; the CLI layer an operator actually reaches refuses first. Same shape as the
stored-vs-running reload gap and the cron host probe: **verification one layer away from the
claim.**

Secondary, same root cause: `require_capability()`'s "Everything else still works: …" clause is
unreachable whenever `n8n_url` or `webhook_secret` is the missing key, because `load_config()`
raises first. Only a missing `n8n_api_key` can ever reach it. Observed in step 1.1 — the refusal
was correct but never told the operator what still worked.

## Solution

TBD. The shape that fits the existing design: `load_config()` should validate only what every
caller needs (readable JSON, `n8n_url` present and https) and leave per-capability key checks to
`require_capability()`, which each entrypoint already has the information to call —
`status.py`/`render_text.py` would call `require_capability(cfg, "status")`, `dispatch.py`
`"contact-upload"`, and so on. That restores the capability matrix the module was built around
and makes the "what still works" clause reachable.

Watch for callers that rely on `load_config()` refusing early for `webhook_secret` — the
contact-upload and review lanes genuinely need it, so they must gain an explicit
`require_capability()` call in the same change or they lose their guard.

**Test the layer the operator hits**, not just the function beneath it: whatever lands needs a
test that drives the CLI entrypoint (or `main()`) against a config missing one key, per the
two-sided rule this milestone has been burned by six times now.
