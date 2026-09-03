# src/merge_policy.py
#
# Non-clobber merge engine. Transcribed from CLAUDE.md §12.8 with exactly ONE
# documented correctness fix (see `choose_best` below).
#
# classify_field_with_haiku / validate_conflict_with_sonnet are bound at import
# time here, so tests monkeypatch `src.merge_policy.*` (not src.classifier_haiku.*).
import uuid
import json
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List
import yaml

from .schemas import HubSpotRecord, CandidateValue, FieldDecision, MergeResult
from .classifier_haiku import classify_field_with_haiku
from .validator_sonnet import validate_conflict_with_sonnet
from .icp_scoring import compute_icp_score


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def is_blank(value):
    return value is None or value == "" or value == []


# Phase 15 (provenance model): per-field metadata rides in ONE JSON blob per object
# (lv_enrichment_provenance / lv_contact_enrichment_provenance) instead of ~7 flat
# `{field}_*` suffix properties, plus 4 carve-out `_verified_at` cache-key datetimes that
# stay top-level and queryable (HubSpot cannot filter inside a JSON text property; RT-5/
# SJ-2 need "verified_at older than 180 days"). Staging folds into the blob too — no
# `lv_waterfall_*`/`lv_claude_web_*` properties exist; `staging_patch` stays empty.
COMPANY_PROVENANCE_KEY = "lv_enrichment_provenance"
CONTACT_PROVENANCE_KEY = "lv_contact_enrichment_provenance"
COMPANY_CACHE_KEY_FIELDS = {"lv_org_type": "lv_org_type_verified_at",
                            "lv_produces_content": "lv_produces_content_verified_at"}
CONTACT_CACHE_KEY_FIELDS = {"jobtitle": "lv_jobtitle_verified_at",
                            "mobilephone": "lv_mobilephone_verified_at"}


def serialize_provenance(entries: dict) -> str:
    """The ONE serialization rule shared (in spec, not in code — Python and JS each
    implement it) with n8n/code/mergeCompanies.js's / mergeContacts.js's
    `stableStringify()`: stable sorted-key JSON so the blob is byte-identical across
    languages for identical input.

    `ensure_ascii=False` is LOAD-BEARING, not cosmetic: Python defaults to
    `ensure_ascii=True` and emits `\\uXXXX` escapes for any non-ASCII character, while
    `JSON.stringify` always emits raw UTF-8 — so a single macron/accent in a value (e.g. a
    Māori place name) would make the two blobs differ despite matching on ASCII-only
    input. See tests/n8n/parity.test.mjs's non-ASCII fixture row + deliberate-break proof.
    """
    return json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def source_metadata(field: str, candidate, status: str, verified_at: str) -> dict:
    """Returns `{field: entry}` — the ONE provenance ENTRY for `field` under the Phase 15
    blob model (source, confidence, verified_at, evidence_url [omitted when blank],
    validation_status, value = the staged raw candidate). `verified_at` is threaded in
    (not computed here) so every field's entry within one build_merge_result() call
    shares the SAME timestamp — this is what makes the blob byte-comparable to the JS
    stamper, which computes ONE verifiedAt per mergeCompanies()/mergeContacts() call, not
    one per field."""
    entry = {
        "source": candidate.provider,
        "confidence": candidate.confidence,
        "verified_at": verified_at,
        "validation_status": status,
        "value": candidate.normalized_value,
    }
    if candidate.evidence.evidence_urls:
        entry["evidence_url"] = candidate.evidence.evidence_urls
    return {field: entry}


def group_candidates(candidates: List[CandidateValue]) -> Dict[str, List[CandidateValue]]:
    grouped = defaultdict(list)
    for c in candidates:
        grouped[c.canonical_field].append(c)
    return grouped


def choose_best(candidates: List[CandidateValue], priority_order: list):
    # DOCUMENTED DEVIATION from CLAUDE.md §12.8: the spec returned the whole sorted
    # LIST, but every caller treats the result as a single candidate — deterministic_gate
    # does `best.confidence` and build_merge_result reads `chosen.normalized_value`.
    # A list has no `.confidence`, so the spec-as-written raises AttributeError on the
    # first field with candidates and build_merge_result cannot run. Fix: return the top
    # element (`[0]`). Sort key is unchanged (provider_priority index asc, confidence desc).
    # Mirrors the Phase 2 precedent of one minimal, flagged fix to a transcription defect.
    return sorted(
        candidates,
        key=lambda c: (
            priority_order.index(c.provider) if c.provider in priority_order else 999,
            -c.confidence
        )
    )[0] if candidates else None


def has_conflict(candidates: List[CandidateValue]) -> bool:
    values = set([str(c.normalized_value).lower() for c in candidates])
    return len(values) > 1


def parse_provenance_entries(raw) -> dict:
    """JS twin: n8n/code/mergeCompanies.js's _parseProvenanceEntries. Fails CLOSED —
    anything that is not a readable plain object degrades to {} and therefore to
    today's refusal."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def is_system_correctable(policy, entry, current_value, row_conflicted) -> bool:
    """May this manual_protected field's EXISTING value be corrected by the candidate?
    (quick task 260904-pav; CLAUDE.md §17.2's "existing value was previously written by
    the enrichment system" PROMOTE clause.) JS twin: mergeCompanies.js's
    _isSystemCorrectable, same four conjuncts.

    DELIBERATE DIVERGENCE, not drift: the JS engine takes `rowConflicted` as an explicit
    caller opt-in, because its wrapper (ENRICH_MERGE_CO) has already computed a ROW-level
    cross-provider conflict set before it calls mergeCompanies. This function has no such
    object — only its own candidate list — so the caller below passes the
    `has_conflict(candidates)` it already computes. Different input, same intent: a
    franchisor's or parent company's domain must never win on confidence alone.
    """
    sources = policy.get("system_correctable_sources") if policy else None
    if not isinstance(sources, list) or not sources:
        return False
    if not isinstance(entry, dict):
        return False
    if entry.get("source") not in sources:
        return False
    if is_blank(entry.get("value")) or is_blank(current_value):
        return False
    if str(entry.get("value")) != str(current_value):
        return False
    return row_conflicted is False


def deterministic_gate(record, field, current_value, candidates, policy, provider_priority):
    if not candidates:
        return {
            "decision": "reject",
            "chosen": None,
            "confidence": 0,
            "reason": "No candidates available."
        }

    best = choose_best(candidates, provider_priority)
    field_class = policy.get("class", "fill_blank_only")
    min_confidence = policy.get("min_confidence", 80)

    if best.confidence < min_confidence:
        return {
            "decision": "needs_review",
            "chosen": best,
            "confidence": best.confidence,
            "reason": f"Best confidence {best.confidence} below threshold {min_confidence}."
        }

    if has_conflict(candidates) and policy.get("allow_sonnet_escalation", False):
        return {
            "decision": "needs_review",
            "chosen": best,
            "confidence": best.confidence,
            "reason": "Conflicting candidate values require validation."
        }

    if field_class == "manual_protected":
        # 260904-pav: the ONE way past manual_protected — the existing value's own
        # provenance says the enrichment system parked it there, it is still that value,
        # no candidate conflicts, and the candidate already cleared the field's own
        # min_confidence (checked above, so a correction is held to domain's 95 with no
        # new threshold key). `record` may be None on this path (several callers pass it),
        # so read the blob defensively.
        props = getattr(record, "properties", None) or {}
        entry = parse_provenance_entries(props.get(COMPANY_PROVENANCE_KEY)).get(field)
        if is_system_correctable(policy, entry, current_value, has_conflict(candidates)):
            return {
                "decision": "promote",
                "chosen": best,
                "confidence": best.confidence,
                "reason": (
                    f"Existing value was written by the enrichment system "
                    f"(provenance source {entry.get('source')}) and still matches; "
                    f"candidate passed the {min_confidence} threshold with no candidate conflict."
                )
            }
        return {
            "decision": "stage_only",
            "chosen": best,
            "confidence": best.confidence,
            "reason": "Field is manual_protected."
        }

    if field_class == "review_required":
        return {
            "decision": "needs_review",
            "chosen": best,
            "confidence": best.confidence,
            "reason": "Field requires review."
        }

    if field_class in ["system_owned", "score_output", "veto_output"]:
        return {
            "decision": "promote",
            "chosen": best,
            "confidence": best.confidence,
            "reason": "System-owned field passed confidence threshold."
        }

    if field_class == "fill_blank_only":
        if is_blank(current_value):
            return {
                "decision": "promote",
                "chosen": best,
                "confidence": best.confidence,
                "reason": "Current value blank and candidate passed threshold."
            }
        return {
            "decision": "stage_only",
            "chosen": best,
            "confidence": best.confidence,
            "reason": "Current value exists and field is fill_blank_only."
        }

    if field_class == "stale_refreshable":
        if is_blank(current_value):
            return {
                "decision": "promote",
                "chosen": best,
                "confidence": best.confidence,
                "reason": "Current value blank and candidate passed threshold."
            }
        return {
            "decision": "needs_review",
            "chosen": best,
            "confidence": best.confidence,
            "reason": "Refresh candidate requires review in MVP."
        }

    return {
        "decision": "stage_only",
        "chosen": best,
        "confidence": best.confidence,
        "reason": "Default conservative behavior."
    }


def build_merge_result(record: HubSpotRecord, candidates: List[CandidateValue]) -> MergeResult:
    run_id = str(uuid.uuid4())
    field_policy = load_yaml("config/field_policy.yaml")
    provider_priority = load_yaml("config/provider_priority.yaml")

    object_policy = field_policy.get(record.object_type, {})
    object_priority = provider_priority.get(record.object_type, {})

    grouped = group_candidates(candidates)
    decisions = []

    # staging_patch stays EMPTY (Phase 15): staging folds into the provenance blob below,
    # not into `{provider}_{field}` properties. Kept as a MergeResult field for schema
    # stability — nothing populates it any more.
    staging_patch = {}
    canonical_patch = {}
    provenance = {}
    # Fields whose final_decision was "promote" this call -- mirrors mergeContacts.js's
    # `cacheKeys` map (Phase 16.2 gpt #6 / Phase 16.3-01), kept separate from `provenance`
    # because the two answer different questions: `provenance` is the audit trail ("did we
    # evaluate a candidate for this field", true for stage_only/needs_review/reject too);
    # `promoted_fields` is the freshness signal ("is it safe to treat this field as
    # up to date"), true only on promote. Conflating them was Bug 2 (STATE.md 16.3-01
    # "Found, not fixed").
    promoted_fields = set()

    # ONE timestamp shared across every field this call touches — parity with the JS
    # stamper, which computes a single verifiedAt per mergeCompanies()/mergeContacts() call
    # rather than one per field (see source_metadata()'s docstring).
    verified_at = now_iso()

    for field, field_candidates in grouped.items():
        current_value = record.properties.get(field)
        policy = object_policy.get(field, {"class": "fill_blank_only", "min_confidence": 80})
        priority = object_priority.get(field, ["zoominfo", "apollo", "lusha", "claude_web"])

        gate = deterministic_gate(
            record=record,
            field=field,
            current_value=current_value,
            candidates=field_candidates,
            policy=policy,
            provider_priority=priority
        )

        chosen = gate["chosen"]

        haiku_result = classify_field_with_haiku(
            record=record,
            field=field,
            current_value=current_value,
            candidates=field_candidates,
            policy=policy
        )

        final_result = haiku_result
        validation_path = "haiku_only"
        verified_by_model = "haiku"
        validation_status = "llm_classified"

        needs_sonnet = (
            gate["decision"] == "needs_review"
            or haiku_result.get("requires_sonnet_validation") is True
            or (has_conflict(field_candidates) and policy.get("allow_sonnet_escalation", False))
        )

        if needs_sonnet:
            final_result = validate_conflict_with_sonnet(
                record=record,
                field=field,
                current_value=current_value,
                candidates=field_candidates,
                haiku_result=haiku_result,
                policy=policy
            )
            validation_path = "haiku_plus_sonnet"
            verified_by_model = "sonnet_5"
            validation_status = final_result.get("validation_status", "sonnet_validated")

        final_decision = final_result.get("decision", gate["decision"])

        if gate["decision"] in ["reject", "stage_only"] and final_decision == "promote":
            final_decision = gate["decision"]

        if chosen:
            provenance.update(
                source_metadata(
                    field=field,
                    candidate=chosen,
                    status=validation_status,
                    verified_at=verified_at,
                )
            )

        field_decision = FieldDecision(
            field=field,
            current_value=current_value,
            chosen_value=chosen.normalized_value if chosen else None,
            source_provider=chosen.provider if chosen else None,
            decision=final_decision,
            confidence=int(final_result.get("confidence", gate["confidence"])),
            reason=final_result.get("reason", gate["reason"]),
            # DOCUMENTED DEVIATION from CLAUDE.md §12.8: the spec assigned the whole
            # evidence_urls LIST to FieldDecision.evidence_url, but the frozen Phase 1
            # schema types that field Optional[str] — pydantic v2 rejects a list and
            # build_merge_result crashes before returning. Schemas are out of scope, so
            # narrow to the first URL (scalar). The provenance entry's evidence_url
            # stays the full list (plain dict, no validation) as the tests assert.
            evidence_url=chosen.evidence.evidence_urls[0] if chosen and chosen.evidence.evidence_urls else None,
            evidence_summary=chosen.evidence.evidence_summary if chosen else None,
            validation_path=validation_path,
            verified_by_model=verified_by_model,
            staging_updates={},  # Phase 15: staging folds into the provenance blob, not here
            canonical_update={
                field: chosen.normalized_value
            } if final_decision == "promote" and chosen else {},
            metadata_updates=source_metadata(field, chosen, validation_status, verified_at) if chosen else {}
        )

        decisions.append(field_decision)

        if final_decision == "promote" and chosen:
            canonical_patch[field] = chosen.normalized_value
            promoted_fields.add(field)

    # Serialize the provenance blob ONCE (not per field) + emit the carve-out cache-key
    # datetimes as real top-level properties (Phase 15 provenance model).
    provenance_key = COMPANY_PROVENANCE_KEY if record.object_type == "companies" else CONTACT_PROVENANCE_KEY
    cache_key_fields = COMPANY_CACHE_KEY_FIELDS if record.object_type == "companies" else CONTACT_CACHE_KEY_FIELDS

    metadata_patch = {}
    if provenance:
        metadata_patch[provenance_key] = serialize_provenance(provenance)[:60000]
    # BUG FIX (STATE.md 16.3-01 "Found, not fixed" -- mirrors mergeContacts.js:183-194 /
    # mergeCompanies.js's Phase 16.3 fix): gate on `field in promoted_fields`, not
    # `field in provenance`. A staged/needs_review/rejected field still gets its full
    # provenance ENTRY (the audit trail Phase 16.2 wanted preserved), but must NOT get
    # its cache-key verified_at stamped -- that would tell the next stale-refresh scan
    # (RT-5/SJ-2) the field is current when it was never actually accepted.
    for field, cache_prop in cache_key_fields.items():
        if field in promoted_fields:
            metadata_patch[cache_prop] = provenance[field]["verified_at"]

    # Approach C (STATE.md Blockers; Phase 15 criterion 4 retires the write path):
    # HubSpot owns the derived ICP outputs (lv_icp_fit_score, lv_icp_tier,
    # lv_anti_icp_flag, lv_anti_icp_reason, lv_icp_score_breakdown, lv_icp_scored_at,
    # lv_icp_scoring_version, lv_icp_confidence, lv_icp_needs_review,
    # lv_recommended_motion). The engine still computes icp_score for in-pipeline
    # routing (needs_review below) and the audit breakdown — only the canonical WRITE
    # is removed; `MergeResult.icp_score` stays populated.
    icp_score = None
    if record.object_type == "companies":
        # staging_patch is always empty now (Phase 15) — canonical_patch alone is the
        # scoring input; the prior `.update(staging_patch)` call was already inert (
        # compute_icp_score's get_signal() only ever looked up bare canonical keys, never
        # the provider-prefixed staging ones).
        icp_score = compute_icp_score(record, dict(canonical_patch))

    needs_review = any(d.decision == "needs_review" for d in decisions)
    if icp_score and icp_score.tier in ["Needs Review", "Unscored"]:
        needs_review = True

    aggregate_confidence = int(sum(d.confidence for d in decisions) / len(decisions)) if decisions else 0

    source_names = sorted(set([c.provider for c in candidates]))

    status_patch = {
        "enrichment_requested": False,
        "enrichment_status": "needs_review" if needs_review else "complete",
        "last_enrichment_run_id": run_id,
        "last_enriched_at": now_iso(),
        "enrichment_confidence": aggregate_confidence,
        "enrichment_needs_review": needs_review,
        "enrichment_last_sources": ",".join(source_names),
        "enrichment_primary_source": source_names if source_names else "unknown",
        "enrichment_source_count": len(source_names),
        "enrichment_validation_path": "haiku_plus_sonnet" if any(d.validation_path == "haiku_plus_sonnet" for d in decisions) else "haiku_only",
        "enrichment_last_decision": json.dumps({
            "run_id": run_id,
            "decisions": [d.model_dump() for d in decisions],
            "icp_score": icp_score.model_dump() if icp_score else None
        })[:60000]
    }

    full_patch = {}
    full_patch.update(staging_patch)
    full_patch.update(metadata_patch)
    full_patch.update(canonical_patch)
    full_patch.update(status_patch)

    return MergeResult(
        object_type=record.object_type,
        record_id=record.id,
        run_id=run_id,
        field_decisions=decisions,
        icp_score=icp_score,
        staging_patch=staging_patch,
        canonical_patch=canonical_patch,
        metadata_patch=metadata_patch,
        status_patch=status_patch,
        full_patch=full_patch
    )
