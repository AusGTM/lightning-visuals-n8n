"""0.7.3 — `column_mapping.yaml` must SHIP inside the plugin, and must not drift.

Found by an operator walking UAT session 2 against the installed 0.7.2 build: the file
existed only at the repo root, so every real install resolved to nothing. `preview.py`
degraded (labels unavailable) but `extraction.py` REFUSED — `mapping_unavailable` — which
blocked prose, JSON, URL and screenshot ingestion entirely. The packaging gap had been
recorded as "minor, display-only" on the strength of preview's behaviour alone; nobody
checked the second consumer.
"""
from pathlib import Path

import pytest

import extraction
import preview

PLUGIN_COPY = Path(preview.PLUGIN_MAPPING_PATH)
REPO_COPY = Path(preview.DEFAULT_MAPPING_PATH)


def test_the_mapping_ships_inside_the_plugin_package():
    """An install has no repo beside it. If this file is absent, extraction is dead."""
    assert PLUGIN_COPY.exists(), (
        f"{PLUGIN_COPY} must ship with the plugin — without it extraction.py raises "
        "mapping_unavailable on every non-tabular input")
    assert PLUGIN_COPY.read_text().strip(), "shipped mapping must not be empty"


def test_the_shipped_copy_has_not_drifted_from_the_repo_copy():
    """Two copies of a backend contract is the second-source-of-truth pattern this
    milestone avoids everywhere else. Shipping one is justified only while a test proves
    they are identical — if this fails, re-copy, do not edit one side."""
    if not REPO_COPY.exists():
        pytest.skip("no repo checkout beside this install — nothing to compare against")
    assert PLUGIN_COPY.read_bytes() == REPO_COPY.read_bytes(), (
        "the plugin's shipped column_mapping.yaml has drifted from the repo's. "
        "The backend's Map Columns node reads the repo copy; a drifted plugin copy means "
        "the preview labels and the extraction allowlist describe a contract the backend "
        "does not implement.")


def test_resolution_prefers_the_shipped_copy_over_the_repo_copy():
    """The install case is the one that was broken; it must win."""
    assert preview.resolve_mapping_path() == PLUGIN_COPY


def test_extraction_can_build_its_allowlist_from_the_shipped_copy():
    """The behaviour the operator actually lost: extraction refusing outright. Drives the
    real derivation, not just the file's presence."""
    props = extraction.canonical_props()
    assert props, "canonical prop allowlist must be non-empty"
    for expected in ("email", "firstname", "lastname"):
        assert expected in props, f"{expected!r} missing from the canonical allowlist"
