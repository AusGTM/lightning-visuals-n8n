## Conflict Detection Report

Ingest set: 2 docs — 1 SPEC (CLAUDE.md), 1 PRD (icp-scoring.md). Mode: new.
Precedence: ADR > SPEC > PRD > DOC. No ADRs, no LOCKED decisions, no cycles.
The SPEC operationalizes the PRD's business logic; their scoring tables were
compared field-by-field for numeric contradictions — none found.

### BLOCKERS (0)

None. No LOCKED-vs-LOCKED contradictions, no cross-ref cycles, no
UNKNOWN/low-confidence classifications. Both docs classified at medium
confidence and are safe to synthesize.

### WARNINGS (0)

None. No competing acceptance variants. The two docs define the same scoring
rubric from complementary angles (PRD supplies rationale/weights derived from
92 closed deals; SPEC supplies the machine-readable config + write pipeline),
and the numeric values agree.

### INFO (3)

[INFO] Verified consistent: ICP scoring model, PRD ↔ SPEC
  source: icp-scoring.md §5 (scoring model + graduated deductions)
  source: CLAUDE.md §10 (config/icp_scoring.yaml, version lv-icp-v0.1)
  Note: Org points (gov/league +40, producer +20, club +5, other 0), content
  +20 (none=veto), ANZ +10 (non-ANZ=veto), revenue $5–500M +10, revenue decay
  −5/−15/−30/−50, gambling −20, and tiers A≥70 / B 40–69 / C 15–39 / D=veto all
  match exactly across both docs. Hard vetoes (non-ANZ, no-content, hardware)
  and the "gambling + >$500M are deductions, never anti-ICP flag" rule also
  match. No resolution needed — recorded for provenance.

[INFO] PRD-only signal not yet operationalized: pixel intent scoring
  source: icp-scoring.md §5 (Intent signals table: +3 / +7 / +5 / +10)
  source: CLAUDE.md §10 (icp_scoring.yaml has no intent component)
  Note: The PRD defines a forward-looking HubSpot-pixel intent-scoring scheme;
  the SPEC's icp_scoring.yaml does not implement it (the PRD itself flags intent
  as forward-looking with no historical data). Not a contradiction — the
  higher-precedence SPEC is silent, not conflicting. Carry as an open item for
  the JTBD 2 rubric build (REQ-intent-scoring) rather than a resolved conflict.

[INFO] SPEC extends PRD tier set with review/gap states
  source: CLAUDE.md §10 (tier_rules: Unscored; §12.7 adds "Needs Review")
  source: icp-scoring.md §5 (tiers A / B / C / D only)
  Note: The SPEC adds "Unscored" (missing required inputs) and "Needs Review"
  (conflicting/low-confidence) tiers absent from the PRD's A/B/C/D. Additive,
  not contradictory — the SPEC handles operational edge cases the PRD does not
  enumerate. Also minor: SPEC scores broadcaster (+20) and regulator (+5)
  explicitly; the PRD omits both from its scoring table but treats broadcaster
  as a ~40% producer-adjacent fit (consistent with +20) and notes regulators
  (e.g. QRIC) sit inside the governing-body bucket without endorsing +40.
