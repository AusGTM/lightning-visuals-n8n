# Dry-Run Report — Gillon McLachlan (Tabcorp)

**Date:** 2026-07-15T05:49:29.139Z  ·  **Mode:** DRY RUN (no HubSpot write)  ·  **Type:** example contact
**Target:** Gillon McLachlan · Tabcorp · tabcorp.com.au

> Live provider calls → real production scoring (`n8n/code`) → read-only HubSpot search → printed payload. Nothing was written to HubSpot.

## 1. Provider auth + retrieval (live)

| Provider | HTTP | Result | Candidates mapped |
|---|---|---|---|
| lusha | 200 | OK | 0 |
| apollo | 200 | OK | 0 |
| zoominfo | 400 | ERROR | 0 |

## 2. Best-per-field winners (scored across providers)

_No candidates scored._ **gap_flag = true** (all providers returned no usable fields for this contact — would route to manual).

## 3. Idempotency decision

- HubSpot search: HTTP 200, 0 existing match(es).
- Gate: **CREATE** — no existing record

## 4. Dry-run payload (WOULD be sent — not written)

```json
{
  "action": "create",
  "contact_id": null,
  "properties": {},
  "note": "DRY RUN — not written to HubSpot"
}
```

## 5. Raw provider responses (live)

### lusha — HTTP 200
```json
{
  "requestId": "919c219f-6774-44ab-b0bf-2de6cf5786b3",
  "results": [
    {
      "error": {
        "code": "NOT_FOUND",
        "message": "Contact not found"
      }
    }
  ],
  "billing": {
    "creditsCharged": 0,
    "resultsReturned": 0
  }
}
```

### apollo — HTTP 200
```json
{
  "person": {
    "id": "6a571f6b746a3e000c64720e",
    "first_name": "Gillon",
    "last_name": "McLachlan",
    "name": "Gillon McLachlan",
    "linkedin_url": null,
    "title": null,
    "photo_url": null,
    "twitter_url": null,
    "github_url": null,
    "facebook_url": null,
    "extrapolated_email_confidence": null,
    "headline": null,
    "organization_id": "54a1269669702d90a28f1800",
    "employment_history": [
      {
        "_id": "6a571f6c746a3e000c647212",
        "created_at": null,
        "current": true,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": null,
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": null,
        "organization_id": "54a1269669702d90a28f1800",
        "organization_name": "Tabcorp",
        "raw_address": null,
        "start_date": null,
        "title": null,
        "updated_at": null,
        "id": "6a571f6c746a3e000c647212",
        "key": "6a571f6c746a3e000c647212"
      }
    ],
    "email": "gillon.mclachlan@tabcorp.com.au",
    "email_status": "verified",
    "organization": {
      "id": "54a1269669702d90a28f1800",
      "name": "Tabcorp",
      "website_url": "http://www.tabcorp.com.au",
      "angellist_url": null,
      "linkedin_url": "http://www.linkedin.com/company/tabcorp",
      "twitter_url": "https://twitter.com/tabcorp",
      "facebook_url": "https://facebook.com/profile.php?id=112682692079234&_rdr",
      "primary_phone": {
        "number": "+61 3 9246 6010",
        "source": "Owler",
        "sanitized_number": "+61392466010"
      },
      "languages": [
        "English",
        "English"
      ],
      "alexa_ranking": 195666,
      "phone": "+61 3 9246 6010",
      "linkedin_uid": "8442",
      "founded_year": 1994,
      "publicly_traded_symbol": "TAH.AX",
      "publicly_traded_exchange": "asx",
      "logo_url": "https://zenprospect-production.s3.amazonaws.com/uploads/pictures/69b381f228cfbb0001a0a709/picture",
      "crunchbase_url": null,
      "primary_domain": "tabcorp.com.au",
      "sic_codes": [
        "7999"
      ],
      "naics_codes": [
        "71312",
        "713290",
        "516110",
        "516120"
      ],
      "sanitized_phone": "+61392466010",
      "industry": "entertainment",
      "estimated_num_employees": 5100,
      "keywords": [
        "wagering",
        "media",
        "gaming services",
        "entertainment providers",
        "media services",
        "sustainability",
        "customer engagement",
        "media and community",
        "d2c",
        "amazon ses",
        "market leader",
        "customer experience",
        "retail outlets",
        "media systems",
        "gaming solutions",
        "multichannel wagering",
        "media and technology",
        "media platforms",
        "digital channels",
        "e-commerce",
        "sports betting",
        "innovation",
        "media and sports",
        "media brands",
        "amusement arcades",
        "mobile app",
        "gambling",
        "community engagement",
        "entertainment",
        "government",
        "digital transformation",
        "compliance",
        "media solutions",
        "b2c",
        "technology innovation",
        "services",
        "betting",
        "media and innovation",
        "media broadcasting",
        "industry solutions",
        "react",
        "cloud infrastructure",
        "market research",
        "gaming",
        "media and wagering",
        "media and growth",
        "media streaming",
        "regulatory compliance",
        "media infrastructure",
        "investment",
        "media and customer engagement",
        "content creation",
        "b2b",
        "media and gaming",
        "responsible gambling",
        "media and digital experience",
        "retail",
        "media technology",
        "salesforce",
        "media and entertainment",
        "media and responsible gaming",
        "mergers",
        "immersive customer experiences",
        "acquisitions",
        "akamai",
        "betting platform",
        "community contributions",
        "horse racing",
        "technology",
        "multi-channel",
        "digital wagering",
        "tab",
        "sky racing",
        "sky sports radio",
        "max",
        "corporate governance",
        "diversity",
        "equity",
        "inclusion",
        "integrity services",
        "multi-venue",
        "broadcasting",
        "shareholder relations",
        "customer care",
        "personal information",
        "data privacy",
        "online services",
        "retail betting",
        "gaming machine monitoring",
        "gaming integrity",
        "employee engagement",
        "careers",
        "workplace culture",
        "annual reports",
        "financial performance",
        "exciting experiences",
        "cutting-edge technology",
        "business growth",
        "partnerships",
        "loyalty programs",
        "promotions",
        "customer data",
        "sports analysis",
        "consumer products & retail",
        "environmental services",
        "renewables & environment",
        "consumer internet",
        "consumers",
        "internet",
        "information technology & services",
        "leisure, travel & tourism",
        "enterprise software",
        "enterprises",
        "computer software",
        "internet infrastructure",
        "games",
        "broadcast media"
      ],
      "organization_revenue_printed": "1.7B",
      "organization_revenue": 1709324000,
      "industries": [
        "entertainment",
        "gambling & casinos",
        "broadcast media"
      ],
      "secondary_industries": [
        "gambling & casinos",
        "broadcast media"
      ],
      "snippets_loaded": true,
      "industry_tag_id": "5567cdd37369643b80510000",
      "industry_tag_hash": {
        "entertainment": "5567cdd37369643
```

### zoominfo — HTTP 400
```json
{
  "detail": "There is invalid field(s) in the request",
  "errors": [
    {
      "code": "PFAPI0005",
      "detail": "Invalid field requested",
      "id": "46b4be8d-a964-45db-bee6-d92f5e14d499",
      "source": {
        "pointer": "/matchPersonInput"
      },
      "status": "400"
    }
  ],
  "title": "Invalid request body"
}
```

---
_No HubSpot write occurred. HubSpot was queried read-only (search) for the existence check only. Secrets/tokens are not included in this report._
## 6. Findings & interpretation

**Outcome:** the pipeline ran end-to-end with **zero HubSpot writes**. Auth for all three providers works. The idempotency gate correctly returned **CREATE** (contact absent from HubSpot). Enrichment yielded **no usable fields** for this contact this run, so `gap_flag=true` → in production it routes to manual review rather than writing thin data. That is the intended safe behaviour.

**Per-provider:**
- **Lusha — HTTP 200, `NOT_FOUND`, 0 credits.** Genuine no-match; billed nothing. Correct.
- **Apollo — HTTP 200, person matched** (Gillon McLachlan · Tabcorp) but `title`/`email`/`phone` are `null`. A `people/match` without reveal returns the identity, not the contactable fields. Email needs the reveal path; **phone is async (webhook)**. → the normalizer had nothing to score.
- **ZoomInfo — HTTP 400** (`PFAPI0005`, pointer `/matchPersonInput`). Auth succeeded (token minted); the **request body shape is wrong** — the GTM enrich contract expects a different `matchPersonInput` structure than sent.

**Concrete fixes surfaced (next):**
1. **ZoomInfo GTM enrich body** — correct the `matchPersonInput` / `outputFields` structure to the GTM v1 contract (the 400 is purely request shape).
2. **Apollo reveal** — enable email reveal (+ the webhook path for phone) so a match returns contactable fields; and confirm the normalizer reads Apollo's `people/match` shape (nested `person`) not just the simplified mock shape.
3. **Normalizer live-shape tuning** — `toCandidates` was written to the simplified fixture shapes; validate it against the real nested Lusha/Apollo/ZoomInfo responses (this dry run is the reference data for that).

**Safety confirmed:** HubSpot was queried read-only (search) only; no PATCH/POST issued; no `lv_*` properties touched; provider spend this run = Lusha 0, Apollo 1 match, ZoomInfo 0 (400 before match).
