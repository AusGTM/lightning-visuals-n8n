---
created: 2026-08-04T09:40:00.000Z
title: UAT 2.2 names two header aliases the column mapping does not support
area: n8n + operator-claude-plugin
severity: major
files:
  - config/column_mapping.yaml
  - n8n/code/columnMap.js
  - operator-claude-plugin/UAT.md
---

## Problem

Found by the operator walking UAT session 2 on plugin `0.7.3` — the first build where the preview
could predict header mapping at all (before it, `column_mapping.yaml` was unpackaged, so the
labels were always "unavailable" and this was invisible).

UAT 2.2 reads, verbatim:

> Give it a CSV or XLSX with messy headers (`E-mail Address`, `Ph.`) — Reads them without you
> renaming anything first

**Neither named example maps.** The alias table has `email address` and `e-mail`, but not
`e-mail address`; it has `phone`/`mobile`/`tel`, but not `ph.`. Also absent: `org.`,
`linkedin profile`. And `Full Name` cannot work at all — there is no name-splitter, by design.

Against `tests/samples/22-messy-headers.csv` (built from the criterion's own wording), 6 of 7
headers drop and every row would land `needs_review` carrying only a job title.

**The plugin behaved correctly** — it predicted the drop, itemised it per header, and refused to
present the file as send-ready. That is the system working. The defect is that the requirement and
the mapping disagree.

**The earlier 2.2 PASS was real but easier than the criterion.** It was granted against
`tests/fixtures/uploads/contacts.csv`, whose headers (`Email Address`, `Phone`, `Company`) all map.
Nobody tested the two aliases the criterion actually names.

**No drift between the two copies.** `n8n/code/columnMap.js` carries the same alias set as
`config/column_mapping.yaml`, so the preview's prediction is faithful to what the backend would do.
But the YAML is **not** a generator source for the JS (`build_cloud_workflows.py` does not
reference it) — they are two hand-maintained copies that currently agree. Worth a pin.

## Solution

TBD — a decision, not a defect fix, because both directions are defensible:

1. **Widen the aliases.** Add `e-mail address`, `ph.`, `org.`, `linkedin profile` (and consider
   `mobile phone`, `work email`, `company name`). Makes the criterion true as written. **Cost:** it
   is a BACKEND change — `columnMap.js` must change with the YAML or they drift, and the workflows
   need a disarmed redeploy + bounce to take effect. Out of client-only scope; a small sealed-phase
   amendment.
2. **Amend the criterion.** Change 2.2's examples to aliases the mapping actually supports, and
   record why. Cheapest, and arguably honest: the plugin's job is to *predict* the backend's
   mapping, not to expand it. But it weakens a requirement to match the implementation, which this
   milestone has been careful not to do silently.
3. **Both, split:** widen the obvious near-misses (`e-mail address`, `org.`) where the operator's
   intent is unambiguous, and amend the criterion for the genuinely ambiguous ones (`Ph.` could be
   phone or a photo column; `Full Name` needs a splitter that does not exist).

**Whichever lands, pin the two alias copies against each other** — a test asserting
`column_mapping.yaml`'s alias map equals `columnMap.js`'s. They agree today by luck, not by
construction, and a widened YAML with an un-widened JS would make the preview lie about the
backend in the confident direction.
