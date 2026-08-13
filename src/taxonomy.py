# src/taxonomy.py
#
# NM-1...NM-5 normalizers over config/taxonomy.yaml — THE single source of truth for
# lv_org_type / lv_content_type (see that file's header). Loaded once at import time,
# same relative-path convention as src/icp_scoring.py's load_yaml("config/....yaml").
#
# This module is the Python side of the taxonomy. scripts/gen_taxonomy_js.py imports
# normalize_key from here (not a re-implementation) so the JS synonym-map keys and this
# module's own lookup use the identical normalization by construction (spec NM-6).
import re

import yaml


def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


TAXONOMY = load_yaml("config/taxonomy.yaml")
VERSION = TAXONOMY.get("version", "unknown")
ORG_TYPES = TAXONOMY["org_types"]
CONTENT_TYPES = TAXONOMY["content_types"]


def _default_key(vocab: dict) -> str:
    # TX-7 guarantees exactly one is_default per vocabulary; conformance tests enforce it.
    for key, spec in vocab.items():
        if spec.get("is_default"):
            return key
    raise ValueError("taxonomy vocabulary has no is_default entry")


DEFAULT_ORG_TYPE = _default_key(ORG_TYPES)
DEFAULT_CONTENT_TYPE = _default_key(CONTENT_TYPES)

EVIDENCE_GATED_ORG_TYPES = sorted(
    k for k, v in ORG_TYPES.items() if v.get("requires_evidence")
)

# TX-10 (Phase 48 Plan 07): every org_types entry's `definition` key, in
# config/taxonomy.yaml key order. Both research prompts (src/web_research.py) render
# org_type_definitions_block() below rather than restating any definition inline -- a
# discriminator present in two hand-maintained copies is two things that drift. Root
# cause this closes: both prompts used to enumerate the 9 lv_org_type VALUES with no
# definitions, so a model classifying Racing NSW keyed on statutory origin instead of the
# correct discriminator (commercial control of the sport).
ORG_TYPE_DEFINITIONS = {k: v.get("definition", "") for k, v in ORG_TYPES.items()}


def org_type_definitions_block() -> str:
    """Deterministic single string listing every lv_org_type option with its semantic
    definition, in config/taxonomy.yaml key order. As of Phase 49 Plan 03,
    gen_taxonomy_js.render() ALSO reads the `definition` key and emits an
    ORG_TYPE_DEFINITIONS const into n8n/code/taxonomy.generated.js, so the n8n research
    prompt carries the same semantic content -- but rendered from that generated
    const directly (scripts/build_cloud_workflows.py's researchSystemPrompt()), not by
    calling this function, which remains the Python-prompt renderer only."""
    lines = ["lv_org_type option definitions:"]
    for key, definition in ORG_TYPE_DEFINITIONS.items():
        lines.append(f"- {key}: {definition}")
    return "\n".join(lines)


def normalize_key(raw) -> str:
    """NM-3 comparison form: lowercase, punctuation/whitespace collapsed to single
    spaces, trimmed. None/"" -> ""."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return s


def _build_synonym_map(vocab: dict) -> dict:
    # normalized synonym -> canonical key, plus the canonical keys themselves so an
    # already-canonical value in any casing/punctuation still matches (NM-2 order:
    # exact canonical key compared in normalized form, THEN synonym table).
    table = {}
    for canonical, spec in vocab.items():
        table[normalize_key(canonical)] = canonical
        for syn in spec.get("synonyms") or []:
            table[normalize_key(syn)] = canonical
    return table


_ORG_TYPE_LOOKUP = _build_synonym_map(ORG_TYPES)
_CONTENT_TYPE_LOOKUP = _build_synonym_map(CONTENT_TYPES)


def normalize_org_type(raw) -> str:
    """NM-1/NM-2/NM-3: canonical org_type key, or DEFAULT_ORG_TYPE. Never anything
    outside ORG_TYPES."""
    key = normalize_key(raw)
    return _ORG_TYPE_LOOKUP.get(key, DEFAULT_ORG_TYPE)


def normalize_org_type_result(raw) -> dict:
    """NM-4: needs_review is True whenever the result is the default AND the raw
    input was not already (a normalized form of) the default — blank/None input
    also counts as unmapped and reviews."""
    value = normalize_org_type(raw)
    was_already_default = normalize_key(raw) == normalize_key(DEFAULT_ORG_TYPE)
    needs_review = value == DEFAULT_ORG_TYPE and not was_already_default
    return {"value": value, "needs_review": needs_review}


def normalize_content_types(raw) -> list:
    """NM-5: drop unrecognised entries, de-duplicate, preserve first-seen order.
    Non-list input -> []."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        key = normalize_key(item)
        canonical = _CONTENT_TYPE_LOOKUP.get(key)
        if canonical is None:
            continue
        if canonical not in out:
            out.append(canonical)
    return out


# Phase 13 (OC-1..4, TS-1..3, AT-2, ER-1): validate_research_output / to_provider_result —
# the output contract for Claude web-research results. Built on the normalizers above so
# the vocabulary gate is reused by construction, not re-implemented.
ALLOWED_REPRESENTS = {"group", "subsidiary", "franchise_outlet", "single_entity", "unknown"}

# CLAUDE.md Section 14.2 web-research return contract for lv_country_region_normalized.
# Mirrored by n8n/code/webResearch.js's ALLOWED_COUNTRY_REGIONS guard (kept parity-honest
# by tests/n8n/parity.test.mjs's GENUINE Python parity assertion).
ALLOWED_COUNTRY_REGIONS = {"AU", "NZ", "ANZ", "Other", "Unknown"}

# Phase 48 Plan 07 Task 3 (D-03 guard extension): a `regulator` classification means
# integrity/licensing only, with commercial functions held elsewhere -- a body with no
# commercial control has no broadcast product to sell and no sponsorship inventory to
# evidence. `regulator` arriving alongside evidence of content output or sponsorship
# reliance is not low-confidence, it is internally inconsistent. Named here rather than
# open-coded in org_type_coherence_flags so the two signals it checks are visible as data.
INCOHERENT_WITH_REGULATOR = ("lv_produces_content", "lv_sponsorship_reliant")


def org_type_coherence_flags(data: dict) -> list:
    """Pure function: a list of human-readable reason strings, empty when coherent.
    Fires ONLY for the one contradiction this guard understands -- org_type normalizes to
    `regulator` while lv_produces_content and/or lv_sponsorship_reliant is True. Any other
    org_type, or a regulator with no such evidence (a QRIC-shaped honest regulator),
    returns an empty list. Reads only; NEVER mutates; NEVER rewrites org_type to another
    value -- an automatic flip would be the same class of guess that produced the error
    this guard exists to catch (prefer-unknown-over-guessing, AT-2 precedent)."""
    data = data or {}
    org_type = normalize_org_type(data.get("lv_org_type"))
    if org_type != "regulator":
        return []
    flags = []
    for field in INCOHERENT_WITH_REGULATOR:
        if data.get(field) is True:
            flags.append(
                f"org_type='regulator' is incoherent with {field}=True -- a pure "
                "regulator holds no commercial functions and should have no content "
                "output or sponsorship inventory to evidence"
            )
    return flags


def validate_research_output(raw) -> dict:
    """OC-2/OC-3/OC-4, TS-1/TS-2/TS-3, AT-2, ER-1. Never raises."""
    if not isinstance(raw, dict):
        return {
            "matched": False,
            "data": {},
            "evidence_by_field": {},
            "entity_resolution": {
                "represents": "unknown",
                "likely_revenue_band": None,
                "notes": "",
            },
            "needs_review": True,
            "coherence_flags": [],
        }

    data = dict(raw.get("data") or {})
    evidence_by_field = dict(raw.get("evidence_by_field") or {})

    org_result = normalize_org_type_result(data.get("lv_org_type"))
    data["lv_org_type"] = org_result["value"]
    data["lv_content_type"] = normalize_content_types(data.get("lv_content_type"))

    produces_content = data.get("lv_produces_content")
    if produces_content is False and not evidence_by_field.get("lv_produces_content"):
        produces_content = None  # TS-2: unevidenced False is not evidence of absence
    data["lv_produces_content"] = produces_content

    region = data.get("lv_country_region_normalized")
    if region is not None and region not in ALLOWED_COUNTRY_REGIONS:
        data["lv_country_region_normalized"] = "Unknown"

    er = dict(raw.get("entity_resolution") or {})
    represents = er.get("represents")
    if represents not in ALLOWED_REPRESENTS:
        represents = "unknown"

    # Additive-only: ORs into the existing needs_review, never replaces it, and never
    # rewrites data["lv_org_type"] (flagged, not fixed).
    coherence_flags = org_type_coherence_flags(data)

    return {
        "matched": bool(raw.get("matched", True)),
        "data": data,
        "evidence_by_field": evidence_by_field,
        "entity_resolution": {
            "represents": represents,
            "likely_revenue_band": er.get("likely_revenue_band"),
            "notes": er.get("notes", ""),
        },
        "needs_review": org_result["needs_review"] or bool(coherence_flags),
        "coherence_flags": coherence_flags,
    }


def to_provider_result(raw):
    """OC-1: builds the evidence_by_field-carrying ProviderResult candidate."""
    from .schemas import ProviderEvidence, ProviderResult  # local import: avoid import cycle

    validated = validate_research_output(raw)
    src = raw if isinstance(raw, dict) else {}
    return ProviderResult(
        provider=src.get("provider", "claude_web"),
        object_type=src.get("object_type", "companies"),
        matched=validated["matched"],
        confidence=int(src.get("confidence", 0)),
        data=validated["data"],
        evidence=ProviderEvidence(evidence_urls=list(validated["evidence_by_field"].values())),
        evidence_by_field=validated["evidence_by_field"],
    )


if __name__ == "__main__":
    # ponytail: smallest runnable self-check for non-trivial branching logic (the
    # synonym lookup + default fallback), no pytest/fixtures required.
    assert normalize_org_type("league") == "governing_body_league"
    assert normalize_org_type("Governing Body") == "governing_body_league"
    assert normalize_org_type("completely made up") == "unknown"
    assert normalize_org_type(None) == "unknown"
    assert normalize_org_type_result("something unmappable") == {
        "value": "unknown", "needs_review": True,
    }
    assert normalize_content_types(
        ["live stream", "streaming", "bogus_value", "highlights"]
    ) == ["streaming", "highlights"]
    assert len(ORG_TYPE_DEFINITIONS) == 9 and all(v.strip() for v in ORG_TYPE_DEFINITIONS.values())
    assert "QRIC" in org_type_definitions_block()
    assert "Racing NSW" in org_type_definitions_block()
    assert org_type_coherence_flags(
        {"lv_org_type": "regulator", "lv_produces_content": True}
    )
    assert org_type_coherence_flags(
        {"lv_org_type": "regulator", "lv_produces_content": None}
    ) == []
    assert org_type_coherence_flags(
        {"lv_org_type": "governing_body_league", "lv_produces_content": True,
         "lv_sponsorship_reliant": True}
    ) == []
    print("src/taxonomy.py self-check OK")
