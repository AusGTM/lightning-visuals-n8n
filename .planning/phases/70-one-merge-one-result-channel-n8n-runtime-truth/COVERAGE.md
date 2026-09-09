# Phase 70 — API Coverage Decision

No external API integration: this phase re-plumbs the n8n graph and the client's result
channel over calls that already exist (HubSpot CRM v3 via existing HTTP/HubSpot nodes, the
provider APIs via existing adapters, and the n8n Executions API the client already reads
through `operator-claude-plugin/scripts/executions_client.py`). No new API, SDK or service
is added, and no new capability of an existing API is reached for the first time.
