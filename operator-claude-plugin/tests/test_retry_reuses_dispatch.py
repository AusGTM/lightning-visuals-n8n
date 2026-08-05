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


def _has_bare_requests_module_transport_default(func_def) -> bool:
    """True if this function's OWN `transport` parameter defaults to the bare
    `requests` MODULE (an `ast.Name` whose `id` is `requests`) rather than an
    attribute like `requests.post` — `enrichment.py`'s
    `dispatch_enrichment(..., transport=requests)` shape, invisible to
    `_has_send_shaped_transport_default` because that default is not an
    `ast.Attribute`. Reuses the same positional/keyword-only default-pairing logic
    rather than duplicating the zip arithmetic."""
    args = func_def.args
    positional_defaulted = (
        list(zip(args.args[len(args.args) - len(args.defaults):], args.defaults))
        if args.defaults else []
    )
    kwonly_defaulted = list(zip(args.kwonlyargs, args.kw_defaults or []))
    for arg, default in positional_defaulted + kwonly_defaulted:
        if (
            arg.arg == "transport"
            and isinstance(default, ast.Name)
            and default.id == "requests"
        ):
            return True
    return False


def _calls_transport_send_verb(func_def) -> bool:
    """True if this function's body contains an `ast.Call` whose `func` is an
    `ast.Attribute` with `.attr` in `_SEND_CALL_ATTRS` and whose `.value` is an
    `ast.Name` equal to THIS function's own `transport` parameter name — e.g.
    `transport.post(...)` inside a function whose `transport` parameter is named
    `transport`. Binding to the parameter's own name (rather than any `.post` call
    anywhere in the body) is what keeps a read-only fetcher that happens to call some
    OTHER object's `.post` out of the set."""
    transport_param = next(
        (a.arg for a in func_def.args.args + func_def.args.kwonlyargs if a.arg == "transport"),
        None,
    )
    if transport_param is None:
        return False
    for inner in ast.walk(func_def):
        if (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr in _SEND_CALL_ATTRS
            and isinstance(inner.func.value, ast.Name)
            and inner.func.value.id == transport_param
        ):
            return True
    return False


def _send_shaped_function_names(tree):
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and (
            _has_send_shaped_transport_default(node)
            or _calls_requests_send_verb_directly(node)
            or (
                _has_bare_requests_module_transport_default(node)
                and _calls_transport_send_verb(node)
            )
        )
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


# The status read (27-03) is a POST only because the n8n webhook that answers it is a
# POST endpoint — `hubspot/backend-status` has no write node anywhere in its chain
# (tests/test_backend_status_wiring.py::test_endpoint_chain_contains_no_write_node), and
# the request carries no records at all. It is a read wearing a POST's clothes, so it is
# allowlisted here rather than gated on arming — and the allowlist is kept honest by
# test_the_allowlisted_status_post_carries_no_record_payload below.
# `enrichment.py`'s `dispatch_enrichment` is the enrichment lane's single send. Its
# `armed` parameter has no default and it raises `NotArmedError` before a transport is
# ever constructed (test_dispatch_enrichment_armed_parameter_carries_no_default,
# below), so it is listed here because the guard can now SEE it — not because it is
# exempt from anything the other two entries above are held to. Until the two helpers
# above existed, this function's `transport=requests` default (the bare module, not an
# attribute) was invisible to every predicate this guard had: not
# `_has_send_shaped_transport_default` (its default is not an `ast.Attribute`), not
# `_calls_requests_send_verb_directly` (its body calls `transport.post`, not
# `requests.post`). This guard's own failure message — "a second dispatch path would
# let a retry bypass the arming gate" — was therefore NOT TRUE of the code it guarded,
# because a second dispatch path already existed and this guard could not see it.
#
# Closing that hole also makes the guard SEE two functions that were ALREADY
# module-shaped (`transport=requests`, body calls `transport.post`) and already
# documented as deliberately outside this guard's radar — `review_queue.py::fetch_queue`
# (its own docstring, D-17/Phase 28 D-28/D-33: "never transport=requests.post ... this
# module must never join that list" — written when the guard genuinely could not see it)
# and `probe_n8n_semantics.py::execute_probe` (a human-supervised, arming-lifecycle-gated
# diagnostic probe, never an operator-facing verb). Neither sends a HubSpot record: the
# review-queue POST body is `{object_type, limit}` only (a query, not a write — the
# retryable thing this guard protects), and `execute_probe`'s POST carries no body at all
# and exists to observe whether n8n's execute endpoint responds, gated by its own
# `_gate()` check. Both are allowlisted here for the same reason as the status read
# above: a read (or, for execute_probe, a bodyless existence check) wearing a send verb's
# clothes, now correctly visible instead of accidentally invisible.
#
# `preingest.py`'s `fetch_matches` (Phase 37) is written attribute-shaped
# (`transport=requests.post`, dispatch.py's exact shape) so it IS visible to
# `_is_requests_send_attribute` and lands on this allowlist deliberately — never
# module-shaped to slip past the guard (37-CONTEXT §7/§12 explicitly forbids that). The
# match POST reads HubSpot search results, writes nothing and spends nothing (an
# explicit empty provider selection is sent), so it is a read wearing a POST's clothes —
# allowlisted rather than armed, and it carries no `armed` parameter at all, so there is
# nothing to gate. The two keeper tests below stop this being a rubber stamp: one
# asserts no call anywhere in `preingest.py` can carry a multipart or form payload, and
# one asserts the four-key lookup allowlist every match request is pinned to
# (`enrichment.MATCH_LOOKUP_KEYS`) cannot silently widen.
_EXPECTED_SEND_SHAPED = [
    ("backend_status.py", ["fetch_backend_status"]),
    ("dispatch.py", ["dispatch"]),
    ("enrichment.py", ["dispatch_enrichment"]),
    ("preingest.py", ["fetch_matches"]),
    ("probe_n8n_semantics.py", ["execute_probe"]),
    ("review_queue.py", ["fetch_queue"]),
]


def test_exactly_one_module_defines_the_send_shaped_function():
    offenders = []
    for path in _plugin_source_files():
        names = _send_shaped_function_names(_parse(path))
        if names:
            offenders.append((path.relative_to(SCRIPTS_DIR).as_posix(), names))

    assert sorted(offenders) == _EXPECTED_SEND_SHAPED, (
        f"expected exactly one record-sending function, dispatch.py's own dispatch() "
        f"(plus the allowlisted read-only status POST); found: {offenders}. A second "
        "dispatch path would let a retry bypass the arming gate that dispatch.py's own "
        "`armed` parameter (no default) enforces."
    )


def test_the_allowlisted_status_post_carries_no_record_payload():
    """Keeps the allowlist above from becoming a rubber stamp: the status POST may be
    exempt from the arming gate only for as long as it cannot carry records. `files=`
    (dispatch.py's multipart upload) or `data=` appearing here would make it a send."""
    source = (SCRIPTS_DIR / "backend_status.py").read_text()
    for payload_kwarg in ("files=", "data="):
        assert payload_kwarg not in source, (
            f"backend_status.py now passes {payload_kwarg} — it is no longer a bodyless "
            "read and must not stay exempt from the arming gate."
        )


def test_the_allowlisted_status_post_sends_an_empty_json_body():
    """The kwarg the status POST actually uses is `json=`, which the check above does not
    cover — grepping for `files=`/`data=` would stay green while `json={"events": [...]}`
    shipped records down an arming-exempt path. Assert the body is the empty literal, by
    AST so a formatting change cannot fool it."""
    tree = _parse(SCRIPTS_DIR / "backend_status.py")
    bodies = [
        kw.value
        for node in ast.walk(tree) if isinstance(node, ast.Call)
        for kw in node.keywords if kw.arg == "json"
    ]
    assert bodies, (
        "backend_status.py no longer passes json= at all — this guard has gone vacuous; "
        "re-derive which kwarg now carries the request body."
    )
    for body in bodies:
        assert isinstance(body, ast.Dict) and not body.keys, (
            "backend_status.py's status POST now sends a non-empty json= body. It can "
            "carry records, so it must not stay exempt from the arming gate."
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


def test_dispatch_enrichment_armed_parameter_still_carries_no_default():
    tree = _parse(SCRIPTS_DIR / "enrichment.py")
    dispatch_def = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch_enrichment"
    )
    args = dispatch_def.args
    positional = args.args
    num_defaults = len(args.defaults)
    defaulted_positional_names = (
        {a.arg for a in positional[len(positional) - num_defaults:]} if num_defaults else set()
    )
    kwonly_defaulted_names = {
        a.arg for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None
    }
    assert "armed" not in defaulted_positional_names | kwonly_defaulted_names, (
        "dispatch_enrichment()'s `armed` parameter must never gain a default — a "
        "forgotten argument on retry must raise, never silently send."
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


# =====================================================================================
# 37-03 Task 1: the two keepers that stop preingest.py's allowlist entry above from
# becoming a rubber stamp. Both parse with `ast` rather than grepping, same idiom as the
# rest of this file, so a docstring mentioning `files=`/`data=` cannot false-positive and
# a formatting change cannot fool the second one.
# =====================================================================================

# The same two names test_the_allowlisted_status_post_carries_no_record_payload already
# forbids — a match request can never carry a multipart file (dispatch.py's shape) or a
# form body.
_FORBIDDEN_PAYLOAD_KWARGS = {"files", "data"}


def test_the_allowlisted_match_post_carries_no_multipart_or_form_payload():
    """Keeper one. `fetch_matches` may stay exempt from the arming gate only for as
    long as nothing in `preingest.py` can carry a record payload."""
    tree = _parse(SCRIPTS_DIR / "preingest.py")
    offenders = sorted({
        kw.arg
        for node in ast.walk(tree) if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg in _FORBIDDEN_PAYLOAD_KWARGS
    })
    assert not offenders, (
        f"preingest.py now passes {offenders} on a call — the match POST can carry "
        "records and must not stay exempt from the arming gate."
    )


def test_match_lookup_keys_stays_the_frozen_four():
    """Keeper two. `enrichment.MATCH_LOOKUP_KEYS` is the allowlist every match
    request's body is projected through — parsed by AST, not imported, so this test
    fails even if some other code path shadowed or reassigned the name at runtime."""
    tree = _parse(SCRIPTS_DIR / "enrichment.py")
    assign = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "MATCH_LOOKUP_KEYS" for t in node.targets)
    )
    assert isinstance(assign.value, (ast.Tuple, ast.List)), (
        "MATCH_LOOKUP_KEYS must be a literal tuple/list of string constants, not an "
        "expression this guard cannot read statically."
    )
    values = [elt.value for elt in assign.value.elts if isinstance(elt, ast.Constant)]
    assert len(values) == len(assign.value.elts), (
        "MATCH_LOOKUP_KEYS must contain only string literal constants."
    )
    assert tuple(values) == ("email", "firstname", "lastname", "company"), (
        f"MATCH_LOOKUP_KEYS changed to {tuple(values)} — a match request would widen "
        "or narrow what crosses the boundary per row."
    )
    for richer_prop in ("phone", "jobtitle", "linkedin_url"):
        assert richer_prop not in values, (
            f"{richer_prop!r} must never appear in MATCH_LOOKUP_KEYS — it is a richer "
            "contact prop the match lookup does not need and must not send."
        )
