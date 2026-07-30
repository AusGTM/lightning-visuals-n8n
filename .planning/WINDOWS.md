---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 1
total_count: 1
last_updated: 2026-07-30T05:06:02.452Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 20 | deviation | n8n/code/lushaRequest.js |  | Plan 20-04 Task 2 Reuse (stored-id re-enrichment) not implemented: docs/LUSHA-V3-CONTRACT.md confirms the free path requires POST /v3/contacts/enrich {ids,reveal} (a different endpoint/body than lushaContactBody's search-and-enrich), and that endpoint's response envelope was never live-probed. Needs a follow-up Lusha probe before implementation. | fixed |  | 2026-07-30T04:30:31.257Z | 2026-07-30T05:06:02.452Z |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "20",
    "file": "n8n/code/lushaRequest.js",
    "line": null,
    "description": "Plan 20-04 Task 2 Reuse (stored-id re-enrichment) not implemented: docs/LUSHA-V3-CONTRACT.md confirms the free path requires POST /v3/contacts/enrich {ids,reveal} (a different endpoint/body than lushaContactBody's search-and-enrich), and that endpoint's response envelope was never live-probed. Needs a follow-up Lusha probe before implementation.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-07-30T04:30:31.257Z",
    "resolved_at": "2026-07-30T05:06:02.452Z"
  }
]
````
