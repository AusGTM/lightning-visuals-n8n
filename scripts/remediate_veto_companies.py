#!/usr/bin/env python3
"""scripts/remediate_veto_companies.py

Phase 47 (VETO-01/02, COVER-01/02) — the single script carrying all four write legs this
phase needs for the 17 pinned companies whose non-ANZ veto is false (blank region misread
as non-ANZ) and whose scoring inputs are blank: web-research enrichment (D-08), the
input + metadata PATCH (D-05/D-09), the component-score PATCH (reusing
scripts.backfill_seed_company_scores.compute_components, D-06), and the D-18 webhook POST
that makes the n8n "Decide Company Action" node actually recompute the veto.

This script writes ONLY: lv_org_type, lv_produces_content, lv_country_region_normalized
(the D-05 widened input set) when research actually establishes them with the evidence
config/field_policy.yaml requires; the seven source-metadata stamps for each of those it
writes; and the five component-score properties (org_type_score, geography_score,
annual_revenue_score, produces_content_score, gambling_score).

It NEVER writes lv_icp_fit_score, lv_icp_tier, lv_anti_icp_flag or lv_anti_icp_reason
(D-07) — those are derived by the HubSpot calculated property, WF1 (4625147345), and the
n8n "Decide Company Action" Code node respectively. This script changes inputs and (D-18)
POSTs a synthetic property-change event so that Code node actually runs, then polls for
the derived values to settle (Task 2's settle_tier/settle_veto) — it never patches the
derived fields directly. FORBIDDEN_PROPS is asserted disjoint from every payload dict this
script builds.

The 17 pinned ids and the 3 structurally-excluded ids (Entain, Gravity Media, Ironman —
verified-correct non-ANZ records) are literals below, enumerated from
46-SIMULATION-REPORT.md (D-12) — never discovered at runtime via search_records. There is
no search-based selection path in this script at all.

Two-key arm: DRY_RUN=false AND ALLOW_VETO_REMEDIATION=true (operator-only, per-shell,
never set by Claude — D-11/D-19). Portal id asserted before any HubSpot call.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    ALLOW_VETO_REMEDIATION=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/remediate_veto_companies.py', run_name='__main__')"

Run dry-run first (the default) and review the printed payloads before arming.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve
PLUGIN_SCRIPTS = ROOT / "operator-claude-plugin" / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))  # flat plugin imports, same idiom scripts/june_run_arm.py uses

import requests  # noqa: E402

from src.hubspot_client import batch_update_companies, get_record  # noqa: E402
from src.icp_scoring import compute_icp_score, load_yaml  # noqa: E402
from src.schemas import HubSpotRecord, ProviderResult  # noqa: E402
from src.web_research import claude_web_research  # noqa: E402
from scripts.backfill_seed_company_scores import compute_components  # noqa: E402

import config_gate  # noqa: E402

# WR-01-style discipline (matches backfill_seed_company_scores.py): hard-coded, no env
# override.
EXPECTED_PORTAL_ID = "22617666"

# The 17 pinned company ids, in the fixed table order 47-01-PLAN.md prints them —
# enumerated from 46-SIMULATION-REPORT.md's rows flagged blank_org_type, false_veto
# (D-12). Dry-run payload output and run-report rows are emitted in THIS order so two
# runs over the same input produce the same row order.
PINNED_COMPANY_ID_ORDER = (
    "9604732797",    # Tweed Valley Jockey Club
    "9604794661",    # Sapphire Coast Turf Club (Bega Valley)
    "9605273630",    # Port Macquarie Race Club
    "9604732795",    # Rockhampton Jockey Club
    "9604738976",    # Bunbury Turf Club
    "9604787229",    # The Alice Springs Turf Club
    "10152138518",   # Thoroughbred Park
    "10215097384",   # Wyong
    "14752488879",   # Coffs Harbour Racing Club
    "17317381378",   # Editix
    "17317850381",   # Jam TV
    "17696004613",   # Pinjarra Park
    "18047161864",   # Simtech LED
    "18796602894",   # The Kalgoorlie-Boulder Racing Club
    "19100977027",   # Newcastle Harness Racing Club
    "20538284384",   # Waikato Racing Club Inc
    "20943964946",   # The Rumble / Pacific Action Sports
)
PINNED_COMPANY_IDS = frozenset(PINNED_COMPANY_ID_ORDER)

# Structurally excluded, never writable by this script — verified correct non-ANZ records
# (2026-08-11). Not a filter: any id absent from PINNED_COMPANY_IDS is refused, and these
# three are simply never members of it. Named here only so resolve_pinned_ids can give a
# clearer refusal message.
EXCLUDED_COMPANY_IDS = frozenset({"10024564084", "15860277364", "17317184159"})
_EXCLUDED_NAMES = {
    "10024564084": "Entain",
    "15860277364": "Gravity Media",
    "17317184159": "Ironman",
}
assert PINNED_COMPANY_IDS.isdisjoint(EXCLUDED_COMPANY_IDS), (
    "a pinned id and an excluded id collided -- this must never happen"
)

# Derived fields owned by the calculated properties and the n8n Decide node (D-07).
# Every payload-building function below asserts its output is disjoint from this set
# before returning.
#
# 2026-08-19 (Phase 50 follow-up): WF1 (4625147345) no longer exists -- Phase 50 deleted
# it and archived lv_icp_tier. Both names STAY in this set: a never-write guard is
# additive, and writing an archived property is no more legitimate than writing it was
# before. lv_icp_tier_derived is added because it is a calculated property
# (readOnlyValue) -- HubSpot itself would reject a write, and this guard should fail
# loudly in our own code first rather than surfacing as an API error.
FORBIDDEN_PROPS = frozenset({
    "lv_icp_fit_score", "lv_icp_tier", "lv_icp_tier_derived",
    "lv_anti_icp_flag", "lv_anti_icp_reason",
})

# D-05: the widened scoring-input set this phase enriches (not lv_org_type alone).
INPUT_PROPS = ("lv_org_type", "lv_produces_content", "lv_country_region_normalized")

# D-09: the seven source-metadata stamps this phase RECORDS for every field it writes.
METADATA_SUFFIXES = (
    "_source", "_confidence", "_evidence_url", "_evidence_summary",
    "_verified_at", "_verified_by_model", "_validation_status",
)

# D-21 (Amendment 2026-08-12, operator-confirmed at the Plan 03 checkpoint): Task 2's
# live property-existence guard found 19 of the 21 D-09 stamp properties absent from the
# portal -- only these two exist and are ever PATCHed to HubSpot. The full seven-suffix
# D-09 trail (build_metadata_record) is still computed for every written field, but is
# recorded in 47-RESEARCH-RESULTS.json / 47-RUN-REPORT.md instead, never sent live. The
# standing "no new HubSpot properties of any kind" constraint is not lifted by this
# narrowing.
LIVE_METADATA_FIELDS = ("lv_org_type", "lv_produces_content")
LIVE_METADATA_STAMP_KEYS = tuple(f"{field}_verified_at" for field in LIVE_METADATA_FIELDS)

# config/field_policy.yaml's lv_org_type.require_evidence_url_for -- read-only input,
# never written to disk by this script.
EVIDENCE_REQUIRED_ORG_TYPES = (
    "governing_body_league", "content_producer", "hardware_vendor", "gambling_operator",
)

# CLAUDE.md §5.1's lv_org_type enumeration. Discovered live 2026-08-12: none of the 17
# pinned records' research results returned a member of this set -- src/web_research.py's
# RESEARCH_SYSTEM prompt does not constrain the model to it, so every live result was
# free text (e.g. "private_company", "Media company / Web television broadcaster").
# RE-CORRECTED 2026-08-12 (Phase 47.5 doc sweep). An earlier "correction" this same day
# claimed lv_org_type is NOT an enumeration and that free text is silently accepted. That
# was WRONG. It trusted docs/WEB-RESEARCH-SPEC.md's 2026-07-20 note, which predates the
# enum migration. VERIFIED LIVE 2026-08-12 via the properties API:
#     type: enumeration | fieldType: select
#     options: governing_body_league, content_producer, broadcaster, individual_club_team,
#              regulator, gambling_operator, hardware_vendor, other, unknown
# So the ORIGINAL comment was right: writing free text to this property 400s the batch.
# The gate below is load-bearing either way — do not remove it. Not fixed at the prompt
# (shared/production, parity-tracked against the n8n mirror) — gated here instead, at the
# trust boundary this script already owns.
VALID_ORG_TYPES = (
    "governing_body_league", "content_producer", "individual_club_team", "broadcaster",
    "gambling_operator", "hardware_vendor", "regulator", "other", "unknown",
)

# The only values compute_icp_score treats as a resolved (non-"unknown") region.
VALID_REGIONS = ("AU", "NZ", "ANZ", "Other")

# D-12: the ceiling equals the pinned-set size, so VETO_MAX_RECORDS can only ever LOWER
# the cap -- never BACKFILL_MAX_RECORDS's default of 10, which would refuse all 17
# (47-RESEARCH.md Pitfall 3).
DEFAULT_MAX_RECORDS = 17
HARD_CEILING_RECORDS = 17

N8N_EXECUTION_BUDGET_MONTH = 2500

# Properties fetched per record: identity fields the research prompt reads (per
# src/web_research.py's user_payload), plus every canonical input compute_components()
# can use (D-04's "enrich first, then one recompute" needs the record's PRE-existing
# canonical inputs merged with what this run researches).
FETCH_PROPS = (
    "name", "domain", "website", "country", "industry",
    "lv_org_type", "lv_produces_content", "lv_country_region_normalized",
    "lv_revenue_band", "lv_is_gambling_operator",
)

BATCH_CHUNK_SIZE = 100

WEBHOOK_PATH = "webhook/hubspot/enrichment/event"


class PinRefused(Exception):
    """Raised when a requested company id is not one of the 17 pinned ids."""


class SettleFailed(Exception):
    """Raised when a settle poll times out, or stabilises on a value other than expected."""


class BudgetRefused(Exception):
    """Raised when a projected run would exceed the n8n monthly execution budget."""


class NotArmedError(Exception):
    """Raised when post_webhook_event is called with armed falsy -- no network call made."""


# --- pin resolution (D-12) ---------------------------------------------------------------

def resolve_pinned_ids(requested):
    """Raises PinRefused naming the offending id if any requested id is absent from
    PINNED_COMPANY_IDS -- this is the membership refusal backfill_seed_company_scores.py
    does not have. Returns the accepted ids sorted into PINNED_COMPANY_ID_ORDER order, so
    output ordering is deterministic regardless of input order."""
    for company_id in requested:
        if company_id not in PINNED_COMPANY_IDS:
            if company_id in EXCLUDED_COMPANY_IDS:
                name = _EXCLUDED_NAMES.get(company_id, "")
                raise PinRefused(
                    f"{company_id!r} ({name}) is structurally excluded -- its non-ANZ "
                    "region is verified correct, not a false veto. Refusing before any "
                    "HubSpot or n8n call."
                )
            raise PinRefused(
                f"{company_id!r} is not one of the 17 pinned company ids. Refusing "
                "before any HubSpot or n8n call."
            )
    requested_set = set(requested)
    return tuple(cid for cid in PINNED_COMPANY_ID_ORDER if cid in requested_set)


# --- sample cap + gates (mirrors backfill_seed_company_scores.py's two-key triad) --------

def _resolved_max_records() -> int:
    raw = os.getenv("VETO_MAX_RECORDS", str(DEFAULT_MAX_RECORDS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_MAX_RECORDS
    return min(value, HARD_CEILING_RECORDS)


def enforce_sample_cap(sample_ids) -> bool:
    """True if the sample is at or under the resolved cap. The caller refuses (exits
    non-zero) rather than silently truncating."""
    return len(sample_ids) <= _resolved_max_records()


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_VETO_REMEDIATION", "false").lower() == "true"
    return (not dry_run) and allow


# --- research (D-08) ----------------------------------------------------------------------

def research_company(record: HubSpotRecord):
    """Delegates to src.web_research.claude_web_research -- returns the ProviderResult
    unchanged. Does not re-implement the research prompt."""
    return claude_web_research(record)


def _has_field_evidence(result, field: str) -> bool:
    """Strict per-field evidence check for GATING (D-14 / config/field_policy.yaml) --
    evidence_by_field only, no fallback. A field a research call did not explicitly cite
    is not evidenced, even if the response carries unrelated general evidence URLs.
    Matches src/taxonomy.py's own produces_content evidence gate."""
    return bool((result.evidence_by_field or {}).get(field))


def _evidence_url_for_metadata(result, field: str):
    """The evidence URL to STAMP for a field already cleared to write -- prefers the
    per-field citation, falling back to the response's first general evidence URL, so a
    field with no per-field citation (e.g. region, which is never evidence-gated) still
    gets a useful pointer."""
    url = (result.evidence_by_field or {}).get(field)
    if url:
        return url
    urls = result.evidence.evidence_urls if result.evidence else []
    return urls[0] if urls else None


def _classify_org_type(data: dict):
    """D-14/D-17: maps a research result to a VALID_ORG_TYPES member WITHOUT guessing.
    The exact enum string passes straight through. Otherwise, the free text is left
    unclassified UNLESS the schema-conformant lv_is_hardware_vendor boolean makes the
    call unambiguous -- keyword-matching the free text itself (e.g. reading "Event
    organizer / Sports league operator" as governing_body_league) is exactly the "they
    are all clubs" guessing D-17 forbids, so this deliberately does not do it.

    lv_is_gambling_operator is deliberately NOT used to derive org_type, despite being
    the same schema shape as lv_is_hardware_vendor. Discovered live 2026-08-12: it fired
    `true` for 8 of the 17 records, every one a not-for-profit racing/turf club whose OWN
    free-text org_type and evidence_summary say "racing club" / "non-profit" -- the model
    is conflating "hosts on-track TAB/bookmaker facilities" (standard for every
    Australian racecourse) with "is a gambling operator entity". Unlike hardware_vendor
    (validated correct against Simtech LED, a genuine LED manufacturer, in this same
    dataset), this boolean is proven UNRELIABLE for org_type derivation here -- trusting
    it would write "gambling_operator" onto 8 racing clubs, exactly the wrong-data
    failure class D-17 warns against, just from a boolean instead of a keyword.

    Returns (org_type_or_None, the_field_name_whose_evidence_backs_the_claim_or_None)."""
    raw = data.get("lv_org_type")
    if raw in VALID_ORG_TYPES:
        return raw, "lv_org_type"
    if data.get("lv_is_hardware_vendor") is True:
        return "hardware_vendor", "lv_is_hardware_vendor"
    return None, None


def _normalize_region(raw):
    """D-14: only unambiguous free-text forms are mapped -- 'Australia', 'Australia -
    NSW', 'New South Wales, Australia' -> AU (a state/territory name qualified by the
    country is still unambiguous); 'New Zealand' -> NZ. Deliberately NOT
    src/normalizer.py's normalize_country_region, whose else-branch maps every
    unrecognized string to 'Other', which would manufacture a genuine non-ANZ veto from
    an ambiguous or mismatched-entity read (e.g. a foreign same-name company). Anything
    else is left unresolved rather than guessed."""
    if raw in VALID_REGIONS:
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip().lower()
    if "new zealand" in text:
        return "NZ"
    if "australia" in text:
        return "AU"
    return None


def build_input_patch(company_id: str, result):
    """Carries only those of INPUT_PROPS the research actually established, per D-05/D-14:
    - lv_org_type: a VALID_ORG_TYPES member (via _classify_org_type, never guessed from
      free text); if it is one of EVIDENCE_REQUIRED_ORG_TYPES, only when the field that
      backs the classification is evidenced.
    - lv_produces_content: only a real boolean AND evidenced -- false on absent evidence is
      NEVER written (D-14: false is a hard veto, and writing it on a data gap manufactures
      exactly the false-veto class this phase clears). Written as the lowercase strings
      HubSpot booleancheckbox properties store, not JSON booleans.
    - lv_country_region_normalized: only an unambiguous AU/NZ/ANZ/Other (_normalize_region).
    """
    props = {}
    data = result.data or {}

    org_type, org_type_evidence_field = _classify_org_type(data)
    if org_type and org_type != "unknown":
        if org_type not in EVIDENCE_REQUIRED_ORG_TYPES or (
            org_type_evidence_field and _has_field_evidence(result, org_type_evidence_field)
        ):
            props["lv_org_type"] = org_type

    produces_content = data.get("lv_produces_content")
    if isinstance(produces_content, bool) and _has_field_evidence(result, "lv_produces_content"):
        props["lv_produces_content"] = "true" if produces_content else "false"

    region = _normalize_region(data.get("lv_country_region_normalized"))
    if region:
        props["lv_country_region_normalized"] = region

    assert FORBIDDEN_PROPS.isdisjoint(props), "build_input_patch produced a forbidden derived-field key"
    return {"id": company_id, "properties": props}


def unresolved_reasons(company_id: str, result) -> dict:
    """Field-keyed dict of short prose reasons for every INPUT_PROPS the patch omitted --
    so an unresolved record is distinguishable from one never attempted (COVER-01, D-14)."""
    written = build_input_patch(company_id, result)["properties"]
    data = result.data or {}
    reasons = {}

    if "lv_org_type" not in written:
        raw_org_type = data.get("lv_org_type")
        org_type, _evidence_field = _classify_org_type(data)
        if not raw_org_type or raw_org_type == "unknown":
            reasons["lv_org_type"] = "research did not establish an org type"
        elif not org_type:
            reasons["lv_org_type"] = (
                f"research returned {raw_org_type!r}, not a recognized lv_org_type enum "
                "value and no boolean signal confirmed a mapping -- left unresolved "
                "rather than guessed (D-17)"
            )
        else:
            reasons["lv_org_type"] = (
                f"org type {org_type!r} requires an evidence URL and none was cited"
            )

    if "lv_produces_content" not in written:
        produces_content = data.get("lv_produces_content")
        if not isinstance(produces_content, bool):
            reasons["lv_produces_content"] = "research did not establish content output"
        else:
            reasons["lv_produces_content"] = (
                "produces_content requires an evidence URL and none was cited"
            )

    if "lv_country_region_normalized" not in written:
        raw_region = data.get("lv_country_region_normalized")
        if not raw_region:
            reasons["lv_country_region_normalized"] = (
                "research did not establish a region in AU/NZ/ANZ/Other"
            )
        else:
            reasons["lv_country_region_normalized"] = (
                f"research returned {raw_region!r}, not confidently AU/NZ -- left "
                "unresolved rather than defaulted to Other (a genuine veto would follow "
                "from a wrong guess)"
            )

    return reasons


def build_metadata_patch(company_id: str, result, written_fields) -> dict:
    """D-21: the NARROWED HubSpot PATCH -- only LIVE_METADATA_STAMP_KEYS
    (lv_org_type_verified_at / lv_produces_content_verified_at), and only for fields
    this run actually wrote. The other five D-09 suffixes per field, and all seven for
    lv_country_region_normalized, do not exist live and are never PATCHed -- see
    build_metadata_record for the full trail this narrowing does not drop, only
    relocates."""
    verified_at = datetime.now(timezone.utc).isoformat()
    props = {
        f"{field}_verified_at": verified_at
        for field in written_fields
        if field in LIVE_METADATA_FIELDS
    }
    assert FORBIDDEN_PROPS.isdisjoint(props), "build_metadata_patch produced a forbidden derived-field key"
    return {"id": company_id, "properties": props}


def build_metadata_record(company_id: str, result, written_fields) -> dict:
    """D-21: the FULL seven-suffix D-09 evidence trail for every field this run
    actually wrote -- never PATCHed to HubSpot (build_metadata_patch is the narrowed
    subset that is). Recorded in 47-RESEARCH-RESULTS.json / 47-RUN-REPORT.md instead, so
    the config/field_policy.yaml evidence-URL obligation for hardware_vendor /
    content_producer / governing_body_league / gambling_operator is met in the repo
    artifact rather than on the live record."""
    props = {}
    verified_by_model = os.getenv("ANTHROPIC_RESEARCH_MODEL", "claude-sonnet-5")
    verified_at = datetime.now(timezone.utc).isoformat()

    for field in written_fields:
        props[f"{field}_source"] = result.provider
        props[f"{field}_confidence"] = result.confidence
        props[f"{field}_evidence_url"] = _evidence_url_for_metadata(result, field)
        props[f"{field}_evidence_summary"] = result.evidence.evidence_summary if result.evidence else None
        props[f"{field}_verified_at"] = verified_at
        props[f"{field}_verified_by_model"] = verified_by_model
        props[f"{field}_validation_status"] = "web_researched"

    assert FORBIDDEN_PROPS.isdisjoint(props), "build_metadata_record produced a forbidden derived-field key"
    return {"id": company_id, "properties": props}


# --- component scoring (reuse, never re-implement the point table) ------------------------

def build_component_patch(company_id: str, props: dict) -> dict:
    """Imports and calls scripts.backfill_seed_company_scores.compute_components -- never
    re-implements the point table. `props` must already carry the NEWLY-researched input
    values merged over the record's existing properties (D-04)."""
    components = compute_components(props)
    assert FORBIDDEN_PROPS.isdisjoint(components), "build_component_patch produced a forbidden derived-field key"
    return {"id": company_id, "properties": components}


def expected_score_and_tier(props: dict):
    """Calls src.icp_scoring.compute_icp_score on the same post-write inputs -- the
    oracle's own score/tier, for the settle assertion to compare against. Uses the
    oracle's own tier boundaries; 70/40/15 are never restated as local literals."""
    record = HubSpotRecord(object_type="companies", id="0", properties=props)
    result = compute_icp_score(record, {})
    return result.score, result.tier


def predicted_label(anti_icp_flag: bool, anti_icp_reason) -> str:
    """D-16/D-17 pre-arm classification: 'clears veto', 'still predicted non-ANZ
    (unresolved)', or a named different genuine veto (e.g. Simtech LED as
    hardware_vendor). The non-ANZ reason string is read from config/icp_scoring.yaml,
    never restated as a local literal (mirrors settle_veto's own predicate)."""
    if not anti_icp_flag:
        return "clears veto"
    cfg = load_yaml("config/icp_scoring.yaml")
    non_anz_reason = cfg["hard_vetoes"]["non_anz"]["reason"]
    reason = anti_icp_reason or ""
    if non_anz_reason in reason:
        return "still predicted non-ANZ (unresolved)"
    return f"different genuine veto ({reason})"


# --- settle-and-assert (D-10: "fail loudly", not a drop-in reuse of _settle()/settle(),
# neither of which asserts anything of their own -- 47-RESEARCH.md "Script surface
# corrections") -----------------------------------------------------------------------

def settle_and_assert(company_id: str, prop: str, expected, timeout, interval,
                       reader=get_record, sleeper=time.sleep):
    """Polls `prop` on `company_id` until two consecutive reads agree, or `timeout`
    elapses -- then asserts the settled value against `expected` (a literal, or a
    single-argument predicate), raising SettleFailed on a stable-but-wrong value as well
    as on timeout. `reader`/`sleeper` are injectable so offline tests need no network and
    no real sleeping."""
    start = time.monotonic()
    previous = None
    first_read = True
    current = None
    elapsed = 0.0

    while True:
        record = reader("companies", company_id, [prop])
        current = record.get("properties", {}).get(prop)
        elapsed = time.monotonic() - start

        if not first_read and current == previous:
            ok = expected(current) if callable(expected) else (current == expected)
            if ok:
                return current, elapsed
            raise SettleFailed(
                f"{company_id}: {prop} settled to {current!r}, but expected {expected!r}."
            )

        first_read = False
        previous = current

        if elapsed >= timeout:
            raise SettleFailed(
                f"{company_id}: {prop} did not settle within {timeout}s (last observed "
                f"{current!r}, expected {expected!r})."
            )
        sleeper(interval)


def settle_tier(company_id: str, expected_tier: str, timeout=120, interval=5,
                 reader=get_record, sleeper=time.sleep):
    """The pure-HubSpot chain: component PATCH -> lv_icp_fit_score (calculated property)
    -> WF1 -> lv_icp_tier. Measured latency is seconds."""
    return settle_and_assert(company_id, "lv_icp_tier_derived", expected_tier, timeout, interval,
                              reader=reader, sleeper=sleeper)


def settle_veto(company_id: str, timeout=900, interval=15, reader=get_record, sleeper=time.sleep):
    """The n8n-dependent chain: only moves once the D-18 webhook POST reaches the
    "Decide Company Action" node. Passes when lv_anti_icp_flag != "true", OR when it is
    "true" but lv_anti_icp_reason does not carry the non-ANZ hard-veto reason string
    (read from config/icp_scoring.yaml, never restated as a local literal) -- a
    legitimately revealed different veto (Simtech LED as hardware_vendor is the expected
    case) is a correct outcome (D-16), not a failure."""
    cfg = load_yaml("config/icp_scoring.yaml")
    non_anz_reason = cfg["hard_vetoes"]["non_anz"]["reason"]

    def _acceptable(flag_value):
        if flag_value != "true":
            return True
        record = reader("companies", company_id, ["lv_anti_icp_reason"])
        reason = record.get("properties", {}).get("lv_anti_icp_reason") or ""
        return non_anz_reason not in reason

    return settle_and_assert(company_id, "lv_anti_icp_flag", _acceptable, timeout, interval,
                              reader=reader, sleeper=sleeper)


# --- the D-18 webhook POST leg (no analog in the repo -- small and local) -----------------

def build_webhook_event(company_id: str, property_name: str = "lv_country_region_normalized",
                        recompute: bool = False, domain: str = None):
    """The raw HubSpot-shaped property-change event array D-18 specifies. Proven live in
    Phase 40-03 -- the workflow's `IF Company Bare Event` -> `HubSpot Company Fetch By Id`
    path accepts a bare object-id event with no domain match required.

    `recompute=True` adds a REAL JSON boolean (Phase 47.5 RECOMP-01). The deployed
    `Parse HubSpot Event` normalizes with `event.recompute === true`, so the string "true"
    would silently fail to arm the lane -- fail-closed by design, but only if this stays a
    bool. It rides the `...event` spread onto the row and is read at request level by
    `IF Company Recompute`. It is deliberately NOT a `mode` value: isReturnOnly() treats
    every non-"write" mode as return-only, so a mode-borne intent would report success and
    write nothing.

    `domain` routes the event through `HubSpot Company Search` (domain EQ) instead of the
    bare-event fetch-by-id lane, which is what populates identity_keys.domain so
    _writeSafetyAllows can match a TEST_RECORD_DOMAINS allowlist -- the only allowlist that
    can be armed for a company that does not exist yet.

    BOTH keys are added only when set. An always-present `recompute: false` / `domain: null`
    would change the event body shape for every existing caller.
    """
    event = {
        "objectId": str(company_id),
        "objectType": "company",
        "subscriptionType": "company.propertyChange",
        "propertyName": property_name,
        "occurredAt": int(time.time() * 1000),
    }
    if recompute:
        event["recompute"] = True
    if domain:
        event["domain"] = domain
    return [event]


def post_webhook_event(company_id: str, armed, config: dict, transport=requests,
                       recompute: bool = False, domain: str = None, timeout: float = 300):
    """`armed` has NO default, mirroring operator-claude-plugin/scripts/dispatch.py --
    raises NotArmedError when falsy before any network call. Target is config_gate-
    resolved n8n_url joined with webhook/hubspot/enrichment/event; header
    X-Enrichment-Secret from config["webhook_secret"]. Never prints the secret or the
    HubSpot token.

    `timeout` defaults to 300 seconds, not the 30 this function used to hardcode. Phase 47
    correction 4 (live-discovered): a lane that reaches Decide runs far longer than 30s, and
    the read timeout fired against a run n8n had ALREADY COMPLETED. That correction was
    patched into a throwaway driver's transport wrapper
    (.planning/phases/47-veto-remediation/47-armed-driver.py) rather than here, so the next
    caller inherited the same bug. It belongs in the script.
    """
    if not armed:
        raise NotArmedError(
            "Live writes are off for this run -- nothing was sent. Arming "
            "(ALLOW_VETO_REMEDIATION=true) is an operator-only, per-shell decision, "
            "never made by Claude."
        )
    url = f"{str((config or {}).get('n8n_url') or '').rstrip('/')}/{WEBHOOK_PATH}"
    headers = {"X-Enrichment-Secret": config["webhook_secret"]}
    response = transport.post(
        url, headers=headers,
        json=build_webhook_event(company_id, recompute=recompute, domain=domain),
        timeout=timeout,
    )
    response.raise_for_status()
    return response


# --- cost estimate + budget refusal (D-03/D-20) --------------------------------------------

# D-20/D-17: the ~4 pinned records (Simtech LED, Editix, Jam TV, The Rumble / Pacific
# Action Sports) whose names plainly are not racing clubs, and are therefore the ones
# most likely to land on an EVIDENCE_REQUIRED_ORG_TYPES org type, re-triggering the
# deployed workflow's "Research Trigger Gate" a second time. This is a documented
# ESTIMATE (D-20), not a live prediction -- the true count is only knowable after
# research actually runs, which is the whole reason D-08 chose research over guessing.
KNOWN_LIKELY_EVIDENCE_GATED_IDS = frozenset({
    "18047161864",  # Simtech LED
    "17317381378",  # Editix
    "17317850381",  # Jam TV
    "20943964946",  # The Rumble / Pacific Action Sports
})

# Phase 20 canary figure ($0.0686/record) -- measured on the n8n Haiku-plus-Sonnet path,
# NOT this script's single claude-sonnet-5 + native web_search call. Excludes the native
# web_search tool's per-search billing this path incurs. An explicit under-estimate, not
# a live-measured figure for this code path (47-RESEARCH.md "Cost estimate inputs").
ANTHROPIC_PER_RECORD_ESTIMATE_USD = 0.0686


def estimate_cost(ids) -> dict:
    """D-03/D-20 cost projection over `ids` (the ids about to run) -- a static
    projection, never a live balance check. There is no n8n usage endpoint (project
    memory n8n-execution-budget.md); month-to-date headroom is the operator's own
    confirmation at the arming checkpoint."""
    n_records = len(ids)
    redundant = len(set(ids) & KNOWN_LIKELY_EVIDENCE_GATED_IDS)
    return {
        "web_research_calls": n_records,
        "redundant_research_calls": redundant,
        "n8n_executions": n_records,
        "n8n_budget_month": N8N_EXECUTION_BUDGET_MONTH,
        "lusha_credits": 0,
        "lusha_credits_note": "D-08: web research only, no provider waterfall -- zero Lusha credits drawn.",
        "anthropic_estimate_usd": round(n_records * ANTHROPIC_PER_RECORD_ESTIMATE_USD, 4),
        "anthropic_estimate_note": (
            "Derived from the Phase 20 canary figure ($0.0686/record), measured on the "
            "n8n Haiku-plus-Sonnet path -- NOT this script's single claude-sonnet-5 + "
            "native web_search call, and excludes that call's per-search billing. An "
            "under-estimate, not a live-measured figure for this path."
        ),
    }


def refuse_if_over_budget(estimate: dict, ids):
    """D-03: refuse rather than truncate. Returns `ids` UNMODIFIED when the projected
    n8n_executions stays within n8n_budget_month; raises BudgetRefused otherwise."""
    if estimate["n8n_executions"] > estimate["n8n_budget_month"]:
        raise BudgetRefused(
            f"projected n8n executions ({estimate['n8n_executions']}) exceed the "
            f"monthly budget ({estimate['n8n_budget_month']}). Refusing rather than "
            "truncating the run -- no API call made."
        )
    return ids


# --- D-20 clobber verify ---------------------------------------------------------------

def verify_post_run(company_id: str, expected_inputs: dict, expected_metadata: dict, reader=get_record):
    """Re-reads the input properties AND the metadata stamps this script wrote, and
    returns the set of field names whose live value diverges from what was written.
    Project memory `companies-research-lane-rowloss` records a suspected latent row-loss
    when the n8n re-research lane runs (D-20) -- the ~4 KNOWN_LIKELY_EVIDENCE_GATED_IDS
    are exactly the ones that lane re-enters."""
    expected = {**expected_inputs, **expected_metadata}
    if not expected:
        return set()
    record = reader("companies", company_id, list(expected.keys()))
    live = record.get("properties", {})
    return {
        field for field, expected_value in expected.items()
        if str(live.get(field)) != str(expected_value)
    }


# --- Task 2 (T-47-13): live property-existence guard, before any write branch -----------

def _live_property_lister(object_type):
    """Production seam for the guard's HTTP call -- lazy-imports
    scripts.check_schema_drift._get_live_properties to avoid a module-level import cycle
    (scripts.veto_remediation_report imports PINNED_COMPANY_ID_ORDER/resolve_pinned_ids/
    expected_score_and_tier from THIS module, so this module must never import that one
    at module level). Tests monkeypatch this module-level name directly with a fake
    lister -- do not inline the import at the call site."""
    from scripts.check_schema_drift import _get_live_properties
    return _get_live_properties(object_type)


def _run_property_existence_guard(records) -> list:
    """The checked name set is deliberately WIDER than what this run writes: every
    payload key across all built payloads (input, metadata, component), UNION the 8
    read-only property names scripts.veto_remediation_report observes -- which includes
    the four derived fields this phase never writes and both VETO-03 search property
    names. A written name that's missing 400s the whole batch mid-window; a read name
    that's missing fails silently and returns None, the same defect class as the false
    veto this phase exists to clear. Returns the sorted list of missing names (empty if
    none)."""
    from scripts.veto_remediation_report import (
        OBSERVED_PROPS, live_property_names, missing_property_names,
    )

    payload_keys = set(OBSERVED_PROPS)
    for rec in records:
        payload_keys.update(rec["input_patch"]["properties"].keys())
        payload_keys.update(rec["metadata_patch"]["properties"].keys())
        payload_keys.update(rec["component_patch"]["properties"].keys())

    live_names = live_property_names("companies", lister=_live_property_lister)
    return missing_property_names(payload_keys, live_names)


# --- main -----------------------------------------------------------------------------

def _parse_ids_csv(raw: str) -> list:
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--company-id", action="append", default=[], dest="company_ids",
                         help="Explicit pinned company id to remediate (repeatable).")
    parser.add_argument("--ids", default="",
                         help="Comma-separated pinned company ids (alias for repeated --company-id).")
    parser.add_argument("--report", default=None,
                         help="Path to write the JSON run report.")
    parser.add_argument("--research-only", action="store_true",
                         help="Run the web-research pass only, cache raw ProviderResult "
                              "dicts (keyed by company id) to --out, and exit. No HubSpot "
                              "write of any kind.")
    parser.add_argument("--from-cache", default=None,
                         help="Path to a --research-only cache file. Every resolved id must "
                              "be present -- a missing id refuses the run rather than "
                              "falling through to live research.")
    parser.add_argument("--out", default=None,
                         help="Output path for --research-only's cached research results.")
    parser.add_argument("--report-md", default=None,
                         help="Path to write the D-21 full-evidence-trail markdown report "
                              "(the seven D-09 suffixes per written field, plus D-14 "
                              "reasons and the predicted post-write outcome) -- never "
                              "PATCHed to HubSpot, recorded here instead.")
    return parser


def requested_ids_from_args(args) -> list:
    """The raw requested id list before pin-resolution: explicit --company-id/--ids, or
    (if neither given) the full pinned set. There is no search-based selection path at
    all (D-12) -- the fallback the backfill script has (a search_records sweep) is
    exactly the runtime-discovery D-12 forbids, so it is deliberately absent here."""
    explicit = list(args.company_ids) + _parse_ids_csv(args.ids)
    return explicit or list(PINNED_COMPANY_ID_ORDER)


def _fetch_company(company_id: str) -> HubSpotRecord:
    record = get_record("companies", company_id, list(FETCH_PROPS))
    return HubSpotRecord(object_type="companies", id=company_id, properties=record.get("properties", {}))


def _process_one(company_id: str, research_fn=research_company) -> dict:
    """Runs one pinned company through research + the payload builders. Returns
    everything main()'s print/report/armed-write step needs. No batching, no writes --
    this is the pure "one path" this task proves. `research_fn` is injectable so
    --from-cache can substitute a cache lookup for a live research call without touching
    this function's body."""
    record = _fetch_company(company_id)
    result = research_fn(record)

    input_patch = build_input_patch(company_id, result)
    written_fields = list(input_patch["properties"].keys())
    metadata_patch = build_metadata_patch(company_id, result, written_fields)  # D-21: narrowed
    metadata_record = build_metadata_record(company_id, result, written_fields)  # D-21: full trail
    merged_props = {**record.properties, **input_patch["properties"]}
    component_patch = build_component_patch(company_id, merged_props)
    scored = compute_icp_score(HubSpotRecord(object_type="companies", id="0", properties=merged_props), {})
    webhook_event = build_webhook_event(company_id)

    return {
        "id": company_id,
        "name": record.properties.get("name"),
        "input_patch": input_patch,
        "metadata_patch": metadata_patch,
        "metadata_record": metadata_record,
        "component_patch": component_patch,
        "expected_score": scored.score,
        "expected_tier": scored.tier,
        "predicted_anti_icp_flag": scored.anti_icp_flag,
        "predicted_anti_icp_reason": scored.anti_icp_reason,
        "predicted_label": predicted_label(scored.anti_icp_flag, scored.anti_icp_reason),
        "webhook_event": webhook_event,
        "unresolved_reasons": unresolved_reasons(company_id, result),
    }


def _research_fn_from_cache(cache: dict):
    """A research_fn (same call shape as research_company) that looks up
    `cache[record.id]` instead of calling claude_web_research. Raises KeyError -- never
    falls through to a live call -- when an id is missing, so a partial cache refuses
    rather than silently re-researching (and re-spending) mid-run."""
    def _fn(record):
        cached = cache.get(record.id)
        if cached is None:
            raise KeyError(
                f"{record.id!r} missing from research cache -- refusing rather than "
                "falling through to live research."
            )
        return ProviderResult(**cached)
    return _fn


def _run_research_only(resolved_ids, out_path) -> int:
    """D-08's one-and-only live research pass. Writes raw ProviderResult dicts, keyed by
    company id, to `out_path` -- flushed after every record so a mid-run failure does not
    lose already-paid-for calls. No HubSpot write of any kind; the cost/budget gate
    (estimate_cost/refuse_if_over_budget) has already run in main() before this is
    called."""
    if not out_path:
        print("REFUSED: --research-only requires --out. No call made.")
        return 1
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("REFUSED: ANTHROPIC_API_KEY must be set for --research-only. No call made.")
        return 1

    out = Path(out_path)
    results = {}
    for company_id in resolved_ids:
        record = _fetch_company(company_id)
        result = research_company(record)
        results[company_id] = json.loads(result.model_dump_json())
        out.write_text(json.dumps(results, indent=2, default=str))  # incremental flush
        print(f"RESEARCHED: {company_id}")

    print(f"research-only complete -- {len(results)}/{len(resolved_ids)} records written to {out_path}")
    return 0 if len(results) == len(resolved_ids) else 1


def _render_run_report_md(records, estimate: dict) -> str:
    """D-21: the full D-09 seven-suffix evidence trail plus D-14 reasons and the
    predicted post-write outcome, per record -- committed to 47-RUN-REPORT.md since 19
    of the 21 D-09 stamp properties do not exist live and are never PATCHed."""
    lines = [
        "# Phase 47 Plan 03 -- Run Report (D-21 full evidence trail)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Cost estimate: {json.dumps(estimate)}",
        "",
        "Both HubSpot write surfaces are disarmed for every record below (DRY_RUN "
        "default, ALLOW_VETO_REMEDIATION unset). D-21: only "
        f"{', '.join(LIVE_METADATA_STAMP_KEYS)} are ever PATCHed to HubSpot -- every "
        "other D-09 field is recorded here, never on the live record.",
        "",
        "| id | name | lv_org_type | lv_produces_content | lv_country_region_normalized "
        "| predicted_score | predicted_tier | outcome |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for rec in records:
        props = rec["input_patch"]["properties"]
        reasons = rec["unresolved_reasons"]
        org_type = props.get("lv_org_type") or f"UNRESOLVED: {reasons.get('lv_org_type', '')}"
        produces = props.get("lv_produces_content")
        if produces is None:
            produces = f"UNRESOLVED: {reasons.get('lv_produces_content', '')}"
        region = props.get("lv_country_region_normalized") or f"UNRESOLVED: {reasons.get('lv_country_region_normalized', '')}"
        lines.append(
            f"| {rec['id']} | {rec['name']} | {org_type} | {produces} | {region} | "
            f"{rec['expected_score']} | {rec['expected_tier']} | {rec['predicted_label']} |"
        )

    lines += ["", "## Full D-09 evidence trail per record (never PATCHed to HubSpot)", ""]
    for rec in records:
        lines.append(f"### {rec['id']} -- {rec['name']}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(rec["metadata_record"]["properties"], indent=2, default=str))
        lines.append("```")
        if rec["unresolved_reasons"]:
            lines.append("")
            lines.append(f"D-14 unresolved reasons: {json.dumps(rec['unresolved_reasons'])}")
        lines.append("")

    return "\n".join(lines)


def main(argv=None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this script.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    requested = requested_ids_from_args(args)
    try:
        resolved_ids = resolve_pinned_ids(requested)
    except PinRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    if not enforce_sample_cap(resolved_ids):
        print(f"REFUSED: resolved sample has {len(resolved_ids)} records, exceeding the "
              f"cap ({_resolved_max_records()}, hard ceiling {HARD_CEILING_RECORDS}). "
              "No API call made.")
        return 1

    print(f"RESOLVED_IDS: {json.dumps(list(resolved_ids))}")

    estimate = estimate_cost(resolved_ids)
    print(f"COST ESTIMATE: {json.dumps(estimate, indent=2)}")
    try:
        resolved_ids = refuse_if_over_budget(estimate, resolved_ids)
    except BudgetRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    if args.research_only:
        return _run_research_only(resolved_ids, args.out)

    research_fn = research_company
    if args.from_cache:
        cache_path = Path(args.from_cache)
        if not cache_path.exists():
            print(f"REFUSED: cache file {args.from_cache} does not exist. No call made.")
            return 1
        cache = json.loads(cache_path.read_text())
        missing_cache_ids = [cid for cid in resolved_ids if cid not in cache]
        if missing_cache_ids:
            print(f"REFUSED: {len(missing_cache_ids)} resolved id(s) missing from research "
                  f"cache {args.from_cache}: {missing_cache_ids}. Refusing rather than "
                  "falling through to live research.")
            return 1
        research_fn = _research_fn_from_cache(cache)

    records = [_process_one(company_id, research_fn=research_fn) for company_id in resolved_ids]

    missing = _run_property_existence_guard(records)
    if missing:
        print(f"REFUSED: {len(missing)} checked property name(s) are absent from the "
              f"live portal -- refusing before any write branch: {missing}")
        return 1

    for rec in records:
        combined_props = {**rec["input_patch"]["properties"], **rec["metadata_patch"]["properties"]}
        # D-13: print the EXACT batch-update payload each record would send -- same
        # function, same dry_run=True short-circuit, as the armed branch below uses.
        if combined_props:
            batch_update_companies([{"id": rec["id"], "properties": combined_props}], dry_run=True)
        batch_update_companies([rec["component_patch"]], dry_run=True)
        # D-21: the full D-09 trail, printed for visibility even though it is never
        # PATCHed -- 47-RUN-REPORT.md is the committed record of it.
        print(json.dumps(
            {"id": rec["id"], "recorded_not_written_to_hubspot": rec["metadata_record"]["properties"]},
            indent=2, default=str,
        ))
        print(json.dumps(rec["webhook_event"], indent=2))
        if rec["unresolved_reasons"]:
            print(json.dumps({"id": rec["id"], "unresolved_reasons": rec["unresolved_reasons"]}, indent=2))

    if args.report:
        Path(args.report).write_text(json.dumps({
            "resolved_ids": list(resolved_ids),
            "writes_allowed": _writes_allowed(),
            "records": records,
        }, indent=2, default=str))

    if args.report_md:
        Path(args.report_md).write_text(_render_run_report_md(records, estimate))

    if not _writes_allowed():
        print("DRY RUN complete -- no write performed. Set DRY_RUN=false and "
              "ALLOW_VETO_REMEDIATION=true to arm.")
        return 0

    cfg = config_gate.load_config()
    for rec in records:
        # D-01: all four write legs for one record happen inside the one armed window --
        # batch-PATCH inputs+metadata -> batch-PATCH components -> settle_tier ->
        # webhook POST -> settle_veto -> verify_post_run -> conditional re-stamp.
        combined_props = {**rec["input_patch"]["properties"], **rec["metadata_patch"]["properties"]}
        if combined_props:
            batch_update_companies([{"id": rec["id"], "properties": combined_props}], dry_run=False)
        batch_update_companies([rec["component_patch"]], dry_run=False)
        settle_tier(rec["id"], rec["expected_tier"])

        post_webhook_event(rec["id"], True, cfg)
        settle_veto(rec["id"])

        # D-20: the deployed Research Trigger Gate re-enters ~4 evidence-gated records
        # and can overwrite this run's own stamps. Verify INSIDE the armed window --
        # discovering a clobber after disarm would need a second arming ceremony, the
        # exact twice-touched cost D-01 exists to avoid.
        diverged = verify_post_run(
            rec["id"], rec["input_patch"]["properties"], rec["metadata_patch"]["properties"],
        )
        if diverged:
            print(f"  {rec['id']}: re-research lane diverged fields {sorted(diverged)} -- re-stamping once")
            restamp = {k: v for k, v in combined_props.items() if k in diverged}
            batch_update_companies([{"id": rec["id"], "properties": restamp}], dry_run=False)
            diverged_again = verify_post_run(
                rec["id"], rec["input_patch"]["properties"], rec["metadata_patch"]["properties"],
            )
            if diverged_again:
                raise RuntimeError(
                    f"{rec['id']}: fields {sorted(diverged_again)} diverged again after "
                    "re-stamp -- refusing to continue silently."
                )

    print(f"armed run complete -- {len(records)} companies patched and settled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
