# UAT stress assets (`tests/stress-tests/`)

Two CSVs and the reset procedure for the end-client stress session. Run the reset script
from the repo root.

# Mixed dense/sparse contacts batch (2026-09-13)

File: `uat-stress-mixed-batch-2026-09-13.csv` (GITIGNORED — rows 1–2 are real CRM people; regenerate from the row map below if absent) — 48 rows, 15 columns. Built for the
end-client stress session; every fictitious row is marked so it can be found and removed.

## Header set (deliberately non-canonical, all resolve via `config/column_mapping.yaml`)

`First Name, Surname, Organisation, E-mail Address, Job Title, Tel, Mobile, LinkedIn, City,
State/Region, Country, Seniority, Persona, HubSpot Company ID, UAT Marker`

- `Mobile` → `mobilephone` (D-72-03 — not `phone`). `Tel` → `phone`.
- `UAT Marker` is intentionally UNMAPPED. The preview must list it as unresolved and drop it;
  it is never written to HubSpot. Cleanup uses the email pattern instead (below).
- Preview run offline 2026-09-13: 48 rows, 14 headers mapped, 1 unresolved, 0 refusals.

## Row map

| Rows | Shape | Count | Expected outcome |
| --- | --- | --- | --- |
| 1 | Colin Telfer, ATC, real existing contact `1251`, full row + `company_id` | 1 | **update**; existing `phone` survives (SAFE-01); nothing clobbered |
| 2 | Jimmy Busteed, ATC, name + company + title only, `company_id` | 1 | matched by name lane or created (if the Test 3 contact `352522004980` was deleted); enrich reveals email |
| 3–14 | Dense fictitious creates at real ANZ racing orgs — email, title, tel, mobile, LinkedIn, city/state/country, seniority, persona | 12 | **create** + associate; all widened fields land (mobilephone, `lv_linkedin_url` + `hs_linkedin_url`, geo, seniority, persona) |
| 15–22 | Email-only, real org domains | 8 | company resolves by email domain; create; providers return NOT_FOUND for fictitious people (0 Lusha credits) |
| 23–30 | First + Surname + Organisation only (no email) | 8 | weak-key lane → match attempt, then enrich-before-ingest or **held** for review; never a confident write |
| 31–34 | LinkedIn URL only | 4 | linkedin identity lane; company unknown → create refused, **held** |
| 35 | email without TLD | 1 | preview flags bad email; row refused |
| 36 | email with `@@` | 1 | preview flags bad email; row refused |
| 37 | exact duplicate of row 3 | 1 | dedupe → 1 write, duplicate reported |
| 38 | case-variant duplicate of row 3 (`PRIYA…@…`, uppercased) | 1 | case-insensitive dedupe (G3) → collapsed, not a second contact |
| 39 | name only, no company, no email | 1 | **review**, never matched |
| 40 | freemail (`gmail.com`) + NZ location + mobile | 1 | freemail resolves no company → create downgraded to review/held |
| 41 | full row at `Wagga Wagga Rowing Club` (org NOT in portal) | 1 | company never created by the ingest lane → **held** with reason |
| 42 | name + unknown company, no email | 1 | held/review |
| 43 | whitespace-padded cells, `(08)` landline, `0421` mobile | 1 | trimmed; AU numbers normalised to `+61`; create |
| 44 | mobile identical to phone | 1 | both land (D-72-25 acceptable duplication); one `_2` slot never used |
| 45 | email + `company_id` `18756544347` only | 1 | association by manual id (HRNSW) |
| 46 | office switchboard as `Tel`; bare-host `linkedin.com/in/...` URL | 1 | phone lands; LinkedIn normalised or flagged |
| 47 | `New South Wales` long-form state, `AU` ISO country | 1 | state/country normalised; `hs_state_code`/`hs_country_region_code` remain unmapped (no CSV source) |
| 48 | `Tabcorp` (gambling operator class) | 1 | contact creates if company resolves; ICP veto logic is company-side, contact lane unaffected |

Real people: rows 1–2 only (already in the CRM). Every other person is fictitious; every
fictitious email local-part starts with `uat.` and every fictitious LinkedIn slug with `uat-`.

## Cost and budget

- Providers: fictitious names return NOT_FOUND → Lusha 0 credits per row; ZoomInfo/Apollo
  ~0–1 credit per attempted match. Rows 1–2 may spend (real people, up to 7 Lusha credits
  on a rich first-time reveal — exec `12372` precedent).
- To run the shape test without provider spend say **"no providers"** when asking for the
  batch (`enrichment_providers` override to `[]`).
- n8n executions: match POSTs at ≤20 rows each (3), write dispatches at 2 records each
  (~24 worst case) → budget roughly 30 executions of the 2,500/month plan.
- Arming is one write grant for the batch; nothing writes without it.

## Cleanup after the session

Search contacts whose email contains `uat.` (HubSpot search `CONTAINS_TOKEN` on `email`,
or a saved filter "Email contains uat.") and restorable-delete them. LinkedIn-only creates
(if any landed) carry `lv_linkedin_url` containing `uat-`. Rows 1–2 are real records — do NOT
delete; verify `1251`'s phone is unchanged. Every delete returns `204`; record the ids in the
session report the way `72-UAT.md` does.

---

# Companies stress batch (2026-09-14) — feeds the suggest-contacts lane

File: `uat-stress-companies-2026-09-14.csv` (committed — public organisations only) — 36 rows, columns `Company Name, Website, Notes,
UAT Marker`. Run it through **enrich-records** in its companies form ("enrich/create these
companies", the skill builds `{"companies": [{"name","domain"}]}` from the table; domain is
mandatory). When the batch settles the assistant offers **suggest-contacts** for every company
with nobody named — that is the lane this file exists to exercise.

| Rows | Shape | Expected |
| --- | --- | --- |
| 1–6 | ATC, HRNSW, MRC, BRC, Perth Racing, Racing Victoria — already in the portal | **matched, never recreated**. ATC/MRC/BRC match by domain. HRNSW (`www.harnessmediacentre.com.au`), Perth Racing and Racing Victoria are held under domains that differ from the CSV, so all three must fall through to the exact-NAME match (exec `11922` precedent) — the snapshot did not see them by domain |
| 7–25 | Real ANZ racing bodies and clubs with public websites — snapshot 2026-09-15 found 9 of these already in the portal (Hawkesbury, Newcastle JC, GCTC, SCTC, Darwin, Tasracing, HRV, RWWA) plus Moonee Valley from row 32; the rest are creates | **created** (armed) and ICP-scored; then suggest-contacts crawls each site's about/board/team pages. Verify a domain live before blaming the lane — a few are best-effort (`gctc.com.au`, `sctc.com.au`, `aucklandracing.co.nz`) |
| 26 | Sky Racing | broadcaster / content producer — no veto |
| 27 | Tabcorp | gambling operator — graduated deduction, no hard veto |
| 28 | Daktronics | hardware vendor AND non-ANZ — both hard vetoes, Tier D |
| 29 | New York Racing Association | non-ANZ — hard veto, Tier D |
| 30 | Wagga Wagga Rowing Club (fictitious) | created if armed; a SECOND run of the contacts CSV then associates row 41/42 instead of holding them; suggest-contacts crawl fails cleanly (no site) |
| 31–32 | `https://www.vrc.com.au/`, `WWW.THEVALLEY.COM.AU` | normalised to `vrc.com.au` / `thevalley.com.au` before search |
| 33 | duplicate of row 7 | deduped to one |
| 34 | Gosford Race Club, no website | refused by name in the domain table; domain research offered (costed) |
| 35 | LinkedIn company page as website | **refused** — never created under `linkedin.com` |
| 36 | `gmail.com` as website | refused / flagged (freemail is not a company domain) |

Cost: company enrichment is the expensive lane (providers + Haiku + Sonnet per company, ~37 s
each at 2 records per POST → ~15 write POSTs for 30 companies). Lusha 2 credits/company.
Suggest-contacts spends only fetch budget until proposals are sent as contacts (then normal
ingest cost). Budget roughly 40–60 n8n executions across the two files.

## Reset script — `scripts/uat_reset.py` (repo root)

Deletes only what the session created; pre-existing companies are protected by a snapshot
taken BEFORE the run. Restorable deletes (HubSpot recycle bin), `204` per record, JSON report
next to the CSV. Nothing is deleted without `--execute` AND `ALLOW_UAT_RESET=true`.

```
# 1. before the session — record which CSV domains already exist (protects ATC, HRNSW, …)
! set -a; . ./.env; set +a; python3 scripts/uat_reset.py --snapshot --companies-csv tests/stress-tests/uat-stress-companies-2026-09-14.csv

# 2. after the session — dry run (lists every contact/company it WOULD delete)
! set -a; . ./.env; set +a; python3 scripts/uat_reset.py --companies-csv tests/stress-tests/uat-stress-companies-2026-09-14.csv

# 3. execute
! set -a; . ./.env; set +a; ALLOW_UAT_RESET=true python3 scripts/uat_reset.py --companies-csv tests/stress-tests/uat-stress-companies-2026-09-14.csv --execute
```

What it selects: contacts whose email local-part starts `uat.` or whose `lv_linkedin_url`
slug starts `uat-` (every fictitious row in the contacts CSV); companies from the CSV that
are NOT in the snapshot and were created at/after the snapshot time (`--since` overrides);
and contacts created since then that are associated with one of those companies (the real
people suggest-contacts found). Rows 1–2 of the contacts CSV (`1251`, Busteed) are never
selected — real emails, old `createdate`. Pass `--since <ISO>` to tighten the window. A company the run created under a domain the rule
refuses (freemail, social page) is invisible to the domain rule — name it with
`--extra-company-id <id>` (repeatable; still guarded by createdate). Stage B 2026-09-15 created
`288135240183` ("Country Racing Collective", domain `gmail.com`) this way.
