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

## Resolution

Resolved by **Phase 72 (enrichment extras land in HubSpot)**, plans 01–06. The shipped answer
follows this todo's four operator rulings and its proposed mapping table with three differences
from what the table above proposed:

1. **Overflow is capped at ONE `_2` slot per kind, not an open set.** The table above left the
   second-phone/mobile destination open-ended ("a new custom `lv_phone_2`"). D-72-11 fixed it at
   exactly one `_2` slot per kind — `lv_phone_2` and `lv_mobilephone_2` on contacts, `lv_phone_2`
   on companies — created live in plan 05. A third-or-later candidate never gets a slot; it rides
   on the primary field's provenance entry only. No `_3` slot exists or can exist by construction
   (`_overflowSlot()`/`_overflow_slot()` in `n8n/code/mergeContacts.js`, `mergeCompanies.js`,
   `src/merge_policy.py`).
2. **Verification stamps are provenance JSON only, not new per-field `_source`/`_verified_at`
   properties.** The table's own "Notes" column implied per-property verifier stamps in the §6.1
   pattern; D-72-13 kept every landed slot's source/confidence/timestamp inside the object's
   existing `lv_enrichment_provenance`/`lv_contact_enrichment_provenance` blob instead. No new
   HubSpot property was declared for this purpose. `hs_additional_emails` also turned out to be
   an `enumeration` type (not the assumed string), so the second-email write in the table's row 2
   was never built — the second email lands in provenance only (plan 05's live probe,
   `72-PORTAL-PROBE.json`).
3. **Companies are in scope, not contacts alone.** The table above only mapped contact
   properties. Plan 06 gave companies the equivalent geo/phone shape (`state`, `hs_state_code`,
   `phone` + its own `lv_phone_2` overflow) wherever a real provider (Lusha, Apollo) actually
   supplies the value — `hs_country_region_code` stayed out of scope because the live probe found
   the property does not exist on companies, and `hs_additional_domains` stayed an accepted
   no-producer gap because no provider branch pushes a company `domain` candidate at all.

Plan-by-plan: 01 split `mobilephone` off `phone` and wired `existingRecord` into the ingest
merge; 02 widened the remaining seven candidate keys and added `hs_linkedin_url` as a second
native write target; 03 closed the LinkedIn naming fork inside `merge_enriched` and made
create-time provider-wins/`source_by_field` real; 04 added the recency/TTL promotion arm and the
ingest lane's own property-history fetch; 05 created the three overflow-slot properties live and
built the winner/runner-up routing; 06 gave companies their own geo/phone producers. See each
plan's own `*-SUMMARY.md` for verification detail. One gap this phase deliberately leaves open is
tracked in a new pending todo:
`.planning/todos/pending/2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md`.
