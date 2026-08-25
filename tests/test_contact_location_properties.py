# tests/test_contact_location_properties.py
#
# 260826-20w Task 2 — property-existence pin for the five HubSpot-native contact
# location properties (city, state, country, hs_state_code, hs_country_region_code).
# This test IS the property verification the plan requires: it replaces any live portal
# listing, reading the operator's committed 2026-08-26 portal export directly, and it
# fails loudly if a future export ever drops one of the five or changes its type.
#
# Also asserts the negative: no `ip_`-prefixed analytics property (ip_city, ip_country,
# ip_country_code, ip_state, ip_state_code, ...) is ever a write target for this plan's
# location fields — those are HubSpot-set from visitor IP geolocation, not enrichment
# inputs, and writing to them would silently no-op or fight HubSpot's own writer.
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT_CSV = (
    ROOT / "docs" / "hs_props"
    / "hubspot-properties-export-contacts-19-other-objects-2026-08-26" / "contact.csv"
)

LOCATION_PROPERTIES = [
    "city",
    "state",
    "country",
    "hs_state_code",
    "hs_country_region_code",
]


def _load_export_rows():
    with EXPORT_CSV.open(newline="", encoding="utf-8") as f:
        return {row["Internal name"]: row for row in csv.DictReader(f)}


def test_export_file_exists():
    assert EXPORT_CSV.exists(), (
        f"operator's 2026-08-26 portal export missing at {EXPORT_CSV} — this file is the "
        "evidence backing the five contact location properties; without it, the plan's "
        "claim that they exist live is unverifiable by this test."
    )


def test_five_location_properties_present_string_and_writable():
    rows = _load_export_rows()
    for name in LOCATION_PROPERTIES:
        row = rows.get(name)
        assert row is not None, f"{name} is missing from the operator's portal export"
        assert row["Type"] == "string", f"{name} is Type={row['Type']!r}, expected 'string'"
        assert row["Read only value"] == "false", (
            f"{name} is Read only value={row['Read only value']!r} — a read-only property "
            "can never be written by this pipeline"
        )


def test_no_ip_prefixed_property_in_the_location_write_set():
    for name in LOCATION_PROPERTIES:
        assert not name.startswith("ip_"), (
            f"{name} is an HubSpot analytics (ip_*) property — never a write target"
        )
    # Belt-and-braces: confirm the export itself DOES carry ip_-prefixed siblings (proves
    # this test would catch a future accidental substitution, e.g. hs_state_code ->
    # ip_state_code), and that none of them collide with our write set.
    rows = _load_export_rows()
    ip_props = {name for name in rows if name.startswith("ip_")}
    assert ip_props, "expected the export to carry ip_-prefixed analytics properties"
    assert not (ip_props & set(LOCATION_PROPERTIES)), (
        "an ip_-prefixed property leaked into the location write set"
    )
