# tests/test_contact_normalizer.py
#
# Offline proof for the Phase 5 contact-field normalizers. No network, no API key,
# no DNS (normalize_email uses check_deliverability=False). Fixtures loaded
# cwd-relative; the suite runs from the repo root.
import json

from src.schemas import HubSpotRecord, ProviderResult
from src.normalizer import (
    normalize_phone,
    normalize_email,
    normalize_seniority,
    normalize_field,
)

CANONICAL_SENIORITY = {"c_suite", "vp", "director", "manager", "individual", "unknown"}


def test_normalize_phone():
    assert normalize_phone("0412 345 678") == "+61412345678"      # AU local default
    assert normalize_phone("+14155552671") == "+14155552671"      # international passthrough
    assert normalize_phone("abc") is None                          # malformed, no raise
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_normalize_email():
    assert normalize_email("  Bob@Example.COM ") == "bob@example.com"  # strip + validate + lower
    assert normalize_email("not-an-email") is None
    assert normalize_email("") is None
    assert normalize_email(None) is None


def test_normalize_seniority():
    assert normalize_seniority("VP Sales") == "vp"
    assert normalize_seniority("") == "unknown"
    assert normalize_seniority(None) == "unknown"
    assert normalize_seniority("Chief Revenue Officer") == "c_suite"
    assert normalize_seniority("Director of Ops") == "director"
    assert normalize_seniority("Sales Manager") == "manager"
    assert normalize_seniority("Account Executive") == "individual"
    for probe in ["CEO", "Head of Growth", "Analyst", "random text", ""]:
        assert normalize_seniority(probe) in CANONICAL_SENIORITY


def test_normalize_field_dispatch():
    assert normalize_field("phone", "0412 345 678") == "+61412345678"
    assert normalize_field("mobilephone", "0400 111 222") == "+61400111222"
    assert normalize_field("email", "X@Y.COM") == "x@y.com"
    assert normalize_field("seniority", "VP Sales") == "vp"


def test_company_path_no_regression():
    # Company branch must be byte-for-byte unchanged.
    assert normalize_field("lv_revenue_band", 12000000) == "5-50M"


def test_contact_fixtures_parse():
    record = HubSpotRecord(**json.load(open("tests/fixtures/contact_current.json")))
    assert record.object_type == "contacts"
    assert record.properties["email"] == "bob.smith@example.com"
    assert record.properties["phone"] == ""

    for provider in ["apollo", "lusha", "zoominfo"]:
        result = ProviderResult(
            **json.load(open(f"tests/fixtures/provider_{provider}_contact.json"))
        )
        assert result.object_type == "contacts"
        assert result.matched is True
