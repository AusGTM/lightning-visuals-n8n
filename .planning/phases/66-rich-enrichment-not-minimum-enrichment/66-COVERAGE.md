# Phase 66 Plan 02: Field Producer/Consumer Matrix (D-66-07)

**Measured:** 2026-09-05, from `tests/n8n/fieldProducerMatrix.test.mjs` (run it to reproduce —
every column below is read from `config/field_policy.yaml`, `n8n/code/normalizeProviders.js`,
`scripts/build_cloud_workflows.py`, and the regenerated `n8n/wf_enrichment_cloud.json`, never
hand-copied).

## The three spellings of one field

A single field can carry up to three different names, and the seam between them is what made
`lv_linkedin_url` invisible for as long as it was:

1. **The pushed key** — what `normalizeProviders.js`'s `_push(out, field, ...)` call writes.
   Usually identical to the policy key, except the two PN-1 renames below.
2. **The policy / HubSpot property key** — what `config/field_policy.yaml`, the merge engine's
   policy table, and the gate's `REQUIRED`/search-property lists all use. This is the column
   header in both tables below.
3. **The identity-matching key** — `config/column_mapping.yaml`'s `required_identity.any_of`
   and `n8n/code/columnMap.js`'s `requiredIdentity`, contacts only. `linkedin_url` here is a
   **different, unrelated spelling** from the pushed key of the same name — it identifies a
   contact for matching, it does not merge/promote a candidate.

**The two PN-1 renames (contacts only):** the pushed key is unprefixed (`linkedin_url`,
`persona_group`); the policy/search key is `lv_`-prefixed (`lv_linkedin_url`,
`lv_persona_group`). The rename happens once, in `ENRICH_MERGE`
(`scripts/build_cloud_workflows.py`), at `candidate.lv_linkedin_url = canonicalizeLinkedin(winners.linkedin_url)`
and `candidate.lv_persona_group = winners.persona_group`. A push under the prefixed spelling
is a silent no-op — `scoreEnrichment.js` groups candidates by the pushed key, so the merge's
`winners.linkedin_url` read would simply never see it, with no error anywhere. Companies has no
equivalent rename: every companies policy key is what its producer branch (or the research
lane) already pushes/spreads verbatim.

## Contacts lane (12 policy keys)

All 12 keys are `promote_to_canonical: true`. `REQUIRED` already equals the full set (66-01
Task 3) — this lane needed no widening in this plan.

| Field (policy key) | Class | Producing branches | Pushed key (if different) | Fetched onto `existingRecord` | Chased by gate | Notes |
|---|---|---|---|---|---|---|
| `email` | fill_blank_only | Lusha, Apollo, ZoomInfo | — | Yes | Yes | |
| `city` | fill_blank_only | Lusha, Apollo, ZoomInfo | — | Yes | Yes | |
| `state` | fill_blank_only | Lusha, Apollo, ZoomInfo | — | Yes | Yes | |
| `country` | fill_blank_only | Lusha, Apollo, ZoomInfo | — | Yes | Yes | |
| `hs_state_code` | fill_blank_only | Lusha, Apollo (code-shaped only), ZoomInfo (code-shaped only) | — | Yes | Yes | Apollo/ZoomInfo only emit when the raw value is already code-shaped (`_codeShaped`), never a name->code lookup. |
| `hs_country_region_code` | fill_blank_only | Lusha, Apollo (code-shaped only), ZoomInfo (code-shaped only) | — | Yes | Yes | Same guard as above. |
| `phone` | fill_blank_only | Lusha, Apollo, ZoomInfo | — | Yes | Yes | Dynamic `field` variable (`"phone"`/`"mobilephone"` by ternary), not a literal `_push(out, "phone", ...)` call — the matrix test's literal scan over the whole branch text still finds it because both string literals appear in the same branch. |
| `mobilephone` | fill_blank_only | Lusha, Apollo, ZoomInfo | — | Yes | Yes | Same dynamic-field note as `phone`. |
| `jobtitle` | stale_refreshable (180d) | Lusha, Apollo, ZoomInfo | — | Yes | Yes | |
| `seniority` | system_owned | Lusha, Apollo, ZoomInfo | — | Yes | Yes | |
| `lv_linkedin_url` | fill_blank_only | Apollo | pushed as `linkedin_url` (PN-1 rename) | Yes | Yes | ZoomInfo pushes **no** linkedin producer — see Known Gap 1 below. Host-guarded (`_linkedinHostOnly`, `linkedin.com` and subdomains only). |
| `lv_persona_group` | system_owned | Lusha, Apollo | pushed as `persona_group` (PN-1 rename) | Yes | Yes | ZoomInfo pushes no persona_group either (not flagged as a gap — no ICP/veto dependency, unlike LinkedIn's identity-matching value). |

## Companies lane (17 policy keys)

Three-part derivation rule (RICH-02): a companies key is chased (`REQUIRED`) only when **all
three** hold — `promote_to_canonical: true`; class is neither `score_output` nor
`veto_output`; and this matrix records at least one producing branch. 13 of 17 keys clear the
rule; the other 4 are excluded, each for a different, load-bearing reason (see Notes).

| Field (policy key) | Class | `promote_to_canonical` | Producing branches | Fetched onto `existingRecord` | Chased by gate | Notes |
|---|---|---|---|---|---|---|
| `domain` | manual_protected | false | **none** | Yes | No | Excluded twice over: not promotable, AND producer-less. Known Gap 2 below — open todo, cited not fixed. |
| `industry` | stale_refreshable (365d) | true | Lusha, Apollo, ZoomInfo | Yes | No -> **Yes (this plan)** | |
| `numberofemployees` | fill_blank_only | true | Lusha, Apollo, ZoomInfo | Yes | No -> **Yes (this plan)** | CLAUDE.md §29.1's ONE scoped exception (58-05 Task 2): admits an already-numeric provider value only, no band parsing. Chasing this field does not widen that exception — the merge's admission rule is unchanged. |
| `annualrevenue` | review_required | false | **none** | Yes | No | Excluded: not promotable (stage-only, human review), AND producer-less. If it were required, every company without a human-entered value would gate to `enrich` forever, every scheduled tick — the 2026-08-09 execution-runaway shape. The single most important exclusion in this plan. |
| `lv_revenue_band` | system_owned | true | Lusha, Apollo, ZoomInfo | **No -> Yes (this plan, CSV)** | No -> **Yes (this plan)** | Not currently in `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` — added in the same commit that widens `REQUIRED`, or the non-clobber comparison would read it as permanently blank. |
| `lv_employee_band` | system_owned | true | Lusha, Apollo, ZoomInfo | **No -> Yes (this plan, CSV)** | No -> **Yes (this plan)** | Same CSV gap as `lv_revenue_band`. |
| `lv_country_region_normalized` | system_owned | true | Lusha, ZoomInfo | Yes | No -> **Yes (this plan)** | Apollo's companies branch does not push this (no dedicated region field on Apollo's org object); Lusha/ZoomInfo suffice. |
| `country` | fill_blank_only | true | Lusha, Apollo, ZoomInfo | Yes | No -> **Yes (this plan)** | |
| `city` | fill_blank_only | true | Lusha, Apollo | Yes | No -> **Yes (this plan)** | ZoomInfo's company enrich requests no `city` outputField — documented absence in `normalizeProviders.js`, not a gap (Lusha/Apollo suffice). |
| `lv_org_type` | system_owned | true | Claude web research | Yes | Yes (unchanged) | |
| `lv_produces_content` | system_owned | true | Claude web research | Yes | Yes (unchanged) | |
| `lv_content_type` | system_owned | true | Claude web research | Yes | No -> **Yes (this plan)** | |
| `lv_sponsorship_reliant` | system_owned | true | Claude web research | Yes | No -> **Yes (this plan)** | |
| `lv_is_hardware_vendor` | system_owned | true | Claude web research | Yes | No -> **Yes (this plan)** | |
| `lv_is_gambling_operator` | system_owned | true | Claude web research | Yes | No -> **Yes (this plan)** | |
| `lv_anti_icp_flag` | veto_output | true | *(recomputed, not chased)* | n/a | No | Recomputed by `Decide Company Action` every run from current inputs — never chased, the same reasoning that keeps `lv_icp_fit_score` out of any contacts-shaped `REQUIRED` list. |
| `lv_anti_icp_reason` | veto_output | true | *(recomputed, not chased)* | n/a | No | Same as above. |

**Research-lane producer signal:** the Claude web-research lane (`n8n/code/webResearch.js`)
spreads `{...raw.data}` wholesale rather than pushing named literals, so a source-text scan for
`_push`-shaped calls (as done for the three provider branches) cannot find its output fields.
The matrix instead reads `config/field_policy.yaml`'s `allow_web_research: true` flag — the
same flag the merge policy already uses to gate promoting a research candidate for that field —
as the derivable "research produces this field" signal. All 6 `system_owned` ICP fields with no
provider-branch producer carry this flag.

**`HS_SEARCH_BODY_EXPR`** (`build_enrichment_local_live()` only, contacts) remains a known
narrower sibling of the widened `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`, deliberately not
widened in 66-01 or here — flagged in a code comment for a future plan, not this matrix.

## Known Gaps (pinned by test, not fixed here)

1. **ZoomInfo contacts: no LinkedIn producer.** `ZOOM_OUTPUT_FIELDS` is account-verified; an
   unprobed output field risks a batch-wide 400 (`zoominfo-gtm-enrich-400-blocker` memory
   record). Not a chase-gate hole — Apollo already produces `lv_linkedin_url` (66-01 Task 3).
   Precedent for probing before trusting a new field: `scripts/probe_zoominfo_location_fields.mjs`.
   Pinned by `tests/n8n/fieldProducerMatrix.test.mjs`'s "known gap: ZoomInfo's contacts branch
   pushes no linkedin-shaped field" test.

2. **Companies `domain`: no candidate source at all.** Has a policy entry
   (`manual_protected`), a create-seed provenance stamp, and zero producers on either lane
   mechanism (no provider push, no research field). This is a merge-correction question, not
   a chased-field question — reviewed by `66-CONTEXT.md`'s `<deferred>` block and deliberately
   NOT folded into this phase. Open todo:
   `.planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md`. Pinned by
   `tests/n8n/fieldProducerMatrix.test.mjs`'s "known gap: no provider branch pushes a companies
   `domain` candidate" test.

Neither gap is a machine-checked assertion FAILURE in `fieldProducerMatrix.test.mjs`'s four
main assertions — both fields are out of scope for those assertions by construction (`domain`
because `promote_to_canonical: false`; ZoomInfo-LinkedIn because `lv_linkedin_url` already has
a producer via Apollo). They are pinned by two small, separate regression tests instead, so a
future change that silently closes or widens either gap is still caught.

---
*Phase: 66-rich-enrichment-not-minimum-enrichment, Plan 02*
*Produced by: `tests/n8n/fieldProducerMatrix.test.mjs`*
