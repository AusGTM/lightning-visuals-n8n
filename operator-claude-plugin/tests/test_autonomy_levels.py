"""D-67-01/D-67-02/D-67-03 — the three autonomy levels as a default-setter, not a gate.

`autonomy_enabled(config, level)` decides only whether an ALREADY-authorised action
proceeds without asking (D-67-02). It is never consulted by `write_grant` or
`n8n_arming` — see `test_headless_grant_boundary.py` for the symbol-absence pins on the
headless/cron path. This file exercises the reader in isolation, plus one real
settings-file round trip through `config_gate.load_config` so the tracer covers the
file-to-reader path an operator's install actually takes, not just a hand-built dict
(Task 2's own read_first instruction).

The near-miss and malformed-parent behaviour below is Task 1's recorded answer to
Question B, not a re-derivation: near-miss values read the level OFF (the round asks,
b-near-miss-asks); a non-dict `autonomy` parent reads every level OFF (b-malformed-off).
Both fail toward asking, never toward silent authorisation.
"""
import json

import pytest

import config_gate

_NEAR_MISS_LEVEL_VALUES = ("false", "true", 0, 1, "yes", None)


def test_absent_autonomy_object_reads_every_level_on():
    assert config_gate.autonomy_enabled({}, "write") is True
    assert config_gate.autonomy_enabled({}, "read_only") is True
    assert config_gate.autonomy_enabled({}, "spend_no_write") is True


def test_absent_level_inside_a_present_object_reads_on():
    assert config_gate.autonomy_enabled({"autonomy": {}}, "write") is True


def test_none_config_reads_every_level_on():
    """A capability lookup site that has not yet loaded a config at all must not raise —
    mirrors `write_grants_enabled`'s own `(config or {})` guard."""
    assert config_gate.autonomy_enabled(None, "write") is True


def test_explicit_false_reads_that_level_off_and_leaves_the_others_on():
    cfg = {"autonomy": {"write": False}}
    assert config_gate.autonomy_enabled(cfg, "write") is False
    assert config_gate.autonomy_enabled(cfg, "read_only") is True
    assert config_gate.autonomy_enabled(cfg, "spend_no_write") is True


@pytest.mark.parametrize("near_miss", _NEAR_MISS_LEVEL_VALUES)
def test_every_near_miss_level_value_reads_off_not_on(near_miss):
    """b-near-miss-asks (Task 1, recorded answer): only the JSON boolean `true` or an
    absent level authorises skipping the ask. A near miss must fail toward asking, not
    toward silent proceed."""
    cfg = {"autonomy": {"write": near_miss}}
    assert config_gate.autonomy_enabled(cfg, "write") is False


def test_true_is_the_only_value_that_reads_on():
    """The positive half of the parametrisation above — without it, an `autonomy_enabled`
    that returned False unconditionally would pass every near-miss row too."""
    assert config_gate.autonomy_enabled({"autonomy": {"write": True}}, "write") is True
    for near_miss in _NEAR_MISS_LEVEL_VALUES:
        assert config_gate.autonomy_enabled({"autonomy": {"write": near_miss}}, "write") is False


def test_bare_boolean_parent_reads_every_level_off_and_raises_nothing():
    """b-malformed-off (Task 1, recorded answer): `{"autonomy": true}` — a bare boolean
    where the object belongs — degrades to asking for every level rather than crashing a
    round mid-batch."""
    cfg = {"autonomy": True}
    assert config_gate.autonomy_enabled(cfg, "write") is False
    assert config_gate.autonomy_enabled(cfg, "read_only") is False
    assert config_gate.autonomy_enabled(cfg, "spend_no_write") is False


def test_explicit_null_parent_reads_every_level_off_not_on():
    """CR-01 (67-REVIEW): `{"autonomy": null}` is key-PRESENT-but-not-a-dict, the same
    malformed shape a bare boolean parent already degrades to OFF (b-malformed-off) — not
    key-ABSENT, which is the only case that reads ON (D-67-03). `dict.get` can't tell the
    two apart on its own; the reader must check membership before defaulting."""
    cfg = {"autonomy": None}
    assert config_gate.autonomy_enabled(cfg, "write") is False
    assert config_gate.autonomy_enabled(cfg, "read_only") is False
    assert config_gate.autonomy_enabled(cfg, "spend_no_write") is False


def test_unknown_level_raises_value_error_naming_it():
    with pytest.raises(ValueError) as exc:
        config_gate.autonomy_enabled({}, "admin")
    assert "admin" in str(exc.value)


def test_autonomy_enabled_is_pure_and_repeatable():
    """D-67-02: two calls with the same config return the same value, and neither call
    writes any file, opens any socket, or mutates the config."""
    cfg = {"autonomy": {"write": False}}
    before = json.loads(json.dumps(cfg))
    first = config_gate.autonomy_enabled(cfg, "write")
    second = config_gate.autonomy_enabled(cfg, "write")
    assert first == second
    assert cfg == before


def test_a_config_file_with_no_autonomy_key_reads_every_level_on_through_the_real_loader(
        tmp_path, fake_config):
    """Drives the absent-key case through a real `config_gate.load_config` round trip
    rather than a hand-built dict, so this tracer covers settings-file-to-reader end to
    end (Task 2's own read_first instruction) — an existing install with no `autonomy`
    key moves to the new defaults without anything being written into its file
    (D-67-03/D-67-10)."""
    cfg_path = tmp_path / "operator.local.json"
    assert "autonomy" not in fake_config
    cfg_path.write_text(json.dumps(fake_config))

    loaded = config_gate.load_config(cfg_path)

    assert "autonomy" not in loaded
    assert config_gate.autonomy_enabled(loaded, "write") is True
    assert config_gate.autonomy_enabled(loaded, "read_only") is True
    assert config_gate.autonomy_enabled(loaded, "spend_no_write") is True


def test_the_settings_key_is_not_a_capability_row():
    """Mirrors `test_write_grant.py::test_the_settings_key_is_not_a_capability_row` for
    `WRITE_GRANT_SETTINGS_KEY`: `CAPABILITY_KEYS` means "these keys are PRESENT", not "an
    admin set a default". Folding the autonomy key in would quietly change what a
    `require_capability` refusal means, so a later well-meaning edit that does it fails
    here loudly."""
    assert config_gate.AUTONOMY_SETTINGS_KEY not in config_gate.CAPABILITY_KEYS
    assert config_gate.AUTONOMY_SETTINGS_KEY not in config_gate._CAPABILITY_DESCRIPTIONS
    for required_keys in config_gate.CAPABILITY_KEYS.values():
        assert config_gate.AUTONOMY_SETTINGS_KEY not in required_keys
