# tests/test_provider_registry_parity.py
#
# Phase 16.1 Task 2 (reviews A3/SC-3) — mirrors tests/test_builder_flag_parity.py's
# two-lists-in-lockstep discipline: scripts/provider_registry.py's PROVIDER_REGISTRY and
# n8n/code/normalizeProviders.js's MAPPERS must carry the EXACT same provider-name set.
# A provider added to only one side (half-registered) fails this test.
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from provider_registry import PROVIDER_REGISTRY, PROVIDER_NAMES  # noqa: E402

MAPPERS_RE = re.compile(r"const MAPPERS\s*=\s*\{([^}]*)\}")
KEY_RE = re.compile(r"(\w+):")


def _mappers_keys() -> set:
    src = (ROOT / "n8n" / "code" / "normalizeProviders.js").read_text()
    m = MAPPERS_RE.search(src)
    assert m, "normalizeProviders.js: could not find `const MAPPERS = { ... }`"
    return set(KEY_RE.findall(m.group(1)))


def test_provider_registry_keys_equal_normalize_providers_mappers_keys():
    assert set(PROVIDER_REGISTRY.keys()) == _mappers_keys(), (
        "scripts/provider_registry.py PROVIDER_REGISTRY and n8n/code/normalizeProviders.js "
        "MAPPERS have drifted — a provider cannot be half-registered (reviews A3/SC-3)."
    )


def test_provider_names_derived_from_registry_matches_registry_keys():
    assert set(PROVIDER_NAMES) == set(PROVIDER_REGISTRY.keys())
    assert len(PROVIDER_NAMES) == len(PROVIDER_REGISTRY)  # no duplicates


def test_adding_a_provider_to_only_one_side_would_fail_this_test():
    """Sanity-check the parity guard actually discriminates (mirrors
    test_builder_flag_parity.py's own self-check style) — a mutated copy with an extra
    registry-only key must NOT equal the real MAPPERS key set."""
    mutated = set(PROVIDER_REGISTRY.keys()) | {"bogus_new_provider"}
    assert mutated != _mappers_keys()


def test_every_registry_entry_carries_a_normalize_key_matching_its_own_registry_key():
    """normalize_key is documented as MUST equal the registry key (16.1-RESEARCH.md
    Task 3) — assert the invariant holds, not just that the key SETS match."""
    for name, entry in PROVIDER_REGISTRY.items():
        assert entry["normalize_key"] == name, (
            f"PROVIDER_REGISTRY[{name!r}]['normalize_key'] = {entry['normalize_key']!r}, "
            f"expected {name!r}"
        )
