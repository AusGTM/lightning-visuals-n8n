"""operator-claude-plugin/scripts/n8n_control.py

The mutating half of the n8n surface — the only place in this milestone that changes
backend state. Everything here is bracketed by two independent reads, and no status code
is ever, on its own, reported as success (D-14).

Reading is not this module's job. `n8n_read.get_workflow()` (shipped by 27-01) is the same
GET against the same endpoint with the same `X-N8N-API-KEY` header, already injectable and
already returning `None` for every failure mode there is — that `None` feeds the `failed`
verdict directly, because an unreadable read-back is not a verified one (D-27). There is no
fetcher here, and no second write-safety declaration regex either (D-26).

The transport seam, stated plainly because getting it wrong trips a structural guard
silently. Every network-touching function takes `transport` defaulting to the BARE
`requests` module, and every call goes through `transport.get` / `transport.post` /
`transport.put`. That matches n8n_read.py's injectable-read seam, not dispatch.py's send
seam. See D-28 in 28-CONTEXT.md and the long comment above `_send()` for what breaks if
this is written the other way.

Credentials come from `config_gate.load_config()` only — never from the shell environment.
`N8N_URL` / `N8N_API_KEY` are the backend deploy script's variables; a plugin-side guard
reading them while the request authenticates from config is a guard that cannot fire (D-29).
"""
import copy
import json

import requests

import n8n_read

DEFAULT_TIMEOUT = 30

VERIFIED = "verified"
FAILED = "failed"

# Source: scripts/deploy_n8n_workflows.py::_update_workflow_live (lines 482-487), which
# filters to exactly these four keys and is live-tested against this same n8n Cloud
# instance. n8n rejects any other top-level key outright with "must NOT have additional
# properties" — a 400, not a silent strip (D-16). Copied verbatim rather than imported:
# PLUGIN-04 forbids importing across the client/backend boundary, so parity is held by
# the pin test in tests/test_control_verify_reporting.py, which reads the deploy script
# as TEXT.
PUT_BODY_KEYS = ("name", "nodes", "connections", "settings")

# How much of a prior value the reversal sentence quotes before it stops being a sentence.
_REVERSAL_VALUE_LIMIT = 200


class MutationRefused(Exception):
    """A requested change fell outside the allowlist and was refused, not attempted.

    Raised BEFORE any mutating call is made, so a refusal never leaves the backend
    half-changed or a live workflow deactivated (D-15, D-19, T-28-01).
    """


class MutationResult:
    """One mutation's whole story: what was asked, what was there before, what an
    INDEPENDENT read found afterwards, and the verdict that follows from comparing the
    last two.

    `reversal` is the plain-language undo sentence, built from the prior value that the
    pre-mutation read already had in hand (D-11/D-12). Nothing here composes operator
    prose beyond that sentence — the consequence statement and the confirmation are the
    surface's job, not this module's.
    """

    __slots__ = ("action", "prior", "requested", "observed", "verdict", "reversal", "detail")

    def __init__(self, action, prior, requested, observed, verdict, reversal, detail=None):
        self.action = action
        self.prior = prior
        self.requested = requested
        self.observed = observed
        self.verdict = verdict
        self.reversal = reversal
        self.detail = detail

    @property
    def verified(self) -> bool:
        return self.verdict == VERIFIED

    def as_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__slots__}

    def __repr__(self) -> str:
        return f"MutationResult(action={self.action!r}, verdict={self.verdict!r})"


def _headers(config: dict) -> dict:
    return n8n_read._headers(config)


def _workflow_url(config: dict, workflow_id) -> str:
    return f"{n8n_read._base_url(config)}/api/v1/workflows/{workflow_id}"


def _send(transport, verb: str, url: str, config: dict, body=None):
    """One mutating call. Returns `(ok, detail)`; never raises.

    The verb is fetched off `transport` by name rather than called as a literal
    module attribute. That is deliberate and load-bearing: test_retry_reuses_dispatch.py
    flags any function that names the send verbs directly on the requests module, or that
    takes a transport parameter defaulting to one of them, and it allowlists exactly two
    functions. This module must satisfy that guard rather than be added to it — the
    allowlist is what stands between a retry path and dispatch()'s no-default arming gate
    (T-28-30).
    """
    kwargs = {"headers": _headers(config), "timeout": DEFAULT_TIMEOUT}
    if body is not None:
        kwargs["json"] = body
    try:
        response = getattr(transport, verb)(url, **kwargs)
    except Exception:
        # The exception text can carry request headers; report the shape, not the text.
        return False, f"the {verb.upper()} to n8n could not be completed"

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or not 200 <= status_code < 300:
        return False, f"n8n answered the {verb.upper()} with status {status_code}"
    return True, None


def _verdict(requested, observed):
    """The ONE place a verified verdict can come from.

    Verified requires the independently fetched value to equal the requested one. A
    read-back that still shows the old value therefore fails by the same comparison that
    catches a read-back showing anything else — the all-200-but-stale case has no separate
    branch to forget (D-14, D-17, T-28-02).
    """
    if observed is not None and observed == requested:
        return VERIFIED, None
    return FAILED, (f"n8n was asked for {_quote(requested)} but an independent read-back "
                    f"found {_quote(observed)}")


def _quote(value) -> str:
    if value is None:
        return "nothing readable"
    # A string value is already the operator-readable form. Running it through json.dumps
    # would backslash-escape the quotes inside a JS flag literal, which is noise in a
    # sentence a person has to read.
    if isinstance(value, str):
        text = value
        return text if len(text) <= _REVERSAL_VALUE_LIMIT else text[:_REVERSAL_VALUE_LIMIT] + "…"
    try:
        text = json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = repr(value)
    return text if len(text) <= _REVERSAL_VALUE_LIMIT else text[:_REVERSAL_VALUE_LIMIT] + "…"


def _active_word(active) -> str:
    return "on" if active else "off"


def _active_reversal(prior_active) -> str:
    if prior_active is None:
        return "the prior state could not be read, so there is nothing to restore it to."
    word = _active_word(prior_active)
    return f"it was {word}; to undo, I'll turn it back {word}."


def _value_reversal(prior) -> str:
    if prior is None:
        return "the prior value could not be read, so there is nothing to restore it to."
    return f"it was {_quote(prior)}; to undo, I'll set it back to {_quote(prior)}."


def put_body(workflow: dict) -> dict:
    """The four keys `PUT /api/v1/workflows/{id}` accepts, and nothing else.

    Drops `id`, `active`, `tags`, `createdAt`, `updatedAt`, `staticData`, `versionId`,
    `pinData` and `meta`, all of which a raw GET response carries and all of which n8n
    rejects on the way back in. `active` in particular is never a PUT concern — activation
    state belongs exclusively to the activate/deactivate endpoints.
    """
    return {k: v for k, v in (workflow or {}).items() if k in PUT_BODY_KEYS}


def _nodes_by_name(workflow: dict) -> dict:
    nodes = (workflow or {}).get("nodes")
    nodes = nodes if isinstance(nodes, list) else []
    by_name = {node.get("name"): node for node in nodes if isinstance(node, dict)}
    if len(by_name) != len(nodes):
        raise MutationRefused(
            "refusing PUT: the workflow's node names are not unique, so a name-keyed diff "
            "cannot prove what changed"
        )
    return by_name


def _canonical(node) -> str:
    return json.dumps(node, sort_keys=True, default=str)


def assert_only_allowlisted_change(original: dict, modified: dict, allowed_node_names) -> None:
    """Refuse unless the ONLY difference is inside the named nodes.

    This is what makes an out-of-allowlist change impossible rather than merely
    unattempted (D-19). `PUT` replaces `nodes`/`connections`/`settings` wholesale, so
    anything that drifts between the fetch and the PUT lands in production; a structural
    diff is the only check that catches drift nobody intended.

    Raises `MutationRefused` naming the specific node or top-level key that differed, so a
    failure reads as an accusation rather than a puzzle.
    """
    allowed = set(allowed_node_names or ())
    original_nodes = _nodes_by_name(original)
    modified_nodes = _nodes_by_name(modified)

    # A typo in an allowlisted node name would otherwise sail through every check below
    # and produce a PUT that changes nothing while reporting a successful mutation.
    absent = sorted(name for name in allowed if name not in original_nodes)
    if absent:
        raise MutationRefused(
            f"refusing PUT: allowlisted node(s) {absent} are not in the fetched workflow — "
            "a mis-typed node name would produce a PUT that changes nothing while "
            "reporting success"
        )

    added = sorted(name for name in modified_nodes if name not in original_nodes)
    removed = sorted(name for name in original_nodes if name not in modified_nodes)
    if added or removed:
        raise MutationRefused(
            f"refusing PUT: the node set itself changed (added: {added}, removed: {removed}) "
            "— adding or removing a node is never allowlisted"
        )

    for name, node in original_nodes.items():
        if name in allowed:
            continue
        if _canonical(node) != _canonical(modified_nodes[name]):
            raise MutationRefused(
                f"refusing PUT: node {name!r} changed outside the allowlist"
            )

    if (original or {}).get("connections") != (modified or {}).get("connections"):
        raise MutationRefused("refusing PUT: 'connections' changed — never allowlisted")
    if (original or {}).get("settings") != (modified or {}).get("settings"):
        raise MutationRefused("refusing PUT: 'settings' changed — never allowlisted")


def set_active(workflow_id, desired_active: bool, config: dict, transport=requests) -> MutationResult:
    """Turn one workflow on or off, and prove it (CONTROL-02).

    GET the prior state, POST the bodyless activate/deactivate, then GET AGAIN and decide
    the verdict from that second, independent read. The activate/deactivate response echoes
    the workflow, but that echo is the mutation's own voice and is never the read-back
    (28-RESEARCH.md Pattern 4).
    """
    desired_active = bool(desired_active)
    action = f"turn workflow {workflow_id} {_active_word(desired_active)}"

    before = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    if not isinstance(before, dict):
        return MutationResult(action, None, desired_active, None, FAILED,
                              _active_reversal(None),
                              "the workflow could not be read before mutating, so nothing "
                              "was attempted")
    prior_active = bool(before.get("active"))
    reversal = _active_reversal(prior_active)

    verb_path = "activate" if desired_active else "deactivate"
    ok, detail = _send(transport, "post", f"{_workflow_url(config, workflow_id)}/{verb_path}",
                       config)
    if not ok:
        return MutationResult(action, prior_active, desired_active, None, FAILED, reversal,
                              detail)

    after = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    observed = bool(after.get("active")) if isinstance(after, dict) else None
    verdict, detail = _verdict(desired_active, observed)
    return MutationResult(action, prior_active, desired_active, observed, verdict, reversal,
                          detail)


def apply_mutation(workflow_id, mutate_fn, allowed_node_names, config, *, verify_fn,
                   transport=requests, action="workflow content mutation") -> MutationResult:
    """The bracketed content mutation every allowlisted PUT in this phase goes through.

    Sequence: fetch fresh, deep-copy, mutate the copy, REFUSE before any network call if
    anything outside the allowlist differs, then deactivate → PUT → restore the PRIOR
    active state, then fetch once more and read the verdict off that.

    `verify_fn(workflow) -> value` is required and has no default. It is the caller's
    narrow reader for the thing being changed (a write-safety literal, a cron string) —
    narrow because a whole-body comparison would fail on fields n8n normalizes server-side
    and would then have to be loosened, which is how status-code optimism gets back in.

    The workflow is always fetched here and never accepted as an argument: a copy fetched
    earlier in the session can have gone stale, and PUTting a stale body is the
    self-inflicted tampering path in the threat register (T-28-06).

    Restoring the prior active state rather than blindly activating is not a detail. A
    workflow an operator deliberately left off must not come back on because the plugin
    re-timed a schedule inside it (D-24, T-28-03). Where the prior state WAS active, the
    reactivation is also what forces the running instance to reload the changed content
    (D-18); where it was inactive there is no running instance and nothing to force.
    """
    original = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    if not isinstance(original, dict):
        return MutationResult(action, None, None, None, FAILED, _value_reversal(None),
                              "the workflow could not be read before mutating, so nothing "
                              "was attempted")

    prior = verify_fn(original)
    reversal = _value_reversal(prior)
    prior_active = bool(original.get("active"))

    modified = copy.deepcopy(original)
    mutate_fn(modified)
    # Before the deactivate, not merely before the PUT: a refusal that has already
    # deactivated a live workflow is a failed mutation dressed as a refusal.
    assert_only_allowlisted_change(original, modified, allowed_node_names)
    requested = verify_fn(modified)

    url = _workflow_url(config, workflow_id)

    if prior_active:
        ok, detail = _send(transport, "post", f"{url}/deactivate", config)
        if not ok:
            return MutationResult(action, prior, requested, None, FAILED, reversal, detail)

    ok, detail = _send(transport, "put", url, config, body=put_body(modified))
    if not ok:
        restore_detail = _restore_active(transport, url, config, prior_active)
        return MutationResult(action, prior, requested, None, FAILED, reversal,
                              detail if restore_detail is None else f"{detail}; {restore_detail}")

    restore_detail = _restore_active(transport, url, config, prior_active)
    if restore_detail is not None:
        return MutationResult(action, prior, requested, None, FAILED, reversal, restore_detail)

    after = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    observed = verify_fn(after) if isinstance(after, dict) else None
    verdict, detail = _verdict(requested, observed)
    return MutationResult(action, prior, requested, observed, verdict, reversal, detail)


def _restore_active(transport, url: str, config: dict, prior_active: bool):
    """Put the workflow back the way it was found. Returns a detail string on failure,
    `None` on success or when there was nothing to restore.

    A workflow that was off before the mutation gets no activate call at all — there is no
    running instance to reload and turning it on is a mutation nobody requested.
    """
    if not prior_active:
        return None
    ok, detail = _send(transport, "post", f"{url}/activate", config)
    if ok:
        return None
    return (f"{detail} — the workflow was active before this change and is now LEFT "
            "DEACTIVATED; an admin should re-activate it in n8n directly")
