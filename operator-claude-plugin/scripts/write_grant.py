"""operator-claude-plugin/scripts/write_grant.py

The operator-openable write grant (53-01): the authority and the envelope that let a
dispatch arm live HubSpot writes without anyone setting a shell environment variable.

Three things a reader needs and cannot infer from the code:

1. **This is the repository's first deliberate exception to "authority gates are
   environment variables compared against the exact string 'true'"** (D-34, D-53-01). The
   interactive arm's authority is now an admin-set key in `operator.local.json`
   (`config_gate.WRITE_GRANT_SETTINGS_KEY`). The probe gate, the deploy gate and the
   HEADLESS arm gate (`n8n_arming.ARM_ENV_VAR`, which `scheduled_arm.py` still relies on)
   are unchanged and stay environment-gated. A reader who changes one of those must NOT
   assume the others followed — the split is three-way on purpose. The defect that forced
   it: `_arm_gate()` required `ALLOW_N8N_ARM=true` in the session's shell, which an
   operator in Claude Desktop cannot set, so the documented operator path ended in a
   refusal only an admin with terminal access could clear (G-2, live client UAT
   2026-08-25).

2. **The grant is held in the conversation, for the session, and is never persisted**
   (D-53-03). No file is written, no environment variable is set, no cache is kept, and
   there is no default for an absent grant (GRANT-06). The accepted risk that comes with
   that — a crashed session leaves the backend armed with a live record-scoped allowlist —
   was put to the operator on 2026-08-25 and accepted; 53-02's guardrails bound it.

3. **The grant is authority and envelope, NOT a held-open armed window.** Every send still
   opens and closes its own `n8n_arming.armed_window`. That is what keeps the guaranteed
   disarm the milestone's "what must NOT be lost" list names, and it is what D-53-04's
   "a failed disarm fails that send only" presupposes: there has to BE a per-send disarm
   for one to fail. A reader looking here for a disarm will not find one, and that is not
   an omission — see `close_grant`.
"""
import copy
from datetime import datetime, timezone

import config_gate
import executions_client
import scheduled_arm

KIND = "write_grant"
PROPOSAL_KIND = "write_grant_proposal"

OPEN = "open"
CLOSED = "closed"
REFUSED = "refused"

# Lane name -> the n8n workflow NAME it arms. Names are respelled nowhere: n8n assigns ids
# server-side, so a lane is resolved by name at plan time through the same resolver
# `scheduled_arm.py` uses.
#
# THE REVIEW LANE IS DELIBERATELY NOT GRANTABLE. `ALLOW_HUBSPOT_REVIEW_WRITES` is excluded
# from `n8n_arming.DISPATCH_FLAGS` by 30-01's D-02/D-08e precisely so that arming a
# dispatch grants nothing on the review path, and `ALLOW_REVIEW_SUBMIT` is its own gate.
# Folding review into a dispatch grant would revoke that separation silently.
#
# A GRANT MAY SPAN BOTH LANES — D-53-05, operator, 2026-08-25, accepted explicitly for
# speed after the planner raised the cost in full. Recorded here rather than only in
# planning because it REMOVES a protection a previous phase deliberately installed: with
# one grant across both lanes of enrich-before-ingest, the ingest authorization is
# necessarily given BEFORE the enriched preview exists, so held rows and merge conflicts —
# which that preview is the only place to see ahead of a write — are authorized unseen
# (37-CONTEXT §6.3 is the protection being traded). What still holds, and what the tests
# hold: the allowlist stays record-scoped to the batch, so the collapse widens WHEN the
# approval is given and never WHAT it covers; the enriched preview is still rendered; and
# revocation still works — the default flips from ask-again to proceed-unless-stopped.
LANES = {
    "enrichment": scheduled_arm.ENRICHMENT_WORKFLOW_NAME,
    "contacts": executions_client.CONTACT_INGEST_WORKFLOW_NAME,
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _refusal(detail, **fields):
    return {"outcome": REFUSED, "detail": detail, **fields}


def _normalise(values):
    return [str(v).strip() for v in (values or []) if str(v).strip()]


def plan_grant(config, *, lanes, object_type, record_ids, record_domains, allow_create,
               label, transport=None, preflight=None):
    """Compose a PROPOSAL for a write grant. Reads only — never mutates anything.

    Refuses, in this order and before returning anything: an unauthorized config, an
    unknown lane, an empty record set, a lane whose workflow cannot be resolved by name.

    `preflight` is a named seam for 53-02's guardrail A (refuse to open a grant when a
    live read finds writes already armed). When callable it is invoked with
    `(config, workflow_ids, transport)` before the proposal is built and its return value,
    when truthy, is returned unchanged as the refusal. The seam exists now so the
    guardrail lands as a fill rather than a reshape.
    """
    if not config_gate.write_grants_enabled(config):
        return _refusal(
            f"opening a write grant needs {config_gate.WRITE_GRANT_SETTINGS_KEY!r} set to "
            f"true in operator.local.json, which is not configured. Your n8n admin sets "
            f"it — it is the switch that lets live HubSpot writes be authorized from this "
            f"conversation at all. Nothing was read and nothing was changed.")

    lane_names = list(lanes or [])
    unknown = [lane for lane in lane_names if lane not in LANES]
    if unknown:
        return _refusal(
            f"there is no grantable lane called {', '.join(repr(l) for l in unknown)}. "
            f"The grantable lanes are: {', '.join(sorted(LANES))}. The review lane is "
            f"deliberately not grantable — review writeback is its own authority.")
    if not lane_names:
        return _refusal(
            f"a write grant must name at least one lane. The grantable lanes are: "
            f"{', '.join(sorted(LANES))}.")

    ids = _normalise(record_ids)
    domains = _normalise(record_domains)
    if not ids and not domains:
        return _refusal(
            "refusing to plan a grant over an empty record set. The deployed "
            "_writeSafetyAllows() returns false when both allowlists are empty, so a "
            "grant over nothing would report as a grant while granting nothing at all — "
            "worse than refusing, because it reads as success.")

    import requests as _requests
    transport = transport if transport is not None else _requests
    get_transport = transport.get if hasattr(transport, "get") else transport

    workflow_ids = {}
    unresolved = []
    for lane in lane_names:
        workflow_id = executions_client.resolve_workflow_id(
            config, transport=get_transport, workflow_name=LANES[lane])
        if workflow_id is None:
            unresolved.append(lane)
        else:
            workflow_ids[lane] = workflow_id
    if unresolved:
        return _refusal(
            f"could not resolve a workflow for lane(s) {', '.join(sorted(unresolved))} — "
            f"no workflow on this n8n instance is named "
            f"{', '.join(repr(LANES[l]) for l in sorted(unresolved))}. Nothing was armed. "
            f"Ask your n8n admin whether that workflow is deployed.")

    if callable(preflight):
        blocked = preflight(config, workflow_ids, transport)
        if blocked:
            return blocked

    return {
        "kind": PROPOSAL_KIND,
        "lanes": lane_names,
        "workflow_ids": workflow_ids,
        "object_type": object_type,
        "record_ids": ids,
        "record_domains": domains,
        "allow_create": bool(allow_create),
        "label": label,
        # 53-02 fills this with the arithmetic shown before the yes (GRANT-02/D-53-02).
        "envelope": None,
        "consequence": (
            f"Opening this grant lets live HubSpot writes be armed for exactly "
            f"{len(ids)} record id(s) and {len(domains)} domain(s) — and for nothing else "
            f"— on the {', '.join(lane_names)} lane(s), "
            f"{'including' if allow_create else 'excluding'} creation of new records. "
            f"Each send still opens and closes its own armed window, so the backend is "
            f"disarmed between sends. The grant covers no record outside that list, and "
            f"it closes when the batch finishes, on revocation, or when this session "
            f"ends."),
    }


def open_grant(proposal, confirmation, config):
    """Turn a PROPOSAL into an open grant. The only way a grant comes into existence.

    `confirmation` has NO default, so a caller that forgets it gets a TypeError rather
    than a silent open, and only the exact string "yes" proceeds — the same structural
    gate `control_actions.execute_action` uses, reproduced deliberately rather than
    approximated. Because it takes a proposal, a caller that skipped planning has nothing
    to open.

    The authority is re-checked here against the CONFIG, not against the proposal: a
    hand-built dict shaped like a proposal cannot open a grant on a backend whose admin
    never enabled write grants.
    """
    if not config_gate.write_grants_enabled(config):
        return _refusal(
            f"opening a write grant needs {config_gate.WRITE_GRANT_SETTINGS_KEY!r} set to "
            f"true in operator.local.json, which is not configured. Your n8n admin sets "
            f"it. Nothing was opened.")

    if confirmation != "yes":
        return _refusal(
            "not confirmed — no grant was opened. To go ahead, confirm with an explicit "
            "yes after reading what the grant covers.")

    if not isinstance(proposal, dict) or proposal.get("kind") != PROPOSAL_KIND:
        return _refusal(
            "there is nothing to open: a grant is opened from a proposal, so that what "
            "is being authorized has been composed and shown first. Plan the grant, then "
            "confirm it.")

    grant = copy.deepcopy(proposal)
    grant["kind"] = KIND
    grant["state"] = OPEN
    grant["opened_at"] = _now_iso()
    # Initialised here, written by 53-02, so its guardrails are a fill rather than a
    # reshape of a dict wave-1 tests already bind to.
    grant["closed_reason"] = None
    grant["consecutive_disarm_failures"] = 0
    return grant


def close_grant(grant, reason):
    """Close a grant. Returns a COPY; the input is never mutated.

    Performs NO network call and does NOT disarm — and that is not a forgotten step. With
    per-send armed windows there is no window open at close time: every send disarmed
    itself on the way out. 53-02 adds the two guardrail-B paths that DO disarm, for the
    specific reason that those two have just observed or inferred a live-write state.
    """
    closed = copy.deepcopy(grant if isinstance(grant, dict) else {})
    closed["state"] = CLOSED
    closed["closed_reason"] = reason
    return closed


def covers(grant, *, lane=None, workflow_id, record_ids, record_domains):
    """None when the send is inside the grant; a refusal dict when it is not.

    The ONE implementation of the scope question, so `arm_for_dispatch`'s grant branch and
    any lane skill answer it with one wording. `lane` is optional because
    `arm_for_dispatch` knows a workflow id and not a lane name — when it is None the
    workflow id is checked against every id the grant resolved.

    Refusals NAME the offending values: a refusal that said only "outside the grant" would
    leave the operator diffing two lists by eye.
    """
    if not isinstance(grant, dict) or grant.get("kind") != KIND:
        return _refusal("that is not a write grant, so it authorizes nothing.")

    if grant.get("state") != OPEN:
        return _refusal(
            f"this write grant is closed and authorizes nothing further. It closed "
            f"because: {grant.get('closed_reason')!r}. Open a new grant to continue.")

    granted_ids = grant.get("workflow_ids") or {}
    if lane is not None and lane not in (grant.get("lanes") or []):
        return _refusal(
            f"this grant does not cover the {lane!r} lane. It covers: "
            f"{', '.join(grant.get('lanes') or []) or '(none)'}.")

    permitted = [granted_ids[lane]] if lane is not None and lane in granted_ids \
        else list(granted_ids.values())
    if workflow_id not in permitted:
        return _refusal(
            f"this grant does not cover workflow {workflow_id!r}. It covers "
            f"{permitted!r}. A grant on one lane cannot authorize arming another lane's "
            f"workflow.")

    outside_ids = [v for v in _normalise(record_ids)
                   if v not in (grant.get("record_ids") or [])]
    outside_domains = [v for v in _normalise(record_domains)
                       if v not in (grant.get("record_domains") or [])]
    if outside_ids or outside_domains:
        return _refusal(
            f"these are outside the grant and were not authorized: "
            f"ids {outside_ids!r}, domains {outside_domains!r}. The grant covers "
            f"{len(grant.get('record_ids') or [])} id(s) and "
            f"{len(grant.get('record_domains') or [])} domain(s), and widening it needs a "
            f"new grant — a grant's record set is what bounds it (GRANT-03).",
            outside_record_ids=outside_ids, outside_record_domains=outside_domains)

    return None
