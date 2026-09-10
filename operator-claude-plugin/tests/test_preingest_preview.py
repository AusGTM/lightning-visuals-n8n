"""Tests for preingest.render_enriched_preview — the operator's one look at exactly
what will reach HubSpot before the operator's yes can grant the write (37-CONTEXT §5
step 6).

The weight-bearing assertion is that the preview renders exactly what
`partition_for_ingest` returns, never a second predicate re-derived here, because
`write_dispatch_csv` builds its CSV from that exact same function — a divergent second
predicate would show the operator a row as SEND that the gate then refuses.
"""
import extraction
import preingest
import preview


def _row(row_id, **fields):
    return {"row_id": row_id, **fields}


def _merged(row_id, **fields):
    return {"row_id": row_id, **fields}


def _preview(rows, merge_report=None, responses=None, tier="high"):
    """Phase 70 Plan 06 (D-70-11): the preview's per-row verdict is
    `confidence.assess`'s now, so a render needs the RECOVERED rows to assess. The
    tests below predate that and are about the RENDER — the row view, the sampling, the
    statements — not about the gate, which `test_the_previews_send_count_is_the_dispatch
    _sendable_count_itself` and its neighbours at the bottom of this file own. So they
    default to a high-tier answer per row: the batch the gate passes, which is exactly
    the batch each of these tests was written against.
    """
    if responses is None:
        source = merge_report.rows if merge_report is not None else rows
        responses = [_answer(row.get("row_id"), tier) for row in source
                     if isinstance(row, dict) and row.get("row_id")]
    return preingest.render_enriched_preview(rows, merge_report, responses=responses)



# --------------------------------------------------------- per-row shape (behavior 1)


def test_every_row_shows_source_values_enriched_values_source_and_verdict():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Amy", email="amy@x.com", jobtitle="CEO"),),
    )

    result = _preview(rows, merge_report)

    assert result["adaptive"] is False
    entry = result["send_rows"][0]
    assert entry["row_id"] == "row-1"
    assert entry["source_values"] == {"firstname": "Amy", "email": "amy@x.com"}
    assert entry["enriched_values"] == {"jobtitle": "CEO"}
    assert entry["source"] == "the enrichment waterfall"
    assert entry["verdict"] == "SEND"
    assert entry["reason"] is None


def test_a_replaced_value_shows_in_enriched_values_beside_the_original_in_source_values():
    # jobtitle is protect_if_current_present: false (ruling 2026-09-11) -- merge_
    # enriched can replace a present value, and the operator's one pre-arm look must
    # show the NEW value under enriched_values, not just the superseded one under
    # source_values (which still shows what the operator originally had).
    rows = [_row("row-1", firstname="Amy", email="amy@x.com", jobtitle="Head of Marketing")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Amy", email="amy@x.com",
                       jobtitle="Head of Marketing and Content"),),
    )

    result = _preview(rows, merge_report)

    entry = result["send_rows"][0]
    assert entry["source_values"]["jobtitle"] == "Head of Marketing"
    assert entry["enriched_values"] == {"jobtitle": "Head of Marketing and Content"}
    assert entry["source"] == "the enrichment waterfall"


def test_a_row_enrichment_added_nothing_to_carries_no_source_and_no_enriched_values():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Amy", email="amy@x.com"),),
    )

    result = _preview(rows, merge_report)

    entry = result["send_rows"][0]
    assert entry["enriched_values"] == {}
    assert entry["source"] is None


def test_omitting_the_merge_report_renders_the_rows_as_their_own_merged_form():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com")]
    result = _preview(rows)
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

    result = _preview(rows)

    assert result["send_count"] == 0
    assert result["held_count"] == 2
    assert {entry["row_id"] for entry in result["held_rows"]} == {"row-1", "row-2"}
    assert all(entry["verdict"] == "HELD" for entry in result["held_rows"])


def test_a_real_emailless_row_is_held_by_the_real_predicate_with_no_stub():
    rows = [_row("row-1", firstname="Amy", email="amy@x.com"),
            _row("row-2", firstname="Ben", email="")]

    result = _preview(rows)

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

    result = _preview(rows, merge_report)

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

    result = _preview(rows, merge_report)

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

    result = _preview(rows, merge_report)

    assert result["unanswered_count"] == 1
    assert {entry["row_id"] for entry in result["send_rows"]} == set()


def test_no_entry_in_unanswered_rows_carries_the_no_email_reason():
    rows = [_row("row-1", firstname="Ben")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Ben"),),
        unanswered=(_unanswered_entry("row-1", _merged("row-1", firstname="Ben")),),
    )

    result = _preview(rows, merge_report)

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

    result = _preview(rows, merge_report)

    assert result["send_count"] + result["held_count"] + result["unanswered_count"] == result["total"]


def test_a_batch_with_no_unanswered_rows_says_so_explicitly():
    rows = [_row("row-1", email="a@x.com")]
    result = _preview(rows)
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

    result = _preview(rows)

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

    result = _preview(rows)

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

    result = _preview(rows, merge_report)

    assert result["unanswered_count"] == 25
    assert len(result["unanswered_rows"]) == 25
    assert isinstance(result["unanswered_rows"], list)  # never the leading/trailing shape


# ------------------------------------------------------------- both boundaries (behavior)


def test_a_batch_where_nothing_is_held_says_so_explicitly():
    rows = [_row("row-1", email="a@x.com"), _row("row-2", email="b@x.com")]
    result = _preview(rows)
    assert result["held_count"] == 0
    assert "No rows are held back" in result["held_statement"]


def test_a_batch_where_everything_is_held_says_so_and_that_sending_writes_nothing():
    rows = [_row("row-1", email=""), _row("row-2", email="")]
    result = _preview(rows)
    assert result["held_count"] == 2
    assert result["send_count"] == 0
    assert "All 2 rows" in result["held_statement"]
    assert "would write nothing" in result["held_statement"]


# ---------------------------------------------------------- nothing has reached HubSpot


def test_the_result_states_nothing_has_reached_hubspot_yet():
    rows = [_row("row-1", email="a@x.com")]
    result = _preview(rows)
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

    result = _preview(rows, merge_report)

    assert result["conflicts"] == (
        {"row_id": "row-1", "field": "jobtitle", "kept": "CEO", "provider_value": "COO"},
    )


def test_no_merge_report_means_no_conflicts_reported():
    rows = [_row("row-1", email="amy@x.com")]
    result = _preview(rows)
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
    _preview(rows, merge_report)

    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after == []


# =====================================================================================
# Phase 70 Plan 06 Task 2 (D-70-11) — ONE per-row verdict, and it is
# `confidence.assess`'s. Folded todo: 2026-09-09-enriched-preview-says-send-for-rows-
# the-confidence-gate-holds.md — on run `2bc3617b` the preview said SEND for two rows
# the confidence gate held `no_match`, the operator granted the write on that display,
# and nothing was ingested.
# =====================================================================================

import confidence  # noqa: E402


def _answer(row_id, tier, *, candidate_count=1):
    """One `Build Response` item as `preingest.parse_outcome` reads it."""
    return {
        "row_id": row_id,
        "outcome_contract_version": preingest.OUTCOME_CONTRACT_VERSION,
        "match": {"tier": tier},
        "candidate_count": candidate_count,
    }


def test_a_no_match_row_with_a_found_email_renders_held_never_sendable():
    """The exact shape the folded todo found: enrichment DID find an email, and the
    gate still holds the row because there is no existing record to confirm against
    (D-61-03). Email presence is not a verdict."""
    rows = [_row("row-1", firstname="Greg")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Greg", email="greg@found.example"),),
    )

    preview_data = preingest.render_enriched_preview(
        rows, merge_report, responses=[_answer("row-1", "none")])

    assert preview_data["send_count"] == 0
    assert [r["row_id"] for r in preview_data["held_rows"]] == ["row-1"]
    held = preview_data["held_rows"][0]
    assert held["hold_code"] == confidence.HOLD_NO_MATCH
    assert "no match" in held["reason"].lower()


def test_a_high_tier_row_with_an_email_renders_sendable():
    rows = [_row("row-1", firstname="Amy")]
    merge_report = preingest.MergeResult(
        rows=(_merged("row-1", firstname="Amy", email="amy@x.com"),),
    )

    preview_data = preingest.render_enriched_preview(
        rows, merge_report, responses=[_answer("row-1", "high")])

    assert preview_data["send_count"] == 1
    assert preview_data["held_rows"] == []


def test_the_previews_send_count_is_the_dispatch_sendable_count_itself():
    """D-70-11: an EQUALITY, not two computations that agree today. The preview renders
    exactly what `partition_for_ingest` returns — the same function the dispatch step
    calls to build its CSV — so there is no second predicate that can drift."""
    rows = [_row("row-1"), _row("row-2"), _row("row-3")]
    merged = (
        _merged("row-1", email="amy@x.com"),        # high tier + email -> sendable
        _merged("row-2", email="greg@found.example"),  # no match -> held
        _merged("row-3"),                            # high tier, no email -> held
    )
    merge_report = preingest.MergeResult(rows=merged)
    responses = [_answer("row-1", "high"), _answer("row-2", "none"),
                 _answer("row-3", "high")]

    preview_data = preingest.render_enriched_preview(rows, merge_report,
                                                     responses=responses)
    sendable, held = preingest.partition_for_ingest(list(merged), responses)

    assert preview_data["send_count"] == len(sendable) == 1
    assert preview_data["held_count"] == len(held) == 2


def test_partition_for_ingest_holds_before_it_checks_the_email():
    """A no-match row is held for NO_MATCH, never for the email — the reason the
    operator reads has to be the one that actually withheld it."""
    rows = [_merged("row-1")]  # no email AND no match

    _, held = preingest.partition_for_ingest(rows, [_answer("row-1", "none")])

    assert held[0]["hold_code"] == confidence.HOLD_NO_MATCH


def test_partition_for_ingest_never_widens_the_hold_code_vocabulary():
    """SAFE-01: the email hold is real, but it is not a confidence hold — it carries no
    code rather than a new one, so `confidence.ALL_HOLD_CODES` stays closed."""
    rows = [_merged("row-1")]

    _, held = preingest.partition_for_ingest(rows, [_answer("row-1", "high")])

    assert held[0]["hold_code"] is None
    assert held[0]["reason"]


def test_round_b_shape_send_count_zero_all_three_held_no_match():
    """Pins UAT run `2bc3617b` (Round B, 2026-09-09): three unmatched rows — two the
    waterfall found an email for, one it did not — all held `no_match`, including the
    emailless one, because `confidence.assess` runs before the email check. The
    incident's actual failure was a preview showing `send_count == 2` against a gate
    that held all three; this test's real people are substituted for plausible rows,
    the shape is what is pinned, not the person."""
    rows = [_row("row-1", firstname="Greg"), _row("row-2", firstname="Barry"),
            _row("row-3", firstname="Nardine")]
    merge_report = preingest.MergeResult(
        rows=(
            _merged("row-1", firstname="Greg", email="greg@found.example"),
            _merged("row-2", firstname="Barry", email="barry@found.example"),
            _merged("row-3", firstname="Nardine"),  # seniority only, no email
        ),
    )
    responses = [_answer("row-1", "none"), _answer("row-2", "none"),
                 _answer("row-3", "none")]

    preview_data = preingest.render_enriched_preview(rows, merge_report,
                                                     responses=responses)
    sendable, held = preingest.partition_for_ingest(
        list(merge_report.rows), responses)

    assert preview_data["send_count"] == 0
    assert preview_data["held_count"] == 3
    assert preview_data["send_count"] == len(sendable)
    assert preview_data["held_count"] == len(held)
    assert [r["hold_code"] for r in preview_data["held_rows"]] == \
        [confidence.HOLD_NO_MATCH] * 3
