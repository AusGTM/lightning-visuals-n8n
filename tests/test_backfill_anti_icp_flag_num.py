# tests/test_backfill_anti_icp_flag_num.py
#
# Phase 50 Plan 06 Task 3 -- offline pin for scripts/backfill_anti_icp_flag_num.py.
# Offline only: no network, no HubSpot credentials.
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from backfill_anti_icp_flag_num import (  # noqa: E402
    MAX_BACKFILL_RECORDS,
    assert_payload_scope,
    build_updates,
    enforce_backfill_cap,
    veto_search_filter,
    _writes_allowed,
)


# --- payload-scope assertion (T-50-28) ---------------------------------------------------

def test_assert_payload_scope_accepts_exactly_one_key():
    assert_payload_scope([{"id": "1", "properties": {"lv_anti_icp_flag_num": "1"}}])


def test_assert_payload_scope_rejects_a_second_key():
    with pytest.raises(ValueError):
        assert_payload_scope([
            {"id": "1", "properties": {"lv_anti_icp_flag_num": "1", "lv_anti_icp_flag": "true"}},
        ])


def test_assert_payload_scope_rejects_wrong_single_key():
    with pytest.raises(ValueError):
        assert_payload_scope([{"id": "1", "properties": {"lv_anti_icp_flag": "true"}}])


# --- cap refusal --------------------------------------------------------------------------

def test_enforce_backfill_cap_allows_at_cap():
    assert enforce_backfill_cap([str(i) for i in range(MAX_BACKFILL_RECORDS)]) is True


def test_enforce_backfill_cap_refuses_over_cap():
    assert enforce_backfill_cap([str(i) for i in range(MAX_BACKFILL_RECORDS + 1)]) is False


def test_max_backfill_records_is_ten():
    assert MAX_BACKFILL_RECORDS == 10


# --- gate: closed unless both env keys set ------------------------------------------------

@pytest.mark.parametrize(
    "dry_run, allow, expected",
    [
        (None, None, False),
        ("true", "true", False),
        ("false", "false", False),
        ("false", None, False),
        (None, "true", False),
        ("false", "true", True),
        ("False", "True", True),
    ],
)
def test_writes_allowed_only_when_both_keys_set(monkeypatch, dry_run, allow, expected):
    if dry_run is None:
        monkeypatch.delenv("DRY_RUN", raising=False)
    else:
        monkeypatch.setenv("DRY_RUN", dry_run)
    if allow is None:
        monkeypatch.delenv("ALLOW_ANTI_ICP_MIRROR_BACKFILL", raising=False)
    else:
        monkeypatch.setenv("ALLOW_ANTI_ICP_MIRROR_BACKFILL", allow)
    assert _writes_allowed() is expected


# --- build_updates: the value written for a true flag is "1" -----------------------------

def test_build_updates_writes_string_one():
    assert build_updates(["18047161864"]) == [
        {"id": "18047161864", "properties": {"lv_anti_icp_flag_num": "1"}}
    ]


def test_build_updates_empty_list_is_empty():
    assert build_updates([]) == []


# --- veto_search_filter: a non-true record can never be included in the target set -------

def test_veto_search_filter_only_matches_true_flag():
    assert veto_search_filter() == [
        {"propertyName": "lv_anti_icp_flag", "operator": "EQ", "value": "true"}
    ]
