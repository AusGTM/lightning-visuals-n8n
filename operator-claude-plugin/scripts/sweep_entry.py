"""operator-claude-plugin/scripts/sweep_entry.py

The sweep's entrypoint — what an unattended cron fire of `claude -p` ultimately invokes
(29-03; host per 29-HOST-PROBE.md). Gather, evaluate, format, return.

THE ONE RULE THIS MODULE ENFORCES (D-15): silence means healthy, so the sweep must never
be silent merely because it FAILED TO RUN. With nobody watching, a raised exception
produces nothing — indistinguishable from a well backend. So:

- a config lacking the sweep capability's keys returns a notice naming the missing keys
  (never a value), attributed to an admin — it does not raise and does not return [];
- a gather in which EVERY read came back unavailable returns a "cannot see the backend"
  notice rather than silence;
- zero fired conditions over successful reads returns [] — genuine silence, the only
  kind there is (D-08, NOTICE-04). No heartbeat, no all-clear: this is deliberately NOT
  a fix for T-29-19 (a sweep that stops firing), which stays deferred to v0.7.

The `sweep` capability row exists so an admin can decline to enable unattended running
without disabling the operator's interactive status check. It requires all three keys —
n8n_url, n8n_api_key AND webhook_secret — because unlike `status`, which degrades to the
half it can read, a sweep that can only read half the conditions stays quiet about the
other half, and quiet is a claim.

29-05 Task 3: the two notices above (config missing, sweep blind) are constructed here
directly and never pass through `sweep_notify.render` — they stay one notice each,
regardless of how many conditions later fire, because D-15's "a sweep that cannot run
must say so" is a different claim from "several things are wrong" and must never be
folded into the same grouping logic. Everything that DOES reach `sweep_notify.render`
(zero, one, or several fired conditions) gets that module's silence/single/grouped
behaviour: zero is `[]`, genuine silence (D-08, NOTICE-04); one renders as its own
notice; several group into a single delivery rather than one banner per condition.
"""
import requests

import config_gate
import sweep_conditions
import sweep_notify
import sweep_read


def run_sweep(config, get_transport=requests.get, post_transport=None, now=None):
    """One sweep. Returns a list of notice dicts; [] is genuine silence."""
    try:
        config_gate.require_capability(config, "sweep")
    except config_gate.ConfigError as refusal:
        # The message names missing KEYS and where to fix them, never a value
        # (config_gate T-27-12). Turned into a notice because an exception here would
        # make a misconfigured sweep read as a healthy backend (D-15).
        return [{
            "condition": "sweep_not_configured",
            "headline": "LV backend sweep: not configured — it is NOT watching",
            "detail": (f"{refusal}\nUntil this is fixed the sweep runs but cannot "
                       f"check anything, so silence from it means nothing."),
            "who_can_fix": "admin",
            "execution_id": None,
        }]

    gathered = sweep_read.gather(config, get_transport=get_transport,
                                 post_transport=post_transport, now=now)

    if sweep_read.nothing_was_readable(gathered):
        return [{
            "condition": "sweep_blind",
            "headline": "LV backend sweep: cannot see the backend at all",
            "detail": ("Every read failed — n8n's executions API and the backend status "
                       "endpoint were both unreachable. The backend may be fine, but "
                       "this sweep cannot tell, and silence from it would have been a "
                       "lie. Your n8n admin should check connectivity and credentials."),
            "who_can_fix": "admin",
            "execution_id": None,
        }]

    return sweep_notify.render(sweep_conditions.evaluate(gathered))


def _cli_main(load_config=config_gate.load_config, get_transport=requests.get,
              post_transport=None, now=None):
    """What `python3 scripts/sweep_entry.py` prints (29-06 Task 1 — the skill this
    plan ships needs a runnable entrypoint, and none existed before this plan; the
    module had only ever been driven directly from tests). Isolated from `__main__`
    so a test can drive it with an injected config loader — no subprocess, no touching
    the real (gitignored) operator.local.json, no network risk, the same injection
    discipline every transport in this closure already uses.

    D-15's rule applies one layer above `run_sweep`'s own "sweep" capability check:
    the base config load (`config_gate.load_config`) can raise `ConfigError` before
    `run_sweep` ever gets a config dict to check at all (e.g. no `n8n_url` or
    `webhook_secret` configured whatsoever). That must be a notice too, never a raised
    traceback — with nobody watching, a traceback prints nothing to the log a cron
    wrapper redirects into, which is silence, and silence means healthy (D-08).
    """
    try:
        cfg = load_config()
    except config_gate.ConfigError as refusal:
        return [{
            "condition": "sweep_not_configured",
            "headline": "LV backend sweep: not configured — it is NOT watching",
            "detail": (f"{refusal}\nUntil this is fixed the sweep runs but cannot "
                       f"check anything, so silence from it means nothing."),
            "who_can_fix": "admin",
            "execution_id": None,
        }]
    return run_sweep(cfg, get_transport=get_transport, post_transport=post_transport,
                     now=now)


if __name__ == "__main__":
    import json

    print(json.dumps(_cli_main()))
