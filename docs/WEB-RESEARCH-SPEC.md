# Web Research + Taxonomy Spec

**Status:** approved for MVP, pre-implementation
**Version:** `lv-taxonomy-v1`
**Scope:** companies only. Contacts unchanged.

Every requirement below has an ID. `tests/test_taxonomy_conformance.py` and
`tests/test_web_research_spec.py` cite these IDs. A requirement with no test is a spec
bug; a test with no requirement is scope creep.

---

## 0. Context

The company enrichment branch resolves firmographics from three providers. It cannot
resolve the two ICP fields that actually drive scoring:

- `lv_org_type` — 0–40 base points
- `lv_produces_content` — +20, and its `false` value fires a **hard veto**

Measured against the five live prospect accounts (2026-07-20 probe):

| Signal | Resolvable from provider data |
|---|---|
| `lv_org_type` | 3/5 — from ZoomInfo `descriptionList` |
| `lv_produces_content` | **0/5** — no description mentions broadcast or streaming |

Melbourne Racing Club's provider description is generated filler (*"is a company that
operates in the Amusement Parks… industry. It employs 50to99 people"*) — zero signal.

Web research fills this gap and does double duty on entity resolution (§5).

---

## 0.5. Runtime & deployment constraint

**The deliverable is n8n workflow JSON, deployed to n8n Cloud. No custom middleware is
deployed to an IaaS.** This was understood but unwritten; recording it because several
requirements below name Python modules and could otherwise be read as implying a deployed
Python service.

**AR-1.** Every runtime code path MUST execute inside n8n — Code nodes, HTTP Request nodes,
and native n8n nodes. No workflow may depend on a service this project deploys and hosts.

**AR-2.** Outbound HTTP from a workflow is limited to third-party APIs we consume:
HubSpot, Lusha, Apollo, ZoomInfo, Anthropic, and the email verifier. Any other host is
middleware creep and fails the AR-2 guard test.

**AR-3.** `src/*.py` is a **development oracle**, not a deployment artifact. It exists to
(a) run the local dry-run harness, (b) hold the reference implementation that the JS in
Code nodes is proven equal to (NM-6 parity), and (c) generate node content at build time.
None of it runs in production.

**AR-4.** n8n Code nodes cannot read files (no `fs`, no `require` of project paths at
runtime). Anything a node needs MUST be inlined at build time by
`scripts/build_cloud_workflows.py`. This is why the taxonomy is generated into a JS literal
rather than read from YAML — see §2.

> **Known deviation (2026-07-20; quarantined 2026-07-21).** Two Milestone-2 workflows still
> encode the superseded middleware pattern. They now live in `n8n/deprecated/` so that
> `n8n/*.json` IS the deploy manifest — "import every workflow in `n8n/`" is a safe
> instruction, enforced by `test_top_level_is_exactly_the_deployable_set`.
> `n8n/deprecated/wf_upload_ingest.json` and `n8n/deprecated/wf_weekly_sweep.json` consist
> only of a trigger plus `POST http://host.docker.internal:8088/{ingest,sweep}` against the
> FastAPI service in `src/service.py`. They are superseded by `wf_contact_ingest_*.json`,
> which are fully n8n-native. They are excluded from the AR-2 guard by name and MUST NOT be
> deployed to n8n Cloud. Retire or delete them before production rollout.

---

## 0.6. Property naming convention

**Every custom property this workflow creates MUST be prefixed `lv_`.** The prefix is
ownership signalling: it marks the property as created by Lightning Visuals' team, and
distinguishes ours from HubSpot-native fields and from third-party integration properties
(`xero_*`, `zoom_webinar_*`) already in the portal.

**PN-1.** Any property this project creates is named `lv_<name>`.

**PN-2.** HubSpot-native properties are NEVER renamed or prefixed. Verified native in
portal 22617666 (`hubspotDefined: true`): `email`, `firstname`, `lastname`, `jobtitle`,
`phone`, `mobilephone`, `seniority`, `company`, `domain`, `industry`, `annualrevenue`,
`numberofemployees`, `name`, `website`, `country`. The pipeline reads and writes these
under their native names.

**PN-3.** Provider staging properties compose as `lv_<provider>_<field>` with any leading
`lv_` stripped from the field first, so the prefix appears exactly once:

| Canonical field | Staging property |
|---|---|
| `jobtitle` (native) | `lv_apollo_jobtitle` |
| `lv_revenue_band` | `lv_zoominfo_revenue_band` — NOT `lv_zoominfo_lv_revenue_band` |
| `lv_org_type` | `lv_claude_web_org_type` |

**PN-4.** Source-metadata properties compose the same way: `lv_<field>_source`,
`lv_<field>_confidence`, `lv_<field>_evidence_url`, `lv_<field>_verified_at`,
`lv_<field>_validation_status` — again with a leading `lv_` stripped from `<field>` first.
So `lv_org_type` yields `lv_org_type_source` (unchanged), and native `jobtitle` yields
`lv_jobtitle_verified_at`.

**PN-5.** Control properties take the prefix: `lv_enrichment_requested`,
`lv_enrichment_status`, `lv_enrichment_needs_review`, `lv_last_enriched_at`, etc. This
supersedes the unprefixed names in CLAUDE.md §4, §6, §7, §8 and §22.

> **Timing (portal audit, 2026-07-20).** Adopting this now costs nothing. All 5 existing
> custom company properties already comply (`lv_anti_icp_flag`, `lv_icp_fit_score`,
> `lv_icp_tier`, `lv_org_type`, `lv_produces_content`). The ~40 control/staging/metadata
> properties do not exist yet, so there is nothing to migrate. Raised after Phase 15 this
> would have been a rename migration across live data.
>
> The 11 custom contact properties (`xero_*`, `zoom_webinar_*`,
> `initial_zoom_webinar_attendance_average_duration`) are third-party integration fields,
> not ours — correctly excluded by the convention. `organisation__short_name_` is
> ambiguous; confirm ownership before assuming it is out of scope.

---

## 0.7. Scheduled-job predicates under Approach C

CLAUDE.md §19.2 and §19.5 queue scheduled work off **derived** fields (`lv_icp_tier`,
`lv_icp_scored_at`). Under Approach C the pipeline writes only ICP **inputs**; HubSpot
owns the derived outputs, and `lv_icp_tier` / `lv_icp_fit_score` are today placeholder
calculations (every company scores 2). Derived fields are therefore unusable as queue
signals. This section supersedes the §19.2 / §19.5 predicates. Scope: Phase 16; the
acceptance tests land with that phase's plan.

**SJ-1 (input-gap scan, hourly — replaces §19.2 "unscored scan").** Queue a company for
enrichment when any pipeline-owned input is unresolved:
`lv_org_type` empty or `unknown`, OR `lv_produces_content` empty. MUST NOT reference
`lv_icp_tier` or any derived output.

**SJ-2 (stale refresh, monthly — replaces §19.5).** Queue when
`lv_org_type_verified_at` OR `lv_produces_content_verified_at` is older than 180 days.
MUST NOT reference `lv_icp_scored_at` — the pipeline never writes it.

**SJ-3 (requested poller, every 15 min — §19.1 carried forward).** Predicate unchanged
in substance, property names per PN-5: `lv_enrichment_requested = true AND
lv_enrichment_status ≠ running`.

---

## 1. Resolution order

Established over the preceding design discussion. Each stage only runs when the prior
one is exhausted.

```
1. deterministic — cross-provider conflict → withhold + review   [BUILT]
2. retrieval     — web search over first-party sources           [THIS SPEC]
3. judgement     — adjudicate candidates GIVEN 1+2 (§15)         [THIS SPEC]
```

**RO-1.** Judgement MUST NOT run without retrieval output. An LLM judging from parametric
recall alone is least reliable exactly where the ICP lives: it knows Harvey Norman and
FanDuel (which hard vetoes already handle) and confabulates on obscure ANZ clubs (where a
wrong answer actually changes the tier).

**RO-2.** Size conflicts (§5) MUST NOT trigger a model call on their own. Revenue band
only drives graduated deductions, never a veto; withholding already scores it 0.

---

## 2. Taxonomy — single source of truth

`config/taxonomy.yaml` is normative. All other representations are derived.

**TX-1.** Every `org_types` key MUST have a `score` entry in
`config/icp_scoring.yaml → base_score.org_type`, and the values MUST be equal.

**TX-2.** The set of `org_types` keys MUST equal the set of keys in
`icp_scoring.yaml → base_score.org_type`. No extras on either side.

**TX-3.** `field_policy.yaml → companies.lv_org_type.require_evidence_url_for` MUST equal
exactly the set of org_types with `requires_evidence: true`.

**TX-4.** `n8n/code/mergeCompanies.js` MUST NOT contain a hand-maintained copy of the
evidence-gated list. It is generated from the taxonomy at build time. *(Retires debt
introduced 2026-07-20.)*

**TX-5.** Any `org_types` entry declaring `hard_veto: <k>` MUST have `<k>` present in
`icp_scoring.yaml → hard_vetoes`.

**TX-6.** Every `content_types` key MUST declare `implies_content` as exactly `true`,
`false`, or `null`.

**TX-7.** Exactly one `org_types` entry and exactly one `content_types` entry MUST carry
`is_default: true` (`unknown` in both cases).

**TX-8.** Synonyms MUST be unique across the vocabulary — no string may map to two
different values, in either vocabulary.

**TX-9.** No synonym may equal a canonical key of the same vocabulary.

### Adding a value later

Edit `taxonomy.yaml` → rebuild workflows → run the HubSpot property sync → run the
conformance suite. **Never edit a node.** A value added only to a node scores 0 silently
(`.get(org_type, 0)`) and 400s on the HubSpot write.

---

## 3. Normalization

**NM-1.** `normalize_org_type(raw)` MUST return a canonical `org_types` key or the
default (`unknown`). It MUST NEVER return a value outside the vocabulary.

> Note (portal audit, 2026-07-20): `lv_org_type` in portal 22617666 is `string/text`, NOT
> an enumeration — HubSpot will accept *any* string. There is therefore no CRM-level
> guard, which makes NM-1 the **only** barrier between a hallucinated org_type and the
> CRM, and makes `icp_scoring`'s `.get(org_type, 0)` silently score it 0. Strengthening
> the property to an enumeration is tracked separately as an irreversible migration.

**NM-2.** Matching order: exact canonical key → synonym table → `unknown`.

**NM-3.** Comparison is on the normalized string: lowercased, punctuation → space,
whitespace collapsed, trimmed. `"Governing Body"`, `"governing-body"` and
`"  GOVERNING  BODY "` all resolve identically.

**NM-4.** A raw value that resolves to the default MUST set `needs_review`.

**NM-5.** `normalize_content_types(list)` MUST drop unrecognised entries rather than pass
them through, and MUST de-duplicate.

**NM-6.** Python and JS normalizers MUST agree on every case in the shared table — same
taxonomy, same results. Enforced by parity test.

---

## 4. Retrieval

Native Anthropic `web_search` server tool, `WEB_RESEARCH_MAX_SEARCHES` (default 5).

**RT-1.** Three query intents: **identity** (`<name> <domain> about`), **content**
(`<name> watch live | broadcast | streaming`), **size** (`<name> annual report revenue`
— only when §5 withheld a band).

**RT-2.** First-party domains preferred for identity and content. Reputable secondary
sources acceptable for size.

**RT-3.** Fires when EITHER `lv_org_type` is unresolved / lands on an evidence-gated
value, OR `lv_produces_content` is needed. In practice the latter means ~one call per
unscored company.

**RT-4.** Gated by `ALLOW_WEB_RESEARCH` and `MAX_WEB_RESEARCH_PER_RUN`.

**RT-5.** Results cached by **domain** (not record ID), TTL 180 days per SJ-2.
*Blocked:* requires `lv_org_type_verified_at` / `lv_produces_content_verified_at`, which
do not exist in portal 22617666. (`lv_icp_scored_at` is NOT a cache key — Approach C, see
§0.7.) Until created, every run re-researches. Property creation is a prerequisite for
cost control, not a follow-up.

---

## 5. Entity resolution (double duty)

Providers disagree wildly on size when a domain is a franchisor or holding company.
Confirmed live on `harveynorman.com.au`:

| Provider | Entity returned | Band |
|---|---|---|
| ZoomInfo | Harvey Norman | `1-5M` |
| Apollo | Harvey Norman **Seconds World** | `5-50M` |
| Lusha | Harvey Norman | `1B-1.2B` |

A 40-point ICP swing. Note `harveynorman.com.au` resolves to a *store*; the actual group
sits on `harveynormanholdings.com.au`. Domain-keying does not fix this, and neither does
name matching — ZoomInfo's wrong entity is named identically to the right one.

**ER-1.** Output MUST include `entity_resolution.represents` ∈ {`group`, `subsidiary`,
`franchise_outlet`, `single_entity`, `unknown`}.

**ER-2.** When §1 withheld a band, research MAY supply `likely_revenue_band` with a
citable source. Unsourced, the band stays withheld.

**ER-3.** Research MUST NOT overwrite a non-conflicting provider band.

---

## 6. Output contract

Existing `ProviderResult` shape, `provider: "claude_web"`, plus:

```json
{
  "data": {
    "lv_org_type": "<canonical org_types key>",
    "lv_produces_content": true | false | null,
    "lv_content_type": ["<canonical content_types keys>"],
    "...": "remaining REQUIRED_FIELDS"
  },
  "entity_resolution": {
    "represents": "group|subsidiary|franchise_outlet|single_entity|unknown",
    "likely_revenue_band": "<band or null>",
    "notes": "..."
  },
  "evidence_by_field": {
    "lv_org_type": "https://…/about",
    "lv_produces_content": "https://…/watch-live"
  }
}
```

**OC-1.** `evidence_by_field` is REQUIRED and keyed per field. `mergeCompanies` takes
`opts.evidence = {field: url}` and refuses to promote `lv_produces_content` (always) or
evidence-gated `lv_org_type` values without a per-field URL. A flat `evidence_urls` array
does not satisfy the gate that already exists and is tested.

**OC-2.** `data.lv_org_type` MUST be a canonical key (post-NM-1).

**OC-3.** `data.lv_content_type` MUST contain only canonical keys.

**OC-4.** Malformed / unparseable model output MUST yield `matched: false` and MUST NOT
raise into the workflow.

---

## 7. The tri-state rule

`lv_produces_content` is a HubSpot boolean but has three meaningful states.
`src/icp_scoring.py:91` vetoes on `is False`; `None` never reaches that branch and routes
via lines 115-118 to Needs Review / Unscored by score.

| Value | Emit when | Consequence |
|---|---|---|
| `true` | Positive evidence — watch-live page, broadcast partner, streaming presence | +20 |
| `null` | **No evidence found — the default** | 0, Needs Review or Unscored |
| `false` | Positive evidence of *absence*: substantive site, no content anywhere | **Hard veto → Tier D → disqualify** |

**TS-1.** Research MUST emit `null`, not `false`, when evidence is thin or absent.

**TS-2.** Post-validation MUST coerce `false` → `null` when the retrieval returned few or
low-quality sources. A failed search is not evidence of absence, and thin-web-presence
ANZ clubs are the ICP core.

**TS-3.** `false` MUST carry an `evidence_by_field` URL.

**TS-4.** No human-confirmation gate on first-time `false`. The queue self-targets: a
no-content retailer scores <15 → `Unscored` (no queue); a plausible prospect scores ≥15 →
`Needs Review`. A blanket gate would put the entire prospect list in the queue, since "no
content" is the majority outcome.

**TS-5.** §21.2's existing high-risk gates are retained: `true`→`false` overwrite,
tier `A/B`→`D`, `lv_anti_icp_flag` `false`→`true`.

---

## 8. Judgement

Per CLAUDE.md §15, unchanged. Haiku classifies from retrieved text; Sonnet 5 escalates.

**JG-1.** Escalate to Sonnet when: research `lv_org_type` conflicts with the
provider-derived prior; `lv_produces_content` would be `false`; `hardware_vendor` or
`gambling_operator` detected; confidence in 75–85.

**JG-2.** The judge is pointed at **entity identity and classification**, never at
numeric plausibility. LLMs are well calibrated on "does this page describe a governing
body?" and poorly calibrated on "is $1–5M plausible for this company?".

**JG-3.** Judge output below confidence 80 → `needs_review`, never promote.

**JG-4 (added 2026-07-21 from the closed-lost smoke).** The judge MUST assess whether a
cited URL **substantiates the specific claim**, not merely that a URL is present. The
Phase-13 evidence gate checks presence only; the closed-lost control run
(`.planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md`) showed the
model satisfying that gate with citations that do not evidence content output:

| Citation class | Example from the run | Verdict |
|---|---|---|
| Third-party business directory | `myausweb.net.au/automotive/supertech-electronics/` | INSUFFICIENT |
| Tourism / listing directory | `visitbunburygeographe.com.au/business/...` | INSUFFICIENT |
| Bare first-party homepage | `racingnsw.com.au/`, `vrc.com.au/` | INSUFFICIENT for `lv_produces_content` |
| First-party content page | `sctc.com.au/race-fields-footage/`, `.../news/` | SUFFICIENT |
| Owned video channel | `youtube.com/@brisbaneracingclub427` | SUFFICIENT |

Insufficient evidence for `lv_produces_content` demotes the value to `null` (never to
`false` — absence of proof is not proof of absence, TS-1) and sets `needs_review`.

**JG-5.** The `lv_produces_content=true` false positive and the `lv_is_hardware_vendor`
veto are independent paths and MUST both be exercised. Worked case: **Supertech
Electronics** (`supertech-electronics.com.au`) read `true` off a directory listing. Whether
or not JG-4 demotes it, the hardware-vendor veto should independently disqualify it —
verify, do not assume.

---

## 9. Acceptance tests

Golden set = the five live prospect accounts, which between them cover every branch:

| Account | Asserts |
|---|---|
| Racing NSW | `governing_body_league` + content `true` w/ evidence → Tier A/B |
| Melbourne Racing Club | provider text is filler → research carries the classification alone |
| Australian Turf Club | `individual_club_team` — low-score path |
| FanDuel | `gambling_operator` + non-ANZ → deduction *and* veto |
| Harvey Norman | entity resolution — franchise/group split detected |

**AT-1.** Synthetic "obscure club, no web presence" MUST yield `null`, never `false`.
**AT-2.** Synthetic "model returns an off-vocabulary org_type" MUST yield `unknown` +
`needs_review`, never the raw value.
**AT-3.** Golden-set assertions run against recorded fixtures, not live APIs.

---

## 10. Out of scope for MVP

- Contacts (`lv_*` contact fields) — companies only
- Parent/child hierarchy modelling — ZoomInfo `enrichcorporatehierarchy` exists if a real
  account later demands it
- Name-mismatch detection — evaluated and rejected: blind to the identical-name case that
  actually costs (ZoomInfo "Harvey Norman"), and its only true positive is already caught
  by the §1 conflict detector
- `lv_sponsorship_reliant`, `lv_cloud_fear_risk`, `lv_price_sensitivity_risk`
