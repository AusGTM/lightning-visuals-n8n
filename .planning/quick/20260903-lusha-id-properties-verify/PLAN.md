---
slug: lusha-id-properties-verify
created: 2026-09-03
status: complete
---

# Quick: verify the pending Lusha id properties, create if absent

**Ask:** run `sync_hubspot_properties.py` dry-run; if it confirms the 2 pending creates,
create them (operator authorised, classifier disabled). The ask also carried an `lv_`-prefix
rule for new properties — **the operator withdrew that rule the same day; see below.**

**Outcome: nothing was created, because nothing needed creating.** The dry-run reports
**0 properties to create** on both objects, and a direct read of the live portal confirms
both properties already exist. No write was made; the authorisation went unused.

## Evidence (read-only GETs, portal 22617666, 2026-09-03)

| Property | Object | Group | Type | createdAt |
|---|---|---|---|---|
| `lusha_contact_id` | contacts | `lv_enrichment_contacts` | string / text | 2026-07-30T09:35:00.653Z |
| `lusha_company_id` | companies | `lv_enrichment` | string / text | 2026-07-30T09:34:58.490Z |

Both timestamps are Phase 20's own date. **Task 3 was performed at the time**; only the
record went stale — `20-VERIFICATION.md` was authored later and never re-checked live.

## The `lv_` naming instruction — WITHDRAWN by the operator, 2026-09-03

**The rule is cancelled and does not apply to future properties.** It was given during
this task and withdrawn in the next message, before any property was created under it.
No property was created here in any case, so it never had a subject and nothing in the
portal reflects it. Do NOT treat it as a standing naming convention.

The history check it prompted is kept below, because it is a useful fact about the
portal independent of the withdrawn rule.

The instruction was to check history. The history is **mixed**, not uniformly `lv_`:
`config/hubspot_properties.yaml` carries 53 names — 46 `lv_`-prefixed, and 7 not:

- `lusha_contact_id`, `lusha_company_id` — provider-id staging (this task's subject)
- `org_type_score`, `geography_score`, `annual_revenue_score`,
  `produces_content_score`, `gambling_score` — the five component scores the calculated
  `lv_icp_fit_score` sums

The 7 unprefixed names are consistent with CLAUDE.md §7.1, which specifies provider
staging fields unprefixed by design (`apollo_domain`, `lusha_domain`, ...).

**Renaming the existing 7 was never on the table, and is NOT recommended regardless:**
HubSpot has no rename — it is delete + recreate, which drops the stored values. The five
component scores feed a live calculated property, and the two Lusha ids are read and
written at 8+ code sites (`build_cloud_workflows.py` :1344, :1782, :2379, :1563, :1636,
:3359, :5465, :5487, plus the search-property CSVs at :2027 and :4805). Out of scope here
and a real regression risk; raise it as its own phase if the consistency is wanted.

## Correction to the prior turn's claim

The earlier session statement — "confirmed genuinely open, not stale: `lusha_contact_id`
appears nowhere in `scripts/sync_hubspot_properties.py`" — was wrong, and so was the
latent-400 risk built on it. The names live in `config/hubspot_properties.yaml`, which the
script reads at `CONFIG_PATH`; grepping the script alone proved nothing. **There is no
latent 400** on the Lusha id write path: the properties exist.
