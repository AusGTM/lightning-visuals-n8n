from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

ObjectType = Literal["contacts", "companies"]
Decision = Literal["promote", "stage_only", "reject", "needs_review"]

class HubSpotRecord(BaseModel):
    object_type: ObjectType
    id: str
    properties: Dict[str, Any]

class ProviderEvidence(BaseModel):
    last_seen: Optional[str] = None
    match_basis: List[str] = Field(default_factory=list)
    evidence_urls: List[str] = Field(default_factory=list)
    evidence_summary: Optional[str] = None

class ProviderResult(BaseModel):
    provider: str
    object_type: ObjectType
    matched: bool
    confidence: int
    data: Dict[str, Any]
    evidence: ProviderEvidence
    model_trace: Dict[str, Any] = Field(default_factory=dict)

class CandidateValue(BaseModel):
    canonical_field: str
    provider: str
    value: Any
    normalized_value: Any
    confidence: int
    evidence: ProviderEvidence
    model_trace: Dict[str, Any] = Field(default_factory=dict)

class FieldDecision(BaseModel):
    field: str
    current_value: Any
    chosen_value: Any = None
    source_provider: Optional[str] = None
    decision: Decision
    confidence: int = 0
    reason: str
    evidence_url: Optional[str] = None
    evidence_summary: Optional[str] = None
    validation_path: str = "deterministic_only"
    verified_by_model: Optional[str] = None
    staging_updates: Dict[str, Any] = Field(default_factory=dict)
    canonical_update: Dict[str, Any] = Field(default_factory=dict)
    metadata_updates: Dict[str, Any] = Field(default_factory=dict)

class ICPScoreResult(BaseModel):
    score: int
    tier: str
    anti_icp_flag: bool
    anti_icp_reason: Optional[str] = None
    recommended_motion: str
    confidence: int
    breakdown: Dict[str, Any]
    scoring_version: str

class MergeResult(BaseModel):
    object_type: ObjectType
    record_id: str
    run_id: str
    field_decisions: List[FieldDecision]
    icp_score: Optional[ICPScoreResult] = None
    staging_patch: Dict[str, Any]
    canonical_patch: Dict[str, Any]
    metadata_patch: Dict[str, Any]
    status_patch: Dict[str, Any]
    full_patch: Dict[str, Any]

# Phase 6: file ingestion (parse + map + reject-malformed).
class RejectedRow(BaseModel):
    row_index: int
    reason: str
    raw: Dict[str, Any] = Field(default_factory=dict)

class IngestBatch(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    rejects: List[RejectedRow] = Field(default_factory=list)

# Phase 7: identity/dedupe classification (classify-only; no create/PATCH).
class IdentityResult(BaseModel):
    outcome: Literal["match", "net_new", "ambiguous"]
    contact_id: Optional[str] = None          # set ONLY on a confident single match
    match_key: Optional[str] = None           # email | linkedin_url | phone_lastname | name_company | None
    candidate_ids: List[str] = Field(default_factory=list)  # all ids seen for this row
    reason: str

# Phase 9: dedupe/mangled maintenance sweep (CLAUDE.md §13.4 Workflow D). Classify-only:
# flags records to needs_review, never writes. Findings are plain JSON-serializable dicts
# (same style as ingest.py's report) so the Phase-10 decision service can transport them
# without per-finding sub-models.
class SweepReport(BaseModel):
    duplicates: List[Dict[str, Any]] = Field(default_factory=list)  # {key_type, key_value, ids}
    mangled: List[Dict[str, Any]] = Field(default_factory=list)     # {id, field, raw, reason}
    duplicate_count: int = 0
    mangled_count: int = 0
    # sorted-unique LIST with set semantics: a real set is neither ordered nor
    # JSON-serializable, so a sorted list gives determinism + Phase-10 transport.
    to_review_ids: List[str] = Field(default_factory=list)
