# Phase 57 — API Coverage Matrix

The deterministic detector returned `detected: true` (signals: `rest`, `api`). This phase
integrates **no new** external API, but it does consume three already-integrated ones. The
matrix below is the subtraction record: one row per capability of each surface, `INTEGRATE`
or `OPT-OUT` with a reason.

## n8n Cloud Public API (`/api/v1/...`, via `operator-claude-plugin/scripts/n8n_read.py` and `executions_client.py`)

| Capability | Disposition | Reason |
|---|---|---|
| `GET /executions` (list, cursor-paginated) | INTEGRATE | RUN-05's month-to-date sample — `n8n_read.executions_in_window`, the only source of "what has this month already spent" |
| `GET /executions/{id}` | OPT-OUT | already used by `report_enrichment` for per-execution detail; a ceiling needs counts, not bodies |
| `DELETE /executions/{id}` | OPT-OUT | destructive; this phase never prunes execution history |
| `GET /workflows`, `GET /workflows/{id}` | INTEGRATE | unchanged existing use — workflow-id resolution and guardrail A's live write-safety read |
| `PUT /workflows/{id}` | INTEGRATE | one disarmed redeploy only, to carry the `row_id` field added to `Build Ingest Response` (plan 57-02) |
| `POST /workflows/{id}/activate` + `/deactivate` | INTEGRATE | the bounce a stored change needs to actually run (a bare PUT never reloads a running workflow) |
| `GET/POST /credentials` | OPT-OUT | this phase reads no credential body and mints none |
| `GET /users`, `/projects`, `/variables`, `/tags`, `/source-control` | OPT-OUT | no operator, project, variable, tag or source-control surface is in this phase's scope |
| `GET /audit` | OPT-OUT | n8n's security audit report is unrelated to execution budgeting |
| billing / usage quota | UNAVAILABLE | no such endpoint exists on this plan (P-05/P-12). This absence is *why* the allowance is sampled from the executions list and never read authoritatively — CLAUDE.md §13.0.3: "the executions API list is not the billing quota" |

## Provider balance APIs (read-only credit checks, called backend-side by the deployed workflow)

| Capability | Disposition | Reason |
|---|---|---|
| Lusha `GET v3/account/usage` (`credits.remaining`) | INTEGRATE | already working; the one readable balance, unchanged by this phase |
| ZoomInfo `GET gtm/data/v1/users/usage` | INTEGRATE — re-probe only | G-4. Read-only, never writes, spends no credit. The historically-documented cause (missing `Accept: application/vnd.api+json`) is already fixed in current code, so the 2026-08-25 `provider_error` needs a live observation, not a code change |
| Apollo `POST usage_stats/api_usage_stats` | OPT-OUT | 403 by design for a non-master API key. Structurally unfixable in this repo; disclosed as a permanent blind spot per D-57-02 rather than papered over |

## Other external surfaces deliberately not touched

| Surface | Disposition | Reason |
|---|---|---|
| HubSpot CRM API (`crm/v3`, `crm/v4`) | OPT-OUT | this phase writes no HubSpot property, adds no canonical-write path, and may not arm a write |
| Anthropic Messages API | OPT-OUT | no usage read-back exists anywhere in this repo, which is why the `$` ceiling figure stays labelled `PROJECTED` and never becomes `MEASURED` |
