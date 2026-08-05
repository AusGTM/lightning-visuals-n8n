"""Tests for preview_enrichment.py — the rendered cost guard (PREVIEW-02, PREVIEW-03).

Three assertions carry the weight, and each one fails against a plausible defect rather
than passing trivially:

* an unreadable balance's rendered row must carry **no zero figure** for that provider —
  an assertion of the shape "the unreadable value is falsy" passes against the very defect
  it is meant to catch, and 25-VALIDATION.md bans it;
* a readable zero and an unreadable balance must render as **different text** (D-17's
  third independent assertion of that distinction, after the n8n response assembly in
  25-02 and the client comparison in 25-05);
* the tabular lane's preview must carry a cost block at all (D-16).

Every function under test is pure, so nothing here needs a transport — but the autouse
`no_network` guard is in force regardless.
"""
import re

import chunking
import cost_guard
import enrichment
import preview_enrichment
from preview import build_preview, tabular_cost_block

IDS_SPEC = {"record_ids": ["101", "102", "103"], "object_type": "companies"}
LIST_SPEC = {"list": "Named Targets", "object_type": "contacts"}


def _plan(spec, ceiling=2):
    return chunking.plan_chunks(spec, ceiling)


def _rates():
    return cost_guard.load_rates()


def _balances(**overrides):
    """A balance map in `cost_guard.fetch_balances()`'s shape. Defaults to every provider
    readable and comfortable, so any test's own override is what the result turns on."""
    balances = {
        provider: {"credits": 500, "unreadable": False, "reason": None}
        for provider in cost_guard.PROVIDERS
    }
    balances.update(overrides)
    return balances


def _unreadable(reason="balance_not_reported"):
    return {"credits": None, "unreadable": True, "reason": reason}


def _preview(spec, providers=("lusha",), balances=None, ceiling=2, rate_age_days=1):
    plan = _plan(spec, ceiling)
    count = plan.record_count if isinstance(plan.record_count, int) else None
    estimate = cost_guard.estimate_batch(
        count, spec.get("object_type"), list(providers), _rates()
    )
    verdicts = cost_guard.compare(estimate, balances if balances is not None else _balances())
    return preview_enrichment.assemble_preview(
        spec, list(providers), plan, estimate, verdicts,
        rate_age_days=rate_age_days, ceiling=ceiling,
    )


def _row_for(block, provider):
    label = preview_enrichment.PROVIDER_LABELS[provider]
    rows = [line for line in block.splitlines() if line.startswith(f"| {label} |")]
    assert len(rows) == 1, f"expected exactly one {label} row, got {rows}"
    return rows[0]


def _cells(row):
    return [cell.strip() for cell in row.strip("|").split("|")]


# ------------------------------------------------------------------ record counting


def test_named_record_ids_show_the_exact_count():
    block = _preview(IDS_SPEC)["blocks"]["records"]
    assert "3" in block
    assert preview_enrichment.UNKNOWN not in block


def test_a_list_input_preview_contains_no_numeric_record_count():
    """D-02/D-21: the client does not resolve a list and does not count one. The word
    `unknown` is the answer — a fabricated `0` here would be this milestone's recurring
    partial-read-impersonating-a-healthy-one shape arriving through the preview."""
    result = _preview(LIST_SPEC)
    block = result["blocks"]["records"]

    assert re.search(r"\d", block) is None, (
        f"a list preview must show no numeral at all where a count would go: {block!r}"
    )
    assert "unknown" in block
    assert "Named Targets" in block
    assert result["record_count"] == chunking.UNKNOWN
    assert result["record_count"] != 0


def test_a_list_preview_never_reads_as_nothing_to_do():
    markdown = _preview(LIST_SPEC)["markdown"]
    for forbidden in ("0 records", "no records", "nothing to do", "0 contacts"):
        assert forbidden not in markdown.lower()


# --------------------------------------------------------------- provider selection


def test_the_full_waterfall_is_named_explicitly_and_marked_as_the_default():
    block = _preview(IDS_SPEC, providers=enrichment.FULL_WATERFALL)["blocks"]["providers"]
    for provider in enrichment.FULL_WATERFALL:
        assert preview_enrichment.PROVIDER_LABELS[provider] in block
    assert "default" in block.lower()


def test_an_empty_provider_selection_is_still_stated_rather_than_omitted():
    block = _preview(IDS_SPEC, providers=[])["blocks"]["providers"]
    assert block.strip(), "the providers block must never be empty (D-06)"
    assert "none" in block.lower()


def test_every_preview_names_the_selection_whatever_it_resolved_to():
    for providers in ([], ["lusha"], enrichment.FULL_WATERFALL):
        result = _preview(IDS_SPEC, providers=providers)
        assert result["blocks"]["providers"].startswith("**Providers:**")
        assert result["blocks"]["providers"] in result["markdown"]


# ------------------------------------------------------------------------- the cost


def test_the_cost_block_shows_per_provider_credits_and_the_anthropic_dollar_figure():
    block = _preview(IDS_SPEC, providers=["lusha"])["blocks"]["cost"]
    # Lusha companies: 2 credits/company x 3 companies.
    assert _cells(_row_for(block, "lusha"))[1] == "6"
    assert "$0.21" in block  # 3 x $0.068624


def test_a_provider_with_no_measured_rate_renders_unknown_and_never_zero():
    """Apollo's rate is permanently unknown on this account (D-10a) — the common case,
    not an edge case."""
    block = _preview(IDS_SPEC, providers=["apollo"])["blocks"]["cost"]
    cells = _cells(_row_for(block, "apollo"))
    assert cells[1].startswith("unknown")
    assert "0" not in cells[1]


def test_a_readable_zero_balance_and_an_unreadable_balance_render_as_different_text():
    """D-17's banned assertion shape is "unreadable is falsy" — it passes against the
    defect. Assert the two produce different OUTPUT instead."""
    zero = _preview(
        IDS_SPEC, providers=["lusha"],
        balances=_balances(lusha={"credits": 0, "unreadable": False, "reason": None}),
    )["blocks"]["cost"]
    unreadable = _preview(
        IDS_SPEC, providers=["lusha"], balances=_balances(lusha=_unreadable("http_403")),
    )["blocks"]["cost"]

    assert zero != unreadable
    assert _cells(_row_for(zero, "lusha"))[2] == "0"
    assert _cells(_row_for(unreadable, "lusha"))[2].startswith("unknown")


def test_an_unreadable_balance_row_carries_no_zero_figure_for_that_provider():
    block = _preview(
        IDS_SPEC, providers=["lusha"], balances=_balances(lusha=_unreadable()),
    )["blocks"]["cost"]
    for cell in _cells(_row_for(block, "lusha")):
        assert cell != "0", f"an unreadable balance rendered a zero figure: {cell!r}"


def test_an_unreadable_balance_warns_that_headroom_could_not_be_confirmed():
    block = _preview(
        IDS_SPEC, providers=["lusha"], balances=_balances(lusha=_unreadable()),
    )["blocks"]["cost"]
    assert "could not be confirmed" in block
    assert "not a report that there is enough" in block
    assert _headroom(block, "lusha") != "enough"


def _headroom(block, provider):
    return _cells(_row_for(block, provider))[3]


def test_a_readable_zero_balance_warns_in_the_same_shape_as_any_other_insufficiency():
    zero = _preview(
        IDS_SPEC, providers=["lusha"],
        balances=_balances(lusha={"credits": 0, "unreadable": False, "reason": None}),
    )["blocks"]["cost"]
    low = _preview(
        IDS_SPEC, providers=["lusha"],
        balances=_balances(lusha={"credits": 1, "unreadable": False, "reason": None}),
    )["blocks"]["cost"]

    assert _headroom(zero, "lusha") == _headroom(low, "lusha") == "**NOT enough**"
    assert "would run out of credits" in zero
    assert "could not be read" not in _row_for(zero, "lusha")


def test_a_readable_balance_below_the_estimate_names_the_provider_in_its_warning():
    block = _preview(
        IDS_SPEC, providers=["lusha"],
        balances=_balances(lusha={"credits": 1, "unreadable": False, "reason": None}),
    )["blocks"]["cost"]
    warning = [line for line in block.splitlines() if line.startswith("- ⚠")]
    assert warning and "Lusha" in warning[0]


def test_every_preview_shows_the_rate_tables_measurement_date_and_its_age():
    block = _preview(IDS_SPEC, rate_age_days=214)["blocks"]["cost"]
    assert _rates()["measured_on"] in block
    assert "214 days ago" in block


def test_the_cost_copy_says_at_most_rather_than_claiming_precision():
    """25-05's estimator deliberately over-states Lusha (first-time rate, never the
    measured-zero re-enrich rate), so the copy must not read as a quote."""
    block = _preview(IDS_SPEC)["blocks"]["cost"]
    assert "at most" in block.lower()
    assert "will cost" not in block.lower()


def test_the_preview_renders_in_full_when_the_balance_fetch_failed():
    """A guard that vanishes when the backend is unreachable is not a guard (T-25-22)."""
    all_unreadable = {
        provider: _unreadable("status_endpoint_unavailable")
        for provider in cost_guard.PROVIDERS
    }
    result = _preview(
        IDS_SPEC, providers=enrichment.FULL_WATERFALL, balances=all_unreadable
    )

    for name in ("records", "providers", "cost", "chunks"):
        assert result["blocks"][name].strip(), f"{name} block vanished on an unreachable backend"
    assert "3" in result["blocks"]["records"]          # the count still shows
    assert "2 chunks" in result["blocks"]["chunks"]    # the plan still shows
    for provider in enrichment.FULL_WATERFALL:
        assert _headroom(result["blocks"]["cost"], provider) == "**could not be confirmed**"
        assert result["verdicts"][provider]["verdict"] == "unknown"


def test_apollos_unknown_is_explained_as_normal_rather_than_as_a_fault():
    block = _preview(
        IDS_SPEC, providers=["apollo"], balances=_balances(apollo=_unreadable("http_403")),
    )["blocks"]["cost"]
    assert "rate limits rather than a depleting credit pool" in block
    assert "not a fault" in block


# ---------------------------------------------------------------------- the chunks


def test_a_batch_above_the_ceiling_shows_the_chunk_count_and_the_rows_in_each_chunk():
    result = _preview(IDS_SPEC, ceiling=2)
    block = result["blocks"]["chunks"]
    assert "2 chunks" in block
    assert "2, 1" in block
    assert result["row_counts"] == [2, 1]
    assert result["chunk_count"] == _plan(IDS_SPEC, 2).chunk_count


def test_a_batch_at_or_below_the_ceiling_still_shows_a_one_chunk_plan():
    block = _preview(IDS_SPEC, ceiling=5)["blocks"]["chunks"]
    assert "1 chunk" in block
    assert "3" in block


def test_the_chunk_ceiling_is_presented_as_measured_not_provisional():
    """D-06/D-20's rule cuts both ways: presenting a derivation as a measurement was
    forbidden while B4 was unrun, and presenting a measurement as provisional after
    B4 ran (2026-08-03, 37.44 s full waterfall) would misstate it in the other
    direction. The date and figure travel with the claim."""
    block = _preview(IDS_SPEC, ceiling=2)["blocks"]["chunks"]
    assert "PROVISIONAL" not in block
    assert "measured" in block
    assert "37.44" in block


def test_the_chunk_block_is_rendered_from_the_plan_dispatch_will_iterate():
    plan = chunking.ChunkPlan(
        chunks=({"record_ids": ["1", "2", "3"], "object_type": "companies"},),
        row_counts=(3,),
        record_count=3,
    )
    block = preview_enrichment.chunks_block(plan)
    assert "1 chunk" in block and "rows per chunk: 3" in block


# --------------------------------------------------------------- the tabular lane


def test_the_tabular_lanes_preview_carries_a_cost_block(sample_csv):
    preview = build_preview(sample_csv)
    assert "cost_block" in preview
    assert preview["cost_block"].strip()


def test_the_tabular_cost_block_states_a_zero_with_its_reason():
    block = tabular_cost_block(25)
    assert "**0**" in block
    assert "$0.00" in block
    assert "calls no enrichment provider" in block
    # A real, explainable zero — the word `unknown` belongs to a balance that could not
    # be read, and must not appear on a lane whose zero is a fact.
    assert preview_enrichment.UNKNOWN not in block
    assert "could not be confirmed" not in block


def test_both_lanes_render_their_cost_block_through_the_same_helper():
    """Two cost blocks that can drift apart is the second-source-of-truth pattern this
    milestone avoids everywhere else (D-16)."""
    assert tabular_cost_block(3).startswith(
        preview_enrichment.cost_block(preview_enrichment.zero_cost_estimate(3), {})
        .splitlines()[0]
    )


# ------------------------------------------------------------------------ purity


def test_rendering_mutates_nothing_and_the_plan_is_unchanged_afterwards():
    plan = _plan(IDS_SPEC, 2)
    before = (plan.chunks, plan.row_counts, plan.record_count)
    spec = dict(IDS_SPEC)
    estimate = cost_guard.estimate_batch(3, "companies", ["lusha"], _rates())
    preview_enrichment.assemble_preview(
        spec, ["lusha"], plan, estimate, cost_guard.compare(estimate, _balances())
    )
    assert (plan.chunks, plan.row_counts, plan.record_count) == before
    assert spec == IDS_SPEC


def test_a_view_is_refused_before_any_preview_is_built():
    try:
        _plan({"view": "My Saved View"})
    except enrichment.ViewNotSupportedError as exc:
        assert str(exc) == enrichment.VIEW_REFUSAL
    else:
        raise AssertionError("a saved view must be refused, not previewed")


# ------------------------------------------------------------- 37-05 Task 1: rows branch

ROWS_SPEC = {
    "rows": [{"row_id": "row-1", "email": "a@x.com"},
              {"row_id": "row-2", "email": "b@x.com"},
              {"row_id": "row-3", "email": "c@x.com"}],
    "object_type": "contacts",
}

_IDS_RECORDS_BLOCK_LITERAL = (
    "**Records:** 3 companies, named by ID. Nothing is structured or "
    "uploaded — these already exist in HubSpot."
)
_LIST_RECORDS_BLOCK_LITERAL = (
    '**Records:** the HubSpot list "Named Targets" (contacts) — record count: '
    "**unknown**. The backend resolves the list and counts it; I do not, so "
    "no number is shown here rather than a fabricated one."
)


def test_a_rows_spec_records_block_states_the_rows_are_not_in_hubspot_yet():
    block = _preview(ROWS_SPEC)["blocks"]["records"]
    assert "3" in block
    assert "not" in block
    assert "in HubSpot yet" in block
    assert "nothing is created" in block.lower()


def test_a_rows_spec_records_block_never_carries_the_already_exist_claim():
    """The rows branch and the named-IDs branch make opposite claims about the same
    field position — a rendering regression would smuggle one into the other."""
    block = _preview(ROWS_SPEC)["blocks"]["records"]
    assert "already exist" not in block


def test_a_record_ids_records_block_is_byte_identical_to_before():
    """Asserted against a literal, not by eye — a regression in an untouched branch
    is exactly what an added sibling branch risks."""
    block = _preview(IDS_SPEC)["blocks"]["records"]
    assert block == _IDS_RECORDS_BLOCK_LITERAL


def test_a_list_records_block_is_byte_identical_to_before():
    block = _preview(LIST_SPEC)["blocks"]["records"]
    assert block == _LIST_RECORDS_BLOCK_LITERAL


def test_a_rows_spec_with_a_noninteger_count_renders_unknown_never_a_numeral_or_zero():
    plan = chunking.ChunkPlan(chunks=(), row_counts=(), record_count=chunking.UNKNOWN)
    block = preview_enrichment.records_block(ROWS_SPEC, plan)
    assert re.search(r"\d", block) is None
    assert "unknown" in block
    assert "0" not in block


def test_assemble_preview_over_a_rows_spec_produces_all_four_blocks_in_order():
    result = _preview(ROWS_SPEC)
    assert list(result["blocks"]) == ["records", "providers", "cost", "chunks"]
    for name in ("records", "providers", "cost", "chunks"):
        assert result["blocks"][name].strip()


def test_cost_block_is_identical_for_a_rows_spec_and_a_record_id_spec_of_equal_size():
    """`cost_guard.estimate_batch` prices a bare integer count and never reads a
    record id, so the cost path is genuinely shared between the two spec forms —
    same object_type and count, so nothing else could account for a difference."""
    rows_spec_companies = {**ROWS_SPEC, "object_type": "companies"}
    rows_block = _preview(rows_spec_companies, providers=["lusha"])["blocks"]["cost"]
    ids_block = _preview(IDS_SPEC, providers=["lusha"])["blocks"]["cost"]
    assert rows_block == ids_block
