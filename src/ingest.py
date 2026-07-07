# src/ingest.py
#
# Phase 8: wire object_type=contacts through the pipeline end to end. An uploaded
# file row becomes just another enrichment SOURCE (`csv`) that flows through the SAME
# build_merge_result engine shipped in Milestone 1 (contacts skip ICP at merge_policy).
# The one genuinely new mechanism is a gated net-new create with a re-check-by-email
# guard. HubSpot fns (hs_search / hs_get / create) are INJECTED so the whole path runs
# offline with canned-dict stubs — no token, no network.
from typing import List

from .schemas import ProviderResult, ProviderEvidence, HubSpotRecord
from .normalizer import provider_to_candidates, normalize_email
from .identity import resolve_identity
from .merge_policy import build_merge_result
from .file_loader import ingest_file
from .hubspot_client import get_record, search_records, create_record, patch_record

# Contact fields an upload row may carry (matches column_mapping canonical props).
_UPLOAD_FIELDS = ["email", "firstname", "lastname", "jobtitle",
                  "phone", "mobilephone", "linkedin_url", "company"]

# Properties fetched for a matched contact before merging (enough for non-clobber).
_CONTACT_PROPS = _UPLOAD_FIELDS + ["seniority", "persona_group",
                                   "enrichment_status", "enrichment_requested"]

# Same email-EQ search shape as identity._search_ids, reused by the recheck guard.
_SEARCH_PROPS = ["email", "linkedin_url", "phone", "firstname", "lastname", "company"]


def row_to_provider_result(row: dict, confidence: int = 80) -> ProviderResult:
    # ponytail: confidence default 80 (ceiling). CLAUDE.md's example used 60, but EVERY
    # contacts threshold in field_policy is >=75 (phone 80, jobtitle 75, linkedin 85,
    # email 95) — a 60-confidence upload could NEVER fill a blank. 80 reflects a
    # DECLARABLE trusted internal export (source_registry csv) and lets fill_blank_only /
    # stale_refreshable actually exercise their promote/needs_review branches. Kept a
    # parameter so a caller/test can lower it to hit the needs_review branch. Raise per
    # upload if a higher-trust source warrants it.
    data = {k: row[k] for k in _UPLOAD_FIELDS if row.get(k) not in (None, "")}
    return ProviderResult(
        provider="csv",
        object_type="contacts",
        matched=True,
        confidence=confidence,
        data=data,
        evidence=ProviderEvidence(match_basis=["upload"],
                                  evidence_summary="user-uploaded file row"),
    )


def precreate_email_recheck(email: str, hs_search=search_records) -> list:
    # Re-run the email EQ search immediately before create. Empty list == clear to
    # create; non-empty == a dup appeared since resolution. CLASSIFY ONLY — never create.
    if not email:
        return []
    resp = hs_search(
        object_type="contacts",
        filters=[{"propertyName": "email", "operator": "EQ", "value": email}],
        properties=_SEARCH_PROPS,
    )
    results = (resp or {}).get("results", []) or []
    return [str(r["id"]) for r in results if isinstance(r, dict) and "id" in r]


def run_contact_ingest(path, hs_search=search_records, hs_get=get_record,
                       allow_create=False, dry_run=True, upload_confidence=80) -> list:
    # ponytail: report is a list of plain dicts — JSON-serializable for the Phase 10
    # decision service. Add a pydantic model only if a consumer needs validation.
    batch = ingest_file(path)
    report: List[dict] = []

    # One entry per rejected (malformed / no-identity) row — no write, just surfaced.
    for rej in batch.rejects:
        report.append({"row_index": rej.row_index, "outcome": "rejected",
                       "action": "skip", "reason": rej.reason})

    for idx, row in enumerate(batch.rows):
        ident = resolve_identity(row, hs_search=hs_search)

        if ident.outcome == "match":
            fetched = hs_get("contacts", ident.contact_id, _CONTACT_PROPS)
            record = HubSpotRecord(object_type="contacts", id=ident.contact_id,
                                   properties=fetched.get("properties", {}))
            candidates = provider_to_candidates(
                row_to_provider_result(row, confidence=upload_confidence))
            merge = build_merge_result(record, candidates)
            patch = merge.full_patch  # staging + metadata + canonical + status (no ICP)
            patch_record("contacts", ident.contact_id, patch, dry_run=dry_run)
            report.append({"row_index": idx, "outcome": "match", "action": "patch",
                           "contact_id": ident.contact_id, "payload": patch,
                           "canonical_patch": merge.canonical_patch})

        elif ident.outcome == "net_new":
            email = normalize_email(row.get("email"))
            ids = precreate_email_recheck(email, hs_search)
            if ids:
                report.append({"row_index": idx, "outcome": "net_new", "action": "review",
                               "reason": "dup found on pre-create recheck",
                               "candidate_ids": ids})
            elif not allow_create:
                report.append({"row_index": idx, "outcome": "net_new", "action": "review",
                               "reason": "ALLOW_CONTACT_CREATE is off; staged for review"})
            else:
                # Reuse the normalize path; INCLUDES email as the new record's identity
                # (nothing to protect on create — the record does not exist yet).
                create_props = {
                    c.canonical_field: c.normalized_value
                    for c in provider_to_candidates(
                        row_to_provider_result(row, confidence=upload_confidence))
                    if c.normalized_value not in (None, "")
                }
                result = create_record("contacts", create_props, dry_run=dry_run)
                report.append({"row_index": idx, "outcome": "net_new", "action": "create",
                               "payload": result})

        else:  # ambiguous
            report.append({"row_index": idx, "outcome": "ambiguous", "action": "review",
                           "reason": ident.reason})

    return report
