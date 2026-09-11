"""Tests for `review-triage/SKILL.md`'s held-queue fences (260911-w6q, F2-3).

The operator's 2026-09-11 F2 ruling: review-triage reads BOTH the HubSpot
`lv_enrichment_needs_review` queue and the local `held_queue.json` into one
numbered table, and a held `new_person` row gets a route to HubSpot through the
contact-ingest lane -- created, confirmed by an independent re-read, then marked.

**Reconciled against 260911-w6p's shipped API, not the plan's original guess** (see
this item's SUMMARY for the full reconciliation record):

- The classifier is `held_queue.classify_facet(entry, known_company_domains)`, never
  a domain-free `facet(entry)`. It discriminates on whether the entry's OWN email
  domain is already known to exist as a HubSpot company (the caller-resolved
  `known_company_domains` set) -- never on whether `entry["row"]["company"]` is
  filled in. `KATIE_ENTRY` below carries a company name and still reads
  `needs_company`, because the column is never consulted.
- The mark verb is `held_queue.record_verb(row_id, verb, run_id, path=None)` -- it
  loads and saves itself, collapsing the plan's assumed `load()`/`mark()`/`save()`
  triple into one call.
- The open/undecided split uses the shipped `held_queue.open_entries()` (drops
  `create`/`skip`/`drop`, keeps `retry`) and `held_queue.entry_verb() is None`
  (also drops `retry`) rather than a hand-rolled `not entry.get("status")` filter.
"""
from pathlib import Path

import pytest

import chunking
import confidence
import extraction
import held_queue
import preingest


# =====================================================================================
# Fixtures -- mirrors `test_held_queue_facets.py`'s own `_entry()` helper and the
# recorded run a254d1eda71246a2a964922cdf5c2bd2 shape, reused rather than re-derived.
# =====================================================================================

def _entry(email, company, hold_code=confidence.HOLD_NO_MATCH, status=None, company_known=None):
    entry = {
        "hold_code": hold_code,
        "reason": "no match found for this row",
        "observed_signals": {},
        "resume_fingerprint": "a254d1e" + "0" * 57,
        "row": {"email": email, "company": company},
    }
    if status is not None:
        entry["status"] = status
    if company_known is not None:
        entry["company_known"] = company_known
    return entry


# Jimmy Busteed: a real new person at Australian Turf Club, once that club's own
# domain is known to already be in HubSpot. Phase 71 (D-71-01..03): stamped at
# persist time -- a cold start reads him as new_person from the stamp alone, with
# no domain the test hands the fence directly.
JIMMY_DOMAIN = "australianturfclub.com.au"
JIMMY_ENTRY = _entry(
    "jbusteed@australianturfclub.com.au", "Australian Turf Club",
    company_known={"domain": JIMMY_DOMAIN, "source": "step2_match"})

# Katie Poggioli: carries a company NAME (Atherton Turf Club), but classify_facet
# never reads that column -- what puts her in needs_company is that HER OWN domain
# (athertonturfclub.com.au) is absent from known_company_domains, a fact unrelated
# to whether the company field is populated.
KATIE_ENTRY = _entry("secretary@athertonturfclub.com.au", "Atherton Turf Club")
KATIE_DOMAIN = "athertonturfclub.com.au"

BARRY_ENTRY = _entry("Devraclb@bigpond.net.au", "Devonport Racing Club")  # freemail/ISP
CONFLICT_ENTRY = _entry(
    "someone@example.com", "Some Club", hold_code=confidence.HOLD_UNADJUDICATED_CONFLICT)
RETRY_ENTRY = _entry(
    "retry@example.com", "Retry Club",
    status={"verb": held_queue.VERB_RETRY, "at": "2026-09-01T00:00:00+00:00",
            "run_id": "run-old"})
SETTLED_ENTRY = _entry(
    "done@example.com", "Done Club",
    status={"verb": held_queue.VERB_CREATE, "at": "2026-09-01T00:00:00+00:00",
            "run_id": "run-old"})


def _read_and_facet(path, known_company_domains=frozenset()):
    """The documented step 2b/2c read/bucket fence, run for real — see
    `review-triage/SKILL.md` step 2b. `known_company_domains` here is what an
    in-conversation source (2c) would ADD on top of the cold-start seed -- the seed
    itself is always folded in from the queue's own `company_known` stamps
    (`held_queue.stamped_domains`), never supplied by a caller from scratch."""
    held_state = held_queue.classify_read(path=path)
    held_entries = held_queue.load(path=path)
    still_open = held_queue.open_entries(held_entries)
    undecided = {rid: e for rid, e in still_open.items()
                 if held_queue.entry_verb(e) is None}

    domains = held_queue.stamped_domains(held_entries) | set(known_company_domains)
    by_facet = {}
    for rid, entry in undecided.items():
        by_facet.setdefault(
            held_queue.classify_facet(entry, domains), []).append(rid)

    shown = (set(by_facet.get(held_queue.FACET_NEW_PERSON, []))
             | set(by_facet.get(held_queue.FACET_NEEDS_COMPANY, [])))
    parked_ids = set(still_open) - shown
    return held_state, held_entries, still_open, undecided, by_facet, parked_ids


@pytest.fixture
def recovers_matches(monkeypatch):
    """Mirrors `test_preingest_match.py`'s own fixture of the same name — the match
    webhook answers with an ack, so `match_batch` reads its verdicts from the settled
    execution recovered through `watch.recover_dispatch`, stubbed here."""
    import watch

    def _install(items, *, recovered=True):
        monkeypatch.setattr(
            watch, "recover_dispatch",
            lambda *a, **k: {"recovered": recovered,
                              "responses": [dict(item) for item in items],
                              "run_data": {}},
        )

    return _install


# =====================================================================================
# Task 1 — one held new person, end to end: read, render, create, confirm, mark
# =====================================================================================

def test_one_held_new_person_end_to_end_read_render_create_confirm_mark(
        tmp_path, fake_config, stub_post_transport_factory, recovers_matches):
    """A COLD START: no prior conversation, no domain the test hands the fence
    directly -- Jimmy's own `company_known` stamp (written at persist time,
    D-71-01) is the ONLY thing that puts him in new_person here."""
    queue_path = tmp_path / "held_queue.json"
    held_queue.save(
        "run-1", {"row-jimmy": JIMMY_ENTRY, "row-settled": SETTLED_ENTRY},
        path=queue_path)

    # Behaviour 1: a no_match entry whose row carries an email, bucketed under
    # new-person from its own stamp -- no known_company_domains supplied by the
    # caller at all.
    held_state, held_entries, still_open, undecided, by_facet, parked_ids = (
        _read_and_facet(queue_path))
    assert held_state == held_queue.PARSEABLE
    assert held_queue.stamped_domains(held_entries) == {JIMMY_DOMAIN}
    assert by_facet[held_queue.FACET_NEW_PERSON] == ["row-jimmy"]
    # Same call `_read_and_facet` makes internally, inline here too so this test
    # function's OWN source names the sink `test_skill_sequence_coverage.py` checks
    # for (the read/bucket fence's registered identity).
    assert held_queue.classify_facet(JIMMY_ENTRY, {JIMMY_DOMAIN}) == \
        held_queue.FACET_NEW_PERSON

    # Behaviour 2: a settled entry is excluded from the table by the same fence.
    assert "row-settled" not in still_open
    assert "row-settled" not in undecided
    assert not parked_ids  # jimmy is shown, settled is gone entirely — nothing parked

    # Behaviour 3: the CSV-build fence (4a) turns the chosen row into a dispatch CSV
    # holding exactly the chosen rows, in the ingest lane's own columns.
    chosen_row_ids = ["row-jimmy"]
    send_path = tmp_path / "dispatch.csv"
    create_rows = [held_entries[rid]["row"] for rid in chosen_row_ids]
    created_by_row_id = {
        rid: held_entries[rid]["row"].get("email") for rid in chosen_row_ids}
    create_rows = preingest.strip_enrichment_extras(create_rows)
    create_rows = extraction.strip_row_id(create_rows)
    extraction.write_dispatch_csv(create_rows, send_path)
    send_row_count = len(create_rows)

    assert send_row_count == 1
    assert send_path.exists()
    import csv
    with send_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    assert "row_id" not in header
    assert len(rows) == 1
    assert rows[0][header.index("email")] == "jbusteed@australianturfclub.com.au"

    # Behaviour 4: the confirm fence (4c) joins the re-read back to the held row BY
    # EMAIL, yielding a HubSpot object id.
    recovers_matches([{
        "row_id": "row-1", "action": "proposed", "hs_object_id": "555",
        "match": {"tier": "high"},
    }])
    stub = stub_post_transport_factory()
    cfg = {**fake_config, "max_rows_per_match_request": 50}
    confirm_spec = preingest.build_rows_spec(
        [{"email": email} for email in created_by_row_id.values() if email])
    confirm_plan = chunking.plan_chunks(
        confirm_spec, chunking.chunk_ceiling(cfg, key="max_rows_per_match_request"))
    confirm_outcome = preingest.match_batch(confirm_plan, cfg, transport=stub)
    confirmed = preingest.classify_matches(
        confirm_spec["rows"], confirm_outcome.responses,
        unchecked_row_ids=confirm_outcome.unchecked_row_ids)
    landed = {entry["row"]["email"]: entry["hs_object_id"]
              for entry in confirmed["auto_matched"]}

    assert landed == {"jbusteed@australianturfclub.com.au": "555"}

    # Behaviour 5: mark only the row the re-read actually found.
    run_id = "run-1"
    for row_id, email in created_by_row_id.items():
        if email and email in landed:
            held_queue.record_verb(row_id, held_queue.VERB_CREATE, run_id, path=queue_path)

    reloaded = held_queue.load(path=queue_path)
    assert held_queue.entry_verb(reloaded["row-jimmy"]) == held_queue.VERB_CREATE
    assert held_queue.is_settled(reloaded["row-jimmy"])


def test_a_row_absent_from_the_confirm_re_read_is_not_marked_created(
        tmp_path, fake_config, stub_post_transport_factory, recovers_matches):
    queue_path = tmp_path / "held_queue.json"
    held_queue.save("run-1", {"row-jimmy": JIMMY_ENTRY}, path=queue_path)
    held_entries = held_queue.load(path=queue_path)

    created_by_row_id = {"row-jimmy": held_entries["row-jimmy"]["row"]["email"]}
    recovers_matches([{
        "row_id": "row-1", "action": "proposed", "match": {"tier": "none"},
    }])
    stub = stub_post_transport_factory()
    cfg = {**fake_config, "max_rows_per_match_request": 50}
    confirm_spec = preingest.build_rows_spec(
        [{"email": email} for email in created_by_row_id.values() if email])
    confirm_plan = chunking.plan_chunks(
        confirm_spec, chunking.chunk_ceiling(cfg, key="max_rows_per_match_request"))
    confirm_outcome = preingest.match_batch(confirm_plan, cfg, transport=stub)
    confirmed = preingest.classify_matches(
        confirm_spec["rows"], confirm_outcome.responses,
        unchecked_row_ids=confirm_outcome.unchecked_row_ids)
    landed = {entry["row"]["email"]: entry["hs_object_id"]
              for entry in confirmed["auto_matched"]}

    assert landed == {}

    for row_id, email in created_by_row_id.items():
        if email and email in landed:
            held_queue.record_verb(row_id, held_queue.VERB_CREATE, "run-1", path=queue_path)

    reloaded = held_queue.load(path=queue_path)
    assert held_queue.entry_verb(reloaded["row-jimmy"]) is None, (
        "a row the re-read did not find must stay open, never marked on a hope"
    )


# =====================================================================================
# Task 2 — the other three facets: conflicts renumbered (untouched), needs-a-company,
# nothing-found, parked
# =====================================================================================

def test_needs_company_nothing_found_and_parked_totals_account_for_every_unlisted_open_entry(
        tmp_path):
    queue_path = tmp_path / "held_queue.json"
    entries = {
        "row-jimmy": JIMMY_ENTRY,
        "row-katie": KATIE_ENTRY,
        "row-barry": BARRY_ENTRY,
        "row-conflict": CONFLICT_ENTRY,
        "row-retry": RETRY_ENTRY,
        "row-settled": SETTLED_ENTRY,
    }
    held_queue.save("run-1", entries, path=queue_path)

    held_state, held_entries, still_open, undecided, by_facet, parked_ids = (
        _read_and_facet(queue_path, known_company_domains={JIMMY_DOMAIN}))

    # A held no_match entry with an email whose domain is not (yet) known buckets
    # under needs-a-company, regardless of its own company column (Katie's is filled
    # in) — the column is never consulted.
    assert by_facet[held_queue.FACET_NEEDS_COMPANY] == ["row-katie"]

    # A held no_match entry with no usable email (a freemail/ISP address) buckets
    # under nothing-found and does not appear in the table.
    assert by_facet[held_queue.FACET_NOTHING_FOUND] == ["row-barry"]

    # A held entry whose hold code is not no_match also does not appear in the table.
    assert by_facet[None] == ["row-conflict"]

    # `open_entries` drops only the settled (create/skip/drop) entry; it keeps retry.
    assert set(still_open) == {
        "row-jimmy", "row-katie", "row-barry", "row-conflict", "row-retry"}
    assert "row-settled" not in still_open

    # The parked total is every open entry the table did not list — nothing-found,
    # the non-no_match hold, and the retry-marked entry — no open entry is both
    # unlisted and uncounted.
    assert parked_ids == {"row-barry", "row-conflict", "row-retry"}
    shown = (set(by_facet.get(held_queue.FACET_NEW_PERSON, []))
             | set(by_facet.get(held_queue.FACET_NEEDS_COMPANY, [])))
    assert parked_ids | shown == set(still_open)
    assert not (parked_ids & shown)


def test_a_needs_company_row_re_facets_to_new_person_once_its_domain_is_confirmed():
    """4c's re-offer: the facet does not flip on its own — classify_facet is pure
    over the entry plus the caller's own known_company_domains. Re-supplying the
    domain, once the company lands via enrich-records, is what flips it."""
    known_company_domains = set()
    assert held_queue.classify_facet(KATIE_ENTRY, known_company_domains) == \
        held_queue.FACET_NEEDS_COMPANY

    known_company_domains.add(KATIE_DOMAIN)
    assert held_queue.classify_facet(KATIE_ENTRY, known_company_domains) == \
        held_queue.FACET_NEW_PERSON


def test_default_empty_known_company_domains_never_reads_new_person():
    """The safe default this skill's own step 2b leans on: with nothing confirmed
    yet this sitting, every usable-email entry reads needs_company."""
    assert held_queue.classify_facet(JIMMY_ENTRY) == held_queue.FACET_NEEDS_COMPANY
