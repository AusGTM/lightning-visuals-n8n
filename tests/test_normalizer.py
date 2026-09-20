# tests/test_normalizer.py
#
# Phase 75 Plan 02 (D-75-06/D-75-08): this file did not exist before this plan (a plan-text
# discrepancy -- 75-02-PLAN.md's Task 2 read_first cites it as "the existing Python
# normaliser tests whose expectations move" but grep found no such file anywhere in the
# repo; tests/test_merge_policy.py already carries two normalize_country_region cases,
# left untouched below). Created new, home for the widened-whitelist region cases Task 2
# requires.
from src.normalizer import normalize_country_region


def test_normalize_country_region_whitelisted_country_name():
    assert normalize_country_region("United States") == "US"


def test_normalize_country_region_whitelisted_iso2():
    assert normalize_country_region("gb") == "GB"


def test_normalize_country_region_unmapped_known_country_is_other():
    assert normalize_country_region("Germany") == "Other"


def test_normalize_country_region_blank_is_unknown():
    assert normalize_country_region("") == "Unknown"
