# src/sweep.py
#
# Phase 9: weekly dedupe/mangled maintenance sweep (CLAUDE.md §13.4 Workflow D).
# CLASSIFY ONLY — flags records to needs_review, never creates or PATCHes. The record
# list is INJECTED (an in-memory list of HubSpot-contact-like dicts), so the whole
# function is pure, deterministic, and offline. A thin HubSpot-search adapter can feed it
# in Phase 10 — do NOT build that here (YAGNI).
#
# The one correctness property that matters: dedupe keys are compared AFTER normalization
# (normalize_email / normalize_phone / canonicalize_linkedin), never as raw strings — so
# two phones in different raw formats that share one E.164 collapse into a single group.
from .schemas import SweepReport
from .normalizer import normalize_email, normalize_phone
from .identity import canonicalize_linkedin

# Fixed (key_type, normalizer, property) order for deterministic duplicate output.
# Phone dedup keys on the "phone" property only; mobilephone is out of scope this phase.
_DUP_KEYS = [
    ("email", normalize_email, "email"),
    ("phone", normalize_phone, "phone"),
    ("linkedin_url", canonicalize_linkedin, "linkedin_url"),
]

# Fixed (field, normalizer, reason) order for mangled detection.
_MANGLED_FIELDS = [
    ("email", normalize_email, "invalid email"),
    ("phone", normalize_phone, "unparseable phone"),
]


def dedupe_sweep(records: list[dict]) -> SweepReport:
    duplicates = []
    review_ids = set()

    for key_type, normalizer, prop in _DUP_KEYS:
        by_key: dict = {}
        for rec in records:
            raw = rec.get("properties", {}).get(prop)
            key = normalizer(raw)
            if not key:  # blank or mangled -> not a group key
                continue
            by_key.setdefault(key, []).append(str(rec["id"]))
        for key in sorted(by_key):
            ids = by_key[key]
            if len(ids) >= 2:
                duplicates.append({"key_type": key_type, "key_value": key,
                                   "ids": sorted(ids)})
                review_ids.update(ids)

    mangled = []
    for rec in sorted(records, key=lambda r: str(r["id"])):
        props = rec.get("properties", {})
        for field, normalizer, reason in _MANGLED_FIELDS:
            raw = props.get(field)
            if raw in (None, ""):  # blank is NOT mangled
                continue
            if normalizer(raw) is None:
                rid = str(rec["id"])
                mangled.append({"id": rid, "field": field, "raw": raw, "reason": reason})
                review_ids.add(rid)

    return SweepReport(
        duplicates=duplicates,
        mangled=mangled,
        duplicate_count=len(duplicates),
        mangled_count=len(mangled),
        to_review_ids=sorted(review_ids),
    )
