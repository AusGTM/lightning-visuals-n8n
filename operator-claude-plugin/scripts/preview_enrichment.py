"""operator-claude-plugin/scripts/preview_enrichment.py

The operator-facing half of the cost guard: the four blocks a batch cannot be launched
without reading first (PREVIEW-02, PREVIEW-03, D-02, D-06, D-08, D-10, D-11).

Four blocks, in the order the decision needs them:

1. **What is being enriched** — the exact record count for named IDs, or the list
   identifier with the count stated as backend-resolved. For a list the count is the word
   `unknown`, NEVER `0` and never a guess: the client does not resolve a list and does not
   count one (D-02, D-21). A preview built on something it cannot read must not render as
   "0 records" or "nothing to do".
2. **Which providers** — stated explicitly on every render, including the full-waterfall
   and the empty selections. The shipped default is permissive, which is exactly what makes
   the display mandatory rather than optional (D-06).
3. **What it will cost** — per provider in credits, plus the Anthropic dollar figure, with
   the rate table's date and age alongside so a stale table reads as stale (D-08). The
   copy says *at most*: the estimator always prices Lusha at the first-time rate, never the
   measured-zero stored-id rate, so it over-states deliberately.
4. **How it will be split** — the chunk count and the rows in each chunk, read off the
   very `ChunkPlan` dispatch will iterate. Never recomputed here; a preview whose plan is
   rebuilt at send time is not a contract (PREVIEW-03).

The balance line is where the tri-state has to survive contact with prose. A readable
balance below the estimate is a warning naming the provider. A readable **zero** is the
same warning shape, because zero is a real balance. An unreadable balance is neither: its
cell is the word `unknown`, never a numeral, and its warning says headroom could not be
*confirmed* — it is never a sentence that could be read as "you have enough". Apollo
returns rate limits rather than a credit pool, so unknown is that provider's NORMAL answer
and not a fault (D-10a); copy that treated it as an exception state would be a standing
false alarm on every run of the default waterfall.

Every function here is PURE: no network call, no dispatch, no write. Balances arrive as an
argument, so the preview renders identically whether or not the status endpoint answered —
a cost guard that disappears when the backend is down is a cost guard nobody can rely on.
"""
import json

import chunking
import cost_guard
import enrichment

# The word, borrowed rather than redeclared — a second spelling of "unknown" is a second
# thing to keep in step.
UNKNOWN = chunking.UNKNOWN

PROVIDER_LABELS = {"zoominfo": "ZoomInfo", "apollo": "Apollo", "lusha": "Lusha"}

_BLOCK_ORDER = ("records", "providers", "cost", "chunks")

# Why the tabular lane's figures are zero. A stated zero with its reason, not an omitted
# block (D-16): criterion 3 says every preview on both lanes, and this zero is real and
# explainable — unlike a balance that could not be read.
TABULAR_COST_REASON = (
    "This lane calls no enrichment provider and makes no model call — the rows go "
    "straight to `hubspot/contact-upload`, and enriching them is a separate step with "
    "its own preview and its own approval. So this is a real, explainable zero, not a "
    "balance that could not be read."
)


def _label(provider):
    return PROVIDER_LABELS.get(str(provider).lower(), str(provider))


# ------------------------------------------------------------------ block 1: records


def records_block(spec, plan):
    """What is about to be enriched. For a list: the identifier and the word `unknown`,
    with no numeral anywhere — the client has no count and must not invent one."""
    spec = spec or {}
    if spec.get("list"):
        return (
            f'**Records:** the HubSpot list "{spec["list"]}" '
            f'({spec.get("object_type") or "unknown object type"}) — record count: '
            f"**{UNKNOWN}**. The backend resolves the list and counts it; I do not, so "
            f"no number is shown here rather than a fabricated one."
        )
    count = getattr(plan, "record_count", UNKNOWN)
    if not isinstance(count, int):
        return (
            f"**Records:** record count: **{UNKNOWN}** — this batch could not be counted, "
            f"which is not the same as it being empty."
        )
    object_type = spec.get("object_type") or "record"
    return (
        f"**Records:** {count} {object_type}, named by ID. Nothing is structured or "
        f"uploaded — these already exist in HubSpot."
    )


# ---------------------------------------------------------------- block 2: providers


def providers_block(providers):
    """The resolved selection, stated every time (D-06) — including when it resolved to
    the whole waterfall and when it resolved to none."""
    providers = list(providers or [])
    if not providers:
        return (
            "**Providers:** none. No provider will be called for this batch, so no "
            "provider credits burn. This selection is still sent explicitly."
        )
    names = ", ".join(_label(p) for p in providers)
    full = set(p.lower() for p in providers) == set(enrichment.FULL_WATERFALL)
    suffix = " — the full waterfall, which is the shipped default" if full else ""
    return (
        f"**Providers:** {names}{suffix}. This selection is sent explicitly on every "
        f"request; the backend enables nothing when a request names nothing."
    )


# --------------------------------------------------------------------- block 3: cost


def zero_cost_estimate(record_count):
    """The tabular lane's estimate: no provider, no model call, a real zero.

    Shaped exactly like `cost_guard.estimate_batch()`'s result so it renders through the
    SAME helper below. Two cost blocks that can drift apart is the second-source-of-truth
    pattern this milestone avoids everywhere else (D-16).
    """
    return {
        "record_count": record_count,
        "record_count_known": isinstance(record_count, int),
        "providers": [],
        "provider_credits": {},
        "anthropic_usd": 0.0,
        "anthropic_usd_per_record": 0.0,
        "rates_version": None,
        "rates_measured_on": None,
    }


def _credits(value):
    if value is None:
        return UNKNOWN
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _usd(value):
    return UNKNOWN if value is None else f"${value:,.2f}"


def _estimated_cell(figure):
    if figure.get("known"):
        return _credits(figure.get("credits"))
    if figure.get("rate") is None:
        return f"{UNKNOWN} — no measured rate for this provider"
    return f"{UNKNOWN} — the backend resolves the record count"


def _remaining_cell(verdict):
    """The cell that must never show a numeral it did not read. `remaining_credits` is
    None on every unreadable branch (cost_guard.compare sets it so deliberately), and a
    genuine zero arrives here as the integer 0 and renders as `0`."""
    remaining = verdict.get("remaining_credits")
    if remaining is None:
        return f"{UNKNOWN} — could not be read"
    return _credits(remaining)


def _headroom_cell(verdict):
    return {
        "ok": "enough",
        "insufficient": "**NOT enough**",
    }.get(verdict.get("verdict"), "**could not be confirmed**")


def _cost_row(provider, figure, verdict):
    return (
        f"| {_label(provider)} | {_estimated_cell(figure)} | {_remaining_cell(verdict)} "
        f"| {_headroom_cell(verdict)} |"
    )


def _warnings(verdicts):
    lines = []
    unknown_providers = []
    for provider in sorted(verdicts or {}):
        verdict = verdicts[provider] or {}
        reason = verdict.get("reason") or "no reason was given"
        if verdict.get("verdict") == "insufficient":
            lines.append(
                f"- ⚠ **{_label(provider)}**: {reason}. This batch would run out of "
                f"credits partway through."
            )
        elif verdict.get("verdict") != "ok":
            unknown_providers.append(provider)
            lines.append(
                f"- ⚠ **{_label(provider)}**: {reason}. **Headroom could not be "
                f"confirmed** — this is not a report that there is enough."
            )
    if "apollo" in unknown_providers:
        lines.append(
            "- Apollo exposes per-endpoint rate limits rather than a depleting credit "
            "pool, so `unknown` is the normal answer there, not a fault to fix."
        )
    return lines


def cost_block(estimate, verdicts, rate_age_days=None, reason=None):
    """The cost block, shared by BOTH lanes.

    `estimate` is `cost_guard.estimate_batch()`'s result, or `zero_cost_estimate()` for a
    lane that spends nothing. `verdicts` is `cost_guard.compare()`'s result — empty when
    no provider is involved. `rate_age_days` is supplied, never read off the clock here,
    so the rendered text is deterministic.
    """
    estimate = estimate or {}
    lines = ["**Estimated cost — at most.**"]

    measured_on = estimate.get("rates_measured_on")
    if measured_on:
        age = f", {rate_age_days} days ago" if isinstance(rate_age_days, int) else ""
        lines.append(
            f"Rates measured **{measured_on}**{age}. Lusha is priced at its first-time "
            f"rate, never the measured-zero re-enrich rate, so these figures over-state "
            f"rather than under-state."
        )

    figures = estimate.get("provider_credits") or {}
    if figures:
        lines += [
            "",
            "| Provider | Estimated credits | Credits remaining | Headroom |",
            "|---|---|---|---|",
        ]
        lines += [
            _cost_row(provider, figures[provider], (verdicts or {}).get(provider) or {})
            for provider in sorted(figures)
        ]
    else:
        lines.append("No provider credits: **0**.")

    lines.append("")
    anthropic = estimate.get("anthropic_usd")
    per_record = estimate.get("anthropic_usd_per_record")
    detail = (
        f" (at ${per_record:.6f} per record)"
        if isinstance(per_record, (int, float)) and per_record
        else ""
    )
    lines.append(f"Anthropic model spend: **{_usd(anthropic)}**{detail}.")

    if reason:
        lines += ["", reason]

    warnings = _warnings(verdicts)
    if warnings:
        lines += [""] + warnings

    return "\n".join(lines)


# ------------------------------------------------------------------- block 4: chunks


def chunks_block(plan, ceiling=None):
    """The split, read off the plan dispatch will iterate — always shown, including the
    one-chunk case, because an omitted chunk line is indistinguishable from a chunk plan
    nobody made."""
    if getattr(plan, "record_count", None) == UNKNOWN:
        return (
            f"**Chunk plan:** 1 request carrying the whole list. The rows in it are "
            f"**{UNKNOWN}** until the backend resolves the list — and the backend refuses "
            f"a list it cannot finish inside one response rather than enriching part of "
            f"it. Dispatch sends exactly this plan."
        )

    chunk_count = plan.chunk_count
    rows = ", ".join(str(count) for count in plan.row_counts)
    plural = "chunk" if chunk_count == 1 else "chunks"
    text = (
        f"**Chunk plan:** {chunk_count} {plural} — rows per chunk: {rows}. Dispatch "
        f"sends exactly this plan; nothing is re-split at send time."
    )
    if isinstance(ceiling, int):
        text += (
            f" The per-request ceiling of {ceiling} is **PROVISIONAL**: it is derived "
            f"from single-record, company-lane timings against the backend's ~100 s "
            f"response window, and the full-waterfall probe has not been run."
        )
    return text


# ----------------------------------------------------------------------- assembly


def assemble_preview(spec, providers, plan, estimate, verdicts,
                     rate_age_days=None, ceiling=None):
    """The whole enrichment preview: four blocks of markdown plus the structured form.

    Pure. Balances have already been read (or already failed to be read) by the caller,
    so this renders in full whether or not the status endpoint answered.
    """
    blocks = {
        "records": records_block(spec, plan),
        "providers": providers_block(providers),
        "cost": cost_block(estimate, verdicts, rate_age_days),
        "chunks": chunks_block(plan, ceiling),
    }
    return {
        "blocks": blocks,
        "markdown": "\n\n".join(blocks[name] for name in _BLOCK_ORDER),
        "record_count": plan.record_count,
        "chunk_count": plan.chunk_count,
        "row_counts": list(plan.row_counts),
        "providers": list(providers or []),
        "estimate": estimate,
        "verdicts": verdicts or {},
    }


if __name__ == "__main__":
    import sys
    from datetime import date

    import config_gate

    if len(sys.argv) not in (2, 3):
        print(json.dumps({
            "ok": False,
            "error": "usage: preview_enrichment.py <spec-json> [providers-json]",
        }))
        raise SystemExit(1)

    try:
        _spec = json.loads(sys.argv[1])
        _override = json.loads(sys.argv[2]) if len(sys.argv) == 3 else None
        _cfg = config_gate.load_config()
        _providers = enrichment.resolve_providers(_override, _cfg)
        _ceiling = chunking.chunk_ceiling(_cfg)
        _plan = chunking.plan_chunks(_spec, _ceiling)
        _table = cost_guard.load_rates()
    except (json.JSONDecodeError, config_gate.ConfigError, cost_guard.CostRateError,
            chunking.ChunkPlanError, enrichment.ProviderSelectionError,
            enrichment.RecordSpecError) as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    _count = _plan.record_count if isinstance(_plan.record_count, int) else None
    _estimate = cost_guard.estimate_batch(
        _count, _spec.get("object_type"), _providers, _table
    )
    # A failed balance read degrades to every provider unreadable; it never raises and
    # never stops the preview rendering.
    _verdicts = cost_guard.compare(_estimate, cost_guard.fetch_balances(_cfg))

    print(json.dumps({
        "ok": True,
        "preview": assemble_preview(
            _spec, _providers, _plan, _estimate, _verdicts,
            rate_age_days=cost_guard.rate_table_age_days(_table, date.today()),
            ceiling=_ceiling,
        ),
    }))
