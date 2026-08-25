"""Tests for preingest.render_enriched_preview — the operator's one look at exactly
what will reach HubSpot before the operator's yes can grant the write (37-CONTEXT §5
step 6).

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


# --------------------------------------------- unanswered rows are their own group (T-38-01)


def _unanswered_entry(row_id, row, reason=None):
    return {"row_id": row_id, "row": row, "reason": reason or preingest.UNANSWERED_REASON}


def test_a_two_row_chunk_answered_with_one_item_puts_row_2_in_unanswered_never_held():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com"),
            _row("row-2", firstname="Ben", email="ben@x.com")]
    merge_report = preingest.MergeResult(
        rows=(
            _merged("row-1", firstname="Amy", email="amy@x.com", jobtitle="CEO"),
            _merged("row-2", firstname="Ben", email="ben@x.com"),
        ),
        unanswered=(_unanswered_entry("row-2", _merged("row-2", firstname="Ben", email="ben@x.com")),),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    assert result["unanswered_count"] == 1
    assert {entry["row_id"] for entry in result["unanswered_rows"]} == {"row-2"}
    assert {entry["row_id"] for entry in result["held_rows"]} == set()
    assert {entry["row_id"] for entry in result["send_rows"]} == {"row-1"}


def test_an_unanswered_row_with_no_email_is_never_held_for_it_the_live_bug_pinned():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com"),
            _row("row-2", firstname="Ben")]  # no email at all
    merge_report = preingest.MergeResult(
        rows=(
            _merged("row-1", firstname="Amy", email="amy@x.com"),
            _merged("row-2", firstname="Ben"),
        ),
        unanswered=(_unanswered_entry("row-2", _merged("row-2", firstname="Ben")),),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    assert {entry["row_id"] for entry in result["held_rows"]} == set(), (
        "an unanswered row with no email must never land in held — the reason would "
        "be a fabricated claim about the row's data standing in for a claim about "
        "the response"
    )
    assert {entry["row_id"] for entry in result["unanswered_rows"]} == {"row-2"}


def test_an_unanswered_row_with_a_source_email_is_still_unanswered_not_sent():
    rows = [_row("row-1", email="ben@x.com")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", email="ben@x.com"),),
        unanswered=(_unanswered_entry("row-1", _merged("row-1", email="ben@x.com")),),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    assert result["unanswered_count"] == 1
    assert {entry["row_id"] for entry in result["send_rows"]} == set()


def test_no_entry_in_unanswered_rows_carries_the_no_email_reason():
    rows = [_row("row-1", firstname="Ben")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Ben"),),
        unanswered=(_unanswered_entry("row-1", _merged("row-1", firstname="Ben")),),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    for entry in result["unanswered_rows"]:
        assert "no usable email" not in entry["reason"]
        assert entry["reason"] == preingest.UNANSWERED_REASON


def test_send_count_plus_held_count_plus_unanswered_count_equals_total():
    rows = [_row(f"row-{i}", firstname=f"Person{i}", email=f"p{i}@x.com" if i % 2 else "")
            for i in range(1, 8)]
    merge_report = preingest.MergeResult(
        rows=tuple(_merged(row["row_id"], **{k: v for k, v in row.items() if k != "row_id"})
                   for row in rows),
        unanswered=(
            _unanswered_entry("row-3", _merged("row-3", firstname="Person3", email="")),
            _unanswered_entry("row-6", _merged("row-6", firstname="Person6", email="")),
        ),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    assert result["send_count"] + result["held_count"] + result["unanswered_count"] == result["total"]


def test_a_batch_with_no_unanswered_rows_says_so_explicitly():
    rows = [_row("row-1", email="a@x.com")]
    result = preingest.render_enriched_preview(rows)
    assert result["unanswered_count"] == 0
    assert "No rows are unanswered" in result["unanswered_statement"]


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


def test_an_unanswered_batch_larger_than_the_adaptive_threshold_still_names_every_row():
    """T-38-06: `unanswered_rows` must never pass through `preview._adaptive_sample`
    either — a sampled-out unanswered row is a person nobody is told about."""
    rows = [_row(f"row-{i}", email=f"p{i}@x.com") for i in range(1, 26)]
    merge_report = preingest.MergeResult(
        rows=tuple(_merged(row["row_id"], email=row["email"]) for row in rows),
        unanswered=tuple(
            _unanswered_entry(row["row_id"], _merged(row["row_id"], email=row["email"]))
            for row in rows
        ),
    )

    result = preingest.render_enriched_preview(rows, merge_report)

    assert result["unanswered_count"] == 25
    assert len(result["unanswered_rows"]) == 25
    assert isinstance(result["unanswered_rows"], list)  # never the leading/trailing shape


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
