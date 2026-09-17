#!/bin/sh
# Short adversarial demo, main path only: companies then contacts, from this folder.
# Run after the pre-flight in RUNBOOK.md (plugin installed + configured, snapshot taken).
# Interactive session so cost-guard, write-grant and permission prompts can be answered.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
exec claude "Run the SHORT recorded demo per RUNBOOK.md in this folder — main path only, two steps, no edge-case exploring. Use the installed operator plugin skills; never read or run anything from a source repository. \
Decisions are pre-made — do not ask me between steps; stop only if anything reads armed at a step boundary. \
Write autonomy is on: open the write grant by name for the companies batch, arm/dispatch/disarm yourself, and never paste a Webhook Trigger runData block anywhere. \
\
Step 1 — companies (enrich-records, companies form) from demo-companies-adversarial.csv. Domain table: Australian Turf Club, Pakenham Racing Club, Murray Bridge Racing Club, Sky Racing — accept as given. Brisbane Racing Club is blank — propose brc.com.au and accept it. New Zealand Thoroughbred Racing and Gosford Race Club are blank — research both, accept the research line and its cost. Illawarra Turf Club gave a LinkedIn page — refuse it as a website and decline to name-only. Cost guard: yes. Write grant: yes. Expected: ATC and BRC matched (never recreated); Pakenham, Murray Bridge, Sky Racing, NZTR, Gosford created and scored; Illawarra held for review with a reason. Decline the suggest-contacts offer. List every created company id with its domain. \
\
Step 2 — contacts (enrich-before-ingest) from demo-contacts-mixed-adversarial.csv, providers ON. Expected: rows 5, 7 and 8 refused by name for missing identity at no provider cost; rows 2, 3, 4, 6 and 9 matched (none found), waterfall NOT_FOUND, held as 'nothing found' with a reason each. Nothing is created — that is a PASS. \
\
Close-out: 'What's the backend doing?' (execution delta, nothing running long, nothing armed) then 'What needs review?' (list each held item with its reason, change nothing). Report per step: run id, execution id range, counts (matched / created / held / refused), every created company id and domain, and a disarm check. Do NOT run reset.py — that is mine."
