# tests/test_recompute_flag_isolation.py
#
# Phase 75 Plan 04 (D-75-18) -- pins that ALLOW_HUBSPOT_RECOMPUTE_WRITES is deliberately
# excluded from every arming/overlay/disarm surface, and that the one script that DOES
# read it live (scripts/bounce_n8n_workflows.py) compares it against the COMMITTED
# workflow body rather than a hardcoded literal. Lives under the ROOT tests/ directory
# (not operator-claude-plugin/tests/), precisely so this plan implies no plugin release --
# see 75-04-SUMMARY.md.
#
# Each assertion below names D-75-18 and the consequence of the pin being removed: if the
# flag were EVER added to n8n_arming's overlay/disarm sets, an unattended disarm() call
# (triggered by a guardrail, a crashed dispatch, or an operator "kill everything" request)
# would silently rewrite this STANDING authority back to "false" -- exactly the mechanism
# D-75-16's operator ruling says must NOT be able to touch it.
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
PLUGIN_SCRIPTS = ROOT / "operator-claude-plugin" / "scripts"
if str(PLUGIN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SCRIPTS))

FLAG = "ALLOW_HUBSPOT_RECOMPUTE_WRITES"


# --- 1. WRITE_SAFETY_DEFAULTS ships the flag "false" -----------------------------------

def test_flag_is_in_write_safety_defaults_as_false():
    import build_cloud_workflows

    assert FLAG in build_cloud_workflows.WRITE_SAFETY_DEFAULTS, (
        f"D-75-18: {FLAG} must be a registered build-time constant (WRITE_SAFETY_DEFAULTS) "
        "-- if this pin is removed, the flag silently stops being a tracked write-safety "
        "literal at all, and no test anywhere would notice it drifting off \"false\"."
    )
    assert build_cloud_workflows.WRITE_SAFETY_DEFAULTS[FLAG] == "false", (
        f"D-75-18/D-75-17: {FLAG} must ship \"false\" -- the operator flips it live, by "
        "hand, post-supervised-sweep; a non-false committed default would arm every "
        "future build without that supervised review ever happening."
    )


# --- 2. absent from every n8n_arming.py overlay/disarm set -----------------------------

def test_flag_absent_from_n8n_arming_overlay_and_disarm_sets():
    import n8n_arming

    assert FLAG not in n8n_arming.OVERLAY_DISABLED_LITERALS, (
        f"D-75-18a: {FLAG} must NOT be in OVERLAY_DISABLED_LITERALS -- if it were, "
        "n8n_arming.disarm()'s derivation (`[flag for flag in OVERLAYABLE_FLAGS if ...]`) "
        "would rediscover it on every disarm and silently rewrite this STANDING authority "
        "back to \"false\" on an unattended guardrail trip, defeating D-75-16's ruling "
        "that only the operator flips it."
    )
    assert FLAG not in n8n_arming.OVERLAYABLE_FLAGS, (
        f"D-75-18a: {FLAG} must NOT be in OVERLAYABLE_FLAGS -- this is the set "
        "set_write_safety()/disarmed_targets() both gate every rewrite against; admitting "
        "it here is precisely what would let disarm() (see above) or a canary-style "
        "--enable-baked-flags overlay touch it at all."
    )
    assert FLAG not in n8n_arming.WRITE_ENABLING_FLAGS, (
        f"D-75-18a: {FLAG} must NOT be in WRITE_ENABLING_FLAGS -- that set drives "
        "arm_for_dispatch()'s per-authority flag selection (FLAGS_BY_AUTHORITY); "
        "admitting it here would let a plain dispatch/review arm grant recompute "
        "authority as a side effect, which D-75-16 never authorised."
    )


# --- 3. absent from deploy_n8n_workflows.py's overlay spec -----------------------------

def test_flag_absent_from_deploy_overlay_flag_spec():
    import deploy_n8n_workflows

    assert FLAG not in deploy_n8n_workflows._OVERLAY_FLAG_SPEC, (
        f"D-75-18a: {FLAG} must NOT be in _OVERLAY_FLAG_SPEC -- admitting it would let "
        "`--enable-baked-flags` arm this STANDING authority the same way it arms a "
        "bounded, per-invocation write-path canary, with no supervised-sweep review gate "
        "in between."
    )
    assert FLAG not in deploy_n8n_workflows._OVERLAYABLE_FLAGS, (
        f"D-75-18a: {FLAG} must NOT be in _OVERLAYABLE_FLAGS -- this is the set the "
        "overlay's own unknown-flag ValueError is checked against; its absence is what "
        "makes an attempt to overlay this flag refuse rather than silently succeed."
    )


# --- 4. asking n8n_arming to target it is refused (the existing unknown-flag path) -----

def test_set_write_safety_refuses_to_target_the_flag():
    """arm_for_dispatch() and disarm() both route every rewrite through
    set_write_safety()/disarmed_targets(); neither accepts an arbitrary flag name as a
    direct parameter, so this exercises the SAME unknown-flag refusal mechanism both
    functions rely on to make targeting this flag impossible by construction."""
    import n8n_arming

    workflow = {"nodes": [{"parameters": {"jsCode": f'const {FLAG} = "false";'}}]}
    with pytest.raises(n8n_arming.ArmingRefused) as excinfo:
        n8n_arming.set_write_safety(workflow, {FLAG: "true"})
    assert FLAG in str(excinfo.value), (
        f"D-75-18a: set_write_safety() must name {FLAG} in its refusal -- if this pin is "
        "removed (the flag admitted to OVERLAYABLE_FLAGS), arm_for_dispatch()/disarm() "
        "gain a live path to rewrite this standing authority."
    )


def test_disarmed_targets_refuses_to_target_the_flag():
    import n8n_arming

    with pytest.raises(n8n_arming.ArmingRefused) as excinfo:
        n8n_arming.disarmed_targets(FLAG)
    assert FLAG in str(excinfo.value), (
        f"D-75-18a: disarmed_targets() -- the function disarm() calls to build its "
        f"rewrite payload -- must refuse {FLAG} outright; disarm()'s own derivation only "
        "ever iterates OVERLAYABLE_FLAGS (see build_cloud_workflows check above), so this "
        "refusal is the second, independent backstop if that set were ever widened."
    )


# --- 5. bounce_n8n_workflows._row_ok compares live against the COMMITTED body ----------

def _bounce_body(recompute_value):
    return {
        "active": True,
        "settings": {"executionOrder": "v1"},
        "nodes": [
            {"parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";'}},
            {"parameters": {"jsCode": 'const ALLOW_HUBSPOT_CREATE = "false";'}},
            {"parameters": {"jsCode": f'const {FLAG} = "{recompute_value}";'}},
        ],
    }


def test_row_ok_accepts_live_true_when_committed_is_true():
    import bounce_n8n_workflows as bounce

    live = _bounce_body("true")
    committed = _bounce_body("true")
    assert bounce._row_ok(live, expected_nodes=3, committed_body=committed) is True, (
        f"D-75-18b: {FLAG}=\"true\" must be ACCEPTED when the committed body also carries "
        "\"true\" -- this is the operator's post-supervised-sweep flip (D-75-17); a "
        "bounce that rejected the agreeing case would either block the operator's own "
        "documented deploy step or (worse, if worked around) stop reading this flag "
        "entirely."
    )


def test_row_ok_rejects_live_true_when_committed_is_false():
    import bounce_n8n_workflows as bounce

    live = _bounce_body("true")
    committed = _bounce_body("false")
    assert bounce._row_ok(live, expected_nodes=3, committed_body=committed) is False, (
        f"D-75-18b: {FLAG}=\"true\" live against a \"false\" committed body must be "
        "REJECTED -- this is the case a bounce that silently ignored the flag (or a "
        "stale WRITE_FLAGS-only check) would pass, letting a standing authority stay "
        "armed with no committed-JSON authorisation and no operator visibility (T-75-15)."
    )


def test_row_ok_rejects_live_false_when_committed_is_true():
    """The opposite direction: the committed body says the operator flipped it, but the
    live workflow never actually received that PUT (or was reverted) -- a state the bounce
    must also flag, not just the more obviously dangerous direction above."""
    import bounce_n8n_workflows as bounce

    live = _bounce_body("false")
    committed = _bounce_body("true")
    assert bounce._row_ok(live, expected_nodes=3, committed_body=committed) is False, (
        f"D-75-18b: a committed \"true\" with live still \"false\" must also REJECT -- "
        "the committed-vs-live comparison is bidirectional, proving a stale/reverted "
        "deploy is caught exactly as readily as an over-armed one."
    )
