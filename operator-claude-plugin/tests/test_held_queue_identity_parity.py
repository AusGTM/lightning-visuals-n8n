"""Parity guard for `held_queue.identity_keys()` against
`config/column_mapping.yaml`'s `required_identity.any_of` (WR-02, 71-REVIEW.md) --
mirrors `tests/n8n/columnMapIdentityParity.test.mjs`'s intent on the Python side:
driven FROM the YAML (via `extraction.identity_groups()`, the same loader
`held_queue.identity_keys()` itself now calls), not from three hand-written cases, so a
future group added to the YAML is covered here without this file needing an edit.
"""
import extraction
import held_queue

# Realistic per-field values so a built row actually satisfies each field's own
# validator inside identity_keys() (e.g. email needs a real "x@y" shape). Only the
# fields the current YAML's groups use need an entry here -- a future group naming a
# field not in this table fails loudly with a KeyError, which is the intended signal
# that this table (not held_queue.py) needs updating.
_FIELD_VALUES = {
    "email": "person@example.com",
    "firstname": "Grant",
    "lastname": "Dewsbury",
    "company": "Acme Co",
    "linkedin_url": "https://linkedin.com/in/example",
}

_GROUP_PREFIX = {
    ("email",): "email",
    ("firstname", "lastname", "company"): "name",
    ("linkedin_url",): "linkedin",
}


def _row_for(group):
    return {field: _FIELD_VALUES[field] for field in group}


def test_a_row_satisfying_each_configured_identity_group_yields_a_key():
    groups = extraction.identity_groups()
    assert groups, "config/column_mapping.yaml must define at least one identity group"
    for group in groups:
        row = _row_for(group)
        keys = held_queue.identity_keys(row)
        assert keys, (
            f"row satisfying group {group!r} produced no identity_keys() -- "
            "YAML/held_queue.identity_keys drift"
        )


def test_a_row_satisfying_no_configured_group_yields_no_keys():
    assert held_queue.identity_keys({"jobtitle": "CEO", "phone": "555-0100"}) == ()
    assert held_queue.identity_keys({}) == ()


def test_identity_keys_order_and_prefixes_match_the_yamls_own_group_order():
    groups = extraction.identity_groups()
    row = {}
    for group in groups:
        row.update(_row_for(group))

    keys = held_queue.identity_keys(row)
    assert len(keys) == len(groups), "identity_keys() key count must track the YAML's group count"

    prefixes = [k.split(held_queue.KEY_SEPARATOR, 1)[0] for k in keys]
    expected_prefixes = [_GROUP_PREFIX[tuple(group)] for group in groups]
    assert prefixes == expected_prefixes, (
        "identity_keys()'s key order diverged from config/column_mapping.yaml's "
        "required_identity.any_of order"
    )
