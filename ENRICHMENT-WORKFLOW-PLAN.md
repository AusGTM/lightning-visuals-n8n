# Enrichment Workflow — Plan (POC, Cloud-ready n8n)

**Goal:** An idempotent, quality-scored enrichment workflow that checks HubSpot first, then **creates / enriches / skips**, and — instead of FIFO stop-on-first-match — **scores all sources for accuracy + richness, cross-checks, and pushes the best value per field** into the contact-ingestion (non-clobber) merge.

**Status:** Plan (build follows). Provider keys are empty → build against **mock provider responses** shaped to the real API fields (below). `lv_*` HubSpot properties are **awaited** → build against the defined schema, mock the HubSpot read/write. Both swap to live nodes when keys + properties land.

---

## 1. Research verdict — can we score accuracy + richness across 3 sources? YES

None of the 3 has a standalone email/phone *validation* endpoint — validation rides **inside enrichment**. But each returns per-record quality signals sufficient to score, and values normalize enough to cross-check. (Full per-provider findings captured from official docs; key signals below.)

### Per-provider scoring signals

| Signal class | Lusha | Apollo | ZoomInfo |
|---|---|---|---|
| **Email accuracy** | `emails[].confidence` (`A+`/`A`/null), `emails[].type` | `email_status` (`verified`/`guessed`/`unavailable`/`bounced`/`pending`), `extrapolated_email_confidence`, `email_domain_catchall` | *(no per-email grade)* → use `contactAccuracyScore` |
| **Phone accuracy** | `phones[].type` (mobile/direct), `phones[].doNotCall` | `status_cd`, `confidence_cd`, `dnc_status_cd`, `type_cd` (async webhook) | `phone` vs `mobilePhone` (structural type); no grade |
| **Record accuracy** | *(none numeric)* | `waterfall.status` | **`contactAccuracyScore` 0-100**, `matchStatus` (`FULL_MATCH`) |
| **Recency (staleness)** | per-field `updateDate` | `updated_at` | **`validDate`**, `lastUpdatedDate`, `certificationDate` |
| **Match quality** | binary (result vs `error.code=NOT_FOUND`) | match implicit | `matchStatus` |
| **Richness (coverage)** | `has[]`/`canReveal[]` (pre-score before spending credits!) | count populated person+org fields | `requiredFields` gate + count fields, `numberOfContactsInZoomInfo` |
| **Credit model** | per revealed datapoint; re-reveal free | 0 credits on no-match; email/phone reveal cost | 1 credit/record, then free re-enrich for **365 days** |

### Cross-check (consensus) surface — normalized, comparable across all 3
- **Phone** → E.164 (Lusha `phones[].number`, Apollo `sanitized_number`, ZoomInfo `phone`/`mobilePhone`)
- **Email** → address + each provider's verdict
- **Revenue** → numeric/range (Lusha `revenueRange`, Apollo `annual_revenue`, ZoomInfo `revenue`/`revenueRange`)
- **Employees** → numeric/band (all three)
- **Industry** → **NAICS/SIC codes** (Lusha `naicsCodes`/`sicCodes`, ZoomInfo `naicsCodes`) — cleanest join key; free-text `industry` as fallback
- **Country** → ISO alpha-2 (Lusha `countryIso2`)
- **Identity anchors** → LinkedIn URL, domain

---

## 2. Scoring model (field-level best-of-breed)

Score **each candidate value** (a specific field from a specific source), then pick `argmax` per canonical field. Field-level (not whole-source) maximizes richness — best email from Apollo, best phone from ZoomInfo, etc. — and slots straight into the existing per-field non-clobber merge.

```
value_score = wA·A + wR·R + wG·G + wT·T
```
- **A — accuracy** (0-1), from the provider's signal for THAT field:
  - Apollo email: `verified`=1.0, `guessed`=0.5·(extrapolated_confidence), `pending`=0.3, `unavailable`/`bounced`=0; `email_domain_catchall`→×0.6.
  - Lusha email: `A+`=1.0, `A`=0.8, null=0.4; work-type ×1.0, private ×0.8.
  - ZoomInfo: `contactAccuracyScore`/100 (applies to all its contact fields); `matchStatus≠FULL_MATCH`→drop person fields.
  - Phone: Apollo `status_cd=valid_number`=1.0 (× `confidence_cd`); Lusha mobile/direct=0.8, work=0.5; ZoomInfo mobilePhone present=0.8. `doNotCall`/`dnc_status`→suppress (not just downscore).
  - Firmographics with no per-field grade → A = source base (0.6) modulated by recency + agreement.
- **R — recency** (0-1): `1 - min(age_days / stale_ceiling, 1)`. Source of age: ZoomInfo `validDate`→`lastUpdatedDate`; Lusha field `updateDate`; Apollo `updated_at`. `stale_ceiling` per field from `field_policy` (`stale_after_days`).
- **G — agreement** (0-1): fraction of *other* called sources whose **normalized** value matches this one (E.164 phone, lowercased email, revenue band, NAICS). 2+ agree → strong boost. Cross-check = this term.
- **T — source trust** (0-1): base rank from `source_registry` (zoominfo .85, lusha .80, apollo .75) — tiebreaker only.

Default weights (config, tunable): `wA=0.45, wR=0.20, wG=0.25, wT=0.10`. Emit per-winner `{value, source, score, components, agreedBy[]}` as provenance.

**Selection modes (config):**
- `scored_all` (POC default): call all available sources, score, pick best per field. Max accuracy + full cross-check. Cost = N credits/record.
- `scored_cost_aware` (production option): call in cost order (Lusha native → Apollo → ZoomInfo); after each, if every *required* field already has a winner scoring ≥ `high_quality_bar`, stop early; else continue; pick best per field across called sources. Honors "quality-gated, not blind FIFO" while saving credits. Cross-check limited to sources actually called.

> This directly answers the brief: FIFO stop-on-first-match validates only *presence*; this validates *quality* (accuracy + richness) and cross-checks before choosing.

---

## 3. Idempotency + staleness (create / enrich / skip)

```
identity (contact or company)
  → HubSpot search (by email/domain/linkedin — reuse resolveIdentity)
     ├─ NOT found ................ → ENRICH (scored waterfall) → CREATE
     ├─ found, STALE/invalid ..... → ENRICH → non-clobber MERGE → UPDATE
     └─ found, CURRENT+accurate .. → SKIP (do nothing)
```

**"STALE / needs validation"** — record needs enrichment if ANY required field is:
- **missing/blank**, OR
- **stale**: `now - <field>_verified_at > field_policy.stale_after_days` (contacts: jobtitle 180d, phone/email fill-only; companies: revenue 365d, employees 180d), OR
- **invalid**: email fails validation (verifier/`email_status`), phone not E.164.

**"CURRENT + accurate" (skip)** — all required fields present, fresh (within TTL), and passing validation. No write, no credit spent.

Required-field set per object comes from the Phase-1 minimum-data definition (contacts: email or name+company, jobtitle, one phone; companies: domain, industry, employees, revenue, org_type).

---

## 4. n8n workflow design (Cloud-compatible, no deployed service)

```
Trigger (Webhook / Schedule / from ingestion pipe)
  → Code: build identity keys
  → HubSpot: search contact/company           [live node; mocked in POC]
  → Code: exists? + staleness/validation gate  → branch: create | enrich | skip
  → [enrich branch]
       → HTTP: Lusha search+enrich             [mocked in POC]
       → HTTP: Apollo people/org match         [mocked; phone via webhook in prod]
       → HTTP: ZoomInfo search→enrich          [mocked]
       → Code: normalize + SCORE + select best-per-field (the new module)
  → Code: hand winners to non-clobber merge (reuse mergeContacts.js)
  → IF: HubSpot Update (stale) | HubSpot Create (new) | NoOp (skip)   [gated, dry-run default]
  → Set: data-quality labels + gap-flag (all sources failed → manual)
```
All logic in inline **Code nodes** (no npm), HTTP nodes for providers, native HubSpot node for read/write. Provider calls mocked in POC via a Set/Code node returning realistic fixtures; swap to real HTTP/native nodes + credentials for Cloud.

---

## 5. Build plan (waves)

**Wave A — scoring + staleness engine (JS, tested against oracle):**
- `n8n/code/scoreEnrichment.js` — `scoreCandidates(fieldCandidates, opts)` → best-per-field with provenance; per-provider accuracy normalizers; agreement/recency/trust terms.
- `n8n/code/enrichmentGate.js` — `decideAction(existingRecord, requiredFields, policy, now)` → `create|enrich|skip` + which fields are stale/invalid/missing.
- `n8n/code/normalizeProviders.js` — map each provider's raw response → common candidate shape `{field, source, value, normalizedValue, accuracy, recencyDate}`.
- Mock fixtures: `tests/fixtures/enrichment/{lusha,apollo,zoominfo}_{contact,company}.json` shaped to the real API fields (email_status, contactAccuracyScore, confidence, validDate, etc.), incl. a conflict case (sources disagree on revenue; Apollo verified email vs ZoomInfo high accuracyScore).
- `tests/n8n/enrichment.test.mjs` — scoring picks the right winner per field; agreement boosts consensus; staleness gate returns create/enrich/skip correctly; cross-format phone agreement works.

**Wave B — n8n workflow + local run:**
- `n8n/wf_enrichment_cloud.json` (production-shaped, real node types) + `n8n/wf_enrichment_local.json` (mocked, headless-executable).
- Inline the Wave-A modules into Code nodes (via `build_cloud_workflows.py`).
- `scripts/n8n_enrichment_replica.sh` — import + execute on the running local n8n; assert create/enrich/skip branches fire and best-per-field selection produces scored winners; no live write.
- Extend `n8n/README.md` with the enrichment workflow + provider-credential + `lv_*`-property dependencies.

**Verification:** Node tests green; Python suite untouched/green; local n8n replica PASS (all 3 branches, scored selection, no HubSpot write); GUI-viewable at http://localhost:5678.

---

## 6. Dependencies / awaiting
- **`lv_*` HubSpot properties** — not yet created. Workflow reads/writes them by name; mocked until the property-creation step lands. (Separate task: script their creation in the portal.)
- **Provider API keys** (Lusha/Apollo/ZoomInfo) + **HubSpot credentials** — empty; POC mocks provider responses. Apollo phone is **async (webhook)** in production — the Cloud template includes a Webhook-return node for it.
- **Minimum-data definition** (Phase 1) — drives the required-field set for the staleness gate; using the CLAUDE.md/field_policy set as the working definition until Phase-1 confirms.

---

## 7. Open design choices (defaulted, tunable)
- Selection = `scored_all` in POC (full cross-check); `scored_cost_aware` early-exit available for production credit control.
- Scoring weights `wA/wR/wG/wT` = 0.45/0.20/0.25/0.10 — tune against a labeled set later.
- `high_quality_bar` and per-field `stale_after_days` live in config, not code.
