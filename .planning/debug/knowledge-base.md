# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## empty-evidence-by-field — closed-won smoke reported evidence_by_field empty for every company
- **Date:** 2026-07-21
- **Error patterns:** evidence_by_field, empty evidence, lv_produces_content, stop_reason, max_tokens, USE_MOCK_WEB_RESEARCH, setdefault, mock fixture, live smoke, identical verdicts, claude_web_research
- **Root cause:** PRIMARY: scripts/smoke_closed_won_research.py used `os.environ.setdefault("USE_MOCK_WEB_RESEARCH", "false")` to force live research mode, but the documented run command sources `.env` first (which sets `USE_MOCK_WEB_RESEARCH=true`), so the key was already present and `setdefault` silently no-op'd — every "live" run was actually replaying the static mock fixture (identical data for every company, no `evidence_by_field` key since the fixture predates that field). SECONDARY (real, independently confirmed): `max_tokens=2000` for the live Claude web-research call is insufficient once live calls do happen — claude-sonnet-5's extended thinking consumes ~1000-1300 tokens on this prompt, causing `stop_reason=max_tokens` truncation that drops `evidence_by_field` (emitted after the `data` block) before the JSON closes.
- **Fix:** (1) Changed `os.environ.setdefault(...)` to direct assignment `os.environ["USE_MOCK_WEB_RESEARCH"] = "false"` in scripts/smoke_closed_won_research.py. (2) Raised `max_tokens` 2000->4096 in both src/web_research.py (Python dev oracle) and scripts/build_cloud_workflows.py (n8n production prompt, parity requirement), rebuilt n8n workflows.
- **Files changed:** scripts/smoke_closed_won_research.py, src/web_research.py, scripts/build_cloud_workflows.py, n8n/wf_enrichment_local_live.json
---
