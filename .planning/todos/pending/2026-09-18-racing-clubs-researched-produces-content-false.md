---
created: 2026-09-18T00:00:00.000Z
updated: 2026-09-18
title: "Racing clubs researched `lv_produces_content: false` with evidence at high confidence, firing a no_content veto on bodies that plausibly do produce content"
area: n8n-enrichment
severity: medium
kind: question
trigger: "next Stage B / enrich-records companies run: compare researched `produces_content` against the RUNBOOK's expected content producers"
owner: operator
files:
  - scripts/build_cloud_workflows.py
  - src/web_research.py
  - config/taxonomy.yaml
---

## Found during

Quick task 260918-32u, re-reading the Stage B executions of stress attempt 3 (run
`ca0537929b26401384f361902039ce7e`, executions 12526-12542) on 2026-09-18.

## What was observed

`Validate Research Output` parsed 18/18 research responses — nothing was lost to a parser.
Several of those parsed answers set `lv_produces_content: false`:

- **GRNSW, execution 12536** — `false` at confidence **92**, WITH evidence, and it survived
  TS-2. That took a `no_content` hard veto on a `governing_body_league`.
- **Perth Racing**, **Pakenham** and **Murray Bridge** researched `false` too.

## The question

Is `false` the right answer for a racing club or a governing body that streams or broadcasts
its own race meetings, and if not, what in the research prompt leads the model there? The
answers are the research model's own evidenced conclusions, not a parse loss and not a
pipeline defect — the veto fired on a value the model deliberately returned at high
confidence.

**No code in quick task 260918-32u touched the research prompt.** That task fixed the phantom
`research_failed` marker only (see
`.planning/todos/completed/2026-09-17-phantom-research-failed-marker-row.md`); it made no
change to `ENRICH_VALIDATE_RESEARCH`, the research request body, `src/web_research.py`, or the
taxonomy definitions that the prompt renders.

## What would close it

The next Stage B / `enrich-records` companies run: compare the researched
`produces_content` value per company against the RUNBOOK's expected content producers. If the
same bodies come back `false` again, this becomes a research-prompt defect with a named fix
(likely a taxonomy/prompt definition of what counts as producing content for a governing body
that licenses or commissions its broadcast rather than operating the camera). If they come
back `true`, the attempt-3 results were a one-off and this closes as a non-issue.
