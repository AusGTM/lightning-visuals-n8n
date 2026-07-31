"""operator-claude-plugin/scripts/probe_n8n_semantics.py

A one-time, human-supervised diagnostic. It exists to turn three MEDIUM-LOW-confidence
assumptions into observed facts BEFORE the arming lifecycle (28-03) and the cadence
surface (28-04) are built on top of them — because the alternative is discovering one of
them wrong during an armed live window, which is the most expensive place there is.

    roundtrip <workflow-id>              D-20 / Open Question 3: does this instance
                                         round-trip `settings` and `connections` cleanly
                                         through GET -> PUT -> GET? The PUT is a genuine
                                         no-op by construction: the body sent is
                                         `put_body` applied to what the GET returned, with
                                         nothing mutated in between.

    execute_probe <workflow-id>          Research A2: does POST /workflows/{id}/execute
                                         exist on THIS Cloud account? Expect 404/405,
                                         which confirms the CONTROL-01 amendment (D-05a).
                                         A 2xx is a FINDING to record, not an error, and
                                         nothing in this phase acts on it.

    cadence_reload <workflow-id> <node>  D-18 / research A1: does the deactivate -> PUT ->
                                         activate bracket actually make a changed Schedule
                                         Trigger interval take effect on a RUNNING
                                         instance? Changes one node's interval, WAITS FOR
                                         THE OPERATOR (see below), reads the executions
                                         API once, then puts the captured interval back
                                         and reports that restore as its own verdict.

THE WAIT IS THE OPERATOR'S, NOT A POLL LOOP. `tests/test_report_sufficiency.py` forbids
every plugin script from importing `time`, calling `sleep()`, or containing a `while` —
Phase 26's D-07, which reserves the bounded watch for Phase 29 so it is built once. That
guard is right and this module satisfies it rather than being excused from it: the elapsed
window is supplied by the human who is already standing at this checkpoint (Task 3 is
`blocking-human`), and the observation afterwards is ONE read of the executions page, not
a poll — n8n retains execution history, so a single read at the end sees everything a loop
would have accumulated. Two things fall out, both good: there is no unattended process
holding a shortened schedule open, and the restore happens in the same process that made
the change, so it cannot be orphaned by a lost terminal.

WHAT THIS MODULE CANNOT DO. There is no code path here that writes a write-safety
constant — it does not so much as name one, so no later edit reaches for one by
autocomplete. Arming is 28-03's job, behind its own human gate. A diagnostic that could
arm by accident defeats the entire point of running the diagnostic first (T-28-07).

THREE GATES, ALL BEFORE ANY TRANSPORT IS CONSTRUCTED:

1. `ALLOW_N8N_PROBE` must read EXACTLY `true`. Not `1`, not `yes`, not `TRUE` — D-34 makes
   gating uniform across the repo's `ALLOW_*` switches, because two gates in one phase that
   disagree about what counts as "on" teach the operator a rule that is false half the time.
2. `config_gate.require_capability(cfg, "control")`. Credentials come from
   `config_gate.load_config()` and nowhere else. The plugin has never read `N8N_URL` from
   the shell — those are the backend deploy script's variables (D-29).
3. The wrong-instance check, applied to `config["n8n_url"]` — the value the request
   actually authenticates with. Shape borrowed from
   `scripts/deploy_n8n_workflows.py::_instance_ok()` (line 199 as of this writing; the
   plan's citation of line 163 was stale) and reimplemented rather than imported, because
   PLUGIN-04 forbids importing across the client/backend boundary. Reading the shell's
   N8N_URL variable here — a variable the plugin never authenticates with — would be a
   guard that cannot fire, which is worse than no guard because it reads like one
   (T-28-09). This module therefore contains no environment read but the two named above.

Everything mutating goes through 28-01's `n8n_control.apply_mutation`: same fetch-fresh,
same pre-flight structural refusal, same prior-active-restoring bracket, same
verdict-from-an-independent-read. If the probe needed a different pipeline to work, the
pipeline would be wrong — and finding that out is one of the things this plan is for.
"""
import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

import config_gate
import n8n_control
import n8n_read

PROBE_ENV_VAR = "ALLOW_N8N_PROBE"
EXPECTED_URL_ENV_VAR = "N8N_EXPECTED_URL"

# Verdicts. VERIFIED/FAILED are n8n_control's — one vocabulary for the whole phase.
REFUSED = "refused"
EXPECTED = "expected"        # execute_probe: the endpoint is absent, as D-05a assumed
FINDING = "finding"          # execute_probe: it is present, which overturns D-05a
INCONCLUSIVE = "inconclusive"

# The probe's own short interval, and the window the operator is asked to let elapse. Two
# minutes is short enough to observe several fires and long enough that n8n's scheduler is
# not being asked for anything unusual; ten minutes bounds the credit exposure of a
# schedule that is briefly firing more often than it should (T-28-08).
DEFAULT_PROBE_INTERVAL_MINUTES = 2
DEFAULT_WAIT_MINUTES = 10

# One bounded page of executions per poll, filtered to the one workflow.
_EXECUTION_PAGE_LIMIT = 20

_SUBCOMMANDS = ("roundtrip", "execute_probe", "cadence_reload")


def _gate(config: dict, probe_name: str):
    """The three gates, in the order that leaves the smallest trace when one fires.

    Returns a refusal dict, or None to proceed. Nothing here constructs a transport or
    reads a URL off the network, so a refusal leaves an EMPTY call log — not merely an
    empty MUTATING call log, which is the weaker invariant 28-01's `apply_mutation` is
    stuck with because it must fetch fresh before it can refuse (D-35).
    """
    if os.environ.get(PROBE_ENV_VAR) != "true":
        return _refusal(
            probe_name,
            f"refusing: this is a live diagnostic against production and {PROBE_ENV_VAR} "
            f"is not set to exactly 'true' (it reads "
            f"{os.environ.get(PROBE_ENV_VAR)!r}). Your n8n admin sets it, for one shell "
            f"only: {PROBE_ENV_VAR}=true. No API call was made.")

    try:
        config_gate.require_capability(config, "control")
    except config_gate.ConfigError as e:
        return _refusal(probe_name, f"refusing: {e}")

    url = str((config or {}).get("n8n_url") or "")
    expected = os.environ.get(EXPECTED_URL_ENV_VAR)
    if expected:
        if url != expected:
            return _refusal(
                probe_name,
                f"refusing: the configured n8n_url ({url}) is not the expected instance "
                f"({expected}). Both may be genuine n8n Cloud tenants, so only this pin "
                f"can tell them apart. No API call was made.")
    else:
        host = urlparse(url).netloc
        if not host or not host.endswith(".n8n.cloud"):
            return _refusal(
                probe_name,
                f"refusing: the configured n8n_url ({url}) is not an n8n Cloud host, and "
                f"{EXPECTED_URL_ENV_VAR} is not set to pin the expected one. This check "
                f"never fails open. No API call was made.")
    return None


def _refusal(probe_name: str, detail: str) -> dict:
    return {"probe": probe_name, "verdict": REFUSED, "detail": detail}


def interval_of(workflow, node_name):
    """One Schedule Trigger's `parameters.rule.interval`, or None.

    Narrow on purpose: this is `apply_mutation`'s `verify_fn`, and a whole-body comparison
    would fail on the fields n8n normalizes server-side and would then have to be
    loosened — which is how status-code optimism gets back in (28-01).
    """
    for node in (workflow or {}).get("nodes") or []:
        if isinstance(node, dict) and node.get("name") == node_name:
            return ((node.get("parameters") or {}).get("rule") or {}).get("interval")
    return None


def _shape_of(workflow) -> dict:
    """What `roundtrip` is actually asking about: the two keys Open Question 3 says an
    n8n Cloud PUT may quietly rewrite."""
    return {"settings": (workflow or {}).get("settings"),
            "connections": (workflow or {}).get("connections")}


def roundtrip(workflow_id, config, transport=requests) -> dict:
    """D-20: GET -> PUT the same body back -> GET, and report what survived.

    The mutation function is a no-op and the allowlist is empty, so the structural
    pre-flight diff passes trivially — which is itself the thing being proven. A PUT that
    cannot survive its own output is a PUT no real mutation should be built on.
    """
    refusal = _gate(config, "roundtrip")
    if refusal:
        return refusal

    result = n8n_control.apply_mutation(
        workflow_id, lambda _workflow: None, (), config,
        verify_fn=_shape_of, transport=transport,
        action=f"no-op round-trip of workflow {workflow_id}")

    requested = result.requested or {}
    observed = result.observed
    diff = ([key for key in ("settings", "connections")
             if requested.get(key) != (observed or {}).get(key)]
            if isinstance(observed, dict) else ["settings", "connections"])

    return {"probe": "roundtrip", "verdict": result.verdict, "detail": result.detail,
            "prior": result.prior, "observed": observed, "diff": diff,
            "action": result.action}


def execute_probe(workflow_id, config, transport=requests) -> dict:
    """Research A2: is `POST /api/v1/workflows/{id}/execute` there on THIS account?

    D-05a amended CONTROL-01 around an endpoint that exists only in an open, unmerged
    upstream PR. That is an inference about an upstream repository's state, not an
    observation about this tenant, and the two are not the same claim.
    """
    refusal = _gate(config, "execute_probe")
    if refusal:
        return refusal

    url = f"{n8n_read._base_url(config)}/api/v1/workflows/{workflow_id}/execute"
    try:
        response = transport.post(url, headers=n8n_read._headers(config),
                                  timeout=n8n_control.DEFAULT_TIMEOUT)
    except Exception:
        # The exception text can carry request headers; report the shape, not the text.
        return {"probe": "execute_probe", "verdict": INCONCLUSIVE, "status_code": None,
                "body": None, "detail": "the POST to n8n could not be completed"}

    status_code = getattr(response, "status_code", None)
    body = _readable_body(response)

    if status_code in (404, 405):
        verdict, detail = EXPECTED, (
            f"n8n answered {status_code}: the execute endpoint is absent on this account, "
            "which confirms D-05a's amendment (the operator re-times or enables/disables "
            "instead of firing an off-cycle run).")
    elif isinstance(status_code, int) and 200 <= status_code < 300:
        verdict, detail = FINDING, (
            f"n8n answered {status_code}: this account HAS the execute endpoint, which "
            "overturns D-05a's premise. Record it; nothing in this phase acts on it.")
    else:
        verdict, detail = INCONCLUSIVE, (
            f"n8n answered {status_code}, which is neither the expected absence (404/405) "
            "nor a success — the question is unanswered, not answered negatively.")

    return {"probe": "execute_probe", "verdict": verdict, "status_code": status_code,
            "body": body, "detail": detail}


def _readable_body(response, limit: int = 500):
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text[:limit]
    try:
        return json.dumps(response.json(), default=str)[:limit]
    except Exception:
        return None


def _executions_for(config, workflow_id, transport):
    """One bounded, workflow-filtered page. Reuses `n8n_read`'s GET — same header, same
    None-on-every-failure contract — rather than opening a second way to read n8n."""
    body = n8n_read._get_json(config, f"{n8n_read._base_url(config)}/api/v1/executions",
                              {"workflowId": workflow_id, "limit": _EXECUTION_PAGE_LIMIT},
                              transport.get)
    data = (body or {}).get("data")
    return data if isinstance(data, list) else []


def _observe_starts(config, workflow_id, transport):
    """Distinct execution start times, from ONE read of the filtered page.

    Not a poll: n8n retains execution history, so a single read taken after the operator's
    wait sees everything a loop would have accumulated, at one call instead of twenty.
    """
    seen = {}
    for execution in _executions_for(config, workflow_id, transport):
        if isinstance(execution, dict) and execution.get("id") is not None:
            seen.setdefault(execution["id"], execution.get("startedAt"))
    return [ts for ts in seen.values() if ts]


def _spacing_minutes(starts):
    """Minutes between consecutive execution starts, oldest first.

    The clock is read ONCE and reused for every timestamp. Reading it per-comparison is
    how a suite grows an intermittent sub-millisecond mismatch, and this repo has already
    paid for that lesson twice.
    """
    now = datetime.now(timezone.utc)
    ages = [age for age in (n8n_read.elapsed_minutes(ts, now=now) for ts in starts)
            if age is not None]
    ages.sort(reverse=True)  # oldest first
    return [round(ages[i] - ages[i + 1], 2) for i in range(len(ages) - 1)]


def cadence_reload(workflow_id, node_name, config, transport=requests, *, wait_fn,
                   probe_interval_minutes=DEFAULT_PROBE_INTERVAL_MINUTES,
                   wait_minutes=DEFAULT_WAIT_MINUTES) -> dict:
    """D-18 / research A1: does the bracket make a cadence change take effect LIVE?

    The phase has to perform a real cadence change to satisfy CONTROL-03 regardless. This
    does it early, once, under human supervision, where the answer is still cheap.

    It is deliberately NOT the cadence-as-one-shot-fire workaround D-05c rejected: nothing
    is being made to fire in place of a manual trigger, and this is never an
    operator-facing verb.

    `wait_fn(message)` is required and has no default — the same shape `apply_mutation`
    gives `verify_fn`, and for the same reason. The elapsed window is the operator's to
    provide (the CLI blocks on a prompt); a default would let some future caller acquire a
    blocking prompt, or an unattended poll loop, without asking for one.
    """
    refusal = _gate(config, "cadence_reload")
    if refusal:
        return refusal

    before = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    if not isinstance(before, dict):
        return {"probe": "cadence_reload", "verdict": n8n_control.FAILED,
                "detail": "the workflow could not be read, so nothing was attempted",
                "restore_verdict": None}

    if not before.get("active"):
        return _refusal(
            "cadence_reload",
            f"refusing: workflow {workflow_id} is not active. The question this probe "
            "answers is specifically whether an ALREADY-RUNNING instance retimes; "
            "activation is itself the load event by n8n's own model, so running this "
            "here would answer a different question and read as if it answered this one.")

    prior_interval = interval_of(before, node_name)
    if prior_interval is None:
        return _refusal(
            "cadence_reload",
            f"refusing: no Schedule Trigger named {node_name!r} with a "
            "`parameters.rule.interval` is in this workflow. Nothing was attempted.")
    prior_interval = copy.deepcopy(prior_interval)
    probe_interval = [{"field": "minutes", "minutesInterval": int(probe_interval_minutes)}]

    def _reader(workflow):
        return interval_of(workflow, node_name)

    changed = _apply_interval(workflow_id, node_name, probe_interval, config, transport,
                              _reader, f"re-time {node_name!r} to every "
                                       f"{probe_interval_minutes} minutes")
    if isinstance(changed, dict):       # a refusal from the allowlist diff
        return changed

    starts = []
    if changed.verified:
        wait_fn(f"{node_name!r} is now on a {probe_interval_minutes}-minute interval. Let "
                f"about {wait_minutes} minutes pass, then continue — the executions read "
                f"and the restore both happen when you do.")
        starts = _observe_starts(config, workflow_id, transport)

    restored = _apply_interval(workflow_id, node_name, prior_interval, config, transport,
                               _reader, f"restore {node_name!r} to its captured interval")
    if isinstance(restored, dict):
        restore_verdict, restore_detail = n8n_control.FAILED, restored["detail"]
    else:
        restore_verdict, restore_detail = restored.verdict, restored.detail

    detail = changed.detail
    if restore_verdict != n8n_control.VERIFIED:
        detail = (f"THE SCHEDULE IS STILL ON THE PROBE INTERVAL. Restore it by hand from "
                  f"the committed n8n/wf_scheduled_maintenance_cloud.json value for "
                  f"{node_name!r} — do not leave this; it burns provider credits silently."
                  f" ({restore_detail})")

    return {"probe": "cadence_reload",
            "verdict": changed.verdict if restore_verdict == n8n_control.VERIFIED
            else n8n_control.FAILED,
            "detail": detail,
            "change_verdict": changed.verdict,
            "restore_verdict": restore_verdict,
            "restore_detail": restore_detail,
            "prior_interval": prior_interval,
            "probe_interval_minutes": int(probe_interval_minutes),
            "observed_starts": starts,
            "spacing_minutes": _spacing_minutes(starts),
            "wait_minutes": wait_minutes}


def _apply_interval(workflow_id, node_name, interval, config, transport, reader, action):
    """One allowlisted interval change through 28-01's pipeline. Returns a
    `MutationResult`, or a refusal dict when the structural diff rejected it."""
    def _mutate(workflow):
        for node in workflow.get("nodes") or []:
            if isinstance(node, dict) and node.get("name") == node_name:
                node.setdefault("parameters", {}).setdefault("rule", {})["interval"] = \
                    copy.deepcopy(interval)
                return
        raise n8n_control.MutationRefused(
            f"refusing PUT: {node_name!r} vanished between the pre-read and the mutation")

    try:
        return n8n_control.apply_mutation(workflow_id, _mutate, (node_name,), config,
                                          verify_fn=reader, transport=transport,
                                          action=action)
    except n8n_control.MutationRefused as e:
        return _refusal("cadence_reload", str(e))


def _prompt_operator(message: str) -> None:
    """The CLI's wait: block on the human who is already standing at this checkpoint.

    Deliberately the only interactive call in the plugin. It exists so the process holding
    a shortened schedule open is one a person is looking at — and so that abandoning the
    wait means abandoning it in front of a printed restore instruction, not silently.
    """
    print(f"\n{message}\n")
    input("Press Enter to read the executions and restore the captured interval... ")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Disarmed n8n semantics probe (28-02). Requires ALLOW_N8N_PROBE=true.")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    for name in _SUBCOMMANDS:
        child = sub.add_parser(name)
        child.add_argument("workflow_id")
        if name == "cadence_reload":
            child.add_argument("node_name")
            child.add_argument("--probe-interval-minutes", type=int,
                               default=DEFAULT_PROBE_INTERVAL_MINUTES)
            child.add_argument("--wait-minutes", type=int, default=DEFAULT_WAIT_MINUTES)
    args = parser.parse_args(argv)

    try:
        config = config_gate.load_config()
    except config_gate.ConfigError as e:
        print(json.dumps(_refusal(args.subcommand, str(e)), indent=2))
        return 1

    if args.subcommand == "cadence_reload":
        result = cadence_reload(args.workflow_id, args.node_name, config,
                                wait_fn=_prompt_operator,
                                probe_interval_minutes=args.probe_interval_minutes,
                                wait_minutes=args.wait_minutes)
    else:
        result = globals()[args.subcommand](args.workflow_id, config)

    print(json.dumps(result, indent=2, default=str))
    return 0 if result["verdict"] in (n8n_control.VERIFIED, EXPECTED, FINDING) else 1


if __name__ == "__main__":
    sys.exit(main())
