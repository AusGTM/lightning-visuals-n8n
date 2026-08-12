#!/usr/bin/env python3
"""scripts/enrich_coverage_companies.py

Phase 48 (COVER-01/02) -- resolves lv_org_type for the up-to-5 companies left blank after
Phase 47/47.5: an offline enum-mapping pass over 47-RESEARCH-RESULTS.json for four
already-researched records (D-01), one fresh enum-constrained web-research call for
Racing NSW (a later plan's job -- this plan's decide_org_type raises PendingResearch for
it), and the D-03 "unknown" + lv_enrichment_review_reason marker for the one record whose
identity could not be resolved (Editix).

This script writes ONLY: lv_org_type, lv_org_type_verified_at, and (only for the D-03
un-enrichable marker) lv_enrichment_review_reason. It NEVER writes lv_icp_fit_score,
lv_icp_tier, lv_anti_icp_flag or lv_anti_icp_reason (project D-07) -- those are derived by
the n8n "Decide Company Action" Code node. This script changes inputs and (D-09, a later
plan) POSTs a synthetic property-change event with recompute=True so that Code node
actually runs, then reads the derived values back -- it never patches the derived fields
directly.

Two-key arm: DRY_RUN=false AND ALLOW_ENRICH_COVERAGE=true, set PER-SHELL only (never
`.env`, never a profile). Deliberately NOT ALLOW_VETO_REMEDIATION -- a distinct arm key
for a distinct script. The n8n-side allowlist (TEST_RECORD_IDS/ALLOW_HUBSPOT_RECORD_WRITES)
is the SECOND, independent arming surface `scripts/june_run_arm.py` guards --
`run_coverage_window` below refuses to write unless BOTH are open (`assert_allowlist_exact`).

AMENDMENT (48-CONTEXT.md D-48-01, operator-granted 2026-08-13, Phase 48 only): both arming
surfaces above -- normally operator-only per this docstring's original wording -- were
delegated to Claude for this phase only. D-48-01 does not revive any earlier, expired
waiver and expires with Phase 48; both surfaces revert to operator-only immediately after.

`.env` is Read/Bash permission-blocked this session -- the operator invocation for any
live read is:
    .venv/bin/python -c "from dotenv import load_dotenv; \
        load_dotenv('/abs/path/to/.env'); import runpy; \
        runpy.run_path('scripts/enrich_coverage_companies.py', run_name='__main__')"
A bare load_dotenv() resolves relative to the calling file, not the cwd -- pass an
absolute path or every HubSpot read 401s.

Run dry-run first (the default) and review the printed payloads before any write.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*`/`src.*` imports resolve

from scripts.remediate_veto_companies import (  # noqa: E402
    VALID_ORG_TYPES,
    FORBIDDEN_PROPS,
    N8N_EXECUTION_BUDGET_MONTH,
    ANTHROPIC_PER_RECORD_ESTIMATE_USD,
    refuse_if_over_budget,
    post_webhook_event,
    settle_and_assert,
    BudgetRefused,
    NotArmedError,
    PinRefused,
    SettleFailed,
)
from scripts import june_run_arm  # noqa: E402
from src.hubspot_client import search_records, get_record, batch_update_companies  # noqa: E402
from src.schemas import HubSpotRecord  # noqa: E402
from src.web_research import claude_web_research, RACING_NSW_ORG_TYPE_SYSTEM  # noqa: E402
from src.taxonomy import org_type_coherence_flags  # noqa: E402

# scripts.remediate_veto_companies (imported above) inserts operator-claude-plugin/scripts
# onto sys.path as a side effect of its own module-level import -- these flat plugin
# imports resolve because of that, the same idiom remediate_veto_companies.py itself uses.
import config_gate  # noqa: E402
import execution_errors  # noqa: E402
import executions_client  # noqa: E402
import n8n_arming  # noqa: E402
import n8n_read  # noqa: E402

RESEARCH_RESULTS_PATH = ROOT / ".planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json"

# Plan 48-07 Task 1: Racing NSW has no entry in the 17-keyed 47-RESEARCH-RESULTS.json (it
# was never one of the pinned 17) -- its captured evidence lives in its own file, and
# unlike 47-RESEARCH-RESULTS.json (a dict KEYED BY company id), 48-RESEARCH-RACING-NSW.json
# IS the research dict itself. One guard in the loader (_load_captured_research below), not
# a special case grown at every caller.
RESEARCH_PATH_OVERRIDES = {
    "15008671672": ROOT / ".planning/phases/48-enrichment-coverage/48-RESEARCH-RACING-NSW.json",
}

# CONTEXT.md's per-record mapping table, in the order the table prints (Racing NSW,
# Editix, Jam TV, Waikato, The Rumble). A literal, order-preserving tuple -- the same
# pattern PINNED_COMPANY_ID_ORDER uses, new membership.
COVERAGE_COMPANY_ID_ORDER = (
    "15008671672",   # Racing NSW
    "17317381378",   # Editix
    "17317850381",   # Jam TV
    "20538284384",   # Waikato Racing Club Inc
    "20943964946",   # The Rumble / Pacific Action Sports
)
COVERAGE_COMPANY_IDS = frozenset(COVERAGE_COMPANY_ID_ORDER)

# D-01/D-05: the literal per-record decision table authored from CONTEXT.md. No
# regex/keyword mapper exists anywhere in this module -- decide_org_type below reads this
# table, it never derives the enum value from research free text.
ORG_TYPE_DECISIONS = {
    # Plan 48-03 Task 3 made the ONE live enum-constrained call, captured verbatim in
    # 48-RESEARCH-RACING-NSW.json (matched=True confidence=95). It returned "regulator" --
    # citing Wikipedia and the Thoroughbred Racing Act 1996, the model read Racing NSW's
    # statutory origin and concluded regulator, not league/governing body.
    #
    # Plan 48-07 Task 1: OPERATOR REVIEW ON 2026-08-13 REJECTED THAT CLASSIFICATION and
    # overrides it to "governing_body_league" here. The discriminator is COMMERCIAL
    # CONTROL of the sport, not statutory origin -- statutory origin is useless as a test
    # because both a pure regulator and a governing body can be creatures of an Act. This
    # is an override of an operator-reviewed, evidenced value -- not a guess and not a
    # rewrite of the captured artifact (48-RESEARCH-RACING-NSW.json stays byte-identical;
    # see override_of/override_rationale below, which record the divergence as data).
    "15008671672": {
        "org_type": "governing_body_league",
        "override_of": "regulator",
        "override_rationale": (
            "Operator review on 2026-08-13 rejected the returned 'regulator' "
            "classification. The discriminator is COMMERCIAL CONTROL of the sport, not "
            "statutory origin -- statutory origin is useless as a test because both a "
            "pure regulator and a governing body can be creatures of an Act. The test: "
            "does a DIFFERENT body hold the commercial functions (race programme and "
            "calendar, prizemoney, media rights, sponsorship)? If yes, this org is a pure "
            "regulator. If this org holds them itself, it is a governing body, even where "
            "it also carries statutory regulatory powers. QRIC is the pure-regulator "
            "anchor -- integrity, licensing and stewards only, with Racing Queensland "
            "holding the commercial functions after Queensland split them out in 2016. "
            "Racing NSW is the governing-body anchor: it sets the race calendar, "
            "distributes prizemoney, collects Race Fields fees, runs its own streaming "
            "and is Tabcorp-sponsored. Every one of those commercial facts is already "
            "stated in the captured artifact's own evidence.evidence_summary -- cited, "
            "not re-fetched. Two independent repo artifacts already agree: "
            "config/taxonomy.yaml lists 'racing authority' and 'controlling body' among "
            "governing_body_league's synonyms, and docs/WEB-RESEARCH-SPEC.md §9 "
            "already names Racing NSW -> governing_body_league + Tier A/B as a "
            "golden-set acceptance case."
        ),
        "basis": (
            "48-RESEARCH-RACING-NSW.json matched=True confidence=95, "
            "evidence_by_field[\"lv_org_type\"]="
            "'https://en.wikipedia.org/wiki/Racing_NSW' -- statutory body corporate "
            "under the Thoroughbred Racing Act 1996, but the same artifact's "
            "evidence.evidence_summary shows it programmes racing, distributes "
            "prizemoney, collects Race Fields fees, runs its own streaming and is "
            "Tabcorp-sponsored -- commercial control, which is why the returned "
            "'regulator' is overridden to 'governing_body_league' (see override_of/"
            "override_rationale)"
        ),
    },
    "17317850381": {
        "org_type": "broadcaster",
        "basis": (
            "47-RESEARCH-RESULTS.json matched=true confidence=85, 'Media company / Web "
            "television broadcaster'"
        ),
    },
    "20538284384": {
        "org_type": "individual_club_team",
        "basis": (
            "47-RESEARCH-RESULTS.json matched=true confidence=85, 'Racing Club / Sports "
            "Organization'"
        ),
    },
    "20943964946": {
        "org_type": "content_producer",
        "basis": (
            "D-05: research says 'Event organizer / Sports league operator' conf 92, but "
            "the same evidence names Skate Australia as the sport's governing body and "
            "The Rumble as a partner -- it produces and broadcasts content, it does not "
            "govern"
        ),
    },
    "17317381378": {
        "org_type": "unknown",
        "basis": (
            "D-03: matched=false confidence=5, every data field null -- identity "
            "unresolvable, not merely unresearched"
        ),
    },
}

# D-03: the un-enrichable reason, authored data (never generated prose), keyed by company
# id -- the home for every record whose ORG_TYPE_DECISIONS entry is the "unknown" marker.
UNENRICHABLE_REASONS = {
    "17317381378": (
        "Web searches for 'Editix edetrix.com.au', 'Editix broadcast streaming live', and "
        "'edetrix.com.au OR Editix Australia media' returned no results for a company "
        "matching this identity (matched=false, confidence=5, every data field null). "
        "Near-hits were EditiX (an XML editor), Editrix (an AI book-editing tool) and "
        "EditShare (media software) -- none matching the company name+domain. Identity is "
        "unresolvable, not merely unresearched."
    ),
}

# --- Task 3: the one enum-constrained research call for Racing NSW -------------------------

RACING_NSW_ID = COVERAGE_COMPANY_ID_ORDER[0]

# Identity fields src/web_research.py's user_payload reads -- a subset of
# remediate_veto_companies.FETCH_PROPS, since this call never recomputes scoring itself
# (D-07) and needs no canonical ICP inputs merged back in.
RACING_NSW_FETCH_PROPS = ("name", "domain", "website", "country", "industry")


def _fetch_racing_nsw_record(fetcher=get_record) -> HubSpotRecord:
    record = fetcher("companies", RACING_NSW_ID, list(RACING_NSW_FETCH_PROPS))
    return HubSpotRecord(object_type="companies", id=RACING_NSW_ID, properties=record.get("properties", {}))


def research_racing_nsw(fetcher=get_record, research_fn=claude_web_research) -> dict:
    """Makes the ONE enum-constrained research call this plan authorizes -- Racing NSW
    only, USE_MOCK_WEB_RESEARCH=false required for a live call. Returns the verbatim
    ProviderResult dict; the caller writes it to 48-RESEARCH-RACING-NSW.json before any
    mapping happens (phase hard rule: exactly one paid call, no retry loop)."""
    record = _fetch_racing_nsw_record(fetcher)
    result = research_fn(record, system_prompt=RACING_NSW_ORG_TYPE_SYSTEM)
    return result.model_dump()


def resolve_racing_nsw_decision(research: dict) -> dict:
    """D-03 fallback logic over a captured research dict (real or synthetic). FOUR
    refusal conditions each land on the "unknown" marker with a non-empty reason rather
    than a forced value: an out-of-vocabulary lv_org_type, a bare "unknown" answer, a
    valid enum value with no evidence_by_field URL for the classification, or (Task 3) a
    coherence-guard trip -- `regulator` arriving alongside evidence of content output or
    sponsorship reliance is internally inconsistent, not merely low-confidence. This
    function NEVER rewrites org_type to a different value on its own: a corrected
    classification, if any, comes only from an operator-authored ORG_TYPE_DECISIONS
    override (Task 1) -- never from this guard guessing a replacement. Returns a dict
    shaped like an ORG_TYPE_DECISIONS entry, plus a "reason" key (for
    UNENRICHABLE_REASONS) present only when org_type == "unknown"."""
    data = (research or {}).get("data") or {}
    org_type = data.get("lv_org_type")
    evidence_url = (research.get("evidence_by_field") or {}).get("lv_org_type")

    if org_type not in VALID_ORG_TYPES:
        return {
            "org_type": "unknown",
            "basis": (
                f"48-RESEARCH-RACING-NSW.json: returned lv_org_type {org_type!r} is not "
                "a VALID_ORG_TYPES member -- D-03 marker applied, never force-fit."
            ),
            "reason": (
                f"Research call returned lv_org_type={org_type!r}, not one of the 9 live "
                "enum options -- refusing to force-fit an out-of-vocabulary value."
            ),
        }
    if org_type == "unknown":
        return {
            "org_type": "unknown",
            "basis": '48-RESEARCH-RACING-NSW.json: model answered "unknown" for lv_org_type.',
            "reason": (
                (research.get("evidence") or {}).get("evidence_summary")
                or 'Research call answered "unknown" for lv_org_type -- no reason summary captured.'
            ),
        }
    if not evidence_url:
        return {
            "org_type": "unknown",
            "basis": (
                f"48-RESEARCH-RACING-NSW.json: lv_org_type={org_type!r} carries no "
                'evidence_by_field["lv_org_type"] URL.'
            ),
            "reason": (
                f"Research call returned lv_org_type={org_type!r} but cited no evidence "
                "URL for the org-type classification -- D-03 marker applied per the "
                "require-evidence rule."
            ),
        }

    flags = org_type_coherence_flags(data)
    if flags:
        joined = "; ".join(flags)
        return {
            "org_type": "unknown",
            "basis": (
                f"48-RESEARCH-RACING-NSW.json: lv_org_type={org_type!r} is incoherent -- "
                + joined
            ),
            "reason": (
                f"Research call returned lv_org_type={org_type!r} alongside evidence this "
                f"guard treats as contradictory: {joined} -- refusing to promote a "
                "self-contradictory classification. The guard does not guess a "
                "replacement value; a corrected classification, if any, comes only from "
                "an operator-authored override (D-03, Task 1)."
            ),
        }

    return {
        "org_type": org_type,
        "basis": (
            f"48-RESEARCH-RACING-NSW.json matched={research.get('matched')} "
            f"confidence={research.get('confidence')}, lv_org_type={org_type!r}, "
            f'evidence_by_field["lv_org_type"]={evidence_url!r}'
        ),
    }


# The exact live HubSpot search filter CONTEXT.md re-derived the population with.
POPULATION_FILTERS = [
    {
        "propertyName": "lv_icp_fit_score",
        "operator": "HAS_PROPERTY",
    },
    {
        "propertyName": "lv_org_type",
        "operator": "NOT_HAS_PROPERTY",
    },
]
POPULATION_PROPERTIES = (
    "hs_object_id",
    "name",
    "lv_org_type",
    "lv_icp_fit_score",
    "lv_icp_tier",
    "lv_country_region_normalized",
    "lv_anti_icp_flag",
)


class PendingResearch(Exception):
    """Raised by decide_org_type for a coverage id with no ORG_TYPE_DECISIONS entry yet
    (Racing NSW, until a later plan supplies its researched value)."""


# --- pin resolution (new membership, same pattern as resolve_pinned_ids) ------------------

def resolve_coverage_ids(requested):
    """Raises the imported PinRefused, naming the offending id, if any requested id is
    absent from COVERAGE_COMPANY_IDS -- before any HubSpot or n8n call. Returns the
    accepted ids sorted into COVERAGE_COMPANY_ID_ORDER order."""
    for company_id in requested:
        if company_id not in COVERAGE_COMPANY_IDS:
            raise PinRefused(
                f"{company_id!r} is not one of the 5 coverage company ids. Refusing "
                "before any HubSpot or n8n call."
            )
    requested_set = set(requested)
    return tuple(cid for cid in COVERAGE_COMPANY_ID_ORDER if cid in requested_set)


# --- live population re-derivation ---------------------------------------------------------

def derive_population(searcher=search_records):
    """Re-derives the live population with the exact filter CONTEXT.md used. `searcher` is
    injectable so offline tests need no network call."""
    result = searcher("companies", POPULATION_FILTERS, list(POPULATION_PROPERTIES))
    rows = result.get("results", [])
    return {
        "derived_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "ids": [row.get("id") for row in rows],
        "rows": rows,
    }


def reconcile_population(derived, literal=COVERAGE_COMPANY_ID_ORDER):
    """Never mutates either set and never narrows the run -- returns the full expected
    list even when drift is found, so a moved population is an operator decision, not
    something this driver absorbs. CONTEXT.md's snapshot (5 ids, read 2026-08-12) is the
    expectation; a different live count is a finding to disclose, not a reason to edit the
    literal tuple silently."""
    derived_ids = list(derived.get("ids") or [])
    expected = list(literal)
    missing = [cid for cid in expected if cid not in derived_ids]
    unexpected = [cid for cid in derived_ids if cid not in expected]
    return {
        "expected": expected,
        "derived": derived_ids,
        "missing": missing,
        "unexpected": unexpected,
        "drift": bool(missing or unexpected),
    }


# --- the offline mapping pass (D-01/D-05) + the D-03 marker semantics ---------------------

def _load_captured_research(company_id, path=RESEARCH_RESULTS_PATH):
    override_path = RESEARCH_PATH_OVERRIDES.get(company_id)
    if override_path is not None:
        if not override_path.exists():
            return None
        return json.loads(override_path.read_text())
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get(company_id)


def decide_org_type(company_id, research):
    """Returns ORG_TYPE_DECISIONS[company_id] after confirming the evidence it cites is
    present on `research` (matched/confidence, and -- for a matched record -- a non-empty
    data.lv_org_type free-text field to ground the basis). It reads `research` ONLY to
    assert that evidence is present; it never derives the enum value from that free text
    -- no regex, no substring scan, no .lower() keyword match anywhere in this function
    (D-01). Raises PendingResearch for a coverage id with no table entry yet."""
    if company_id not in ORG_TYPE_DECISIONS:
        raise PendingResearch(
            f"{company_id!r} has no ORG_TYPE_DECISIONS entry -- research has not been "
            "captured/evidenced yet for this coverage id."
        )
    decision = ORG_TYPE_DECISIONS[company_id]
    if not isinstance(research, dict) or "matched" not in research or "confidence" not in research:
        raise ValueError(
            f"{company_id!r}: research is missing matched/confidence -- cannot ground "
            "the decision table's basis"
        )
    if research["matched"] and not (research.get("data") or {}).get("lv_org_type"):
        raise ValueError(
            f"{company_id!r}: research is matched but carries no lv_org_type free text "
            "to ground the decision table's basis"
        )
    return decision


def coverage_state(record_properties):
    """D-03's three-state semantics, machine-readable: blank lv_org_type is
    never_attempted; "unknown" is attempted_unresolved; any other valid enum value is
    resolved. This is what makes COVER-01's "distinguishable from never attempted" bar an
    assertion rather than a description."""
    org_type = (record_properties or {}).get("lv_org_type")
    if not org_type:
        return "never_attempted"
    if org_type == "unknown":
        return "attempted_unresolved"
    return "resolved"


def build_coverage_patch(company_id, decision, now_iso):
    """Returns exactly lv_org_type, lv_org_type_verified_at, and (only for the D-03
    marker) lv_enrichment_review_reason. Raises ValueError naming the id and value when
    decision['org_type'] is not a VALID_ORG_TYPES member -- the out-of-vocabulary write
    must never reach the wire."""
    org_type = decision["org_type"]
    if org_type not in VALID_ORG_TYPES:
        raise ValueError(
            f"{company_id!r}: {org_type!r} is not a member of VALID_ORG_TYPES -- "
            "refusing to build a patch that would 400 the whole batch"
        )
    props = {
        "lv_org_type": org_type,
        "lv_org_type_verified_at": now_iso,
    }
    if org_type == "unknown":
        reason = UNENRICHABLE_REASONS.get(company_id)
        if not reason:
            raise ValueError(
                f"{company_id!r}: org_type is 'unknown' but UNENRICHABLE_REASONS has no "
                "entry -- D-03 requires a non-empty reason"
            )
        props["lv_enrichment_review_reason"] = reason
    assert FORBIDDEN_PROPS.isdisjoint(props), (
        f"{company_id!r}: build_coverage_patch produced a forbidden derived-field key"
    )
    return {"id": company_id, "properties": props}


# --- cost estimate + budget refusal (COVER-02) ---------------------------------------------

def estimate_phase48_cost(research_ids, written_ids, proof_executions=0) -> dict:
    """Phase-48-shaped estimate: research is a direct Anthropic call costing zero n8n
    executions; the n8n executions are exactly the D-09 recompute POSTs, one per written
    record, plus any disarmed proof-of-deploy execution declared up front."""
    return {
        "web_research_calls": len(research_ids),
        "n8n_executions": len(written_ids) + proof_executions,
        "n8n_budget_month": N8N_EXECUTION_BUDGET_MONTH,
        "lusha_credits": 0,
        "lusha_credits_note": (
            "D-01: offline mapping + at most one direct research call, no provider "
            "waterfall -- zero Lusha credits drawn."
        ),
        "anthropic_estimate_usd": round(len(research_ids) * ANTHROPIC_PER_RECORD_ESTIMATE_USD, 4),
    }


# --- two-key arm gate (own name, deliberately not ALLOW_VETO_REMEDIATION) -----------------

def coverage_writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_ENRICH_COVERAGE", "false").lower() == "true"
    return (not dry_run) and allow


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


# --- Plan 48-05: the before/after snapshot, the allowlist assertion, and the one armed
# window (D-06) -----------------------------------------------------------------------

# The 8 properties CONTEXT.md's Task 1 requires captured for both 48-BEFORE.json (always
# disarmed) and 48-AFTER.json's per-record after-state (read back independently inside
# the armed window). Deliberately one quoted name per line -- the same style
# POPULATION_PROPERTIES already uses -- so the acceptance grep for the four forbidden
# derived-field names
# (grep -vE '^\s*(#|")' scripts/enrich_coverage_companies.py | grep -cE ...)
# excludes these read-only property-name literals the same way it already excludes
# POPULATION_PROPERTIES' own "lv_icp_fit_score/lv_icp_tier/lv_anti_icp_flag" lines. This
# module reads these fields to prove what the n8n node settled, never PATCHes them
# (FORBIDDEN_PROPS stays asserted disjoint from every payload build_coverage_patch
# produces).
BEFORE_PROPS = (
    "lv_org_type",
    "lv_enrichment_review_reason",
    "lv_icp_fit_score",
    "lv_icp_tier",
    "lv_anti_icp_flag",
    "lv_anti_icp_reason",
    "lv_country_region_normalized",
    "hs_lastmodifieddate",
)


class AllowlistNotExact(Exception):
    """Raised by assert_allowlist_exact when the deployed workflow's n8n-side
    write-safety state is not exactly what this window intends -- Trap 4 (an EMPTY
    allowlist arms successfully and denies every write while still reporting armed)
    plus two cheap adjacent checks: a populated allowlist with ALLOW_HUBSPOT_RECORD_WRITES
    still reading false (execution 11858's exact silent-denial shape), and a populated
    TEST_RECORD_DOMAINS this population never needs. Raised before this driver's first
    write, always from an INDEPENDENT fetch -- never from a prior arm call's own return
    value."""


class WindowError(Exception):
    """Raised by run_coverage_window before its first write, when
    coverage_writes_allowed() is False -- this driver's own two-key gate (DRY_RUN=false
    AND ALLOW_ENRICH_COVERAGE=true, per-shell) is not open. Nothing is sent."""


def _read_snapshot(company_id, reader=get_record):
    record = reader("companies", company_id, list(BEFORE_PROPS))
    return record.get("properties", {})


def snapshot_records(ids=None, reader=get_record):
    """Reads BEFORE_PROPS for every id, in COVERAGE_COMPANY_ID_ORDER order (never the
    caller's order) -- the shared read used for both 48-BEFORE.json (Task 1, always
    disarmed) and 48-AFTER.json's per-record after-state (Task 3, read back
    independently inside the armed window)."""
    resolved = resolve_coverage_ids(ids or COVERAGE_COMPANY_ID_ORDER)
    return {company_id: _read_snapshot(company_id, reader) for company_id in resolved}


def assert_allowlist_exact(expected_ids, config=None,
                            workflow_name=june_run_arm.DEFAULT_WORKFLOW_NAME,
                            workflow_id=None, resolver=None, fetcher=None):
    """Independently re-fetches the deployed workflow -- a FRESH GET, never a prior arm
    call's own return value -- and asserts the n8n-side write-safety state is exactly
    what this window intends, before this driver's first write:
      - ALLOW_HUBSPOT_RECORD_WRITES reads "true"
      - TEST_RECORD_IDS is non-empty AND its id set equals `expected_ids` exactly
      - TEST_RECORD_DOMAINS is empty (this population is id-armed only)
    Raises AllowlistNotExact naming the observed state on any mismatch. `workflow_id`
    and `fetcher` are both injectable (the latter workflow_id -> workflow dict) so
    offline tests need no network call at all."""
    expected = frozenset(str(v).strip() for v in expected_ids if str(v).strip())
    cfg = config if config is not None else config_gate.load_config()
    resolve = resolver or (lambda: executions_client.resolve_workflow_id(cfg, workflow_name=workflow_name))
    resolved_workflow_id = workflow_id if workflow_id is not None else resolve()
    if resolved_workflow_id is None:
        raise AllowlistNotExact(
            f"no workflow named {workflow_name!r} was found -- refusing to assert an "
            "allowlist that cannot be read."
        )
    fetch = fetcher or (lambda wid: n8n_read.get_workflow(cfg, wid))
    workflow = fetch(resolved_workflow_id)
    if not isinstance(workflow, dict):
        raise AllowlistNotExact(
            f"workflow {workflow_id!r} could not be read -- refusing to assert an "
            "allowlist against an unreadable workflow."
        )

    def _read(flag):
        observed = n8n_read.read_write_safety(workflow, flag)
        if observed.get("disagreement") is not None:
            raise AllowlistNotExact(
                f"{flag} declaring nodes disagree: {observed.get('nodes')} -- refusing "
                "to trust a desynced flag."
            )
        return observed.get("value")

    writes_flag = _read("ALLOW_HUBSPOT_RECORD_WRITES")
    if writes_flag != "true":
        raise AllowlistNotExact(
            f"ALLOW_HUBSPOT_RECORD_WRITES reads {writes_flag!r}, not 'true' -- a "
            "populated id allowlist with this flag false is a silent denial (the exact "
            "shape of execution 11858). Refusing before any write."
        )

    domains_raw = _read("TEST_RECORD_DOMAINS") or ""
    domains = frozenset(v.strip() for v in domains_raw.split(",") if v.strip())
    if domains:
        raise AllowlistNotExact(
            f"TEST_RECORD_DOMAINS is non-empty ({sorted(domains)}) -- this population is "
            "id-armed only; a populated domain allowlist widens the grant beyond what "
            "this window intends. Refusing before any write."
        )

    ids_raw = _read("TEST_RECORD_IDS") or ""
    observed_ids = frozenset(v.strip() for v in ids_raw.split(",") if v.strip())
    if not observed_ids:
        raise AllowlistNotExact(
            "TEST_RECORD_IDS is empty -- an empty allowlist denies every write while "
            "still reporting armed (Trap 4). Refusing before any write."
        )
    if observed_ids != expected:
        raise AllowlistNotExact(
            f"TEST_RECORD_IDS reads {sorted(observed_ids)}, not exactly the expected "
            f"{sorted(expected)} -- refusing before any write."
        )
    return observed_ids


def _duration_seconds(started, stopped):
    if not started or not stopped:
        return None
    try:
        s = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(stopped).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (e - s).total_seconds()


def _node_output_json(execution, node_name):
    """One named node's first output item's `json` payload from
    data.resultData.runData -- the same defensive `main[0]` walk report.py/
    execution_errors.py already use (report.py's own comment: this exact tiny walk is
    reimplemented at each call site in this repo rather than shared)."""
    run_data = ((execution.get("data") or {}).get("resultData") or {}).get("runData")
    if not isinstance(run_data, dict):
        return None
    runs = run_data.get(node_name)
    if not isinstance(runs, list) or not runs:
        return None
    first = runs[0]
    if not isinstance(first, dict):
        return None
    main = (first.get("data") or {}).get("main")
    if not isinstance(main, list) or not main:
        return None
    branch = main[0] if isinstance(main[0], list) else []
    for item in branch:
        if isinstance(item, dict) and isinstance(item.get("json"), dict):
            return item["json"]
    return None


def summarize_execution(execution):
    """The per-record execution evidence 48-AFTER.json records: node count (Trap 6),
    which nodes actually ran, whether `HubSpot Company Update` ran, `Decide Company
    Action`'s own output, and errors judged from node-level runData (Trap 1) via the
    shipped `execution_errors.harvest_errors` -- never from top-level `status` alone."""
    if not isinstance(execution, dict):
        return None
    workflow_data = execution.get("workflowData") or {}
    run_data = ((execution.get("data") or {}).get("resultData") or {}).get("runData")
    nodes_run = sorted(run_data.keys()) if isinstance(run_data, dict) else []
    return {
        "execution_id": execution.get("id"),
        "status": execution.get("status"),
        "node_count": len(workflow_data.get("nodes") or []),
        "nodes_run": nodes_run,
        "hubspot_company_update_ran": "HubSpot Company Update" in nodes_run,
        "decide_company_action_output": _node_output_json(execution, "Decide Company Action"),
        "duration_seconds": _duration_seconds(execution.get("startedAt"), execution.get("stoppedAt")),
        "errors": execution_errors.harvest_errors(execution),
    }


def _independent_disarm_reread(cfg, workflow_id):
    """A FRESH GET performed AFTER the disarm mutation, never a re-read of the disarm
    call's own echoed/verified response (Trap 3) -- this is the closure evidence the
    run report quotes verbatim."""
    workflow = n8n_read.get_workflow(cfg, workflow_id)
    if not isinstance(workflow, dict):
        return {"error": "workflow could not be independently re-read after disarm"}
    flags = {
        flag: n8n_read.read_write_safety(workflow, flag).get("value")
        for flag in n8n_arming.DISPATCH_FLAGS
    }
    return {"flags": flags, "active": workflow.get("active")}


def run_coverage_window(
    ids=None,
    armed=False,
    now_iso=None,
    config=None,
    writes_allowed_fn=coverage_writes_allowed,
    allowlist_asserter=assert_allowlist_exact,
    patcher=batch_update_companies,
    poster=post_webhook_event,
    lister=executions_client.list_executions,
    finder=executions_client.find_execution_for_dispatch,
    getter=executions_client.get_execution,
    disarmer=None,
    rereader=_independent_disarm_reread,
    reader=get_record,
    sleeper=time.sleep,
    settle_timeout=90,
    settle_interval=5,
    workflow_id=None,
    workflow_resolver=None,
):
    """The single entry point for the D-06 armed window: asserts both gates, then for
    every record PATCHes the org-type input, fires one D-09 recompute POST, waits for
    the derived chain to stabilise (reusing settle_and_assert -- never a new poller),
    and reads the record back independently. Disarms the n8n side in a `finally` so a
    mid-loop failure can never leave the window open (D-48-01: "disarm is ungated and
    runs even when the write leg fails or raises"). Never trims `ids` -- refuses whole
    (COVER-02) via WindowError/AllowlistNotExact before the first write.

    `armed=False` (the default) never touches the network beyond the two pre-write
    gates: every PATCH is built and recorded but sent with dry_run=True, and no webhook
    POST is made (mirrors post_webhook_event's own NotArmedError contract) -- this is
    what a rehearsal/offline call exercises. Only `armed=True` sends a real PATCH and a
    real webhook POST.
    """
    resolved_ids = resolve_coverage_ids(ids or COVERAGE_COMPANY_ID_ORDER)

    if not writes_allowed_fn():
        raise WindowError(
            "coverage_writes_allowed() is False -- DRY_RUN=false AND "
            "ALLOW_ENRICH_COVERAGE=true must both be set, per-shell, before the first "
            "write. Nothing was sent."
        )

    cfg = config if config is not None else config_gate.load_config()
    resolve_workflow_id = workflow_resolver or (
        lambda: executions_client.resolve_workflow_id(
            cfg, workflow_name=june_run_arm.DEFAULT_WORKFLOW_NAME,
        )
    )
    resolved_workflow_id = workflow_id if workflow_id is not None else resolve_workflow_id()

    allowlist_asserter(resolved_ids, config=cfg, workflow_id=resolved_workflow_id)

    now_iso = now_iso or datetime.now(timezone.utc).isoformat()
    workflow_id = resolved_workflow_id
    disarm_fn = disarmer or (lambda: june_run_arm.disarm())

    pre_window_executions = lister(cfg, workflow_id, limit=1) if (armed and workflow_id) else []

    results = []
    try:
        for company_id in resolved_ids:
            decision = decide_org_type(company_id, _load_captured_research(company_id))
            patch = build_coverage_patch(company_id, decision, now_iso)
            patcher([patch], dry_run=not armed)

            record = {
                "id": company_id,
                "decision": decision,
                "patch_properties": patch["properties"],
                "timed_out": False,
                "execution": None,
                "after_properties": None,
            }

            if armed:
                dispatched_at = datetime.now(timezone.utc)
                try:
                    poster(company_id, True, cfg, recompute=True)
                except requests.exceptions.Timeout:
                    # Trap 2: n8n completes server-side; a client timeout is never
                    # retried. Fall straight through to reading the execution back.
                    record["timed_out"] = True

                candidates = lister(cfg, workflow_id, limit=5)
                handle = finder(candidates, dispatched_at)
                execution = getter(cfg, handle["execution_id"]) if handle else None
                record["execution_handle"] = handle
                record["execution"] = summarize_execution(execution)

                try:
                    settle_and_assert(
                        company_id,
                        "lv_icp_tier",
                        lambda _v: True,
                        settle_timeout,
                        settle_interval,
                        reader=reader,
                        sleeper=sleeper,
                    )
                except SettleFailed:
                    pass  # recorded via the after-read below, not fatal to the window

                record["after_properties"] = _read_snapshot(company_id, reader=reader)

            results.append(record)
    finally:
        # D-48-01: "disarm is ungated and runs even when the write leg fails or
        # raises" -- called unconditionally, never inside the try, never skipped on
        # an exception. The independent re-read only bothers hitting the network when
        # this window actually armed the n8n side (armed=True and a workflow_id was
        # resolved); a dry-run/rehearsal call never armed anything to re-read.
        disarm_outcome = disarm_fn()
        disarm_reread = (
            rereader(cfg, workflow_id) if (armed and workflow_id) else None
        )

    post_window_executions = lister(cfg, workflow_id, limit=10) if (armed and workflow_id) else []

    return {
        "results": results,
        "disarm_outcome": disarm_outcome,
        "disarm_reread": disarm_reread,
        "pre_window_last_execution_id": (
            pre_window_executions[0].get("id") if pre_window_executions else None
        ),
        "post_window_execution_ids": [
            item.get("id") for item in post_window_executions if isinstance(item, dict)
        ],
    }


# --- main -----------------------------------------------------------------------------

def _parse_ids_csv(raw: str) -> list:
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", default="",
                         help="Comma-separated coverage company ids (default: all 5).")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                         help="Print payloads only, no write (default; this plan has no "
                              "armed write leg regardless of this flag).")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                         help="Reserved for a future plan's armed write leg -- this plan "
                              "performs no writes regardless of this flag.")
    parser.add_argument("--population-out", default=None,
                         help="Path to write the live-derived population JSON.")
    return parser


def main(argv=None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    requested = _parse_ids_csv(args.ids) or list(COVERAGE_COMPANY_ID_ORDER)
    try:
        resolved_ids = resolve_coverage_ids(requested)
    except PinRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    if _has_credentials():
        population = derive_population()
        if args.population_out:
            Path(args.population_out).write_text(json.dumps(population, indent=2, default=str))
        reconciliation = reconcile_population(population)
        print(f"POPULATION: {json.dumps(population, indent=2, default=str)}")
        print(f"RECONCILE: {json.dumps(reconciliation, indent=2)}")
        if reconciliation["drift"]:
            print("DRIFT DETECTED -- live population diverges from the 5-id literal set. "
                  "Disclosed, not silently absorbed. Operator decision required.")
    else:
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set for live "
              "population re-derivation. 48-POPULATION.json was not produced.")

    now_iso = datetime.now(timezone.utc).isoformat()
    research_ids = []
    written_ids = []
    for company_id in resolved_ids:
        try:
            decision = decide_org_type(company_id, _load_captured_research(company_id))
        except PendingResearch as exc:
            print(f"PENDING RESEARCH: {exc}")
            research_ids.append(company_id)
            continue
        patch = build_coverage_patch(company_id, decision, now_iso)
        written_ids.append(company_id)
        print(f"DECISION[{company_id}]: {json.dumps(decision)}")
        print(f"PATCH[{company_id}]: {json.dumps(patch['properties'], indent=2)}")

    estimate = estimate_phase48_cost(research_ids, written_ids)
    print(f"COST ESTIMATE: {json.dumps(estimate, indent=2)}")
    try:
        refuse_if_over_budget(estimate, written_ids)
    except BudgetRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    print("DRY RUN complete -- no write performed. This plan carries no armed write leg; "
          "a later plan owns coverage_writes_allowed()'s consuming branch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
