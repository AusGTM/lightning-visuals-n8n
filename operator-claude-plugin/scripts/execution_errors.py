"""operator-claude-plugin/scripts/execution_errors.py

Reads what actually failed inside one n8n execution — from its per-node output, not from
its run status.

Why that distinction is the whole point (D-04a, verified node-by-node against the
deployed JSON): every provider-facing node in the enrichment workflow is configured
`onError: continueRegularOutput`. A Lusha 401, an Apollo 403 or an exhausted ZoomInfo
quota therefore does not fail the execution — the executions API reports that run
`success`. Three of STATUS-02's four named causes live inside runs n8n calls healthy, so
run status alone is not a failure catalog, and a status surface that trusted it would
report a wedged backend as fine (T-27-17).

Pure over an already-fetched execution mapping — no transport, no network. The fetch is
`n8n_read.get_execution`, gated at the call site because the payload is large (T-27-18).

Defensive in the same shape as scripts/enrichment_cost_ledger.py's extractor: every level
type-checked, nothing raises, a node that never ran kept distinct from a node that ran and
produced nothing, and a present-but-wrong-type value failing closed as unreadable rather
than passing as an empty success.

Translation is `error_table.translate()` and nothing else. There is no second table here
and no way for a caller to supply its own attribution — D-05's guardrail is worth exactly
as much as the number of paths that can bypass it.
"""
import error_table


def _message_from(value):
    """The human-readable text out of whatever shape an error arrived in.

    27-RESEARCH.md A4: the documented shapes (`{message, stack?, context?}` /
    `{message, description?}`) were never observed against a real failed execution in
    this instance, so nothing here may depend on a particular key being present.
    """
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("message", "description", "reason", "error"):
            text = _message_from(value.get(key))
            if text:
                return text
    return None


def _output_items(run):
    """One NodeRun's output items (`data.main[0]`), or [] on any shape mismatch."""
    if not isinstance(run, dict):
        return []
    data = run.get("data")
    if not isinstance(data, dict):
        return []
    main = data.get("main")
    if not isinstance(main, list) or not main:
        return []
    branch = main[0]
    return branch if isinstance(branch, list) else []


def _collect(raw, node, level, into):
    """Translate one raw error and fold it into the collapsed findings.

    Collapse key is (node, cause) for a recognised signature and (node, raw) for an
    unrecognised one: a hundred rows rejected by the same node for the same reason is one
    problem with a count, and the operator reads one sentence instead of a hundred. Two
    different nodes hitting the same cause stay separate, because they are separate
    things to go and fix.
    """
    message = _message_from(raw)
    if not message:
        return
    translated = error_table.translate(message)
    key = (node, translated["cause"] or translated["raw"])
    existing = into.get(key)
    if existing is not None:
        existing["count"] += 1
        return
    into[key] = {"node": node, "level": level, "count": 1, **translated}


def harvest_errors(execution) -> dict:
    """Every distinct failure inside one execution payload.

    Returns ``{available, reason, findings}``. `available` False names why nothing could
    be read; `findings` is always a list. Each finding carries its node, which of the
    three places it came from, a count, and `error_table.translate()`'s full result.
    """
    execution = execution if isinstance(execution, dict) else {}

    data = execution.get("data")
    if not isinstance(data, dict):
        return {"available": False, "reason": "execution payload has no 'data' section "
                                              "(it was fetched without includeData)",
                "findings": []}
    result_data = data.get("resultData")
    if not isinstance(result_data, dict):
        return {"available": False, "reason": "no resultData in execution payload",
                "findings": []}
    run_data = result_data.get("runData")
    if not isinstance(run_data, dict):
        return {"available": False, "reason": "runData is not a mapping", "findings": []}

    # A node key present with a non-list value is a malformed or truncated payload, not a
    # legitimate "didn't run" — fail the whole harvest closed rather than report a partial
    # result that reads as a clean bill of health.
    for node, runs in run_data.items():
        if not isinstance(runs, list):
            return {"available": False,
                    "reason": f"runData[{node!r}] run items are not a list",
                    "findings": []}

    findings = {}
    _collect(result_data.get("error"), result_data.get("lastNodeExecuted"),
             "execution", findings)

    for node, runs in run_data.items():
        for run in runs:
            if not isinstance(run, dict):
                continue
            _collect(run.get("error"), node, "node", findings)
            for item in _output_items(run):
                if isinstance(item, dict):
                    _collect((item.get("json") or {}).get("error")
                             if isinstance(item.get("json"), dict) else item.get("error"),
                             node, "item", findings)

    return {"available": True, "reason": None, "findings": list(findings.values())}


if __name__ == "__main__":
    import json
    import sys

    import config_gate
    import n8n_read

    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: execution_errors.py <execution_id>"}))
        raise SystemExit(1)

    try:
        _cfg = config_gate.load_config()
        config_gate.require_capability(_cfg, "status")
    except config_gate.ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    _body = n8n_read.get_execution(_cfg, sys.argv[1])
    if _body is None:
        print(json.dumps({"ok": False, "error": "that execution could not be read"}))
        raise SystemExit(1)

    print(json.dumps({"ok": True, **harvest_errors(_body)}, indent=2))
