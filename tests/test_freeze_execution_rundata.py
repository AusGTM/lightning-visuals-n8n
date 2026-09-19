"""tests/test_freeze_execution_rundata.py

Phase 74 Plan 01, Task 1 (D-74-07). Offline behavioral coverage for
`scripts/freeze_execution_rundata.py`'s `_scrub` — the widened, non-enumerating
redaction that replaces the old `_redact_headers` (which only ever reached
`run["data"]["main"][branch][item]["json"]["headers"]` and silently missed a
node-run-level `run["error"]` sibling of `run["data"]`, plus `request`/`options`/
`config` at any depth — CR-04).

No fixture, no network, no live credentials: pure function tests over hand-built
dicts, plus one `_SENSITIVE_KEYS` composition check. Grepped both
`operator-claude-plugin/tests/` and `tests/` for an existing test file covering
this script before creating this one (D-74-07 task instruction) — none exists;
this file follows `tests/test_bounce_n8n_workflows.py`'s sibling
`sys.path.insert(scripts/)` + bare-module-name import pattern, the nearest
existing root-tests convention for a `scripts/*.py` CLI.
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import freeze_execution_rundata as freeze  # noqa: E402


def test_error_sibling_of_data_is_replaced():
    """A node run whose `error` key sits as a sibling of `data` (not inside
    `data.main`) comes back with that value replaced by the placeholder — the
    exact gap the old `_redact_headers` (which only ever walked `data.main`)
    left open."""
    run_data = {
        "Some Node": [
            {"data": {"main": [[]]}, "error": {"message": "Bearer super-secret-token"}}
        ]
    }
    out = freeze._scrub(run_data)
    assert out["Some Node"][0]["error"] == freeze.REDACTED_PLACEHOLDER


def test_nested_bearer_under_error_request_headers_replaced_at_first_match():
    """An item carrying a bearer value at json.error.request.headers.Authorization
    has the whole `error` value replaced at the first matching key, so nothing
    below it (request/headers/Authorization) survives in the output."""
    run_data = {
        "Some Node": [
            {
                "data": {
                    "main": [
                        [
                            {
                                "json": {
                                    "error": {
                                        "request": {
                                            "headers": {
                                                "Authorization": "Bearer super-secret-token"
                                            }
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                }
            }
        ]
    }
    out = freeze._scrub(run_data)
    item = out["Some Node"][0]["data"]["main"][0][0]
    assert item["json"]["error"] == freeze.REDACTED_PLACEHOLDER


def test_options_or_config_key_at_any_depth_is_replaced():
    run_data = {
        "Some Node": [
            {"data": {"main": [[{"json": {"a": {"b": {"options": {"apiKey": "sk-live-xyz"}}}}}]]}}
        ]
    }
    out = freeze._scrub(run_data)
    scrubbed = out["Some Node"][0]["data"]["main"][0][0]["json"]["a"]["b"]["options"]
    assert scrubbed == freeze.REDACTED_PLACEHOLDER

    run_data_cfg = {
        "Some Node": [{"config": {"retries": 3, "secret": "sk-live-xyz"}}]
    }
    out_cfg = freeze._scrub(run_data_cfg)
    assert out_cfg["Some Node"][0]["config"] == freeze.REDACTED_PLACEHOLDER


def test_dict_with_no_sensitive_key_round_trips_byte_identical():
    run_data = {"Some Node": [{"data": {"main": [[{"json": {"a": 1, "b": "x"}}]]}}]}
    out = freeze._scrub(copy.deepcopy(run_data))
    assert out == run_data


def test_non_dict_node_run_entry_is_returned_unchanged_and_does_not_raise():
    for entry in ([1, 2, 3], "a string", None, 42):
        run_data = {"Some Node": [entry]}
        out = freeze._scrub(run_data)
        assert out["Some Node"][0] == entry


def test_callers_input_dict_is_never_mutated():
    run_data = {"Some Node": [{"error": {"secret": "abc"}}]}
    original = copy.deepcopy(run_data)
    freeze._scrub(run_data)
    assert run_data == original


def test_zoom_token_and_access_token_values_are_replaced():
    """Deviation (Rule 1/2, found during Task 1 research): the plan's literal
    5-key list (headers/error/request/options/config, D-74-07) does not cover
    the actual live leak in the committed exec_12434.runData.json /
    exec_12449.runData.json fixtures — both carry a ZoomInfo OAuth JWT
    (`eyJ...`) under `zoom_token` (35/17 occurrences) and `access_token`
    (2/2), never under any of the 5 specified keys (confirmed by walking every
    `eyJ`-prefixed string in both fixtures back to its parent key before
    writing this fix). `_SENSITIVE_KEYS` is widened by exactly these two names
    so D-74-07's own acceptance criterion ("carries no JWT-shaped value") is
    satisfiable on the real data, not just the specified-but-untested key
    list."""
    run_data = {
        "IF Needs Judge": [
            {"data": {"main": [[{"json": {"zoom_token": "eyJhbGciOiJSUzI1NiJ9.payload.sig"}}]]}}
        ],
        "Build Judge Request": [
            {"data": {"main": [[{"json": {"access_token": "eyJhbGciOiJSUzI1NiJ9.payload.sig"}}]]}}
        ],
    }
    out = freeze._scrub(run_data)
    assert (
        out["IF Needs Judge"][0]["data"]["main"][0][0]["json"]["zoom_token"]
        == freeze.REDACTED_PLACEHOLDER
    )
    assert (
        out["Build Judge Request"][0]["data"]["main"][0][0]["json"]["access_token"]
        == freeze.REDACTED_PLACEHOLDER
    )


def test_sensitive_keys_composition():
    assert set(freeze._SENSITIVE_KEYS) >= {
        "headers",
        "error",
        "request",
        "options",
        "config",
        "zoom_token",
        "access_token",
    }
