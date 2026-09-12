---
created: 2026-09-12T01:30:00.000Z
updated: 2026-09-12
title: "Ingest lane drops paid-for enrichment extras (mobile, LinkedIn, seniority, geo) at the dispatch boundary — operator ruling 2026-09-12: map them, fix the linkedin_url naming, recency-bias conflicts, allow multi-value email/phone"
area: "operator-plugin, n8n-ingest-lane"
severity: major
kind: design
decision_needed: "sign-off on the property mapping table (below) before the follow-up phase is planned; the four rulings themselves are MADE (operator, 2026-09-12, at the D-71-06 gate)"
owner: operator
files:
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/extraction.py
  - config/column_mapping.yaml
  - config/field_policy.yaml
  - n8n/code/columnMap.js
  - n8n/code/adaptFetchById.js
  - scripts/build_cloud_workflows.py
---

## Observed (live, D-71-06 gate, 2026-09-12 — 71-UAT.md F71-5)

Jimmy Busteed `352422766048` landed with email + phone + jobtitle only. His held row carried
`mobilephone +61 419 212 580` and `lv_linkedin_url linkedin.com/in/jimmybusteed` — found by the
waterfall, paid for, then dropped by `preingest.strip_enrichment_extras` because the ingest CSV
lane's canonical header set is only `company, company_id, email, firstname, jobtitle, lastname,
linkedin_url, phone` (`extraction.canonical_props()`). Louise White `352433740230` and Luke
Janovsky `352403124690` lost the same fields.

Naming defect on top: the lane HAS a `linkedin_url` header, but the enrichment lane emits the
key as `lv_linkedin_url` (`n8n/code/adaptFetchById.js:90` maps the other way), so LinkedIn
never lands through the header that exists for it. Also `column_mapping.yaml` aliases
`mobile: phone`, collapsing a mobile column onto `phone`.

## Operator rulings (2026-09-12) — not to be relitigated

1. Fix the LinkedIn column naming defect.
2. Do NOT drop enrichment extras — map them onto HubSpot properties at the dispatch boundary.
3. Conflicts resolve with a RECENCY bias: the newer observation wins (provider result observed
   now > spreadsheet value of unknown age > HubSpot value whose `lastmodifieddate` is older than
   the observation; a HubSpot value modified more recently than the provider observation keeps).
4. Multiple email / phone / mobilephone values are acceptable.

## Proposed HubSpot mapping (worked example, for sign-off) — properties verified live 2026-09-12

| Enriched key | HubSpot property | Notes |
|---|---|---|
| `email` (primary) | `email` | identity key, unchanged |
| 2nd+ email | `hs_additional_emails` (HubSpot-defined, writable) — `;`-separated; `work_email` for a work address when primary is personal | never overwrite `email` on an existing record; extras append |
| `phone` (landline/office) | `phone` | keep |
| `mobilephone` | `mobilephone` (HubSpot-defined `phonenumber`) | `mobile` alias must map HERE, not to `phone`; `lv_mobilephone_verified_at` exists for the verifier stamp |
| 2nd phone | `hs_whatsapp_phone_number` if a mobile; else a new custom `lv_phone_2` | custom prop needs creating (lowercase name, live-only validation) |
| `lv_linkedin_url` | `hs_linkedin_url` (HubSpot-defined) AND keep custom `lv_linkedin_url` | rename the ingest header/alias to `lv_linkedin_url` or map `linkedin_url` → `hs_linkedin_url` in the lane; pick one, pin with the YAML/JS parity test |
| `seniority` | `seniority` (string) — `hs_seniority` is an enum; map only if the vocabulary matches | |
| `lv_persona_group` | `lv_persona_group` (exists) | |
| `city` / `state` / `country` | `city` / `state` / `country` | `hs_state_code` / `hs_country_region_code` when the provider gives ISO codes |

Worked example, Busteed: `{email: jbusteed@…, phone: +61 2 9663 8460, mobilephone: +61 419 212 580,
hs_linkedin_url: http://www.linkedin.com/in/jimmybusteed, lv_linkedin_url: same, jobtitle: "General
Manager of Sales" (provider, newer, wins over the CSV title under ruling 3), city/state/country: absent
(no provider location) }`.

## Scope

Follow-up phase (touches `column_mapping.yaml` + `columnMap.js` parity, `strip_enrichment_extras`
→ a mapping step, `merge_enriched`'s conflict rule, `field_policy.yaml`, the ingest lane's contact
property assembly in `build_cloud_workflows.py` → regenerate + deploy + bounce, plus HubSpot custom
properties). Not Phase 71.
