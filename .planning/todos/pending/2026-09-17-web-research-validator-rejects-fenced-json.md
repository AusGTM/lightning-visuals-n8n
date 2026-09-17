---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-17
title: Deployed research validator (ENRICH_VALIDATE_RESEARCH / "Validate Research Output" node) does not strip a ```json fence, so fenced Claude Web Research output is discarded as research_failed
area: n8n-enrichment
severity: medium
kind: defect
evidence: "Stage B live run (73-UAT.md § Attempt 3, executions 12526-12542, run_id ca0537929b26401384f361902039ce7e): ~12/18 companies' web research completed (haiku-4.5, end_turn, valid JSON with evidence URLs) but were discarded as research_failed because the response was wrapped in a ```json fence; the deployed JS validator (scripts/build_cloud_workflows.py::ENRICH_VALIDATE_RESEARCH, node 'Validate Research Output') has no fence-stripping step, unlike src/web_research.py::_extract_json which already strips ```json / ``` fences before json.loads"
files:
  - scripts/build_cloud_workflows.py
  - src/web_research.py
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage B of stress attempt 3, 2026-09-17/18.

## What happened

`Claude Web Research` (the HTTP node calling haiku-4.5) returned valid, well-formed JSON with
evidence URLs and a normal `end_turn` stop reason for the affected companies — the model did
its job. The response text was wrapped in a markdown ` ```json ... ``` ` fence, which is a
documented, common completion shape for a model asked to "return only JSON" without a
constraining response format. `Validate Research Output` (`ENRICH_VALIDATE_RESEARCH` in
`scripts/build_cloud_workflows.py`) parses the response with a bare JSON parse and no fence
strip, so it failed to parse and the row was marked `research_failed`.

Downstream consequence, observed live: several companies were left with `lv_org_type=None`
because the (correct, available) web research answer was thrown away, and at least one
`no_content` veto fired spuriously — a `governing_body_league` classification that DID have
content, but the classification itself never survived validation, so a stale/absent
`produces_content` fell through to the veto.

`src/web_research.py::_extract_json` (the Python oracle) already handles this case — it strips
a leading/trailing ` ```(json)? ` fence with a regex before attempting `json.loads`, falling
back to a `{...}` regex extraction if that still fails. The parity gap is that the JS wrapper
emitted by `ENRICH_VALIDATE_RESEARCH` was never given the equivalent strip.

## Fix (not designed here)

Port `_extract_json`'s fence-strip (and ideally its brace-extraction fallback) into the JS
validator emitted by `ENRICH_VALIDATE_RESEARCH`, in `scripts/build_cloud_workflows.py` — this
is a Phase 46 parity pair (`src/web_research.py` <-> the n8n JS engine), so the fix belongs in
both, in one commit, per the project's standing parity rule. Needs a regression fixture with a
fenced-JSON research response asserting `Validate Research Output` accepts it, and a companion
Python test if `_extract_json`'s own coverage doesn't already pin the fenced case.
