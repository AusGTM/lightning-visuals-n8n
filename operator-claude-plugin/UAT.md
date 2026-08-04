# Operator UAT — v0.6

**For the operator, in Claude Desktop.** No terminal, no n8n, no HubSpot admin. Every step is
something you say; the pass criteria are things you can see.

**Cost:** sessions 1–4, 6, 7 and 8 cost **nothing** — the plugin is disarmed by default and every
dispatch stops at a preview you can abort (DISPATCH-03, PREVIEW-04). Only session 5 spends
money, and it says so before it does. (In session 7, only ask to "run now" a workflow the
steps name as safe — running the enrichment workflow spends provider credits.)

**If any step fails, stop and report it.** A step that "sort of worked" is a fail — write down
what you saw instead. The point of UAT is to find the gap between what was promised and what
arrived, not to get a clean sheet.

---

## Session 0 — install and set up

| # | Do | Pass when |
|---|---|---|
| 0.1 | `/plugin marketplace add AusGTM/lightning-visuals-n8n` then `/plugin install operator-claude-plugin@lightning-visuals-operator` | It installs without you editing any file or knowing any path |
| 0.2 | `/operator-claude-plugin:initialize` | It tells you the **full path** to your settings file and names which values you still need |
| 0.3 | Let it put the template in place, then fill in `n8n_url` and `webhook_secret` from your n8n admin | It never asks you to type a secret **into the chat** |
| 0.4 | `/operator-claude-plugin:initialize` again | Says setup is complete and changes nothing. Running it twice is safe |

**Fail if:** it says you are set up while a value is still the template placeholder, or it asks
you to paste a secret into the conversation.

*Covers PLUGIN-01, PLUGIN-02, PLUGIN-03.*

---

## Session 1 — the plugin refuses safely when it cannot work

Do this **before** the happy path. A tool that fails badly is worse than one that fails loudly.

| # | Do | Pass when |
|---|---|---|
| 1.1 | Temporarily blank `webhook_secret` in the settings file, then ask to upload contacts | It refuses in **plain language**, names the missing setting, and does **not** show a stack trace |
| 1.2 | Same state — ask for backend status | Status still works. A missing upload secret must not break the status answer |
| 1.3 | Restore the secret | Both work again |

**Fail if:** it says the plugin is "broken" or refuses everything when only one setting is
missing. Over-refusing is a defect (PLUGIN-03).

---

## Session 2 — getting contacts in, five ways

Each is a fresh message. Use your own data or anything realistic.

| # | Do | Pass when |
|---|---|---|
| 2.1 | Paste an email signature or a few lines of prose with names and companies | Rows come back, and it says **where each value came from** |
| 2.2 | Give it a CSV or XLSX with messy headers (`E-mail Address`, `Ph.`) | Reads them without you renaming anything first |
| 2.3 | Give it JSON in some other shape | Translated into contact rows |
| 2.4 | Give it a public URL | Contact/company data extracted from the page |
| 2.5 | Paste one or more screenshots of a page | Rows extracted from the image, same provenance rules |
| 2.6 | Give it something unreadable — an empty file, a PDF of a photo | A **clear, actionable** error. Never a silent drop, never zero rows with no explanation |
| 2.7 | Look at any row where a field was absent in your source | It is **empty** — not guessed, not filled from the company name |

**Fail if:** any value appears that was not in your input. Invention is the most serious defect
in this list (STRUCT-04).

*Covers INGEST-01/02/03/05/06/07, STRUCT-03/04.*

---

## Session 3 — the preview, and aborting from it

| # | Do | Pass when |
|---|---|---|
| 3.1 | Take any batch to the point of sending | You see the **exact payload** and the **row count** before anything is sent |
| 3.2 | Read the cost line | An estimated **provider-credit and token cost**, with the date its rates were measured |
| 3.3 | Try a batch bigger than the chunk size | It shows you the **chunking plan** before sending |
| 3.4 | Say no / abort | **Nothing is sent and nothing is spent.** Ask for backend status afterwards to confirm no run started |
| 3.5 | Check what it says about credits | If a balance is unknown it says **unknown** — never `0`, never "healthy" |

**Fail if:** aborting still costs something, or an unknown balance renders as zero.

*Covers PREVIEW-01/02/03/04, STATUS-06.*

---

## Session 4 — asking what the backend is doing

| # | Do | Pass when |
|---|---|---|
| 4.1 | "What's the backend doing?" | **One plain-language answer.** No JSON, no node names, no n8n jargon |
| 4.2 | Ask about a run that failed | The real cause **translated** — not a raw error string |
| 4.3 | Ask for the dashboard | It publishes, and shows the **same** workflows and counts as the text answer |
| 4.4 | Ask for a refresh in the same conversation | **Same URL**, timestamp moves forward |
| 4.5 | **Brand-new conversation** — ask for the dashboard again | Lands on the **same URL**, not a second one |
| 4.6 | Anything the backend could not read | Shows as **unknown**, never zero |

**Fail if:** step 4.5 mints a new URL. That is the one step that proves the dashboard survives
a session, and it is why the state file exists.

*Covers STATUS-01/02/05/06 — this is RB-4.*

---

## Session 5 — the one that spends money

**Read the preview before approving. This is the only session with a real cost.**

| # | Do | Pass when |
|---|---|---|
| 5.1 | Take a **small** batch (2–3 rows) to preview and approve it | It required an explicit approval — a live send is never the default (DISPATCH-03) |
| 5.2 | Watch what comes back | **Per-record outcome**: accepted, matched, created, failed — row by row |
| 5.3 | If any row failed | The **failing rows are identified**, and you are told what to do about them |
| 5.4 | If the run is still going | It says so and shows partial results — it does not hang or pretend to be done |
| 5.5 | Check the records in HubSpot | They match what the report said |

**Fail if:** the report is a summary count with no per-row detail, or a failure is reported as
a success.

*Covers DISPATCH-01/03/04, REPORT-01/03.*

---

## Session 6 — the review queue

| # | Do | Pass when |
|---|---|---|
| 6.1 | Ask to see records waiting on a human | Each one's conflict is in **plain language** — what disagrees, and what each source said |
| 6.2 | Look for a HubSpot link | Present if the portal id is configured; if not, it says the link is missing rather than guessing a URL |
| 6.3 | Resolve one conversationally | It asks for a **separate confirmation** before writing back — approving a review is not covered by any earlier approval |
| 6.4 | Reject one | The rejection **reason is recorded** and the record **stays in the queue** |
| 6.5 | After an approve lands | It stamps that a **human** made it, with timestamp and your reason — and the record's history still shows what the machine had said before you overrode it |
| 6.6 | If a held value includes a **protected** field (e.g. `domain`) | It is **labelled protected and withheld** — the approve applies the other fields and says which one it withheld. The protected field never changes |
| 6.7 | If the backend refuses | The refusal **names the gate** — "not on the allowlist", "not a value HubSpot accepts" — never a bare failure or an empty answer |

**Fail if:** a review writes back without its own confirmation step (REVIEW-03).

**Note:** an approve that actually lands needs the backend opened by an admin first (a
deploy-time write flag plus a record allowlist, and an environment variable on your machine).
Without that, steps 6.1–6.3 and 6.7 still work — the preview shows the exact write and the
submit refuses naming what is closed. That refusal is a **pass**, not a fail.

*Covers REVIEW-01/02/03/04/05 — proven live 2026-08-04 (RB-9 close).*

---

## Session 7 — controlling the backend

| # | Do | Pass when |
|---|---|---|
| 7.1 | Ask to turn a scheduled workflow **off**, then **on** again | Each change asks for its own confirmation first, then reports the new state **read back from the backend**, not assumed |
| 7.2 | Ask to change a schedule's cadence | You see current cadence and proposed cadence **before** confirming; afterwards the new cadence is read back |
| 7.3 | Ask for something outside the allowlist (e.g. "edit the workflow's nodes", "change a credential") | It refuses and says that is an **admin task**, not a plugin action |
| 7.4 | Ask to arm live writes without the admin having opened the backend | It refuses **naming the closed gate** and who opens it — it never pretends to be armed |
| 7.5 | After any mutation | Backend status reflects it — the two answers agree |

**Fail if:** a mutation happens without its own confirmation, or a state change is reported
from memory rather than read back.

*Covers CONTROL-01…07 — the armed dispatch path itself was proven in RB-7 (admin-audited).*

---

## Session 8 — notices

| # | Do | Pass when |
|---|---|---|
| 8.1 | After approving a send (session 5), stay in the conversation | When the run settles it **reports itself** — you did not have to ask |
| 8.2 | Run the sweep on demand (`/operator-claude-plugin:backend-sweep`) | It reports **only what needs a human** — or says the backend is healthy and reports nothing else |
| 8.3 | Ask what the unattended schedule would have said | Same answer as 8.2 — the on-demand run is exactly what the next unattended fire would report |

**Unattended firing is an admin install** (a `cron`/`launchd` entry per
`skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` — terminal commands, so not part of *operator*
UAT). If notices are expected but never arrive, the first thing to check is whether that
schedule was ever installed — an uninstalled trigger is silent; an installed-but-broken one
now announces itself.

*Covers NOTICE-01…05 — the unattended path was proven under real cron 2026-08-03 (RB-8).*

---

## Reporting your results

For each session, one line: **pass**, or **what you saw instead**. Include the step number.

The three that matter most, in order:

1. **Any invented value** (2.7) — a field that was not in your input.
2. **A failure reported as success** (5.2–5.3, 6.3).
3. **The dashboard minting a second URL** (4.5).

A "small" thing you noticed and dismissed is worth reporting. Three real defects in this
milestone were found exactly that way — by someone walking the steps and saying "that looked
odd" rather than assuming it was meant to be like that.
