"""operator-claude-plugin/scripts/sweep_conditions.py

Pure functions over already-fetched data (29-03). No I/O, no clock, no client — the
import-graph guard depends on this module staying that way.

This slice ships exactly one condition: the stuck execution. It CONSUMES Phase 27's
already-computed verdict — the tri-state `stuck` key summarize_execution() put on each
summary, judged against stuck_threshold_minutes(config) — rather than re-deriving it.
There is no is_stuck() anywhere in the tree (D-14), and a second stuck definition that
drifts from Phase 27's is the exact failure 29-RESEARCH.md's Don't-Hand-Roll table names.

All three states survive end to end: True fires, False does not, and None — in flight
with a start time we could not read — fires its own distinct outcome. Rounding None down
to "fine" is the specific bug Phase 27 D-07b(i) exists to prevent: a run whose age we
cannot read is not a run that just started.

29-05 Task 1 adds quota-exhausted and credential-failure — NEW JUDGMENT over Phase 27's
existing credit-probe data (D-08a), not a new read. "Unknown" and "exhausted" both look
like "can't rely on this provider" but mean opposite things and need opposite attribution,
so the outcome is explicit rather than a boolean plus a convention: `"exhausted"` /
`"ok"` / `"unknown"` / `"not_configured"` for quota (the fourth state, D-22, is a provider
never probed at all — absent from `balances` entirely) and `True`/`False`/`None` for a
credential refusal. `DEFAULT_QUOTA_FLOOR = 0` (documented at its definition) is a
parameter, not a hardcode, so an admin who wants headroom above zero has somewhere to put
it.

29-05 Task 2 adds failed-scheduled-run, review-backlog and D-10's stuck-armed backstop:

Failed-scheduled-run and review-backlog reuse Phase 27's read surface unmodified, plus
the maintenance workflow's swallowed-failure blind spot (D-08b): its own HubSpot-Search
nodes are `onError: continueRegularOutput` (D-21), so a run reporting `success` is not
evidence the search underneath it worked. That needs `runData`, which `sweep_read.gather`
fetches for the maintenance workflow's most recent execution only (D-17) via
`n8n_read.get_execution` + `execution_errors.harvest_errors` — both pure over
already-fetched data, so importing them here does not reach a write path.

Stuck-armed is the backstop for Phase 28 D-03's arm/disarm crash window. `WRITE_SAFETY_
FLAGS` below is `status.WRITE_SAFETY_FLAGS` copied verbatim rather than imported:
`status.py` supplies `requests.post` as a default parameter value, and importing it would
pull a second write-verb site into this module's closure — widening test_sweep_read_
only.py's D-13 exception from one POST site to two for no reason. Both flags are checked
(D-16: they are a PAIR over different node subsets), and a truthy `disagreement` fires
rather than being swallowed as unknown — that disagreement IS the residue a crash between
arm and disarm leaves, which is exactly what this backstop exists to catch.
"""
import n8n_read

STUCK = "stuck_execution"
STUCK_AGE_UNREADABLE = "stuck_age_unreadable"
QUOTA_EXHAUSTED = "quota_exhausted"
CREDENTIAL_FAILURE = "credential_failure"
FAILED_RUN = "failed_scheduled_run"
REVIEW_BACKLOG = "review_backlog"
SWALLOWED_MAINTENANCE_FAILURE = "swallowed_maintenance_failure"
STUCK_ARMED = "stuck_armed"
BURN_RATE = "burn_rate_alarm"
BURN_RATE_NOT_CONFIGURED = "burn_rate_not_configured"
BURN_RATE_UNREADABLE = "burn_rate_unreadable"

# The floor below which a provider's prepaid balance counts as exhausted. Zero is the
# only value guaranteed to mean "cannot buy one more lookup" without provider-specific
# pricing knowledge this module has no way to hold; an admin who wants headroom raises it
# via the `floor` parameter rather than this module guessing at one.
DEFAULT_QUOTA_FLOOR = 0

# How many records awaiting review counts as a backlog rather than a normal queue depth.
# 25 is a conservative starting point pending observed volume — unlike
# n8n_read.DEFAULT_STUCK_MINUTES (also a documented starting point, not a measured value)
# there is no batch-timing precedent to derive this from yet. Raise it via the
# `threshold` parameter once real volume is known.
DEFAULT_REVIEW_BACKLOG_THRESHOLD = 25

# Copied verbatim from status.WRITE_SAFETY_FLAGS (status.py:23) — not imported, per the
# module docstring above.
WRITE_SAFETY_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")

# n8n's documented terminal execution statuses that mean the run did not succeed.
# "canceled" is excluded on purpose: an operator- or admin-cancelled run is not the same
# condition as one that failed on its own.
FAILED_STATUSES = frozenset({"error", "crashed"})

# Fire when rate x 30d > allowance x threshold. 1.0 default: the idle floor is ~95/month
# (~4% of a 2,500/month plan), so any real anomaly clears 1.0 by an order of magnitude —
# the key exists for tightening later, not because 1.0 is marginal (D-06).
DEFAULT_BURN_RATE_THRESHOLD = 1.0


def check_stuck(summaries):
    """Fired-condition dicts for every summary whose stuck verdict is True or None."""
    fired = []
    for summary in summaries or []:
        if not isinstance(summary, dict):
            continue
        verdict = summary.get("stuck")
        if verdict is False:
            continue
        if verdict is True:
            fired.append({
                "condition": STUCK,
                "execution_id": summary.get("execution_id"),
                "workflow_name": summary.get("workflow_name"),
                "running_for_minutes": summary.get("running_for_minutes"),
                "threshold_minutes": summary.get("stuck_threshold_minutes"),
                "reason": (
                    f"a run of {summary.get('workflow_name') or 'an unnamed workflow'} "
                    f"has been going for about "
                    f"{round(summary.get('running_for_minutes') or 0)} minutes — past "
                    f"the {summary.get('stuck_threshold_minutes')}-minute point where a "
                    f"run counts as wedged"),
            })
        elif verdict is None and summary.get("in_flight"):
            fired.append({
                "condition": STUCK_AGE_UNREADABLE,
                "execution_id": summary.get("execution_id"),
                "workflow_name": summary.get("workflow_name"),
                "running_for_minutes": None,
                "threshold_minutes": summary.get("stuck_threshold_minutes"),
                "reason": (
                    f"a run of {summary.get('workflow_name') or 'an unnamed workflow'} "
                    f"is in flight but its age could not be read, so whether it is "
                    f"wedged is unknown — unknown is not fine"),
            })
    return fired


def _balance_row(provider, balances):
    for row in balances or []:
        if isinstance(row, dict) and row.get("provider") == provider:
            return row
    return None


def _health_row(provider, credential_health):
    for row in credential_health or []:
        if isinstance(row, dict) and row.get("source") == provider:
            return row
    return None


def classify_quota(provider, balances, credential_health, floor=DEFAULT_QUOTA_FLOOR):
    """One provider's quota state against `floor` credits.

    Returns one of four explicit outcomes rather than a boolean plus a convention — a
    function that can only answer yes/no forces the caller to invent a representation
    for "unknown", which is exactly how unknown quietly becomes false:

    - `"exhausted"` — a real number at or below `floor`.
    - `"ok"` — a real number above it.
    - `"unknown"` — probed but unreadable (Apollo's 403-by-design, or a transient
      `no_response`). Never reported as exhausted, never as healthy (D-08).
    - `"not_configured"` — never probed at all. D-22 found this LIVE as a fourth, distinct
      state: the provider is absent from `balances` entirely (that node only maps over
      REQUESTED providers) and named only in `credential_health` as
      `{state: unknown, reason: not_configured}`. Reading only `balances` would make this
      state invisible, so it is confirmed via `credential_health` rather than guessed from
      an absence alone.
    """
    health = _health_row(provider, credential_health)
    if health is not None and health.get("state") == "unknown" and health.get("reason") == "not_configured":
        return "not_configured"

    balance = _balance_row(provider, balances)
    if balance is None:
        return "not_configured"

    credits = balance.get("credits")
    if credits is None:
        return "unknown"

    return "exhausted" if credits <= floor else "ok"


def classify_credential(provider, credential_health):
    """One provider's credential state, classified from the SHAPE of the probe result
    rather than from a provider's prose message (which varies and changes):

    - `True` — refused. The backend positively identified an auth signature (e.g.
      Apollo's by-design 403).
    - `False` — ok. A working credential, whatever the balance underneath it reads.
    - `None` — unknown. The backend could not tell — `no_response` is a REAL live state
      distinct from an invalid credential (verified live 2026-08-03) and must degrade to
      unknown rather than firing as "credentials broken" (Phase 27 D-05's guardrail: an
      honest "I cannot tell" beats a confident wrong cause).
    """
    health = _health_row(provider, credential_health)
    if health is None:
        return None
    state = health.get("state")
    if state == "refused":
        return True
    if state == "ok":
        return False
    return None


def check_quota_and_credentials(backend_data, floor=DEFAULT_QUOTA_FLOOR):
    """Fired conditions for exhausted quota and credential failure, one provider at a
    time. Both attribute to an admin downstream (error_table's unmatched-cause guardrail):
    provider credentials live in n8n by design (REQUIREMENTS.md's credential boundary), so
    neither is something the operator can act on themselves.

    A zero balance with a working credential classifies as `"exhausted"` from
    `classify_quota` and `False` (ok) from `classify_credential` — exhausted and broken
    carry different remedies, and conflating them would send an admin to renew a
    credential that was never the problem.
    """
    data = backend_data or {}
    balances = data.get("balances") or []
    credential_health = data.get("credential_health") or []
    providers = sorted(
        {row.get("provider") for row in balances if isinstance(row, dict) and row.get("provider")}
        | {row.get("source") for row in credential_health if isinstance(row, dict) and row.get("source")}
    )

    fired = []
    for provider in providers:
        quota_state = classify_quota(provider, balances, credential_health, floor=floor)
        if quota_state == "exhausted":
            balance = _balance_row(provider, balances) or {}
            fired.append({
                "condition": QUOTA_EXHAUSTED,
                "provider": provider,
                "reason": (
                    f"{provider}'s prepaid balance has reached {balance.get('credits')} "
                    f"credits, at or below the {floor}-credit floor — no further lookups "
                    f"can be made against it until it is topped up"),
            })

        if classify_credential(provider, credential_health) is True:
            fired.append({
                "condition": CREDENTIAL_FAILURE,
                "provider": provider,
                "reason": (
                    f"{provider}'s saved credential was refused by the backend, so "
                    f"nothing can be looked up from it until the credential is renewed"),
            })

    return fired


def check_failed_run(summaries):
    """Fired conditions for a scheduled run in a documented terminal-failure status.

    This is the ordinary case where the execution's own status already says it failed —
    distinct from check_swallowed_maintenance_failure, which is the case where the status
    says success and is wrong.
    """
    fired = []
    for summary in summaries or []:
        if not isinstance(summary, dict):
            continue
        if summary.get("status") in FAILED_STATUSES:
            fired.append({
                "condition": FAILED_RUN,
                "execution_id": summary.get("execution_id"),
                "workflow_name": summary.get("workflow_name"),
                "reason": (
                    f"a run of {summary.get('workflow_name') or 'an unnamed workflow'} "
                    f"ended in status {summary.get('status')!r} rather than succeeding"),
            })
    return fired


def check_review_backlog(counts, threshold=DEFAULT_REVIEW_BACKLOG_THRESHOLD):
    """Fires when companies + contacts awaiting review exceeds `threshold`.

    Either sub-count being unreadable (`None`) skips firing rather than treating the
    unreadable half as zero (D-08) — a genuine 0 stays 0, but an unknown half must not
    silently shrink the total.
    """
    counts = counts or {}
    companies = counts.get("companies_awaiting_review")
    contacts = counts.get("contacts_awaiting_review")
    if companies is None or contacts is None:
        return []

    total = companies + contacts
    if total <= threshold:
        return []

    return [{
        "condition": REVIEW_BACKLOG,
        "reason": (
            f"{total} records are waiting for human review (companies {companies}, "
            f"contacts {contacts}) — past the {threshold}-record point where the queue "
            f"counts as backed up"),
    }]


def check_swallowed_maintenance_failure(maintenance_errors):
    """D-08b's blind spot: the maintenance workflow's own HubSpot-Search nodes are
    `onError: continueRegularOutput`, so a run reporting `success` is not evidence the
    search underneath it worked. `maintenance_errors` is `execution_errors.harvest_errors`'s
    own `{available, reason, findings}` over the maintenance workflow's most recent
    execution (fetched by sweep_read.gather, gated per D-17 — never for every execution
    in the page).

    `available: False` here is a read that could not happen (no recent execution to check,
    or the fetch failed) and does NOT fire — it is neither evidence of health nor a claim
    otherwise, the same D-15 degrade-rather-than-assert rule 29-03 established one layer
    up. What this condition can and cannot see is stated in its own notice text: it only
    ever inspects the single MOST RECENT maintenance execution, so an older swallowed
    failure would not be caught here.
    """
    maintenance_errors = maintenance_errors or {}
    if not maintenance_errors.get("available"):
        return []

    findings = maintenance_errors.get("findings") or []
    if not findings:
        return []

    causes = "; ".join(sorted({
        finding.get("sentence") or finding.get("raw") or "an unrecognised failure"
        for finding in findings if isinstance(finding, dict)
    }))
    return [{
        "condition": SWALLOWED_MAINTENANCE_FAILURE,
        "reason": (
            f"the scheduled maintenance run reported success, but one of its own search "
            f"nodes recorded a failure the run status hides: {causes}. This check only "
            f"sees the workflow's single most recent execution — an older swallowed "
            f"failure would not be caught here"),
    }]


def _workflow_in_flight(workflow_id, executions_summaries):
    return any(
        isinstance(summary, dict)
        and summary.get("workflow_id") == workflow_id
        and summary.get("in_flight")
        for summary in executions_summaries or []
    )


def check_stuck_armed(workflows, executions_summaries):
    """D-10: the backstop for Phase 28 D-03's arm/disarm crash window.

    Checks BOTH of `WRITE_SAFETY_FLAGS` (D-16 — they are a pair over different node
    subsets, not one flag) via `n8n_read.read_write_safety`, and fires when either reads
    armed with nothing dispatching against it, OR when either reads a truthy
    `disagreement` — a partially-armed workflow is exactly the residue a crash between arm
    and disarm leaves, so treating it as "unknown, therefore quiet" would blind this
    backstop to its own headline case.

    The in-flight discriminator is data the sweep already has (the executions summaries'
    `workflow_id` + `in_flight`), never a new read — an armed flag with a live dispatch
    running on its lane is a normal in-progress batch, not a stuck one. Getting this wrong
    in the noisy direction is the worse failure: a sweep that cries stuck-armed during
    every normal dispatch is a sweep the operator learns to ignore.

    `workflows` is `sweep_read.gather`'s `{"available": bool, "items": [...]}` shape. A
    workflow item missing a `nodes` list (an unreadable body) is skipped rather than
    guessed at — write-safety stays unknown for it, never assumed disarmed.
    """
    fired = []
    for workflow in (workflows or {}).get("items") or []:
        if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
            continue

        workflow_id = workflow.get("id")
        workflow_name = workflow.get("name") or "a backend workflow"
        in_flight = _workflow_in_flight(workflow_id, executions_summaries)

        for flag in WRITE_SAFETY_FLAGS:
            result = n8n_read.read_write_safety(workflow, flag)
            armed = result.get("value") == "true"
            disagreement = bool(result.get("disagreement"))

            if not armed and not disagreement:
                continue
            if in_flight:
                continue

            if disagreement:
                nodes = ", ".join(entry.get("node") or "an unnamed node"
                                  for entry in result["disagreement"])
                reason = (
                    f"{flag}'s declaring nodes on {workflow_name} disagree with each "
                    f"other ({nodes}) — a partial arm or disarm, the exact residue a "
                    f"crash between arm and disarm leaves")
            else:
                reason = (
                    f"{flag} is armed on {workflow_name} with nothing currently "
                    f"dispatching against it — this is the crash-window backstop Phase "
                    f"28 named this sweep for")

            fired.append({
                "condition": STUCK_ARMED,
                "workflow_name": workflow_name,
                "flag": flag,
                "reason": reason + ("; check and disarm it from the backend-control "
                                    "skill rather than editing the workflow directly"),
            })

    return fired


def _parsed_burn_rate_threshold(execution_budget, default):
    """Mirrors n8n_read.stuck_threshold_minutes exactly, including its rationale: a
    status read must not fail because a config value was typed wrong. Configuration
    first, the documented default on missing, blank, unparseable or non-positive.

    WR-03: `bool` is an `int`/`float` subclass in Python, so a misconfigured
    `"burn_rate_alarm_threshold": true` would otherwise silently parse as `1.0` rather
    than degrading to the default like any other unusable value -- the same gotcha
    `tests/test_execution_budget_drift.py` already guards the static config artifacts
    against. Checked before the float() call, not after: `float(True) == 1.0` succeeds,
    so `isinstance(..., bool)` is the only place this can be caught."""
    value = (execution_budget or {}).get("threshold")
    if isinstance(value, bool):
        return default
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


# CR-01: a rate sampled over a span this short cannot support a 30-day extrapolation at
# all, regardless of what it projects to — a handful of executions with no anchoring
# older item is not evidence of a sustained rate. One hour is a starting point, not a
# measured value, same footing as DEFAULT_STUCK_MINUTES / DEFAULT_REVIEW_BACKLOG_THRESHOLD
# elsewhere in this module.
MIN_SAMPLE_SPAN_HOURS = 1.0


def _burn_rate_span_clause(window, window_hours):
    """The span clause is honest about WHY it is short (D-01) — three cases, three
    different sentences, so a reader never confuses a pruning-shrunk window with a
    sweep-imposed read bound.

    CR-01: the third case (`covers_full_window` False, `truncated_by_page_cap` False)
    means the walk read every execution n8n has and none of it reaches back to the
    window's edge — but that is NOT evidence n8n pruned anything. A fresh deploy, a
    history wipe, or simply a quiet system that has not run window_hours worth of jobs
    yet reads identically from this function's inputs. Naming pruning unconditionally
    here was itself part of CR-01: a notice must never claim a cause it did not observe
    (D-01). Both possibilities are named, neither is asserted as the cause.
    """
    observed = window.get("observed_span_hours") or 0.0
    if window.get("covers_full_window"):
        return f"the full {window_hours:g}-hour window"
    if window.get("truncated_by_page_cap"):
        return (
            f"only the last {observed:.1f} hours — the sample stopped at this sweep's "
            f"own execution read bound, not pruning, so the span is shorter than the "
            f"{window_hours:g}-hour target")
    return (
        f"only the last {observed:.1f} hours — that is everything n8n's retained "
        f"execution history reaches back; nothing older is available. n8n's own pruning "
        f"could be why, or this could simply be a system with no older execution yet — "
        f"this read cannot tell the two apart, so neither is claimed")


def check_burn_rate(executions, execution_budget, threshold=DEFAULT_BURN_RATE_THRESHOLD):
    """Fires when the sampled n8n execution rate, projected over 30 days, would exceed
    `allowance x threshold` (ALARM-01, D-02 — anchor-free: n8n exposes no billing-cycle
    day, so a "for the current billing period" claim would be invented).

    `executions` is `sweep_read.gather`'s widened `{"available", "summaries", "window"}`
    dict; `execution_budget` is its `{"key", "allowance", "threshold_key", "threshold"}`
    dict of RAW config values — parsing happens here, never upstream, so this stays a
    pure function over already-fetched data.

    Precedence order (documented, not incidental):

    1. Allowance not usable (absent, blank, non-numeric, a `bool` (WR-03), or not
       strictly positive) -> `BURN_RATE_NOT_CONFIGURED`, naming the exact config key,
       never a value (this module inherits config_gate's names-only rule). With the
       allowance missing the check cannot run at all, so naming the missing key is the
       one actionable fact — adding "also could not read history" to it would be
       noise; the operator learns
       that fact on the next sweep. `sweep_entry` already short-circuits to its own
       `sweep_blind` notice when EVERY read failed, so this never double-reports that
       case.
    2. Executions unreadable (unavailable, or no window) -> `BURN_RATE_UNREADABLE`
       (ALARM-04). Checked second, only once the allowance is known usable.
    3. CR-01: the observed span is too short to anchor a 30-day extrapolation AND the
       sweep's own read did not stop it short (`not covers_full_window and not
       truncated_by_page_cap and observed_span_hours < MIN_SAMPLE_SPAN_HOURS`) -> `[]`,
       silently. This is deliberately NOT a fourth named condition: unlike
       not-configured/unreadable (both genuinely actionable — a missing key, a failed
       read), "not enough sample yet" is a normal transient state (first sweep after a
       deploy, a history wipe, a quiet system) that resolves itself within the hour and
       asks nothing of an operator or admin — a notice here would be exactly the noise
       NOTICE-04 warns turns a sweep into one the operator learns to ignore (D-15:
       silence is only a lie when something readable and actionable was suppressed).
       `truncated_by_page_cap` is excluded from this guard on purpose: a runaway rate
       fast enough to fill the whole page walk (T-45-02's 1,000-execution ceiling) inside
       an hour pins `observed_span_hours` below the guard for the ENTIRE duration of the
       burn — silencing that case would blind the alarm to the exact incident shape it
       exists for (D-01).
    4. Otherwise, compute and compare. The comparison is made on UNROUNDED floats;
       rounding happens only inside the rendered reason string via format specifiers,
       so a projection a fraction over the ceiling still fires (ALARM-01 precision).

    D-07: this condition deliberately RE-FIRES on every sweep while the burn persists —
    the one condition where repetition is the discipline, since an active burn costs
    money hourly. It is self-clearing: the rate is computed over a moving window, so it
    drops when the burn stops. That is what distinguishes it from LOOK-01's stale-history
    defect, where an already-fixed failure kept re-notifying about the past. No
    suppression is added here.
    """
    executions = executions or {}
    execution_budget = execution_budget or {}

    # WR-03: bool is an int/float subclass, so float(True) == 1.0 -- checked before the
    # float() call so a misconfigured "allowance": true degrades to not-configured
    # rather than silently becoming a real allowance of 1.0.
    allowance_raw = execution_budget.get("allowance")
    if isinstance(allowance_raw, bool):
        allowance = None
    else:
        try:
            allowance = float(allowance_raw)
        except (TypeError, ValueError):
            allowance = None
    if allowance is None or allowance <= 0:
        key_name = execution_budget.get("key") or n8n_read.EXECUTION_ALLOWANCE_KEY
        return [{
            "condition": BURN_RATE_NOT_CONFIGURED,
            "reason": (
                f"the sweep is not watching the n8n execution budget because {key_name} "
                f"is not configured (missing, blank, or not a positive number) — set it "
                f"following operator.local.example.json's shape to enable this check; "
                f"every other check in this sweep still ran"),
        }]

    window = executions.get("window")
    if not executions.get("available") or not window:
        return [{
            "condition": BURN_RATE_UNREADABLE,
            "reason": (
                "the execution history could not be read this sweep, so the burn rate "
                "is unknown — unknown is not fine"),
        }]

    resolved_threshold = _parsed_burn_rate_threshold(execution_budget, threshold)
    window_hours = window.get("window_hours") or n8n_read.DEFAULT_EXECUTION_WINDOW_HOURS
    count_in_window = window.get("count_in_window") or 0
    observed_span_hours = window.get("observed_span_hours") or n8n_read.MIN_OBSERVED_SPAN_HOURS

    if (not window.get("covers_full_window") and not window.get("truncated_by_page_cap")
            and observed_span_hours < MIN_SAMPLE_SPAN_HOURS):
        return []

    rate_per_hour = count_in_window / observed_span_hours
    projected = rate_per_hour * n8n_read.HOURS_PER_MONTH
    ceiling = allowance * resolved_threshold

    if projected <= ceiling:
        return []

    span_clause = _burn_rate_span_clause(window, window_hours)

    return [{
        "condition": BURN_RATE,
        "reason": (
            f"n8n execution rate sampled at {rate_per_hour:.1f} per hour over "
            f"{span_clause}, projecting to about {projected:.0f} executions over the "
            f"next 30 days against the {allowance:.0f}-execution monthly allowance "
            f"({resolved_threshold:g}x ceiling {ceiling:.0f}) — this is a sampled rate, "
            f"not a total for this month, because n8n prunes execution history and "
            f"exposes no usage figure to an API key"),
    }]


def evaluate(gathered, quota_floor=DEFAULT_QUOTA_FLOOR,
            review_backlog_threshold=DEFAULT_REVIEW_BACKLOG_THRESHOLD):
    """Every condition this slice knows, over one gather."""
    gathered = gathered or {}
    executions = gathered.get("executions") or {}
    backend = gathered.get("backend") or {}

    fired = []

    if executions.get("available"):
        summaries = executions.get("summaries")
        fired.extend(check_stuck(summaries))
        fired.extend(check_failed_run(summaries))
        # The in-flight discriminator only means something against a readable executions
        # page — gate stuck-armed on it too, rather than risk a false fire.
        fired.extend(check_stuck_armed(gathered.get("workflows"), summaries))

    if backend.get("available"):
        data = backend.get("data")
        fired.extend(check_quota_and_credentials(data, floor=quota_floor))
        fired.extend(check_review_backlog((data or {}).get("counts"),
                                          threshold=review_backlog_threshold))

    fired.extend(check_swallowed_maintenance_failure(gathered.get("maintenance_errors")))

    # OUTSIDE the executions.available gate on purpose: ALARM-04 (executions unreadable)
    # is unreachable by construction if this were nested inside that block (Phase 45).
    fired.extend(check_burn_rate(gathered.get("executions"), gathered.get("execution_budget")))

    return fired
