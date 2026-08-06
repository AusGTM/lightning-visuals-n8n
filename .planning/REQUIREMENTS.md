# Requirements — Milestone v0.7: HubSpot Scoring Engine Remediation

Defined 2026-08-06. Source evidence: `HANDOVER-2026-08-06-icp-scoring.md` (§2–§4 original
finding, §10 amended workflow investigation, defects F1–F10 all live-validated). Scoring
engine stays HubSpot-resident (operator decision, reaffirmed 2026-08-06). Parity oracle:
`src/icp_scoring.py` + `config/icp_scoring.yaml` (version lv-icp-v0.1).

## v0.7 Requirements

### Path Decision

- [ ] **DECIDE-01**: Operator has an in-portal verification of company fit-score availability
  on Sales Hub Pro, and a recorded path decision — fix the four-workflow chain in place vs
  lead-scoring-tool rebuild — with rationale. Everything downstream is path-shaped by this.

### Scoring Engine (path-neutral outcomes)

- [ ] **ENGINE-01**: A company with `lv_org_type=governing_body_league`,
  `lv_produces_content=true`, region AU, revenue band 50-500M scores **80** and grades **A**
  entirely inside HubSpot — no pipeline scoring code. (Today: 60/B via native inputs; F1.)
- [ ] **ENGINE-02**: `lv_produces_content=true` contributes +20 to the score. (F1 — term
  absent from every component, workflow, and formula.)
- [ ] **ENGINE-03**: Scoring reads the canonical `lv_country_region_normalized` and
  `lv_revenue_band` properties the pipeline actually writes — never native free-text
  `country` or never-written `annualrevenue`. (F2/F3 — current triggers watch properties
  enrichment can never drive.)
- [ ] **ENGINE-04**: Revenue decay fires −5/−15/−30/−50 per rubric, with exact boundary
  values (500M, 750M, 1B, 1.2B) landing in the rubric-correct band. (F10 boundary overlap —
  750M scored −5 live, rubric −15.)
- [ ] **ENGINE-05**: Gambling deduction (−20) is driven by `lv_is_gambling_operator`,
  independent of org type, and never sets the veto flag. (F9 — currently wired as
  org-type points; `lv_is_gambling_operator` referenced by nothing.)
- [ ] **ENGINE-06**: Every org-type point value matches `config/icp_scoring.yaml`,
  including regulator = 5. (F10 — regulator currently 0.)
- [ ] **ENGINE-07**: A score below 15 without a veto does not grade D. (F8 — low fit
  currently conflated with disqualify.)

### Veto Machinery

- [ ] **VETO-01**: All three hard vetoes (non-ANZ, no broadcast/streaming content, hardware
  vendor) set `lv_anti_icp_flag=true` AND write `lv_anti_icp_reason`. (Today: only non-ANZ
  exists, reason never written; F4/F10.)
- [ ] **VETO-02**: Correcting the veto condition clears the flag and reason — no one-way
  latch. (F6 — validated: Australia restored, flag stayed true, tier stuck D.)
- [ ] **VETO-03**: A flag change updates `lv_icp_tier` without requiring an unrelated score
  change. (F7 — tier currently recomputes only on score movement.)

### Data Coverage

- [ ] **DATA-01**: The 66 web-researched companies (49 high-confidence) from the ICP
  validation analysis land in HubSpot with `lv_*` inputs and provenance stamped — zero
  provider spend.
- [ ] **DATA-02**: Imported companies score automatically on landing — no per-record manual
  touch. (Proves triggers fire on the write path enrichment/import actually uses.)

### Parity & Regression

- [ ] **PARITY-01**: A parity harness recomputes expected scores via `compute_icp_score`
  and asserts them against HubSpot's live scores for fixtures plus a real-record sample.
  (Every F-defect was invisible in the HubSpot UI; this is the standing drift guard.)
- [ ] **PARITY-02**: The F4/F7/F9/F10 scratch scenarios (AU-string veto, tier lag, gambling
  conflation, boundary overlap) are encoded as named regression cases in the harness.

### Cleanup

- [ ] **CLEAN-01**: Superseded scoring artifacts are archived, not deleted
  (`scripts/snapshot_hubspot_schema.py` run first), and `config/hubspot_properties.yaml`
  reconciles clean against the live portal.

## Future Requirements (deferred beyond v0.7)

- Full-712 input-coverage backfill trigger — re-enrollment mechanism for existing companies
  (property defaults only stamp new records). Explicitly deferred at scoping (2026-08-06).
- Intent/pixel scoring block (+3/+7/+5/+10) — no property, no config entry, no node
  (carried from v0.5 deferral).
- Review-queue policy at volume — `src/icp_scoring.py` routes 711/712 to review on unknown
  org_type/content; policy decision precedes any armed backfill.

## Out of Scope

| Item | Reason |
| --- | --- |
| Rubric weight changes | JTBD-2 weighted-rubric sign-off (REQ-signoff-gate) is an external business-owner gate ON this milestone, not work inside it |
| Operator plugin changes | Plugin is v0.6's surface; scoring remediation is backend/HubSpot-side |
| `milestone` ws Phase 22 armed canary | Pending operator action in the v0.5 workstream; dependency, separately owned |
| Pipeline-side score computation | Scoring engine stays HubSpot-resident — operator decision 2026-08-06; `src/icp_scoring.py` remains oracle-only |

## Traceability

(Filled by roadmap.)
