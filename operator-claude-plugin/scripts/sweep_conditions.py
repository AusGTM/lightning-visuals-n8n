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
"""

STUCK = "stuck_execution"
STUCK_AGE_UNREADABLE = "stuck_age_unreadable"
QUOTA_EXHAUSTED = "quota_exhausted"
CREDENTIAL_FAILURE = "credential_failure"

# The floor below which a provider's prepaid balance counts as exhausted. Zero is the
# only value guaranteed to mean "cannot buy one more lookup" without provider-specific
# pricing knowledge this module has no way to hold; an admin who wants headroom raises it
# via the `floor` parameter rather than this module guessing at one.
DEFAULT_QUOTA_FLOOR = 0


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


def evaluate(gathered, quota_floor=DEFAULT_QUOTA_FLOOR):
    """Every condition this slice knows, over one gather. 29-05 expands this list."""
    gathered = gathered or {}
    executions = gathered.get("executions") or {}
    backend = gathered.get("backend") or {}

    fired = []
    if executions.get("available"):
        fired.extend(check_stuck(executions.get("summaries")))

    if backend.get("available"):
        fired.extend(check_quota_and_credentials(backend.get("data"), floor=quota_floor))

    return fired
