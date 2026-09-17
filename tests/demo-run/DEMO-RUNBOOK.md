# Operator demo — HubSpot enrichment plugin (recorded run)

Self-contained: everything needed is this folder plus an installed plugin. No project repo, no
`.env`, no terminal knowledge during the demo — the operator talks to Claude in plain words. The
only terminal steps are install (once), the snapshot, and cleanup (after).

Two ways to run it:

- **Scripted, one command each** — `./demo-e2e.sh` (clean assets, one combined file) or
  `./demo-e2e-adversarial.sh` (the two adversarial files). Each starts one Claude session with
  every decision pre-made; you still answer the cost-guard, write-grant and permission prompts
  on camera. Same pre-flight and cleanup as below.
- **Narrated, act by act** — the acts below, said to Claude in plain words (~30 min).

## Read this before recording — what lands and what does not

**No demo asset carries an email address or a LinkedIn URL any more.** The earlier fictitious
`demo.…@` addresses and `demo-…` LinkedIn slugs broke real enrichment: a provider looked up by a
fake email finds nothing, and a fake address at a real company domain would have been written
into HubSpot. They are gone from every CSV, the screenshot and the URL list.

The consequence is deliberate and must be said on camera: **a fictitious person can never be
created.** The ingest lane resolves a contact by email; a name + company row is matched, enriched
and — when the waterfall returns NOT_FOUND, as it must for someone who does not exist — **held
as "nothing found"**, by name, with a reason. Companies land (they are real organisations);
people the assistant finds on those companies' own websites land (real people, real emails);
the spreadsheet people do not. That is the gate working, not a failure.

**Landing a contact from a spreadsheet** needs a real, enrichable person the client is entitled
to enrich: append one row (first name, surname, organisation, nothing else) to a copy of the
contacts file named `*-real*.csv` — that pattern is gitignored — and the waterfall reveals the
email (Lusha up to 7 credits for a rich reveal) and the row goes through. Never commit such a
file.

Assets in this folder:

| File | Used in |
| --- | --- |
| `demo-combined.csv` | Scripted clean run — 6 company rows (Organisation + Website, no person) then 8 contact rows (person + Organisation, no Website), one file for both lanes. The companies form is built from the 6 company rows; the contacts lane reads the whole file and refuses the 6 company-only rows by name (no identity) at no cost |
| `demo-companies.csv` | Act 1 — 8 companies: 2 already in HubSpot, 4 new real organisations, 1 with no website, 1 with a LinkedIn page instead of a website |
| `demo-contacts-mixed.csv` | Act 2 — 8 fictitious people, every row name + organisation, dense (phones, city) to sparse (name + org + title only) |
| `demo-companies-adversarial.csv` | Act 1b — same 8 companies with the website column sabotaged: 3 blank, 1 LinkedIn page |
| `demo-contacts-mixed-adversarial.csv` | Act 2b — 8 rows, 3 of them with no usable identity |
| `demo-attendees.csv` + `demo-attendees-screenshot.png` | Act 3 — an image of an attendee table (5 people, one with no organisation); the CSV is what the image was rendered from and is what cleanup reads |
| `demo-urls.txt` | Act 3 — two company website URLs, nothing else |
| `demo-e2e.sh`, `demo-e2e-adversarial.sh` | the one-command runs |
| `reset.py` | Cleanup — removes everything the demo created, nothing that existed before |

Cleanup finds companies by domain + creation time against a snapshot, and contacts by **name**
from the contacts CSVs (`--contacts-csv`, repeatable) plus creation time, plus anyone created at
a company the demo created. The old `demo.` / `demo-` marker rule is still in `reset.py` but
matches nothing in these assets.

---

## Before recording (operator, once, ~15 min)

### Install the plugin

```
claude plugin marketplace add https://github.com/AusGTM/lightning-visuals-n8n.git
claude plugin install operator-claude-plugin@lightning-visuals-operator
```

Restart Claude Code. In the new session say **"Set up the enrichment plugin"**. It names the
settings file path and the three values it needs from the n8n admin: `n8n_url`, `webhook_secret`,
`n8n_api_key`. Type them into that file, never into the chat. Say **"Is the plugin configured?"**
→ *already set up*. The admin must also have set `allow_write_grants: true` in the same file; the
demo writes to HubSpot only through the grant the operator opens on camera.

### Record the starting line

```
export HUBSPOT_PRIVATE_APP_TOKEN=<from the HubSpot admin — paste in the terminal only>
python3 reset.py --snapshot --companies-csv demo-companies.csv
```

Prints which demo companies already exist in the portal (they are protected from cleanup) and
writes `uat-reset-snapshot.json` beside the CSV. Expect Australian Turf Club and Brisbane Racing
Club at least; anything else already present simply becomes a "match" instead of a "create". The
same snapshot covers `demo-combined.csv` and the adversarial companies file — they name the
same domains.

Then, in Claude: **"What's the backend doing?"** — all workflows on, nothing running, writes off.
Note the latest execution id for the closing comparison.

Camera check: hide the terminal after this. Nothing else in the demo needs it.

---

## Act 1 — companies in, people out (~8 min)

Say: **"Enrich or create these companies"** and give `demo-companies.csv`.

Talk track while it works:
- The assistant shows a **website table**, one row per company. Six are confirmed from the file.
  *Gosford Race Club* has no website — the assistant proposes or researches one and shows where it
  came from. *Illawarra Turf Club* gave a LinkedIn page: refused as a website (a company filed
  under `linkedin.com` would poison every later match). Say **"decline Illawarra, accept the
  rest"** — it is then held for review, named, with what to supply.
- **Cost guard**: which providers, worst-case credits, model spend, how many requests. Say yes.
- **Write grant**: one yes covers the batch; every send arms writes for exactly its own records and
  disarms after. Say yes.
- Result: existing companies **enriched in place, never duplicated**; new ones **created and
  scored** — org type, region, content signals, ICP tier. Point at one created company in HubSpot.

Then the assistant offers: **"Who's at these companies?"** Say yes, keep the default of 2 people
per company.
- It reads each company's **own website first** (about / board / team pages) and shows the page
  next to every person it proposes. Someone found only on an industry site is **held**, never
  sent. Sites that refuse a crawl shut the fallback for that company — it says so.
- Approve the ready proposals. They go in through the same gates as a spreadsheet row. **These
  are the contacts that land in this demo** — real people from the companies' own pages.

## Act 1b — adversarial companies (~4 min)

Say: **"Enrich or create these companies"** and give `demo-companies-adversarial.csv`. Same
eight organisations, website column sabotaged. What each row exercises:

| Row | Company | Website cell | Expect |
| --- | --- | --- | --- |
| 2 | Australian Turf Club | as given | matched, not recreated |
| 3 | Brisbane Racing Club | **blank** | assistant proposes `brc.com.au`; accept → matched, not recreated |
| 4 | Pakenham Racing Club | as given | created (or matched if Act 1 ran first) |
| 5 | Murray Bridge Racing Club | as given | created / matched |
| 6 | New Zealand Thoroughbred Racing | **blank** | research line — accept → created under the researched domain, NZ geography, no veto |
| 7 | Sky Racing | as given | created / matched, broadcaster |
| 8 | Gosford Race Club | **blank** | research line — accept → created under the researched domain |
| 9 | Illawarra Turf Club | **LinkedIn page** | refused as a website; say **decline** → held for review naming the match outcome, "no domain", and what to supply — never created, never skipped |

Say **"accept the proposals and the research, decline Illawarra"**. Cost guard and grant as
before. Two companies created under researched domains are not in any CSV: note their ids from
the report for cleanup (`--extra-company-id`).

## Act 2 — contact list, name + organisation (~6 min)

Say: **"Enrich these contacts before uploading them"** and give `demo-contacts-mixed.csv`.

Talk track:
- **Preview first, always**: 8 rows, how each column mapped (note `Mobile` → Mobile Phone, `Tel`
  → Phone; the empty `E-mail Address` and `LinkedIn` columns map but carry nothing). A row needs
  an email, or a LinkedIn URL, or first + last name + company — every row here has the third.
- **Match, then enrich, then hold**: each row is checked against HubSpot, the waterfall
  (ZoomInfo → Apollo → Lusha) is asked, and every fictitious person comes back NOT_FOUND at no
  cost — say so on camera. The enriched preview then shows all 8 **held as "nothing found"**, by
  name, with the reason. Nothing is written. This is the point of the act: a person the system
  cannot confirm never reaches the CRM.
- One yes for spend. There is nothing to grant. To show a row going through, use a `*-real*.csv`
  copy with one real person appended (see the top of this file).

## Act 2b — adversarial contact list (~4 min)

Say: **"Enrich these contacts before uploading them"** and give
`demo-contacts-mixed-adversarial.csv`. What each row exercises:

| Row | Cells | Expect |
| --- | --- | --- |
| 2 | Priya Whitcombe, ATC, title, tel, mobile, city/state/country | name + company → matched (none), NOT_FOUND, held "nothing found" |
| 3 | Tomas Nakamura, BRC, tel + mobile, **no title** | same; `0439 …` normalised to `+61 …` in the preview |
| 4 | Ngaire Delacroix, Pakenham, title | held "nothing found" |
| 5 | **no name** — organisation + title only | **refused** by name at the match step: no identity (the reason names the three ways to fix it); no provider call |
| 6 | Mei Oyelaran, Sky Racing, title | held "nothing found" |
| 7 | **first name only** | **refused**: no identity |
| 8 | Kofi Tuilagi, **no organisation** | **refused**: a name without a company is not an identity either |
| 9 | Ines Castellano, NZTR, Wellington, **no state** | held "nothing found" |

Every row is accounted for; none is written; the three refusals never cost a provider call.

## Act 3 — not a spreadsheet (~4 min)

**Screenshot.** Drag `demo-attendees-screenshot.png` into the chat and say **"Load these
contacts into HubSpot."** The assistant extracts a contact table from the image and shows the
same preview: 5 rows, name + organisation + role, no emails; *Zara Rangi* has no organisation
and is called out. Same match → enrich → hold path as Act 2: fictitious, so held by name.

**URLs only.** Paste the contents of `demo-urls.txt` and say **"Load whoever you can find
here."** Two company website URLs: the assistant reads each site for the people on it, proposes
them with the source page beside each, and they go through the same gates — real people, so
these can land.

## Act 4 — status and review (~3 min)

- **"What's the backend doing?"** — workflows, what ran, execution count since the starting
  line, credits where readable, nothing armed.
- **"What needs review?"** — the Illawarra company hold and the held rows from Acts 2–3, one at
  a time: what each source said and the exact write approval would make. Reject Illawarra with
  a reason; leave the rest.

---

## After recording — cleanup (operator, ~3 min)

Terminal again, same folder, token still exported:

```
python3 reset.py --companies-csv demo-companies.csv \
  --contacts-csv demo-contacts-mixed.csv --contacts-csv demo-contacts-mixed-adversarial.csv \
  --contacts-csv demo-attendees.csv \
  --extra-company-id <NZTR id> --extra-company-id <Gosford id>
```

Dry run. Read the list: it must contain only companies created during the demo (by domain from
the CSV, or by the ids you passed) and contacts that are either named in a contacts CSV or were
created at one of those companies since the snapshot. It must not list any pre-existing record.
Then the same line again, `ALLOW_UAT_RESET=true` first and `--execute` last:

```
ALLOW_UAT_RESET=true python3 reset.py --companies-csv demo-companies.csv \
  --contacts-csv demo-contacts-mixed.csv --contacts-csv demo-contacts-mixed-adversarial.csv \
  --contacts-csv demo-attendees.csv \
  --extra-company-id <NZTR id> --extra-company-id <Gosford id> --execute
```

Every delete prints `204` (restorable in HubSpot). Notes:
- `--companies-csv` accepts `demo-combined.csv` too (same Website column). Pass whichever file
  the run used; the domains are the same.
- a company created from a **researched** website is reachable by the domain rule only if the
  researched domain equals the CSV's (`nzracing.co.nz` is in the CSVs; Gosford's is not).
  When it differs, pass the id with `--extra-company-id`, from the run's report;
- a `*-real*.csv` file you appended a real person to: pass it as another `--contacts-csv` if that
  person was created and should go; leave it out if the client keeps them.

Enrichment written onto pre-existing companies is real enrichment on real records and is not
undone; HubSpot property history keeps prior values.

---

## Adapting to another portal

- Replace the two "already in HubSpot" companies in the companies CSVs with two the target
  portal holds; keep the domains exactly as the portal stores them (a `www.` prefix or a
  different TLD makes the match fall back to exact name, and a name variant then creates a
  duplicate — a known gap at time of writing).
- Fictitious people are found by name at cleanup: keep first name + surname on every fictitious
  row you add, and pass every contacts CSV to `reset.py --contacts-csv`. Real surnames at a real
  company are fine — the creation-time guard keeps a namesake who predates the snapshot safe.
- Regenerate the screenshot from `demo-attendees.csv` if you change the attendees (any table
  renderer will do; keep Name / Organisation / Role as the columns).
- Batches over ~20 rows: the contact-upload lane throttles its HubSpot lookups to 4 requests per
  second, so a 48-row file takes ~45 s after the immediate acknowledgement. Keep demo files small.
