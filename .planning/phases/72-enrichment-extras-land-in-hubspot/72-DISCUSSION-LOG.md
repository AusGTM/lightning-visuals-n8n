# Phase 72: Enrichment extras land in HubSpot - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-12
**Phase:** 72-enrichment-extras-land-in-hubspot
**Areas discussed:** Where the mapping lives, Recency rule (scoped), Multi-value email/phone, Geo + live gate, Company parity (operator-raised)

---

## Where the mapping lives

| Option | Description | Selected |
|---|---|---|
| Widen the ingest lane | 12 keys into column map + candidate assembly; plugin stops stripping | ✓ |
| Create thin, then enrich by id | no n8n change; second provider spend per create | |
| Plugin-side only | rename linkedin + one header | |

Also: source of truth = `field_policy.yaml` ✓ (vs column_mapping.yaml); `mobile → mobilephone` ✓; LinkedIn → both `lv_linkedin_url` + `hs_linkedin_url` ✓.

## Recency rule, scoped

| Option | Selected |
|---|---|
| Create: provider wins, CSV recorded as conflict | ✓ |
| Create: CSV wins unless provider ≥ min_confidence | |
| Create: per-field identity/CSV vs rest/provider | |
| Update: only stale_refreshable past TTL | ✓ |
| Update: any system-owned/stale_refreshable | |
| Update: create-only, update unchanged | |
| Timestamps: provider=run time, CSV=none, HubSpot=property history | ✓ |
| Self-overwrite: yes when newer and ≥ min_confidence | ✓ |

## Multi-value email/phone

| Option | Selected |
|---|---|
| 2nd email → hs_additional_emails, primary stays | ✓ |
| 2nd email → work_email by domain class | |
| Primary = provider (recency on email) | |
| Overflow: fixed cap, one `_2` slot each, rest to provenance JSON | ✓ (chosen after the operator asked whether properties scale per record — they are per object type; growth is by slot count) |
| Overflow: one multi-value text property | |
| Overflow: provenance JSON only | |
| Provider tie: trust-rank winner to slot, loser to `_2` | ✓ |
| Stamps: provenance JSON only | ✓ |
| Stamps: per-slot `_source`/`_verified_at` | |

**Notes:** operator asked whether on-the-fly property creation is per record — answered: schema-level per object type, created once at setup, never during a run; bounded by slot cap.

## Geo + live gate

| Option | Selected |
|---|---|
| Names + ISO codes when available | ✓ |
| Contact geo does NOT feed lv_country_region_normalized | ✓ |
| One held new person re-read + one update no-overwrite row | ✓ |
| Deploy ingest lane only | ✓ |

## Company parity (operator-raised mid-discussion)

| Option | Selected |
|---|---|
| Recency in shared policy layer, both objects, both engines | ✓ |
| Company multi-value: hs_additional_domains in scope | ✓ |
| Company geo: add state + hs_state_code + hs_country_region_code | ✓ |
| Company phone: phone (fill_blank_only) + lv_phone_2 | ✓ |
| Company email: confirmed non-goal (no HubSpot property) | ✓ |

## Claude's Discretion
Parity-test shape; property-creation script shape; `hs_additional_emails` serialisation (verify live); per-provider geo field mapping.

## Deferred Ideas
`_3` overflow / multi-value text property; per-field stamp properties; `lv_company_email`.
