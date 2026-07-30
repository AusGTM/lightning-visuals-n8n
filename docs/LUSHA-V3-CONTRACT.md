# Lusha v3 Enrichment API — Contract of Record

**This document, not `.planning/phases/20-lusha-v3-migration/20-RESEARCH.md`, is the
contract of record.** RESEARCH.md's v3 wire-contract section was WebSearch-snippet-derived
(`docs.lusha.com` is a JS-rendered SPA that could not be fetched byte-exact) and explicitly
flagged itself as "the probe's starting hypothesis, not ground truth." Every claim below was
confirmed against a live `HTTP 200`/`400`/`401` from `api.lusha.com` on 2026-07-30, using
`scripts/probe_lusha_v3.py` and equivalent direct calls against the same endpoints/bodies in
the same session.

## 1. Status header

- **Probe date:** 2026-07-30 (UTC).
- **Account context:** Lusha `professional` plan, portal renewal 2025-11-19 → 2026-11-19.
- **Credits before probe session:** 3955 remaining (of 4200 total).
- **Credits after probe session:** 3943 remaining (of 4200 total).
- **Total probe session spend: 12 credits** (well under the 40-credit cap).
- **Measurement caveat:** `GET /v3/account/usage`'s `credits.remaining` is **eventually
  consistent, not synchronous** — a balance re-read taken immediately after a call can
  under-report the true debit by several credits for a few seconds (observed directly:
  one repeat-search call showed a 0-credit delta on an immediate re-read, then a re-read
  ~4 seconds later showed the debit had landed). Every credit figure in this document
  below is the response body's own synchronous `billing.creditsCharged` field (not
  subject to this lag) unless stated otherwise; the balance figures above are settled,
  re-confirmed reads taken several seconds after the last billable call.

## 2. Endpoints and auth

| Capability | Method | URL | Auth | Confirmed |
|---|---|---|---|---|
| Contacts combined | POST | `https://api.lusha.com/v3/contacts/search-and-enrich` | `api_key` header | Live 200 |
| Contacts two-step search | POST | `https://api.lusha.com/v3/contacts/search` | `api_key` header | Live 200 |
| Contacts two-step enrich | POST | `https://api.lusha.com/v3/contacts/enrich` | `api_key` header | Live 200 |
| Companies combined | POST | `https://api.lusha.com/v3/companies/search-and-enrich` | `api_key` header | Live 200 |
| Account usage | GET | `https://api.lusha.com/v3/account/usage` | `api_key` header | Live 200 (already in production use) |

`Content-Type: application/json` is required on every POST. Auth stays the `api_key`
header (assumption A5) — confirmed by a real 200 on every endpoint above, not by
inference from the sibling usage endpoint alone.

## 3. Contacts: request

**Winning body** (verbatim, PII redacted per §"PII redaction" below):

```json
{
  "contacts": [
    {
      "firstName": "Kyle",
      "lastName": "Bettler",
      "companyName": "Racing NSW",
      "companyDomain": "racingnsw.com.au"
    }
  ]
}
```

**Every attempted property, accepted or rejected:**

| Body shape tried | Result | Rejection message |
|---|---|---|
| `{"contacts": [{"contactId": "1", firstName, lastName, companyName, companyDomain}]}` | **400** | `contacts.0.property contactId should not exist` |
| `{"contacts": [{"contactId": "1", fullName, companyName}]}` | **400** | `contacts.0.property contactId should not exist` (rejected before reaching `fullName`) |
| Flat body, no `contacts` wrapper: `{firstName, lastName, companyName, companyDomain}` | **400** | `property firstName should not exist` (top level must be `{"contacts": [...]}`) |
| `{"contacts": [{firstName, lastName, companyName, companyDomain}]}` (**no `contactId`**) | **200** | — WINNER |
| `{"contacts": [{firstName, lastName, "notARealProperty": "x"}]}` | **400** | `contacts.0.property notARealProperty should not exist` |

**Key finding:** v3 dropped the v2 `contactId` array-indexing convention entirely — any
`contactId` key inside a `contacts[]` item is rejected outright. The array wrapper itself
(`{"contacts": [...]}`) is still required (a flat top-level body is also rejected), but
each item is a plain identity object with no synthetic index key.

## 4. Contacts: response

**Envelope** (verbatim structure; the person's revealed email is a synthetic placeholder,
see §"PII redaction"):

```json
{
  "requestId": "<uuid>",
  "results": [
    {
      "id": "v1.KAhdDgsmsNBQGn3i1G3Kol8BeXocnO-klQ",
      "firstName": "Kyle",
      "lastName": "Bettler",
      "fullName": "Kyle Bettler",
      "jobTitle": {
        "title": "Head of Live Racing",
        "departments": ["Other"],
        "seniority": "Director",
        "startDate": "2025-03-01"
      },
      "company": {
        "id": "v1.2H4pQSagp9OuOjAPuKXjEWQyn8yvWUI",
        "name": "Entain Australia & New Zealand",
        "domain": "www.entaingroup.com.au",
        "industry": "Entertainment"
      },
      "location": {
        "country": "Australia", "countryIso2": "AU", "city": "Sydney",
        "continent": "Oceania", "coordinates": [151.207, -33.868], "isEuContact": false
      },
      "socialLinks": { "linkedin": "https://www.linkedin.com/in/example-redacted-slug" },
      "partialProfile": false,
      "linkedinConnections": 559,
      "linkedinFollowers": 563,
      "emails": [
        {"email": "REDACTED-SYNTHETIC@example-corp.com.au", "type": "work",
         "confidence": null, "updateDate": "2024-09-25"}
      ],
      "phones": [],
      "tags": [],
      "previousEmployment": [
        {"company": {"name": "Racing NSW", "domain": "racingnsw.com.au"},
         "jobTitle": {"title": "Race Fields and Operations Manager",
                      "departments": ["Operations"], "seniority": "Manager"}}
      ],
      "updateDate": "2024-09-25"
    }
  ],
  "billing": { "creditsCharged": 1, "resultsReturned": 1 }
}
```

**Field paths `lushaCandidates()` needs:**

| Signal | Path |
|---|---|
| Record identifier (for `lusha_contact_id` staging) | `results[i].id` |
| Email list | `results[i].emails[]` → `.email`, `.type` (`"work"`/etc.) |
| Phone list, mobile-vs-other discriminator | `results[i].phones[]` → `.number`, `.type` (`"mobile"` \| `"direct"`) |
| Job title | `results[i].jobTitle.title` |
| Seniority | `results[i].jobTitle.seniority` |
| Department | `results[i].jobTitle.departments[]` |
| Update dates | `results[i].updateDate` (record-level); `results[i].emails[].updateDate` / `.phones[].updateDate` (field-level) |

No `contacts.{id}` map keying (v2's shape) — v3 is a flat `results` array, positionally
aligned with the request's `contacts` array (single-item in this waterfall's usage
pattern, so index `[0]` is safe without a match-back key).

## 5. Companies: request and response

**Winning body:**

```json
{"companies": [{"domain": "racingnsw.com.au"}]}
```

**Every attempted property:**

| Body shape tried | Result | Rejection message |
|---|---|---|
| `{"companies": [{"companyId": "1", "domain": "racingnsw.com.au"}]}` | **400** | `companies.0.property companyId should not exist` |
| `{"companies": [{"domain": "racingnsw.com.au"}]}` (no `companyId`) | **200** | WINNER |

Same v3 pattern as contacts: the v2-style synthetic index key (`companyId`, mirroring
`contactId`) is rejected; a plain identity object survives.

**Response envelope** (truncated to the fields the merge layer needs; nothing here is
personal data, no redaction needed):

```json
{
  "requestId": "<uuid>",
  "results": [
    {
      "id": "v1.I1A7s1z0zyPx-me1MP0DoLFaOfyjNjfH",
      "name": "Racing NSW",
      "domain": "www.racingnsw.com.au",
      "emailDomain": "racingnsw.com.au",
      "homepageUrl": "https://racingnsw.com.au",
      "companyType": "Private Company",
      "yearFounded": 1996,
      "employeeCount": {"exact": 191, "min": 51, "max": 200},
      "industry": "Entertainment",
      "subIndustry": "Sports",
      "location": {"city": "Sydney", "state": "New South Wales", "country": "Australia",
                    "countryIso2": "AU"},
      "revenueRange": {"min": 10000000, "max": 50000000},
      "socialLinks": {"linkedin": "https://www.linkedin.com/company/racing-nsw"}
    }
  ],
  "billing": {"creditsCharged": 2, "resultsReturned": 1}
}
```

**No `has`/`canReveal` fields appear anywhere in this response.** Unlike the contacts
two-step `/search` response (§6), the companies lane never exposes a reveal-preview
structure — see §6's Open-Question-1 verdict.

## 6. Reveal model

**Vocabulary, confirmed live (not guessed):** the parameter name is `reveal`, an array of
field-name strings. Confirmed accepted values: `"emails"`, `"phones"`. The `/contacts/search`
response (the two-step lane's first call) exposes a preview structure per matched result:

```json
"has": ["firstName", "lastName", "jobTitle", "location", "socialLinks", "emails", "phones", "previousEmployment"],
"canReveal": [
  {"field": "emails", "credits": 0},
  {"field": "phones", "credits": 0}
]
```

`canReveal[].credits` is Lusha's own **advertised** marginal reveal cost per field —
observed as `0` for every field on every identity probed this session (contrast with the
generic price list at `GET /v3/account/usage` → `pricing.revealEmail: 1 credit`,
`pricing.revealPhone: 5 credits` — the generic sticker price does not match what this
account was actually charged, see below).

**Measured A/B (the number REQ-lusha-selective-reveal's premise rests on):** using Mick
James / Australian Turf Club (a contact confirmed to have BOTH a revealable email and two
revealable phone numbers), two independent `/contacts/enrich` calls against the SAME
stored contact `id`:

| Call | `reveal` value | `billing.creditsCharged` |
|---|---|---|
| Minimal | `["emails"]` | **0** |
| Maximal | `["emails", "phones"]` | **0** |

**Delta between reveal-nothing and reveal-phones: 0 credits (identical).** Additionally, a
true "reveal nothing" call is **not achievable** on `/contacts/enrich` at all — an empty
`reveal: []` returns HTTP 400, `"reveal must contain at least 1 elements"`.

**Verdict: selective reveal buys nothing on this account.** Whether a `/contacts/enrich`
call asks for 1 field or 2 fields, the billed cost is identical (0 credits either way, for
a contact whose `id` is already known). The entire cost of enriching a KNOWN contact is
therefore already zero regardless of which fields are requested — there is no marginal
reveal charge to avoid by gating `reveal[]` on `missingFields`. **Assumption A3 is
REFUTED as originally stated** (see §10). The real cost driver this probe found is NOT
which fields are revealed — it is whether the call re-runs a fresh identity **search**
(billed 1 credit, every time, even on a verified repeat of the exact same identity — see
§7) versus enriching an **already-known `id`** (billed 0 credits, unconditionally).

**Companies lane (Open Question 1 — answered):** no `has`/`canReveal` structure appears
anywhere in the companies response. The companies lane has **no selective-reveal
mechanism at all** — it is a flat per-match charge (2 credits observed for a repeat
domain match, see §5's billing block). REQ-lusha-selective-reveal's mechanism does not
extend to companies; no reveal-derivation code should be written for that lane
(RESEARCH.md Pitfall 4 confirmed correct).

## 7. Two-step vs combined

Measured for a fresh (never-previously-searched-this-session) identity, Mick James:

| Step | Endpoint | `billing.creditsCharged` |
|---|---|---|
| Two-step, call 1 | `POST /contacts/search` | 1 |
| Two-step, call 2 | `POST /contacts/enrich` (`reveal: ["emails"]`) | 0 |
| **Two-step total** | | **1** |
| Combined, single call | `POST /contacts/search-and-enrich` (first time for that identity) | 1 |

**For this waterfall's one-identity-per-call usage pattern, two-step and combined cost
the SAME (1 credit) on a first-time enrichment** — there is no credit saving from
splitting into two HTTP calls. **Recommendation: ship on the combined
`search-and-enrich` endpoint** (Plan 02) — it keeps one HTTP node per lane (existing
topology 1:1) and there is no measured cost reason to add the two-step's extra HTTP node
+ branch.

**The real lever is re-enrichment, not two-step-vs-combined** (see §8): a **repeat**
`search-and-enrich` call for the SAME identity (fields, not id) was billed
`creditsCharged: 1` again (confirmed live — re-running the exact Kyle Bettler identity
body a second time in this session billed 1 credit again, not 0). The credit saving
Plan 04 should target is calling `/contacts/enrich` with a **stored `id`** on
re-enrichment, instead of re-running `search-and-enrich` by identity fields — see §8.

## 8. Record id re-enrichment

Measured across four independent `/contacts/enrich` calls, each passing a previously
returned `id` back in the `ids` array:

| Call | Contact | `reveal` | `billing.creditsCharged` |
|---|---|---|---|
| 1 | Kyle Bettler (id from the P1 combined-call match) | `["emails"]` | **0** |
| 2 | David Preschlack (id from a fresh `/search` call, first-ever reveal of his phone) | `["phones"]` | **0** |
| 3 | Mick James (first enrich call for this id) | `["emails"]` | **0** |
| 4 | Mick James (SAME id, second enrich call, broader reveal) | `["emails", "phones"]` | **0** |

**Every `/contacts/enrich` call against a stored `id` billed 0 credits**, regardless of
whether it was the first-ever reveal for that id or a repeat. **Verdict: CONFIRMED.**
Passing a stored `lusha_contact_id`/`lusha_company_id` back on
`/contacts/enrich`/(presumed, untested directly) a companies-lane enrich call avoids the
1-credit search charge that a fresh identity-based `search-and-enrich` call always incurs
— including on a verified repeat of the exact same identity (§7). This is exactly
REQ-lusha-id-staging's premise, and it holds.

## 9. No-match envelope, error shapes, and rate-limit headers

**No-match** (fabricated identity `Zzz Qqqnotreal` / `Nonexistent Holdings Pty Ltd`,
tried on both the combined and the two-step `/search` endpoint):

```json
{
  "requestId": "<uuid>",
  "results": [
    {"error": {"code": "NOT_FOUND", "message": "Contact not found"}}
  ],
  "billing": {"creditsCharged": 0, "resultsReturned": 0}
}
```

HTTP status is **200** (not a top-level 404) — the no-match signal lives inside the
per-item `results[i].error` object. `billing.creditsCharged: 0` — a no-match is free.
This directly answers Open Question 3: v3 keeps the "per-item error, outer 200" shape
that `lushaCandidates()`'s v2 defensive-unwrap logic already expects; the equivalent v3
branch needs to check `results[0].error` rather than `contacts["1"].error`.

**Error shapes (two DISTINCT envelope families observed):**

| Case | HTTP | Envelope |
|---|---|---|
| Malformed property (`notARealProperty` on an identity object) | **400** | Business-validation family: `{"name": "BadRequest", "message": "contacts.0.property notARealProperty should not exist", "code": 400, "className": "bad-request", "errors": {}}` |
| Wrong API key, same format/length (auth guard actually runs) | **401** | Auth-guard family: `{"statusCode": 401, "timestamp": "<iso>", "message": "Invalid API key", "error": "Unauthorized"}` |
| API key wrong format/length entirely | **400** | Auth-guard family: `{"statusCode": 400, "timestamp": "<iso>", "message": "Invalid API key format", "error": "Bad Request"}` |

Neither error path carries a `billing` key at all (not merely `creditsCharged: 0`) —
rejected/unauthenticated calls are structurally distinguishable from a billed 200 by the
mere presence/absence of `billing`, in addition to the HTTP status.

**Rate-limit headers**, confirmed present on every response (200 and 400 alike):

```
x-daily-requests-left, x-rate-limit-daily
x-hourly-requests-left, x-rate-limit-hourly
x-minute-requests-left, x-rate-limit-minute
```

No `429` was observed this session (request volume stayed far under the hourly/minute
limits). No credit was charged on any 400/401 response observed.

## 10. Assumption verdicts

| # | Claim | Verdict | Decided by |
|---|---|---|---|
| A1 | `POST /v3/contacts/search-and-enrich` / `POST /v3/companies/search-and-enrich` are the correct v2→v3 endpoint mappings. | **CONFIRMED** | §3 (live 200), §5 (live 200) |
| A2 | Request body moves query params into JSON body with v2-similar identity key names. | **CONFIRMED, with a correction** | §3, §5 — `firstName`/`lastName`/`companyName`/`companyDomain` (contacts) and `domain` (companies) all work verbatim, but the hypothesized `contactId`/`companyId` indexing keys are REJECTED (400) — v3 has no synthetic per-item index key at all. |
| A3 | `reveal[]` is an array of field-name strings, with a `canReveal` array of `{field, credits}` describing per-field reveal cost; reveal-nothing should cost less than reveal-phones. | **REFUTED** (the field-name/array-shape half is CONFIRMED; the cost-differentiation half is REFUTED) | §6 — the A/B delta between `reveal:["emails"]` and `reveal:["emails","phones"]` is 0 (identical); an empty `reveal:[]` isn't even a valid request. |
| A4 | Companies lane has no distinct reveal-gated credit model (flat search/enrich charge). | **CONFIRMED** | §5, §6 — no `has`/`canReveal` in the companies response at all. |
| A5 | Auth stays `api_key` header (not OAuth/Bearer) on v3 enrichment endpoints. | **CONFIRMED** | §2 — every endpoint accepted the `api_key` header live. |
| A6 | Error shape is roughly `{"error": {code, message}}`/`{"statusCode", "message", "errors"}`; rate-limit signals arrive via `x-rate-limit-*`/`x-*-requests-left` headers; a 429 does not consume a credit. | **CONFIRMED** (error envelopes and rate-limit headers); **UNKNOWN** for the 429-credit claim specifically (no 429 was triggered this session) | §9 |
| A7 | v3 contact/company IDs are permanent, account-scoped identifiers; passing a stored ID on a later request yields `canReveal.credits: 0` / a free re-enrichment. | **CONFIRMED** | §8 — 4/4 independent `/contacts/enrich` calls against a stored id billed 0 credits, including calls that revealed a field for the very first time. |

## 11. Usage endpoint

**Confirmed working, no migration needed.** `scripts/provider_registry.py`'s
`PROVIDER_REGISTRY["lusha"]["credit"]["url"]` is already
`https://api.lusha.com/v3/account/usage`, and `scripts/build_cloud_workflows.py:3942-3943`
builds the `"Lusha Usage"` HTTP node as
`_credit_http_node("Lusha Usage", lusha_credit["url"], lusha_credit["method"], ...)` where
`lusha_credit = PROVIDER_REGISTRY["lusha"]["credit"]` — the node's URL is sourced from the
registry, not a hard-coded literal (RESEARCH.md Open Question 4, now resolved: zero build
work required).

`.venv/bin/python scripts/check_provider_credits.py` (run through the dotenv wrapper)
printed `lusha: credits=3943 status=200`. A direct `GET /v3/account/usage` read taken in
the same window returned `credits.remaining: 3943` — **the two agree.**

## PII redaction note

Per threat T-20-03, every revealed email address and phone number that appeared in a live
response has been replaced above with a structurally identical synthetic placeholder
(same field shape, same type, same general format) and is marked `REDACTED-SYNTHETIC` or
omitted where a placeholder would be misleading. Field names, list shapes, and value
*types* are the contract; the specific revealed values are not, and this committed
document does not carry real Lusha-revealed PII. Company-level firmographic data (§5) is
not personal data and required no redaction. LinkedIn profile slugs were also replaced
with a placeholder out of caution even though they are already-public professional URLs.

## Gate verdict (Task 3 — operator review)

**Approved 2026-07-30.** Operator confirmed the A3/A7 verdicts, the 12-credit spend, and
the PII redaction above. The re-scope this doc's §6/§8 findings implied has already
landed upstream (`559eda5`, `docs(phase-20): re-scope REQ-lusha-selective-reveal after A3
refutation`):

- **REQ-lusha-selective-reveal re-scoped**, not dropped: `reveal[]` derived from
  `missingFields` survives as **PII-minimization hygiene** on the contacts lane only
  (never send a broader reveal than the gate asked for), not as a cost-control lever —
  the live A/B proved reveal-field-count doesn't change billed cost. A minimal
  non-empty set is always sent (`reveal:[]` is invalid — §6). No reveal-derivation code
  is written for the companies lane (no mechanism exists there — §5/§6).
- **Cost lever is stored-id re-enrichment (A7) + flat v3 pricing**, not selective reveal:
  full-sweep cost now projects at flat v3 rates (~1 credit/contact first-time enrich, ~2
  credits/company match, 0 credits on any stored-id re-enrich), comfortably inside the
  ~3.9k balance — see ROADMAP.md success criterion 3 (re-scoped) and REQUIREMENTS.md.
- **Plan 02 proceeds on the combined `search-and-enrich` endpoint only** (§7
  recommendation) — no two-step topology change.
- **A7 confirmed — Plan 04 (`lusha_contact_id`/`lusha_company_id` staging) unchanged.**

Plans 02 and 04 may now proceed against this contract and the re-scoped requirement.
