# src/normalizer.py
#
# Candidate normalization. Transcribed from CLAUDE.md §12.4.
# Band boundaries match the Phase 2 ICP rubric bands.
import re
from typing import Any, List

import phonenumbers
from email_validator import validate_email, EmailNotValidError

from .schemas import ProviderResult, CandidateValue


def normalize_text(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.strip().split())
    return value


def normalize_bool(value: Any):
    if isinstance(value, bool):
        return value
    if value in ["true", "True", "yes", "Yes", "1", 1]:
        return True
    if value in ["false", "False", "no", "No", "0", 0]:
        return False
    return None


def normalize_revenue_band(value: Any):
    if value is None or value == "":
        return "unknown"
    if isinstance(value, str):
        return value
    try:
        v = float(value)
    except Exception:
        return "unknown"

    if v < 1_000_000:
        return "<1M"
    if v < 5_000_000:
        return "1-5M"
    if v < 50_000_000:
        return "5-50M"
    if v < 500_000_000:
        return "50-500M"
    if v < 750_000_000:
        return "500-750M"
    if v < 1_000_000_000:
        return "750M-1B"
    if v < 1_200_000_000:
        return "1B-1.2B"
    return "1.2B+"


def normalize_employee_band(value: Any):
    if value is None or value == "":
        return "unknown"
    if isinstance(value, str) and not value.isdigit():
        return value
    try:
        v = int(value)
    except Exception:
        return "unknown"

    if v <= 9:
        return "1-9"
    if v <= 50:
        return "10-50"
    if v <= 200:
        return "51-200"
    if v <= 500:
        return "201-500"
    if v <= 1000:
        return "501-1000"
    return "1001+"


def normalize_country_region(value: Any):
    if not value:
        return "Unknown"
    v = str(value).strip().lower()
    if v in ["australia", "au", "aus"]:
        return "AU"
    if v in ["new zealand", "nz"]:
        return "NZ"
    return "Other"


def normalize_phone(value: Any, region: str = "AU"):
    # region="AU" per the ANZ ICP; a leading '+' makes phonenumbers ignore region
    # (international passthrough). Malformed input -> None, never raises.
    if not value:
        return None
    try:
        parsed = phonenumbers.parse(str(value), region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def normalize_email(value: Any):
    # check_deliverability=False -> no DNS/network, stays offline. Invalid -> None.
    if not value:
        return None
    try:
        result = validate_email(str(value).strip(), check_deliverability=False)
    except EmailNotValidError:
        return None
    # .normalized lowercases the domain; explicit .lower() also lowercases the local part.
    return result.normalized.lower()


# Ordered keyword scan -> canonical seniority set. Order matters: vp before the
# c_suite 'president' check (so 'vice president' != 'president'), 'head' -> manager
# (not director) per spec. `phrases` match as substrings; `tokens` match only as
# whole words -- critical because short abbreviations like 'cto' are substrings of
# 'director', so 'Director of Ops' must not read as c_suite. No ML, no external calls.
_SENIORITY_KEYWORDS = [
    ("vp", ["vice president"], ["vp"]),
    ("c_suite", ["chief", "president", "founder", "owner", "c-suite"],
     ["ceo", "cfo", "coo", "cto", "cro", "cmo"]),
    ("director", ["director"], []),
    ("manager", ["manager", "head of", "supervisor"], ["head", "lead"]),
    ("individual", ["account executive", "executive", "analyst", "associate",
                    "specialist", "coordinator", "representative", "engineer",
                    "consultant"], []),
]


def normalize_seniority(value: Any):
    if not value:
        return "unknown"
    v = str(value).strip().lower()
    if not v:
        return "unknown"
    tokens = set(re.split(r"[^a-z]+", v))
    for canonical, phrases, abbrevs in _SENIORITY_KEYWORDS:
        if any(p in v for p in phrases) or (tokens & set(abbrevs)):
            return canonical
    return "unknown"


def normalize_field(field: str, value: Any) -> Any:
    if field in [
        "lv_produces_content",
        "lv_sponsorship_reliant",
        "lv_is_hardware_vendor",
        "lv_is_gambling_operator",
        "lv_has_broadcast_or_streaming_signals",
        "lv_has_sports_media_fit"
    ]:
        return normalize_bool(value)

    if field in ["annualrevenue", "lv_revenue_band"]:
        return normalize_revenue_band(value)

    if field in ["numberofemployees", "lv_employee_band"]:
        return normalize_employee_band(value)

    if field in ["country", "lv_country_region_normalized"]:
        return normalize_country_region(value)

    if field in ["phone", "mobilephone"]:
        return normalize_phone(value)

    if field == "email":
        return normalize_email(value)

    if field == "seniority":
        return normalize_seniority(value)

    # jobtitle intentionally has no branch: normalize_text (the fallback) already
    # trims and collapses whitespace, which is exactly the required jobtitle
    # normalization. Do not add a redundant normalize_jobtitle.
    return normalize_text(value)


def provider_to_candidates(result: ProviderResult) -> List[CandidateValue]:
    candidates = []
    if not result.matched:
        return candidates

    for field, value in result.data.items():
        if value is None or value == "":
            continue

        candidates.append(
            CandidateValue(
                canonical_field=field,
                provider=result.provider,
                value=value,
                normalized_value=normalize_field(field, value),
                confidence=result.confidence,
                evidence=result.evidence,
                model_trace=result.model_trace
            )
        )

    return candidates
