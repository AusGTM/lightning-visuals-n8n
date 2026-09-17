#!/bin/sh
# One command, whole demo, clean assets: companies + contacts from demo-combined.csv.
# Run from this folder after the pre-flight in DEMO-RUNBOOK.md (plugin installed and
# configured, snapshot taken). Starts an interactive Claude session so cost-guard,
# write-grant and permission prompts can still be answered on camera.
cd "$(dirname "$0")" || exit 1
exec claude "Run the recorded demo end to end per DEMO-RUNBOOK.md using ONE file, demo-combined.csv in this folder. \
Decisions are pre-made — do not ask me between steps; stop only if anything reads armed at a step boundary or a runbook stop condition fires. \
Write autonomy is on: open the write grant by name for each batch, arm/dispatch/disarm yourself, and never paste a Webhook Trigger runData block anywhere. \
\
Baseline: 'What's the backend doing?' — record the latest execution id and the provider balances. \
\
Step 1 — companies: the six rows of demo-combined.csv that carry a Website and no person are the companies batch (enrich-records, companies form, name + domain). Accept every domain as given; no domain research is needed. Cost guard: yes. Write grant: yes. Pass: Australian Turf Club and Brisbane Racing Club MATCH their existing portal records and are never recreated; the other four are created and scored (org type, region, produces-content, ICP tier). List every created company id. \
\
Step 2 — people at the new companies: accept the suggest-contacts offer for every company with nobody named, default 2 per company, default role list. Send the ready proposals under the same grant discipline; held proposals stay held. Verify two created people by re-read (associated to the right company, email domain equals the company domain or held with the mismatch reason). \
\
Step 3 — contacts: give the WHOLE of demo-combined.csv to enrich-before-ingest, unchanged (Organisation maps to company; Website is an unmapped header and is dropped). Providers ON. Expected: the six company-only rows (no First Name/Surname) are REFUSED by name with the identity reason at no provider cost; the eight people are fictitious and carry no email, so they are matched against HubSpot (none found), the waterfall returns NOT_FOUND at no Lusha cost, and every one is HELD as 'nothing found' with a reason naming the person — nothing is created. That is a PASS; do not create them. If a row I appended for a real person reveals an email, it may land under the grant. \
\
Step 4 — 'What's the backend doing?' (execution delta since baseline, nothing running long, nothing armed, balances numeric) then 'What needs review?' — list every held item with its reason; approve nothing, reject nothing, leave the queue as is. \
\
Close-out: per step the run id, execution id range, counts (matched / created / held / refused), every created company and contact id (I need them for the reset), and a disarm check at each boundary. Do NOT run reset.py — that is mine."
