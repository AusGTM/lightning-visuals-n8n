"""operator-claude-plugin/scripts/n8n_arming.py

The write half of the write-safety overlay (28-03): the bidirectional setter the
arm -> dispatch -> disarm lifecycle is built on.

WHY THIS EXISTS AT ALL. `scripts/deploy_n8n_workflows.py::enable_baked_flags()` can only
widen disabled -> enabled: its exact-literal replace searches for the DISABLED
declaration, so once a workflow is armed that function can no longer find anything to
rewrite and cannot put it back. Disarming therefore needs a setter that replaces a
declaration regardless of the literal it currently carries. That is the one genuinely new
thing here.

WHAT THIS MODULE DOES NOT CONTAIN: a reader. `n8n_read.read_write_safety(workflow, name)`
shipped in 27-01 and already scans every node, returns the parsed literal plus the
declaring node names, and reports disagreement when declaring nodes desync. It is
imported and called. A second reader would sit under the same flat name on conftest's
`sys.path`, and a duplicate cannot detect a desync it is itself the cause of.

The fail-closed re-scan is therefore performed BY THE SHIPPED READER rather than by a
copied regex. `n8n_read`'s pattern (`const\\s+NAME\\s*=\\s*([^;]+);`) is character-for-
character `enable_baked_flags()`'s own re-scan pattern, and is deliberately LOOSER than
the exact-literal replace above it — that asymmetry is what catches a spacing or literal
drift the replace could not reach, and it is preserved here by reuse.

PLUGIN-04: no import crosses the client/backend boundary. `_OVERLAY_FLAG_SPEC`'s contents
are copied below verbatim rather than imported, and parity is held by
`tests/test_control_flag_parity.py` reading the deploy script as TEXT. `n8n_read` is a
plugin sibling, so importing it is not a boundary crossing.
"""
import json
import re

import n8n_control
import n8n_read

# Copied verbatim from scripts/deploy_n8n_workflows.py::_OVERLAY_FLAG_SPEC (lines
# 176-189) — {name: disabled_literal}. Parity is pinned by test_control_flag_parity.py,
# which reads that table as text; this is never imported (PLUGIN-04).
#
# FIVE names, not four. 28-03-PLAN.md says "the four overlayable constant names"
# throughout — that was accurate when the plan was written and is not now:
# ALLOW_HUBSPOT_REVIEW_WRITES was added to the deploy table by 30-01 (D-02/D-08e) after
# Phase 28 was planned. Implementing four would fail this module's own parity pin, which
# compares against the live table. Review-write authority is SEPARATE from the dispatch
# pair: arming it grants nothing on the dispatch path and vice versa.
OVERLAY_DISABLED_LITERALS = {
    "ALLOW_HUBSPOT_RECORD_WRITES": '"false"',
    "ALLOW_HUBSPOT_CREATE": '"false"',
    "ALLOW_HUBSPOT_REVIEW_WRITES": '"false"',
    "TEST_RECORD_IDS": '""',
    "TEST_RECORD_DOMAINS": '""',
}
OVERLAYABLE_FLAGS = frozenset(OVERLAY_DISABLED_LITERALS)
WRITE_ENABLING_FLAGS = frozenset({
    "ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE", "ALLOW_HUBSPOT_REVIEW_WRITES",
})
ALLOWLIST_FLAGS = frozenset({"TEST_RECORD_IDS", "TEST_RECORD_DOMAINS"})

# Letters, digits, dot, dash, underscore; comma-separated.
#
# The CHARACTER CLASS matches the deploy script's `_ALLOWLIST_VALUE_RE` and is pinned
# against it. The SEPARATOR deliberately differs: the deploy script permits `|` and
# converts it to a comma later, purely because `,` already separates entries inside the
# `ENABLE_BAKED_FLAGS` environment-variable envelope. The plugin has no such envelope, so
# comma-direct is correct plugin-side.
#
# The charset is ENFORCED, not merely escaped, because the fail-closed re-scan's
# declaration regex terminates at the first `;` — a value carrying a semicolon would split
# a declaration the re-scan could then not verify, which is a silent hole rather than a
# loud one.
_ALLOWLIST_VALUE_RE = re.compile(r"[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+)*")


class ArmingRefused(Exception):
    """A rewrite was refused before anything was changed, or the fail-closed re-scan
    caught a partial rewrite afterwards. Never downgraded to a return value: a caller
    that mistakes a failed arm for a successful one is the failure this module exists to
    make impossible."""


def _render_literal(flag: str, value) -> str:
    """The JS literal for a target value. Allowlist values go through `json.dumps`, so
    they always land as a quoted JS string and can never inject JS."""
    if flag in ALLOWLIST_FLAGS:
        text = "" if value is None else str(value)
        if text and not _ALLOWLIST_VALUE_RE.fullmatch(text):
            raise ArmingRefused(
                f"refusing to write {flag}: value {text!r} is outside the permitted "
                f"charset (letters, digits, dot, dash, underscore; comma-separated). "
                f"A semicolon in particular would split the declaration that the "
                f"fail-closed re-scan then could not verify."
            )
        return json.dumps(text)

    if isinstance(value, bool):
        return json.dumps(json.dumps(value))    # True -> '"true"'
    return json.dumps(str(value))


def set_write_safety(workflow, targets):
    """Rewrite every declaration of each named constant, in EITHER direction.

    `targets` maps constant name -> desired value: a bool or "true"/"false" for the
    write-enabling flags, a comma-separated string (or "") for the allowlist flags.

    Returns `(new_workflow, {flag: rewrite_count})`. The input is never mutated.

    Raises `ArmingRefused` for a name outside the overlayable set, for an allowlist value
    outside the charset, and — the point of the function — when any surviving declaration
    of a requested constant does not read the target literal afterwards.
    """
    unknown = sorted(set(targets) - OVERLAYABLE_FLAGS)
    if unknown:
        raise ArmingRefused(
            f"cannot set {unknown}: not in the overlayable set "
            f"{sorted(OVERLAYABLE_FLAGS)}. Cost caps, model names and every other "
            f"constant are never overlayable."
        )

    # Render every literal BEFORE touching the workflow, so a rejected value refuses with
    # nothing half-rewritten.
    literals = {flag: _render_literal(flag, value) for flag, value in targets.items()}

    wf = json.loads(json.dumps(workflow))       # deep copy, stdlib only
    counts = {flag: 0 for flag in literals}

    for node in wf.get("nodes", []):
        if not isinstance(node, dict):
            continue
        js_code = (node.get("parameters") or {}).get("jsCode")
        if not isinstance(js_code, str):
            continue
        for flag, literal in literals.items():
            # Bidirectional: match the declaration whatever literal it currently holds,
            # which is exactly what enable_baked_flags()'s exact-literal replace cannot do.
            decl_re = re.compile(rf"const\s+{re.escape(flag)}\s*=\s*[^;]+;")
            js_code, n = decl_re.subn(f"const {flag} = {literal};", js_code)
            counts[flag] += n
        node["parameters"]["jsCode"] = js_code

    # Fail-closed re-scan, performed by the SHIPPED reader. A `disagreement` return is a
    # partial rewrite — caught here, before anything is dispatched.
    for flag, literal in literals.items():
        if not counts[flag]:
            continue                            # nothing declared here; not this module's error
        observed = n8n_read.read_write_safety(wf, flag)
        expected = literal.strip('"')
        if observed.get("disagreement") is not None:
            raise ArmingRefused(
                f"refusing the rewrite of {flag}: declaring nodes disagree after it, which "
                f"means the rewrite was partial. Nodes: {observed.get('nodes')}"
            )
        if observed.get("value") != expected:
            raise ArmingRefused(
                f"refusing the rewrite of {flag}: after rewriting {counts[flag]} "
                f"declaration(s) the workflow reads {observed.get('value')!r}, not "
                f"{expected!r}. A workflow that deploys in the wrong state while reporting "
                f"success is the false-success this check exists to prevent."
            )

    return wf, counts


def disarmed_targets(*flags):
    """The disabled literal for each named flag — the disarm payload, derived from the
    spec rather than written out again at each call site."""
    unknown = sorted(set(flags) - OVERLAYABLE_FLAGS)
    if unknown:
        raise ArmingRefused(f"cannot disarm {unknown}: not in the overlayable set "
                            f"{sorted(OVERLAYABLE_FLAGS)}")
    return {flag: OVERLAY_DISABLED_LITERALS[flag].strip('"') for flag in flags}


# ---------------------------------------------------------------------------------------
# 28-03 Task 2 — the arm -> dispatch -> disarm lifecycle
# ---------------------------------------------------------------------------------------

ARM_ENV_VAR = "ALLOW_N8N_ARM"

# The DISPATCH lifecycle's four constants. ALLOW_HUBSPOT_REVIEW_WRITES is deliberately NOT
# here: 30-01's D-02/D-08e makes review writeback a SEPARATE authority, so arming the
# dispatch path must not grant it and disarming the dispatch path must not silently revoke
# it. Five names are overlayable; exactly these four belong to a dispatch.
DISPATCH_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE",
                  "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")

ARMED = "armed"
DISARMED = "disarmed"
DISARM_FAILED = "disarm_failed"
REFUSED = "refused"


class DisarmFailed(Exception):
    """The disarm's read-back did not show the disabled literals. Live writes may still be
    enabled on a real workflow. This is its own exception type precisely so no caller can
    fold it into a generic failure and move past it (D-03)."""

    def __init__(self, outcome: dict):
        super().__init__(outcome.get("detail", "disarm failed"))
        self.outcome = outcome


def _arm_gate():
    """The env kill switch, checked BEFORE any transport is constructed, so a missing gate
    costs zero HTTP calls.

    Semantics are character-identical to `ALLOW_N8N_PROBE` (28-02) and `ALLOW_N8N_DEPLOY`:
    the value must read EXACTLY 'true'. This module is the only one in the milestone that
    writes an *enabled* write-safety literal to a live workflow, so shipping it behind a
    weaker gate than the read-only probe would invert the repo's convention (D-34).
    """
    import os
    value = os.environ.get(ARM_ENV_VAR)
    if value != "true":
        return {
            "outcome": REFUSED,
            "detail": (f"refusing to arm live writes: {ARM_ENV_VAR} is not set to exactly "
                       f"'true' (it reads {value!r}). Your n8n admin sets it, for one shell "
                       f"only: {ARM_ENV_VAR}=true. No API call was made."),
        }
    return None


def _declaring_nodes(workflow, flags=DISPATCH_FLAGS):
    """The node names that actually declare a write-safety constant, DISCOVERED from the
    fetched workflow. Never a hardcoded list — the declaring set moves (23-01 added one,
    30-01 added a constant to eight nodes, 30-02 added a whole workflow), and a stale list
    silently narrows what the guard inspects."""
    names = set()
    for flag in flags:
        names.update(n8n_read.read_write_safety(workflow, flag).get("nodes") or [])
    return sorted(names)


def _assert_only_declaration_lines_changed(original, modified, node_names, flags=DISPATCH_FLAGS):
    """Node-level allowlisting permits rewriting a whole gate's body. This narrows the
    permitted diff to the declaration lines themselves: re-substituting the ORIGINAL
    literals back into the modified jsCode must reproduce the original byte for byte."""
    originals = {node.get("name"): (node.get("parameters") or {}).get("jsCode")
                 for node in original.get("nodes", []) if isinstance(node, dict)}

    for node in modified.get("nodes", []):
        if not isinstance(node, dict) or node.get("name") not in node_names:
            continue
        name = node.get("name")
        was, now = originals.get(name), (node.get("parameters") or {}).get("jsCode")
        if not isinstance(was, str) or not isinstance(now, str):
            continue

        rebuilt = now
        for flag in flags:
            decl_re = re.compile(rf"const\s+{re.escape(flag)}\s*=\s*[^;]+;")
            for original_decl in decl_re.findall(was):
                rebuilt = decl_re.sub(lambda _m, d=original_decl: d, rebuilt, count=1)

        if rebuilt != was:
            raise ArmingRefused(
                f"refusing the arm: node {name!r} differs outside its write-safety "
                f"declaration lines. Only the declarations may change during an arm; "
                f"anything else means the mutation reached further than it was allowed to."
            )


def arm_for_dispatch(workflow_id, record_ids, record_domains, allow_create, config,
                     transport=None):
    """Grant live writes for ONE dispatch, bounded to exactly the records in it.

    The allowlist is derived from the batch about to be dispatched, so the grant is
    record-scoped as well as operation-scoped: during the armed window the backend cannot
    write a record that was not in the dispatch. That is the strongest safety property this
    phase has, and it is reported back to the operator rather than left implicit.
    """
    import requests as _requests

    refusal = _arm_gate()
    if refusal:
        return refusal

    transport = transport if transport is not None else _requests

    ids = [str(v).strip() for v in (record_ids or []) if str(v).strip()]
    domains = [str(v).strip() for v in (record_domains or []) if str(v).strip()]

    if not ids and not domains:
        return {
            "outcome": REFUSED,
            "detail": ("refusing to arm: the record allowlist is empty. The deployed "
                       "_writeSafetyAllows() returns false when both allowlists are empty, "
                       "so arming the flag alone would report a successful arming that "
                       "grants nothing at all — worse than refusing, because it reads as "
                       "success."),
        }


    targets = {
        "ALLOW_HUBSPOT_RECORD_WRITES": True,
        "TEST_RECORD_IDS": ",".join(ids),
        "TEST_RECORD_DOMAINS": ",".join(domains),
    }
    if allow_create:
        targets["ALLOW_HUBSPOT_CREATE"] = True

    # Mirror of the deploy script's second fail-safe: the create constant has no effect
    # unless record-writes is enabled in the SAME request. Record-writes is unconditional
    # here, so this can only trip if a future edit makes it conditional — which is exactly
    # when it needs to fail.
    if "ALLOW_HUBSPOT_CREATE" in targets and not targets.get("ALLOW_HUBSPOT_RECORD_WRITES"):
        return {"outcome": REFUSED,
                "detail": ("refusing to arm: creation was requested without record writes "
                           "in the same call, which the deployed gate treats as no grant.")}

    prior = {}

    def _mutate(workflow):
        prior.update({flag: n8n_read.read_write_safety(workflow, flag).get("value")
                      for flag in DISPATCH_FLAGS})
        node_names = _declaring_nodes(workflow)
        rewritten, _counts = set_write_safety(workflow, targets)
        _assert_only_declaration_lines_changed(workflow, rewritten, node_names)
        workflow["nodes"] = rewritten["nodes"]

    def _verify(workflow):
        return {flag: n8n_read.read_write_safety(workflow, flag).get("value")
                for flag in targets}

    original = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    if not isinstance(original, dict):
        return {"outcome": REFUSED,
                "detail": "refusing to arm: the workflow could not be read, so nothing was "
                          "attempted."}

    result = n8n_control.apply_mutation(
        workflow_id, _mutate, _declaring_nodes(original), config,
        verify_fn=_verify, transport=transport,
        action=f"arm live writes on {workflow_id} for {len(ids)} id(s) and "
               f"{len(domains)} domain(s)")

    expected = {flag: (json.loads(_render_literal(flag, value)).strip('"')
                       if flag in ALLOWLIST_FLAGS else str(value).lower())
                for flag, value in targets.items()}

    if result.verdict != n8n_control.VERIFIED or result.observed != expected:
        return {"outcome": "failed", "detail": result.detail,
                "observed": result.observed, "requested": expected,
                "reversal": result.reversal,
                "operator_note": ("the arm did not verify — DO NOT DISPATCH. Some "
                                  "declaration still reads disabled, or declaring nodes "
                                  "disagree.")}

    return {
        "outcome": ARMED,
        "workflow_id": workflow_id,
        "prior": dict(prior),
        "observed": result.observed,
        "record_ids": ids,
        "record_domains": domains,
        "reversal": result.reversal,
        "consequence": (
            f"Live writes are enabled on {workflow_id} for exactly "
            f"{len(ids)} record id(s) and {len(domains)} domain(s) — and for nothing else. "
            f"The backend cannot write a record outside that list even while this window is "
            f"open. It closes as soon as the dispatch returns."),
    }


def disarm(workflow_id, config, transport=None):
    """Take live writes away again and PROVE it by an independent re-read.

    Deliberately NOT gated on ALLOW_N8N_ARM. A kill switch that blocked disarming would
    strand an armed backend, which is the exact failure the whole ceremony exists to
    prevent.
    """
    import requests as _requests
    transport = transport if transport is not None else _requests

    targets = disarmed_targets(*DISPATCH_FLAGS)

    def _mutate(workflow):
        rewritten, _counts = set_write_safety(workflow, targets)
        workflow["nodes"] = rewritten["nodes"]

    def _verify(workflow):
        return {flag: n8n_read.read_write_safety(workflow, flag).get("value")
                for flag in DISPATCH_FLAGS}

    original = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    node_names = _declaring_nodes(original) if isinstance(original, dict) else []
    workflow_name = original.get("name") if isinstance(original, dict) else None

    result = n8n_control.apply_mutation(
        workflow_id, _mutate, node_names, config, verify_fn=_verify,
        transport=transport, action=f"disarm live writes on {workflow_id}")

    expected = {flag: literal for flag, literal in targets.items()}
    observed = result.observed if isinstance(result.observed, dict) else {}

    still_enabled = {flag: value for flag, value in observed.items()
                     if value != expected.get(flag)}

    if result.verdict != n8n_control.VERIFIED or still_enabled:
        return {
            "outcome": DISARM_FAILED,
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "observed": observed,
            "expected": expected,
            "detail": (
                f"DISARM FAILED on {workflow_name!r} ({workflow_id}). Observed "
                f"{still_enabled or observed!r} where {expected!r} was required. "
                f"LIVE WRITES MAY STILL BE ENABLED — an admin should open n8n and check "
                f"this workflow directly. Do not treat this run as finished."),
        }

    return {"outcome": DISARMED, "workflow_id": workflow_id,
            "workflow_name": workflow_name, "observed": observed}


class armed_window:
    """Context manager: arm, run the caller's dispatch, disarm — including on the exception
    path, because a crash between dispatch and disarm is the one failure D-01's scoping
    cannot design away (D-02).

    When the body raised AND the disarm also failed, BOTH are surfaced. The disarm failure
    is the one that leaves state behind on a real backend, so it must not be buried under
    the body's traceback.
    """

    def __init__(self, workflow_id, record_ids, record_domains, allow_create, config,
                 transport=None):
        self._args = (workflow_id, record_ids, record_domains, allow_create, config)
        self._transport = transport
        self.workflow_id = workflow_id
        self.arm_result = None
        self.disarm_result = None

    def __enter__(self):
        self.arm_result = arm_for_dispatch(*self._args, transport=self._transport)
        if self.arm_result.get("outcome") != ARMED:
            raise ArmingRefused(self.arm_result.get("detail", "the arm did not succeed"))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disarm_result = disarm(self._args[0], self._args[4], transport=self._transport)

        if self.disarm_result.get("outcome") == DISARM_FAILED:
            if exc is None:
                raise DisarmFailed(self.disarm_result)
            # Both failed. Chain them so neither is lost: the body's exception is the
            # cause, the disarm failure is what still needs a human.
            raise DisarmFailed(self.disarm_result) from exc

        return False        # never swallow the body's exception
