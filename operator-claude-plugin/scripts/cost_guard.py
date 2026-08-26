"""operator-claude-plugin/scripts/cost_guard.py

PREVIEW-02's arithmetic half: what a batch will cost, what is actually left, and the
honest third answer when the second question cannot be answered.

Three pieces, in order:

1. **The rate table** (`config/cost_rates.json`) is plugin-local and dated. Its numbers
   are literals copied from this repo's measured actuals at implementation time — never
   a runtime read of a `docs/` or planning path, because a runtime coupling to a planning
   path has already broken once here (D-09). `rate_table_age_days()` takes a reference
   date rather than reading the clock, so staleness is displayable and testable (D-08).

2. **The balance read** goes through `backend_status.fetch_backend_status()`, the one
   client this plugin has for the n8n-side `hubspot/backend-status` endpoint. The plugin
   holds no provider credential and never constructs a provider request (D-10). Every
   failure path — unreachable, non-2xx, unparseable body, a provider simply absent from
   the response — resolves to that provider being *unreadable*, with a short synthesized
   reason. There is no numeric fallback anywhere in this file: a defaulted number would
   be indistinguishable from a real balance, which is the whole of D-10.

3. **The comparison** is tri-state and branches on readability BEFORE magnitude. A
   balance that could not be read is `unknown`; a balance that is genuinely zero is
   `insufficient`. Those are different answers and this account produces the first one
   routinely — Apollo exposes no credit pool at all (its usage endpoint returns
   per-endpoint rate limits, not a depleting balance), so `unknown` is the common case,
   not the edge case. Rendering it as zero would be a standing false alarm that trains
   the operator to ignore the warning entirely.
"""
import json
from datetime import date
from pathlib import Path

import backend_status
import config_gate

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RATES_PATH = PLUGIN_ROOT / "config" / "cost_rates.json"

# The three canonical providers the status endpoint probes unconditionally. A provider
# missing from a response is unreadable, never absent-and-therefore-free.
PROVIDERS = ("lusha", "apollo", "zoominfo")

# Which rate each provider bills at, per object type. Lusha prices companies and contacts
# differently; ZoomInfo and Apollo bill one per-match rate for both.
#
# ponytail: the estimator always uses Lusha's FIRST-TIME contact rate, never the
# stored-id re-enrich rate (a measured 0). A re-enrich of an already-known contact bills
# nothing, so this over-states rather than under-states — the safe direction for a guard.
PROVIDER_RATE_KEYS = {
    "lusha": {"contacts": "lusha_contacts_first_time_enrich",
              "companies": "lusha_companies_match"},
    "zoominfo": {"contacts": "zoominfo_per_match", "companies": "zoominfo_per_match"},
    "apollo": {"contacts": "apollo_per_match", "companies": "apollo_per_match"},
}

ANTHROPIC_RATE_KEY = "anthropic_usd_per_record"

# The rate key for backend domain research (D-58-08/09) -- unmeasured, ships null, same
# apollo_per_match precedent estimate_batch already leans on.
RESEARCH_RATE_KEY = "company_domain_research"


class CostRateError(Exception):
    """Raised when the plugin's rate table is missing or unreadable. Names the file."""


# ------------------------------------------------------------------------- rate table


def load_rates(path=None) -> dict:
    """Load the plugin-local rate table. Resolves relative to the plugin root, the same
    way config_gate resolves its own file."""
    rates_path = Path(path) if path is not None else DEFAULT_RATES_PATH

    if not rates_path.exists():
        raise CostRateError(
            f"Cost rate table not found at {rates_path}. It ships with the plugin — if "
            "it is missing, the install is incomplete; reinstall rather than estimating "
            "without it."
        )
    try:
        table = json.loads(rates_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise CostRateError(
            f"Cost rate table at {rates_path} could not be parsed as JSON."
        ) from None

    if not isinstance(table.get("rates"), dict) or not table.get("measured_on"):
        raise CostRateError(
            f"Cost rate table at {rates_path} is missing its 'rates' or 'measured_on' "
            "field, so no estimate from it could be dated."
        )
    return table


def rate_table_age_days(table: dict, reference_date) -> int:
    """How old the rates are, against a supplied reference date.

    The clock is a parameter, not an internal read — so the number is testable and the
    preview can state it plainly (D-08). A stale table must read as stale, not as fact.
    """
    if isinstance(reference_date, str):
        reference_date = date.fromisoformat(reference_date)
    return (reference_date - date.fromisoformat(table["measured_on"])).days


def _rate_entry(table: dict, key: str) -> dict:
    return (table.get("rates") or {}).get(key) or {}


# --------------------------------------------------------------------------- estimate


def estimate_batch(record_count, object_type: str, providers, rates: dict) -> dict:
    """What this batch is expected to cost, per provider plus the model chain.

    `record_count` of None is the backend-resolved list case (D-02): the client cannot
    count the records, so every figure is reported unknown rather than computed against
    an invented number.

    A provider whose rate is unknown (Apollo, on this account) yields an unknown credit
    figure — never zero. `known` is the flag callers branch on; `credits` is None in
    exactly the cases where `known` is False.
    """
    count_known = isinstance(record_count, int) and record_count >= 0
    object_type = "companies" if object_type == "companies" else "contacts"

    provider_credits = {}
    for provider in (providers or []):
        name = str(provider).lower()
        rate_key = (PROVIDER_RATE_KEYS.get(name) or {}).get(object_type)
        if rate_key is None:
            continue
        entry = _rate_entry(rates, rate_key)
        rate = entry.get("value")
        known = rate is not None and count_known
        provider_credits[name] = {
            "credits": rate * record_count if known else None,
            "known": known,
            "rate": rate,
            "unit": entry.get("unit"),
            "confidence": entry.get("confidence"),
            "citation": entry.get("citation"),
        }

    anthropic_rate = _rate_entry(rates, ANTHROPIC_RATE_KEY).get("value")
    anthropic_known = anthropic_rate is not None and count_known

    return {
        "record_count": record_count if count_known else None,
        "record_count_known": count_known,
        "object_type": object_type,
        "providers": sorted(provider_credits),
        "provider_credits": provider_credits,
        "anthropic_usd": anthropic_rate * record_count if anthropic_known else None,
        "anthropic_usd_per_record": anthropic_rate,
        "rates_version": rates.get("version"),
        "rates_measured_on": rates.get("measured_on"),
    }


# --------------------------------------------------------------------- domain research


def research_line(rows, rates: dict) -> dict:
    """Price backend domain research for a set of company rows needing it (D-58-08/09).

    `rows` is expected to be the SAME needs-research row set a caller's decision
    structure (`company_domain.needs_research`) already named -- this function does not
    derive that set itself, it only prices whatever it is handed, so the priced count
    and the decided count can never silently diverge into two different numbers.

    Zero rows and an unmeasured rate are two DIFFERENT kinds of nothing, checked in that
    order: zero rows means no company needs it (checked first, regardless of whether the
    rate is known); an unmeasured rate on a non-empty set means the price is genuinely
    unknown. Neither is ever rendered as a $0 figure -- inheriting `compare()`'s
    readability-before-magnitude discipline rather than reimplementing it.
    """
    rows = list(rows or [])
    entry = _rate_entry(rates, RESEARCH_RATE_KEY)
    rate = entry.get("value")
    count = len(rows)

    if count == 0:
        state = "no_rows"
        cost_usd = None
        line = "Domain research: no company needs it."
    elif rate is None:
        state = "unmeasured"
        cost_usd = None
        noun = "company" if count == 1 else "companies"
        line = f"Domain research: {count} {noun} -- cost not measured."
    else:
        state = "measured"
        cost_usd = rate * count
        noun = "company" if count == 1 else "companies"
        line = (
            f"Domain research: {count} {noun} × ${rate:,.2f}/company = "
            f"${cost_usd:,.2f}."
        )

    return {
        "count": count,
        "rows": rows,
        "row_ids": sorted((row.get("row_id") for row in rows), key=lambda v: (v is None, v)),
        "state": state,
        "known": state == "measured",
        "cost_usd": cost_usd,
        "rate": rate,
        "unit": entry.get("unit"),
        "confidence": entry.get("confidence"),
        "citation": entry.get("citation"),
        "line": line,
    }


# --------------------------------------------------------------------------- balances


def _all_unreadable(reason: str) -> dict:
    return {p: {"credits": None, "unreadable": True, "reason": reason} for p in PROVIDERS}


def fetch_balances(config: dict, transport=None) -> dict:
    """Remaining credits per provider, from the n8n-side status endpoint.

    Returns `{provider: {credits, unreadable, reason}}` for all three providers, always.
    Never raises, and never substitutes a number for a balance it could not read — an
    invented figure here is indistinguishable from a real one, which is the defect D-10
    exists to prevent.
    """
    # ponytail: backend_status.fetch_backend_status is the plugin's only status client
    # and already carries the secret header, the finite timeout and the transport seam.
    # Passing `transport` only when supplied keeps this function out of the send-shaped
    # set that test_retry_reuses_dispatch.py pins to exactly two entries (D-33).
    kwargs = {} if transport is None else {"transport": transport}
    result = backend_status.fetch_backend_status(config, **kwargs)

    if not result.get("available"):
        return _all_unreadable(result.get("reason") or "status_endpoint_unavailable")

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    rows = data.get("balances") if isinstance(data.get("balances"), list) else []

    reported = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "").lower()
        if provider not in PROVIDERS:
            continue
        credits = row.get("credits")
        # Identity checks only — never a truthiness or magnitude test, both of which
        # collapse an unreadable balance into a zero-shaped one.
        unreadable = row.get("unreadable") is True or credits is None
        reported[provider] = {
            "credits": None if unreadable else credits,
            "unreadable": unreadable,
            "reason": row.get("error") if unreadable else None,
        }

    balances = _all_unreadable("not_reported_by_status_endpoint")
    balances.update(reported)
    for balance in balances.values():
        if balance["unreadable"] and not balance["reason"]:
            balance["reason"] = "unreadable"
    return balances


# -------------------------------------------------------------------------- comparison


def compare(estimate: dict, balances: dict) -> dict:
    """One verdict per estimated provider: `ok`, `insufficient` or `unknown`.

    Branch order is load-bearing. Readability first, then whether the estimate itself is
    known, and only then magnitude. Comparing an unreadable balance numerically is how an
    unknown becomes a confident wrong answer in either direction — a false insufficiency
    alarm, or a false clearance. Nothing below performs an arithmetic operation on a
    balance that has not first been established as readable.
    """
    verdicts = {}
    for provider, figure in (estimate.get("provider_credits") or {}).items():
        balance = (balances or {}).get(provider) or {}
        estimated = figure.get("credits") if figure.get("known") else None

        if balance.get("unreadable") is not False:
            reason = balance.get("reason") or "balance_not_reported"
            verdicts[provider] = _verdict(
                "unknown", estimated, None,
                f"remaining credits could not be read ({reason})",
            )
            continue

        if not figure.get("known"):
            verdicts[provider] = _verdict(
                "unknown", None, balance.get("credits"),
                "no measured rate for this provider, so the cost cannot be estimated"
                if figure.get("rate") is None else
                "the record count is resolved by the backend, so the cost cannot be "
                "estimated before dispatch",
            )
            continue

        remaining = balance.get("credits")
        sufficient = remaining >= estimated
        verdicts[provider] = _verdict(
            "ok" if sufficient else "insufficient", estimated, remaining,
            None if sufficient else
            f"estimated {estimated} credits exceeds the {remaining} remaining",
        )
    return verdicts


def _verdict(verdict, estimated, remaining, reason):
    return {"verdict": verdict, "estimated_credits": estimated,
            "remaining_credits": remaining, "reason": reason}


if __name__ == "__main__":
    _table = load_rates()
    _cfg = config_gate.load_config()
    _estimate = estimate_batch(None, "companies", [], _table)
    print(json.dumps({
        "rates_version": _table["version"],
        "rates_measured_on": _table["measured_on"],
        "rate_table_age_days": rate_table_age_days(_table, date.today()),
        "estimate": _estimate,
        "balances": fetch_balances(_cfg),
    }, indent=2))
