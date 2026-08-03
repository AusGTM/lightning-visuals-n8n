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
import os

import requests

import config_gate

DECISION_PATH = "webhook/hubspot/review/decision"
DEFAULT_TIMEOUT = 30

# The plugin-side kill switch. NOT ALLOW_HUBSPOT_REVIEW_WRITES — see the module docstring.
SUBMIT_ENV_VAR = "ALLOW_REVIEW_SUBMIT"
SUBMIT_ENV_VALUE = "true"

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

# The un-doing decisions the env kill switch must never block (D-16 property (c)). A
# rejection records a reason and leaves the record in the queue — it walks a decision back
# rather than promoting anything.
UNDOING_DECISIONS = ("reject",)

_ENV_REFUSAL = (
    "Review writeback is switched off on this machine: the ALLOW_REVIEW_SUBMIT "
    "environment variable is not set to exactly `true`. Nothing was sent and no request "
    "was even built. Your administrator sets that variable — this plugin cannot set it "
    "and neither can this conversation. Two things still work without it: previewing the "
    "exact write, and rejecting a record, which records your reason and leaves the record "
    "in the queue."
)

_NOT_ARMED_REFUSAL = (
    "Review writeback is off for this conversation — nothing was sent. The write shown is "
    "exactly what would be sent, computed by the backend rather than guessed at here. Say "
    "the review arming phrase to turn review writeback on for this conversation only. "
    "Arming contact dispatch does not arm this, and arming this does not arm that."
)


def decision_target(config: dict) -> str:
    """The endpoint this module POSTs to. Never includes the secret."""
    return f"{str(config.get('n8n_url') or '').rstrip('/')}/{DECISION_PATH}"


def submit_enabled() -> bool:
    """True only when `ALLOW_REVIEW_SUBMIT` reads exactly `true`.

    Every near-miss — unset, `""`, `"1"`, `"yes"`, `"TRUE"`, `"True"` — is False. Same
    semantics as `ALLOW_N8N_ARM` / `ALLOW_N8N_PROBE` / `ALLOW_N8N_DEPLOY`; a divergence
    between them is itself the defect (D-16).
    """
    return os.environ.get(SUBMIT_ENV_VAR) == SUBMIT_ENV_VALUE


def is_undoing(decision) -> bool:
    """True for a decision that walks a record back rather than promoting anything.

    Only these bypass `ALLOW_REVIEW_SUBMIT`. An unrecognised decision word is NOT
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

    Deliberately NOT gated on `ALLOW_REVIEW_SUBMIT` and not on the session arm. A dry run
    writes nothing, and if the operator cannot see the patch they cannot approve it —
    gating the preview would remove the display the arm exists to protect.

    `would_write` on an approval is a MULTI-key patch: the class-filtered canonical fields,
    reviewApply's clear patch, and a `lv_enrichment_provenance` JSON blob that can run to
    kilobytes. A rejection's is exactly one key (D-30).
    """
    body = _request_body(object_type, record_id, decision, reason, None, True)
    return _post_decision(config, body, transport)


def submit_decision(config, object_type, record_id, decision, reason, reviewed_by,
                    review_armed, preview=None, transport=requests):
    """Send the decision for real — only when the env gate AND the session arm are open.

    `ALLOW_REVIEW_SUBMIT` is checked first and before anything else, so an unset variable
    leaves the transport's call log EMPTY (D-16). An un-doing decision skips that check by
    design: a closed kill switch must not be able to strand a record mid-decision.

    `review_armed` has no default — the arm arrives from the conversation as an explicit
    argument and is never read from or written to a file, a cache, or module state.

    `preview` is the envelope `preview_decision` already returned, used only so an unarmed
    refusal can restate the exact write the operator was looking at. Nothing is fetched to
    populate it: an unarmed submit performs NO call of any kind.
    """
    if not is_undoing(decision) and not submit_enabled():
        return _unavailable("submit_not_enabled", message=_ENV_REFUSAL,
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
    # Diagnostic only: reports whether the env kill switch is open. It never sends
    # anything, and it never prints a secret or a config value.
    print(json.dumps({
        "ok": True,
        "env_var": SUBMIT_ENV_VAR,
        "submit_enabled": submit_enabled(),
        "note": ("Submitting a review decision also needs the session arm and the "
                 "backend's own ALLOW_HUBSPOT_REVIEW_WRITES allowlist."),
    }))
