# src/live_patch.py
#
# Boundary translation between the oracle-internal merge-result patch dict (bare
# `enrichment_*` status keys, occasional other bare canonical keys, Python bool values)
# and a live-safe HubSpot PATCH properties payload.
#
# merge_policy.build_merge_result's bare status_patch keys ARE the Python oracle's
# correct INTERNAL contract (CLAUDE.md §4.0 as-built delta, commit 54d7fe4) -- pinned by
# tests/fixtures/company_current.json, tests/test_merge_policy.py, tests/test_main.py,
# and tests/test_contact_ingest.py. Nothing inside build_merge_result gets renamed.
# This module runs ONLY at the two live-write boundaries (main.py, src/ingest.py),
# immediately before their patch_record() call -- never inside
# hubspot_client.patch_record itself, since tests/test_scoring_parity.py calls
# patch_record directly with ~20 already-correct lv_-named payloads and changing its
# semantics would corrupt those.
#
# Measured live 2026-08-11 against portal 22617666 (companies AND contacts -- identical
# shape on both objects, confirmed by direct GET /crm/v3/properties/{object}): of
# status_patch's 11 keys, 3 have a real lv_-prefixed live property; the other 8 were
# spec'd in CLAUDE.md §4.1 but never created. canonical_patch/metadata_patch keys
# (Phase 15 provenance blob) are otherwise already fully lv_-prefixed or genuinely
# native (domain/industry/numberofemployees/annualrevenue/email/phone/mobilephone/
# jobtitle/seniority/firstname/lastname/company -- config/field_policy.yaml's own PN-1
# comments confirm which bare names are native vs. which needed an lv_ rename already)
# -- ONE exception found by measurement: src/ingest.py's _UPLOAD_FIELDS emits bare
# "linkedin_url" (matching config/column_mapping.yaml's canonical prop name), but PN-1
# already renamed the live/policy property to lv_linkedin_url -- confirmed reachable: a
# CSV row with a LinkedIn column promotes bare "linkedin_url" into canonical_patch on a
# blank-current contact, which would 400 under the bare name exactly like status_patch's
# 3 renamable keys.

# Bare keys with a real live counterpart under a different (lv_-prefixed) name.
_BARE_TO_LIVE_RENAME = {
    "enrichment_requested": "lv_enrichment_requested",
    "enrichment_status": "lv_enrichment_status",
    "enrichment_needs_review": "lv_enrichment_needs_review",
    "linkedin_url": "lv_linkedin_url",
}

# status_patch keys with NO live property under either name. Dropped, never invented
# (constraint: no new HubSpot properties).
_ORPHAN_KEYS = {
    "last_enrichment_run_id",
    "last_enriched_at",
    "enrichment_confidence",
    "enrichment_last_sources",
    "enrichment_primary_source",
    "enrichment_source_count",
    "enrichment_validation_path",
    "enrichment_last_decision",
}


def to_live_patch(patch: dict) -> dict:
    """Translate one merge-result patch dict into a live-safe PATCH properties dict.
    Renames the known bare keys with a real live counterpart, drops (and logs) the
    known orphans, stringifies booleans to "true"/"false" (HubSpot's PATCH properties
    map is Map<String,String>), and passes every other key through unchanged."""
    live = {}
    dropped = []

    for key, value in patch.items():
        if key in _ORPHAN_KEYS:
            dropped.append(key)
            continue
        live_key = _BARE_TO_LIVE_RENAME.get(key, key)
        if isinstance(value, bool):
            value = "true" if value else "false"
        live[live_key] = value

    if dropped:
        print(f"to_live_patch: dropped {len(dropped)} orphan key(s) with no live "
              f"HubSpot property: {sorted(dropped)}")

    return live
