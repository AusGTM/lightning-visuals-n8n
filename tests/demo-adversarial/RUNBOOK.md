# Short demo — main path, adversarial fixtures (~10 min)

Two files, two steps, one close-out. Shows the main path only: **companies land, people are
gated.** Edge cases are exercised only where the fixtures force them (three sabotaged website
cells, three rows with no identity) — each is one line of talk track, not an act.

Self-contained: this folder plus the **installed plugin**. Nothing reads the source repository
during the run — the plugin resolves every config it needs from its own shipped copies
(since 0.50.2 there is no repo fallback left, `preview.py` included).

| File | Purpose |
| --- | --- |
| `demo-companies-adversarial.csv` | 8 racing organisations; website column sabotaged (3 blank, 1 LinkedIn page) |
| `demo-contacts-mixed-adversarial.csv` | 8 fictitious people; 3 rows carry no usable identity; no emails anywhere |
| `run.command` | double-click: one Claude session, decisions pre-made, both steps + close-out |
| `RUNBOOK.md` | this file |

Cleanup uses `../demo-run/reset.py` (not duplicated here).

## Before (operator, once)

1. Install the plugin on this machine: run `bash install.sh` inside `operator-claude-plugin/install/`
   from the install bundle your admin gave you (or follow `USAGE.md` steps 1–5). Restart
   Claude Code. Say **"Is the plugin configured?"** → *already set up*.
   `allow_write_grants: true` must be set in the settings file by the admin.
2. Record the starting line (terminal, this folder). Companies already in the portal are
   protected from cleanup by the snapshot:
   ```
   export HUBSPOT_PRIVATE_APP_TOKEN=<from the HubSpot admin — terminal only>
   python3 ../demo-run/reset.py --snapshot --companies-csv demo-companies-adversarial.csv
   ```
   Expect Australian Turf Club and Brisbane Racing Club at least.
3. Hide the terminal. Everything else is said to Claude.

## Run

Double-click `run.command` (or say the two steps yourself, below). Answer the cost-guard,
write-grant and permission prompts when they appear — those are the only questions.

### Step 1 — companies (~4 min)

Say: **"Enrich or create these companies"** → `demo-companies-adversarial.csv`.

Talk track: the website table. Four domains confirmed from the file. Brisbane Racing Club is
blank → the assistant proposes `brc.com.au` (the portal's own record). NZ Thoroughbred Racing and
Gosford Race Club are blank → one research line each, with the source. Illawarra Turf Club gave a
LinkedIn page → refused as a website. Say **"accept the proposals and the research, decline
Illawarra"**. Cost guard: yes. Write grant: yes.

Result to point at: ATC and BRC **matched, never recreated**; Pakenham, Murray Bridge, Sky Racing,
NZTR, Gosford **created and scored** (org type, region, content signals, ICP tier); Illawarra
**held for review** with a reason naming what to supply. Note the two researched-domain company
ids from the report for cleanup.

Skip the "Who's at these companies?" offer (say no) — keeps the demo short.

### Step 2 — contacts (~4 min)

Say: **"Enrich these contacts before uploading them"** → `demo-contacts-mixed-adversarial.csv`.

Talk track: the preview accounts for all 8 rows. Rows 5 (no name), 7 (first name only) and 8
(name, no company) are **refused** at no cost — a row needs an email, or a LinkedIn URL, or
first + last name + company. The other five are matched against HubSpot (none found), the
waterfall returns NOT_FOUND at no Lusha cost, and all five are **held as "nothing found"**, by
name. Nothing is written. That is the gate working: a person the system cannot confirm never
reaches the CRM. One yes for spend; there is nothing to grant.

### Close-out (~1 min)

Say: **"What's the backend doing?"** — nothing running long, nothing armed, execution delta since
the starting line. Then **"What needs review?"** — the Illawarra hold and the five held people,
each with its reason. Leave the queue as is.

## After — cleanup (terminal, token still exported)

```
python3 ../demo-run/reset.py --companies-csv demo-companies-adversarial.csv \
  --contacts-csv demo-contacts-mixed-adversarial.csv \
  --extra-company-id <NZTR id> --extra-company-id <Gosford id>
```

Dry run first: the list must hold only the five demo-created companies and no pre-existing
record. Then the same line with `ALLOW_UAT_RESET=true` first and `--execute` last. Every delete
prints `204` (restorable in HubSpot). Enrichment written onto ATC/BRC is real enrichment on real
records and is not undone.
