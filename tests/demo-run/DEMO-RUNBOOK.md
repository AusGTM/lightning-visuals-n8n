# Operator demo — HubSpot enrichment plugin (recorded run)

Self-contained: everything needed is this folder plus an installed plugin. No project repo, no
`.env`, no terminal knowledge during the demo — the operator talks to Claude in plain words. The
only terminal steps are install (once) and cleanup (after).

What the recording shows, in four acts (~25 min):

1. **Companies in, people out** — load a company spreadsheet, watch existing companies match and
   new ones get created and scored, then let the assistant find who works at the new ones.
2. **Mixed-quality contact list** — load a spreadsheet where some rows are complete and some are
   an email or a name only; watch the waterfall enrich what it can, create what it may, and hold
   what it cannot resolve — by name, with a reason.
3. **Not a spreadsheet** — a screenshot of an attendee list, then a text file of URLs. Same
   preview, same gates.
4. **What the backend is doing**, and the review queue.

Assets in this folder:

| File | Used in |
| --- | --- |
| `demo-companies.csv` | Act 1 — 8 companies: 2 already in HubSpot, 4 new real organisations, 1 with no website, 1 with a LinkedIn page instead of a website |
| `demo-contacts-mixed.csv` | Act 2 — 8 fictitious people, dense to sparse: full rows, email-only, name+company, LinkedIn-only, name-only |
| `demo-attendees-screenshot.png` | Act 3 — an image of an attendee table (5 people, one with a personal email, one with none) |
| `demo-urls.txt` | Act 3 — one company website URL and two LinkedIn profile URLs, nothing else |
| `reset.py` | Cleanup — removes everything the demo created, nothing that existed before |

Every fictitious person's email starts `demo.` and every fictitious LinkedIn slug starts `demo-`
— that is how cleanup finds them. Companies are real public organisations; the demo may create up
to 5 of them and cleanup removes exactly those.

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
Club at least; anything else already present simply becomes a "match" in Act 1 instead of a
"create".

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
  rest"**.
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
- Approve the ready proposals. They go in through the same gates as a spreadsheet row.

## Act 2 — mixed-quality contact list (~7 min)

Say: **"Enrich these contacts before uploading them"** and give `demo-contacts-mixed.csv`.

Talk track:
- **Preview first, always**: 8 rows, how each column mapped (note `Mobile` → Mobile Phone, `Tel`
  → Phone), which rows are usable. A row needs an email, or a LinkedIn URL, or first + last name +
  company. Row 7 (*Kofi Tuilagi*, name only) is called out as review — matching the wrong person
  is worse than matching nobody.
- **Match, then enrich, then write**: each usable row is checked against HubSpot, the waterfall
  (ZoomInfo → Apollo → Lusha) fills gaps, and the enriched preview shows what will land. Fictitious
  people return "not found" from the providers at no cost — say so on camera; to show a real
  reveal, append one row for a real person the client is entitled to enrich.
- One yes for spend, one for the write (or one grant covering both). Rows the system is confident
  about go through; the rest come back as **one review list**, named, with reasons.
- Open one created contact in HubSpot: company association, mobile in the Mobile field, LinkedIn
  in both LinkedIn fields, city/state/country.

## Act 3 — not a spreadsheet (~5 min)

**Screenshot.** Drag `demo-attendees-screenshot.png` into the chat and say **"Load these
contacts into HubSpot."** The assistant extracts a contact table from the image, shows the same
preview (5 rows: one has a personal Gmail — flagged, its company cannot be resolved from that
domain; one has no email — held), and proceeds through the same gates.

**URLs only.** Paste the contents of `demo-urls.txt` and say **"Load whoever you can find
here."** Two LinkedIn URLs are enough identity on their own — no company needed; the website URL
is read for the people on it. Same preview, same gates.

## Act 4 — status and review (~3 min)

- **"What's the backend doing?"** — workflows, what ran, execution count since the starting
  line, credits where readable, nothing armed.
- **"What needs review?"** — the held rows from Acts 2–3, one at a time: the conflict, what each
  source says, the exact write approval would make. Approve one, reject one with a reason.

---

## After recording — cleanup (operator, ~3 min)

Terminal again, same folder, token still exported:

```
python3 reset.py --companies-csv demo-companies.csv
```

Dry run. Read the list: it must contain only companies created during the demo and contacts whose
email starts `demo.` or LinkedIn slug `demo-`, plus any real people suggest-contacts created at
those companies. It must not list any pre-existing record. Then:

```
ALLOW_UAT_RESET=true python3 reset.py --companies-csv demo-companies.csv --execute
```

Every delete prints `204` (restorable in HubSpot). Two cases need an extra flag:
- a company created from a **researched** website (Gosford → e.g. `theentertainmentgrounds.com.au`,
  not in the CSV): add `--extra-company-id <id>` with the id from the Act 1 report;
- a contact created from the **screenshot's Gmail row** has no company; it is still caught by the
  `demo.` marker.

Enrichment written onto pre-existing companies is real enrichment on real records and is not
undone; HubSpot property history keeps prior values.

---

## Adapting to another portal

- Replace the two "already in HubSpot" companies in `demo-companies.csv` with two the target
  portal holds; keep the domains exactly as the portal stores them (a `www.` prefix or a
  different TLD makes the match fall back to exact name, and a name variant then creates a
  duplicate — a known gap at time of writing).
- Keep every fictitious email under a `demo.` local part and every LinkedIn slug under `demo-`;
  `reset.py` also accepts `uat.` / `uat-`. Change the marker only if you also change
  `is_uat_contact()` in `reset.py`.
- Batches over ~20 rows: the contact-upload lane throttles its HubSpot lookups to 4 requests per
  second, so a 48-row file takes ~45 s after the immediate acknowledgement. Keep demo files small.
