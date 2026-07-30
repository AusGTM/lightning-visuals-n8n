"""Tests for DISPATCH-04.

Task 1: `report.classify_retryability()` and the report-level re-sendable roll-up —
which rows a re-send can actually fix.

Task 2: the single-send-path / no-accepted-row-store structural guard. Parses with
`ast` rather than grepping, mirroring `test_no_backend_imports.py`'s idiom, so a
docstring mentioning "dispatch" cannot fail it and an aliased definition cannot slip
past it.
"""
import ast
from pathlib import Path

import report

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"


def test_no_email_ambiguous_row_is_permanently_stuck(contact_execution):
    built = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})
    stuck = [
        r for r in built["failing_rows"]
        if r.get("email_status") == "NO_EMAIL" and r.get("outcome") == "ambiguous"
    ]
    assert stuck, "fixture must carry a NO_EMAIL + ambiguous row for this test to mean anything"
    for row in stuck:
        assert row["retryability"] == "permanently_stuck"
        assert row["retry_reason"] is not None
        assert "email" in row["retry_reason"].lower()

    resendable_ids = {r["_identity"] for r in built["resendable_rows"]}
    for row in stuck:
        assert row["_identity"] not in resendable_ids, (
            "a permanently-stuck row must never appear in the re-sendable set"
        )


def test_review_row_with_a_reason_other_than_no_email_is_a_business_outcome(contact_execution):
    built = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})
    # Fixture row 4: action=skip/outcome=rejected/email_status=NO_EMAIL but NOT
    # ambiguous — the marker requires NO_EMAIL *and* ambiguous together (D-11b). This
    # row fails for a business reason (missing required identity fields), not the
    # permanently-stuck one.
    business_rows = [r for r in built["failing_rows"] if r.get("outcome") == "rejected"]
    assert business_rows, "fixture must carry a non-ambiguous rejected row"
    for row in business_rows:
        assert row["retryability"] == "business_outcome"
        assert row["retryability"] != "permanently_stuck"
        assert row["retryability"] != "transport_failure"
        assert "same outcome" in row["retry_reason"]


def test_successfully_written_rows_are_nothing_to_retry(contact_execution):
    built = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})
    for row in built["rows"]:
        if row["reported_label"] in report.SUCCESS_LABELS:
            assert row["retryability"] == "nothing_to_retry"
            assert row["retry_reason"] is None


def test_not_confirmed_row_is_a_transport_failure_and_is_resendable():
    # A decided update/create the write-safety gate filtered before it reached
    # HubSpot — the same shape as a chunk that never got a response or came back
    # with a server error (Phase 25's failed-chunk unit). Safe to re-send unchanged.
    row = {
        "action": "update",
        "reported_outcome": "not_confirmed",
        "outcome": "match",
        "contact_id": "contact-x",
        "email_status": "verified",
        "reason": "the write was gated or filtered before it reached HubSpot",
    }
    assert report.classify_retryability(row) == "transport_failure"


def test_classifier_never_raises_on_a_row_missing_every_field_it_reads():
    for row in ({}, {"action": "review"}, {"email_status": "NO_EMAIL"}, None, "not-a-dict"):
        state = report.classify_retryability(row)
        assert state in {
            "nothing_to_retry", "transport_failure", "permanently_stuck", "business_outcome",
        }


def test_resendable_rows_never_include_permanently_stuck_or_business_outcome(contact_execution):
    built = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})
    for row in built["resendable_rows"]:
        assert row["retryability"] == "transport_failure"


# =====================================================================================
# Task 2: the single-send-path / no-accepted-row-store structural guard.
# =====================================================================================

# A send is a body-carrying, state-changing HTTP verb — POST or PUT — as opposed to
# executions_client.py's own injectable `transport` parameter, which defaults to
# `requests.get` for every one of its (read-only) functions. Distinguishing on the
# verb, not on "calls something named transport", is what keeps this guard from
# flagging the read-only fetchers 26-01 already added.
_SEND_CALL_ATTRS = {"post", "put"}

# A store of previously-sent/accepted rows would be a second dedupe authority
# competing with the backend's own identity resolution (D-04/D-05). Any assignment
# (module-level or nested inside a function) whose name suggests this is forbidden
# outright, regardless of whether it's ever populated.
_LEDGER_NAME_MARKERS = ("accepted", "sent_rows", "dedupe", "already_sent", "seen_rows")


def _plugin_source_files():
    return [p for p in SCRIPTS_DIR.rglob("*.py") if "__pycache__" not in p.parts]


def _parse(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_requests_send_attribute(node) -> bool:
    """True for `requests.post` / `requests.put` (as an attribute value, e.g. a
    parameter default) — the same object dispatch.py's `transport=requests.post`
    default carries."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr in _SEND_CALL_ATTRS
        and isinstance(node.value, ast.Name)
        and node.value.id == "requests"
    )


def _has_send_shaped_transport_default(func_def) -> bool:
    """True if this function's OWN `transport` parameter defaults to
    `requests.post`/`requests.put` — dispatch.py's exact shape. A function whose
    `transport` parameter defaults to `requests.get` (every function in
    executions_client.py) is a fetch, not a send, and must not match."""
    args = func_def.args
    positional_defaulted = (
        list(zip(args.args[len(args.args) - len(args.defaults):], args.defaults))
        if args.defaults else []
    )
    kwonly_defaulted = list(zip(args.kwonlyargs, args.kw_defaults or []))
    for arg, default in positional_defaulted + kwonly_defaulted:
        if arg.arg == "transport" and default is not None and _is_requests_send_attribute(default):
            return True
    return False


def _calls_requests_send_verb_directly(func_def) -> bool:
    """True if this function's body calls `requests.post(...)`/`requests.put(...)`
    directly (not via an injected `transport` callable)."""
    for inner in ast.walk(func_def):
        if isinstance(inner, ast.Call) and _is_requests_send_attribute(inner.func):
            return True
    return False


def _send_shaped_function_names(tree):
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and (_has_send_shaped_transport_default(node) or _calls_requests_send_verb_directly(node))
    ]


def _module_level_assigned_names(tree):
    """Names assigned at MODULE scope only (direct children of the module body) —
    e.g. `executions_client.py`'s own `_workflow_id_cache: dict = {}`. A "store" is
    by definition something that persists across calls; a local variable recomputed
    fresh inside a function body every call (extraction.py's `accepted` rows, say)
    cannot persist anything and is a false positive this guard must not raise."""
    names = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        names.append(sub.id)
    return names


def test_scan_found_at_least_one_plugin_source_file():
    """Non-vacuity: this guard cannot pass by scanning nothing."""
    assert len(_plugin_source_files()) > 0


def test_exactly_one_module_defines_the_send_shaped_function():
    offenders = []
    for path in _plugin_source_files():
        names = _send_shaped_function_names(_parse(path))
        if names:
            offenders.append((path.relative_to(SCRIPTS_DIR).as_posix(), names))

    assert offenders == [("dispatch.py", ["dispatch"])], (
        f"expected exactly one send-shaped function, dispatch.py's own dispatch(); "
        f"found: {offenders}. A second dispatch path would let a retry bypass the "
        "arming gate that dispatch.py's own `armed` parameter (no default) enforces."
    )


def test_dispatch_armed_parameter_still_carries_no_default():
    tree = _parse(SCRIPTS_DIR / "dispatch.py")
    dispatch_def = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch"
    )
    args = dispatch_def.args
    # `armed` has no default iff it is not among the last len(defaults) positional
    # args, and not present among the keyword-only defaults either.
    positional = args.args
    num_defaults = len(args.defaults)
    defaulted_positional_names = (
        {a.arg for a in positional[len(positional) - num_defaults:]} if num_defaults else set()
    )
    kwonly_defaulted_names = {
        a.arg for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None
    }
    assert "armed" not in defaulted_positional_names | kwonly_defaulted_names, (
        "dispatch()'s `armed` parameter must never gain a default — a forgotten "
        "argument on retry must raise, never silently send (T-26-11)."
    )


def test_no_module_defines_or_persists_a_previously_sent_row_store():
    offenders = {}
    for path in _plugin_source_files():
        tree = _parse(path)
        hits = [
            name for name in _module_level_assigned_names(tree)
            if any(marker in name.lower() for marker in _LEDGER_NAME_MARKERS)
        ]
        if hits:
            offenders[path.relative_to(SCRIPTS_DIR).as_posix()] = hits

    assert not offenders, (
        f"found a name suggesting a client-side accepted/sent-row store: {offenders}. "
        "Duplicate safety on retry is a backend property (D-04/D-05) — the backend "
        "resolves identity and routes update-vs-create on every row. A client-side "
        "ledger of what was previously sent/accepted would be a second dedupe "
        "authority that can drift from the backend's."
    )
