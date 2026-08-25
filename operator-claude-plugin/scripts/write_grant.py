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

4. **Opening a grant is deliberately NOT in `control_actions.ACTION_KINDS`** (53-03). A
   reader comparing the two surfaces will notice a second confirmation gate here and
   wonder why it is not one gate in one place. `ACTION_KINDS` is the allowlist
   `execute_action` checks, and `execute_action` is documented as the only MUTATING path;
   opening a grant reads, computes and returns — it mutates nothing. Putting a read-only
   action on a mutation allowlist blurs the same capability-versus-authorization
   distinction D-53-01 keeps the settings key out of `CAPABILITY_KEYS` for. The cost is
   two confirmation gates, and it is paid by pinning them BEHAVIOURALLY: one shared
   near-miss list is driven through both `execute_action` and `open_grant`
   (`test_write_grant.py`, 53-01 Task 2), never a source-text pin.
"""
import copy
from datetime import date, datetime, timezone

import chunking
import config_gate
import cost_guard
import executions_client
import n8n_arming
import n8n_read
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


# ------------------------------------------------------------- GRANT-02: the envelope
#
# THE ENVELOPE DISCLOSES; IT DOES NOT CONSTRAIN (D-53-02, operator, 2026-08-25).
#
# The figures below are computed FROM the batch, so they cannot refuse the batch: a
# ceiling derived from what was named can never block anything that naming already
# implies. Recorded here, and stated in the operator-facing block itself, because a
# number labelled "ceiling" reads as a guard, and an operator who believes a guard is
# watching stops watching. The refuse-before-starting check — the projection compared
# against what is LEFT of the monthly execution allowance, not against the plan's
# configured allowance — is Phase 57's, and it is the only thing that will actually
# stand between a large batch and the execution budget.
#
# No second cost model is built here. `cost_guard` is dated, measured, deliberately
# over-stating (Lusha at its first-time rate, never its measured-zero re-enrich rate) and
# tri-state about readability. A second estimator would drift from it silently.

MEASURED = "measured"
PROJECTED = "projected"
UNCONFIGURED = "unconfigured"

# One webhook execution per chunk, plus one sub-execution per record. This follows from
# the enrichment workflow having no batching node (see `max_records_per_chunk`'s own
# provenance note in operator.local.example.json: every record in one POST runs the full
# provider + Haiku + Sonnet chain), but nobody has COUNTED executions for a multi-chunk
# grant end to end. It is therefore labelled PROJECTED everywhere it appears, and the
# figure it is labelled against is what the plan allows per month, never what is left of
# it this month.
EXECUTIONS_BASIS = (
    "1 webhook execution per chunk + 1 sub-execution per record (the enrichment "
    "workflow has no batching node, so it fans out per record)")

_ALLOWANCE_GAP = (
    "This projection is against the plan's CONFIGURED monthly execution allowance, not "
    "against what is left of it this month. n8n exposes no usage endpoint to an API key, "
    "so the remainder is sampled rather than read, and sampling it is not built yet — "
    "the schedulers have already spent an unknown share of this month's allowance and "
    "none of it is subtracted below.")

_DISCLOSURE_NOT_CONSTRAINT = (
    "These figures are this grant's ceiling, and they describe what this batch can cost "
    "— they do not prevent it. The ceiling is computed FROM the batch you named, so it "
    "cannot block anything that batch already implies. If you want a smaller ceiling, "
    "name a smaller batch.")


def _usd(value):
    return f"${value:.2f}" if isinstance(value, (int, float)) else "unknown"


def _credits(value):
    if not isinstance(value, (int, float)):
        return "unknown"
    return f"{value:g}"


def _headroom(verdict):
    """The tri-state, rendered. `unknown` is its own answer and never reads as headroom."""
    state = (verdict or {}).get("verdict")
    if state == "ok":
        return "ok"
    if state == "insufficient":
        return "NOT ENOUGH"
    return "unconfirmed"


def _post_transport(transport):
    if transport is None:
        return None
    return transport.post if hasattr(transport, "post") else transport


def envelope(config, *, object_type, record_ids, record_domains, providers,
             transport=None, today=None):
    """The arithmetic an operator reads BEFORE the yes (GRANT-02).

    Returns `{figures..., "block": <markdown>}`. Every figure carries its basis in
    `basis`: `measured` for anything read off the dated rate table times a counted
    record set, `projected` for the execution count, `unconfigured` for a figure a
    missing config key made unavailable.

    A missing allowance key degrades ONE line. A missing chunk ceiling degrades the
    execution projection only — `chunking.chunk_ceiling` refuses to guess a bound that is
    a real timeout constraint, and that refusal belongs to the dispatch, not to a
    projection. Neither takes the whole grant down with it: an operator refused a grant
    because a projection line could not be computed learns nothing and can act on
    nothing.
    """
    ids = _normalise(record_ids)
    domains = _normalise(record_domains)
    # Worst case, deliberately: a grant naming 3 ids and 2 domains is priced as 5
    # records, because nothing here can prove the domains are not five more companies.
    record_count = len(ids) + len(domains)
    providers = sorted({str(p).strip().lower() for p in (providers or []) if str(p).strip()})

    rates = cost_guard.load_rates()
    estimate = cost_guard.estimate_batch(record_count, object_type, providers, rates)

    balances = {}
    if estimate.get("provider_credits"):
        post = _post_transport(transport)
        balances = cost_guard.fetch_balances(
            config, **({} if post is None else {"transport": post}))
    verdicts = cost_guard.compare(estimate, balances)

    reference = today if today is not None else date.today()
    try:
        age_days = cost_guard.rate_table_age_days(rates, reference)
    except (ValueError, TypeError, KeyError):
        age_days = None

    # Chunk arithmetic depends only on HOW MANY records there are, so the projection
    # reuses the very plan dispatch will build rather than re-deriving a ceil() that
    # could drift from it.
    chunk_count = None
    ceiling = None
    executions = None
    executions_basis = PROJECTED
    try:
        ceiling = chunking.chunk_ceiling(config)
        chunk_count = chunking.plan_chunks(
            {"record_ids": ids + domains, "object_type": object_type},
            ceiling).chunk_count
        executions = chunk_count + record_count
    except chunking.ChunkPlanError:
        executions_basis = UNCONFIGURED

    allowance = (config or {}).get(n8n_read.EXECUTION_ALLOWANCE_KEY)
    allowance_configured = isinstance(allowance, int) and not isinstance(allowance, bool) \
        and allowance > 0
    if not allowance_configured:
        allowance = None

    figures = {
        "record_count": record_count,
        "object_type": object_type,
        "providers": providers,
        "provider_credits": estimate.get("provider_credits") or {},
        "verdicts": verdicts,
        "anthropic_usd": estimate.get("anthropic_usd"),
        "anthropic_usd_per_record": estimate.get("anthropic_usd_per_record"),
        "rates_version": estimate.get("rates_version"),
        "rates_measured_on": estimate.get("rates_measured_on"),
        "rate_table_age_days": age_days,
        "chunk_ceiling": ceiling,
        "chunk_count": chunk_count,
        "projected_executions": executions,
        "executions_projection_basis": EXECUTIONS_BASIS,
        "monthly_execution_allowance": allowance,
        "allowance_configured": allowance_configured,
        "remaining_allowance_sampled": False,
        "basis": {
            "record_count": MEASURED,
            "provider_credits": MEASURED,
            "anthropic_usd": MEASURED,
            "projected_executions": executions_basis,
            "monthly_execution_allowance": (
                MEASURED if allowance_configured else UNCONFIGURED),
        },
    }
    figures["block"] = _envelope_block(figures)
    return figures


def _envelope_block(figures):
    """The envelope in the register `preview_enrichment.cost_block` already established:
    a dated rate line, one table row per provider with its tri-state headroom, then the
    two sentences an operator must not have to infer."""
    measured_on = figures.get("rates_measured_on")
    age = figures.get("rate_table_age_days")
    age_text = f", {age} days ago" if isinstance(age, int) else ""

    lines = [
        "**What this grant can cost — at most.**",
        "",
        f"**Records:** {figures['record_count']} "
        f"{figures.get('object_type') or 'record(s)'}, named by this grant and by nothing "
        f"else.",
    ]
    if measured_on:
        lines.append(
            f"Rates measured **{measured_on}**{age_text}. Lusha is priced at its "
            f"first-time rate, never its measured-zero re-enrich rate, so these figures "
            f"over-state rather than under-state.")

    credits = figures.get("provider_credits") or {}
    if credits:
        lines += ["",
                  "| Provider | Worst-case credits | Credits remaining | Headroom |",
                  "|---|---|---|---|"]
        for provider in sorted(credits):
            verdict = (figures.get("verdicts") or {}).get(provider) or {}
            lines.append(
                f"| {provider} | {_credits(credits[provider].get('credits'))} "
                f"| {_credits(verdict.get('remaining_credits'))} "
                f"| {_headroom(verdict)} |")
    else:
        lines += ["", "No provider credits: **0** — this grant runs no provider."]

    lines += ["", f"Anthropic model spend: **{_usd(figures.get('anthropic_usd'))}** "
                  f"worst case."]

    executions = figures.get("projected_executions")
    if isinstance(executions, int):
        lines.append(
            f"n8n executions: **{executions} (projected, not measured)** — "
            f"{figures['executions_projection_basis']}, at {figures['chunk_count']} "
            f"chunk(s) of at most {figures['chunk_ceiling']} record(s).")
    else:
        lines.append(
            f"n8n executions: **not projected** — `{chunking.CEILING_KEY}` is not set in "
            f"the operator config, so the chunk count is unknown. Every other figure "
            f"above still holds; a dispatch will refuse for the same missing key and say "
            f"so.")

    if figures.get("allowance_configured"):
        lines.append(
            f"Against a configured monthly allowance of "
            f"**{figures['monthly_execution_allowance']}** executions.")
    else:
        lines.append(
            f"Monthly execution allowance: **unconfigured** — "
            f"`{n8n_read.EXECUTION_ALLOWANCE_KEY}` is not set, so there is no figure to "
            f"compare the projection against. That is one missing line, not a reason to "
            f"refuse the grant.")

    lines += ["", _ALLOWANCE_GAP, "", _DISCLOSURE_NOT_CONSTRAINT]
    return "\n".join(lines)


def _consequence(lane_names, ids, domains, allow_create):
    """What turns on, bounded to what, what turns it off, and what happens if turning it
    off fails — the register `control_actions.plan_action` already produces for
    `arm_dispatch` (53-CONTEXT `<specifics>`), extended to a grant.

    EVERY LANE IS NAMED INDIVIDUALLY. Under D-53-05 one grant may span both the
    enrichment and the contacts lanes, and the operator is approving two distinct write
    surfaces — collapsing them into a collective phrase would hide one of them behind the
    other.
    """
    per_lane = " ".join(
        f"On the {lane} lane, live writes will be enabled on {LANES[lane]!r} for this "
        f"grant's records only."
        for lane in lane_names)

    sentence = (
        f"{per_lane} The grant is bounded to exactly {len(ids)} record id(s) and "
        f"{len(domains)} domain(s) — the backend cannot write a record outside that list "
        f"even while a window is open — and "
        f"{'includes' if allow_create else 'excludes'} creation of new records. "
        f"Each send still opens and closes its OWN armed window, so writes turn off "
        f"between sends; closing the grant ends the authority to open another. If a "
        f"disarm fails, that send is reported as a disarm failure rather than assumed "
        f"clean; one failure fails that send only, a second consecutive failure closes "
        f"the grant, and an admin must check n8n.")

    if len(lane_names) > 1:
        # D-53-05's traded protection, stated at the yes — the last place it can be
        # stated. 37-CONTEXT §6.3 held the enriched preview as strictly preceding the
        # ingest arm precisely so held rows and merge conflicts were visible before the
        # write was approved. This grant approves both lanes at once, so it is approved
        # BEFORE that preview exists, and the operator reads that here or nowhere.
        sentence += (
            " This grant covers both lanes at once, which means the HubSpot write is "
            "authorized BEFORE the enriched preview exists — held rows and merge "
            "conflicts that the enriched preview is the only place to see ahead of a "
            "write are authorized unseen. The preview is still rendered, and the record "
            "set is unchanged; what moved is WHEN you approved it, not WHAT it covers.")
    return sentence


def plan_grant(config, *, lanes, object_type, record_ids, record_domains, allow_create,
               label, providers=None, transport=None, preflight=None, today=None):
    """Compose a PROPOSAL for a write grant. Reads only — never mutates anything.

    Refuses, in this order and before returning anything: an unauthorized config, an
    unknown lane, an empty record set, a lane whose workflow cannot be resolved by name.

    `providers` is the resolved provider selection the envelope is priced against;
    `None` means the configured selection in `enrichment_providers`, the same default
    every other lane in this plugin resolves to.

    `preflight` IS GUARDRAIL A, and it is not optional. `None` means the real one; a
    caller may substitute another callable (a test does), but a non-callable value is a
    TypeError rather than a skipped check. There is no config key, environment variable
    or phrase that turns it off — an off switch on a guardrail is the guardrail's absence
    with extra steps (T-53-12). It is invoked with `(config, workflow_ids, transport)` and
    its refusal is returned with the envelope attached.

    CALL ORDER, frozen because every scripted test depends on it: the cheap refusals
    (authority, lanes, record set) cost nothing; then one workflow-collection GET per
    lane to resolve ids; then ONE status POST for provider balances, and only when the
    batch actually prices a provider; then one workflow GET per lane for guardrail A.
    The envelope is computed BEFORE guardrail A so that a refused open still tells the
    operator what the batch would have cost.
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

    figures = envelope(
        config, object_type=object_type, record_ids=ids, record_domains=domains,
        providers=providers if providers is not None
        else (config or {}).get("enrichment_providers"),
        transport=transport, today=today)

    preflight = guardrail_a if preflight is None else preflight
    if not callable(preflight):
        raise TypeError(
            "guardrail A is not optional: `preflight` must be callable. Passing a "
            "non-callable would make the live write-safety read skippable by argument, "
            "which is the toggle this guardrail may not have.")
    blocked = preflight(config, workflow_ids, transport)
    if blocked:
        # The envelope rides along on the refusal: an operator who is refused still
        # learns what the batch would have cost, and can act on the refusal without
        # re-planning to find out.
        return {**blocked, "envelope": figures}

    return {
        "kind": PROPOSAL_KIND,
        "lanes": lane_names,
        "workflow_ids": workflow_ids,
        "object_type": object_type,
        "record_ids": ids,
        "record_domains": domains,
        "allow_create": bool(allow_create),
        "label": label,
        # The arithmetic shown BEFORE the yes (GRANT-02/D-53-02). `open_grant` deep-copies
        # the proposal, so what was shown and what the grant is bound to are one object.
        "envelope": figures,
        "consequence": _consequence(lane_names, ids, domains, allow_create),
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
    # Every refusal below carries the proposal's envelope when there is one, so an
    # operator who is refused still reads what the batch would have cost.
    shown = {"envelope": proposal["envelope"]} if (
        isinstance(proposal, dict) and proposal.get("envelope")) else {}

    if not config_gate.write_grants_enabled(config):
        return _refusal(
            f"opening a write grant needs {config_gate.WRITE_GRANT_SETTINGS_KEY!r} set to "
            f"true in operator.local.json, which is not configured. Your n8n admin sets "
            f"it. Nothing was opened.", **shown)

    if confirmation != "yes":
        return _refusal(
            "not confirmed — no grant was opened. To go ahead, confirm with an explicit "
            "yes after reading what the grant covers.", **shown)

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
    if reason not in CLOSE_REASONS:
        raise ValueError(
            f"{reason!r} is not a close reason this system can report on. A grant closes "
            f"for one of: {', '.join(sorted(CLOSE_REASONS))}. GRANT-04 requires each "
            f"expiry to be REPORTED, and a free-text reason is one nobody can report on.")

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


# --------------------------------------------- GRANT-04/GRANT-05: lifetime and revocation
#
# THE FIVE WAYS A GRANT ENDS (GRANT-04). Named constants, not free text: a close reason
# that can be anything is a close reason nobody can report on, and GRANT-04 requires each
# expiry to be REPORTED, which means each has to be recognisable.
CLOSED_BATCH_COMPLETE = "batch_complete"
CLOSED_CEILING_BREACH = "ceiling_breach"
CLOSED_REVOKED = "operator_revocation"
CLOSED_SESSION_END = "session_end"
CLOSED_UNHANDLED_ERROR = "unhandled_error"

GRANT_04_REASONS = frozenset({
    CLOSED_BATCH_COMPLETE, CLOSED_CEILING_BREACH, CLOSED_REVOKED,
    CLOSED_SESSION_END, CLOSED_UNHANDLED_ERROR,
})

# Guardrail B's own close reasons (53-02 Task 3). They are NOT folded into one of the five
# above: "two consecutive disarm failures" is not batch completion, not a ceiling breach,
# not a revocation, not a session end, and not an unhandled error — nothing raised. Folding
# it into one of those would misreport the one close the operator most needs to read
# correctly. GRANT_04_REASONS stays exactly five and is pinned by name.
GUARDRAIL_B_REASONS = frozenset()

CLOSE_REASONS = GRANT_04_REASONS | GUARDRAIL_B_REASONS

# WHERE GRANT-04'S "each expiry disarms the backend" ACTUALLY BITES.
#
# On batch completion, revocation and session end it is VACUOUSLY satisfied: every send
# opens and closes its own `n8n_arming.armed_window`, so at close time there is no window
# open to disarm. `close_grant` therefore makes no call, and that is a consequence of the
# per-send design rather than a skipped step.
#
# The two paths where it is NOT vacuous are guardrail B's, and both of those DO attempt a
# disarm (Task 3): each closes having just observed live writes or having twice failed to
# turn them off, which is exactly when walking away would leave a live record-scoped
# allowlist behind.
#
# SESSION END AND UNHANDLED ERROR ARE CALLER-MADE CLOSES, AND THERE IS NO PROCESS TO MAKE
# THEM FOR A SESSION THAT DIES MID-TURN. That is D-53-03's accepted risk, put to the
# operator on 2026-08-25 and accepted after the alternative (an expiry inside the shared
# write-safety gate) was offered and declined. The thing that catches the case where nobody
# made the call is GUARDRAIL A: the next session's plan reads the live write-safety state
# and refuses to open over an armed backend. A reader who cannot connect those two will
# read this gap as an oversight; it is a designed one with a named counterpart.


def revoke_grant(grant):
    """Operator revocation, reachable by the name a request maps onto (GRANT-05). Returns
    a closed COPY — the caller replaces its handle.

    WHAT REVOCATION BUYS, AND WHAT IT DOES NOT (GRANT-05, re-scoped by the operator
    2026-08-25 from "within one chunk boundary" to "at the next SEND").

    It refuses the NEXT SEND. `chunking.dispatch_plan` loops over every chunk of an
    approved plan internally and never consults a grant; there is no per-chunk hook and
    none is added here, because adding one changes the shared dispatch loop every lane in
    this plugin uses. So a dispatch already running COMPLETES ITS REMAINING CHUNKS under
    the arm it opened with. At the shipped `max_records_per_chunk` of 2, a 40-record send
    is 20 chunks, and a revoke arriving at chunk three stops none of them.

    That is a real reduction in what a revoke is worth, it is tested rather than claimed
    away (`test_a_revocation_midway_does_not_stop_a_running_dispatch`), and anyone who
    needs chunk-granular revocation has to make `dispatch_plan` grant-aware first.

    IDEMPOTENT, AND REASON-PRESERVING BECAUSE OF IT. An operator who says stop twice has
    not made a mistake, so an already-closed grant comes back unchanged rather than
    raising. Returning it UNCHANGED rather than re-closing it is the load-bearing half:
    `close_grant` does not inspect state, so a plain re-close would overwrite
    `closed_reason` — and a grant that guardrail B closed for
    `two_consecutive_disarm_failures` re-reading as `operator_revocation` would misreport
    the one close the operator most needs to read correctly, which is exactly the
    confusion 53-02 gave guardrail B its own reason set to prevent.
    """
    if isinstance(grant, dict) and grant.get("state") == CLOSED:
        return grant
    return close_grant(grant, CLOSED_REVOKED)


# The wave-2 name, kept so callers written against it keep working. One implementation:
# `revoke_grant` is the operator-facing name 53-03 added because GRANT-05 asks for
# revocation to be REACHABLE, and a reachable thing needs a name a request maps onto.
revoke = revoke_grant


def check_before_send(grant, *, lane=None, workflow_id, record_ids, record_domains):
    """The ONE question every send asks: may this send go? None, or a refusal.

    Composes the state check and the scope check (`covers`) so there is exactly one place
    a send is refused and exactly one wording for each refusal. A closed grant refuses and
    names the reason it closed; an open grant whose record set does not cover the send
    refuses and names the offending ids and domains.
    """
    return covers(grant, lane=lane, workflow_id=workflow_id,
                  record_ids=record_ids, record_domains=record_domains)


def record_send_outcome(grant, outcome, config=None, *, transport=None):
    """Fold one send's result into the grant. Returns a new grant; never mutates.

    `outcome` is a dict a send composes. Two keys are read and both are optional:

    * `disarm` — `n8n_arming.disarm`'s result (or an `armed_window`'s `disarm_result`).
      A verified disarm RESETS `consecutive_disarm_failures` to zero; a
      `disarm_failed` increments it. An outcome carrying no disarm verdict leaves the
      counter alone: there is no verdict to read, and inventing one in either direction
      is worse than carrying the unknown forward.
    * `ceiling_breach` — truthy closes the grant rather than continuing. Nothing in this
      phase MEASURES spend as it happens, so this reason has no producer here and is
      reached only by a caller that supplies it; Phase 57 is what makes it fire on its
      own. Named now so its emptiness is deliberate rather than a missed wire.

    ONE FAILED DISARM FAILS THAT SEND ONLY and the session continues (D-53-04, chosen
    deliberately so a transient blip does not abort a long run). The bound is on the
    SECOND — 53-02 Task 3 adds it on top of this counter.

    Pure, and returns a new dict, because the grant round-trips through the conversation
    between turns: any state that mutates in place is state that is lost. `config` and
    `transport` are here for the closing disarm Task 3 performs.
    """
    updated = copy.deepcopy(grant if isinstance(grant, dict) else {})
    outcome = outcome if isinstance(outcome, dict) else {}

    verdict = (outcome.get("disarm") or {}).get("outcome")
    if verdict == n8n_arming.DISARMED:
        updated["consecutive_disarm_failures"] = 0
    elif verdict == n8n_arming.DISARM_FAILED:
        updated["consecutive_disarm_failures"] = \
            int(updated.get("consecutive_disarm_failures") or 0) + 1

    if outcome.get("ceiling_breach"):
        return close_grant(updated, CLOSED_CEILING_BREACH)

    # GUARDRAIL B, path 1 (D-53-04): the SECOND consecutive disarm failure closes the
    # grant. The first does not — a transient blip must not abort a long run — but an
    # unbounded march of writes over a backend nobody can confirm is disarmed must not be
    # possible either. That is the whole distinction, and it is why the bound is on 2.
    #
    # The close ATTEMPTS a disarm because this path has now failed twice to turn writes
    # off: closing and walking away would leave a live record-scoped allowlist behind at
    # exactly the moment the system knows one is there.
    if updated["consecutive_disarm_failures"] >= 2:
        failed_on = (outcome.get("disarm") or {}).get("workflow_id")
        return _close_with_disarm(
            updated, CLOSED_DISARM_UNCONFIRMED, config,
            [failed_on] if failed_on else _covered_workflow_ids(updated), transport)

    return updated


# =========================================================================================
# 53-02 Task 3 — THE TWO GUARDRAILS (D-53-03 and D-53-04's proposed defences)
#
# Both were PROPOSED in 53-CONTEXT.md and neither may be assumed away. They are built here
# as working code, and NEITHER IS REACHABLE BY AN ENVIRONMENT VARIABLE, A CONFIG KEY OR A
# PHRASE. An off switch on a guardrail is the guardrail's absence with extra steps.
#
# THE CONTRAST BETWEEN THEM IS DELIBERATE AND ASYMMETRIC, and it lives here so a later edit
# cannot "harmonise" them:
#
#   GUARDRAIL A found a state IT DID NOT CREATE. It names what it found, offers a disarm,
#   and takes none — D-53-03 mandates offer-only. A guardrail that silently repaired the
#   state would remove the evidence that a previous session died armed, and that evidence
#   is the one signal telling the operator the client-held design is costing them.
#
#   GUARDRAIL B is closing a window ITS OWN RUN OPENED and is responsible for. Both of its
#   close paths ATTEMPT a disarm, carry its verdict on the closed grant, and CLOSE EITHER
#   WAY. `n8n_arming.disarm` is ungated by design, so this adds no authority anywhere.
# =========================================================================================

# The two flags that actually enable a write. TEST_RECORD_IDS / TEST_RECORD_DOMAINS bound a
# write that is already enabled; they cannot enable one on their own (the deployed
# `_writeSafetyAllows` denies everything on an empty allowlist), so they are REPORTED by
# guardrail A rather than treated as an armed state.
WRITE_ENABLING_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")

CLOSED_DISARM_UNCONFIRMED = "two_consecutive_disarm_failures"
CLOSED_WRITES_STILL_LIVE = "writes_still_live_at_next_send"

GUARDRAIL_B_REASONS = frozenset({CLOSED_DISARM_UNCONFIRMED, CLOSED_WRITES_STILL_LIVE})
CLOSE_REASONS = GRANT_04_REASONS | GUARDRAIL_B_REASONS


def _enabled(value):
    """A declaration reads ENABLED. Compared as text because the declaration is a JS
    literal read back out of the deployed workflow, where `true` and `"true"` are both
    what an arm can leave behind."""
    return str(value).strip().strip('"').strip("'").lower() == "true"


def read_live_write_state(config, workflow_ids, transport=None):
    """What the LIVE workflows say about writes right now, one read per covered lane.

    Reads through `n8n_read.get_workflow` + `n8n_read.read_write_safety` over
    `n8n_arming.DISPATCH_FLAGS` — the shipped reader, never a second declaration regex.

    This is NOT a call into `status.describe_workflow`, and that is not duplication:
    `describe_workflow` reads only two of the four dispatch flags and returns no
    allowlists, while a refusal an operator can act on has to name the allowlist that is
    currently in force. Narrow read, on purpose.

    Returns `{lane: {workflow_id, workflow_name, readable, flags, disagreements}}`.
    """
    import requests as _requests
    transport = transport if transport is not None else _requests
    get_transport = transport.get if hasattr(transport, "get") else transport

    state = {}
    for lane, workflow_id in (workflow_ids or {}).items():
        body = n8n_read.get_workflow(config, workflow_id, transport=get_transport)
        if not isinstance(body, dict):
            state[lane] = {"workflow_id": workflow_id, "workflow_name": None,
                           "readable": False, "flags": {}, "disagreements": {}}
            continue

        flags = {}
        disagreements = {}
        for flag in n8n_arming.DISPATCH_FLAGS:
            reading = n8n_read.read_write_safety(body, flag)
            flags[flag] = reading.get("value")
            if reading.get("disagreement"):
                disagreements[flag] = reading["nodes"]

        readable = all(flags.get(flag) is not None for flag in WRITE_ENABLING_FLAGS)
        state[lane] = {"workflow_id": workflow_id, "workflow_name": body.get("name"),
                       "readable": readable, "flags": flags,
                       "disagreements": disagreements}
    return state


def _live_write_faults(state):
    """The three states that refuse an open, per lane. Order is presentation only — a lane
    can be in more than one."""
    faults = {}
    for lane, reading in (state or {}).items():
        why = []
        if not reading.get("readable"):
            # THE ONE A HURRIED IMPLEMENTATION GETS WRONG. An unreadable write-safety state
            # is not evidence of a disarmed backend, and this guardrail exists precisely
            # for the case where something is already wrong.
            why.append("its write-safety state could not be read at all")
        if reading.get("disagreements"):
            why.append("its declaring nodes disagree with each other")
        live = [flag for flag in WRITE_ENABLING_FLAGS
                if _enabled((reading.get("flags") or {}).get(flag))]
        if live:
            why.append(f"{', '.join(live)} reads enabled")
        if why:
            faults[lane] = {"reasons": why, "live_flags": live, **reading}
    return faults


def guardrail_a(config, workflow_ids, transport=None):
    """GUARDRAIL A (D-53-03): refuse to plan a grant over a backend where writes are
    already live — or where nobody can tell. None when the open may proceed.

    WHAT THIS PROVES AND WHAT IT DOES NOT. It proves that at THIS plan, on the lanes this
    grant covers, live writes were off and readable. It proves nothing about a session
    that died between an arm and a disarm inside the same turn and was then cleaned up by
    something else, and it cannot see a lane this grant does not name (a backend armed on
    some other workflow stays unnoticed — widening it to every workflow the API key can
    see would train the operator to override refusals citing unrelated work). It is the
    only cheap defence available under a client-held grant, and D-53-03 recorded that
    plainly when the alternative was offered and declined.

    IT NEVER DISARMS. It names what it found and offers the disarm as the operator's next
    step. Turning D-53-03's accepted risk from silent into loud is the whole job; a
    guardrail that quietly repaired the state would destroy the evidence.
    """
    state = read_live_write_state(config, workflow_ids, transport)
    faults = _live_write_faults(state)
    if not faults:
        return None

    lines = []
    for lane, fault in sorted(faults.items()):
        flags = fault.get("flags") or {}
        lines.append(
            f"[{lane}] {fault.get('workflow_name') or 'unnamed workflow'} "
            f"({fault.get('workflow_id')}): {'; '.join(fault['reasons'])}. "
            f"Flags read: "
            f"{', '.join(f'{flag}={flags.get(flag)!r}' for flag in n8n_arming.DISPATCH_FLAGS)}."
            f" Records currently allowlisted: "
            f"ids={flags.get('TEST_RECORD_IDS')!r}, "
            f"domains={flags.get('TEST_RECORD_DOMAINS')!r}.")

    return _refusal(
        "refusing to open a write grant: this backend is not in a known-disarmed state. "
        + " ".join(lines)
        + " I have NOT changed anything. A previous session may have ended without "
          "disarming, which is exactly what this check exists to make visible. Your next "
          "step, if you recognise this state as stale: ask me to disarm those workflows, "
          "then plan the grant again. If you do not recognise it, an admin should look at "
          "n8n before anything else writes.",
        guardrail="A", live_write_state=state, faults=faults,
        offered_action="disarm")


# ------------------------------------------------------------------------- GUARDRAIL B


def _close_with_disarm(grant, reason, config, workflow_ids, transport=None):
    """Close a grant AND attempt to disarm the workflows it may have left live.

    THE CLOSE HAPPENS EITHER WAY. A failed closing disarm must never be a reason to leave
    the grant open — that would let the run continue over exactly the state that triggered
    the guardrail. The verdict rides on the closed grant under `closing_disarm` so the
    operator reads whether it worked.

    `n8n_arming.disarm` is ungated by design (a kill switch that blocked disarming would
    strand an armed backend), so closing with a disarm adds no new authority anywhere.
    """
    verdicts = []
    for workflow_id in workflow_ids or []:
        try:
            result = n8n_arming.disarm(workflow_id, config, transport=transport)
            verdicts.append({"workflow_id": workflow_id,
                             "outcome": result.get("outcome"),
                             "detail": result.get("detail")})
        except Exception as failure:      # noqa: BLE001 — the close must survive anything
            verdicts.append({"workflow_id": workflow_id,
                             "outcome": n8n_arming.DISARM_FAILED,
                             "detail": f"the disarm raised: {type(failure).__name__}"})

    closed = close_grant(grant, reason)
    closed["closing_disarm"] = verdicts
    closed["closing_disarm_verified"] = bool(verdicts) and all(
        v["outcome"] == n8n_arming.DISARMED for v in verdicts)
    return closed


def _covered_workflow_ids(grant, lane=None):
    ids = (grant or {}).get("workflow_ids") or {}
    if lane is not None and lane in ids:
        return [ids[lane]]
    return list(ids.values())


def preflight_before_send(grant, config, lane, transport=None):
    """GUARDRAIL B, path 2: read the lane's live write state BEFORE a send.

    Writes still live means the previous window's disarm did not take, whatever the
    failure counter reads — so the grant closes, a disarm is ATTEMPTED, its verdict is
    carried, and that send is refused. Returns `(grant, refusal_or_None)`; the caller
    replaces its handle with the returned grant either way.

    An unreadable or disagreeing state does NOT close here. Guardrail A refuses at the
    open for that, where refusing costs nothing; mid-run, a single unreadable read is more
    likely a transient API blip than a live-write state, and D-53-04's whole point is that
    a blip must not abort a long run. Only an actually-live write closes.
    """
    granted = (grant or {}).get("workflow_ids") or {}
    workflow_ids = {lane: granted[lane]} if lane in granted else {}

    state = read_live_write_state(config, workflow_ids, transport)
    live = {name: reading for name, reading in state.items()
            if any(_enabled((reading.get("flags") or {}).get(flag))
                   for flag in WRITE_ENABLING_FLAGS)}
    if not live:
        return grant, None

    closed = _close_with_disarm(grant, CLOSED_WRITES_STILL_LIVE, config,
                                [r["workflow_id"] for r in live.values()], transport)
    return closed, _refusal(
        f"refusing this send: a pre-flight read found live writes still enabled on "
        f"{', '.join(sorted(live))}, which means the previous send's disarm did not take. "
        f"The grant is closed and a disarm was attempted — "
        f"{'it verified' if closed['closing_disarm_verified'] else 'IT DID NOT VERIFY, so an admin must check n8n'}. "
        f"Nothing further will be sent under this grant.",
        guardrail="B", live_write_state=state)
