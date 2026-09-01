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
import math
from datetime import date, datetime, timezone

import chunking
import config_gate
import cost_guard
import executions_client
import n8n_arming
import n8n_read
import scheduled_arm
import written_records

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
REVIEW_LANE = "review"
REVIEW_WORKFLOW_NAME = "LV Review Decision (Cloud)"

LANES = {
    "enrichment": scheduled_arm.ENRICHMENT_WORKFLOW_NAME,
    "contacts": executions_client.CONTACT_INGEST_WORKFLOW_NAME,
    REVIEW_LANE: REVIEW_WORKFLOW_NAME,
}

# D-59-07 AMENDMENT (operator, 2026-08-28): the operator-facing HALF of the paragraph
# above -- the sentence `_consequence()` used to render at the yes, saying the HubSpot
# write is authorized before the enriched preview exists -- was retired as
# operator-facing text. The trade recorded above is UNCHANGED: one grant still spans
# both lanes, and the allowlist is still record-scoped to the batch. What changed is
# only what the operator is told in exchange for it: see `_consequence()`'s two-lane
# branch and `written_records.written_records_path()` (59-01 built the artifact,
# 59-03 pointed the disclosure at it). The historical paragraph above is left
# unedited -- it is the code's own record of why the trade was made, and it stays
# readable as that.

# D-60-01/D-60-05 AMENDMENT (operator, 2026-09-01): Phase 60 REVERSES the paragraph
# above -- the review lane's exclusion it describes is no longer true.
# `"review"` is now a third grantable lane (`REVIEW_LANE` / `REVIEW_WORKFLOW_NAME`
# above). The reversal happened because the separation the paragraph describes cost
# TWO manual round trips to close a single flagged record -- an admin setting
# `ALLOW_REVIEW_SUBMIT` in their own shell (which an operator in Claude Desktop cannot
# do) plus a separate admin-run deploy baking `ALLOW_HUBSPOT_REVIEW_WRITES` and the
# record's id into the workflow -- which made the documented operator path
# unreachable from the operator's chair (60-CONTEXT.md D-60-01, mirroring G-2's
# original diagnosis for the dispatch lanes in 53-01). What still holds, unchanged:
# `ALLOW_HUBSPOT_REVIEW_WRITES` stays OUT of `n8n_arming.DISPATCH_FLAGS` -- arming a
# dispatch grant still grants nothing on the review path and vice versa
# (`n8n_arming.REVIEW_FLAGS` is its own separate tuple) -- and a grant's record
# scoping (`covers()`, GRANT-03) still bounds every review decision exactly as it
# bounds every dispatch send. Only the WALL between the two authorities' consent
# ceremonies came down; the wall between what they can each touch did not.


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _refusal(detail, **fields):
    return {"outcome": REFUSED, "detail": detail, **fields}


def _normalise(values):
    return [str(v).strip() for v in (values or []) if str(v).strip()]


# ------------------------------------------------------------- GRANT-02: the envelope
#
# D-57-00 SUPERSEDES D-53-02 (Phase 57, RUN-05; recorded in .planning/STATE.md,
# 57-DISCUSSION-LOG.md and 61-CONTEXT.md). This block used to say the envelope discloses
# and cannot constrain — true only while the remainder was sampled rather than read, and
# the sampling was unbuilt. It is built now: `allowance_headroom` walks the executions
# list and `plan_grant` refuses a CEILING_OVER batch before anything is armed. The
# figures below still describe what this batch can cost; they also now say what stops it.
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

_ALLOWANCE_SAMPLED = (
    "This projection is now compared against the SAMPLED remaining monthly execution "
    "allowance, not only the plan's configured total (Phase 57, D-57-01). The executions "
    "API list is not the billing quota (CLAUDE.md section 13.0.3 — [documented], not "
    "verified against billing), and the sample is capped at a page budget sized to the "
    "configured allowance — up to 1,000 executions across ALL workflows on the instance "
    "by default — so a month whose true traffic exceeds that budget can still come back "
    "unsampled and read as unknown rather than as a number.")

_CEILING_CONSTRAINT = (
    "These figures are this grant's ceiling, and the projected execution count above is "
    "compared against the sampled remaining monthly allowance BEFORE anything is armed "
    "or sent — a batch that would exceed it is refused, not merely disclosed. The "
    "comparison uses a formula measured to OVER-STATE a real chunk's cost (roughly 3x), "
    "deliberately, so it refuses early rather than letting an over-budget batch through "
    "late. When the remainder cannot be sampled, the run proceeds with the gap named "
    "rather than being blocked (D-57-02).")


# ------------------------------------------------------ RUN-05 / D-57-01: the ceiling
#
# D-57-00 supersedes D-53-02 for every run this milestone covers. D-53-02 recorded that a
# grant's computed ceiling is disclosure, not constraint — correct while a human watched
# every send. Phase 57 makes the execution allowance a conservative binding preflight
# refusal and a pre-send mid-run stop. The prior behaviour remains historical context,
# not current behaviour. Sampling limits and the retention caveat are disclosed rather
# than pretended away.

CEILING_OK = "ok"
CEILING_OVER = "over"
CEILING_UNKNOWN = "unknown"

RETENTION_CAVEAT = (
    "An exhausted listing is complete only with respect to what the n8n API RETAINS. "
    "n8n prunes execution history, and a pruned execution was still billed — so the "
    "sampled spend is a LOWER bound on this month's true cost and the sampled remainder "
    "is an UPPER bound on headroom. That is the one axis on which this guard is "
    "permissive, never the one on which it refuses too late. [documented] (n8n's "
    "retention behaviour, CLAUDE.md section 13.0.3), not [observed live]."
)


def allowance_headroom(config, *, transport=None, now=None) -> dict:
    """Sample THIS calendar month to date against the executions list, and report what is
    left of the configured monthly execution allowance (Phase 57, D-57-01, RUN-05).

    Returns `allowance`, `spent_sampled`, `remaining_sampled`, `covers_full_window`,
    `listing_exhausted`, `truncated_by_page_cap`, `observed_span_hours`, `sampled`,
    `retention_caveat` and `reason`.

    `sampled` is True only when: the allowance key is a positive int, AND
    `n8n_read.executions_in_window` returned a dict (not None — the read itself did not
    fail), AND `truncated_by_page_cap` is False, AND (`covers_full_window` OR
    `listing_exhausted`). In every other case `sampled` is False and `remaining_sampled`
    is None — NEVER a number derived from a partial count (Pitfall 4). `ceiling_verdict`
    reads `sampled` alone to decide reachability; it never re-derives this predicate.

    THE PAGE BUDGET IS RAISED TO FIT THE ALLOWANCE (REVIEW-57-H1). The module default —
    `n8n_read.MAX_EXECUTION_PAGES` (4) x `n8n_read.EXECUTIONS_WINDOW_PAGE_LIMIT` (250) —
    is 1,000 executions across ALL workflows on the instance, sized for a 24h sweep, not
    a month. This caller asks for `ceil(allowance / EXECUTIONS_WINDOW_PAGE_LIMIT) + 2`
    pages instead, so a month whose executions fit inside the CONFIGURED allowance cannot
    be truncated by a page budget sized for a different question. At the documented
    Starter 2,500/month that is 12 pages — up to 12 GETs per grant, once, not per lane.

    THE RETENTION CAVEAT, CARRIED ON `retention_caveat` AND NEVER SOFTENED: an exhausted
    listing (`listing_exhausted`) is complete only with respect to what the API retains.
    n8n prunes; a pruned execution was still billed. `spent_sampled` is therefore a LOWER
    bound and `remaining_sampled` an UPPER bound on headroom — the one axis on which this
    guard is permissive rather than conservative, tagged `[documented]` rather than
    `[observed live]` per CLAUDE.md section 13.0.3.
    """
    now = now or datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    window_hours = max(
        (now - month_start).total_seconds() / 3600.0, n8n_read.MIN_OBSERVED_SPAN_HOURS)

    raw_allowance = (config or {}).get(n8n_read.EXECUTION_ALLOWANCE_KEY)
    allowance_valid = (isinstance(raw_allowance, int) and not isinstance(raw_allowance, bool)
                       and raw_allowance > 0)

    unsampled = {
        "spent_sampled": None, "remaining_sampled": None, "covers_full_window": None,
        "listing_exhausted": None, "truncated_by_page_cap": None,
        "observed_span_hours": None, "sampled": False, "retention_caveat": RETENTION_CAVEAT,
    }

    if not allowance_valid:
        return {
            "allowance": None,
            "reason": (
                f"{n8n_read.EXECUTION_ALLOWANCE_KEY!r} is not configured (or is not a "
                f"positive whole number), so there is no monthly allowance to sample a "
                f"remainder against."),
            **unsampled,
        }

    max_pages = math.ceil(raw_allowance / n8n_read.EXECUTIONS_WINDOW_PAGE_LIMIT) + 2
    get_transport = transport.get if hasattr(transport, "get") else transport
    read_kwargs = {} if get_transport is None else {"transport": get_transport}

    window = n8n_read.executions_in_window(
        config, now=now, window_hours=window_hours, max_pages=max_pages, **read_kwargs)

    if window is None:
        return {
            "allowance": raw_allowance,
            "reason": (
                "the executions list could not be read at all this month, so there is "
                "nothing to sample a remainder against."),
            **unsampled,
        }

    covers_full_window = window.get("covers_full_window")
    listing_exhausted = window.get("listing_exhausted")
    truncated = bool(window.get("truncated_by_page_cap"))
    spent = window.get("count_in_window")

    sampled = (not truncated) and bool(covers_full_window or listing_exhausted)
    remaining = (raw_allowance - spent) if sampled and isinstance(spent, int) else None

    if sampled:
        if listing_exhausted and not covers_full_window:
            reason = (
                "sampled from an exhausted executions listing — there is nothing "
                "further for the API to return this month. Subject to the retention "
                "caveat: a pruned execution would not appear here even though it was "
                "billed.")
        else:
            reason = "sampled: retained history reaches back past the start of this month."
    elif truncated:
        reason = (
            f"the executions list truncated at the {max_pages}-page budget before "
            f"reaching either the start of the month or an exhausted listing — the "
            f"partial count is NEVER read as a full one.")
    else:
        reason = "the executions list could not be confirmed complete or exhausted."

    return {
        "allowance": raw_allowance,
        "spent_sampled": spent if sampled else None,
        "remaining_sampled": remaining,
        "covers_full_window": covers_full_window,
        "listing_exhausted": listing_exhausted,
        "truncated_by_page_cap": truncated,
        "observed_span_hours": window.get("observed_span_hours"),
        "sampled": sampled,
        "retention_caveat": RETENTION_CAVEAT,
        "reason": reason,
    }


def ceiling_verdict(figures, headroom) -> dict:
    """Pure, no I/O: compare a batch's projected execution count against a sampled
    monthly remainder (Phase 57, D-57-01).

    `CEILING_UNKNOWN` whenever `headroom["sampled"]` is False OR
    `figures["projected_executions"]` is None — two of three provider balances already
    read `unknown` on this account, and D-57-02 is explicit that an unknown verdict must
    proceed rather than refuse (a guard that always fires is indistinguishable from a
    feature that is off). `CEILING_OVER` only when both are real numbers and the
    projection STRICTLY exceeds the remainder — consuming the exact remaining allowance
    is legitimate and must not refuse.
    """
    headroom = headroom or {}
    projected = (figures or {}).get("projected_executions")
    sampled = bool(headroom.get("sampled"))
    remaining = headroom.get("remaining_sampled")
    allowance = headroom.get("allowance")
    spent = headroom.get("spent_sampled")

    if not sampled or projected is None:
        verdict = CEILING_UNKNOWN
        shortfall = None
        if not sampled:
            reason = headroom.get("reason") or "the monthly remainder could not be sampled."
        else:
            reason = "this batch has no execution projection to compare against a remainder."
    else:
        over = projected > remaining
        verdict = CEILING_OVER if over else CEILING_OK
        shortfall = (projected - remaining) if over else None
        reason = (
            f"the projected {projected} execution(s) exceed the sampled {remaining} "
            f"remaining this month by {shortfall}." if over else
            f"the projected {projected} execution(s) fit inside the sampled {remaining} "
            f"remaining this month.")

    return {
        "verdict": verdict,
        "projected_executions": projected,
        "allowance": allowance,
        "spent_sampled": spent,
        "remaining_sampled": remaining,
        "shortfall": shortfall,
        "basis": EXECUTIONS_BASIS,
        "reason": reason,
    }


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


def _ceiling_line(ceiling):
    """Phase 57 / D-57-01 / RUN-05: the sampled monthly ceiling verdict, in the
    operator's own reading order — `ok`, `over` with the shortfall, or `unconfirmed`.
    `unconfirmed` is its own answer here too, in the same register `_headroom` already
    established for an unreadable provider balance, and it must never read as headroom."""
    verdict = (ceiling or {}).get("verdict")
    if verdict == CEILING_OK:
        return (
            f"Execution ceiling: **ok** — sampled {ceiling.get('spent_sampled')} spent, "
            f"{ceiling.get('remaining_sampled')} remaining this month of the configured "
            f"{ceiling.get('allowance')}.")
    if verdict == CEILING_OVER:
        return (
            f"Execution ceiling: **OVER** — sampled {ceiling.get('spent_sampled')} "
            f"spent, only {ceiling.get('remaining_sampled')} remaining this month of the "
            f"configured {ceiling.get('allowance')}; this batch is "
            f"{ceiling.get('shortfall')} execution(s) over.")
    return (
        f"Execution ceiling: **unconfirmed** — "
        f"{(ceiling or {}).get('reason') or 'the monthly remainder could not be sampled.'}")


def _post_transport(transport):
    if transport is None:
        return None
    return transport.post if hasattr(transport, "post") else transport


def envelope(config, *, object_type, record_ids, record_domains, providers,
             transport=None, today=None, headroom=None):
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

    `headroom=None` (default) means this call samples the month-to-date executions list
    itself, via `allowance_headroom`. A caller that already has a sample — `plan_grant`
    does, computed once per grant before this call — passes it in here so the executions
    list is walked ONCE per grant, never twice (REVIEW-57-H9's frozen call order names
    this as a single read).
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
    # CR-01 fix (Phase 60 review): this used to share the name `ceiling` with the
    # sampled-allowance verdict dict assigned below, so `figures["chunk_ceiling"]`
    # ended up holding the verdict dict instead of this int, and the GRANT-02
    # disclosure rendered a dict repr where a record count belongs. Kept as its own
    # name so the two meanings (per-chunk record cap vs. monthly verdict) can never
    # collide again.
    chunk_record_ceiling = None
    executions = None
    executions_basis = PROJECTED
    try:
        chunk_record_ceiling = chunking.chunk_ceiling(config)
        chunk_count = chunking.plan_chunks(
            {"record_ids": ids + domains, "object_type": object_type},
            chunk_record_ceiling).chunk_count
        executions = chunk_count + record_count
    except chunking.ChunkPlanError:
        executions_basis = UNCONFIGURED

    allowance = (config or {}).get(n8n_read.EXECUTION_ALLOWANCE_KEY)
    allowance_configured = isinstance(allowance, int) and not isinstance(allowance, bool) \
        and allowance > 0
    if not allowance_configured:
        allowance = None

    # Phase 57 / D-57-01 / RUN-05: the sampled monthly ceiling, computed here so every
    # caller of `envelope()` — not only `plan_grant` — gets the verdict for free.
    if headroom is None:
        get_transport = transport.get if hasattr(transport, "get") else transport
        headroom = allowance_headroom(config, transport=get_transport)
    ceiling = ceiling_verdict({"projected_executions": executions}, headroom)

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
        "chunk_ceiling": chunk_record_ceiling,
        "chunk_count": chunk_count,
        "projected_executions": executions,
        "executions_projection_basis": EXECUTIONS_BASIS,
        "monthly_execution_allowance": allowance,
        "allowance_configured": allowance_configured,
        # Phase 57 / D-57-01 / RUN-05: the ceiling is now sampled, not asserted absent.
        "remaining_allowance_sampled": bool(headroom.get("sampled")),
        "spent_sampled": headroom.get("spent_sampled"),
        "remaining_sampled": headroom.get("remaining_sampled"),
        "sample_covers_full_window": headroom.get("covers_full_window"),
        "sample_listing_exhausted": headroom.get("listing_exhausted"),
        "sample_truncated_by_page_cap": headroom.get("truncated_by_page_cap"),
        "retention_caveat": headroom.get("retention_caveat"),
        "ceiling": ceiling,
        "basis": {
            "record_count": MEASURED,
            "provider_credits": MEASURED,
            # 2026-08-27, Phase 54 Task 3 (OP-54-05): this was MEASURED before this date.
            # It is a static rate-table multiplication (record_count * config/
            # cost_rates.json's dated anthropic_usd_per_record) — no code path anywhere
            # in this repo reads back Anthropic's real token usage for a real execution,
            # so it was never a measurement. Relabelled PROJECTED; the figure itself is
            # unchanged, only the label an operator reads it under.
            "anthropic_usd": PROJECTED,
            "projected_executions": executions_basis,
            "monthly_execution_allowance": (
                MEASURED if allowance_configured else UNCONFIGURED),
            "remaining_allowance": MEASURED if headroom.get("sampled") else UNCONFIGURED,
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
                  f"— a projection from the dated rate table above, not a "
                  f"measurement (this repo never reads back real Anthropic usage)."]

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

    # Phase 57 / D-57-01 / RUN-05: the sampled ceiling verdict, in the operator's own
    # reading order, right after the allowance line it compares against.
    lines.append(_ceiling_line(figures.get("ceiling") or {}))
    if figures.get("sample_listing_exhausted") and not figures.get("sample_covers_full_window"):
        lines.append(figures.get("retention_caveat") or RETENTION_CAVEAT)

    lines += ["", _ALLOWANCE_SAMPLED, "", _CEILING_CONSTRAINT]
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
        # D-59-07, operator, 2026-08-28: the pre-emptive warning this branch used to
        # render at the yes -- "the HubSpot write is authorized BEFORE the enriched
        # preview exists, so held rows and merge conflicts are authorized unseen" -- is
        # RETIRED as operator-facing text. 53-04 described it as "the whole of what you
        # got for the protection you traded": a warning nobody could act on until after
        # the fact anyway. What replaces it is actionable -- a durable, post-run list of
        # the records this run actually wrote (see `written_records.py`), which the
        # operator can open in HubSpot and amend. This is a deliberate operator
        # decision, not a simplification: the D-53-05 trade itself (one grant, both
        # lanes, the allowlist unchanged) is UNTOUCHED -- only what the operator is told
        # about it changed.
        #
        # D-59-09 gap-closure, operator, 2026-08-29: the sentence disclosing the
        # written-records artifact used to live ONLY in this multi-lane branch --
        # scoped there in error, since the artifact is written after EVERY dispatch
        # regardless of how many lanes a grant spans. That sentence has MOVED below,
        # outside this branch, so it fires for a single-lane grant too. What is left
        # here, genuinely multi-lane, is the statement that this one grant covers every
        # named lane at once. Phase 60, D-60-02: a grant may now span up to three lanes,
        # not just two, so the count is derived from `lane_names` rather than the fixed
        # "both" this sentence used to say — the trailing clause itself is unchanged and
        # stays pinned by `test_a_two_lane_grant_names_both_lanes_and_points_at_the_written_records_list`.
        sentence += (
            f" This grant covers all {len(lane_names)} lanes at once: it enables "
            f"enrichment and writes to HubSpot.")

    # D-59-09 (operator, 2026-08-29): fires for every grant, one lane or two -- see the
    # note above for why this moved out of the multi-lane branch. The artifact itself
    # moved from one file shared across runs to one file per run under the same
    # decision (`written_records.written_records_path(run_id)`); the wording below
    # names that per-run shape rather than a single fixed filename.
    sentence += (
        f" After the run, the records it actually wrote are listed in a "
        f"written_records-<run_id>.json file (one per run, matching the pattern "
        f"{written_records.WRITTEN_RECORDS_GLOB!r}), in the plugin's durable state "
        f"directory, so you can open them in HubSpot and amend them.")
    return sentence


# --------------------------------------------------------- D-57-04: the auto-split offer
#
# RUN-05's "offers a smaller batch", made concrete. `split_for_allowance` has TWO
# products, and the second is PROJECTED FROM the first (REVIEW-57-H1, the correction to
# an earlier draft that split them independently — see the module-level comment above
# `plan_grant`'s CEILING_OVER branch, the one call site, for why that mattered enough to
# be the whole correctness argument of this section).

def _looks_like_hs_object_id(value) -> bool:
    """A HubSpot object id is a bare run of digits; a domain never is. This is the
    ONLY test used to tell "id-shaped" from "domain-shaped" apart when a `record_ids`
    spec carries both (`envelope()`'s own `ids + domains` combined projection, above,
    is exactly such a spec) — never a positional assumption about which half of the
    list is which (REVIEW-57-H1)."""
    text = str(value).strip()
    return bool(text) and text.isdigit()


def _classify_scope_member(key, record):
    """One record from a `spec`'s list-bearing `key`, classified into the grant scope's
    own vocabulary: `("record_ids", value)`, `("record_domains", value)`, or `None`
    when the record carries neither identity a grant scope can express.

    `record_ids`-keyed members are matched on their own shape (see
    `_looks_like_hs_object_id`) because that key's list may hold ids and domains mixed
    together. `companies`-keyed members are always domain-only creates — `domain` is
    the only identity a company spec's own shape ever carries (CLAUDE.md section
    13.0.1; `enrichment.build_envelope`'s companies branch never emits an id). `rows`
    and `people` members describe someone who may not be matched to a HubSpot record
    yet; the only identity such a record can carry that maps onto a grant scope is a
    PRE-RESOLVED `hs_object_id` some upstream match step already attached — a domain
    has no meaning for a contact, so an unmatched row/person contributes to neither
    scope key, exactly as it would need a read-only HubSpot lookup (D-59-08's own
    refusal text) before it could be granted at all.
    """
    if key == "record_ids":
        value = str(record).strip()
        if not value:
            return None
        return (("record_ids", value) if _looks_like_hs_object_id(value)
                else ("record_domains", value))
    if key == "companies":
        domain = str((record or {}).get("domain") or "").strip()
        return ("record_domains", domain) if domain else None
    hs_object_id = (record or {}).get("hs_object_id") if isinstance(record, dict) else None
    if hs_object_id and _looks_like_hs_object_id(hs_object_id):
        return ("record_ids", str(hs_object_id).strip())
    return None


def _project_scope(key, records):
    """The grant scope PROJECTED FROM `records`, walked in their own order — never a
    separately-ordered `(kind, value)` sequence. A side with no members omits its key,
    matching `envelope()`/`plan_grant()`'s own `record_ids`/`record_domains` shape."""
    scope_ids, scope_domains = [], []
    for record in records:
        identity = _classify_scope_member(key, record)
        if identity is None:
            continue
        bucket, value = identity
        (scope_ids if bucket == "record_ids" else scope_domains).append(value)
    scope = {}
    if scope_ids:
        scope["record_ids"] = scope_ids
    if scope_domains:
        scope["record_domains"] = scope_domains
    return scope


def _spec_for(key, members, object_type):
    """One half of a split, in `chunking.failed_batch()`'s own shape — directly
    re-sendable to `chunking.dispatch_plan` with no re-derivation."""
    spec = {key: list(members)}
    if key in chunking.KEYS_WITH_OBJECT_TYPE:
        spec["object_type"] = object_type
    return spec


def _affordable_record_count(total, ceiling, remaining):
    """The largest N (0 <= N <= `total`) such that `ceil(N / ceiling) + N` — the SAME
    `chunk_count + record_count` basis `EXECUTIONS_BASIS` and
    `run_state.spend_against_ceiling` already use, never re-derived — is at or under
    `remaining`. A linear scan that stops at the first N whose cost overshoots — never
    a `while` loop (D-07's own AST guard, `test_report_sufficiency.py`, forbids one in
    every plugin script but `watch.py`) — which is correct only because the cost is
    monotonically non-decreasing in N (increasing N never decreases either term),
    pinned by `test_affordable_record_count_cost_is_monotonic_over_a_range_of_n` in
    `test_write_grant.py` rather than assumed: once one N overshoots, every larger N
    overshoots too, so stopping there never misses a larger affordable N.
    """
    if remaining is None or remaining < 0 or total < 1:
        return 0
    best = 0
    for n in range(1, total + 1):
        cost = -(-n // ceiling) + n  # ceil(n / ceiling) + n, integer arithmetic
        if cost > remaining:
            break
        best = n
    return best


# Every key `split_for_allowance` can fail to fill in — both work-spec halves and both
# scope halves — so a refusal always carries the same four `None`s rather than a
# caller-visible difference between "no spec" and "unsampleable" failure shapes.
_NO_SPLIT_OFFER = {
    "affordable_spec": None, "remainder_spec": None,
    "affordable": None, "remainder": None,
    "runs": None, "record_ceiling_per_run": None,
}


def split_for_allowance(config, *, object_type, spec=None, record_ids=None,
                        record_domains=None, headroom, providers=None):
    """D-57-04: the smaller-batch offer a `CEILING_OVER` refusal carries. Pure — no
    transport, no durable write; the caller decides whether to accept, and only an
    ACCEPTED offer's remainder is ever persisted (`remainder_queue.save`, at the
    runbook step after a fresh grant opens — REVIEW-57-H5, see `plan_grant`'s own
    CEILING_OVER branch, the one call site, for the state transition in full).

    `record_ids=`/`record_domains=`/`providers=` are accepted for signature parity
    with `envelope()`/`plan_grant()`'s own scope arguments but play no part in the
    split itself — see the paragraph below for why. Nothing but `spec` and `headroom`
    is read.

    **TWO PRODUCTS, and the second is PROJECTED FROM the first (REVIEW-57-H1).** An
    earlier draft split a work spec's own records and a `record_ids`/`record_domains`
    scope as two INDEPENDENTLY ordered sequences, cut at the same N, and called them
    "consistent by construction" on a count check alone. They are not: a work list
    that interleaves an id-backed record and a domain-only create candidate cuts to a
    DIFFERENT membership on each side once the two sequences are ordered differently —
    the exact failure this phase exists to prevent, produced by the mechanism meant to
    prevent it. So there is ONE ordered sequence — `spec`'s own records, in the
    caller's order — cut once at N; `affordable`/`remainder` are then PROJECTIONS of
    that same cut, computed by walking each half and classifying every record by its
    own shape (`_classify_scope_member`), never by a second, independently-ordered
    list. `spec=None` means there is nothing to project from, so EVERY key — both
    spec halves and both scope halves — comes back `None`; that parallel
    scope-without-a-spec path is exactly what this correction removes.

    Returns `affordable_spec`/`remainder_spec` (WORK, `chunking.failed_batch()` shape,
    directly re-sendable), `affordable`/`remainder` (the GRANT SCOPE, keyed
    `record_ids`/`record_domains`, projected from the matching spec half — a side with
    no members omits its key), `runs` (how many runs of `record_ceiling_per_run`'s
    size the whole batch would take), `record_ceiling_per_run` (the N found), and
    `reason` (`None` on success, or why no split could be offered).

    No split is offered — every key `None`, `reason` naming which — when: `spec` is
    missing or not a dict; `spec` names none of `chunking.LIST_BEARING_KEYS`; `spec`'s
    list is empty; `headroom["sampled"]` is False (there is no number to split
    against, per D-57-02); the configured chunk ceiling cannot be read; or the largest
    affordable N works out below 1 (not even one record fits — never an empty batch
    dressed as an offer).
    """
    if spec is None or not isinstance(spec, dict):
        return {**_NO_SPLIT_OFFER, "reason": (
            "no work specification (`spec=`) was supplied to split against — there is "
            "no scope split without the work it would be projected from.")}

    key = next((k for k in chunking.LIST_BEARING_KEYS if k in spec), None)
    if key is None:
        return {**_NO_SPLIT_OFFER, "reason": (
            "the work specification names none of record_ids, rows, people or "
            "companies, so there is nothing to split by record.")}

    records = list(spec.get(key) or [])
    if not records:
        return {**_NO_SPLIT_OFFER, "reason":
                "the work specification names no records to split."}

    headroom = headroom or {}
    if not headroom.get("sampled"):
        return {**_NO_SPLIT_OFFER, "reason": (
            headroom.get("reason")
            or "the monthly remainder could not be sampled, so no split can be offered.")}

    try:
        ceiling = chunking.chunk_ceiling(config)
    except chunking.ChunkPlanError as e:
        return {**_NO_SPLIT_OFFER, "reason": str(e)}

    total = len(records)
    n = _affordable_record_count(total, ceiling, headroom.get("remaining_sampled"))
    if n < 1:
        return {**_NO_SPLIT_OFFER, "reason": (
            f"not even one record fits inside the sampled "
            f"{headroom.get('remaining_sampled')} execution(s) remaining this month — "
            f"no smaller batch can be offered.")}

    affordable_records = records[:n]
    remainder_records = records[n:]

    return {
        "affordable_spec": _spec_for(key, affordable_records, object_type),
        "remainder_spec": _spec_for(key, remainder_records, object_type),
        "affordable": _project_scope(key, affordable_records),
        "remainder": _project_scope(key, remainder_records),
        "runs": math.ceil(total / n),
        "record_ceiling_per_run": n,
        "reason": None,
    }


def plan_grant(config, *, lanes, object_type, record_ids, record_domains, allow_create,
               label, providers=None, transport=None, preflight=None, today=None,
               override=False, override_reason=None):
    """Compose a PROPOSAL for a write grant. Reads only — never mutates anything.

    Refuses, in this order and before returning anything: an unauthorized config, an
    unknown lane, an empty record set, a lane whose workflow cannot be resolved by name,
    a batch whose projected executions exceed the sampled remaining monthly allowance
    (Phase 57, D-57-01, RUN-05 — see `ceiling` below).

    `providers` is the resolved provider selection the envelope is priced against;
    `None` means the configured selection in `enrichment_providers`, the same default
    every other lane in this plugin resolves to.

    `override`/`override_reason` (Phase 57, REVIEW-57-M6) let an operator proceed past a
    `CEILING_OVER` refusal. `override=True` with no non-blank `override_reason` string
    RAISES `ValueError` rather than proceeding — an override with no recorded
    justification is not an override, it is the guard's absence with extra steps. THE
    OVERRIDE NEVER TRAVELS: it is accepted here only from the caller's own immediate
    argument, never read from a config key, a stored grant, or a remainder resume — no
    runbook step may set it from anything but the operator's answer in that conversation
    (Task 4 pins this with a structural grep). When accepted, the returned proposal's
    `ceiling` dict carries `overridden: True`, `override_reason` and
    `override_authority: "operator"`, rendered in full wherever the run is reported.

    `preflight` IS GUARDRAIL A, and it is not optional. `None` means the real one; a
    caller may substitute another callable (a test does), but a non-callable value is a
    TypeError rather than a skipped check. There is no config key, environment variable
    or phrase that turns it off — an off switch on a guardrail is the guardrail's absence
    with extra steps (T-53-12). It is invoked with `(config, workflow_ids, transport)` and
    its refusal is returned with the envelope attached.

    `ceiling` (Phase 57): the `ceiling_verdict` computed against `allowance_headroom`'s
    live sample, attached to every returned proposal AND every refusal so an operator is
    never shown a batch's cost without also being shown how much of the month it would
    spend. `CEILING_UNKNOWN` — an unconfigured or unsampleable allowance — does NOT
    refuse (D-57-02: a guard that always fires is indistinguishable from a feature that
    is off; two of three provider balances already read `unknown` on this account, and
    refusing on unknown would block essentially every run). Only `CEILING_OVER` refuses,
    and only when `override` is falsey.

    CALL ORDER, frozen because every scripted test depends on it: the cheap refusals
    (authority, lanes, record set) cost nothing; then one workflow-collection GET per
    lane to resolve ids; then ONE executions-list read sequence for the Phase 57
    headroom sample (never per lane — the sample is per grant, and it is sampled here
    rather than inside `envelope()` so a grant that already has one hands it in and
    `envelope()` never re-walks the list — REVIEW-57-H9); then ONE status POST for
    provider balances, and only when the batch actually prices a provider, computed
    INSIDE `envelope()`; then one workflow GET per lane for guardrail A. The envelope
    AND the ceiling are computed BEFORE guardrail A so that a refused open still tells
    the operator what the batch would have cost and how it stood against the month's
    allowance.
    """
    if override and not (isinstance(override_reason, str) and override_reason.strip()):
        raise ValueError(
            "an override with no recorded reason is not an override. Pass "
            "`override_reason` as the operator's own words, given in this conversation, "
            "for why this batch must exceed the sampled remaining monthly allowance."
        )

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
            f"The grantable lanes are: {', '.join(sorted(LANES))}.")
    if not lane_names:
        return _refusal(
            f"a write grant must name at least one lane. The grantable lanes are: "
            f"{', '.join(sorted(LANES))}.")

    ids = _normalise(record_ids)
    domains = _normalise(record_domains)
    if not ids and not domains:
        # D-59-08, operator, 2026-08-28 (GATE-06, FINDING 1 of 53-WALK-RECORD.md): the
        # refusal ITSELF is deliberately unchanged — a grant over nothing is still
        # correctly refused, for the same reason stated below. What changed is that it
        # now NAMES what would resolve it. The resolution happens in the skill, BEFORE
        # this call — never here. `plan_grant` gains no lookup, no transport call and
        # no resolution logic; see the structural test in test_write_grant.py pinning
        # that.
        return _refusal(
            "refusing to plan a grant over an empty record set. The deployed "
            "_writeSafetyAllows() returns false when both allowlists are empty, so a "
            "grant over nothing would report as a grant while granting nothing at all — "
            "worse than refusing, because it reads as success. This is resolvable: a "
            "read-only HubSpot lookup for the record's own object id, or — for a "
            "record that does not exist yet and therefore has no id — for its "
            "company's domain, which is the handle this allowlist can express a "
            "create with. Resolve it and plan the grant again with the result.")

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

    # Phase 57 / D-57-01 / RUN-05: sample the month-to-date remainder ONCE per grant,
    # right after lane resolution and before `envelope()`'s own balances POST, and hand
    # it to `envelope()` so the figures an operator reads already carry the verdict.
    # `envelope()` would otherwise sample it a SECOND time for a caller that has none —
    # REVIEW-57-H9's frozen call order is one executions-list read per grant, not two.
    headroom = allowance_headroom(config, transport=get_transport)

    figures = envelope(
        config, object_type=object_type, record_ids=ids, record_domains=domains,
        providers=providers if providers is not None
        else (config or {}).get("enrichment_providers"),
        transport=transport, today=today, headroom=headroom)

    # Phase 57 / D-57-01 / RUN-05: the refuse-before-starting check, computed from the
    # SAME headroom sample the envelope was just built from (a refusal still carries the
    # batch's own figures) and BEFORE guardrail A (an over-ceiling batch never reaches a
    # live write-safety read at all).
    #
    # DELIBERATE DIVERGENCE FROM `n8n_cadence.check_budget_floor`'s own analog, recorded
    # here rather than left for a reader to notice and "fix": that function refuses
    # FIRST and unconditionally on a missing config key. This one does not. A
    # `CEILING_UNKNOWN` verdict proceeds with the blind spot disclosed, per D-57-02 — two
    # of three provider balances already read `unknown`, and refusing on unknown would
    # block essentially every run today, which makes the guard indistinguishable from
    # the feature being switched off. Only `CEILING_OVER` refuses. `envelope()`'s own
    # established contract for a missing allowance key ("one missing line, not a reason
    # to refuse") is preserved by this choice, not contradicted.
    ceiling = figures["ceiling"]
    if ceiling["verdict"] == CEILING_OVER and not override:
        # D-57-04, option-a (operator, Task 1's checkpoint): the refusal carries a
        # concrete offer alongside the arithmetic. `plan_grant` has no chunking-shaped
        # work spec of its own — only the resolved `ids`/`domains` scope — so the spec
        # split against is the same combined "record_ids" projection `envelope()` above
        # already uses for its own chunk count (`ids + domains`, worst case priced as
        # every domain being a distinct record). `split_for_allowance` classifies each
        # element by its OWN shape (id-shaped vs domain-shaped) rather than assuming
        # this combined list is ordered "ids then domains" (REVIEW-57-H1). This call is
        # PURE — no transport, no durable write — so a refusal the operator never
        # accepts writes nothing (REVIEW-57-H5; see `split_for_allowance`'s own
        # docstring for the four-step state transition an ACCEPTED offer follows).
        split_offer = split_for_allowance(
            config, object_type=object_type,
            spec={"record_ids": ids + domains, "object_type": object_type},
            record_ids=ids, record_domains=domains,
            headroom=headroom,
            providers=providers if providers is not None
            else (config or {}).get("enrichment_providers"),
        )
        return _refusal(
            f"refusing to open this grant: it projects {ceiling['projected_executions']} "
            f"execution(s) this month against a sampled {ceiling['remaining_sampled']} "
            f"remaining of the configured {ceiling['allowance']} allowance "
            f"({ceiling['spent_sampled']} already sampled spent this month) — "
            f"{ceiling['shortfall']} execution(s) over. This projection is "
            f"{EXECUTIONS_BASIS}, and it is measured to OVER-STATE a real chunk's cost "
            f"(roughly 3x) — deliberately, so it refuses early rather than letting an "
            f"over-budget batch through late. {RETENTION_CAVEAT} Name a smaller batch, "
            f"or tell me to override this refusal and why."
            + (
                f" A smaller batch is available now: "
                f"{split_offer['record_ceiling_per_run']} of "
                f"{figures['record_count']} record(s) would fit this run, with the "
                f"other "
                f"{figures['record_count'] - split_offer['record_ceiling_per_run']} "
                f"queued for a future run you will separately authorise — each "
                f"subsequent run opens its OWN grant, so this is a plan of work, never "
                f"standing permission to spend and never a schedule that runs itself."
                if split_offer.get("affordable_spec") is not None else
                f" {split_offer['reason']}"
            ),
            envelope=figures, ceiling=ceiling, split_offer=split_offer)

    if override:
        # Recorded, not just honoured (REVIEW-57-M6): every reader downstream —
        # 57-05's end-of-run report included — must be able to tell an overridden run
        # from an under-ceiling one at a glance.
        ceiling = {**ceiling, "overridden": True, "override_reason": override_reason,
                   "override_authority": "operator"}

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
        return {**blocked, "envelope": figures, "ceiling": ceiling}

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
        # Phase 57 / RUN-05: this grant's ceiling verdict against the sampled monthly
        # remainder — see `ceiling_verdict`. `open_grant` deep-copies the proposal, so
        # this rides along onto the opened grant unchanged.
        "ceiling": ceiling,
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

    Phase 61 Plan 06 Task 3 (REVIEW-11), VERIFIED, NO CODE CHANGE: a record created
    DURING a batch has an id absent from `grant['record_ids']` (unknowable at grant-
    open time), which reviewers read as an unclosed scope gap for "one grant covers the
    whole batch, including what it creates." The check below is symmetric across
    `record_ids` AND `record_domains` — every value in BOTH lists must be inside the
    grant, an AND, not an OR — so a send that also passes the create's own brand-new id
    still refuses even when its domain is covered. What closes the gap is upstream, not
    here: `enrich-before-ingest/SKILL.md`'s own batch-composition step confirms every
    company's domain BEFORE the grant opens, and this skill's calling convention never
    passes a record's own id for a row that has none yet (SKILL.md: "record_ids=<this
    send's ids>" is empty for such a row) — it expresses the send by domain alone. A
    same-run create is therefore covered via `record_domains`, with no widening of
    `covers()` itself; see `test_write_grant.py`'s
    `test_covers_admits_a_same_run_create_via_the_domain_named_at_grant_time` for the
    verification this comment describes.
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


def authorize_send(grant, *, lane, record_ids, record_domains):
    """The ONE function a lane skill calls to turn an open grant into the `armed` argument
    `chunking.dispatch_plan` already takes. Returns a dict carrying:

        armed        the bool `dispatch_plan`/`dispatch_enrichment` take, with no default
        workflow_id  the lane's id, for `armed_window`
        grant        the grant to hand to `armed_window` (unchanged)
        refusal      `check_before_send`'s refusal, or None
        detail       one sentence for the operator

    NOTHING ELSE ABOUT THE DISPATCH PATH CHANGES. The arm is still
    `n8n_arming.arm_for_dispatch`, the window is still `armed_window`, the allowlist is
    still the send's own records, and the arm is still verified by `apply_mutation`'s
    independent re-read.

    WHAT IT DELIBERATELY DOES NOT DO, both because a later reader will be tempted:

    * **It does not widen the allowlist to the grant's whole record set.** Each send's
      window stays scoped to THAT SEND's records, which is strictly narrower than the
      grant. That is the milestone's "arming a session must widen the allowlist to the
      batch, never to everything", and with D-53-05 accepted it is the only remaining
      structural protection on the enrich-before-ingest path — the collapse there widened
      WHEN the approval is given, and this is what keeps it from widening WHAT it covers.
      This function returns a workflow id and a bool; it never returns a record list, so
      there is nothing here for a caller to pass to the arm by mistake.
    * **It does not hold a window open across sends.** Every send opens and closes its
      own, which is what keeps the guaranteed disarm (53-01's flagged assumption).

    WITH NO GRANT THIS IS NOT A REFUSAL. D-53-04 is explicit that the grant is an ADDITION
    rather than a replacement: with no grant open, today's per-send confirmation is
    unchanged. A bridge that refused the ungranted case would have removed the path it was
    supposed to leave alone, so `grant=None` returns `armed=False` with `refusal=None` and
    a detail naming the per-send phrase.

    Pure: no config, no transport, no network. `preflight_before_send` is guardrail B's
    live read and is a SEPARATE call a lane skill makes with a config in hand — it returns
    `(grant, None)` on a lane the grant does not cover, so it is not a lane gate and must
    not be mistaken for one. `check_before_send`, composed here, is the one place a send
    is refused.
    """
    if grant is None:
        return {
            "armed": False, "workflow_id": None, "grant": None, "refusal": None,
            "detail": ("no write grant is open, so this send is on the ordinary per-send "
                       "path: confirm this one send with the operator, as before."),
        }

    workflow_id = ((grant or {}).get("workflow_ids") or {}).get(lane)
    refusal = check_before_send(grant, lane=lane, workflow_id=workflow_id,
                                record_ids=record_ids, record_domains=record_domains)
    if refusal:
        return {"armed": False, "workflow_id": workflow_id, "grant": grant,
                "refusal": refusal, "detail": refusal["detail"]}

    return {
        "armed": True, "workflow_id": workflow_id, "grant": grant, "refusal": None,
        "detail": (f"authorized by the open write grant: live writes for this send only, "
                   f"bounded to this send's {len(_normalise(record_ids))} record id(s) "
                   f"and {len(_normalise(record_domains))} domain(s) — narrower than the "
                   f"grant, never wider."),
    }


def authorize_review_batch(grant):
    """The ONE function a review-triage sitting calls to turn an open grant into a
    BATCH-SCOPED window covering the WHOLE sitting (D-60-06), rather than the
    per-send-shaped window `authorize_send` composes. Returns the same `{armed,
    workflow_id, grant, refusal, detail}` shape every other authorization in this module
    returns, PLUS `record_ids` and `record_domains` — the grant's own lists, normalised
    through `_normalise`.

    THE DELIBERATE DIVERGENCE FROM `authorize_send`, STATED PLAINLY. `authorize_send`
    refuses to return a record list precisely so a caller cannot widen a per-send window to
    the grant's whole batch (its own docstring, "WHAT IT DELIBERATELY DOES NOT DO" — "this
    function returns a workflow id and a bool; it never returns a record list, so there is
    nothing here for a caller to pass to the arm by mistake"). This function returns one ON
    PURPOSE, because D-60-06 makes the review window batch-scoped: its allowlist IS the
    grant's own record scope, fixed at open time, and it must never grow as records are
    triaged one by one.

    WHAT STILL BOUNDS IT, even with a record list returned. `covers` (composed here through
    `check_before_send`) already refused anything outside the grant before this function
    ever returned a record list — the grant's own record scoping is untouched. And every
    INDIVIDUAL decision made inside the open batch window is still scoped per record
    through `authorize_send(lane=REVIEW_LANE, record_ids=[that one record])`, exactly as
    every dispatch send is — so a wide window never widens what a single decision may
    approve. The batch is wide; each approval inside it stays narrow.

    WHAT THIS IS NOT FOR. It takes no `lane` argument anywhere — it always checks the
    REVIEW lane specifically — so a dispatch caller cannot reach a batch-scoped window by
    passing some other lane name. It refuses on any grant that does not cover the review
    lane, in the exact wording `check_before_send`/`covers` already use for any other lane.

    Composed through `check_before_send(grant, lane=REVIEW_LANE, ...)` rather than a new
    refusal wording, so a closed grant, a missing lane and a bad grant shape all refuse
    exactly as they already do everywhere else in this module.

    See `preflight_before_send`'s own docstring (MEDIUM-1, Phase 60) for the guard that
    keeps the window THIS FUNCTION authorizes from tripping over its own arm mid-batch.
    """
    workflow_id = ((grant or {}).get("workflow_ids") or {}).get(REVIEW_LANE)
    ids = _normalise((grant or {}).get("record_ids"))
    domains = _normalise((grant or {}).get("record_domains"))

    refusal = check_before_send(grant, lane=REVIEW_LANE, workflow_id=workflow_id,
                                record_ids=ids, record_domains=domains)
    if refusal:
        return {"armed": False, "workflow_id": workflow_id, "grant": grant,
                "refusal": refusal, "detail": refusal["detail"],
                "record_ids": ids, "record_domains": domains}

    return {
        "armed": True, "workflow_id": workflow_id, "grant": grant, "refusal": None,
        "detail": (
            f"authorized by the open write grant for a batch review window: live review "
            f"writes for this whole sitting, bounded to the grant's {len(ids)} record "
            f"id(s) and {len(domains)} domain(s) — fixed at open time, never widened as "
            f"records are triaged."),
        "record_ids": ids, "record_domains": domains,
    }


def authorize_ungranted_send(config, *, lane, object_type, record_ids, record_domains,
                             allow_create, label, providers=None, transport=None,
                             preflight=None, today=None):
    """The per-send counterpart to `authorize_send`, for a send with NO standing grant
    open (F2, 2026-08-25, debug/resolved/walk-write-path-defects.md). Before this, an
    ungranted send's per-send "yes" (VOCAB-05 consent) armed the client's own POST only —
    it never reached `n8n_arming`, so `ALLOW_HUBSPOT_RECORD_WRITES` stayed false on the
    deployed workflow and every ungranted write returned `write_blocked` regardless of
    consent (executions 11934/11935/11937, F2's live proof). The operator's decision
    (2026-08-25, verbatim in the debug file): the per-send yes now opens a PER-SEND armed
    window scoped to that send's records, using the SAME machinery a standing grant uses.

    Composes `plan_grant()` + `open_grant(proposal, "yes", config)` into a single-lane,
    single-use grant scoped to EXACTLY this send's records, and returns the identical
    `{armed, workflow_id, grant, refusal, detail}` shape `authorize_send` returns — a lane
    skill's dispatch code branches on `decision["armed"]` the same way whichever function
    produced it.

    WHY plan_grant()/open_grant() RATHER THAN A LIGHTER HAND-BUILT GRANT DICT. Composing
    the real functions is what gives this path the SAME guardrails a standing grant gets,
    for free, rather than as a second implementation to keep in sync:

    * Authority — `plan_grant`'s own `config_gate.write_grants_enabled(config)` check.
      No new settings key: the admin's existing `allow_write_grants: true` is what turns
      this path on, exactly as it does for a standing grant.
    * Guardrail A (the dirty-backend refusal) — `plan_grant` calls it internally, at THE
      MOMENT OF THIS SEND (there is no earlier "plan" turn on this path the way a
      standing grant has one), so a backend a previous session left armed is caught here
      too, not only under a grant.
    * Scope — the proposal (and the grant `open_grant` returns) covers ONLY the record
      ids/domains this send names, so `armed_window`'s own scope check (`covers`, via
      `arm_for_dispatch`'s grant branch) narrows it no further than it already is.

    Guardrail B (the failed-disarm loud report) needs NOTHING extra here: it lives in
    `n8n_arming.armed_window.__exit__`'s `DisarmFailed` raise, which fires unconditionally
    on any window regardless of what authorized it. What does NOT carry over from a
    standing grant is `consecutive_disarm_failures` accumulation — that counter lives on
    a grant object across MULTIPLE sends, and this grant is used for exactly one before
    being discarded, so it never has a second send to accumulate a failure against.

    THE GRANT THIS RETURNS IS NEVER REMEMBERED. The caller uses it for exactly one
    `armed_window` call and then discards it — never held open for a later send, never
    treated as a standing grant an operator could later revoke by name, never written to
    disk (GRANT-06, unchanged: this function calls nothing that writes anything).

    `n8n_arming.arm_for_dispatch`/`_arm_gate`/`authorize_send` are UNTOUCHED by this
    function's existence — the headless env-var gate (`scheduled_arm.py` and everything
    that calls `arm_for_dispatch` with no `grant` argument) stays exactly as it was.

    `record_ids`/`record_domains` are THIS SEND's records — never a wider batch — the
    same narrowing rule `authorize_send` already documents.
    """
    proposal = plan_grant(
        config, lanes=[lane], object_type=object_type, record_ids=record_ids,
        record_domains=record_domains, allow_create=allow_create, label=label,
        providers=providers, transport=transport, preflight=preflight, today=today)
    if proposal.get("kind") != PROPOSAL_KIND:
        # plan_grant's own refusal (authority, empty record set, an unresolved workflow,
        # or Guardrail A) — relayed verbatim, never re-worded into a second message.
        return {"armed": False, "workflow_id": None, "grant": None,
                "refusal": proposal, "detail": proposal.get("detail")}

    grant = open_grant(proposal, "yes", config)
    if grant.get("kind") != KIND:
        return {"armed": False, "workflow_id": None, "grant": None,
                "refusal": grant, "detail": grant.get("detail")}

    ids = _normalise(record_ids)
    domains = _normalise(record_domains)
    return {
        "armed": True, "workflow_id": (grant.get("workflow_ids") or {}).get(lane),
        "grant": grant, "refusal": None,
        "detail": (
            f"authorized by a one-time window for this send only: live writes for this "
            f"send, bounded to this send's {len(ids)} record id(s) and {len(domains)} "
            f"domain(s) — never wider, and discarded once this dispatch finishes."),
    }


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


def record_dispatch_outcome(grant, outcome, config=None, *, disarm=None, transport=None,
                            reason=None):
    """The adapter that turns a real `chunking.DispatchOutcome` into the
    `record_send_outcome` call D-57-01 requires (Pitfall 1, REVIEW-57-H8/M5/M7).

    Builds `{"ceiling_breach": outcome.ceiling_stop is not None, "disarm": disarm}` and
    delegates to the EXISTING `record_send_outcome` — no second close path, no second
    outcome vocabulary. It exists so the producer is reachable from a pytest-driven
    dispatch rather than only from SKILL.md prose; the `ceiling_breach` computation
    belongs here, never duplicated into a skill.

    `reason`, keyword-only (Task 4, REVIEW-57-M7): when supplied, it OVERRIDES the
    derived `ceiling_breach` reading and closes the grant with exactly that reason. An
    explicit `reason=write_grant.CLOSED_UNHANDLED_ERROR` from a runbook's `except` arm
    must never be relabelled a budget stop just because the `outcome` it caught also
    happens to carry a `ceiling_stop` — the override wins.

    `outcome=None` is accepted for exactly the circumstance this exists to cover
    (REVIEW-57-M5): an exception raised INSIDE `dispatch_plan` before it returns —
    `enrichment.build_envelope`, or the transport itself — leaves no outcome object to
    inspect at all. A caller in that state still needs to close the grant with its own
    explicit `reason`; requiring a real outcome here would make the crash-recovery path
    itself raise `UnboundLocalError`-shaped failures, in the one circumstance closing the
    grant matters most.
    """
    if reason is not None:
        return close_grant(grant, reason)

    ceiling_stop = getattr(outcome, "ceiling_stop", None) if outcome is not None else None
    payload = {"ceiling_breach": ceiling_stop is not None, "disarm": disarm}
    return record_send_outcome(grant, payload, config, transport=transport)


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

# The flags that actually enable a write. TEST_RECORD_IDS / TEST_RECORD_DOMAINS bound a
# write that is already enabled; they cannot enable one on their own (the deployed
# `_writeSafetyAllows` denies everything on an empty allowlist), so they are REPORTED by
# guardrail A rather than treated as an armed state.
#
# D-60-01 CONSEQUENCE (2026-09-01): review became grantable (LANES above), so a stuck-open
# review authorization is now exactly the kind of state guardrail A exists to find — and a
# two-flag tuple was structurally unable to find it. `"ALLOW_HUBSPOT_REVIEW_WRITES"` is
# APPENDED LAST, never inserted or reordered: `_live_write_faults` builds `live_flags` by
# iterating this tuple in order, and an existing test
# (`test_an_open_over_a_live_armed_backend_refuses_and_names_what_it_found`) asserts that
# list exactly as `["ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"]` when the review
# flag reads disabled. Order here is load-bearing.
WRITE_ENABLING_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE",
                        "ALLOW_HUBSPOT_REVIEW_WRITES")

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

    Reads through `n8n_read.get_workflow` + `n8n_read.read_write_safety` over ALL FIVE
    `n8n_arming.OVERLAYABLE_FLAGS` — the shipped reader, never a second declaration regex.
    Uniform per lane, not lane-keyed (D-60-01 consequence, 2026-09-01): every deployed cloud
    workflow built from the shared write-safety gate declares all five constants regardless
    of which ones it branches on — verified against the committed enrichment, contacts and
    review workflow JSON — so reading all five on every lane is not overreach onto lanes
    that predate review, it matches deployed reality on lanes that existed before it too.

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
        for flag in sorted(n8n_arming.OVERLAYABLE_FLAGS):
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
            f"{', '.join(f'{flag}={flags.get(flag)!r}' for flag in sorted(n8n_arming.OVERLAYABLE_FLAGS))}."
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

    D-60-06/MEDIUM-1 AMENDMENT (Phase 60, cross-AI review, 2026-09-01). Task 1 widened
    `WRITE_ENABLING_FLAGS` to include `ALLOW_HUBSPOT_REVIEW_WRITES` so Guardrail A could see
    a stuck-open review authorization at the NEXT grant open. But `authorize_review_batch`'s
    own batch window arms that SAME flag for the length of a whole triage sitting — and an
    un-narrowed pre-flight called mid-batch on the review lane would read the window's OWN
    arm as "writes still live", close the grant, disarm mid-batch and refuse the very send
    it exists to authorize. So ON THE REVIEW LANE ONLY, liveness here is evaluated over the
    DISPATCH flags alone (`WRITE_ENABLING_FLAGS` with the review flag excluded) — DERIVED
    from that tuple below, never a second literal list, so the two can never drift. This
    exclusion is scoped narrowly: a live DISPATCH flag found on the review workflow is
    still a genuine anomaly and still closes the grant exactly as before; only the review
    flag itself is excluded, and only when `lane == REVIEW_LANE`. What this pre-flight gives
    up in exchange — noticing a review flag left live BETWEEN sittings — is not lost: that
    is Guardrail A's job at the next grant open (refusing there costs nothing), and a review
    flag left live WITHIN a sitting is still covered by the batch window's own guaranteed
    disarm (`armed_window.__exit__`). With the exclusion in place, calling this pre-flight
    on the review lane mid-batch is harmless rather than forbidden — see
    `authorize_review_batch`'s docstring for the window this guards.
    """
    granted = (grant or {}).get("workflow_ids") or {}
    workflow_ids = {lane: granted[lane]} if lane in granted else {}

    enabling_flags = tuple(flag for flag in WRITE_ENABLING_FLAGS
                           if flag != "ALLOW_HUBSPOT_REVIEW_WRITES") \
        if lane == REVIEW_LANE else WRITE_ENABLING_FLAGS

    state = read_live_write_state(config, workflow_ids, transport)
    live = {name: reading for name, reading in state.items()
            if any(_enabled((reading.get("flags") or {}).get(flag))
                   for flag in enabling_flags)}
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
