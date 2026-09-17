#!/bin/sh
# One command, whole demo, adversarial assets: demo-companies-adversarial.csv then
# demo-contacts-mixed-adversarial.csv. Exercises the refusals and holds. Run from this
# folder after the pre-flight in DEMO-RUNBOOK.md. Interactive session, same reason as demo-e2e.sh.
cd "$(dirname "$0")" || exit 1
exec claude "Run the ADVERSARIAL recorded demo end to end per DEMO-RUNBOOK.md using two files in this folder: demo-companies-adversarial.csv (companies) then demo-contacts-mixed-adversarial.csv (contacts). \
Decisions are pre-made — do not ask me between steps; stop only if anything reads armed at a step boundary or a runbook stop condition fires. \
Write autonomy is on: open the write grant by name for each batch, arm/dispatch/disarm yourself, and never paste a Webhook Trigger runData block anywhere. \
\
Baseline: 'What's the backend doing?' — record the latest execution id and the provider balances. \
\
Step 1 — companies (enrich-records, companies form) from demo-companies-adversarial.csv. Domain table decisions: Australian Turf Club, Pakenham Racing Club, Murray Bridge Racing Club, Sky Racing — accept the domains as given. Brisbane Racing Club has no website — propose brc.com.au (it is the portal's own record) and accept it. New Zealand Thoroughbred Racing and Gosford Race Club have no website — research both; accept the research line and its cost. Illawarra Turf Club gave a LinkedIn page — it must be REFUSED as a website; decline it to name-only. Cost guard: yes. Write grant: yes. Pass: ATC and BRC matched, never recreated; Pakenham, Murray Bridge, Sky Racing, NZTR and Gosford created and scored (the last two under researched domains — record which); Illawarra HELD for review with a reason that names the match outcome, 'no domain', and what to supply — never created under linkedin.com, never a 400, never silently skipped. List every created company id and its domain. \
\
Step 2 — people: accept the suggest-contacts offer for the created companies, default 2 per company; send the ready proposals; held stay held. \
\
Step 3 — contacts (enrich-before-ingest) from demo-contacts-mixed-adversarial.csv, providers ON. The preview must account for all 8 rows: rows 5 (organisation + title, no name), 7 (first name only) and 8 (Kofi Tuilagi, name with no company) REFUSED by name with the identity reason (email, or LinkedIn URL, or first + last name + company) and no provider call; rows 2, 3, 4, 6 and 9 (name + company, no email) matched (none found), waterfall NOT_FOUND at no Lusha cost, then HELD as 'nothing found' with a reason each. Nothing is created — that is a PASS; do not create any of them. \
\
Step 4 — 'What's the backend doing?' (execution delta, nothing running long, nothing armed) then 'What needs review?' — the Illawarra company hold and the held contact rows: show each with its reason; reject the Illawarra hold with the reason 'demo: LinkedIn page is not a website'; leave the rest. \
\
Close-out: per step the run id, execution id range, counts (matched / created / held / refused), every created company id and domain (I need the researched ones for the reset's --extra-company-id), and a disarm check at each boundary. Do NOT run reset.py — that is mine."
