# Phase 43: Pipeline Scoring Hygiene & Explainability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-07
**Phase:** 43-Pipeline Scoring Hygiene & Explainability
**Areas discussed:** Breakdown write path, Loss-reason data reality, Coercion blast radius, Veto hardening + dead-path test

---

## Pre-discussion scouting

Claude grepped the live defect sites (`n8n/code/reviewApply.js:89` → boolean `false`;
`scripts/build_cloud_workflows.py:2637` → boolean `true`; string-comparing EQ filters at
`:5088`/`:5329`), located the parity harness (`scripts/run_scoring_parity.py`,
`tests/test_scoring_parity.py`), and established that `lv_closed_lost_reason` exists nowhere
in config or pipeline code, is a Deal property, and that `config/hubspot_properties.yaml`
manages only companies and contacts.

---

## Breakdown write path

| Option | Description | Selected |
|--------|-------------|----------|
| New opt-in write mode | `--write-breakdown` flag, off by default; read-only tier preserved | ✓ |
| Scheduled pass writes it | Sweep tier writes breakdown; Phase 40 D-12 guarantee lost | |
| Separate breakdown script | New script, harness untouched; duplicated fetch logic | |

| Option | Description | Selected |
|--------|-------------|----------|
| Drop detail, keep totals | Shed evidence strings first; retain version/points/vetoes/total; `truncated:true` | ✓ |
| Hard slice at limit | `json.dumps(...)[:60000]`; can emit invalid JSON | |
| You decide | Claude picks | |

| Option | Description | Selected |
|--------|-------------|----------|
| Records the harness checks | Whatever population the invocation targets | ✓ |
| All scored companies | Portfolio-wide backfill | |
| Needs-review records only | Only likely-challenged tiers | |

---

## Loss-reason data reality

| Option | Description | Selected |
|--------|-------------|----------|
| Report over live truth | Query real Deal API; state absence/emptiness explicitly with counts | ✓ |
| Create property + report | Also create the Deal property with the CLAUDE.md picklist | |
| Report over native closed-lost | Aggregate HubSpot's native field instead | |

| Option | Description | Selected |
|--------|-------------|----------|
| Committed artifact under docs/reports/ | Dated markdown+JSON, existing convention | |
| Sweep-integrated | Counts surfaced in unattended sweep | |
| Operator plugin skill | New skill — conflicts with milestone Out of Scope fence | ✓ |

**Follow-up (Claude surfaced the conflict):** ROADMAP Out of Scope lists "Operator plugin
changes | Plugin is v0.6's surface; scoring remediation is backend/HubSpot-side."

| Option | Description | Selected |
|--------|-------------|----------|
| Script now, skill wraps it next milestone | Aggregator in scripts/, plugin work deferred | |
| Override the fence, build the skill | Admit plugin work into v0.7; record the override | ✓ |
| Committed artifact instead | Respect the fence, docs/reports/ only | |

| Option | Description | Selected |
|--------|-------------|----------|
| Stamp + tier cross-tab | Loss reasons × ICP tier/score, rubric-version stamped | ✓ |
| Version stamp only | No cross-tab | |
| You decide | Claude picks dimensions | |

---

## Coercion blast radius

| Option | Description | Selected |
|--------|-------------|----------|
| Both flags, one fix pattern | lv_enrichment_needs_review + lv_icp_needs_review | |
| Named requirement only | lv_enrichment_needs_review strictly | |
| Every boolean property writer | Sweep all boolean-valued HubSpot writes | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Anchored grep + EQ fixture | 36-07 idiom, red-checked, plus live filter proof | ✓ |
| Grep test only | No live EQ proof | |
| You decide | Claude picks test shape | |

---

## Veto hardening + dead-path test

| Option | Description | Selected |
|--------|-------------|----------|
| 80, matching Phase 40 D-04 | Aligns with hardware/gambling thresholds in field_policy.yaml | ✓ |
| 85 | Matches lv_produces_content's higher bar | |
| You decide | Claude anchors to field_policy.yaml | |

| Option | Description | Selected |
|--------|-------------|----------|
| Keep dead-proof, add policy-shape test | Inspect the policy object, don't drive the path | ✓ |
| Temporarily enable in test only | Fixture exercises the guard end-to-end | |
| You decide | Claude picks proof shape | |

| Option | Description | Selected |
|--------|-------------|----------|
| Builder + bounce + arming grep | Regeneration only, disarmed deploy, grep 0, bounce after deploy | ✓ |
| Builder only, deploy deferred | Deploy as a separate operator action | |
| You decide | Claude picks deploy envelope | |

---

## Claude's Discretion

- Boolean-writer inventory content and fix ordering
- Breakdown JSON schema beyond the retained fields
- Plugin skill name/trigger; script-vs-plugin split for the aggregator
- Report file naming/location
- EQ-filter fixture record strategy

## Deferred Ideas

- Creating `lv_closed_lost_reason` on deals + bringing deals under property management
- Portfolio-wide breakdown backfill
- All four carried backlog todos remain unfolded
