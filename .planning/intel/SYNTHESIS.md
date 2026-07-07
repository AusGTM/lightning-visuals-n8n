# Ingest Synthesis Summary

Entry point for `gsd-roadmapper`. Mode: new. Generated 2026-07-07.

## Doc counts by type
- SPEC: 1 — CLAUDE.md (HubSpot → n8n enrichment + ICP scoring system)
- PRD: 1 — icp-scoring.md (ICP / Anti-ICP validation, for sign-off)
- ADR: 0
- DOC: 0
- Total synthesized: 2 (0 skipped, 0 blocked)

## Decisions locked
- 0 locked decisions (no ADRs in ingest set). See `decisions.md`.

## Requirements extracted
11 from icp-scoring.md (see `requirements.md`):
- REQ-icp-scoring-model, REQ-anti-icp-vetoes, REQ-graduated-deductions,
  REQ-tiering, REQ-org-type-targeting, REQ-enrichment-plan,
  REQ-hubspot-icp-properties, REQ-closed-lost-capture, REQ-finite-list-motion,
  REQ-intent-scoring, REQ-signoff-gate.

## Constraints extracted
11 from CLAUDE.md (see `constraints.md`):
- protocol: CON-platform-sales-hub-pro, CON-orchestration-n8n-cloud,
  CON-llm-cascade, CON-non-clobber-merge, CON-safety-gates,
  CON-locking-idempotency, CON-rollout-phasing (7)
- schema: CON-source-attribution, CON-hubspot-data-model, CON-icp-scoring-config (3)
- api-contract: CON-provider-adapter-contract (1)

## Context topics
2 (see `context.md`): external cross-refs (RTK.md, Market-Research);
market/competition background + PRD data-quality caveats.

## Conflicts
- 0 blockers
- 0 competing variants
- 3 INFO (verified-consistent scoring model; PRD-only intent scoring not yet in
  SPEC; SPEC extends tier set with Unscored/Needs-Review). See
  `../INGEST-CONFLICTS.md`.

## Relationship between the two docs
Complementary, not competing. icp-scoring.md (PRD) is the validated business
case — governing-body-first targeting, anti-ICP vetoes, scoring weights derived
from 92 closed deals, pending Alex sign-off. CLAUDE.md (SPEC) is the
implementation contract that operationalizes those weights into
config/icp_scoring.yaml, a HubSpot data model, a non-clobber merge pipeline, an
LLM cascade, and a phased n8n rollout. Scoring numbers agree across both.

## Open items for roadmapping (not conflicts)
- Point weights are illustrative pending JTBD 2 sign-off (PRD §5, §9).
- Pixel intent scoring defined in PRD but not in SPEC config (REQ-intent-scoring).
- HubSpot on Starter today; Pro tier required; orchestration options still open (PRD §9).

## Pointers
- Report: `../INGEST-CONFLICTS.md`
- Per-type intel: `decisions.md`, `requirements.md`, `constraints.md`, `context.md`
