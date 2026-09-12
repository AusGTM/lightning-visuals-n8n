"""Tests for `preingest.py`'s post-match lane (Phase 37 Plan 04):

Task 2: `merge_enriched` (join by `row_id`, refuse a duplicate, ignore an unknown).

Task 3: `rows_from_table` (one mapping authority — `preview.label_headers`'s exact
alias lookup — read-only).
"""
import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

import confidence
import extraction
import held_queue
import preingest
import remainder_queue
import suggest_contacts
from dispatch import NotArmedError

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_ROOT.parent
SAMPLES_DIR = PLUGIN_ROOT / "tests" / "samples"


# =====================================================================================
# Phase 70 Plan 06 (D-70-05): `rerequest_unanswered` no longer reads its rows out of the
# POST's own response — the webhook answers with an ack, and every row comes back from
# the settled execution's runData (`chunking.dispatch_and_recover`). These tests
# exercise the RETRY PASS's own logic, not the recovery mechanism, which
# `test_chunking.py` and `test_watch_settle_reporting.py` own end to end — so the sole
# channel is stubbed here at `watch.recover_dispatch` and answers nothing by default.
# =====================================================================================

@pytest.fixture(autouse=True)
def recovers(monkeypatch):
    import watch

    def _install(rows=()):
        monkeypatch.setattr(
            watch, "recover_dispatch",
            lambda *a, **k: {"recovered": True,
                             "responses": [dict(row) for row in rows],
                             "run_data": {}},
        )

    _install()
    return _install


def _rows(n):
    return preingest.build_rows_spec([
        {"firstname": f"First{i}", "lastname": "Doe", "company": "GCTC"}
        for i in range(n)
    ])["rows"]


def _unanswered_ids(result):
    return {entry["row_id"] for entry in result.unanswered}


def _response(row_id, properties=None):
    return {
        "action": "enriched", "object_type": "contacts", "hs_object_id": None,
        "gap_flag": False, "row_id": row_id, "mode": "enrich", "match": None,
        "properties": properties or {},
    }


# =====================================================================================
# Task 2: merge_enriched
# =====================================================================================

def test_a_response_items_properties_merge_onto_the_matching_row_only():
    rows = _rows(2)
    responses = [_response(rows[0]["row_id"], {"email": "first0@x.com"})]

    result = preingest.merge_enriched(rows, responses)

    merged = {r["row_id"]: r for r in result.rows}
    assert merged[rows[0]["row_id"]]["email"] == "first0@x.com"
    assert "email" not in merged[rows[1]["row_id"]]


def test_shuffled_response_order_still_lands_on_the_right_rows():
    rows = _rows(3)
    responses = [
        _response(rows[2]["row_id"], {"email": "third@x.com"}),
        _response(rows[0]["row_id"], {"email": "first@x.com"}),
        _response(rows[1]["row_id"], {"email": "second@x.com"}),
    ]

    result = preingest.merge_enriched(rows, responses)

    merged = {r["row_id"]: r for r in result.rows}
    assert merged[rows[0]["row_id"]]["email"] == "first@x.com"
    assert merged[rows[1]["row_id"]]["email"] == "second@x.com"
    assert merged[rows[2]["row_id"]]["email"] == "third@x.com"


def test_reversing_response_order_changes_no_rows_merged_values():
    rows = _rows(3)
    responses = [
        _response(rows[0]["row_id"], {"email": "first@x.com"}),
        _response(rows[1]["row_id"], {"email": "second@x.com"}),
        _response(rows[2]["row_id"], {"email": "third@x.com"}),
    ]

    forward = preingest.merge_enriched(rows, responses)
    backward = preingest.merge_enriched(rows, list(reversed(responses)))

    def by_id(result):
        return {r["row_id"]: r for r in result.rows}

    assert by_id(forward) == by_id(backward)


def test_two_response_items_sharing_a_row_id_raises_and_merges_nothing():
    rows = _rows(1)
    responses = [
        _response(rows[0]["row_id"], {"email": "a@x.com"}),
        _response(rows[0]["row_id"], {"email": "b@x.com"}),
    ]
    with pytest.raises(preingest.MergeError):
        preingest.merge_enriched(rows, responses)


def test_an_unflattened_dispatch_plan_response_raises_instead_of_dropping_every_row():
    # FINDING 2 (53-WALK-RECORD.md): chunking.dispatch_plan(...).responses is one raw
    # BODY PER CHUNK. Passing it straight through unflattened means merge_enriched
    # sees the chunk's own list as a single "item" -- exactly this shape. It must
    # raise, not silently file every row as unanswered.
    rows = _rows(1)
    unflattened = [[_response(rows[0]["row_id"], {"email": "a@x.com"})]]  # one chunk

    with pytest.raises(preingest.MergeError):
        preingest.merge_enriched(rows, unflattened)


@pytest.mark.parametrize("bad_item", [None, "row-1", 42, ["nested"]])
def test_any_non_dict_response_item_raises_merge_error(bad_item):
    rows = _rows(1)
    with pytest.raises(preingest.MergeError):
        preingest.merge_enriched(rows, [bad_item])


def test_a_response_item_matching_no_row_is_reported_and_merged_nowhere():
    rows = _rows(1)
    responses = [
        _response(rows[0]["row_id"], {"email": "a@x.com"}),
        _response("row-does-not-exist", {"email": "b@x.com"}),
    ]
    result = preingest.merge_enriched(rows, responses)

    assert result.unknown_response_row_ids == ("row-does-not-exist",)
    assert len(result.rows) == 1


def test_removing_the_middle_response_item_does_not_shift_the_trailing_rows():
    # A positional zip would let response[2] (meant for rows[2]) silently attach to
    # rows[1] once rows[1]'s own response item is missing — exactly the misalignment
    # the row_id join makes unreachable.
    rows = _rows(3)
    responses = [
        _response(rows[0]["row_id"], {"email": "first@x.com"}),
        _response(rows[2]["row_id"], {"email": "third@x.com"}),
    ]

    result = preingest.merge_enriched(rows, responses)

    merged = {r["row_id"]: r for r in result.rows}
    assert merged[rows[0]["row_id"]]["email"] == "first@x.com"
    assert "email" not in merged[rows[1]["row_id"]]
    assert merged[rows[2]["row_id"]]["email"] == "third@x.com"
    assert rows[1]["row_id"] in _unanswered_ids(result)


def test_a_row_with_no_matching_response_keeps_its_values_and_is_marked_unanswered():
    rows = _rows(2)
    responses = [_response(rows[0]["row_id"], {})]

    result = preingest.merge_enriched(rows, responses)

    assert rows[1]["row_id"] in _unanswered_ids(result)
    assert rows[0]["row_id"] not in _unanswered_ids(result), (
        "a row whose response carried an empty properties map is distinguishable "
        "from a row with no response at all"
    )


def test_an_unanswered_entry_carries_row_id_row_and_the_true_reason():
    rows = _rows(2)
    responses = [_response(rows[0]["row_id"], {})]

    result = preingest.merge_enriched(rows, responses)

    assert len(result.unanswered) == 1
    entry = result.unanswered[0]
    assert entry["row_id"] == rows[1]["row_id"]
    assert entry["row"]["row_id"] == rows[1]["row_id"]
    assert entry["reason"] == preingest.UNANSWERED_REASON


def test_an_unanswered_row_that_carries_a_source_email_is_still_unanswered():
    # An unanswered row is excluded from the sendable set even when it has an email —
    # we do not know what the waterfall would have added, so it is never guessed at.
    rows = _rows(2)
    rows[1]["email"] = "has-email@x.com"
    responses = [_response(rows[0]["row_id"], {})]

    result = preingest.merge_enriched(rows, responses)

    assert rows[1]["row_id"] in _unanswered_ids(result)


def test_a_properties_key_outside_canonical_props_is_dropped_and_reported():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {"lastmodifieddate": "2026-01-01"})]

    result = preingest.merge_enriched(rows, responses)

    merged = result.rows[0]
    assert "lastmodifieddate" not in merged
    assert {"row_id": rows[0]["row_id"], "key": "lastmodifieddate"} in \
        result.dropped_property_keys


# Ruling 2026-09-11: `email` is `protect_if_current_present: true` in
# config/field_policy.yaml and stays the "operator-typed value is never replaced"
# example -- `jobtitle` is `protect_if_current_present: false` and now behaves
# differently (see test_a_present_jobtitle_is_replaced_by_a_differing_response_value
# below).
def test_a_non_empty_source_value_is_never_overwritten_and_is_reported_as_conflict():
    rows = _rows(1)
    rows[0]["email"] = "amy@x.com"
    responses = [_response(rows[0]["row_id"], {"email": "amy@other.com"})]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["email"] == "amy@x.com"
    assert result.conflicts == (
        {"row_id": rows[0]["row_id"], "field": "email",
         "source_value": "amy@x.com", "provider_value": "amy@other.com",
         "replaced": False},
    )


def test_a_present_jobtitle_is_replaced_by_a_differing_response_value():
    # jobtitle is the one contacts: entry with protect_if_current_present: false
    # (stale_refreshable, ruling 2026-09-11) -- a differing waterfall value wins.
    rows = _rows(1)
    rows[0]["jobtitle"] = "Head of Marketing"
    responses = [_response(rows[0]["row_id"], {"jobtitle": "Head of Marketing and Content"})]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["jobtitle"] == "Head of Marketing and Content"
    assert result.conflicts == (
        {"row_id": rows[0]["row_id"], "field": "jobtitle",
         "source_value": "Head of Marketing",
         "provider_value": "Head of Marketing and Content", "replaced": True},
    )


def test_a_field_absent_from_policy_entirely_keeps_fill_only_behaviour():
    # firstname/lastname have NO contacts: entry in field_policy.yaml at all --
    # refreshable_contact_props() cannot name a key it never saw, so this must
    # keep today's protect behaviour exactly like a policy-key-less field.
    rows = _rows(1)
    rows[0]["firstname"] = "Amy"
    responses = [_response(rows[0]["row_id"], {"firstname": "Amelia"})]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["firstname"] == "Amy"
    assert result.conflicts == (
        {"row_id": rows[0]["row_id"], "field": "firstname",
         "source_value": "Amy", "provider_value": "Amelia", "replaced": False},
    )


def test_an_empty_source_value_is_filled_by_the_response():
    rows = _rows(1)
    rows[0]["jobtitle"] = ""
    responses = [_response(rows[0]["row_id"], {"jobtitle": "Analyst"})]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["jobtitle"] == "Analyst"
    assert not result.conflicts


def test_merge_enriched_does_not_mutate_input_rows():
    rows = _rows(1)
    snapshot = dict(rows[0])
    responses = [_response(rows[0]["row_id"], {"jobtitle": "Analyst"})]

    preingest.merge_enriched(rows, responses)

    assert rows[0] == snapshot


def test_every_merged_row_key_is_in_the_merge_allowlist_or_row_id():
    # Phase 65 Plan 02 (RICH-04): broadened from `..._in_canonical_props_or_row_id` --
    # the merge allowlist is now the UNION of canonical_props() and
    # promotable_contact_props(), so a widened key (seniority) must be permitted here
    # too, not just the three canonical keys the old assertion drove.
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {
        "email": "a@x.com", "phone": "555", "linkedin_url": "https://x.com",
        "seniority": "Director",
    })]

    result = preingest.merge_enriched(rows, responses)

    allowed = (
        set(extraction.canonical_props()) | set(preingest.promotable_contact_props())
        | {"row_id"}
    )
    for row in result.rows:
        assert set(row) <= allowed


# =====================================================================================
# Phase 65 Plan 02 (RICH-04): merge_enriched's allowlist widened to the union of
# extraction.canonical_props() and the field-policy's promotable contact keys, so a
# provider-returned field like `seniority` survives onto a blank CREATE row instead of
# being dropped before the fill-versus-conflict rule is ever consulted.
# =====================================================================================

def test_the_shipped_field_policy_copy_is_byte_identical_to_the_repo_source():
    if not preingest.REPO_POLICY_PATH.exists():
        pytest.skip(
            "no repo root beside this checkout (installed plugin tree) -- the parity "
            "pin only bites in a dev checkout"
        )
    assert preingest.PLUGIN_POLICY_PATH.exists(), (
        "the plugin must ship its own config/field_policy.yaml copy -- the "
        "marketplace ships the plugin directory alone, so a repo-root-only lookup "
        "resolves to nothing in an installed plugin tree (RICH-04 finding 2)"
    )
    assert (
        preingest.PLUGIN_POLICY_PATH.read_bytes()
        == preingest.REPO_POLICY_PATH.read_bytes()
    )

    # Phase 65 Plan 02 Task 3 (SAFE-01): the widening changes only WHICH keys may be
    # written, never whether a candidate clears the bar to be written at all -- pin
    # every contacts: entry's min_confidence to this plan's own Findings, so no future
    # edit to either copy can quietly lower a threshold under cover of this widening.
    import yaml as _yaml
    data = _yaml.safe_load(preingest.REPO_POLICY_PATH.read_text(encoding="utf-8"))
    contacts = data["contacts"]
    expected_min_confidence = {
        "email": 80, "city": 80, "state": 80, "country": 80,
        "hs_state_code": 80, "hs_country_region_code": 80, "phone": 80,
        "mobilephone": 85, "jobtitle": 75, "lv_linkedin_url": 85,
        "seniority": 75, "lv_persona_group": 75,
        # Phase 72 Plan 02 (D-72-04): write-only mirror of lv_linkedin_url.
        "hs_linkedin_url": 85,
        # Phase 72 Plan 05 (D-72-11/D-72-12): the single overflow slots for a second
        # phone/mobile a live waterfall disagreement supplies, promote_to_canonical:
        # false (decorative -- see field_policy.yaml's own comment), so
        # test_promotable_contact_props_... below correctly excludes them without
        # code changes; only their min_confidence is pinned here.
        "lv_phone_2": 80, "lv_mobilephone_2": 85,
    }
    assert set(contacts) == set(expected_min_confidence), (
        "the contacts: key set drifted from this plan's own Findings -- update both "
        "this test and promotable_contact_props' expectations together"
    )
    for key, expected in expected_min_confidence.items():
        assert contacts[key]["min_confidence"] == expected, (
            f"{key}'s min_confidence changed from {expected} -- SAFE-01 forbids "
            "lowering a threshold as a rider on this widening"
        )


def test_promotable_contact_props_names_exactly_the_policys_promotable_contact_keys():
    # Phase 72 Plan 02 (D-72-02): renamed off "the twelve" (now thirteen, with
    # hs_linkedin_url) -- the job this test pins is "the function returns exactly the
    # policy's contacts: keys carrying promote_to_canonical: true", derived fresh from
    # the YAML via PyYAML, never a restated literal count or list.
    import yaml as _yaml

    policy_path = preingest.resolve_policy_path()
    data = _yaml.safe_load(Path(policy_path).read_text(encoding="utf-8"))
    contacts = data["contacts"]
    expected = sorted(
        key for key, entry in contacts.items()
        if isinstance(entry, dict) and entry.get("promote_to_canonical") is True
    )

    assert sorted(preingest.promotable_contact_props()) == expected


def test_a_policy_promotable_key_fills_a_blank_row_field_instead_of_being_dropped():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {
        "email": "amy@example.com", "seniority": "Director",
        # Phase 72 Plan 03 (D-72-19): `lv_linkedin_url` is now aliased onto the
        # row's own `linkedin_url` key before the allowlist test -- this fills the
        # CSV canonical field, never a survivng `lv_linkedin_url` key.
        "lv_linkedin_url": "https://li/amy",
    })]

    result = preingest.merge_enriched(rows, responses)

    merged = result.rows[0]
    assert merged["seniority"] == "Director"
    assert merged["linkedin_url"] == "https://li/amy"
    assert "lv_linkedin_url" not in merged
    dropped_keys = {entry["key"] for entry in result.dropped_property_keys}
    assert "seniority" not in dropped_keys
    assert "lv_linkedin_url" not in dropped_keys


def test_a_key_in_neither_set_is_still_dropped_and_reported():
    # RICH-04 boundary: a key in NEITHER canonical_props() nor promotable_contact_props()
    # (lastmodifieddate is in neither) is still dropped and still reported -- the union
    # widens, it does not turn the allowlist into "accept anything".
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {"lastmodifieddate": "2026-01-01"})]

    result = preingest.merge_enriched(rows, responses)

    merged = result.rows[0]
    assert "lastmodifieddate" not in merged
    assert {"row_id": rows[0]["row_id"], "key": "lastmodifieddate"} in \
        result.dropped_property_keys


# =====================================================================================
# Phase 72 Plan 03 (D-72-19): `PROVIDER_KEY_ALIASES` -- the waterfall's promotable
# name for LinkedIn and the CSV's canonical name are one logical field under two
# vocabularies.
# =====================================================================================

def test_provider_key_aliases_maps_lv_linkedin_url_onto_the_rows_own_linkedin_url_key():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {"lv_linkedin_url": "https://li/amy"})]

    result = preingest.merge_enriched(rows, responses)

    merged = result.rows[0]
    assert merged["linkedin_url"] == "https://li/amy"
    assert "lv_linkedin_url" not in merged
    assert preingest.PROVIDER_KEY_ALIASES == {"lv_linkedin_url": "linkedin_url"}


def test_a_response_carrying_both_linkedin_names_resolves_to_one_key_with_a_conflict_recorded():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {
        "lv_linkedin_url": "https://li/aliased", "linkedin_url": "https://li/direct",
    })]

    result = preingest.merge_enriched(rows, responses)

    merged = result.rows[0]
    assert "lv_linkedin_url" not in merged
    linkedin_keys = [k for k in merged if k == "linkedin_url"]
    assert len(linkedin_keys) == 1, "never two keys for one aliased field"
    conflict_fields = {c["field"] for c in result.conflicts}
    assert "linkedin_url" in conflict_fields


def test_strip_enrichment_extras_is_inert_for_a_real_merged_row_carrying_every_promotable_key():
    # Build the row from the DERIVED lists, never a hardcoded key list. `hs_linkedin_
    # url` is excluded from the SIMULATED response on purpose (D-72-04): it is a
    # lane-side-only write target produced inside the n8n merge wrapper from the SAME
    # canonicalized linkedin value, never a key a real provider `properties` response
    # carries -- so a real merged row never has it to strip in the first place.
    # `lv_linkedin_url` IS a real response key; `PROVIDER_KEY_ALIASES` aliases it onto
    # `linkedin_url` before it ever reaches the merged row.
    promotable = set(preingest.promotable_contact_props())
    lane_only_write_targets = {"hs_linkedin_url"}
    assert promotable - set(extraction.canonical_props()) - lane_only_write_targets == {
        "lv_linkedin_url",
    }, "PROVIDER_KEY_ALIASES only names lv_linkedin_url -- update this test if that changes"

    rows = _rows(1)
    properties = {key: f"value-for-{key}" for key in promotable - lane_only_write_targets}
    responses = [_response(rows[0]["row_id"], properties)]

    result = preingest.merge_enriched(rows, responses)
    merged = result.rows[0]

    assert "lv_linkedin_url" not in merged
    assert "hs_linkedin_url" not in merged
    assert set(merged) <= set(extraction.canonical_props()) | {"row_id"}

    stripped = preingest.strip_enrichment_extras([merged])
    assert stripped == [merged]


def test_write_dispatch_csv_accepts_a_merged_row_with_every_promotable_key(tmp_path):
    rows = _rows(1)
    rows[0]["email"] = "amy@example.com"
    promotable = set(preingest.promotable_contact_props())
    properties = {
        key: f"value-for-{key}"
        for key in promotable - {"hs_linkedin_url", "email"}
    }
    responses = [_response(rows[0]["row_id"], properties)]

    result = preingest.merge_enriched(rows, responses)
    sendable = extraction.strip_row_id(preingest.strip_enrichment_extras(result.rows))

    extraction.write_dispatch_csv(sendable, tmp_path / "dispatch.csv")  # must not raise


# =====================================================================================
# Phase 72 Plan 03 (D-72-05/D-72-07/D-72-20): on a CREATE, the provider wins over the
# CSV for every non-identity field; the CSV loser is recorded in the merge report
# only. `provider_sourced_fields` computes the round-level, truthful `source_by_field`
# D-72-22's ingest-lane confidence override reads.
# =====================================================================================

def test_merge_enriched_without_create_row_ids_is_byte_identical_to_the_empty_set():
    rows = _rows(1)
    rows[0]["seniority"] = "Old"
    responses = [_response(rows[0]["row_id"], {"seniority": "New"})]

    default_call = preingest.merge_enriched(rows, responses)
    explicit_empty = preingest.merge_enriched(rows, responses, create_row_ids=frozenset())

    assert default_call == explicit_empty
    assert default_call.rows[0]["seniority"] == "Old", "not a create -- CSV protected"


@pytest.mark.parametrize("field_name,csv_value,provider_value", [
    ("jobtitle", "Old Title", "New Title"),
    ("phone", "0400000001", "0400000002"),
    ("mobilephone", "0411111111", "0422222222"),
    ("seniority", "Manager", "Director"),
    ("city", "Sydney", "Melbourne"),
    ("state", "NSW", "VIC"),
    ("country", "Australia", "New Zealand"),
    ("hs_state_code", "NSW", "VIC"),
    ("hs_country_region_code", "AU", "NZ"),
    ("lv_persona_group", "Ops", "Sales"),
    ("linkedin_url", "https://li/old", "https://li/new"),
])
def test_a_create_row_conflict_promotes_the_provider_value_for_non_identity_fields(
        field_name, csv_value, provider_value):
    rows = _rows(1)
    rows[0][field_name] = csv_value
    # D-72-19: the response uses the WATERFALL's own name for linkedin -- the alias
    # resolves it onto the row's `linkedin_url` key before this rule ever runs.
    response_key = "lv_linkedin_url" if field_name == "linkedin_url" else field_name
    responses = [_response(rows[0]["row_id"], {response_key: provider_value})]

    result = preingest.merge_enriched(
        rows, responses, create_row_ids={rows[0]["row_id"]},
    )

    assert result.rows[0][field_name] == provider_value
    assert result.conflicts == (
        {"row_id": rows[0]["row_id"], "field": field_name,
         "source_value": csv_value, "provider_value": provider_value,
         "replaced": True},
    )


@pytest.mark.parametrize("field_name", ["email", "firstname", "lastname", "company"])
def test_a_create_row_conflict_never_replaces_an_identity_field(field_name):
    rows = _rows(1)
    rows[0][field_name] = "operator-typed"
    responses = [_response(rows[0]["row_id"], {field_name: "provider-said"})]

    result = preingest.merge_enriched(
        rows, responses, create_row_ids={rows[0]["row_id"]},
    )

    assert result.rows[0][field_name] == "operator-typed"
    assert result.conflicts == (
        {"row_id": rows[0]["row_id"], "field": field_name,
         "source_value": "operator-typed", "provider_value": "provider-said",
         "replaced": False},
    )
    assert preingest.IDENTITY_FIELDS == ("email", "firstname", "lastname", "company")


def test_a_create_row_id_does_not_affect_a_different_row_not_named():
    rows = _rows(2)
    rows[0]["seniority"] = "Old"
    rows[1]["seniority"] = "Old2"
    responses = [
        _response(rows[0]["row_id"], {"seniority": "New"}),
        _response(rows[1]["row_id"], {"seniority": "New2"}),
    ]

    result = preingest.merge_enriched(rows, responses, create_row_ids={rows[0]["row_id"]})

    by_id = {r["row_id"]: r for r in result.rows}
    assert by_id[rows[0]["row_id"]]["seniority"] == "New", "create -- provider wins"
    assert by_id[rows[1]["row_id"]]["seniority"] == "Old2", "not a create -- CSV protected"


def test_a_blank_csv_value_is_filled_from_the_provider_on_a_create_row_too():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {"seniority": "Director"})]

    result = preingest.merge_enriched(rows, responses, create_row_ids={rows[0]["row_id"]})

    assert result.rows[0]["seniority"] == "Director"
    assert result.conflicts == ()


def test_provider_sourced_fields_names_a_field_answered_for_every_row_and_omits_a_partial_one():
    rows = _rows(2)
    responses = [
        _response(rows[0]["row_id"], {"seniority": "Director", "jobtitle": "CEO"}),
        _response(rows[1]["row_id"], {"seniority": "Manager"}),  # no jobtitle for row 1
    ]

    result = preingest.merge_enriched(rows, responses)

    assert preingest.provider_sourced_fields(result) == {"seniority"}


def test_provider_sourced_fields_is_empty_when_nothing_was_answered():
    rows = _rows(1)
    result = preingest.merge_enriched(rows, [])
    assert preingest.provider_sourced_fields(result) == set()


def test_provider_sourced_fields_never_names_a_dropped_key():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {
        "seniority": "Director", "lastmodifieddate": "2026-01-01",
    })]

    result = preingest.merge_enriched(rows, responses)

    assert preingest.provider_sourced_fields(result) == {"seniority"}


def test_held_queue_build_entry_key_set_is_unchanged_by_this_plan():
    row = {"row_id": "row-1", "email": "a@example.com"}
    outcome = SimpleNamespace(match_tier=None, candidate_count=None)

    entry = held_queue.build_entry(row, confidence.HOLD_NO_MATCH, "test reason", outcome)

    assert set(entry) == {
        "hold_code", "reason", "observed_signals", "resume_fingerprint", "row",
    }


def test_strip_enrichment_extras_drops_exactly_the_policy_only_keys():
    # Phase 72 Plan 02 (D-72-01): `seniority` is now also a `column_mapping.yaml`
    # canonical alias target, so it is no longer an "extra" -- `lv_linkedin_url`
    # (D-72-19's naming fork, resolved in a later plan) is the one remaining key in
    # `promotable_contact_props() - canonical_props()` this function still strips.
    row = {
        "row_id": "row-1", "email": "amy@example.com", "seniority": "Director",
        "lv_linkedin_url": "https://li/amy",
    }

    stripped = preingest.strip_enrichment_extras([row])

    assert stripped[0] == {
        "row_id": "row-1", "email": "amy@example.com", "seniority": "Director",
    }
    # never mutates the input row
    assert row == {
        "row_id": "row-1", "email": "amy@example.com", "seniority": "Director",
        "lv_linkedin_url": "https://li/amy",
    }


def test_strip_enrichment_extras_passes_a_row_without_the_widened_keys_through_unchanged():
    row = {"row_id": "row-1", "email": "amy@example.com"}

    stripped = preingest.strip_enrichment_extras([row])

    assert stripped[0] == row


def test_write_dispatch_csv_still_raises_on_a_genuinely_unknown_key_after_the_strip(tmp_path):
    row = {"email": "amy@example.com", "not_a_real_property": "x"}

    stripped = preingest.strip_enrichment_extras([row])
    assert "not_a_real_property" in stripped[0], (
        "strip_enrichment_extras only drops the closed, named policy-only set -- an "
        "invented key must survive it and still reach STRUCT-01"
    )

    with pytest.raises(extraction.ExtractionError) as exc_info:
        extraction.write_dispatch_csv(stripped, tmp_path / "dispatch.csv")
    assert exc_info.value.code == "non_canonical_key_in_row"


# bug_002 (2026-08-29 ultrareview): each of build_rows_spec, merge_enriched,
# hold_emailless and write_dispatch_csv was individually correct and individually
# tested, but chained exactly as `enrich-before-ingest/SKILL.md` step 7 documents,
# `row_id` (minted by build_rows_spec, preserved by merge_enriched and hold_emailless)
# reached write_dispatch_csv's STRUCT-01 guard and raised before a byte was written —
# no test drove all four stages in one sequence. This one does, calling
# `strip_row_id` exactly where the skill's step 7 now calls it: between
# `hold_emailless` and `write_dispatch_csv`.
#
# Phase 65 Plan 02 (RICH-04): extended so the response carries a widened key
# (`seniority`) -- proving `preingest.strip_enrichment_extras` (inserted right before
# `strip_row_id`, per the skill's own step 7) is actually DRIVEN by this sequence, not
# merely registered in COVERED. Without it, `seniority` would still be on the row when
# `write_dispatch_csv` raises `non_canonical_key_in_row` -- see the negative-half test
# below.
def test_the_documented_step_7_sequence_reaches_a_written_dispatch_csv(tmp_path):
    rows = _rows(2)
    # Phase 70 Plan 06 (D-70-11): the lane's head is `partition_for_ingest` now, so the
    # response items carry the match signals `confidence.assess` reads — both rows
    # match high-tier here, and the SECOND is held on the email, exactly as before.
    responses = [
        {**_response(rows[0]["row_id"],
                     {"email": "amy@example.com", "seniority": "Director"}),
         "outcome_contract_version": preingest.OUTCOME_CONTRACT_VERSION,
         "match": {"tier": "high"}, "candidate_count": 1},
        {**_response(rows[1]["row_id"], {}),  # no email supplied — this row is held
         "outcome_contract_version": preingest.OUTCOME_CONTRACT_VERSION,
         "match": {"tier": "high"}, "candidate_count": 1},
    ]

    merge_report = preingest.merge_enriched(rows, responses)
    assert merge_report.rows[0]["seniority"] == "Director"
    sendable, held = preingest.partition_for_ingest(merge_report.rows, responses)
    assert len(sendable) == 1
    assert len(held) == 1
    assert held[0]["hold_code"] is None, "held on the email, not on a confidence signal"

    sendable = preingest.strip_enrichment_extras(sendable)
    sendable = extraction.strip_row_id(sendable)

    out_path = tmp_path / "dispatch.csv"
    extraction.write_dispatch_csv(sendable, out_path)  # must not raise

    with out_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        written_rows = list(reader)

    assert "row_id" not in header
    assert len(written_rows) == 1
    assert written_rows[0][header.index("email")] == "amy@example.com"


# =====================================================================================
# Phase 65 Plan 02 Task 2 (RICH-04): trace every merge_enriched caller's downstream
# path and pin the edges the widening moves.
# =====================================================================================

def test_without_the_new_strip_the_step_7_chain_raises_non_canonical_key_in_row(tmp_path):
    # The negative half of the extended step-7 sequence test above -- proves
    # `strip_enrichment_extras` is load-bearing, not decorative: the SAME chain with
    # only `strip_row_id` (no `strip_enrichment_extras`) must still raise.
    # Phase 72 Plan 03 (D-72-19): `lv_linkedin_url` is now ALIASED onto `linkedin_url`
    # (canonical) before the allowlist test, so it no longer demonstrates this --
    # `hs_linkedin_url` is the one remaining promotable-but-not-canonical key
    # (D-72-04: a lane-side-only write target no real provider response carries, but
    # still admitted by `allowed_keys` if a response ever named it, exactly like
    # `lv_linkedin_url` before this plan).
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"],
                            {"email": "amy@example.com", "hs_linkedin_url": "https://li/amy"})]

    merge_report = preingest.merge_enriched(rows, responses)
    sendable, held = extraction.hold_emailless(merge_report.rows)
    sendable = extraction.strip_row_id(sendable)  # no strip_enrichment_extras call

    with pytest.raises(extraction.ExtractionError) as exc_info:
        extraction.write_dispatch_csv(sendable, tmp_path / "dispatch.csv")
    assert exc_info.value.code == "non_canonical_key_in_row"


def test_the_suggest_contacts_path_tolerates_a_widened_key_through_validate():
    # Caller B (suggest-contacts): merged rows -> rejoin_enriched -> partition_for_
    # dispatch -> extraction.validate -- a widened key must be ACCEPTED (never
    # rejected), reported in dropped_keys, because that path reaches no CSV of its own
    # (SKILL.md step 7's dispatch block is the one strip site both callers share).
    # Phase 72 Plan 03 (D-72-19): `hs_linkedin_url` is the key that still demonstrates
    # this -- `lv_linkedin_url` is now aliased onto canonical `linkedin_url`.
    rows = preingest.build_rows_spec(
        [{"firstname": "Amy", "lastname": "Smith", "company": "Acme"}]
    )["rows"]
    records = [{"row": rows[0], "provenance": {"input": "test", "locator": "test"}}]

    merge_report = preingest.merge_enriched(
        rows, [_response(rows[0]["row_id"], {
            "email": "amy@acme.com", "hs_linkedin_url": "https://li/amy",
        })],
    )
    records = suggest_contacts.rejoin_enriched(records, merge_report.rows)

    sendable_rows, held = suggest_contacts.partition_for_dispatch(
        [r["row"] for r in records], {"Acme": "acme.com"},
    )
    assert len(sendable_rows) == 1, "the email domain matches the company's own domain"

    result = extraction.validate(suggest_contacts.round_artifact(records))

    assert len(result.accepted) == 1
    assert {"index": 0, "key": "hs_linkedin_url"} in result.dropped_keys
    assert result.accepted[0]["row"]["email"] == "amy@acme.com"
    assert "hs_linkedin_url" not in result.accepted[0]["row"]


def test_a_rerequest_response_carrying_a_widened_key_keeps_it_on_the_row(
        fake_config, stub_module_transport_factory, recovers):
    # Caller C: preingest.rerequest_unanswered re-enters merge_enriched, so it
    # inherits the union with no separate change.
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [])
    assert len(merge_report.unanswered) == 1

    transport = stub_module_transport_factory()
    recovers([_response(rows[0]["row_id"],
                        {"email": "amy@example.com", "seniority": "Director"})])
    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True,
        {**fake_config, "max_records_per_chunk": 10}, transport=transport,
    )

    merged = {r["row_id"]: r for r in result.rows}
    assert merged[rows[0]["row_id"]]["seniority"] == "Director"


def test_promotable_contact_props_is_empty_when_no_policy_resolves(tmp_path):
    assert preingest.promotable_contact_props(
        policy_path=tmp_path / "nonexistent-field-policy.yaml"
    ) == []


def test_promotable_contact_props_is_empty_when_the_policy_has_no_contacts_section(tmp_path):
    policy_path = tmp_path / "field_policy.yaml"
    policy_path.write_text("companies:\n  domain:\n    class: manual_protected\n")

    assert preingest.promotable_contact_props(policy_path=policy_path) == []


def test_merge_allowlist_falls_back_to_canonical_props_when_the_policy_is_unreadable(
        monkeypatch, tmp_path):
    # Points BOTH resolution steps at nonexistent paths so resolve_policy_path(None)
    # (what merge_enriched calls internally) returns None -- the fallback path a real
    # unresolvable-policy install would hit, not just the explicit-argument path.
    monkeypatch.setattr(preingest, "PLUGIN_POLICY_PATH", tmp_path / "no-plugin-copy.yaml")
    monkeypatch.setattr(preingest, "REPO_POLICY_PATH", tmp_path / "no-repo-copy.yaml")

    assert preingest.promotable_contact_props() == []
    assert preingest.refreshable_contact_props() == [], (
        "an unresolvable policy must degrade to protect-everything, never to "
        "replace-everything -- the opposite direction from promotable_contact_props()"
    )

    # Phase 72 Plan 03 (D-72-19): `lv_linkedin_url` no longer demonstrates this --
    # PROVIDER_KEY_ALIASES fires BEFORE the allowlist test, so it lands as canonical
    # `linkedin_url` even with the policy unresolvable. `hs_linkedin_url` is the key
    # that still demonstrates the fallback: it is promotable-only, never aliased, so
    # it is dropped exactly when `promotable_contact_props()` degrades to `[]`.
    rows = _rows(1)
    rows[0]["jobtitle"] = "Director"
    responses = [_response(rows[0]["row_id"], {
        "email": "a@x.com", "phone": "555", "hs_linkedin_url": "https://li/x",
        "jobtitle": "Analyst",
    })]
    result = preingest.merge_enriched(rows, responses)

    allowed = set(extraction.canonical_props()) | {"row_id"}
    for row in result.rows:
        assert set(row) <= allowed
    assert {"row_id": rows[0]["row_id"], "key": "hs_linkedin_url"} in result.dropped_property_keys
    assert result.rows[0]["jobtitle"] == "Director", (
        "with the policy unresolvable, even jobtitle -- normally refreshable -- "
        "must NOT be replaced"
    )


def test_the_allowlist_is_a_union_and_a_shared_key_behaves_as_before():
    # RICH-04 adjacency: email/phone/jobtitle are in BOTH sets -- they must appear
    # once in the union (never a second pass). `email` is still fill-only and
    # unchanged by this plan, so it still stands in for "the union changes nothing
    # about whether a present value is overwritten" -- `jobtitle`, the third shared
    # key, deliberately no longer behaves this way (ruling 2026-09-11, see
    # test_a_present_jobtitle_is_replaced_by_a_differing_response_value above).
    # Phase 72 Plan 01 (D-72-03): `mobilephone` split off the `phone` alias group into
    # its own canonical target, and it is ALSO a `field_policy.yaml` promotable-contact
    # key (fill_blank_only @ 85) -- a fourth shared key, added by widening the alias
    # table, not a regression of the three above.
    # Phase 72 Plan 02 (D-72-01): the remaining six promotable_contact_props() keys
    # (city, state, country, hs_state_code, hs_country_region_code, seniority,
    # lv_persona_group -- all but lv_linkedin_url, D-72-19's naming fork) now have
    # canonical alias targets too, so they join the shared set.
    shared = set(extraction.canonical_props()) & set(preingest.promotable_contact_props())
    assert shared == {
        "email", "phone", "jobtitle", "mobilephone",
        "city", "state", "country", "hs_state_code", "hs_country_region_code",
        "seniority", "lv_persona_group",
    }

    rows = _rows(1)
    rows[0]["email"] = "amy@x.com"
    responses = [_response(rows[0]["row_id"], {"email": "amy@other.com"})]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["email"] == "amy@x.com"
    assert result.conflicts == (
        {"row_id": rows[0]["row_id"], "field": "email",
         "source_value": "amy@x.com", "provider_value": "amy@other.com",
         "replaced": False},
    )


def test_response_property_order_does_not_change_the_merged_row():
    rows = _rows(1)
    forward = _response(rows[0]["row_id"], {"email": "a@x.com", "seniority": "Director"})
    reordered = _response(rows[0]["row_id"], {"seniority": "Director", "email": "a@x.com"})
    assert list(forward["properties"].keys()) != list(reordered["properties"].keys())

    result_forward = preingest.merge_enriched(rows, [forward])
    result_reordered = preingest.merge_enriched(rows, [reordered])

    assert result_forward.rows[0] == result_reordered.rows[0]


def test_merging_the_same_responses_twice_changes_no_value():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {"email": "a@x.com", "seniority": "Director"})]

    first = preingest.merge_enriched(rows, responses)
    second = preingest.merge_enriched(list(first.rows), responses)

    assert second.rows[0] == first.rows[0]
    assert second.conflicts == (), "an identical incoming value is never a conflict"


def test_a_merged_row_with_a_widened_key_builds_a_remainder_queue_entry_untouched():
    # Destination D (remainder queue half): remainder_queue.build_entry stores its
    # spec verbatim (only a forbidden-name scan, never a key-set filter), so a
    # widened key survives onto the stored entry -- this IS the point of the
    # widening for this path (Finding 8).
    rows = _rows(1)
    merge_report = preingest.merge_enriched(
        rows, [_response(rows[0]["row_id"], {"email": "a@x.com", "seniority": "Director"})],
    )

    entry = remainder_queue.build_entry(
        {"rows": list(merge_report.rows), "object_type": "contacts"},
        remainder_queue.REASON_CEILING_BREACH, note="test",
    )

    assert entry["spec"]["rows"][0]["seniority"] == "Director"


def test_a_merged_row_with_a_widened_key_builds_a_held_queue_entry_without_raising():
    # Destination D (held-queue half) -- CORRECTS Finding 8's grep-based claim: unlike
    # remainder_queue, held_queue.build_entry does NOT carry an arbitrary row key
    # through untouched. `held_queue.ROW_FIELD_ALLOWLIST` is a DELIBERATE, closed,
    # enumerated allowlist (module docstring, REVIEW-A7: "only the identity keys and
    # the columns the envelope projects, never whatever else happened to be in the
    # operator's spreadsheet").
    #
    # Phase 72 Plan 03 (D-72-01/D-72-15): the rationale FLIPPED for `seniority` and
    # the six other keys widened here -- a create resumed from this queue (review-
    # triage 4a) is exactly the D-72-17 read-back route, so these now have a
    # consumer and are needed by a create. `hs_linkedin_url` is the one remaining
    # promotable-but-not-canonical key that still demonstrates a widened-but-
    # excluded name -- it is a lane-side-only write target no provider response
    # ever carries (D-72-04), so it is not part of this widening either.
    rows = _rows(1)
    merge_report = preingest.merge_enriched(
        rows, [_response(rows[0]["row_id"], {
            "email": "a@x.com", "seniority": "Director", "hs_linkedin_url": "https://li/x",
        })],
    )
    row = merge_report.rows[0]
    outcome = SimpleNamespace(match_tier=None, candidate_count=None)

    entry = held_queue.build_entry(row, confidence.HOLD_NO_MATCH, "test reason", outcome)

    assert entry["row"].get("email") == "a@x.com"
    assert entry["row"].get("seniority") == "Director", (
        "Phase 72 Plan 03 flipped seniority's exclusion -- a create resumed from "
        "this queue now needs it"
    )
    assert "hs_linkedin_url" not in entry["row"], (
        "hs_linkedin_url is a lane-side-only write target, never a real response "
        "key -- it stays outside held_queue.ROW_FIELD_ALLOWLIST"
    )


# =====================================================================================
# Phase 65 Plan 02 Task 3 (SAFE-01): a present value for a widened key is never
# overwritten -- the widening changes only WHICH keys may be written, never whether a
# present value is overwritten.
# =====================================================================================

def test_a_present_widened_key_is_never_overwritten_and_records_a_conflict():
    rows = _rows(1)
    rows[0]["seniority"] = "Director"
    responses = [_response(rows[0]["row_id"], {"seniority": "Manager"})]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["seniority"] == "Director"
    assert result.conflicts == (
        {"row_id": rows[0]["row_id"], "field": "seniority",
         "source_value": "Director", "provider_value": "Manager", "replaced": False},
    )


def test_a_byte_equal_widened_key_records_no_conflict_and_writes_nothing():
    rows = _rows(1)
    rows[0]["seniority"] = "Director"
    rows[0]["jobtitle"] = "Director"
    responses = [_response(rows[0]["row_id"], {
        "seniority": "Director", "jobtitle": "Director",
    })]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["seniority"] == "Director"
    assert result.rows[0]["jobtitle"] == "Director", (
        "a byte-equal response value records no conflict and writes nothing, even "
        "for a refreshable field like jobtitle"
    )
    assert result.conflicts == ()


# =====================================================================================
# Phase 38 Plan 01 Task 3: rerequest_unanswered — one re-request pass, through the
# dispatch path that already exists.
# =====================================================================================


def _rerequest_config(fake_config, ceiling=10):
    return {**fake_config, "max_records_per_chunk": ceiling}


def test_rerequest_unanswered_dispatches_one_pass_and_narrows_the_unanswered_set(
        fake_config, stub_module_transport_factory, recovers):
    rows = _rows(2)
    merge_report = preingest.merge_enriched(rows, [])  # neither row answered
    assert len(merge_report.unanswered) == 2

    transport = stub_module_transport_factory()
    recovers([_response(rows[0]["row_id"], {"email": "answered@x.com"})])

    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport,
    )

    assert len(transport.calls) == 1, "one re-request pass, and no more"
    assert len(result.unanswered) == 1
    assert result.unanswered[0]["row_id"] == rows[1]["row_id"]
    merged = {r["row_id"]: r for r in result.rows}
    assert merged[rows[0]["row_id"]]["email"] == "answered@x.com"


def test_rerequest_unanswered_with_nothing_unanswered_dispatches_nothing(
        fake_config, stub_module_transport_factory):
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [_response(rows[0]["row_id"], {})])
    assert merge_report.unanswered == ()

    transport = stub_module_transport_factory()
    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport,
    )

    assert transport.calls == []
    assert result is merge_report


def test_rerequest_unanswered_without_armed_is_a_type_error(
        fake_config, stub_module_transport_factory):
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [])
    with pytest.raises(TypeError):
        preingest.rerequest_unanswered(
            rows, merge_report, ["zoominfo"],
            config=_rerequest_config(fake_config),
            transport=stub_module_transport_factory(),
        )


def test_rerequest_unanswered_with_armed_false_raises_and_dispatches_nothing(
        fake_config, stub_module_transport_factory):
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [])
    transport = stub_module_transport_factory()

    with pytest.raises(NotArmedError):
        preingest.rerequest_unanswered(
            rows, merge_report, ["zoominfo"], False, _rerequest_config(fake_config),
            transport=transport,
        )
    assert transport.calls == [], "the re-request is not a way around the arming grant"


def test_rerequest_unanswered_request_bodies_carry_the_original_row_ids(
        fake_config, stub_module_transport_factory):
    rows = _rows(3)
    merge_report = preingest.merge_enriched(rows, [_response(rows[0]["row_id"], {})])
    unanswered_ids = {rows[1]["row_id"], rows[2]["row_id"]}
    assert {e["row_id"] for e in merge_report.unanswered} == unanswered_ids

    transport = stub_module_transport_factory()
    preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport,
    )

    sent_ids = {
        event["row_id"]
        for call in transport.calls
        for event in call["json"]["events"]
    }
    assert sent_ids == unanswered_ids, (
        "the re-request must reuse the ORIGINAL row_id values — a fresh mint would "
        "orphan every verdict the first pass recorded"
    )


def test_rerequest_unanswered_carries_the_dispatch_outcome_and_ceiling(
        fake_config, stub_module_transport_factory, recovers):
    """Phase 57 / D-57-01 / REVIEW-57-H3: the re-request pass is a real production
    `dispatch_plan` caller that runs a SECOND pass under the same grant, and its own
    spend was invisible to any tally before `execution_ceiling` and `dispatch_outcome`
    existed."""
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [])
    transport = stub_module_transport_factory()
    recovers([_response(rows[0]["row_id"], {"email": "answered@x.com"})])

    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport, execution_ceiling=5,
    )

    assert len(transport.calls) == 1
    assert result.dispatch_outcome is not None
    assert result.dispatch_outcome.ceiling_stop is None, "comfortably under the ceiling"


def test_rerequest_unanswered_with_no_execution_ceiling_is_unchanged(
        fake_config, stub_module_transport_factory, recovers):
    """`execution_ceiling=None` is today's behaviour — the same plan, the same single
    call, the same `MergeResult` fields every existing caller relies on."""
    rows = _rows(2)
    merge_report = preingest.merge_enriched(rows, [])
    transport = stub_module_transport_factory()
    recovers([_response(rows[0]["row_id"], {"email": "answered@x.com"})])

    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport,
    )

    assert len(transport.calls) == 1, "one re-request pass, and no more"
    assert len(result.unanswered) == 1
    assert result.unanswered[0]["row_id"] == rows[1]["row_id"]
    assert result.dispatch_outcome is not None
    assert result.dispatch_outcome.ceiling_stop is None


def test_rerequest_unanswered_threads_run_id_through_to_dispatch_plan(
        fake_config, stub_module_transport_factory, recovers):
    """F4 (uat-batch-review-row-reads-failed): without `run_id=`, `chunking.dispatch_plan`
    mints a FRESH `uuid.uuid4().hex` internally, orphaning this pass's
    `written_records`/bookkeeping under a run_id nobody else in the batch ever sees —
    directly contradicting SKILL.md step 9's own documented invariant, "the match pass,
    the enrich pass, the re-request pass when it ran, and the final ingest send — all
    under the SAME run_id." Passing `run_id=` here must make `dispatch_outcome.run_id`
    echo the SAME id the caller already minted for the rest of this batch."""
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [])
    transport = stub_module_transport_factory()
    recovers([_response(rows[0]["row_id"], {"email": "answered@x.com"})])

    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport, run_id="the-batch-run-id",
    )

    assert result.dispatch_outcome.run_id == "the-batch-run-id"


def test_rerequest_unanswered_with_no_run_id_is_unchanged(
        fake_config, stub_module_transport_factory, recovers):
    """`run_id=None` (the default) is today's behaviour — a fresh id, unchanged for
    every existing caller that does not pass one."""
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [])
    transport = stub_module_transport_factory()
    recovers([_response(rows[0]["row_id"], {"email": "answered@x.com"})])

    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport,
    )

    assert result.dispatch_outcome.run_id is not None


def test_rerequest_unanswered_with_nothing_unanswered_carries_no_dispatch_outcome(
        fake_config, stub_module_transport_factory):
    """No unanswered rows means no dispatch happened at all — `dispatch_outcome` must
    default None rather than pretend a call was made."""
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [_response(rows[0]["row_id"], {})])
    transport = stub_module_transport_factory()

    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport,
    )

    assert result is merge_report
    assert result.dispatch_outcome is None


def test_rerequest_unanswered_with_an_already_exhausted_ceiling_sends_nothing(
        fake_config, stub_module_transport_factory):
    """A ceiling that cannot even cover the first chunk sends zero POSTs and reports the
    stop on the returned outcome rather than silently sending anyway."""
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [])
    transport = stub_module_transport_factory()

    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport, execution_ceiling=0,
    )

    assert transport.calls == []
    assert result.dispatch_outcome is not None
    assert result.dispatch_outcome.ceiling_stop is not None
    assert len(result.unanswered) == 1
    assert result.unanswered[0]["row_id"] == rows[0]["row_id"]


def test_a_failed_rerequest_chunk_leaves_its_rows_unanswered_with_reason_intact(
        fake_config, stub_module_transport_factory):
    rows = _rows(1)
    merge_report = preingest.merge_enriched(rows, [])
    transport = stub_module_transport_factory(responses=[(500, {"message": "boom"})])

    result = preingest.rerequest_unanswered(
        rows, merge_report, ["zoominfo"], True, _rerequest_config(fake_config),
        transport=transport,
    )

    assert len(result.unanswered) == 1
    assert result.unanswered[0]["row_id"] == rows[0]["row_id"]
    assert result.unanswered[0]["reason"] == preingest.UNANSWERED_REASON, (
        "a re-request chunk failure must never become a fabricated verdict"
    )


# =====================================================================================
# Task 3: rows_from_table
# =====================================================================================

def test_exact_alias_headers_produce_one_canonical_row_per_data_row_in_file_order():
    result = preingest.rows_from_table(SAMPLES_DIR / "clean-uat-contacts.csv")

    assert len(result["rows"]) == 3
    assert result["rows"][0]["email"] == "alice@example.com"
    assert result["rows"][0]["firstname"] == "Alice"
    assert result["rows"][1]["firstname"] == "Bob"


def test_a_header_the_alias_table_does_not_recognise_is_dropped_and_reported():
    result = preingest.rows_from_table(SAMPLES_DIR / "clean-uat-contacts.csv")

    assert "Notes" in result["dropped_headers"]
    for row in result["rows"]:
        assert "notes" not in row and "Notes" not in row


def test_a_header_merely_similar_to_an_alias_does_not_map():
    # 22-messy-headers.csv's "Ph." is close to "phone" under difflib but is not an
    # exact alias — must be dropped, never fuzzy-mapped.
    result = preingest.rows_from_table(SAMPLES_DIR / "22-messy-headers.csv")

    assert "Ph." in result["dropped_headers"]
    for row in result["rows"]:
        assert "phone" not in row


def test_case_and_whitespace_variants_of_an_alias_still_map():
    # "Org." is an exact alias for "company" (case/whitespace-normalized).
    result = preingest.rows_from_table(SAMPLES_DIR / "22-messy-headers.csv")

    assert result["rows"][0]["company"] == "Southern Cross Racing Club"


def test_the_source_files_bytes_are_identical_before_and_after():
    path = SAMPLES_DIR / "clean-uat-contacts.csv"
    before = path.read_bytes()

    preingest.rows_from_table(path)

    assert path.read_bytes() == before


def test_a_headers_only_file_with_no_data_rows_returns_an_empty_row_list():
    result = preingest.rows_from_table(SAMPLES_DIR / "26-empty.csv")
    assert result["rows"] == []


def test_when_the_mapping_file_cannot_be_resolved_it_refuses():
    with pytest.raises(preingest.RowsFromTableError):
        preingest.rows_from_table(
            SAMPLES_DIR / "clean-uat-contacts.csv",
            mapping_path="/nonexistent/column_mapping.yaml",
        )
