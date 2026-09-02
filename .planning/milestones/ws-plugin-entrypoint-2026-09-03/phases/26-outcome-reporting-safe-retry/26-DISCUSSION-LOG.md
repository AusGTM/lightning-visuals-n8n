# Phase 26: Outcome Reporting & Safe Retry - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 26-outcome-reporting-safe-retry
**Areas discussed:** Outcome source, Retry safety, Re-check mechanism, Report presentation

---

## Outcome source

| Option | Description | Selected |
|--------|-------------|----------|
| Sync response first, executions API as fallback | Parse per-row items from the webhook; fall back to GET /api/v1/executions with the n8n API key on timeout or partial. Covers criterion 3's in-flight case. | ✓ |
| Sync webhook response only | Simplest; a batch outrunning the webhook timeout has no path to its outcome. | |
| Always poll the executions API | Uniform, in-flight works naturally; adds a poll loop to every send. | |

**User's choice:** Sync first, executions API fallback
**Notes:** Recommended option taken as-is.

---

## Retry safety

| Option | Description | Selected |
|--------|-------------|----------|
| Backend identity resolution already does | n8n resolves identity and routes update-vs-create per row, so a re-sent accepted row updates in place. Client re-sends the failed batch. No second dedupe authority. | ✓ |
| Client tracks accepted rows and excludes them | Explicit in the client; builds a second dedupe authority that can drift. | |
| Both | Belt and braces; same drift risk plus carried state. | |

**User's choice:** Backend identity resolution
**Notes:** Recommended option taken as-is. Consistent with the milestone's scope anchor.

---

## Re-check mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Run handle shown, operator asks to re-check | Report prints an execution reference; re-check is manual. Keeps the bounded watch in Phase 29 where it belongs. | ✓ |
| Auto-poll until settled, in this phase | Better immediate UX; duplicates NOTICE-01 and pulls Phase 29 scope forward. | |
| Re-check by re-running the report command | No handle; ambiguous once there's been more than one run. | |

**User's choice:** Run handle, manual re-check
**Notes:** Recommended option taken as-is. D-07 explicitly forbids a poll loop in this phase.

---

## Report presentation

| Option | Description | Selected |
|--------|-------------|----------|
| Summary counts + drill-down on request | Counts first, failing rows in full, complete detail on request. Mirrors Phase 23 D-08's adaptive convention. | ✓ |
| Full per-record table always | Nothing hidden; buries actionable failures in a 500-row table. | |
| Always publish as an Artifact | Good for wide tables; costs a publish per send when the actionable part is short. | |

**User's choice:** Summary counts + drill-down
**Notes:** Recommended option taken as-is.

---

## Claude's Discretion

- Outcome label wording, provided it maps to created / updated-matched / needs_review / rejected
- Run-handle format and re-check phrasing
- Timeout threshold triggering the executions-API fallback
- Chat vs Artifact for the drill-down
- Grouping of rejected-row reasons when many rows share a cause

## Deferred Ideas

- Unprompted in-session watch — Phase 29 / NOTICE-01, NOTICE-02
- Client-side accepted-row tracking — rejected as a second dedupe authority
- Scheduled sweep reporting — Phase 29 / NOTICE-03
- Full backend health context in reports — Phase 27
