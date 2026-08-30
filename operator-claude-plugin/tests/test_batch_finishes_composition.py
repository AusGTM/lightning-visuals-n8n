"""Tests for the enrich-before-ingest SKILL.md hold-don't-block sequence (Phase 61
Plan 04 Task 4, D-61-07).

Drives the REAL sequence the skill documents — `preingest.match_batch` -> Task 1's
`preingest.parse_outcome` -> `confidence.assess` -> `held_queue.build_entry`/`save` ->
`run_manifest.save`, for a held row; straight through, with no gate, for a confident
one — with only the transport injected, per REVIEW's "documentation-only wiring"
concern. The load-bearing assertion is the LAST row's completion: a batch containing an
earlier chunk failure and an earlier held row must still reach and process its final
row, never stopping at either.
"""
import chunking
import confidence
import held_queue
import preingest
import run_manifest


def _match_item(row_id, tier, candidates=None):
    candidates = candidates or []
    return {
        "row_id": row_id, "action": "proposed", "mode": "propose",
        "outcome_contract_version": 1,
        "match": {"tier": tier, "auto": tier == "high", "reason": "test", "candidates": candidates},
        "candidate_count": len(candidates),
        "provider_agreement": None, "material_conflicts": None,
        "judge_adjudicated_fields": None,
    }


def test_a_batch_with_a_failed_chunk_and_a_held_row_still_reaches_and_dispatches_its_last_row(
        fake_config, stub_post_transport_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))

    rows = [
        {"row_id": "row-1", "firstname": "A", "lastname": "Fails", "company": "X"},
        {"row_id": "row-2", "firstname": "B", "lastname": "Held", "company": "Y"},
        {"row_id": "row-3", "firstname": "C", "lastname": "Confident", "company": "Z",
         "email": "c@example.com"},
    ]
    spec = {"rows": rows, "object_type": "contacts"}
    plan = chunking.plan_chunks(spec, ceiling=1)  # one chunk per row

    transport = stub_post_transport_factory(responses=[
        ConnectionError("simulated chunk failure — row-1's own chunk"),
        [_match_item("row-2", "medium", candidates=[{"hs_object_id": "1"}, {"hs_object_id": "2"}])],
        [_match_item("row-3", "high")],
    ])

    outcome = preingest.match_batch(plan, fake_config, transport=transport)
    assert outcome.unchecked_row_ids == {"row-1"}, "row-1's chunk failed outright"

    responses_by_id = {item["row_id"]: item for item in outcome.responses}
    held_entries = held_queue.load()
    verdicts = run_manifest.load()
    processed_row_ids = []

    for row in rows:
        row_id = row["row_id"]
        item = responses_by_id.get(row_id)
        parsed = preingest.parse_outcome(item) if item is not None else preingest.UNPARSEABLE_OUTCOME
        verdict = confidence.assess(parsed)

        if verdict.verdict == confidence.CONFIDENT:
            # This is the "no per-row gate" case — it proceeds straight to dispatch,
            # never touching held_queue or the manifest.
            processed_row_ids.append(row_id)
            continue

        entry = held_queue.build_entry(row, verdict.hold_code, verdict.reason, parsed)
        held_entries[row_id] = entry
        held_queue.save("run-1", held_entries)
        verdicts[row_id] = run_manifest.CONFIDENCE_HELD
        run_manifest.save("run-1", verdicts)
        processed_row_ids.append(row_id)

    # THE LOAD-BEARING ASSERTION: the batch reached and processed its LAST row
    # (row-3, confident) despite row-1's chunk failing outright and row-2 being held —
    # a held row or a failed chunk never stops the rows behind it.
    assert processed_row_ids == ["row-1", "row-2", "row-3"]

    # row-1 (failed chunk -> unparseable) and row-2 (ambiguous) are both in the durable
    # queue, each with a reason.
    saved_queue = held_queue.load()
    assert set(saved_queue) == {"row-1", "row-2"}
    assert saved_queue["row-1"]["hold_code"] == confidence.HOLD_UNPARSEABLE
    assert saved_queue["row-1"]["reason"]
    assert saved_queue["row-2"]["hold_code"] == confidence.HOLD_AMBIGUOUS_CANDIDATES
    assert saved_queue["row-2"]["reason"]

    # row-3 (confident) never entered the held queue or the confidence_held manifest —
    # nothing is guessed, nothing waits for it mid-run.
    assert "row-3" not in saved_queue
    saved_verdicts = run_manifest.load()
    assert saved_verdicts.get("row-1") == run_manifest.CONFIDENCE_HELD
    assert saved_verdicts.get("row-2") == run_manifest.CONFIDENCE_HELD
    assert saved_verdicts.get("row-3") != run_manifest.CONFIDENCE_HELD
