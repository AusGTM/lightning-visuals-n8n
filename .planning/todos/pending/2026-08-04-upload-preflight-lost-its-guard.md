---
created: 2026-08-04T06:20:00.000Z
title: Upload skill's step-1 preflight no longer refuses a secret-less config — it previews and invites arming
area: operator-claude-plugin
severity: minor
files:
  - operator-claude-plugin/scripts/config_gate.py:136
  - operator-claude-plugin/skills/contact-upload/SKILL.md:27
---

## Problem

Observed in the UAT 1.2 re-walk, 2026-08-04, on the fixed 0.6.1 build. Introduced by `f57b964`
(the `load_config()` over-refusal fix) — a loose end of that change, not a pre-existing bug.

`skills/contact-upload/SKILL.md` step 1 runs `python3 scripts/config_gate.py`, whose `__main__`
calls `load_config()` and prints `{"ok": true, "target": <contact-upload webhook URL>}`. That step
is the upload lane's preflight: under the old code `load_config()` raised for a blank
`webhook_secret`, the skill stopped, and the operator was told immediately. That is the behaviour
UAT 1.1 recorded as PASS.

Since `f57b964`, `load_config()` enforces only `n8n_url`, so the preflight returns `ok: true` and
the skill proceeds. Observed result with `webhook_secret` blank: a full 3-row preview rendered,
followed by *"To send, say **arm the upload**"* — an invitation to arm a send that
`dispatch.dispatch()` will then refuse. The operator reviews a preview and reaches for the arming
phrase before learning the lane cannot send.

`config_gate.py`'s `__main__` prints `describe_target(cfg)`, which is unambiguously the
contact-upload webhook — it is that capability's preflight and nothing else's. It was named in the
original fix todo ("config_gate.py `__main__` → contact-upload (it prints the upload target)") but
`require_capability()` was not added there.

Not a safety issue: `dispatch()` guards the transmit path correctly (added in the same commit and
verified), so nothing can be sent. The cost is a misleading flow, and the loss of UAT 1.1's
contract.

## Decision needed before fixing

Two defensible behaviours, and they differ in what an unconfigured operator may do:

1. **Restore the preflight refusal** — add `require_capability(cfg, "contact-upload")` to
   `config_gate.py`'s `__main__`. Returns exactly the pre-`f57b964` behaviour, keeps UAT 1.1's
   criterion true, and costs the ability to preview a file without a webhook secret (which nobody
   asked for and which did not exist before this week).
2. **Keep the preview, fix the invitation** — leave the preflight open so a secret-less operator
   can still see their file parsed, but have the skill state upfront that sending is unavailable
   and *not* offer the arming phrase. Preserves a genuinely useful read-only capability and
   matches the principle stated for the review lane (`review_decision.py:217`: "gating the preview
   would remove the display the arm exists to protect"). Costs a SKILL.md change and a test that
   the arming invitation is suppressed.

Option 2 is more consistent with how the review lane already reasons about previews; option 1 is
smaller and restores a recorded contract. **The operator should choose** — it changes what an
unconfigured install can do.

Whichever lands: pin it at the entrypoint layer (run the CLI / the skill's step-1 command against
a secret-less config), not by asserting on `load_config()` alone. That is the rule this whole
defect family exists to teach.
