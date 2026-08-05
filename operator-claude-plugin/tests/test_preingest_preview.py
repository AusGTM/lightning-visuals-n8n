"""Tests for preingest.render_enriched_preview — the operator's one look at exactly
what will reach HubSpot before "arm the upload" can be spoken (37-CONTEXT §5 step 6).

The weight-bearing assertion is the monkeypatch test: the SEND/HELD verdict must come
from `extraction.hold_emailless`, never a second predicate re-derived here, because
`write_dispatch_csv` refuses on that exact same function — a divergent second
predicate would show the operator a row as SEND that the gate then refuses.
"""
import extraction
import preingest
import preview


def _row(row_id, **fields):
    return {"row_id": row_id, **fields}


def _merged(row_id, **fields):
    return {"row_id": row_id, **fields}


# --------------------------------------------------------- per-row shape (behavior 1)


def test_every_row_shows_source_values_enriched_values_source_and_verdict():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Amy", email="amy@x.com", jobtitle="CEO"),),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    assert result["adaptive"] is False
    entry = result["send_rows"][0]
    assert entry["row_id"] == "row-1"
    assert entry["source_values"] == {"firstname": "Amy", "email": "amy@x.com"}
    assert entry["enriched_values"] == {"jobtitle": "CEO"}
    assert entry["source"] == "the enrichment waterfall"
    assert entry["verdict"] == "SEND"
    assert entry["reason"] is None


def test_a_row_enrichment_added_nothing_to_carries_no_source_and_no_enriched_values():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Amy", email="amy@x.com"),),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    entry = result["send_rows"][0]
    assert entry["enriched_values"] == {}
    assert entry["source"] is None


def test_omitting_the_merge_report_renders_the_rows_as_their_own_merged_form():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com")]
    result = preingest.render_enriched_preview(rows)
    entry = result["send_rows"][0]
    assert entry["enriched_values"] == {}
    assert entry["verdict"] == "SEND"


# ------------------------------------------------- the one-predicate property (T-37-20)


def test_the_verdict_comes_from_extraction_hold_emailless_never_a_second_predicate(monkeypatch):
    """Monkeypatching `extraction.hold_emailless` to hold everything must flip every
    row's verdict — proving there is no second, inline-derived predicate."""
    rows = [_row("row-1", email="amy@x.com"), _row("row-2", email="ben@x.com")]

    def _hold_everything(merged_rows):
        held = [
            {"index": i, "row": row, "reason": "stubbed — hold everything"}
            for i, row in enumerate(merged_rows)
        ]
        return [], held

    monkeypatch.setattr(extraction, "hold_emailless", _hold_everything)

    result = preingest.render_enriched_preview(rows)

    assert result["send_count"] == 0
    assert result["held_count"] == 2
    assert {entry["row_id"] for entry in result["held_rows"]} == {"row-1", "row-2"}
    assert all(entry["verdict"] == "HELD" for entry in result["held_rows"])


def test_a_real_emailless_row_is_held_by_the_real_predicate_with_no_stub():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com"),
            _row("row-2", firstname="Ben", email="")]

    result = preingest.render_enriched_preview(rows)

    assert result["send_count"] == 1
    assert result["held_count"] == 1
    assert result["held_rows"][0]["row_id"] == "row-2"
    assert "email" in result["held_rows"][0]["reason"]


# ------------------------------------------------- held rows are never sampled (T-37-21)


def test_over_a_50_row_batch_with_12_held_rows_all_12_are_named_while_send_is_sampled():
    rows = []
    for i in range(1, 51):
        if i <= 12:
            rows.append(_row(f"row-{i}", firstname=f"Person{i}", email=""))
        else:
            rows.append(_row(f"row-{i}", firstname=f"Person{i}", email=f"p{i}@x.com"))

    result = preingest.render_enriched_preview(rows)

    assert result["held_count"] == 12
    assert len(result["held_rows"]) == 12
    assert {entry["row_id"] for entry in result["held_rows"]} == {
        f"row-{i}" for i in range(1, 13)
    }
    # 50 - 12 = 38 sendable rows, above preview.ADAPTIVE_THRESHOLD (20) — sampled.
    assert result["send_count"] == 38
    assert result["adaptive"] is True
    assert isinstance(result["send_rows"], dict)
    assert set(result["send_rows"]) == {"leading", "trailing"}
    assert len(result["send_rows"]["leading"]) == preview.LEAD_ROWS
    assert len(result["send_rows"]["trailing"]) == preview.TRAIL_ROWS


def test_a_held_batch_larger_than_the_adaptive_threshold_still_names_every_row():
    """The adaptive-sample rule (preview.ADAPTIVE_THRESHOLD) applies ONLY to the SEND
    rows. 25 held rows exceeds that threshold — if held rows were ever run through the
    same sampler, this would collapse to 13 (10 leading + 3 trailing), a held person
    silently dropped from the operator's view."""
    rows = [_row(f"row-{i}", email="") for i in range(1, 26)]

    result = preingest.render_enriched_preview(rows)

    assert result["held_count"] == 25
    assert len(result["held_rows"]) == 25
    assert isinstance(result["held_rows"], list)  # never the leading/trailing shape


# ------------------------------------------------------------- both boundaries (behavior)


def test_a_batch_where_nothing_is_held_says_so_explicitly():
    rows = [_row("row-1", email="a@x.com"), _row("row-2", email="b@x.com")]
    result = preingest.render_enriched_preview(rows)
    assert result["held_count"] == 0
    assert "No rows are held back" in result["held_statement"]


def test_a_batch_where_everything_is_held_says_so_and_that_sending_writes_nothing():
    rows = [_row("row-1", email=""), _row("row-2", email="")]
    result = preingest.render_enriched_preview(rows)
    assert result["held_count"] == 2
    assert result["send_count"] == 0
    assert "All 2 rows" in result["held_statement"]
    assert "would write nothing" in result["held_statement"]


# ---------------------------------------------------------- nothing has reached HubSpot


def test_the_result_states_nothing_has_reached_hubspot_yet():
    rows = [_row("row-1", email="a@x.com")]
    result = preingest.render_enriched_preview(rows)
    assert "reached HubSpot" in result["nothing_reached_hubspot"]
    assert "yet" in result["nothing_reached_hubspot"]


# ------------------------------------------------------------- merge conflicts surfaced


def test_merge_conflicts_are_surfaced_in_the_result():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Amy", email="amy@x.com"),),
        conflicts=(
            {"row_id": "row-1", "field": "jobtitle", "kept": "CEO", "provider_value": "COO"},
        ),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    assert result["conflicts"] == (
        {"row_id": "row-1", "field": "jobtitle", "kept": "CEO", "provider_value": "COO"},
    )


def test_no_merge_report_means_no_conflicts_reported():
    rows = [_row("row-1", email="amy@x.com")]
    result = preingest.render_enriched_preview(rows)
    assert result["conflicts"] == ()


# ------------------------------------------------------------------------------- purity


def test_render_enriched_preview_performs_no_network_call_and_writes_no_file(tmp_path, monkeypatch):
    """The autouse `no_network` guard already forbids a real request; this adds the
    directory-contents half of the purity claim (no file write)."""
    monkeypatch.chdir(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())

    rows = [_row("row-1", firstname="Amy", email="amy@x.com")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Amy", email="amy@x.com", jobtitle="CEO"),),
        conflicts=({"row_id": "row-1", "field": "jobtitle", "kept": "x", "provider_value": "y"},),
    )
    preingest.render_enriched_preview(rows, merge_report)

    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after == []
