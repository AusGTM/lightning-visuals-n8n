"""Quick 260911-w6r (F2-4): `enrich-before-ingest/SKILL.md` step 6's read/bucket fence
-- `held_queue.load()` joined to `held_queue.classify_facet()` per entry -- driven end
to end, for real.

Mirrors `test_review_triage_facets.py`'s own `_read_and_facet` shape (260911-w6q),
which drives the identical call sequence under `review-triage`'s own SKILL.md fence.
`test_skill_sequence_coverage.py`'s COVERED registry is keyed by (skill_name, calls),
so the two skills need two separate covering tests even though the fence they each
document is byte-for-byte the same shape -- registering one against the other's test
would name a nodeid whose own source never mentions the OTHER skill's identity.

New file, not an addition to `test_held_queue_facets.py` (260911-w6p's own file --
its own tests classify dict literals directly, never a loaded queue, so it does not
drive this join at all) or `test_review_triage_facets.py` (a different skill's fence,
and its `_read_and_facet` helper wraps the sink call rather than naming it inline in
the test's own source, which is what the registry validator actually inspects).
"""
import confidence
import held_queue


def _needs_company_entry():
    return {
        "hold_code": confidence.HOLD_NO_MATCH,
        "reason": "no match found for this row",
        "observed_signals": {},
        "resume_fingerprint": "w6r0" + "0" * 60,
        "row": {"email": "secretary@athertonturfclub.com.au", "company": "Atherton Turf Club"},
    }


def _new_person_entry():
    return {
        "hold_code": confidence.HOLD_NO_MATCH,
        "reason": "no match found for this row",
        "observed_signals": {},
        "resume_fingerprint": "w6r1" + "1" * 60,
        "row": {
            "email": "jbusteed@australianturfclub.com.au",
            "company": "Australian Turf Club",
        },
    }


def test_step_6_fence_loads_the_queue_and_facets_what_it_loaded_not_a_dict_literal(tmp_path):
    """Drives `enrich-before-ingest/SKILL.md` step 6's exact fence over the two
    recorded entry shapes (the needs-a-company one and the new-person one, run
    a254d1eda71246a2a964922cdf5c2bd2) -- the whole point being that `classify_facet`
    is fed entries `held_queue.load()` actually returned, never a dict built by hand
    inline and handed straight to the classifier."""
    queue_path = tmp_path / "held_queue.json"
    held_queue.save(
        "run-1",
        {"row-katie": _needs_company_entry(), "row-jimmy": _new_person_entry()},
        path=queue_path,
    )

    held_state = held_queue.classify_read(path=queue_path)
    held_entries = held_queue.load(path=queue_path)
    still_open = held_queue.open_entries(held_entries)
    undecided = {rid: e for rid, e in still_open.items()
                 if held_queue.entry_verb(e) is None}

    # This sitting already knows australianturfclub.com.au is a HubSpot company (the
    # w6p precedent's own resolved-domain source); atherton is not yet known, so it
    # stays needs_company -- the step 6 fence's own w6p safe default.
    known_company_domains = {"australianturfclub.com.au"}
    by_facet = {}
    for rid, entry in undecided.items():
        by_facet.setdefault(
            held_queue.classify_facet(entry, known_company_domains), []).append(rid)

    assert held_state == held_queue.PARSEABLE
    assert by_facet[held_queue.FACET_NEEDS_COMPANY] == ["row-katie"]
    assert by_facet[held_queue.FACET_NEW_PERSON] == ["row-jimmy"]
    # Inline call, so this test function's OWN source text names the sink
    # `test_skill_sequence_coverage.py`'s registry validator checks for.
    assert held_queue.classify_facet(_new_person_entry(), known_company_domains) == \
        held_queue.FACET_NEW_PERSON


def test_a_settled_row_is_dropped_before_the_facet_render_ever_sees_it(tmp_path):
    """`open_entries` -> the `entry_verb is None` filter runs BEFORE `classify_facet`
    -- a row the operator already answered (create/skip/drop) in an earlier sitting
    never reaches the render again."""
    queue_path = tmp_path / "held_queue.json"
    entries = {"row-jimmy": _new_person_entry()}
    held_queue.save("run-1", entries, path=queue_path)
    held_queue.record_verb("row-jimmy", held_queue.VERB_SKIP, "run-2", path=queue_path)

    held_entries = held_queue.load(path=queue_path)
    still_open = held_queue.open_entries(held_entries)
    undecided = {rid: e for rid, e in still_open.items()
                 if held_queue.entry_verb(e) is None}

    assert "row-jimmy" not in still_open
    assert "row-jimmy" not in undecided
