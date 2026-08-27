# tests/test_company_native_properties.py
#
# 58-05 Task 2 — live, read-only property-existence check for the three native company
# properties this plan's enrichment lane now writes to: country, city, numberofemployees.
# Companies sibling of tests/test_contact_location_properties.py, which reads a committed
# CSV export; no such export exists for companies (docs/hs_props/ only has the contacts
# 2026-08-26 export), so this test hits the live portal directly instead, mirroring the
# GET /crm/v3/properties/{object_type}/{name} pattern already used by
# scripts/rollback_property_migration.py::_get_property_live. Read-only -- no write.
import os

import pytest
import requests
from dotenv import dotenv_values

# `dotenv_values()`, NOT `load_dotenv()`. This module is imported at COLLECTION time, so a
# module-level `load_dotenv()` pushed every `.env` key -- ANTHROPIC_API_KEY included -- into
# os.environ for the WHOLE pytest session. Tests that branch on `if not api_key` then took
# their LIVE branch: tests/test_merge_policy.py, whose own header says "Fully OFFLINE and
# DETERMINISTIC -- no Anthropic call, no network, no API key", was making real billable
# Anthropic calls on every full-suite run. `dotenv_values()` returns a dict and mutates
# nothing; real env still wins over the file for this module's own lookups.
_ENV = {**dotenv_values(), **os.environ}

BASE_URL = "https://api.hubapi.com"

# name -> the HubSpot property `type` the merge output implies (mergeCompanies.js's
# canonicalPatch carries country/city as strings, numberofemployees as a JS number that
# _numericHeadcount guarantees is already numeric -- see n8n/code/normalizeProviders.js).
EXPECTED_TYPES = {
    "country": "string",
    "city": "string",
    "numberofemployees": "number",
}


def _hs_headers():
    token = _ENV.get("HUBSPOT_PRIVATE_APP_TOKEN")
    if not token:
        pytest.skip("HUBSPOT_PRIVATE_APP_TOKEN not set -- cannot reach the live portal")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get_property_live(name: str):
    r = requests.get(
        f"{BASE_URL}/crm/v3/properties/companies/{name}",
        headers=_hs_headers(), timeout=30,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


@pytest.mark.parametrize("name,expected_type", sorted(EXPECTED_TYPES.items()))
def test_native_company_property_exists_writable_and_correct_type(name, expected_type):
    prop = _get_property_live(name)
    assert prop is not None, (
        f"companies.{name} does not exist live -- the enrichment lane cannot write to a "
        "property that isn't there"
    )
    assert prop["type"] == expected_type, (
        f"companies.{name} is type={prop['type']!r}, expected {expected_type!r} -- the "
        "merge output's value shape would not match the live property"
    )
    read_only = prop.get("modificationMetadata", {}).get("readOnlyValue", False)
    assert read_only is False, (
        f"companies.{name} has readOnlyValue=True -- the enrichment lane's PATCH would be "
        "silently ignored by HubSpot"
    )


def test_no_ip_prefixed_property_in_the_native_company_write_set():
    # Belt-and-braces mirror of the contacts sibling test: none of the three native
    # properties this lane writes are an ip_-prefixed HubSpot analytics property (visitor
    # IP geolocation, never an enrichment write target).
    for name in EXPECTED_TYPES:
        assert not name.startswith("ip_"), f"{name} is an ip_-prefixed analytics property"
