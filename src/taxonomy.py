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
    print("src/taxonomy.py self-check OK")
