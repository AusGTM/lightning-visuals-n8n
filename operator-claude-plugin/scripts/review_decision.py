"""operator-claude-plugin/scripts/review_decision.py

The write half of review triage: adjudicate ONE flagged record through the n8n
`hubspot/review/decision` endpoint, see the exact patch the backend would send before it
is sent, and report the result from an independent re-read rather than from a status code
(REVIEW-03, REVIEW-04, REVIEW-05).

THE EXACT-WRITE DISPLAY IS THE BACKEND'S OWN PATCH. `preview_decision` sends the same
request with `dry_run: true`; the endpoint computes the patch and returns it without
writing (D-03, D-05). This module never builds a patch, never names a field, and never
sends a value — the request carries only which record and which decision word, so what the
operator approves is literally what the backend would send and no second copy of the merge
rule exists here (D-07).

THREE INDEPENDENT GATES must all be open before a decision lands. Any one closed stops
the write:

  1. `ALLOW_REVIEW_SUBMIT` — read HERE, by Python, on the operator's machine, before a
     request exists. An admin sets it. See below.
  2. The session arm — `review_armed`, handed in from the conversation, never read from or
     written to disk, so it cannot outlive the session (D-01, D-04). Separate from the
     contact-dispatch arm in both directions (D-02).
  3. `ALLOW_HUBSPOT_REVIEW_WRITES` plus its `TEST_RECORD_*` allowlist — the BACKEND baked
     constant from 30-01: a literal compiled into the workflow JSON, overlaid at deploy
     time, read by `_writeSafetyAllows()` inside n8n, in a different process on a
     different machine. **It is not the variable in (1) despite the similar name.**
     Setting one has not done the work of the other. **Corrected 2026-08-03, Phase 31 Plan
     02 (BUG 30):** an armed-but-not-allowlisted decision no longer returns NO body — it
     answers an explicit `not_allowlisted` outcome naming the allowlist, which
     `verify_decision` reports as `not_written`, not `failed`. A response that genuinely
     fails to parse now means the WORKFLOW ITSELF errored, not the allowlist — see the
     `unparseable_response` handling below.

`ALLOW_REVIEW_SUBMIT` (D-16, Phase 28 D-34) is this module's env kill switch, carried over
from `ALLOW_N8N_ARM` without variation:

  (a) Only the exact string `"true"` proceeds. `""`, `"1"`, `"yes"`, `"TRUE"` and `"True"`
      all refuse. Two gates in one milestone that disagree on what counts as "on" is worse
      than one gate.
  (b) It is checked BEFORE any transport is constructed, so an unset variable leaves an
      empty call log rather than an unsent request. It is the gate that still holds when an
      agent, a test harness or a scheduled routine reaches this module by a path nobody
      anticipated — which is exactly what the conversation-scoped arm and the in-conversation
      confirmation cannot cover.
  (c) It gates SUBMITTING a decision and never any un-doing path, the same way
      `ALLOW_N8N_ARM` gates arming but never disarming. A rejection records a reason and
      leaves the record in the queue (D-10); blocking that would strand a record
      mid-decision, which is the mirror of the stranded-armed-backend failure the carve-out
      exists to prevent. `preview_decision` is likewise ungated — a dry run writes nothing,
      and without it the operator cannot see what they are being asked to approve.

It is defence in depth, not a replacement: the session arm and the per-decision exact-write
display both stay.

D-60-04 AMENDMENT (operator, 2026-09-01): gate 1 above is RETIRED as an environment
variable. `ALLOW_REVIEW_SUBMIT`, `SUBMIT_ENV_VALUE`, `submit_enabled()` and the
`_ENV_REFUSAL` message are deleted from this module (Phase 60) — none of the three
paragraphs above describe live code anymore, and they are left in place rather than
rewritten because they are the record of why the gate looked the way it did. Gate 1 is now
GRANT-AUTHORIZATION: `write_grant.authorize_send(grant, lane=write_grant.REVIEW_LANE,
record_ids=[str(record_id)], record_domains=[])`, checked BEFORE any transport exists,
exactly the same authorization call enrichment's dispatch already uses rather than a second
copy of the check (`write_grant.covers` stays the ONE scope implementation). Property (c)
above — the un-doing carve-out that lets a `reject` bypass gate 1 — SURVIVES, re-pointed at
the grant check rather than deleted, per D-60-07: a closed authority must never be able to
strand a flagged record mid-decision. See `submit_decision`'s own docstring for the honest
limit of what that carve-out delivers (client-side submission, never a guarantee of
landing — cross-AI review, MEDIUM-3, 2026-09-01). Gates 2 (`review_armed`) and 3
(`ALLOW_HUBSPOT_REVIEW_WRITES`) are UNCHANGED by this amendment.

TRANSPORT SHAPE (D-17, Phase 28 D-28/D-33): `transport` defaults to the BARE `requests`
module and every call goes through `transport.post(...)` — never `transport=requests.post`,
never a direct `requests.post(...)`. `tests/test_retry_reuses_dispatch.py` scans every
plugin script for a send-shaped default and allowlists exactly two functions; this module
must never join that list. If that guard fires here, this module is wrong — appending to
`_EXPECTED_SEND_SHAPED` would weaken the guard standing between a client path and
`dispatch()`'s no-default `armed` parameter.

FAILURE MODES SPLIT TWO WAYS (D-35, mirroring `review_queue.fetch_queue`):
`config_gate.require_capability` RAISES `ConfigError` for a misconfiguration — the
operator's own fix, named in plain language, before any transport exists — while every
runtime failure degrades to `{available: False, reason, ...}`. A caller that only checks
for an exception would read a 401, a dead endpoint or an empty body as a completed
decision.

Auth is `X-Enrichment-Secret`. The secret goes in a header and nowhere else: never
rendered, never logged, never echoed in a refusal.
"""
import json

import requests

import config_gate

DECISION_PATH = "webhook/hubspot/review/decision"
DEFAULT_TIMEOUT = 30

# The audit trail must always name something; the backend writes lv_enrichment_reviewed_by
# only when the label is non-empty, so an empty string would leave the field unstamped.
DEFAULT_REVIEWED_BY = "operator (unnamed)"

# The endpoint's full outcome vocabulary (D-30). `unsupported` is retired.
# `not_allowlisted` added Phase 31 Plan 02, 2026-08-03 (BUG 30): the explicit refusal an
# allowlist drop now answers instead of an empty body — see review_decision.py's docstring
# gate 3 and `operator-claude-plugin/tests/test_review_outcome_parity.py`, which pins this
# tuple against BOTH n8n/code/reviewDecision.js and the committed workflow JSON as text.
WRITING_OUTCOMES = ("applied", "rejected")
NON_WRITING_OUTCOMES = ("stale", "no_candidate", "not_flagged", "refused", "not_allowlisted")
OUTCOMES = WRITING_OUTCOMES + NON_WRITING_OUTCOMES

# The un-doing decisions gate 1 must never block (D-16 property (c), re-pointed at the
# grant check by D-60-07). A rejection records a reason and leaves the record in the
# queue — it walks a decision back rather than promoting anything.
UNDOING_DECISIONS = ("reject",)

# D-60-04: gate 1's refusal reason and message. Replaces the retired
# `submit_not_enabled` / `_ENV_REFUSAL` pair — see the docstring amendment above.
GRANT_REFUSAL_REASON = "grant_not_authorized"

_GRANT_REFUSAL = (
    "Review writeback needs an open write grant covering this record: no request was even "
    "built. Opening one is something the operator can do in this conversation, once an n8n "
    "admin has enabled write grants. Two things still work without one: previewing the "
    "exact write, and rejecting a record, which records your reason and leaves the record "
    "in the queue."
)

_NOT_ARMED_REFUSAL = (
    "Review writeback is off — nothing was sent. The write shown is exactly what would be "
    "sent, computed by the backend rather than guessed at here. It turns on only when the "
    "operator says yes to this record's exact write, and that yes covers this record "
    "alone: a yes given on contact dispatch does not authorize a review write, and this "
    "one does not authorize a dispatch."
)


def decision_target(config: dict) -> str:
    """The endpoint this module POSTs to. Never includes the secret."""
    return f"{str(config.get('n8n_url') or '').rstrip('/')}/{DECISION_PATH}"


def is_undoing(decision) -> bool:
    """True for a decision that walks a record back rather than promoting anything.

    Only these bypass gate 1 (grant-authorization). An unrecognised decision word is NOT
    un-doing — the gate fails closed on anything it does not recognise.
    """
    word = decision.strip().lower() if isinstance(decision, str) else ""
    return word in UNDOING_DECISIONS


def _unavailable(reason: str, message=None, would_write=None) -> dict:
    return {"available": False, "reason": reason, "outcome": None, "message": message,
            "would_write": would_write, "verified_properties": None, "verified": None}


def _request_body(object_type, record_id, decision, reason, reviewed_by, dry_run) -> dict:
    """The six keys the endpoint reads, and nothing else (T-30-05). No field name, no
    value, no patch: this client cannot tell the endpoint WHAT to write."""
    return {
        "object_type": object_type,
        "record_id": None if record_id is None else str(record_id),
        "decision": decision,
        # A decision without a reason is still a decision (D-09).
        "reason": "" if reason is None else reason,
        "reviewed_by": (reviewed_by or "").strip() or DEFAULT_REVIEWED_BY,
        "dry_run": dry_run,
    }


def _post_decision(config, body, transport) -> dict:
    """One POST. Returns the five-key contract plus `{available, reason}` (D-19, D-35)."""
    config_gate.require_capability(config, "review")

    headers = {"X-Enrichment-Secret": config["webhook_secret"]}

    try:
        response = transport.post(decision_target(config), headers=headers, json=body,
                                  timeout=DEFAULT_TIMEOUT)
    except Exception:
        # Never echo the transport exception's text — it can carry request headers.
        return _unavailable("endpoint_unreachable")

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or not 200 <= status_code < 300:
        return _unavailable(f"http_{status_code}" if status_code else "no_response")

    try:
        payload = response.json()
    except Exception:
        # CORRECTED Phase 31 Plan 02, 2026-08-03 (BUG 30 — this exact wrong turn misled the
        # live RB-9 run): an allowlist drop no longer returns an empty body — it answers an
        # explicit `not_allowlisted` outcome (see WRITING/NON_WRITING_OUTCOMES above). A
        # body that fails to parse as JSON here therefore means the WORKFLOW ITSELF failed
        # to run to completion, not that the record was refused. n8n execution history is
        # where that failure is diagnosed — TEST_RECORD_IDS is no longer the first place to
        # look for an unparseable response.
        return _unavailable("unparseable_response")

    # ONE dict, never `body[0]`: this endpoint responds with `firstIncomingItem` because
    # exactly one decision is adjudicated per request (D-24).
    if not isinstance(payload, dict):
        return _unavailable("unrecognized_response_shape")

    would_write = payload.get("would_write")
    return {
        "available": True,
        "reason": None,
        "outcome": payload.get("outcome"),
        "message": payload.get("message"),
        "would_write": would_write if isinstance(would_write, dict) else {},
        "verified_properties": payload.get("verified_properties"),
        "verified": payload.get("verified"),
    }


def preview_decision(config, object_type, record_id, decision, reason, transport=requests):
    """The dry run: what the backend WOULD write, without writing it (D-03, D-05).

    Deliberately NOT gated on grant-authorization and not on the session arm. A dry run
    writes nothing, and if the operator cannot see the patch they cannot approve it —
    gating the preview would remove the display the arm exists to protect.

    `would_write` on an approval is a MULTI-key patch: the class-filtered canonical fields,
    reviewApply's clear patch, and a `lv_enrichment_provenance` JSON blob that can run to
    kilobytes. A rejection's is exactly one key (D-30).
    """
    body = _request_body(object_type, record_id, decision, reason, None, True)
    return _post_decision(config, body, transport)


def submit_decision(config, object_type, record_id, decision, reason, reviewed_by,
                    review_armed, grant=None, preview=None, transport=requests):
    """Send the decision for real — only when grant-authorization AND the session arm are
    open (D-60-04, Phase 60).

    Gate 1 is checked first and before anything else, so a missing/out-of-scope grant
    leaves the transport's call log EMPTY — the same property `ALLOW_REVIEW_SUBMIT` used to
    guarantee, now delivered by `write_grant.authorize_send` instead of an environment
    variable. An un-doing decision (`is_undoing`) skips gate 1 by design (D-60-07): a closed
    authority must never be able to strand a flagged record mid-decision. What this
    guarantees is that the request is SUBMITTED, never that it LANDS — the deployed gate
    checks its own record allowlist before it branches on approve-vs-reject, so an ungranted
    reject with no armed window still reaches the POST and still comes back
    `not_allowlisted` (cross-AI review, MEDIUM-3, 2026-09-01). That is not a regression: the
    retired `ALLOW_REVIEW_SUBMIT` carve-out was equally client-side, no weaker than this one.

    `grant` defaults to `None`, matching every other lane's grant-optional call sites: with
    no grant open, `write_grant.authorize_send` reports `armed=False` and this function
    refuses with `GRANT_REFUSAL_REASON`, restating whatever `authorize_send`'s own `detail`
    says (so an out-of-scope record names itself rather than being reworded here).

    `review_armed` (gate 2) has no default — the arm arrives from the conversation as an
    explicit argument and is never read from or written to a file, a cache, or module
    state. Unchanged by this function's grant-authorization gate.

    `preview` is the envelope `preview_decision` already returned, used only so a refused
    submit can restate the exact write the operator was looking at. Nothing is fetched to
    populate it: a refused submit performs NO call of any kind.
    """
    if not is_undoing(decision):
        # Imported inside the function body — this module's house style for avoiding an
        # import cycle (see n8n_arming.py's own `import write_grant` inside
        # `arm_for_dispatch`); write_grant does not import review_decision, but the
        # convention is kept uniform across the plugin's authorization call sites.
        import write_grant
        auth = write_grant.authorize_send(
            grant, lane=write_grant.REVIEW_LANE, record_ids=[str(record_id)],
            record_domains=[])
        if not auth.get("armed"):
            return _unavailable(GRANT_REFUSAL_REASON,
                                message=auth.get("detail") or _GRANT_REFUSAL,
                                would_write=(preview or {}).get("would_write"))

    if not review_armed:
        return _unavailable("not_armed", message=_NOT_ARMED_REFUSAL,
                            would_write=(preview or {}).get("would_write"))

    body = _request_body(object_type, record_id, decision, reason, reviewed_by, False)
    return _post_decision(config, body, transport)


def _verdict(status, response, message, mismatched=None) -> dict:
    return {"status": status, "outcome": response.get("outcome"),
            "message": message, "mismatched": list(mismatched or [])}


def verify_decision(intended, response) -> dict:
    """Did the write land? Decided by comparing an INDEPENDENT re-read, never a status code.

    `intended` is the `would_write` map the operator approved. `response["verified_properties"]`
    is 30-02's post-PATCH refetch — a second HubSpot search issued after the PATCH, not the
    PATCH's own echo (D-19). Comparing a write against its own echo proves the request was
    well-formed and nothing else, which is precisely the "an accepted response is not
    evidence" failure Phase 28 D-14 exists to prevent.

    The comparison is re-derived here rather than read from the response's own `verified`
    field. That field is a convenience and never the authority; nothing in this module may
    default it to true.

    Returns `{status, outcome, message, mismatched}` where status is:
      - `verified`     — every approved key reads back with the approved value
      - `failed`       — a mismatch, an unreadable read-back, or no usable response at all
      - `not_written`  — the endpoint's own non-writing outcome, surfaced with its message

    A written decision arriving with `verified_properties` absent or null is **failed**. An
    unverifiable write is not a verified one.
    """
    intended = intended if isinstance(intended, dict) else {}
    response = response if isinstance(response, dict) else {}

    if not response.get("available"):
        reason = response.get("reason") or "no_response"
        # `unparseable_response` / `no_response` (Phase 31 Plan 02, 2026-08-03, BUG 30):
        # these two reasons mean the WORKFLOW ITSELF failed to answer, not that the record
        # was refused — a genuine allowlist drop now comes back as `not_allowlisted`
        # instead. Point at n8n execution history, never at TEST_RECORD_IDS. Every other
        # reason keeps the generic wording; nothing here interpolates a header, secret, or
        # transport exception text.
        if reason in ("unparseable_response", "no_response"):
            unavailable_message = (
                "The decision could not be confirmed: the backend answered with "
                f"`{reason}`. This means the workflow itself failed to run to completion — "
                "it is NOT the allowlist; a record that is genuinely not on the allowlist "
                "now comes back as `not_allowlisted` instead. Check n8n execution history "
                "for the failing node and its error. Nothing here proves whether a write "
                "landed, so treat it as not landed and check the record in HubSpot before "
                "deciding again."
            )
        else:
            unavailable_message = (
                "The decision could not be confirmed: the backend answered with "
                f"`{reason}`. Nothing here proves whether a write landed, so treat it as "
                "not landed and check the record in HubSpot before deciding again."
            )
        return _verdict("failed", response, response.get("message") or unavailable_message)

    outcome = response.get("outcome")
    endpoint_message = response.get("message")

    if outcome in NON_WRITING_OUTCOMES:
        return _verdict("not_written", response,
                        endpoint_message or f"The backend returned `{outcome}` and wrote nothing.")

    if outcome not in WRITING_OUTCOMES:
        return _verdict(
            "failed", response,
            f"The backend returned an outcome this client does not recognise: {outcome!r}. "
            "Nothing about it can be read as a completed write.",
        )

    if not intended:
        return _verdict(
            "failed", response,
            f"The backend reported `{outcome}` but there is no approved write to compare "
            "against, so nothing can be confirmed.",
        )

    properties = response.get("verified_properties")
    if not isinstance(properties, dict):
        return _verdict(
            "failed", response,
            f"The backend reported `{outcome}` but the record could not be read back "
            "afterwards, so the write is unconfirmed. An unconfirmed write is not a "
            "completed one — check the record in HubSpot.",
        )

    # HubSpot stores and returns every property as a string, so compare stringwise: a
    # boolean or numeric intent must not read as a mismatch against its own stored form.
    mismatched = [key for key in intended
                  if str(properties.get(key)) != str(intended[key])]

    if mismatched:
        return _verdict(
            "failed", response,
            f"The backend reported `{outcome}`, but re-reading the record shows "
            f"{len(mismatched)} field(s) did not take the approved value: "
            f"{', '.join(sorted(mismatched))}. Nothing further was written.",
            mismatched,
        )

    return _verdict(
        "verified", response,
        f"Confirmed: the record was re-read after the write and all "
        f"{len(intended)} field(s) hold the approved values.",
    )


if __name__ == "__main__":
    # Diagnostic only (D-60-04): reports the grant-gate contract, not a live gate state —
    # whether a decision goes through depends on a grant handed in from the conversation,
    # not on anything this process can read on its own. It never sends anything, and it
    # never prints a secret or a config value.
    print(json.dumps({
        "ok": True,
        "gate_1": "grant-authorization via write_grant.authorize_send(lane='review', ...)",
        "grant_refusal_reason": GRANT_REFUSAL_REASON,
        "note": ("Submitting a review decision (other than a reject) needs an open write "
                 "grant covering this record, the session arm (review_armed), and the "
                 "backend's own ALLOW_HUBSPOT_REVIEW_WRITES allowlist. A reject bypasses "
                 "the grant check but still needs the session arm."),
    }))
