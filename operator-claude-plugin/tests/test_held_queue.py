"""Tests for `held_queue.py` (Phase 61 Plan 04 Task 3, D-61-07 / REVIEW-06/HIGH-6).

Isolation mirrors `test_run_manifest.py`: most tests pass an explicit `path=`; the
location tests isolate via `CLAUDE_PLUGIN_DATA` instead.
"""
import json
import stat

import pytest

import confidence
import durable_paths
import held_queue
import preingest
import run_manifest


def _point_at_a_fake_durable_home(monkeypatch, tmp_path):
    fake_durable = tmp_path / "durable"
    fake_durable.mkdir()
    (fake_durable / "dashboard_artifact.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(fake_durable))


def _outcome(tier="medium", candidate_count=1, **overrides):
    base = dict(parseable=True, match_tier=tier, candidate_count=candidate_count,
                provider_agreement=None, material_conflicts=None,
                judge_adjudicated_fields=None)
    base.update(overrides)
    return preingest.Outcome(**base)


# =====================================================================================
# queue_path()
# =====================================================================================


def test_queue_path_shares_a_parent_with_the_manifest_but_not_its_name(monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert held_queue.queue_path().parent == run_manifest.manifest_path().parent
    assert held_queue.queue_path() != run_manifest.manifest_path()


def test_queue_path_is_not_a_dotfile(monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert not held_queue.queue_path().name.startswith(".")


# =====================================================================================
# fingerprint() — the per-hold_code, observable-signal-only hash (REVIEW-C10/C12)
# =====================================================================================


def test_fingerprint_is_identical_across_a_changed_timestamp_run_id_and_credit_balance():
    """Volatile per-run fields never enter the hash — they are not even parameters."""
    outcome_a = _outcome(tier="medium", candidate_count=1)
    outcome_b = _outcome(tier="medium", candidate_count=1)
    assert held_queue.fingerprint(confidence.HOLD_NO_TABLE_ROW_MATCHED, outcome_a) == \
        held_queue.fingerprint(confidence.HOLD_NO_TABLE_ROW_MATCHED, outcome_b)


def test_fingerprint_is_identical_whether_enrichment_signals_are_present_absent_or_different():
    """The property that makes the whole invariant hold: the free match pass cannot
    observe provider_agreement/material_conflicts/judge_adjudicated_fields, so they
    must never affect the hash."""
    base = held_queue.fingerprint(
        confidence.HOLD_UNADJUDICATED_CONFLICT,
        _outcome(tier="high", candidate_count=0, provider_agreement=None,
                  material_conflicts=None, judge_adjudicated_fields=None),
    )
    with_signals = held_queue.fingerprint(
        confidence.HOLD_UNADJUDICATED_CONFLICT,
        _outcome(tier="high", candidate_count=0,
                  provider_agreement={"jobtitle": ["apollo"]},
                  material_conflicts=[{"group": "country", "fields": ["country"]}],
                  judge_adjudicated_fields={"country": 90}),
    )
    different_signals = held_queue.fingerprint(
        confidence.HOLD_UNADJUDICATED_CONFLICT,
        _outcome(tier="high", candidate_count=0,
                  provider_agreement={"jobtitle": []},
                  material_conflicts=[{"group": "org_type", "fields": ["lv_org_type"]}],
                  judge_adjudicated_fields=None),
    )
    assert base == with_signals == different_signals


def test_fingerprint_changes_when_the_hold_code_differs():
    outcome = _outcome(tier="unknown", candidate_count=0)
    assert held_queue.fingerprint(confidence.HOLD_UNKNOWN_TIER, outcome) != \
        held_queue.fingerprint(confidence.HOLD_NO_MATCH, outcome)


def test_fingerprint_changes_when_match_tier_differs():
    a = held_queue.fingerprint(confidence.HOLD_NO_MATCH, _outcome(tier="none", candidate_count=0))
    b = held_queue.fingerprint(confidence.HOLD_NO_MATCH, _outcome(tier="unknown", candidate_count=0))
    assert a != b


def test_fingerprint_changes_when_candidate_count_differs():
    a = held_queue.fingerprint(confidence.HOLD_AMBIGUOUS_CANDIDATES, _outcome(tier="medium", candidate_count=2))
    b = held_queue.fingerprint(confidence.HOLD_AMBIGUOUS_CANDIDATES, _outcome(tier="medium", candidate_count=3))
    assert a != b


def test_fingerprint_of_an_unparseable_outcome_stays_identical_across_calls():
    a = held_queue.fingerprint(confidence.HOLD_UNPARSEABLE, preingest.UNPARSEABLE_OUTCOME)
    b = held_queue.fingerprint(confidence.HOLD_UNPARSEABLE, preingest.UNPARSEABLE_OUTCOME)
    assert a == b


# =====================================================================================
# build_entry() / save() / load() — the schema, the allowlist, the refusal
# =====================================================================================


def test_build_entry_carries_observed_signals_and_fingerprint_as_separate_fields():
    row = {"row_id": "row-1", "email": "a@example.com", "phone": "0400000000"}
    outcome = _outcome(tier="none", candidate_count=0)
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "no match found", outcome,
        observed_signals={"note": "checked email and linkedin"},
    )
    assert entry["hold_code"] == confidence.HOLD_NO_MATCH
    assert entry["observed_signals"] == {"note": "checked email and linkedin"}
    assert entry["resume_fingerprint"] == held_queue.fingerprint(confidence.HOLD_NO_MATCH, outcome)


def test_build_entry_only_persists_allowlisted_row_fields():
    # `phone` moved from excluded to included by quick 260911-w6o's widening (see
    # test_an_enriched_held_row_survives_the_write_to_disk_end_to_end below) --
    # `seniority` is the still-excluded example here: a real waterfall-promotable
    # key that stays OUT of ROW_FIELD_ALLOWLIST because no consumer needs it.
    row = {"row_id": "row-1", "email": "a@example.com", "seniority": "Director",
           "some_random_spreadsheet_column": "should not be persisted"}
    entry = held_queue.build_entry(row, confidence.HOLD_NO_MATCH, "no match", _outcome())
    assert entry["row"] == {"row_id": "row-1", "email": "a@example.com"}
    assert "seniority" not in entry["row"]
    assert "some_random_spreadsheet_column" not in entry["row"]


def test_save_then_load_round_trips_entries(tmp_path):
    target = tmp_path / "held_queue.json"
    row = {"row_id": "row-1", "email": "a@example.com"}
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "no match found", _outcome())
    key = held_queue.stable_key(row)
    held_queue.save("run-1", {key: entry}, path=target)

    assert held_queue.load(path=target) == {key: entry}


def test_save_writes_at_mode_0600(tmp_path):
    target = tmp_path / "held_queue.json"
    row = {"row_id": "row-1", "email": "a@example.com"}
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "no match", _outcome())
    held_queue.save("run-1", {held_queue.stable_key(row): entry}, path=target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_save_refuses_a_hold_code_outside_the_closed_set(tmp_path):
    target = tmp_path / "held_queue.json"
    bad_entry = {"hold_code": "definitely_not_a_real_code", "reason": "x",
                 "observed_signals": {}, "resume_fingerprint": "abc", "row": {}}
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-1", {"test-entry": bad_entry}, path=target)
    assert not target.exists()


def test_save_refuses_an_arming_shaped_key(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-1", {"armed_row": entry}, path=target)
    assert not target.exists()


def test_save_refuses_an_arming_shaped_value_inside_observed_signals(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry(
        {"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome(),
        observed_signals={"leaked": "n8n_api_key=super-secret"},
    )
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-1", {"test-entry": entry}, path=target)
    assert not target.exists()


def test_a_held_armidale_jockey_club_entry_saves_and_loads_back_unchanged(tmp_path):
    """'Armidale Jockey Club' trips the 'arm' marker as a raw substring, and 'the club
    Secretary' trips 'secret' -- both must survive whole-token matching, exercising
    both the allowlisted `row` scan and the free-text `reason` scan (quick 260911-any)."""
    target = tmp_path / "held_queue.json"
    row = {"row_id": "row-1", "company": "Armidale Jockey Club"}
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "held for the club Secretary to confirm", _outcome(),
    )
    key = held_queue.stable_key(row)
    held_queue.save("run-1", {key: entry}, path=target)

    loaded = held_queue.load(path=target)
    assert loaded[key]["row"]["company"] == "Armidale Jockey Club"
    assert loaded[key]["reason"] == "held for the club Secretary to confirm"


# =====================================================================================
# quick 260911-w6o (F2-1): the entry stores the MERGED row, not the source row.
# =====================================================================================


def _f2_1_response(row_id, properties):
    return {
        "action": "enriched", "object_type": "contacts", "hs_object_id": None,
        "gap_flag": False, "row_id": row_id, "mode": "enrich", "match": None,
        "properties": properties,
    }


def test_an_enriched_held_row_survives_the_write_to_disk_end_to_end(tmp_path):
    """Recorded run a254d1eda71246a2a964922cdf5c2bd2 (2026-09-11, executions
    12365-12376): Jimmy Busteed's held entry carried the source row's blank email
    while execution 12372's Lusha reveal returned his email, phone, mobile and
    LinkedIn -- a 7-credit reveal thrown away at the persist boundary. Katie
    Poggioli's thin enrichment returned only her jobtitle. Feed the MERGED rows
    (never the source rows) through build_entry/save/load and assert they survive,
    and that the still-closed allowlist drops `city`."""
    row_3 = {"row_id": "row-3", "firstname": "Jimmy", "lastname": "Busteed",
             "company": "Australian Turf Club", "email": ""}
    row_2 = {"row_id": "row-2", "firstname": "Katie", "lastname": "Poggioli",
             "company": "Atherton Turf Club",
             "email": "secretary@athertonturfclub.com.au", "jobtitle": "Secretary"}

    merge_report = preingest.merge_enriched([row_3, row_2], [
        _f2_1_response("row-3", {
            "email": "jbusteed@australianturfclub.com.au",
            "phone": "0298765432",
            "mobilephone": "0412345678",
            "lv_linkedin_url": "https://www.linkedin.com/in/jbusteed",
            "city": "Sydney",
        }),
        _f2_1_response("row-2", {"jobtitle": "Club Contact"}),
    ])
    merged_by_id = {row["row_id"]: row for row in merge_report.rows}
    outcome = _outcome(tier="none", candidate_count=0)

    entries = {
        held_queue.stable_key(row): held_queue.build_entry(
            row, confidence.HOLD_NO_MATCH, "no match found", outcome)
        for row in merged_by_id.values()
    }
    target = tmp_path / "held_queue.json"
    held_queue.save("run-1", entries, path=target)
    loaded = held_queue.load(path=target)

    jimmy_key = held_queue.stable_key(merged_by_id["row-3"])
    jimmy = loaded[jimmy_key]["row"]
    assert jimmy["email"] == "jbusteed@australianturfclub.com.au"
    assert jimmy["phone"] == "0298765432"
    assert jimmy["mobilephone"] == "0412345678"
    assert jimmy["lv_linkedin_url"] == "https://www.linkedin.com/in/jbusteed"
    assert "city" not in jimmy  # the allowlist is still closed

    katie_key = held_queue.stable_key(merged_by_id["row-2"])
    katie = loaded[katie_key]["row"]
    # jobtitle is the sole refreshable_contact_props() key (operator ruling
    # 2026-09-11) -- assert the replacement, don't assume the source value survived.
    assert katie["jobtitle"] == "Club Contact"


def test_building_from_the_source_row_instead_of_the_merged_one_still_loses_the_email():
    """Documents the actual F2-1 defect and must keep passing after the fix -- it is
    what makes the assertion above mean 'the caller now passes the merged row', not
    'the allowlist alone fixed this'."""
    row_3 = {"row_id": "row-3", "firstname": "Jimmy", "lastname": "Busteed",
             "company": "Australian Turf Club", "email": ""}
    entry = held_queue.build_entry(
        row_3, confidence.HOLD_NO_MATCH, "no match found", _outcome(tier="none", candidate_count=0))
    assert entry["row"]["email"] == ""
    assert "phone" not in entry["row"]


def test_a_row_for_grant_dewsbury_saves_and_loads_back_unchanged(tmp_path):
    """A firstname that is literally the whole marker word `grant` must not be
    refused -- the `row` payload's scan is key-names-only as of 260911-w6o."""
    target = tmp_path / "held_queue.json"
    row = {"row_id": "row-1", "firstname": "Grant", "lastname": "Dewsbury",
           "company": "Darwin Turf Club"}
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "no match", _outcome())
    key = held_queue.stable_key(row)
    held_queue.save("run-1", {key: entry}, path=target)

    loaded = held_queue.load(path=target)
    assert loaded[key]["row"]["firstname"] == "Grant"
    assert loaded[key]["row"]["lastname"] == "Dewsbury"


def test_a_grant_dewsbury_stable_key_is_a_name_group_key_and_persists(tmp_path):
    """Phase 71 (D-71-04, Pitfall 1): the stable key itself is name-shaped
    (`name::grant|dewsbury|...`) -- a whole-token marker collision that the
    pre-Phase-71 positional key (`row-N`) could never produce. Must still persist."""
    target = tmp_path / "held_queue.json"
    row = {"firstname": "Grant", "lastname": "Dewsbury", "company": "Darwin Turf Club"}
    key = held_queue.stable_key(row)
    assert key == "name::grant|dewsbury|darwin turf club"
    entry = held_queue.build_entry(row, confidence.HOLD_NO_MATCH, "no match", _outcome())
    held_queue.save("run-1", {key: entry}, path=target)

    loaded = held_queue.load(path=target)
    assert key in loaded
    assert loaded[key]["row"]["firstname"] == "Grant"


def test_a_linkedin_only_grant_dewsbury_row_persists_under_its_linkedin_key(tmp_path):
    """The exemption is EXACT MEMBERSHIP in `identity_keys` -- a linkedin-only row's
    key tokenises to contain `grant` and must still be exempt."""
    target = tmp_path / "held_queue.json"
    row = {"linkedin_url": "https://www.linkedin.com/in/grant-dewsbury"}
    key = held_queue.stable_key(row)
    assert key.startswith("linkedin::")
    entry = held_queue.build_entry(row, confidence.HOLD_NO_MATCH, "no match", _outcome())
    held_queue.save("run-1", {key: entry}, path=target)

    loaded = held_queue.load(path=target)
    assert key in loaded


def test_save_refuses_a_key_that_is_marker_shaped_and_not_the_entrys_own_identity(tmp_path):
    """The exemption is EXACT MEMBERSHIP -- a marker-shaped key that is NOT the
    entry's own derived identity is still refused (T-71-01)."""
    target = tmp_path / "held_queue.json"
    row = {"firstname": "Grant", "lastname": "Dewsbury", "company": "Darwin Turf Club"}
    entry = held_queue.build_entry(row, confidence.HOLD_NO_MATCH, "no match", _outcome())
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-1", {"webhook_secret": entry}, path=target)
    assert not target.exists()


def test_company_known_stamp_round_trips_through_save_and_load(tmp_path):
    target = tmp_path / "held_queue.json"
    row = {"email": "jbusteed@australianturfclub.com.au"}
    key = held_queue.stable_key(row)
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "no match", _outcome(),
        company_known={"domain": "AustralianTurfClub.com.au", "source": "step2_match"},
    )
    held_queue.save("run-1", {key: entry}, path=target)

    loaded = held_queue.load(path=target)
    assert loaded[key]["company_known"] == {
        "domain": "australianturfclub.com.au", "source": "step2_match",
    }


def test_company_known_stamp_with_an_invalid_source_refuses_the_whole_save(tmp_path):
    target = tmp_path / "held_queue.json"
    row = {"email": "jbusteed@australianturfclub.com.au"}
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "no match", _outcome(),
        company_known={"domain": "australianturfclub.com.au", "source": "same_run_create"},
    )
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-1", {held_queue.stable_key(row): entry}, path=target)
    assert not target.exists()


def test_stamped_domains_collects_only_present_valid_stamps():
    stamped = held_queue.build_entry(
        {"email": "a@example.com"}, confidence.HOLD_NO_MATCH, "x", _outcome(),
        company_known={"domain": "example.com", "source": "step2_match"},
    )
    unstamped = held_queue.build_entry(
        {"email": "b@example.com"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    entries = {"a": stamped, "b": unstamped, "c": "not-a-dict"}
    assert held_queue.stamped_domains(entries) == {"example.com"}
    assert held_queue.stamped_domains({}) == set()
    assert held_queue.stamped_domains(None) == set()


def test_cross_run_record_verb_settles_a_row_saved_under_a_stable_key(tmp_path):
    """Cross-run invariant (Task 2): save under run A's run_id, load, record_verb under
    run B, reload -- is_settled is True, and a fresh row with a DIFFERENT positional
    row_id but the same identity derives the SAME stable key."""
    target = tmp_path / "held_queue.json"
    row_run_a = {"row_id": "row-1", "email": "jbusteed@australianturfclub.com.au"}
    key = held_queue.stable_key(row_run_a)
    entry = held_queue.build_entry(row_run_a, confidence.HOLD_NO_MATCH, "no match", _outcome())
    held_queue.save("run-A", {key: entry}, path=target)

    held_queue.record_verb(key, held_queue.VERB_CREATE, "run-B", path=target)
    loaded = held_queue.load(path=target)
    assert held_queue.is_settled(loaded[key])

    row_run_b = {"row_id": "row-9", "email": "jbusteed@australianturfclub.com.au"}
    assert held_queue.stable_key(row_run_b) == key


def test_save_still_refuses_every_forbidden_shape_except_a_row_value(tmp_path):
    """The guard that stays: a secret-shaped VALUE inside `observed_signals`, a
    secret-shaped `row_id` key, a secret-shaped `reason`, and a hand-built entry
    whose `row` carries a forbidden-shaped KEY all still raise -- only a
    forbidden-shaped VALUE inside `row` is now admitted (the case the widening
    exists for). Each rejected save leaves the previously-saved queue
    byte-identical."""
    target = tmp_path / "held_queue.json"
    good = held_queue.build_entry(
        {"row_id": "row-1", "email": "a@example.com"},
        confidence.HOLD_NO_MATCH, "no match", _outcome())
    held_queue.save("run-1", {"good-entry": good}, path=target)
    before = target.read_text()

    secret_value_entry = held_queue.build_entry(
        {"row_id": "row-2"}, confidence.HOLD_NO_MATCH, "x", _outcome(),
        observed_signals={"leaked": "n8n_api_key=super-secret"},
    )
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save(
            "run-1", {"good-entry": good, "secret-value-entry": secret_value_entry}, path=target)
    assert target.read_text() == before

    secret_row_id_entry = held_queue.build_entry(
        {"row_id": "armed_row"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save(
            "run-1", {"good-entry": good, "armed_row": secret_row_id_entry}, path=target)
    assert target.read_text() == before

    secret_reason_entry = held_queue.build_entry(
        {"row_id": "row-3"}, confidence.HOLD_NO_MATCH,
        "held pending a webhook token", _outcome())
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save(
            "run-1", {"good-entry": good, "secret-reason-entry": secret_reason_entry}, path=target)
    assert target.read_text() == before

    forbidden_row_key_entry = {
        "hold_code": confidence.HOLD_NO_MATCH, "reason": "x",
        "observed_signals": {}, "resume_fingerprint": "abc",
        "row": {"n8n_api_key": "x"},
    }
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save(
            "run-1", {"good-entry": good, "forbidden-row-key-entry": forbidden_row_key_entry},
            path=target)
    assert target.read_text() == before


def test_persisting_an_email_into_a_held_row_does_not_make_a_no_match_hold_resumable():
    """Finding 6, the blocking safety check: `rows_to_resume` reads the CALLER's rows
    and compares by `fingerprint()`, never `entry['row']` -- so a `confidence_held`
    `no_match` entry whose stored row has gained an email stays in `still_held` when
    the current outcome's fingerprint is unchanged. Putting an email in `row` cannot
    make a hold auto-resume into a send (D-70-11 / the F2 ruling)."""
    outcome = _outcome(tier="none", candidate_count=0)
    entry = held_queue.build_entry(
        {"row_id": "row-1", "email": "jbusteed@australianturfclub.com.au",
         "firstname": "Jimmy", "lastname": "Busteed"},
        confidence.HOLD_NO_MATCH, "no match found", outcome,
    )
    manifest = {"row-1": run_manifest.CONFIDENCE_HELD}
    resume_row = {"row_id": "row-1", "firstname": "Jimmy", "lastname": "Busteed"}

    result = run_manifest.rows_to_resume(
        [resume_row],
        manifest,
        # Phase 71 (D-71-04): keyed by the resuming row's own stable key -- this row
        # has no company, so it falls to the total source-position fallback.
        held_entries={held_queue.stable_key(resume_row): entry},
        current_outcomes={"row-1": outcome},
    )
    assert result.rows == ()
    assert result.still_held == ({"row_id": "row-1", "verdict": run_manifest.CONFIDENCE_HELD},)


def test_a_rejected_save_leaves_a_previously_saved_queue_untouched(tmp_path):
    target = tmp_path / "held_queue.json"
    good = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"good-entry": good}, path=target)
    before = target.read_text()

    bad = {"hold_code": "nope", "reason": "x", "observed_signals": {},
           "resume_fingerprint": "abc", "row": {}}
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-2", {"bad-entry": bad}, path=target)

    assert target.read_text() == before


# =====================================================================================
# load() degrades whole on any anomaly
# =====================================================================================


def test_load_on_a_missing_file_returns_empty(tmp_path):
    assert held_queue.load(path=tmp_path / "held_queue.json") == {}


def test_load_on_malformed_json_returns_empty(tmp_path):
    target = tmp_path / "held_queue.json"
    target.write_text("not json", encoding="utf-8")
    assert held_queue.load(path=target) == {}


def test_load_on_a_truncated_queue_returns_empty(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"entry-a": entry}, path=target)
    full_text = target.read_text()
    target.write_text(full_text[: len(full_text) // 2], encoding="utf-8")
    assert held_queue.load(path=target) == {}


def test_load_on_an_entry_with_an_invalid_hold_code_degrades_the_whole_queue(tmp_path):
    target = tmp_path / "held_queue.json"
    target.write_text(json.dumps({
        "run_id": "run-1", "saved_at": "2026-08-30T00:00:00Z",
        "entries": {
            "entry-a": {"hold_code": confidence.HOLD_NO_MATCH, "reason": "x",
                       "observed_signals": {}, "resume_fingerprint": "abc", "row": {}},
            "entry-b": {"hold_code": "not_a_real_code", "reason": "x",
                       "observed_signals": {}, "resume_fingerprint": "def", "row": {}},
        },
    }), encoding="utf-8")
    assert held_queue.load(path=target) == {}


# =====================================================================================
# classify_read() — the four-way review-pass classification (REVIEW-C11)
# =====================================================================================


def test_classify_read_on_a_missing_file_is_absent(tmp_path):
    assert held_queue.classify_read(path=tmp_path / "held_queue.json") == held_queue.ABSENT


def test_classify_read_on_a_good_file_is_parseable(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"entry-a": entry}, path=target)
    assert held_queue.classify_read(path=target) == held_queue.PARSEABLE


def test_classify_read_on_malformed_json_is_anomalous(tmp_path):
    target = tmp_path / "held_queue.json"
    target.write_text("not json", encoding="utf-8")
    assert held_queue.classify_read(path=target) == held_queue.ANOMALOUS


def test_classify_read_never_reports_a_row_count_for_an_anomalous_file(tmp_path):
    """An unreadable file cannot tell you how many rows it held — the classification
    is a bare word, never a number invented from a file nobody could parse."""
    target = tmp_path / "held_queue.json"
    target.write_text("not json", encoding="utf-8")
    result = held_queue.classify_read(path=target)
    assert isinstance(result, str)
    assert result == held_queue.ANOMALOUS


def test_classify_read_on_a_different_runs_file_is_another_run(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"entry-a": entry}, path=target)
    assert held_queue.classify_read(path=target, expected_run_id="run-2") == held_queue.ANOTHER_RUN
    assert held_queue.classify_read(path=target, expected_run_id="run-1") == held_queue.PARSEABLE


def test_load_still_degrades_whole_regardless_of_classify_reads_answer(tmp_path):
    """The loader's own contract is unchanged by adding classify_read() — it still
    degrades to empty on an anomaly rather than raising or partially trusting."""
    target = tmp_path / "held_queue.json"
    target.write_text("not json", encoding="utf-8")
    assert held_queue.classify_read(path=target) == held_queue.ANOMALOUS
    assert held_queue.load(path=target) == {}


# =====================================================================================
# D-71-05 — a legacy (pre-Phase-71 positional-key) document is refused, not silently
# read as empty.
# =====================================================================================


def _legacy_document_path(tmp_path):
    """The live `a254d1e`-shaped document: positional `row-N` keys, no stamp."""
    target = tmp_path / "held_queue.json"
    target.write_text(json.dumps({
        "run_id": "a254d1eda71246a2a964922cdf5c2bd2", "saved_at": "2026-09-11T00:00:00Z",
        "entries": {
            "row-1": {"hold_code": confidence.HOLD_NO_MATCH, "reason": "no match found",
                      "observed_signals": {}, "resume_fingerprint": "a" * 64,
                      "row": {"email": "", "company": "Australian Turf Club"}},
        },
    }), encoding="utf-8")
    return target


def test_a_legacy_row_n_keyed_document_classifies_anomalous_with_a_wipe_naming_reason(tmp_path):
    target = _legacy_document_path(tmp_path)
    assert held_queue.classify_read(path=target) == held_queue.ANOMALOUS
    assert held_queue.load(path=target) == {}
    reason = held_queue.legacy_reason(path=target)
    assert reason is not None
    assert "held_queue.json" in reason


def test_legacy_reason_is_none_for_a_stable_keyed_document(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"entry-a": entry}, path=target)
    assert held_queue.legacy_reason(path=target) is None


def test_legacy_reason_is_none_for_a_missing_file(tmp_path):
    assert held_queue.legacy_reason(path=tmp_path / "held_queue.json") is None


# =====================================================================================
# Write order relative to run_manifest.py (REVIEW-07's other half)
# =====================================================================================


def test_a_failed_manifest_write_after_a_successful_queue_write_leaves_the_row_unresumed_not_lost(
        tmp_path, monkeypatch):
    """queue-then-manifest: a crash between the two writes leaves a queue entry for a
    row the manifest does not mention. That row is simply re-run on the next resume
    (rows_to_resume treats an absent verdict as "include") — the safe direction, never
    a silent drop."""
    queue_target = tmp_path / "held_queue.json"
    manifest_target = tmp_path / "run_manifest.json"

    row = {"row_id": "row-1", "email": "a@example.com"}
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "no match found", _outcome(tier="none", candidate_count=0))
    key = held_queue.stable_key(row)
    held_queue.save("run-1", {key: entry}, path=queue_target)

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(durable_paths.os, "replace", _boom)
    with pytest.raises(OSError):
        run_manifest.save("run-1", {"row-1": run_manifest.CONFIDENCE_HELD}, path=manifest_target)

    # The queue entry survived; the manifest never recorded the verdict.
    assert held_queue.load(path=queue_target) == {key: entry}
    assert run_manifest.load(path=manifest_target) == {}

    # And a resume treats the row as needing work again — re-run, not stranded.
    result = run_manifest.rows_to_resume(
        [{"row_id": "row-1", "email": "a@example.com"}],
        run_manifest.load(path=manifest_target),
    )
    assert result.rows == ({"row_id": "row-1", "email": "a@example.com"},)
